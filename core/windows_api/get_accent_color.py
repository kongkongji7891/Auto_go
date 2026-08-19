"""
accent_color.py — 获取 Windows 系统强调色的十六进制色号

使用方式：
    from accent_color import get_accent_color
    hex_color = get_accent_color()          # 如 '#0078D4'
    hex_color = get_accent_color(default='#0078D4')

依赖：仅 Python 标准库（winreg），适用于 Windows 10/11。
"""

import sys
import winreg
from typing import Tuple, Optional

# 注册表路径和键名
_DWM_REG_PATH = r"Software\Microsoft\Windows\DWM"
_ACCENT_COLOR_KEY = "AccentColor"

def _read_accent_dword() -> Optional[int]:
    """
    从注册表读取 AccentColor 的 DWORD 值。
    返回整数或 None（读取失败时）。
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _DWM_REG_PATH) as key:
            value, _ = winreg.QueryValueEx(key, _ACCENT_COLOR_KEY)
            return value
    except (FileNotFoundError, OSError, PermissionError):
        return None

def _abgr_to_rgb_hex(abgr: int) -> str:
    """
    将 ABGR 格式的 DWORD 转换为 '#RRGGBB' 字符串。
    ABGR 字节顺序：低8位=R，其次G，其次B，最高8位=A。
    """
    r = abgr & 0xFF
    g = (abgr >> 8) & 0xFF
    b = (abgr >> 16) & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"

def get_accent_color(default: str = "#0078D4") -> str:
    """
    获取 Windows 当前强调色的十六进制色号（大写字母，如 '#0078D4'）。
    
    参数：
        default: 读取失败时返回的默认色号（Windows 经典蓝）。
    
    返回：
        str: 形如 '#RRGGBB' 的色号。
    """
    if sys.platform != "win32":
        return default
    
    dword = _read_accent_dword()
    if dword is None:
        return default
    
    try:
        return _abgr_to_rgb_hex(dword)
    except Exception:
        return default

def get_accent_rgb(default: Tuple[int, int, int] = (0, 120, 212)) -> Tuple[int, int, int]:
    """
    获取 Windows 当前强调色的 RGB 元组 (R, G, B)。
    """
    if sys.platform != "win32":
        return default
    
    dword = _read_accent_dword()
    if dword is None:
        return default
    
    try:
        r = dword & 0xFF
        g = (dword >> 8) & 0xFF
        b = (dword >> 16) & 0xFF
        return (r, g, b)
    except Exception:
        return default

# 模块测试
if __name__ == "__main__":
    print("强调色十六进制:", get_accent_color())
    print("强调色 RGB:", get_accent_rgb())