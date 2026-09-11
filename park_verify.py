# -*- coding: utf-8 -*-
"""停靠点 A/B 验证：
A. 复现旧问题：鼠标停在顶部搜索框 (0.5,0.02) → 截图 OCR → 应出现热搜弹框文本
B. 新方案：滚轮翻页后停到窗口外桌面（park_point）→ 截图 OCR → 弹框文本应消失
无点赞/不感兴趣操作，仅滚动一次，无账号副作用。
"""
import time

import cv2
from rapidocr_onnxruntime import RapidOCR

import config
import dy_input
import dy_window

ocr = RapidOCR()


def ocr_texts(img):
    res = ocr(img)
    if isinstance(res, tuple):
        res = res[0]
    return {t.replace(" ", "") for t, s in ((it[1], float(it[2])) for it in (res or [])) if s > 0.6}


def shot_parked(cap, rect, spot, wait=3.0, label=""):
    """把鼠标停到 spot(窗口比例) 等待后截图，返回 OCR 文本集"""
    w_, h_ = rect[2] - rect[0], rect[3] - rect[1]
    x = rect[0] + int(w_ * spot[0])
    y = rect[1] + int(h_ * spot[1])
    dy_input.move_to(x, y)
    time.sleep(wait)
    frame = cap.grab(rect)
    cv2.imwrite(f"verify_{label}.png", frame)
    return ocr_texts(frame)


def main():
    dy_window.ensure_dpi_aware()
    hwnd, rect = dy_window.find_window(config.WINDOW_TITLE)
    if rect is None:
        raise SystemExit("未找到抖音窗口")
    dy_window.activate_window(hwnd)
    time.sleep(1.5)
    cap = dy_window.ScreenCapture()

    # 清场：关掉可能残留的弹框
    dy_input.press_key("esc")
    time.sleep(1.0)

    # B 先行：新停靠点（窗口外桌面）基准
    park = dy_input.park_point(rect)
    dy_input.move_to(*park)
    time.sleep(3.0)
    frame = cap.grab(rect)
    cv2.imwrite("verify_new.png", frame)
    new_texts = ocr_texts(frame)
    print(f"新停靠点 (窗口外 {park}): OCR 文本 {len(new_texts)} 条", flush=True)

    # A：复现旧问题（顶部搜索框）
    old_texts = shot_parked(cap, rect, (0.50, 0.02), wait=3.0, label="old")
    popup = old_texts - new_texts
    print(f"旧停靠点 (0.50,0.02 搜索框): 多出文本 {len(popup)} 条", flush=True)
    print(f"  弹框特征文本: {sorted(popup)[:15] if popup else '无（未复现）'}", flush=True)

    # 关闭弹框，再用新方案完整走一遍「滚轮+停靠」
    dy_input.press_key("esc")
    time.sleep(1.2)
    park = dy_input.park_point(rect)  # 修复后的停靠点（最大化时=窗口内左下角）
    w_, h_ = rect[2] - rect[0], rect[3] - rect[1]
    sx = rect[0] + int(w_ * config.SCROLL_SPOT[0])
    sy = rect[1] + int(h_ * config.SCROLL_SPOT[1])
    dy_input.scroll_wheel(config.SCROLL_NOTCHES, sx, sy, then_move=park)
    time.sleep(3.0)
    frame = cap.grab(rect)
    cv2.imwrite("verify_scroll_new.png", frame)
    final_texts = ocr_texts(frame)
    # 弹框标志文本：搜索下拉框的固定文案（含"搜索你感兴趣的内容"）才算弹框，
    # "推荐"等侧边栏常驻词不算（OCR 逐帧会有少量差异）
    markers = {t for t in popup if ("搜索" in t or "小时前" in t or "热搜" in t or "热榜" in t)}
    leaked = {t for t in markers if t in final_texts}
    print(f"滚轮+新停靠点 {park}: 弹框标志文本残留 {len(leaked)} 条 "
          f"{sorted(leaked) if leaked else ''}", flush=True)

    ok = not leaked
    print("结论:", "✓ 新停靠点无弹框遮挡" if ok else "✗ 仍有弹框文本残留，需进一步排查")


if __name__ == "__main__":
    main()
