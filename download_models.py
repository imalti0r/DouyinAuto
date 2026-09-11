# -*- coding: utf-8 -*-
"""下载 CLIP ONNX 模型（hf-mirror 镜像）到 models/ 目录"""
import os
import sys

import requests

BASE = "https://hf-mirror.com/Xenova/clip-vit-base-patch32/resolve/main/"
FILES = [
    "onnx/vision_model_quantized.onnx",
    "onnx/text_model_quantized.onnx",
    "tokenizer.json",
    "preprocessor_config.json",
]


def main():
    os.makedirs("models", exist_ok=True)
    for f in FILES:
        local = os.path.join("models", os.path.basename(f))
        if os.path.exists(local) and os.path.getsize(local) > 0:
            print("skip", local)
            continue
        print("downloading", f, "...")
        with requests.get(BASE + f, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(local, "wb") as fp:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fp.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done / 1048576:.1f}/{total / 1048576:.1f} MB",
                              end="", flush=True)
            print()
    print("sizes:")
    for f in sorted(os.listdir("models")):
        mb = os.path.getsize(os.path.join("models", f)) / 1048576
        print(f"  {f}: {mb:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
