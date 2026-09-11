# -*- coding: utf-8 -*-
"""DouyinAuto 配置：所有可调参数集中在这里"""

# ---------- 窗口 ----------
WINDOW_TITLE = "抖音"          # 抖音 PC 版窗口标题（模糊匹配，包含即可）
                            # 找不到窗口时会回退使用整个主屏幕

# ---------- 内容判定（OCR 文案关键词） ----------
# 命中任一关键词 → 视为目标视频（点赞）；可自行增删
LIKE_KEYWORDS = [
    # 舞蹈类
    "舞蹈", "跳舞", "热舞", "翻跳", "宅舞", "女团", "爵士",
    "古典舞", "民族舞", "韩舞", "街舞", "dance", "唱跳",
    # cos / 二次元类
    "cos", "coser", "cosplay", "二次元", "汉服", "jk", "JK",
    "旗袍", "lolita", "洛丽塔", "和服", "古装",
    # 美女类（可选，按需增删）
    "小姐姐", "美女", "写真", "泳装",
]

# ---------- 内容判定模式 ----------
# "vision" - CLIP 视觉模型直接识别画面内容（默认，不依赖文案）
# "text"   - OCR 文案关键词判定（旧方案）
# "both"   - 视觉或文案任一命中即点赞（召回优先）
DECIDE_MODE = "vision"

# CLIP 视觉判定参数
CLIP_MODEL_DIR = "models"       # download_models.py 下载的模型目录
VISION_FRAMES = 3               # 每个视频采样帧数
VISION_SAMPLE_SPAN = 3.0        # 采样总时长（秒），多帧覆盖不同镜头
VISION_THRESHOLD = 0.5          # 目标概率阈值 [0,1]，调高更严格、调低更宽松
STUCK_EMBED_COS = 0.95          # 相邻两轮画面嵌入余弦超过此值 → 判定卡在同一视频

# 目标提示词组（CLIP 用英文效果最好）
POSITIVE_PROMPTS = [
    "a beautiful young woman dancing",
    "a pretty girl in cosplay costume",
    "a woman in anime cosplay outfit",
    "a female dancer performing K-pop dance",
    "an attractive young woman posing for the camera",
    "a girl in hanfu or JK school uniform",
    "a woman in a cheongsam or lolita dress",
    "an idol girl group performing on stage",
    "a young woman in a short skirt dancing",
]

# 非目标提示词组（覆盖常见短视频内容类型）
NEGATIVE_PROMPTS = [
    "a plate of delicious food",
    "a man talking to the camera",
    "video game gameplay footage",
    "a car or motorcycle",
    "natural scenery and landscape",
    "cute pets and animals",
    "a basketball or football match",
    "a news anchor in a studio",
    "a product unboxing review",
    "a cartoon anime drawing",
    "a cooking tutorial",
    "a travel vlog of scenery",
    "a text message or meme screenshot",
    "the interface of a software application",
]

# 排除关键词：即使命中点赞关键词，若同时命中这里则跳过（不感兴趣）
# 注意：不要放会出现在界面固定文字里的词（如侧边栏"小游戏/直播"），
#       否则所有视频都会被误排除
EXCLUDE_KEYWORDS = [
    "带货", "教程",
]

# ---------- 图像识别 ----------
TEMPLATE_DIR = "templates"     # 点赞按钮模板图目录（like_*.png）
TEMPLATE_THRESHOLD = 0.80      # 模板匹配置信度阈值
TEMPLATE_SCALES = [1.0, 0.9, 1.1, 0.8, 1.2]  # 多尺度匹配（窗口缩放时更稳）
MIN_OCR_SCORE = 0.5            # OCR 识别置信度低于此值的文本丢弃

# 屏幕区域（相对抖音窗口的比例坐标 x0,y0,x1,y1）
# 点赞按钮搜索区：窗口右侧操作栏（实测爱心约在窗口高度 52% 处）
ACTION_BAR_REGION = (0.85, 0.15, 1.00, 0.95)
# 文案 OCR 区：视频左下（作者名 + 标题 + 话题标签），x0=0.11 跳过左侧导航栏
CAPTION_REGION = (0.11, 0.40, 0.75, 1.00)

