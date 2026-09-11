# -*- coding: utf-8 -*-
"""DouyinAuto 主程序：自动刷 PC 版抖音推荐流

流程（v3.8）：
  采样画面 → 直播检测 →（直播: 直接滚轮切下一个，不按 R 不处理弹窗）
                      →（视频: CLIP 看画面 / OCR 读文案 判定）
                          ├─ 目标视频 → Z 键点赞 →（未关注博主则按 G 关注）→ 观看 → 滚轮切下一个
                          └─ 其余视频 → R 不感兴趣（自动消失，无需切换）
鼠标停靠在窗口内 PARK_SPOT（默认 70%,70%）；悬浮窗日志自动换行；F12 或悬浮窗 × 停止。
"""
import argparse
import glob
import os
import shutil
import subprocess
import threading
import time
from queue import Queue, Full

from pynput import keyboard

import config
import dy_input
import dy_vision
import dy_window

stop_event = threading.Event()
done_event = threading.Event()
stats = {"processed": 0, "liked": 0, "followed": 0, "disliked": 0, "live": 0,
         "unknown": 0, "stuck": 0}

log_queue = Queue(maxsize=500)
_overlay = None  # OverlayManager 实例（main 中创建）


def start_stop_listener():
    """全局热键监听（默认 F12 停止）"""
    hotkey = getattr(keyboard.Key, config.STOP_HOTKEY.lower(), keyboard.Key.f12)

    def on_press(key):
        if key == hotkey:
            stop_event.set()
            return False

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    return listener


def _emit(kind, text):
    """日志路由：有悬浮窗管理器走管理器，否则进本地队列（等待悬浮窗消费）"""
    if _overlay is not None:
        _overlay.emit(kind, text)
    else:
        try:
            log_queue.put_nowait((kind, text))
        except Full:
            pass


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _emit("log", line)


def log_status():
    _emit("status",
          f"处理 {stats['processed']} | 赞 {stats['liked']} | "
          f"关注 {stats['followed']} | 跳过 {stats['disliked']} | 直播 {stats['live']}")


