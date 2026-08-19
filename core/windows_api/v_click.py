"""
v_click.py - 基于 win32api PostMessage 的后台窗口点击
使用 PostMessage 投递鼠标消息，不受 UIPI 权限限制，不抢占前台焦点。
"""
from __future__ import annotations

import logging
import time
from typing import Literal, Tuple

import win32api
import win32con
import win32gui

log = logging.getLogger(__name__)

# 按键消息映射
_BUTTON_DOWN = {
    'left': win32con.WM_LBUTTONDOWN,
    'right': win32con.WM_RBUTTONDOWN,
    'middle': win32con.WM_MBUTTONDOWN,
}
_BUTTON_UP = {
    'left': win32con.WM_LBUTTONUP,
    'right': win32con.WM_RBUTTONUP,
    'middle': win32con.WM_MBUTTONUP,
}
_BUTTON_MK = {
    'left': win32con.MK_LBUTTON,
    'right': win32con.MK_RBUTTON,
    'middle': win32con.MK_MBUTTON,
}


class SimulatedMouse:
    """
    向指定窗口发送后台鼠标点击消息。
    使用 PostMessage 投递到窗口消息队列，不抢占焦点，不受 UIPI 限制。
    """

    def __init__(self, hwnd: int):
        """
        :param hwnd: 目标窗口的句柄（顶层窗口即可）
        """
        self._hwnd = hwnd
        # 不再需要存储窗口位置，PostMessage 使用客户区坐标

    def mouse_input(self,
                    button: Literal['left', 'right', 'middle'],
                    position: Tuple[int, int]) -> None:
        """
        在窗口客户区指定位置模拟鼠标点击（后台消息投递）。

        :param button: 'left' / 'right' / 'middle'
        :param position: 相对窗口客户区坐标 (x, y)
        :raises ValueError: 如果 button 无效
        """
        if button not in _BUTTON_DOWN:
            raise ValueError(f"不支持的按键: {button}")
        
        x, y = position

        #记录原坐标
        o_x, o_y = win32api.GetCursorPos()
        win32api.SetCursorPos((x, y))

        # lParam 低位是 x，高位是 y，使用客户区坐标
        lparam = win32api.MAKELONG(x, y)
        
        #处理正确的位置
        left, top, right, bottom = win32gui.GetWindowRect(self._hwnd)
        x += left
        y += top
        win32api.SetCursorPos((x,y))
        log.debug(f"投递消息到句柄: {self._hwnd}")

        down_msg = _BUTTON_DOWN[button]
        up_msg = _BUTTON_UP[button]
        mk = _BUTTON_MK[button]

        # 模拟点击
        win32api.PostMessage(self._hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
        win32api.PostMessage(self._hwnd, down_msg, mk, lparam)
        time.sleep(0.03)
        win32api.PostMessage(self._hwnd, up_msg, 0, lparam)
        #移回原位
        win32api.SetCursorPos((o_x,o_y))
        log.info(f"点击 {button} 于 ({x},{y}) 已投递")

    def __repr__(self) -> str:
        return f"<SimulatedMouse hwnd={self._hwnd}>"