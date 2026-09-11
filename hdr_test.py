# -*- coding: utf-8 -*-
"""HDR/SDR 检测回归测试：截图当前画面，验证颜色几何检测（关注按钮/已赞心）

用法: python hdr_test.py
画面要求：推荐流视频播放页（已赞/未关注状态均可，结果会标注预期）
"""
import time

import dy_vision
import dy_window


def main():
    dy_window.ensure_dpi_aware()
    hwnd, rect = dy_window.find_window("抖音")
    if rect is None:
        raise SystemExit("未找到抖音窗口")
    dy_window.activate_window(hwnd)
    time.sleep(1.5)
    frame = dy_window.ScreenCapture().grab(rect)

    print("frame:", frame.shape)
    pos = dy_vision.find_like_count_pos(frame)
    print("点赞数位置:", pos)
    print("已点赞检测(颜色):", dy_vision.detect_liked(frame))
    print("关注按钮检测(颜色):", dy_vision.find_follow_button(frame),
          "（None = 博主已关注，属正常）")
    print("提示: 请人工核对——画面若显示粉/红心则已点赞应为 True；"
          "头像下有红/粉+按钮则应返回坐标")


if __name__ == "__main__":
    main()
