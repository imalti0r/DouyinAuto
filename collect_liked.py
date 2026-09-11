# -*- coding: utf-8 -*-
"""红心模板自动采集：检测已点赞（粉红心）状态 → 提取保存 templates/liked_1.png

用法：python collect_liked.py
原理：OCR 定位点赞数 → 其正上方区域内找爱心图标连通块
     （粉红 = 已点赞：R-G>70 且 R-B>50；白色 = 未点赞）
"""
import os
import time

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

import config
import dy_window

ocr = RapidOCR()


def grab_frame(activate=False):
    hwnd, rect = dy_window.find_window(config.WINDOW_TITLE)
    if rect is None:
        raise SystemExit("未找到抖音窗口")
    if activate:
        dy_window.activate_window(hwnd)
        time.sleep(1.5)
    return dy_window.ScreenCapture().grab(rect), rect


def find_like_count(frame):
    """OCR 点赞数（数字+万/亿/w），返回其中心窗口坐标或 None"""
    h, w = frame.shape[:2]
    bar = frame[int(0.05 * h):int(0.95 * h), int(0.85 * w):int(1.0 * w)]
    res = ocr(bar)
    if isinstance(res, tuple):
        res = res[0]
    ox, oy = int(0.85 * w), int(0.05 * h)
    best = None
    for item in (res or []):
        box, text, score = item[0], item[1], float(item[2])
        if score < 0.6:
            continue
        t = text.replace(" ", "")
        if not t or not any(c.isdigit() for c in t):
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        if max(xs) - min(xs) < 60:  # 点赞数较宽，排除小数字
            continue
        cx = ox + (min(xs) + max(xs)) / 2
        cy = oy + (min(ys) + max(ys)) / 2
        if best is None or cy < best[1]:
            best = (cx, cy)
    return best


def find_heart(frame, count_pos):
    """在点赞数正上方区域找爱心图标连通块
    返回 (state, bbox) state='red'/'white'/None, bbox=(x0,y0,x1,y1) 全帧坐标"""
    cx, cy = count_pos
    h, w = frame.shape[:2]
    # 爱心搜索区：点赞数上方 20~160px，水平 ±90px
    x0, x1 = max(0, int(cx - 90)), min(w, int(cx + 90))
    y0, y1 = max(0, int(cy - 160)), max(0, int(cy - 20))
    roi = frame[y0:y1, x0:x1]
    if roi.size == 0:
        return None, None
    b, g, r = (roi[:, :, i].astype(int) for i in range(3))
    pink = ((r - g) > 70) & ((r - b) > 50) & (r > 150)     # 抖音已点赞粉红心
    white = (b > 185) & (g > 185) & (r > 185) & (abs(r - g) < 30)

    def best_blob(mask, min_area=250):
        if mask.sum() < min_area:
            return None
        dil = cv2.dilate(mask.astype(np.uint8), np.ones((7, 7), np.uint8))
        n, labels, stats, cents = cv2.connectedComponentsWithStats(dil)
        best_i, best_area = None, 0
        for i in range(1, n):
            if stats[i, 4] > best_area:
                best_i, best_area = i, stats[i, 4]
        if best_i is None:
            return None
        bx, by, bw_, bh_ = stats[best_i, :4]
        # 爱心应接近正方形且不太小
        if bw_ < 25 or bh_ < 25:
            return None
        return (x0 + bx, y0 + by, x0 + bx + bw_, y0 + by + bh_)

    pink_blob = best_blob(pink)
    white_blob = best_blob(white)
    if pink_blob is not None:
        return "red", pink_blob
    if white_blob is not None:
        return "white", white_blob
    return None, None


def extract_heart(frame, bbox, margin=6):
    """紧贴 bbox 裁剪模板"""
    x0, y0, x1, y1 = bbox
    h, w = frame.shape[:2]
    X0, Y0 = max(0, x0 - margin), max(0, y0 - margin)
    X1, Y1 = min(w, x1 + margin), min(h, y1 + margin)
    return frame[Y0:Y1, X0:X1]


def main():
    dy_window.ensure_dpi_aware()
    print("激活抖音窗口并截取当前画面...", flush=True)
    frame, rect = grab_frame(activate=True)

    count_pos = find_like_count(frame)
    if count_pos is None:
        cv2.imwrite("debug_liked.png", frame)
        raise SystemExit("未定位到点赞数，已保存 debug_liked.png 供排查")
    print(f"点赞数位置≈({count_pos[0]:.0f},{count_pos[1]:.0f})", flush=True)

    state, bbox = find_heart(frame, count_pos)
    print(f"爱心状态: {state} bbox={bbox}", flush=True)

    if state != "red":
        print("\n>>> 当前不是红心。请手动点赞当前视频（点爱心），等待变红...（最多 120 秒）<<<", flush=True)
        deadline = time.time() + 120
        while time.time() < deadline:
            time.sleep(2)
            frame, _ = grab_frame()
            count_pos = find_like_count(frame)
            if count_pos is None:
                continue
            state, bbox = find_heart(frame, count_pos)
            print(f"  检测中... 状态={state}", flush=True)
            if state == "red":
                break
        if state != "red":
            cv2.imwrite("debug_liked.png", frame)
            raise SystemExit("超时未检测到红心，已保存 debug_liked.png 供排查")

    tpl = extract_heart(frame, bbox)
    os.makedirs(config.TEMPLATE_DIR, exist_ok=True)
    path = os.path.join(config.TEMPLATE_DIR, "liked_1.png")
    cv2.imwrite(path, tpl)
    print(f"红心模板已保存: {path} ({tpl.shape[1]}x{tpl.shape[0]})", flush=True)

    # 双向验证：红心模板应匹配当前画面，白心模板不应高置信匹配
    import dy_vision
    liked_tpls = dy_vision.load_templates(prefix="liked_")
    like_tpls = dy_vision.load_templates(prefix="like_")
    hit_liked = dy_vision.find_button(frame, liked_tpls)
    hit_like = dy_vision.find_button(frame, like_tpls) if like_tpls else None
    print(f"验证: 红心画面 vs 红心模板 = {hit_liked}", flush=True)
    print(f"验证: 红心画面 vs 白心模板 = {hit_like}", flush=True)
    if hit_liked is None or hit_liked[2] < 0.85:
        cv2.imwrite("debug_red_frame.png", frame)
        raise SystemExit("[警告] 红心模板匹配置信度不足，请检查 debug_red_frame.png")
    if hit_like is not None and hit_like[2] > 0.85:
        cv2.imwrite("debug_red_frame.png", frame)
        raise SystemExit("[警告] 白心模板误匹配红心画面，防护可能失效")
    print("=== 红心模板采集并验证成功 ===")


if __name__ == "__main__":
    main()
