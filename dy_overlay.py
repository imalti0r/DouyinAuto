# -*- coding: utf-8 -*-
"""悬浮日志窗：置顶半透明小窗，实时滚动显示运行日志

两种运行方式：
  1. 子进程模式（推荐，主程序自动拉起）：
     python dy_overlay.py --child
     - stdin 收日志行（"\x01S" 前缀 = 状态栏更新）
     - 点 × 时向 stdout 输出 STOP（主程序收到后停止），stdin 关闭时自动退出
  2. 同进程模式：主程序所在 Python 有 tkinter 时直接 import FloatingLogWindow
"""
import sys
import threading
from queue import Empty, Queue

import config

try:
    import tkinter as tk
except ImportError:
    tk = None


class FloatingLogWindow:
    def __init__(self, log_queue, stop_event, done_event, on_close=None):
        if tk is None:
            raise ImportError("当前 Python 没有 tkinter")
        self.queue = log_queue
        self.stop_event = stop_event
        self.done_event = done_event
        self.on_close = on_close
        self.max_lines = config.OVERLAY_MAX_LINES

        self.root = tk.Tk()
        self.root.title("DouyinAuto")
        w, h = config.OVERLAY_SIZE
        x, y = config.OVERLAY_POS
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", config.OVERLAY_ALPHA)
        self.root.configure(bg="#14171c")

        # 顶栏：标题 + 状态 + 关闭按钮（可拖动）
        bar = tk.Frame(self.root, bg="#1d232c", height=26)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        tk.Label(bar, text=" DouyinAuto", bg="#1d232c", fg="#7fb0ff",
                 font=("Microsoft YaHei UI", 9, "bold")).pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="启动中...")
        tk.Label(bar, textvariable=self.status_var, bg="#1d232c", fg="#9aa7b4",
                 font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT, padx=10)
        btn = tk.Label(bar, text=" ✕ ", bg="#1d232c", fg="#e06c75",
                       font=("Microsoft YaHei UI", 9, "bold"), cursor="hand2")
        btn.pack(side=tk.RIGHT)
        btn.bind("<Button-1>", self._on_close)
        bar.bind("<ButtonPress-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_move)

        self.text = tk.Text(self.root, bg="#14171c", fg="#c8d2dc", wrap="word",
                            font=("Consolas", 9), bd=0, padx=8, pady=6,
                            state=tk.DISABLED)
        sb = tk.Scrollbar(self.root, command=self.text.yview, width=8)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(fill=tk.BOTH, expand=True)

        self.text.tag_configure("warn", foreground="#e5c07b")
        self.text.tag_configure("err", foreground="#e06c75")
        self.text.tag_configure("ok", foreground="#98c379")
        self.text.tag_configure("head", foreground="#7fb0ff")

        self._drag_off = (0, 0)
        self._closed = False
        self.root.after(120, self._poll)

    # ---------- 拖动 ----------
    def _drag_start(self, e):
        self._drag_off = (e.x, e.y)

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self._drag_off[0]
        y = self.root.winfo_y() + e.y - self._drag_off[1]
        self.root.geometry(f"+{x}+{y}")

    # ---------- 关闭 ----------
    def _on_close(self, _e=None):
        self.stop_event.set()
        if self.on_close:
            self.on_close()
        # 兜底：即使工作线程未及时结束，5 秒后强制关窗
        self.root.after(5000, self._destroy)

    def _destroy(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # ---------- 日志刷新 ----------
    def _poll(self):
        if self._closed:
            return
        updated = False
        try:
            while True:
                kind, text = self.queue.get_nowait()
                if kind == "status":
                    self.status_var.set(text)
                else:
                    self._append(text)
                    updated = True
        except Empty:
            pass
        if updated:
            self.text.see("end")
        if self.done_event.is_set() or self.stop_event.is_set():
            self._destroy()
            return
        try:
            self.root.after(120, self._poll)
        except tk.TclError:
            pass

    def _append(self, line):
        tag = ()
        if "[警告]" in line or "[注意]" in line:
            tag = ("warn",)
        elif "[错误]" in line:
            tag = ("err",)
        elif "点赞" in line or "目标视频" in line:
            tag = ("ok",)
        elif "—— 视频" in line or "—— 直播" in line:
            tag = ("head",)
        self.text.configure(state=tk.NORMAL)
        self.text.insert("end", line + "\n", tag)
        if int(self.text.index("end-1c").split(".")[0]) > self.max_lines:
            self.text.delete("1.0", "2.0")
        self.text.configure(state=tk.DISABLED)

    def run(self):
        self.root.mainloop()


def run_child():
    """子进程模式：stdin 收日志，× → stdout 输出 STOP，stdin EOF 自动退出"""
    q = Queue()
    stop, done = threading.Event(), threading.Event()

    def reader():
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("\x01S"):
                q.put(("status", line[2:]))
            else:
                q.put(("log", line))
        done.set()  # 主程序退出（stdin 关闭）→ 关窗退出

    def on_close():
        try:
            print("STOP", flush=True)
        except OSError:
            pass

    threading.Thread(target=reader, daemon=True).start()
    win = FloatingLogWindow(q, stop, done, on_close=on_close)
    win.run()


if __name__ == "__main__":
    if "--child" in sys.argv:
        run_child()
    else:
        # 自测：推几条日志 3 秒后自动关窗
        import time

        q = Queue()
        stop, done = threading.Event(), threading.Event()

        def worker():
            for i in range(6):
                q.put(("log", f"[12:00:0{i}] 测试日志行 {i} —— 视频 #{i}"))
                time.sleep(0.25)
            q.put(("status", "处理 6 | 赞 3 | 跳过 2 | 直播 1"))
            time.sleep(1.5)
            done.set()

        win = FloatingLogWindow(q, stop, done, on_close=stop.set)
        threading.Thread(target=worker, daemon=True).start()
        win.run()
        print("overlay self-test OK")
