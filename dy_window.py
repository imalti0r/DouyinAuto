# -*- coding: utf-8 -*-
"""窗口定位与屏幕截图：win32 查找抖音窗口 + mss 快速截图"""
import ctypes
import sys

import numpy as np
import win32con
import win32gui
from mss import mss


def ensure_dpi_aware():
    """让本进程感知 DPI，保证窗口坐标与物理像素一致"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def find_window(title_keyword):
    """按标题模糊查找窗口，返回 (hwnd, (x, y, w, h))；找不到返回 (None, None)"""
    def enum_handler(hwnd, result):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_keyword in title:
                result.append(hwnd)

    hits = []
    win32gui.EnumWindows(enum_handler, hits)
    if not hits:
        return None, None
    hwnd = hits[0]
    rect = win32gui.GetWindowRect(hwnd)  # (l, t, r, b)
    x, y = rect[0], rect[1]
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    return hwnd, (x, y, w, h)


def get_hwnd_rect(hwnd):
    """按 hwnd 实时获取窗口区域 (x, y, w, h)，窗口已关闭返回 None"""
    try:
        if not win32gui.IsWindow(hwnd):
            return None
        rect = win32gui.GetWindowRect(hwnd)
        x, y = rect[0], rect[1]
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        if w < 200 or h < 200:
            return None
        return (x, y, w, h)
    except Exception:
        return None


def get_foreground_hwnd():
    """当前前台窗口句柄"""
    return win32gui.GetForegroundWindow()


def is_foreground(hwnd):
    """指定窗口是否在前台"""
    try:
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def get_screen_rect():
    """整个主屏幕区域（找不到窗口时的回退方案）"""
    user32 = ctypes.windll.user32
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return (0, 0, w, h)


def activate_window(hwnd):
    """尽力把窗口带到前台（失败不影响主流程）"""
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # Windows 前台锁定：按一次 Alt 解锁后再置前
            import pydirectinput
            pydirectinput.press("alt")
            win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        print(f"[warn] 无法置前窗口: {e}")
        return False


class ScreenCapture:
    """mss 截图封装，输出 BGR ndarray"""

    def __init__(self):
        self._sct = mss()

    def grab(self, region):
        """region: (x, y, w, h) → np.ndarray (BGR)"""
        x, y, w, h = region
        shot = self._sct.grab({"left": x, "top": y, "width": w, "height": h})
        frame = np.asarray(shot, dtype=np.uint8)  # BGRA
        return frame[:, :, :3].copy()  # BGR


if __name__ == "__main__":
    # 自测：找到抖音窗口并保存一张截图
    ensure_dpi_aware()
    hwnd, rect = find_window("抖音")
    if rect is None:
        print("未找到抖音窗口，回退到主屏幕")
        rect = get_screen_rect()
    else:
        print(f"找到窗口 hwnd={hwnd}, rect={rect}")
    cap = ScreenCapture()
    frame = cap.grab(rect)
    import cv2
    cv2.imwrite("debug_window.png", frame)
    print(f"截图已保存 debug_window.png ({frame.shape[1]}x{frame.shape[0]})")
