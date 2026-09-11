# -*- coding: utf-8 -*-
"""CLIP 零样本画面分类器：直接看视频画面内容，判断是否为目标视频（美女舞蹈/美女cos）

模型：Xenova/clip-vit-base-patch32 的量化 ONNX 版（视觉/文本编码器分离，onnxruntime CPU 运行）
原理：把每一帧画面编码成 512 维向量，与预编码的「目标提示词组」「非目标提示词组」
     分别算余弦相似度，温度 softmax 后得到目标概率。
"""
import json
import os

import cv2
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

import config

_EOS = 49407          # <|endoftext|>
_MAX_LEN = 77         # CLIP 文本最大长度
_SCALE = 100.0        # CLIP 温度（logit_scale = exp(4.6052) ≈ 100）


class ClipClassifier:
    def __init__(self, model_dir=None, prompts_pos=None, prompts_neg=None):
        model_dir = model_dir or config.CLIP_MODEL_DIR
        self.tok = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, (os.cpu_count() or 4) - 1)
        providers = ["CPUExecutionProvider"]
        self.vision = ort.InferenceSession(
            os.path.join(model_dir, "vision_model_quantized.onnx"),
            sess_options=opts, providers=providers)
        self.text = ort.InferenceSession(
            os.path.join(model_dir, "text_model_quantized.onnx"),
            sess_options=opts, providers=providers)

        with open(os.path.join(model_dir, "preprocessor_config.json"), encoding="utf-8") as f:
            pre = json.load(f)
        self.mean = np.array(pre["image_mean"], dtype=np.float32) * 255.0
        self.std = np.array(pre["image_std"], dtype=np.float32) * 255.0
        self.size = pre["crop_size"]["width"]  # 224

        prompts_pos = prompts_pos or config.POSITIVE_PROMPTS
        prompts_neg = prompts_neg or config.NEGATIVE_PROMPTS
        self.text_pos = self.encode_texts(prompts_pos)   # (P,512) 已归一化
        self.text_neg = self.encode_texts(prompts_neg)
        self._warmup_done = False

    # ---------- 图像 ----------
    def _preprocess(self, bgr):
        """BGR ndarray → (1,3,224,224) float32（短边缩放到224+中心裁剪+标准化）"""
        h, w = bgr.shape[:2]
        if w < h:
            nw, nh = self.size, int(h * self.size / w)
        else:
            nw, nh = int(w * self.size / h), self.size
        img = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        top, left = (nh - self.size) // 2, (nw - self.size) // 2
        img = img[top:top + self.size, left:left + self.size]
        img = (img.astype(np.float32) - self.mean) / self.std
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)
        return img[None]

    def encode_images(self, frames_bgr):
        """批量编码画面帧 → (N,512) L2 归一化"""
        pixels = np.concatenate([self._preprocess(f) for f in frames_bgr], axis=0)
        embeds = self.vision.run(None, {"pixel_values": pixels})[0]
        return embeds / np.linalg.norm(embeds, axis=1, keepdims=True)

    # ---------- 文本 ----------
    def _tokenize(self, prompt):
        ids = self.tok.encode(prompt).ids[:_MAX_LEN]
        ids = ids + [_EOS] * (_MAX_LEN - len(ids))  # EOS 后填充（因果注意力+EOS池化，填充不影响结果）
        return np.array([ids], dtype=np.int64)

    def encode_texts(self, prompts):
        ids = np.concatenate([self._tokenize(p) for p in prompts], axis=0)
        embeds = self.text.run(None, {"input_ids": ids})[0]
        return embeds / np.linalg.norm(embeds, axis=1, keepdims=True)

    # ---------- 分类 ----------
    def frame_prob(self, frame_bgr):
        """单帧 → 目标概率 [0,1]"""
        emb = self.encode_images([frame_bgr])[0]           # (512,)
        sim_pos = float(np.max(emb @ self.text_pos.T))     # 与最匹配的目标提示词相似度
        sim_neg = float(np.max(emb @ self.text_neg.T))
        e_pos, e_neg = np.exp(_SCALE * sim_pos), np.exp(_SCALE * sim_neg)
        return e_pos / (e_pos + e_neg)

    def classify_frames(self, frames_bgr):
        """多帧综合判定 → (is_target, mean_prob, per_frame_probs)"""
        if not self._warmup_done:  # 首次推理预热
            self.frame_prob(frames_bgr[0])
            self._warmup_done = True
        probs = [self.frame_prob(f) for f in frames_bgr]
        mean_prob = float(np.mean(probs))
        return mean_prob >= config.VISION_THRESHOLD, mean_prob, probs


if __name__ == "__main__":
    # 自测：合成图 + 真实截图（若有）
    import dy_window
    print("初始化 CLIP 分类器...")
    clf = ClipClassifier()

    # 合成图验证：纯色图 / 文字图
    plain = np.full((480, 360, 3), 128, np.uint8)
    p = clf.frame_prob(plain)
    print(f"纯色图 目标概率 = {p:.4f}（应较低）")

    # 抓当前抖音画面实测
    dy_window.ensure_dpi_aware()
    hwnd, rect = dy_window.find_window(config.WINDOW_TITLE)
    if rect:
        frame = dy_window.ScreenCapture().grab(rect)
        cv2.imwrite("debug_clip_frame.png", frame)
        t0 = __import__("time").time()
        is_t, prob, probs = clf.classify_frames([frame] * 3)
        dt = (__import__("time").time() - t0) / 3 * 1000
        print(f"当前抖音画面: 目标={is_t} 平均概率={prob:.4f} 各帧={ [f'{x:.3f}' for x in probs] } 单帧耗时={dt:.0f}ms")
    else:
        print("（未找到抖音窗口，跳过实测）")
