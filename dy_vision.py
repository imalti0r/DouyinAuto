# -*- coding: utf-8 -*-
"""图像识别：OpenCV 模板匹配点赞按钮 + RapidOCR 识别文案关键词"""
import os
import re

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

import config

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr


def region_slice(frame, region_frac):
    """按比例坐标 (x0,y0,x1,y1) 裁剪 frame"""
    h, w = frame.shape[:2]
    x0 = max(0, int(region_frac[0] * w))
    y0 = max(0, int(region_frac[1] * h))
    x1 = min(w, int(region_frac[2] * w))
    y1 = min(h, int(region_frac[3] * h))
    return frame[y0:y1, x0:x1], (x0, y0)


def load_templates(template_dir=None, prefix="like_"):
    """加载 templates/ 下 like_*.png 模板（灰度）"""
    template_dir = template_dir or config.TEMPLATE_DIR
    templates = []
    if not os.path.isdir(template_dir):
        return templates
    for name in sorted(os.listdir(template_dir)):
        if name.startswith(prefix) and name.lower().endswith(".png"):
            img = cv2.imread(os.path.join(template_dir, name), cv2.IMREAD_COLOR)
            if img is not None:
                templates.append((name, img))
    return templates


def match_templates(region, templates, threshold=None, scales=None):
    """多尺度彩色模板匹配（彩色可区分白心/红心状态），
    返回 (cx, cy, score, name)（区域局部坐标）或 None"""
    threshold = config.TEMPLATE_THRESHOLD if threshold is None else threshold
    scales = config.TEMPLATE_SCALES if scales is None else scales
    best = None
    for name, tpl in templates:
        for s in scales:
            tw, th = int(tpl.shape[1] * s), int(tpl.shape[0] * s)
            if tw < 8 or th < 8 or tw > region.shape[1] or th > region.shape[0]:
                continue
            scaled = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(region, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= threshold and (best is None or max_val > best[2]):
                best = (max_loc[0] + tw // 2, max_loc[1] + th // 2, max_val, name)
    return best


def find_button(frame, templates, region_frac=None):
    """在窗口指定区域找模板（如点赞按钮）
    返回按钮在截图内的坐标 (x, y, score, name)，找不到返回 None"""
    region_frac = config.ACTION_BAR_REGION if region_frac is None else region_frac
    if not templates:
        return None
    region, (ox, oy) = region_slice(frame, region_frac)
    hit = match_templates(region, templates)
    if hit is None:
        return None
    cx, cy, score, name = hit
    return (ox + cx, oy + cy, score, name)


def ocr_caption(frame, region_frac=None):
    """OCR 文案区，返回拼接文本（含话题标签）"""
    region_frac = config.CAPTION_REGION if region_frac is None else region_frac
    region, _ = region_slice(frame, region_frac)
    result = _get_ocr()(region)
    if isinstance(result, tuple):  # 新版返回 (result, elapse)
        result = result[0]
    if not result:
        return ""
    texts = []
    for item in result:
        text, score = item[1], float(item[2])
        if score >= config.MIN_OCR_SCORE:
            texts.append(text)
    return " ".join(texts)


def classify(text):
    """关键词判定：返回 (是否目标, 命中的关键词)"""
    low = text.lower()
    for kw in config.EXCLUDE_KEYWORDS:
        if kw.lower() in low:
            return False, f"排除词[{kw}]"
    for kw in config.LIKE_KEYWORDS:
        if kw.lower() in low:
            return True, kw
    return False, ""


def ocr_items(frame, region_frac):
    """OCR 指定区域，返回文本条目列表（坐标已换算为全截图坐标）
    每项: dict(text, score, cx, cy, left, top, right, bottom)"""
    region, (ox, oy) = region_slice(frame, region_frac)
    result = _get_ocr()(region)
    if isinstance(result, tuple):
        result = result[0]
    items = []
    for box, text, score in (result or []):
        score = float(score)  # 新版 rapidocr 返回 str，统一转 float
        if score < config.MIN_OCR_SCORE:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append({
            "text": text,
            "score": float(score),
            "cx": ox + sum(xs) / 4,
            "cy": oy + sum(ys) / 4,
            "left": ox + min(xs),
            "top": oy + min(ys),
            "right": ox + max(xs),
            "bottom": oy + max(ys),
        })
    return items


def detect_livestream(frame):
    """检测推荐流中的直播（画面底部中心「点击进入直播」按钮）
    返回 (是否直播, 命中文本)"""
    for it in ocr_items(frame, config.LIVE_DETECT_REGION):
        for kw in config.LIVE_BUTTON_KEYWORDS:
            if kw in it["text"]:
                return True, it["text"]
    return False, ""


# ---------- HDR 鲁棒的颜色几何检测 ----------
# 抖音红(SDR) ≈ BGR(85,44,254)：r-g=210, r-b=169
# HDR 偏色后变粉 ≈ BGR(177,132,255)：r-g=123, r-b=78
# 宽判定 r-g>60 & r-b>40 同时覆盖两者；灰色 UI 的 r-g≈0 天然排除


def find_like_count_pos(frame):
    """OCR 操作栏定位点赞数，返回截图内坐标 (cx, cy) 或 None。
    操作栏的点赞/评论/收藏/分享数纵向排成一列（x 几乎相同，间距~147px）：
    取数字候选中最密集的 x 簇（≥45px 邻域计数最多），点赞数 = 簇内最上方项，
    x 用簇内中位数（单条 OCR 的文本框中心有 ±30px 抖动，中位数稳定）。
    孤立噪声（视频画面里的随机数字）因不成簇被天然排除"""
    h, w = frame.shape[:2]
    items = ocr_items(frame, config.ACTION_BAR_REGION)
    cands = [it for it in items
             if any(c.isdigit() for c in it["text"].replace(" ", ""))
             and 0.35 * h <= it["cy"] <= 0.90 * h]
    if not cands:
        return None
    cluster = max(cands, key=lambda c: sum(
        1 for o in cands if abs(o["cx"] - c["cx"]) <= 45))
    members = [o for o in cands if abs(o["cx"] - cluster["cx"]) <= 45]
    if len(members) == 1:  # 无簇可依（只识别到一条），退回取最宽/最上方
        wide = [it for it in cands if it["right"] - it["left"] >= 50]
        best = min(wide or cands, key=lambda it: it["top"])
        return int(best["cx"]), int(best["cy"])
    like = min(members, key=lambda it: it["top"])
    xs = sorted(m["cx"] for m in members)
    cx = xs[len(xs) // 2]
    return int(cx), int(like["cy"])


def _red_blobs(frame, region_frac):
    """区域内红色系近正方形实心连通块（HDR/SDR 通用宽判定）
    填充率过滤（≥0.5）排除视频画面里的碎片化红色内容
    返回 [(cx, cy, bw, bh)] 全截图坐标"""
    h, w = frame.shape[:2]
    region, (ox, oy) = region_slice(frame, region_frac)
    b, g, r = (region[:, :, i].astype(int) for i in range(3))
    mask = ((r - g) > 60) & ((r - b) > 40) & (r > 150)
    if mask.sum() < 80:
        return []
    dil = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8))
    n, _, stats, cents = cv2.connectedComponentsWithStats(dil)
    blobs = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 300 or bw < 18 or bh < 18 or bw > 200 or bh > 200:
            continue
        if not (0.7 < bw / bh < 1.4):
            continue
        fill = mask[y:y + bh, x:x + bw].mean()  # 实心度：图标≈0.75，碎片内容低
        if fill < 0.5:
            continue
        blobs.append((int(ox + cents[i][0]), int(oy + cents[i][1]), bw, bh))
    return blobs


# 关注按钮几何参数（实测窗口高 1856）：按钮中心距点赞数中心约 162px，按钮半径约 22px
FOLLOW_OFFSET = 162
FOLLOW_DISC_R = 28
FOLLOW_X_SCAN = 48     # x 扫描半宽（OCR 文本中心与图标列中心有 ~30px 系统性偏差）
FOLLOW_RED_MIN = 0.30    # 圆盘内红/粉像素占比下限（实测有按钮≈0.43）
FOLLOW_BRIGHT_MIN = 0.04  # 圆盘内亮白（加号）像素占比下限（实测≈0.09-0.25）


def find_follow_button(frame):
    """找关注按钮（未关注状态：头像下方红/粉圆底白加号）——圆盘测量法，HDR 鲁棒。
    y 锚定 OCR 点赞数（上方 FOLLOW_OFFSET 像素，实测稳定）；
    x 在点赞数中心 ±FOLLOW_X_SCAN 内扫描取红粉填充率最高的圆盘位置
    （OCR 文本框中心与图标列中心存在系统性偏差，不能直接用）。
    判定：红粉填充率 ≥ 0.30 且 亮白加号率 ≥ 0.04 → 按钮存在。
    不做连通块分析 → 头像含红色内容与按钮粘连也不影响
    （v3.6 连通块方案在头像泛红时会误判为"已关注"）。
    返回按钮中心 (cx, cy) 或 None（已关注）"""
    h, w = frame.shape[:2]
    pos = find_like_count_pos(frame)
    if pos is not None:
        ay = pos[1] - FOLLOW_OFFSET
        x_lo, x_hi = pos[0] - FOLLOW_X_SCAN, pos[0] + FOLLOW_X_SCAN
    else:
        # OCR 失败兜底：固定窗口比例位（用户实测 3304x1856 窗口按钮在 3087,853）
        ay = int(h * 0.4596)
        x_lo = x_hi = int(w * 0.9344)
    y0, y1 = max(0, ay - FOLLOW_DISC_R), min(h, ay + FOLLOW_DISC_R)
    if y1 <= y0:
        return None
    band = frame[y0:y1, :]
    b, g, r = (band[:, :, i].astype(int) for i in range(3))
    red_mask = ((r - g) > 60) & ((r - b) > 40) & (r > 150)
    # 亮白判定放宽通道差异：HDR 下白色会偏粉（实测加号 ≈ BGR(210,177,255)）
    bright_mask = (r > 190) & (g > 160) & (b > 150)
    yy = np.arange(y0, y1).reshape(-1, 1)
    disc_area = np.pi * FOLLOW_DISC_R ** 2

    best = None  # (red_ratio, cx, bright_ratio)
    for cx in range(max(FOLLOW_DISC_R, x_lo), min(w - FOLLOW_DISC_R, x_hi) + 1, 6):
        x0b = cx - FOLLOW_DISC_R
        xx = np.arange(x0b, x0b + 2 * FOLLOW_DISC_R).reshape(1, -1)
        disc = ((xx - cx) ** 2 + (yy - ay) ** 2) <= FOLLOW_DISC_R ** 2
        red = float((red_mask[:, x0b:x0b + 2 * FOLLOW_DISC_R] & disc).sum()) / disc_area
        if red < FOLLOW_RED_MIN:
            continue
        bright = float((bright_mask[:, x0b:x0b + 2 * FOLLOW_DISC_R] & disc).sum()) / disc_area
        if bright < FOLLOW_BRIGHT_MIN:
            continue
        if best is None or red > best[0]:
            best = (red, cx, bright)
    if best is not None:
        return best[1], ay
    return None


def detect_liked(frame):
    """已点赞检测：点赞数正上方心形位置（40~110px，心中心距约 70px 半高 23px）
    存在红/粉实心块 = 粉红心（已赞）；关注按钮中心距约 163px 不在区间内。
    误报后果仅是跳过点赞，代价小。返回 bool"""
    pos = find_like_count_pos(frame)
    if pos is None:
        return False
    cx, cy = pos
    h, w = frame.shape[:2]
    region = (max(0.0, cx / w - 0.06), max(0.0, (cy - 110) / h),
              min(1.0, cx / w + 0.06), max(0.0, (cy - 40) / h))
    if region[2] <= region[0] or region[3] <= region[1]:
        return False
    blobs = _red_blobs(frame, region)
    return len(blobs) > 0


def is_video_changed(text_a, text_b):
    """两次 OCR 文本相似度判断视频是否已切换"""
    if not text_a or not text_b:
        return True
    a = set(re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", text_a))
    b = set(re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", text_b))
    if not a or not b:
        return True
    overlap = len(a & b) / max(len(a), len(b))
    return overlap < 0.6  # 重合度低 → 视为已切换


if __name__ == "__main__":
    # 自测：对 debug_window.png 做完整识别
    import dy_window
    frame = cv2.imread("debug_window.png")
    if frame is None:
        dy_window.ensure_dpi_aware()
        hwnd, rect = dy_window.find_window("抖音")
        rect = rect or dy_window.get_screen_rect()
        frame = dy_window.ScreenCapture().grab(rect)
    text = ocr_caption(frame)
    print("OCR 文案:", text)
    print("判定:", classify(text))
    tpls = load_templates()
    print(f"已加载 {len(tpls)} 个点赞模板")
    if tpls:
        print("点赞按钮:", find_button(frame, tpls))
    else:
        print("（无模板，跳过按钮匹配测试）")