# ---------- 模拟输入 ----------
ADVANCE_METHOD = "scroll"        # 切换下一个视频的方式：
                                 #   "scroll" = 鼠标滚轮（推荐；部分窗口状态下模拟 ↓ 键不生效）
                                 #   "down"   = 键盘 ↓ 键
SCROLL_NOTCHES = -2              # 滚轮格数（负数=向下滚=下一个视频）
SCROLL_SPOT = (0.50, 0.50)       # 滚轮悬停点（窗口比例坐标，视频画面中心）
PARK_OUTSIDE = False             # False：鼠标停靠在窗口内 PARK_SPOT（用户指定 70%,70%）
PARK_SPOT = (0.70, 0.70)         # 鼠标停靠点（窗口比例坐标）
NEUTRAL_SPOT = (0.03, 0.96)      # PARK_OUTSIDE=True 时的窗口内兜底位（旧逻辑保留）
                                 # （左下角实测无悬停 UI；勿放顶部——搜索框会触发热搜弹框）
KEY_NEXT = "down"                # 备用：键盘 ↓ 下一个视频（滚轮卡住时自动改用）
KEY_LIKE = "z"                 # 点赞（抖音 PC 版快捷键 Z）
KEY_DISLIKE = "r"              # 不感兴趣（抖音 PC 版快捷键）
KEY_FOLLOW = "g"               # 关注博主（抖音 PC 版快捷键，点赞后未关注则自动按）
ADVANCE_AFTER_DISLIKE = False  # 不感兴趣的视频会自动消失，无需按 ↓（True 则额外按 ↓ 强制切换）
MOUSE_MOVE_DURATION = 0.25     # 鼠标移动耗时（秒），模拟人手
WAIT_AFTER_LIKE = (1.0, 2.0)   # 按 Z 点赞后等待动画（秒），随后按 ↓ 切下一个
WAIT_AFTER_DISLIKE = (2.0, 4.0)  # 按 R 后等待视频自动消失/下一个加载（秒）

# ---------- 悬浮日志窗 ----------
OVERLAY_ENABLED = True         # 是否显示悬浮日志窗（False 则仅控制台输出）
OVERLAY_POS = (80, 60)         # 窗口左上角屏幕坐标（默认左上角，避开右侧操作栏与左下文案区）
OVERLAY_SIZE = (480, 300)      # 窗口宽高（像素）
OVERLAY_ALPHA = 0.88           # 不透明度 0-1
OVERLAY_MAX_LINES = 200        # 日志最多保留行数
OVERLAY_PYTHON = ""            # 指定带 tkinter 的 python.exe 路径；留空自动探测
                               # （当前 Python 缺 tkinter 时会自动找系统 Python 起子进程显示悬浮窗）

# ---------- 直播检测 ----------
# 推荐流里的直播会在画面底部中心显示「点击进入直播」按钮，OCR 该区域识别
# 检测到直播后直接滚轮切下一个（不按 R——会弹「为什么不喜欢该直播」窗口需要选选项）
LIVE_DETECT_REGION = (0.20, 0.72, 0.80, 1.00)   # 底部中心条带
LIVE_BUTTON_KEYWORDS = ["进入直播", "直播中"]

# ---------- 节奏控制 ----------
WATCH_TIME_LIKED = (3.0, 5.0)   # 目标视频观看时长区间（秒）
WATCH_TIME_SKIP = (0.5, 1.5)     # 非目标视频观看时长区间（秒）
ACTION_DELAY = 1.0               # 切换视频后等待画面稳定（秒）

# ---------- 安全限制 ----------
MAX_VIDEOS = 1000               # 最多处理多少个视频后自动停止
STOP_HOTKEY = "f12"            # 全局停止热键
STUCK_LIMIT = 2                # 连续 N 次画面未变化判定为卡住（按 Esc+↓ 恢复）
FOREGROUND_TIMEOUT = 60        # 抖音失去前台超过 N 秒自动退出（防止误操作其他窗口）
