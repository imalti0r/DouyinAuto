# -*- coding: utf-8 -*-
"""集成测试：主程序 → 悬浮窗子进程 管道协议（窗口会短暂显示在屏幕上）"""
import glob
import os
import subprocess
import time

home = os.path.expanduser("~")
cands = glob.glob(os.path.join(home, "AppData", "Local", "Programs",
                               "Python", "Python*", "python.exe"))
assert cands, "找不到系统 Python"
py = cands[0]
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

p = subprocess.Popen([py, "dy_overlay.py", "--child"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     encoding="utf-8", env=env)

for i in range(5):
    p.stdin.write(f"[12:00:0{i}] 测试日志行 {i} —— 视频 #{i}\n")
    p.stdin.flush()
    time.sleep(0.3)
p.stdin.write("\x01S处理 5 | 赞 2 | 跳过 2 | 直播 1\n")
p.stdin.flush()
time.sleep(1.0)

assert p.poll() is None, "子进程不应提前退出"
p.stdin.close()  # 模拟主程序退出
rc = p.wait(timeout=10)
out = p.stdout.read()
print("child exited rc =", rc, "| stdout =", repr(out))
assert rc == 0, "子进程应正常退出"
print("=== overlay pipe test OK ===")