class OverlayManager:
    """悬浮窗管理：优先本进程 tkinter；无 tkinter 时探测系统 Python 起子进程
    子进程协议：stdin 传日志行（\x01S 前缀=状态），子进程 × → stdout 输出 STOP"""

    def __init__(self):
        self.mode = None      # "local" / "sub" / None
        self.win = None
        self.proc = None

    def start(self):
        if not config.OVERLAY_ENABLED:
            return
        # 1) 本进程 tkinter
        try:
            from dy_overlay import FloatingLogWindow
            self.win = FloatingLogWindow(log_queue, stop_event, done_event,
                                         on_close=stop_event.set)
            self.mode = "local"
            return
        except ImportError:
            pass
        except Exception as e:
            print(f"[警告] 本进程悬浮窗创建失败: {e}")
        # 2) 子进程（找一个带 tkinter 的 Python）
        py = self._find_tk_python()
        if py is None:
            print("[警告] 未找到带 tkinter 的 Python，悬浮窗不可用，仅控制台输出")
            return
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dy_overlay.py")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        try:
            self.proc = subprocess.Popen(
                [py, script, "--child"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                encoding="utf-8", env=env,
                creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            print(f"[警告] 悬浮窗子进程启动失败({e})，仅控制台输出")
            return
        self.mode = "sub"
        threading.Thread(target=self._reader, daemon=True).start()
        # 补发启动阶段积压在本地队列的日志
        from queue import Empty
        try:
            while True:
                kind, text = log_queue.get_nowait()
                self.emit(kind, text)
        except Empty:
            pass
        print(f"悬浮窗已启动（子进程: {py}）")

    def _find_tk_python(self):
        candidates = []
        if config.OVERLAY_PYTHON:
            candidates.append(config.OVERLAY_PYTHON)
        candidates.append(shutil.which("py"))
        candidates.append(shutil.which("python3"))
        candidates.append(shutil.which("python"))
        home = os.path.expanduser("~")
        candidates += glob.glob(
            os.path.join(home, "AppData", "Local", "Programs", "Python",
                         "Python*", "python.exe"))
        for exe in candidates:
            if not exe or not os.path.exists(exe):
                continue
            try:
                r = subprocess.run([exe, "-c", "import tkinter"],
                                   capture_output=True, timeout=20,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                if r.returncode == 0:
                    return exe
            except Exception:
                continue
        return None

    def _reader(self):
        """读子进程输出：STOP = 用户点了悬浮窗 ×"""
        try:
            for line in self.proc.stdout:
                if line.strip() == "STOP":
                    stop_event.set()
                    break
        except OSError:
            pass

    def emit(self, kind, text):
        if self.mode == "local":
            try:
                log_queue.put_nowait((kind, text))
            except Full:
                pass
        elif self.mode == "sub" and self.proc is not None:
            try:
                prefix = "\x01S" if kind == "status" else ""
                self.proc.stdin.write(prefix + text + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                self.proc = None  # 悬浮窗已关闭/崩溃，后续仅控制台

    def run(self):
        """阻塞直至悬浮窗关闭（仅 local 模式；sub 模式立即返回）"""
        if self.mode == "local" and self.win is not None:
            self.win.run()

    def close(self):
        if self.mode == "sub" and self.proc is not None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass


class Decider:
    """内容判定器：按模式调用视觉/文案判定"""

    def __init__(self, mode, clip=None):
        self.mode = mode
        self.clip = clip
        self.last_embed = None  # 上一轮画面平均嵌入（vision 模式卡住检测用）

    def sample_frames(self, cap, rect, refresh_rect=None):
        """按 VISION_FRAMES / VISION_SAMPLE_SPAN 采样多个画面帧"""
        frames = [cap.grab(rect)]
        n = config.VISION_FRAMES
        if n > 1:
            gap = config.VISION_SAMPLE_SPAN / (n - 1)
            for _ in range(n - 1):
                time.sleep(gap)
                if stop_event.is_set():
                    break
                if refresh_rect is not None:
                    r = refresh_rect()
                    if r is not None:
                        rect = r
                frames.append(cap.grab(rect))
        return frames, rect

    def is_stuck(self, frames):
        """vision 模式：本轮画面嵌入与上一轮几乎相同 → 卡在同一视频"""
        import numpy as np
        embeds = self.clip.encode_images(frames)
        mean = embeds.mean(axis=0)
        mean = mean / np.linalg.norm(mean)
        stuck = False
        if self.last_embed is not None:
            stuck = float(mean @ self.last_embed) >= config.STUCK_EMBED_COS
        self.last_embed = mean
        return stuck

    def decide(self, frames, caption):
        """返回 (is_target, 说明文本)"""
        if self.mode == "vision":
            is_t, prob, _ = self.clip.classify_frames(frames)
            return is_t, f"画面概率={prob:.3f}"
        if self.mode == "text":
            is_t, kw = dy_vision.classify(caption)
            return is_t, f"文案命中[{kw}]" if is_t else "文案未命中"
        # both: 视觉或文案任一命中
        v_t, prob, _ = self.clip.classify_frames(frames)
        t_t, kw = dy_vision.classify(caption)
        return (v_t or t_t), f"画面={prob:.3f} 文案{'命中['+kw+']' if t_t else '未命中'}"


def process_one_video(frames, caption, rect, liked_tpls, decider, dry_run,
                      ensure_fg):
    """处理当前视频，返回动作名称"""
    # 直播优先检测（画面底部中心「点击进入直播」按钮）→ 直接滚轮切换
    is_live, live_text = dy_vision.detect_livestream(frames[-1])
    if is_live:
        log(f"  检测到直播（{live_text}）→ 直接切换")
        stats["live"] += 1
        return "live"

    # 已点赞检测（模板匹配 或 HDR 鲁棒颜色检测）→ 跳过（防止 Z 键取消赞）
    is_liked = (liked_tpls and dy_vision.find_button(frames[-1], liked_tpls)) \
        or dy_vision.detect_liked(frames[-1])
    if is_liked:
        log("  该视频已点过赞，跳过点赞")
        return "already_liked"

    if decider.mode != "vision" and not caption.strip():
        log("  未能识别到文案（OCR 为空），跳过不动作")
        return "unknown"

    is_target, why = decider.decide(frames, caption)
    log(f"  判定: {'目标视频' if is_target else '非目标'}（{why}）")

    if is_target:
        log(f"  → 模拟按键 [{config.KEY_LIKE}] 点赞")
        if not dry_run:
            ensure_fg()
            dy_input.press_key(config.KEY_LIKE)
        stats["liked"] += 1
        return "liked"
    else:
        log(f"  → 模拟按键 [{config.KEY_DISLIKE}] 不感兴趣")
        if not dry_run:
            ensure_fg()
            dy_input.press_key(config.KEY_DISLIKE)
        stats["disliked"] += 1
        return "disliked"


def run_loop(args, mode, decider, hwnd, rect, cap, liked_tpls):
    """工作线程主循环"""
    state = {"rect": rect}

    def get_rect():
        if hwnd is not None:
            r = dy_window.get_hwnd_rect(hwnd)
            if r is None:
                return None
            state["rect"] = r
        return state["rect"]

    def wait_foreground():
        """抖音不在前台时等待用户切回（截图和模拟输入都需要前台），超时退出"""
        if hwnd is None or dy_window.is_foreground(hwnd):
            return True
        log("[注意] 抖音窗口不在前台（截图/按键会作用到其他窗口），等待切回...")
        t0 = time.time()
        last_try = 0.0
        while not stop_event.is_set():
            if dy_window.is_foreground(hwnd):
                log("抖音已回到前台，继续")
                return True
            if time.time() - t0 > config.FOREGROUND_TIMEOUT:
                log(f"[错误] 等待超过 {config.FOREGROUND_TIMEOUT}s 仍未切回，程序退出")
                return False
            if time.time() - last_try >= 10:
                dy_window.activate_window(hwnd)
                last_try = time.time()
            time.sleep(0.5)
        return False

    def ensure_fg():
        return wait_foreground()

    def park():
        """把鼠标停到安全位置（窗口外桌面优先），避免悬停 UI 遮挡截图"""
        if not args.dry_run:
            r = get_rect() or state["rect"]
            dy_input.move_to(*dy_input.park_point(r))

    def advance(dry, method=None, note=""):
        """切换到下一个视频：默认鼠标滚轮（模拟 ↓ 键在部分窗口状态下不生效）"""
        m = method or config.ADVANCE_METHOD
        if m == "scroll":
            log(f"  → 滚轮切换下一个视频{note}")
            if not dry:
                ensure_fg()
                r = get_rect() or state["rect"]
                w_, h_ = r[2] - r[0], r[3] - r[1]
                sx = r[0] + int(w_ * config.SCROLL_SPOT[0])
                sy = r[1] + int(h_ * config.SCROLL_SPOT[1])
                dy_input.scroll_wheel(config.SCROLL_NOTCHES, sx, sy,
                                      then_move=dy_input.park_point(r))
        else:
            log(f"  → 模拟按键 [{config.KEY_NEXT}]{note}")
            if not dry:
                ensure_fg()
                r = get_rect() or state["rect"]
                dy_input.press_key(config.KEY_NEXT)
                dy_input.move_to(*dy_input.park_point(r))

    def follow_if_needed(dry):
        """点赞后自动关注：检测头像下方红/粉「+」按钮（圆盘测量法，HDR 鲁棒），
        未关注则按 G 键关注；已关注（无按钮）跳过"""
        cur = get_rect()
        if cur is None:
            return
        frame = cap.grab(cur)
        hit = dy_vision.find_follow_button(frame)
        if hit is None:
            log("  博主已关注（未检测到关注按钮）")
            return
        log(f"  → 未关注博主，按 [{config.KEY_FOLLOW.upper()}] 关注")
        if not dry:
            ensure_fg()
            dy_input.press_key(config.KEY_FOLLOW)
            # G 生效有延迟（实测按钮约 1.6 秒后消失），轮询确认
            ok = False
            for _ in range(7):
                time.sleep(0.45)
                cur2 = get_rect() or cur
                if dy_vision.find_follow_button(cap.grab(cur2)) is None:
                    ok = True
                    break
            if not ok:
                log("  [警告] 按关注键 3 秒后仍检测到关注按钮，请确认 G 键快捷键有效")
        stats["followed"] += 1
        dy_input.human_sleep(0.4, 0.8)

    log(f">>> 请确保抖音窗口在前台且处于推荐流播放界面 <<<")
    log(f">>> 运行期间请勿移动鼠标/敲键盘，按 {config.STOP_HOTKEY.upper()} 随时停止 <<<")
    for i in range(5, 0, -1):
        log(f"  {i} 秒后开始...")
        time.sleep(1)

    last_caption_marker = None   # text 模式卡住检测
    stuck_count = 0

    try:
        while not stop_event.is_set() and stats["processed"] < args.max_videos:
            if not wait_foreground():
                break
            # 实时刷新窗口位置（用户可能移动了窗口）
            cur = get_rect()
            if cur is None:
                log("[错误] 抖音窗口已关闭，程序退出")
                break
            state["rect"] = cur

            # 采样前先把鼠标停到安全位置（防止悬停 UI 如热搜弹框/进度条遮挡画面）
            park()

            # 采样多帧画面（观看过程）
            frames, cur = decider.sample_frames(cap, cur, get_rect)
            if stop_event.is_set():
                break
            state["rect"] = cur
            caption = ""
            if mode != "vision":
                caption = dy_vision.ocr_caption(frames[0])

            # 卡住检测
            if mode == "vision":
                stuck_now = decider.is_stuck(frames)
            else:
                stuck_now = not dy_vision.is_video_changed(caption, last_caption_marker or "")
                last_caption_marker = caption
            if stuck_now:
                stuck_count += 1
                log(f"  [卡住] 画面与上一轮相同 ({stuck_count}/{config.STUCK_LIMIT})")
                if stuck_count >= config.STUCK_LIMIT:
                    alt = "down" if config.ADVANCE_METHOD == "scroll" else "scroll"
                    log(f"  → 尝试恢复: Esc + 切换（改用{'键盘↓兜底' if alt == 'down' else '滚轮兜底'}）")
                    if not args.dry_run:
                        ensure_fg()
                        dy_input.press_key("esc")
                        time.sleep(0.8)
                    advance(args.dry_run, method=alt, note="（卡住恢复）")
                    stuck_count = 0
                    stats["stuck"] += 1
                    dy_input.human_sleep(config.ACTION_DELAY, config.ACTION_DELAY + 0.5)
                    continue
            else:
                stuck_count = 0

            stats["processed"] += 1
            log(f"—— 视频 #{stats['processed']}/{args.max_videos} ——")
            action = process_one_video(frames, caption, cur, liked_tpls, decider,
                                       args.dry_run, ensure_fg)
            if action == "unknown":
                stats["unknown"] += 1
            log_status()

            # 观看节奏 + 切换策略
            if action == "liked":
                dy_input.human_sleep(*config.WAIT_AFTER_LIKE)  # 等点赞动画/生效
                follow_if_needed(args.dry_run)                  # 未关注博主则自动关注
                dy_input.human_sleep(*config.WATCH_TIME_LIKED)
                advance(args.dry_run)
            elif action == "live":
                # 直播：不按 R（会弹「为什么不喜欢」窗口），直接滚轮切下一个
                dy_input.human_sleep(0.8, 1.5)
                advance(args.dry_run, note="（直播）")
            elif action == "disliked":
                # 不感兴趣的视频会自动消失，无需滚轮切换
                dy_input.human_sleep(*config.WAIT_AFTER_DISLIKE)
                if config.ADVANCE_AFTER_DISLIKE:
                    advance(args.dry_run, note="（ADVANCE_AFTER_DISLIKE 强制切换）")
            elif action == "unknown":
                log("  → 文案未识别，仅切换跳过")
                advance(args.dry_run)
            else:  # target / already_liked
                dy_input.human_sleep(*config.WATCH_TIME_LIKED)
                advance(args.dry_run)

            dy_input.human_sleep(config.ACTION_DELAY, config.ACTION_DELAY + 0.8)

    except KeyboardInterrupt:
        log("收到停止信号")
    except Exception as e:
        import traceback
        log(f"[错误] 运行异常: {e}")
        traceback.print_exc()
    finally:
        done_event.set()
        log_status()


def main():
    parser = argparse.ArgumentParser(description="自动刷 PC 版抖音（模拟输入 + 图像识别）")
    parser.add_argument("--dry-run", action="store_true", help="试运行：只识别打印，不实际点击/按键")
    parser.add_argument("--max-videos", type=int, default=config.MAX_VIDEOS, help="最多处理视频数")
    parser.add_argument("--mode", choices=["vision", "text", "both"],
                        default=config.DECIDE_MODE, help="判定模式：vision=看画面 / text=读文案 / both=两者")
    parser.add_argument("--no-overlay", action="store_true", help="不显示悬浮日志窗")
    args = parser.parse_args()
    mode = args.mode

    print("=" * 62)
    print("  DouyinAuto - PC 版抖音自动刷视频 (v3.8)")
    print(f"  模式: {'【试运行】仅识别不操作' if args.dry_run else '正常运行'} | "
          f"判定: {mode}{'(CLIP看画面)' if 'vision' in mode else '(OCR文案)'}")
    print(f"  上限: {args.max_videos} 个视频 | 停止: {config.STOP_HOTKEY.upper()} 或悬浮窗×")
    print("=" * 62)

    dy_window.ensure_dpi_aware()

    clip = None
    if mode in ("vision", "both"):
        log("加载 CLIP 视觉模型...")
        from dy_clip import ClipClassifier
        t0 = time.time()
        clip = ClipClassifier()
        log(f"CLIP 模型就绪（{time.time() - t0:.1f}s），"
            f"提示词: 正面 {len(config.POSITIVE_PROMPTS)} / 负面 {len(config.NEGATIVE_PROMPTS)}")

    decider = Decider(mode, clip)

    hwnd, rect = dy_window.find_window(config.WINDOW_TITLE)
    if rect is None:
        log(f"[提示] 未找到标题含「{config.WINDOW_TITLE}」的窗口，回退到主屏幕全屏模式")
        hwnd = None
        rect = dy_window.get_screen_rect()
    else:
        log(f"找到抖音窗口 rect={rect}")
        dy_window.activate_window(hwnd)

    cap = dy_window.ScreenCapture()
    liked_tpls = dy_vision.load_templates(prefix="liked_")
    log(f"已加载已点赞模板 {len(liked_tpls)} 张"
        + ("" if liked_tpls else "（无 → 不检测已赞状态，请勿对已赞视频运行）"))

    start_stop_listener()

    # 悬浮日志窗（自动探测 tkinter：本进程或系统 Python 子进程）
    global _overlay
    overlay = None
    if not args.no_overlay:
        overlay = OverlayManager()
        overlay.start()
        _overlay = overlay

    worker = threading.Thread(
        target=run_loop,
        args=(args, mode, decider, hwnd, rect, cap, liked_tpls),
        daemon=True)
    worker.start()

    try:
        if overlay is not None and overlay.mode == "local":
            overlay.run()   # 阻塞在 tkinter mainloop，关窗即返回
        else:
            while not done_event.is_set():
                time.sleep(0.2)
    except KeyboardInterrupt:
        stop_event.set()

    stop_event.set()
    worker.join(timeout=15)
    if overlay is not None:
        overlay.close()
    print("\n" + "=" * 62)
    print(f"  运行结束 | 处理 {stats['processed']} | 点赞 {stats['liked']} | "
          f"关注 {stats['followed']} | 不感兴趣 {stats['disliked']} | "
          f"直播 {stats['live']} | 未识别 {stats['unknown']} | 卡住恢复 {stats['stuck']}")
    print("=" * 62)


if __name__ == "__main__":
    main()
