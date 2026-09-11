# -*- coding: utf-8 -*-
"""滚轮翻页真机验证：在抖音视频区滚动一次，CLIP 嵌入对比前后画面是否切换

用法: python scroll_test.py [notches]   # 默认读 config.SCROLL_NOTCHES（-2）
只滚动不点赞/不感兴趣，对账号无副作用。
"""
import sys
import time

import numpy as np

import config
import dy_input
import dy_window
from dy_clip import ClipClassifier


def avg_embed(clip, cap, rect, n=3, span=1.5):
    frames = [cap.grab(rect)]
    for _ in range(n - 1):
        time.sleep(span / (n - 1))
        frames.append(cap.grab(rect))
    e = clip.encode_images(frames).mean(axis=0)
    return e / np.linalg.norm(e)


def main():
    notches = int(sys.argv[1]) if len(sys.argv) > 1 else config.SCROLL_NOTCHES
    dy_window.ensure_dpi_aware()
    clip = ClipClassifier()
    hwnd, rect = dy_window.find_window(config.WINDOW_TITLE)
    if rect is None:
        raise SystemExit("未找到抖音窗口")
    dy_window.activate_window(hwnd)
    time.sleep(1.5)
    cap = dy_window.ScreenCapture()

    e1 = avg_embed(clip, cap, rect)
    w_, h_ = rect[2] - rect[0], rect[3] - rect[1]
    sx = rect[0] + int(w_ * config.SCROLL_SPOT[0])
    sy = rect[1] + int(h_ * config.SCROLL_SPOT[1])
    park = dy_input.park_point(rect)
    print(f"在视频区 ({sx},{sy}) 滚动 {notches} 格，之后鼠标停靠 ({park[0]},{park[1]})...", flush=True)
    dy_input.scroll_wheel(notches, sx, sy, then_move=park)
    time.sleep(2.0)
    e2 = avg_embed(clip, cap, rect)

    cos = float(e1 @ e2)
    changed = cos < config.STUCK_EMBED_COS
    print(f"滚动前后画面嵌入余弦: {cos:.4f}（阈值 {config.STUCK_EMBED_COS}）")
    print("结论:", "✓ 滚轮翻页生效，画面已切换" if changed else "✗ 画面未变化，翻页未生效")


if __name__ == "__main__":
    main()
