"""
uac_utils.py - 自动请求 UAC 提升权限的工具函数
使用 ShellExecuteEx 以 runas 动词重新启动当前脚本。
"""
import ctypes
import os
import sys
import win32api
import win32con
import win32process
import win32event
from win32com.shell import shell, shellcon
import logging

logger = logging.getLogger(__name__)

def is_admin() -> bool:
    """检查当前进程是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def request_uac(script_path: str = None) -> None:
    """
    请求 UAC 提升：以管理员身份重新启动当前脚本，并终止当前进程。
    
    :param script_path: 要执行的脚本路径，默认为当前脚本（sys.argv[0]）
    """
    if is_admin():
        # 已经是管理员，无需提升
        return

    if script_path is None:
        script_path = sys.argv[0]
    
    # 构建命令行参数（保留原始参数）
    args = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
    
    #使用 ShellExecuteEx 以 runas 动词启动
    try:
        shell.ShellExecuteEx(
            lpVerb='runas',
            lpFile=sys.executable,
            lpParameters=f'"{script_path}" {args}',
            nShow=win32con.SW_SHOWNORMAL
        )
    except Exception as e:
        # 如果用户拒绝UAC或出错,提示错误并退出
        if str(e) == """(1223, 'ShellExecuteEx', '操作已被用户取消。')""":
            logger.warning("用户拒绝获取管理员权限")
        else:
            raise e
        sys.exit(1)
    
    # 退出当前非管理员进程
    sys.exit(0)


def ensure_admin_and_run(main_func):
    """
    装饰器：确保以管理员权限运行 main_func。
    用法：
        @ensure_admin_and_run
        def main():
            ...
    """
    def wrapper(*args, **kwargs):
        if not is_admin():
            request_uac()
            # request_uac 会退出当前进程，以下不会执行
        return main_func(*args, **kwargs)
    return wrapper