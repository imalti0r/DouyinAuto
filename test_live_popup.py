# -*- coding: utf-8 -*-
"""合成图测试：直播「点击进入直播」按钮检测（直播检测后直接滚轮切换，无弹窗处理）"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import dy_vision

W, H = 1920, 1032  # 半尺寸模拟窗口
font_big = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 34)


def draw_case(with_live):
    img = Image.new("RGB", (W, H), (25, 28, 35))
    d = ImageDraw.Draw(img)
    if with_live:
        x0, y0, x1, y1 = int(0.42 * W), int(0.85 * H), int(0.58 * W), int(0.92 * H)
        d.rounded_rectangle((x0, y0, x1, y1), 30, fill=(240, 44, 100))
        d.text(((x0 + x1) / 2, (y0 + y1) / 2), "点击进入直播",
               font=font_big, fill=(255, 255, 255), anchor="mm")
    return np.array(img)


# ---- 场景1：直播画面 ----
is_live, live_text = dy_vision.detect_livestream(draw_case(True))
print("直播检测:", is_live, live_text)
assert is_live, "应检测到直播"

# ---- 场景2：普通视频 ----
is_live2, _ = dy_vision.detect_livestream(draw_case(False))
print("普通视频: 直播=", is_live2)
assert not is_live2, "普通视频不应误报直播"

print("=== 直播检测 全部通过 ===")
