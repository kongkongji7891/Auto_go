"""
katago_gtp.py - KataGo GTP 模式封装库（增强版）
基于标准 GTP 命令，支持落子、设置棋盘、AI 推荐、形势判断、棋盘状态获取。
自带线程和任务队列，命令串行执行，调用者阻塞等待结果。
"""
from __future__ import annotations

import logging
import re
import subprocess
import time
import threading
import queue
from pathlib import Path
from typing import List, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

# 围棋坐标字母表（跳过 I）
_COLS = "ABCDEFGHJKLMNOPQRST"


class _Task:
    """内部任务单元"""
    def __init__(self, command: str):
        self.command = command
        self.result: Tuple[bool, str] = (False, "")
        self.event = threading.Event()


class KataGoGTP:
    """
    KataGo GTP 模式封装，线程安全。
    所有公共方法返回 bool 表示操作是否成功（或相应类型的结果）。
    调用时会阻塞直到命令执行完毕，但实际 GTP 通信在后台线程进行。
    """

    def __init__(
        self,
        katago_path: str,
        model_path: str,
        config_path: Optional[str] = None,
        board_size: int = 19,
        komi: float = 7.5,
        rules: str = "chinese",
        auto_restart: bool = False,
        crash_callback: Optional[Callable[[], None]] = None,
    ):
        self.katago_path = Path(katago_path).resolve()
        self.model_path = Path(model_path).resolve()
        self.config_path = Path(config_path).resolve() if config_path else None
        self.board_size = board_size
        self.komi = komi
        self.rules = rules
        self.auto_restart = auto_restart
        self._crash_callback = crash_callback
        self._process: Optional[subprocess.Popen] = None
        self._last_command_ok = True

        # 任务队列和工作线程
        self._task_queue: queue.Queue[_Task] = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown = False

        self._start_process_and_worker()

    def _start_process_and_worker(self):
        """启动 KataGo 进程和工作线程"""
        self._start_kata_process()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _start_kata_process(self):
        """启动 KataGo 进程并初始化（直接发送命令，不经过队列，避免死锁）"""
        cmd = [str(self.katago_path), "gtp", "-model", str(self.model_path)]
        if self.config_path:
            cmd.extend(["-config", str(self.config_path)])
        # 强制启用分析和得分功能（即使配置文件中未设置或设为 false）
        cmd.extend([
            "-override-config", "allowAnalyze=true",
            "-override-config", "allowScore=true"
        ])
        logger.info(f"启动 KataGo GTP: {' '.join(cmd)}")
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        time.sleep(0.5)
        if self._process.poll() is not None:
            err = self._process.stderr.read()
            raise RuntimeError(f"KataGo 启动失败: {err}")
        # 直接发送初始化命令（不经过队列）
        init_commands = [
            f"boardsize {self.board_size}",
            f"kata-set-rules {self.rules}",
            f"komi {self.komi}",
            "clear_board",
        ]
        for cmd_text in init_commands:
            ok, msg = self._send_raw_internal(cmd_text)
            if not ok:
                raise RuntimeError(f"初始化命令失败: {cmd_text} - {msg}")
        self._last_command_ok = True

    def _worker_loop(self):
        """工作线程主循环：不断从队列取任务并执行"""
        while not self._shutdown:
            try:
                task = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if task.command == "_QUIT_":
                break
            # 确保进程存活
            if self._process is None or self._process.poll() is not None:
                if self.auto_restart:
                    logger.warning("KataGo 进程已终止，正在重启...")
                    self._start_kata_process()  # 重启（直接发送命令，不会死锁）
                    # 重启后调用回调
                    if self._crash_callback:
                        self._crash_callback()
                    # 重新执行当前任务（否则当前任务会丢失）
                    result = self._send_raw_internal(task.command)
                    task.result = result
                    task.event.set()
                    continue
                else:
                    task.result = (False, "KataGo 进程已终止")
                    task.event.set()
                    continue
            # 执行命令
            result = self._send_raw_internal(task.command)
            task.result = result
            task.event.set()
        # 清理
        self._cleanup_process()

    def _send_raw_internal(self, command: str) -> Tuple[bool, str]:
        """内部执行 GTP 命令（在工作线程中调用）"""
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()
        lines = []
        while True:
            line = self._process.stdout.readline().strip()
            if line == "":
                break
            lines.append(line)
        if not lines:
            return False, "无响应"
        first_line = lines[0]
        if first_line.startswith("?"):
            return False, first_line[2:].strip()
        result = first_line[2:] if first_line.startswith("= ") else first_line
        if len(lines) > 1:
            result += "\n" + "\n".join(lines[1:])
        return True, result.strip()

    def _execute_task(self, command: str) -> Tuple[bool, str]:
        """公共方法调用此函数：创建任务、入队、等待结果"""
        task = _Task(command)
        self._task_queue.put(task)
        task.event.wait()
        return task.result

    # ========== 公共接口 ==========

    def is_idle(self) -> bool:
        """检查引擎是否空闲（上一条命令是否成功）"""
        return self._last_command_ok

    def set_max_visits(self, visits: int) -> bool:
        """动态设置每手最大搜索访问次数"""
        ok, msg = self._execute_task(f"kata-set-param maxVisits {visits}")
        self._last_command_ok = ok
        if not ok:
            logger.warning(f"设置 maxVisits 失败: {msg}")
        return ok

    def play_move(self, row: int, col: int, color: str) -> bool:
        """
        在棋盘坐标 (row, col) 落子。
        :param row: 0~18
        :param col: 0~18
        :param color: "black"/"white" 或 "b"/"w"
        :return: 是否成功
        """
        if not (0 <= row < 19 and 0 <= col < 19):
            self._last_command_ok = False
            return False
        vertex = f"{_COLS[col]}{19 - row}"
        ok, msg = self._execute_task(f"play {self._color_full(color)} {vertex}")
        self._last_command_ok = ok
        if not ok:
            logger.warning(f"落子失败: {msg}")
        return ok

    def set_board_from_array(self, board: List[List[int]]) -> bool:
        """
        通过 19x19 二维数组设置棋盘状态。
        board[r][c]: 0=空, 1=黑, 2=白
        :return: 是否成功
        """
        if len(board) != 19 or any(len(row) != 19 for row in board):
            self._last_command_ok = False
            return False
        # 清空棋盘
        ok, _ = self._execute_task("clear_board")
        if not ok:
            self._last_command_ok = False
            return False
        black_pos, white_pos = [], []
        for r in range(19):
            for c in range(19):
                if board[r][c] == 1:
                    black_pos.append((r, c))
                elif board[r][c] == 2:
                    white_pos.append((r, c))
        i, j = 0, 0
        while i < len(black_pos) or j < len(white_pos):
            if i < len(black_pos):
                r, c = black_pos[i]
                vertex = f"{_COLS[c]}{19 - r}"
                ok, msg = self._execute_task(f"play black {vertex}")
                if not ok:
                    self._last_command_ok = False
                    logger.warning(f"设置棋盘失败: {msg}")
                    return False
                i += 1
            if j < len(white_pos):
                r, c = white_pos[j]
                vertex = f"{_COLS[c]}{19 - r}"
                ok, msg = self._execute_task(f"play white {vertex}")
                if not ok:
                    self._last_command_ok = False
                    logger.warning(f"设置棋盘失败: {msg}")
                    return False
                j += 1
        self._last_command_ok = True
        return True

    def get_ai_recommendation(self, color: str) -> Optional[Tuple[int, int]]:
        """
        获取 AI 推荐的下子坐标（不改变棋盘状态）。
        :param color: 当前轮到哪一方
        :return: (row, col) 或 None（如果失败或 pass）
        """
        ok, move_str = self._execute_task(f"genmove {self._color_full(color)}")
        if not ok:
            self._last_command_ok = False
            return None
        # 立即撤销
        self._execute_task("undo")  # 忽略结果
        if move_str == "pass" or move_str == "resign":
            self._last_command_ok = True
            return None
        try:
            col = _COLS.index(move_str[0].upper())
            row = 19 - int(move_str[1:])
            self._last_command_ok = True
            return (row, col)
        except (ValueError, IndexError):
            self._last_command_ok = False
            return None

    def get_evaluation(self, color: str) -> Tuple[float, float]:
        """
        获取当前形势的目差和胜率。
        :param color: 当前轮到哪一方（仅用于日志，实际 kata-analyze 会自动识别）
        :return: (score_lead, winrate) 目差（从当前方角度），胜率 0~1
                 如果获取失败，返回 (0.0, 0.0)
        """
        ok, resp = self._execute_task("kata-analyze 1000 100")
        if ok:
            logger.debug(f"kata-analyze 原始响应:\n{resp}")
            score_lead = 0.0
            winrate = 0.0
            for line in resp.splitlines():
                if line.startswith("rootInfo"):
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "winrate" and i + 1 < len(parts):
                            wr = float(parts[i+1])
                            winrate = wr / 10000.0 if wr > 1.0 else wr
                        elif p == "scoreLead" and i + 1 < len(parts):
                            score_lead = float(parts[i+1])
                    break  # 只取第一条 rootInfo
            self._last_command_ok = True
            return (score_lead, winrate)
        else:
            logger.debug(f"kata-analyze 失败，原始响应: {resp}")
            self._last_command_ok = False
            return (0.0, 0.0)

    def get_board_state(self) -> List[List[int]]:
        """
        获取当前棋盘状态二维数组。
        :return: 19x19 数组，0=空, 1=黑, 2=白
        """
        ok, board_str = self._execute_task("showboard")
        if not ok:
            self._last_command_ok = False
            return [[0]*19 for _ in range(19)]

        logger.debug(f"showboard 原始输出:\n{repr(board_str)}")

        board = [[0]*19 for _ in range(19)]
        lines = board_str.splitlines()
        row_idx = 0
        for line in lines:
            # 使用正则提取所有 X, O, . 字符（忽略数字、空格等）
            symbols = re.findall(r'[XO.]', line)
            if len(symbols) == 19:
                for c, sym in enumerate(symbols):
                    if sym == 'X' or sym == 'x':
                        board[row_idx][c] = 1
                    elif sym == 'O' or sym == 'o':
                        board[row_idx][c] = 2
                    else:
                        board[row_idx][c] = 0
                row_idx += 1
                if row_idx >= 19:
                    break

        self._last_command_ok = True
        logger.debug(f"解析后的棋盘前5行: {board[:5]}")
        return board

    def _cleanup_process(self):
        """清理 KataGo 进程"""
        if self._process and self._process.poll() is None:
            try:
                self._process.stdin.write("quit\n")
                self._process.stdin.flush()
            except:
                pass
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def close(self):
        """关闭引擎，停止工作线程"""
        self._shutdown = True
        # 发送退出任务
        quit_task = _Task("_QUIT_")
        self._task_queue.put(quit_task)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        # 确保进程已清理
        self._cleanup_process()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def _color_full(color: str) -> str:
        mapping = {"b": "black", "w": "white", "black": "black", "white": "white"}
        return mapping.get(color.lower(), color)


# 坐标转换工具

def coord_to_gtp(row: int, col: int, board_size: int = 19) -> str:
    return f"{_COLS[col]}{board_size - row}"

def gtp_to_coord(gtp: str, board_size: int = 19) -> Tuple[int, int]:
    col = _COLS.index(gtp[0].upper())
    row = board_size - int(gtp[1:])
    return row, col