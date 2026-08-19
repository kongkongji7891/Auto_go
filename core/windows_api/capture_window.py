"""
foxgo_window.py - 基于 WGC (wgcapture) 的窗口截图工具
使用 SetWindowPos 强制取消最小化（参考 layout.py 的 SetWindowPos 逻辑）
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)
_user32 = ctypes.windll.user32

# Win32 常量
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_SHOWWINDOW = 0x0040

try:
    from wgcapture import capture_screen
    _WGCAPTURE_AVAILABLE = True
except ImportError:
    _WGCAPTURE_AVAILABLE = False
    log.error("wgcapture 未安装，请运行: pip install wgcapture")


def _force_unminimize_with_setwindowpos(hwnd: int) -> bool:
    """使用 SetWindowPos 强制取消窗口最小化"""
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long), ("top", ctypes.c_long),
            ("right", ctypes.c_long), ("bottom", ctypes.c_long),
        ]
    class WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_uint),
            ("flags", ctypes.c_uint),
            ("showCmd", ctypes.c_uint),
            ("ptMinPosition", POINT),
            ("ptMaxPosition", POINT),
            ("rcNormalPosition", RECT),
        ]

    wp = WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(WINDOWPLACEMENT)
    if not _user32.GetWindowPlacement(hwnd, ctypes.byref(wp)):
        log.warning("GetWindowPlacement 失败")
        return False

    left = wp.rcNormalPosition.left
    top = wp.rcNormalPosition.top
    width = wp.rcNormalPosition.right - wp.rcNormalPosition.left
    height = wp.rcNormalPosition.bottom - wp.rcNormalPosition.top

    log.debug(f"正常位置: ({left},{top}) {width}x{height}")

    flags = _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_SHOWWINDOW
    result = _user32.SetWindowPos(
        hwnd, 0,
        left, top, width, height,
        flags
    )
    if not result:
        log.warning(f"SetWindowPos 返回 {result}, LastError={ctypes.GetLastError()}")
        return False

    log.info("SetWindowPos 成功，窗口已恢复")
    return True


def _is_window_minimized(hwnd: int) -> bool:
    """检查窗口是否最小化"""
    if _user32.IsIconic(hwnd):
        return True
    try:
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]
        class WINDOWPLACEMENT(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_uint),
                ("flags", ctypes.c_uint),
                ("showCmd", ctypes.c_uint),
                ("ptMinPosition", POINT),
                ("ptMaxPosition", POINT),
                ("rcNormalPosition", RECT),
            ]
        wp = WINDOWPLACEMENT()
        wp.length = ctypes.sizeof(WINDOWPLACEMENT)
        if _user32.GetWindowPlacement(hwnd, ctypes.byref(wp)):
            if wp.showCmd == 2:  # SW_SHOWMINIMIZED
                return True
    except Exception:
        pass
    return False


def _find_window_title_by_keyword(keyword: str) -> Optional[str]:
    _EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    found_title = [None]

    def _enum_cb(hwnd: int, _lparam: int) -> bool:
        if not _user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(1024)
        _user32.GetWindowTextW(hwnd, buf, 1024)
        if keyword in buf.value:
            found_title[0] = buf.value
            return False
        return True

    _user32.EnumWindows(_EnumWindowsProc(_enum_cb), 0)
    return found_title[0]


def _find_hwnd_by_title_keyword(keyword: str) -> Optional[int]:
    _EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    found_hwnd = [0]

    def _enum_cb(hwnd: int, _lparam: int) -> bool:
        if not _user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(1024)
        _user32.GetWindowTextW(hwnd, buf, 1024)
        if keyword in buf.value:
            found_hwnd[0] = hwnd
            return False
        return True

    _user32.EnumWindows(_EnumWindowsProc(_enum_cb), 0)
    return found_hwnd[0] if found_hwnd[0] else None


def _check_capture_protection(hwnd: int) -> bool:
    affinity = ctypes.wintypes.DWORD()
    if _user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(affinity)):
        return affinity.value == 0x11
    return False


class CaptureWindow:
    def __init__(self, hwnd: Optional[int] = None, title: Optional[str] = None):
        self._hwnd: int = 0
        self._window_title: Optional[str] = None
        self._last_error: Optional[str] = None

        if not _WGCAPTURE_AVAILABLE:
            raise ImportError("wgcapture 未安装")

        if title is not None:
            full_title = _find_window_title_by_keyword(title)
            if full_title:
                self._window_title = full_title
                self._hwnd = _find_hwnd_by_title_keyword(title) or 0
                log.info(f"通过标题找到窗口: '{full_title}', hwnd={self._hwnd}")
            else:
                raise ValueError(f"未找到标题包含 '{title}' 的窗口")
        elif hwnd is not None:
            self._hwnd = hwnd
            buf = ctypes.create_unicode_buffer(1024)
            _user32.GetWindowTextW(hwnd, buf, 1024)
            self._window_title = buf.value
            if not self._window_title:
                raise ValueError(f"无法获取 hwnd={hwnd} 的窗口标题")
        else:
            raise ValueError("必须提供 hwnd 或 title 参数")

        if self._hwnd and _check_capture_protection(self._hwnd):
            log.warning("目标窗口启用了 WDA_EXCLUDEFROMCAPTURE，WGC 也将返回黑屏")

    @property
    def hwnd(self) -> int:
        return self._hwnd

    def capture(self) -> Optional[np.ndarray]:
        """
        使用 WGC 捕获窗口内容，返回 BGR numpy 数组。
        """
        if not self._window_title:
            self._last_error = "窗口标题为空"
            return None

        # 1. 处理最小化
        if self._hwnd and _is_window_minimized(self._hwnd):
            log.info("检测到窗口最小化，使用 SetWindowPos 强制恢复...")
            if not _force_unminimize_with_setwindowpos(self._hwnd):
                self._last_error = "SetWindowPos 恢复失败"
                log.error(self._last_error)
                return None
            time.sleep(0.3)
            buf = ctypes.create_unicode_buffer(1024)
            _user32.GetWindowTextW(self._hwnd, buf, 1024)
            if buf.value:
                self._window_title = buf.value

        if self._hwnd and _is_window_minimized(self._hwnd):
            self._last_error = "窗口仍处于最小化状态，无法捕获"
            log.error(self._last_error)
            return None

        # 2. 多次尝试捕获（不保存任何图片）
        last_exception = None
        for attempt in range(3):
            try:
                img_rgba = capture_screen(screen=self._window_title)
                if img_rgba is not None:
                    h, w = img_rgba.shape[:2]
                    if h == 0 or w == 0:
                        last_exception = "捕获到空图像"
                        log.warning(f"第 {attempt+1} 次: 空图像，重试...")
                    else:
                        img_bgr = img_rgba[:, :, :3][:, :, ::-1]
                        log.debug(f"WGC 截图成功，尺寸: {w}x{h}")
                        return img_bgr
                else:
                    last_exception = "wgcapture 返回 None"
                    log.warning(f"第 {attempt+1} 次: None，重试...")
            except Exception as e:
                last_exception = f"WGC 捕获异常: {e}"
                log.warning(f"第 {attempt+1} 次失败: {e}")
            time.sleep(0.3)

        self._last_error = f"WGC 捕获失败（3次重试后）: {last_exception}"
        log.error(self._last_error)
        return None

    def release(self):
        """释放窗口引用及相关资源"""
        if self._hwnd != 0:
            log.info(f"释放窗口: hwnd={self._hwnd}, title='{self._window_title}'")
            self._hwnd = 0
            self._window_title = None
            self._last_error = None
        else:
            log.debug("release 调用时窗口已释放或无资源")

    def __del__(self):
        try:
            self.release()
        except Exception:
            pass