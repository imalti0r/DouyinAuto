# -*- coding: utf-8 -*-
"""模拟输入：pydirectinput（SendInput 扫描码方式，兼容性最好）
滚轮为原生 ctypes SendInput 实现（旧版 pydirectinput 无 scroll 接口）"""
import ctypes
import random
import time

import pydirectinput

pydirectinput.PAUSE = 0.05
pydirectinput.FAILSAFE = False  # 程序自己控制鼠标，关闭角落急停

_INPUT_MOUSE = 0
_MOUSEEVENTF_WHEEL = 0x0800
_WHEEL_DELTA = 120


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _InputUnion)]


def _send_wheel(clicks):
    """SendInput 滚轮事件：clicks 正=向上、负=向下（每个 notch=120，逐格发送更拟人）"""
    notches = int(clicks)
    for _ in range(abs(notches)):
        cmd = _Input()
        cmd.type = _INPUT_MOUSE
        cmd.union.mi = _MouseInput(
            0, 0, _WHEEL_DELTA * (1 if notches > 0 else -1),
            _MOUSEEVENTF_WHEEL, 0, None)
        ctypes.windll.user32.SendInput(1, ctypes.byref(cmd), ctypes.sizeof(cmd))
        time.sleep(random.uniform(0.03, 0.09))


def press_key(key):
    """模拟按下并松开按键，如 'r' / 'down' / 'esc'"""
    pydirectinput.press(key)


def move_to(x, y, duration=None):
    """模拟人手移动鼠标到绝对屏幕坐标"""
    pydirectinput.moveTo(x, y, duration=duration or random.uniform(0.15, 0.35))


def click(x=None, y=None):
    """在当前位置（或指定坐标）模拟鼠标左键单击"""
    if x is not None and y is not None:
        move_to(x, y)
        time.sleep(random.uniform(0.05, 0.15))
    pydirectinput.click()


def click_like_button(abs_x, abs_y, jitter=3):
    """点击点赞按钮（带轻微随机偏移，更拟人）"""
    tx = abs_x + random.randint(-jitter, jitter)
    ty = abs_y + random.randint(-jitter, jitter)
    move_to(tx, ty)
    time.sleep(random.uniform(0.08, 0.2))
    pydirectinput.click()
    return tx, ty


def scroll_wheel(clicks, x=None, y=None, then_move=None):
    """在指定位置滚动鼠标滚轮（clicks 负数=向下滚=下一个视频）
    then_move: 滚动后鼠标停靠点，避免悬停视频弹出进度条等 UI 遮挡画面"""
    if x is not None and y is not None:
        move_to(x, y)
        time.sleep(random.uniform(0.05, 0.15))
    _send_wheel(clicks)
    if then_move is not None:
        time.sleep(random.uniform(0.15, 0.3))
        move_to(*then_move)


def park_point(rect, screen=None):
    """鼠标安全停靠点。
    PARK_OUTSIDE=True: 停到窗口右侧的桌面（悬停不会触发抖音任何 UI）；
    PARK_OUTSIDE=False（默认）: 停到窗口内 config.PARK_SPOT（用户指定 70%,70%）。
    注意：不停窗口下方——那是任务栏区域，悬停图标会弹预览窗"""
    import config
    if config.PARK_OUTSIDE:
        if screen is None:
            import dy_window
            screen = dy_window.get_screen_rect()
        if rect[2] + 60 <= screen[2]:
            return rect[2] + 40, (rect[1] + rect[3]) // 2
    w_, h_ = rect[2] - rect[0], rect[3] - rect[1]
    spot = config.PARK_SPOT if not config.PARK_OUTSIDE else config.NEUTRAL_SPOT
    return (rect[0] + int(w_ * spot[0]),
            rect[1] + int(h_ * spot[1]))


def human_sleep(lo, hi):
    time.sleep(random.uniform(lo, hi))


if __name__ == "__main__":
    print("3 秒后开始自测：移动鼠标到屏幕中心并点击一次")
    time.sleep(3)
    user32_screen = (1920, 1080)
    click(user32_screen[0] // 2, user32_screen[1] // 2)
    press_key("down")
    print("自测完成")
