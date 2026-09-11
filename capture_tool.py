# -*- coding: utf-8 -*-
"""模板采集工具：截图抖音窗口 → 拖框选区 → 保存为点赞按钮模板

用法：
    python capture_tool.py

操作：
  1. 运行后 3 秒内切换到抖音（显示一个未点赞的视频）
  2. 在弹出的窗口中用鼠标拖出一个矩形框住【点赞爱心图标】
  3. 点击「保存为未点赞模板」(白心) 或「保存为已点赞模板」(红心)
  4. 可点「重新截图」再截（例如先截白心，再点一个视频赞变红心后截红心）
"""
import os
import time
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk

import config
import dy_window


class CropApp:
    MAX_W, MAX_H = 1400, 900

    def __init__(self, root):
        self.root = root
        self.frame = None      # 原始分辨率截图 (BGR ndarray)
        self.photo = None
        self.scale = 1.0
        self.start_xy = None
        self.rect_id = None

        root.title("DouyinAuto 模板采集 - 拖框选择点赞按钮")
        self.canvas = tk.Canvas(root, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        bar = tk.Frame(root)
        bar.pack(fill=tk.X)
        tk.Button(bar, text="保存为未点赞模板(白心)",
                  command=lambda: self.save("like_")).pack(side=tk.LEFT, padx=6, pady=6)
        tk.Button(bar, text="保存为已点赞模板(红心)",
                  command=lambda: self.save("liked_")).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="重新截图", command=self.recapture).pack(side=tk.LEFT, padx=6)
        tk.Label(bar, text="提示：框选爱心图标即可（含少量边缘更稳）").pack(
            side=tk.RIGHT, padx=8)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.selection = None  # 原始分辨率下的 (x0,y0,x1,y1)
        self.recapture(first=True)

    def recapture(self, first=False):
        if not first:
            self.root.iconify()
            time.sleep(1.2)
        print("3 秒后截图，请切换到抖音窗口...")
        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        hwnd, rect = dy_window.find_window(config.WINDOW_TITLE)
        if rect is None:
            rect = dy_window.get_screen_rect()
        self.frame = dy_window.ScreenCapture().grab(rect)
        self.display()

    def display(self):
        import cv2
        img = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]
        self.scale = min(self.MAX_W / w, self.MAX_H / h, 1.0)
        if self.scale < 1.0:
            img = cv2.resize(img, (int(w * self.scale), int(h * self.scale)))
        self.photo = ImageTk.PhotoImage(Image.fromarray(img))
        self.canvas.config(width=img.shape[1], height=img.shape[0])
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.selection = None
        self.root.deiconify()

    def on_press(self, e):
        self.start_xy = (e.x, e.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def on_drag(self, e):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_xy[0], self.start_xy[1], e.x, e.y,
            outline="#00FF66", width=2)

    def on_release(self, e):
        x0 = int(min(self.start_xy[0], e.x) / self.scale)
        y0 = int(min(self.start_xy[1], e.y) / self.scale)
        x1 = int(max(self.start_xy[0], e.x) / self.scale)
        y1 = int(max(self.start_xy[1], e.y) / self.scale)
        if x1 - x0 < 5 or y1 - y0 < 5:
            self.selection = None
            return
        self.selection = (x0, y0, x1, y1)

    def save(self, prefix):
        if self.selection is None:
            messagebox.showwarning("提示", "请先用鼠标拖框选中点赞按钮")
            return
        x0, y0, x1, y1 = self.selection
        crop = self.frame[y0:y1, x0:x1]
        os.makedirs(config.TEMPLATE_DIR, exist_ok=True)
        n = 1
        while os.path.exists(os.path.join(
                config.TEMPLATE_DIR, f"{prefix}{n}.png")):
            n += 1
        path = os.path.join(config.TEMPLATE_DIR, f"{prefix}{n}.png")
        import cv2
        cv2.imwrite(path, crop)
        print(f"已保存: {path} ({x1-x0}x{y1-y0})")
        messagebox.showinfo("成功", f"已保存 {path}\n可点「重新截图」采集另一种状态")


def main():
    dy_window.ensure_dpi_aware()
    root = tk.Tk()
    CropApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
