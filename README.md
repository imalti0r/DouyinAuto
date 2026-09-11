# DouyinAuto - PC 版抖音自动刷视频

自动刷 PC 版抖音推荐流：**模拟输入**操作 + **图像识别**判断内容 + **悬浮日志窗**实时显示运行状态。

- 目标视频（美女舞蹈 / 美女 cos）→ 按 `Z` 键点赞 → **未关注博主则按 `G` 关注** → 观看 → **鼠标滚轮**切下一个
- 其余视频 → 按 `R` 不感兴趣（视频**自动消失**，无需切换）
- 直播 → 检测到「点击进入直播」→ **直接滚轮切下一个**（不按 R，不处理弹窗）

## 内容判定模式（v2.0 新增视觉模式）

| 模式 | 原理 | 说明 |
|---|---|---|
| `vision`（默认） | **CLIP 视觉模型直接看画面** | 每个视频采样 3 帧画面，与「目标/非目标」提示词组对比相似度，不依赖文案 |
| `text` | OCR 识别文案关键词 | 依赖标题/话题标签里有"舞蹈/cos"等词 |
| `both` | 视觉或文案任一命中 | 召回优先（画面像 或 文案提到 都点赞） |

```bash
python main.py --mode vision   # 默认：CLIP 看画面
python main.py --mode text     # OCR 文案
python main.py --mode both     # 两者任一命中
```

视觉模式首次使用需下载模型（约 150MB，来自 hf-mirror 镜像）：

```bash
python download_models.py      # 下载到 models/ 目录
```

判定效果实测（CLIP ViT-B/32 量化版）：舞蹈/cosplay 美女画面概率 ≥0.99，
美食/游戏画面 ≤0.01；提示词可在 config.py 的
`POSITIVE_PROMPTS` / `NEGATIVE_PROMPTS` 自行调整。

## 工作原理

```
循环：截图抖音窗口（采样多帧）
  ├─ 直播检测（OCR 画面底部「点击进入直播」按钮）
  │     └─ 直播 → 直接滚轮切下一个（不按 R——会弹「为什么不喜欢该直播」窗口需要选选项）
  ├─ [vision] CLIP 画面分类 → 目标概率 ≥ 阈值 → 目标视频
  ├─ [text] OCR 文案 → 关键词命中 → 目标视频
  │     └─ 目标视频 → 按 Z 点赞 → 检测头像下方红/粉「+」→ 未关注则按 G 关注 → 观看 → 滚轮切下一个
  └─ 其余 → 按 R 不感兴趣（自动消失，无需切换）
全程：悬浮窗实时滚动显示日志 + 处理/点赞/直播计数
```

- 模拟输入：`pydirectinput`（SendInput 扫描码方式；Z 点赞 / R 不感兴趣 / G 关注），
  滚轮为原生 ctypes SendInput 实现（**模拟 ↓ 键在部分窗口状态下抖音不响应**，v3.3 起默认滚轮翻页，
  卡住恢复时自动改用另一种方式兜底）
- 屏幕截图：`mss`（只截抖音窗口区域）
- 画面理解：`CLIP ViT-B/32`（ONNX 量化版，onnxruntime CPU 运行，单帧约 75ms）
- 直播识别：`RapidOCR` 检测画面底部「点击进入直播」按钮
- 悬浮日志窗：置顶半透明、顶栏可拖动、点 × 停止程序（当前 Python 缺 tkinter 时自动找系统 Python 起子进程显示）
- 安全机制：F12 / 悬浮窗 × 停止、最大视频数上限、**每次模拟操作前检查抖音前台**（失去前台自动暂停等待）、卡住自动恢复

## 安装

```bash
pip install -r requirements.txt
python download_models.py   # 仅 vision/both 模式需要
```

## 使用步骤

1. **打开抖音 PC 版**，进入推荐流的视频播放界面（点开任意视频的全屏播放），
   保持抖音窗口在前台、**不被其他窗口遮挡**（程序截取的是屏幕像素）。

2. **试运行**（只识别打印决策，不实际点击/按键，建议先跑一次观察判定是否准确）：

   ```bash
   python main.py --dry-run
   # 或双击方式：run.bat --dry-run
   ```

3. **正式运行**：

   ```bash
   python main.py                 # 默认最多处理 100 个视频
   python main.py --max-videos 50 # 自定义数量
   ```

   最简单：**双击 `run.bat`** 即可（自动定位 Python、切到项目目录、参数透传，退出后窗口保留）。
   也可带参数：`run.bat --dry-run`、`run.bat --max-videos 50`、`run.bat --mode text`。

4. 运行期间**不要动鼠标键盘**（悬浮窗顶栏可拖动、点 ✕ 即停止；点击悬浮窗会使抖音暂时失去前台，程序会暂停等待你切回抖音后继续）。

## Git 管理

项目用 git 管理（`models/` 大文件、`__pycache__` 等已在 `.gitignore` 排除，
克隆后需 `python download_models.py` 重新下载模型）。常用：

```bash
git log --oneline     # 查看版本历史
git diff              # 查看未提交改动
git add -A && git commit -m "描述"
```

## 悬浮日志窗

- 屏幕左上角置顶半透明小窗，实时滚动显示判定结果与操作，顶栏显示 `处理 N | 赞 N | 跳过 N | 直播 N` 计数
- 位置/大小/透明度在 config.py 的 `OVERLAY_POS / OVERLAY_SIZE / OVERLAY_ALPHA` 调整
- `python main.py --no-overlay` 关闭悬浮窗（仅控制台输出）
- 当前 Python 没有 tkinter 也没关系：程序会自动探测系统里带 tkinter 的 Python（如 py 启动器）起子进程显示悬浮窗

## 已点赞状态识别（HDR 鲁棒）

程序用两层检测防止"已赞视频再按 Z 取消赞"：
1. **颜色几何检测**（主，HDR/SDR 通用）：OCR 定位点赞数 → 其正上方心形位置找红/粉实心块。
   开启 Windows HDR 后屏幕颜色会偏色（红色按钮变粉），模板匹配失效，此检测不受影响
2. 模板匹配 `liked_*.png`（兜底，SDR 环境有效）

## 自动关注博主（HDR 鲁棒，G 键）

点赞目标视频后，程序检测右侧头像下方是否有关注按钮（圆形红/粉底白色「+」），
未关注则按 `G` 键关注，并轮询确认按钮消失（关注生效实测约 1.6 秒）；
已关注的博主无该按钮，自动跳过。

检测采用**圆盘测量法**（不受 HDR 偏色、头像内容影响）：
OCR 定位点赞数 → 其正上方 162px 处的圆形区域内测「红/粉填充率 ≥0.30 且 亮白加号率 ≥0.04」。
点赞数定位用列聚类（点赞/评论/收藏/分享数 x 对齐成列，取最密集簇），
天然排除视频画面里的随机数字干扰。
顶部状态栏与结束统计均含「关注 N」计数。

回归测试：`python hdr_test.py` 截图当前画面并打印检测状态，便于人工核对。

## 常用配置（config.py）

| 配置 | 说明 |
|---|---|
| `DECIDE_MODE` | 判定模式：vision / text / both |
| `POSITIVE_PROMPTS` / `NEGATIVE_PROMPTS` | 视觉模式的目标/非目标提示词（英文效果最好） |
| `VISION_THRESHOLD` | 目标概率阈值（默认 0.5），调高更严格 |
| `VISION_FRAMES` / `VISION_SAMPLE_SPAN` | 每个视频采样帧数 / 采样时长（秒） |
| `LIKE_KEYWORDS` | text 模式：命中即点赞的文案关键词 |
| `EXCLUDE_KEYWORDS` | text 模式：命中即跳过的排除词 |
| `KEY_LIKE / KEY_DISLIKE / KEY_FOLLOW / KEY_NEXT` | 点赞 / 不感兴趣 / 关注 / 备用切换键（默认 z / r / g / down） |
| `ADVANCE_METHOD` | 切换下一个视频的方式：`scroll`（默认，鼠标滚轮）/ `down`（键盘 ↓） |
| `SCROLL_NOTCHES` / `SCROLL_SPOT` | 滚轮格数（负=向下）/ 滚轮悬停点（窗口比例坐标） |
| `PARK_OUTSIDE` / `PARK_SPOT` / `NEUTRAL_SPOT` | 鼠标停靠策略：默认停窗口内 `PARK_SPOT`（70%,70%）；`PARK_OUTSIDE=True` 时停窗口外桌面、`NEUTRAL_SPOT` 兜底。**勿停靠窗口顶部**——搜索框悬停会触发热搜弹框遮挡画面 |
| `WAIT_AFTER_DISLIKE` | 按 R 后等待视频自动消失的时长（秒） |
| `ADVANCE_AFTER_DISLIKE` | 默认 False（不感兴趣自动消失）；若按 R 后没反应改 True 强制按 ↓ |
| `LIVE_DETECT_REGION` / `LIVE_BUTTON_KEYWORDS` | 直播按钮检测区（窗口比例）/ 识别关键词（检测到直播直接滚轮切换） |
| `OVERLAY_*` | 悬浮窗：开关 / 位置 / 大小 / 透明度 / 指定 Python |
| `WATCH_TIME_LIKED / SKIP` | 目标/非目标视频观看时长区间（秒） |
| `FOREGROUND_TIMEOUT` | 抖音失去前台多久后自动退出（秒） |
| `MAX_VIDEOS` | 单次运行最多处理视频数 |

## 常见问题

- **翻页没反应 / 一直"卡住"**：v3.3 起默认鼠标滚轮翻页（模拟 ↓ 键在部分窗口状态下抖音不响应）。
  若滚轮也无效，调大 `SCROLL_NOTCHES`（如 -3）或改 `ADVANCE_METHOD = "down"`；
  真机验证可用 `python scroll_test.py`（只滚动一次并用画面对比确认是否翻页，无账号副作用）。
- **翻页后弹出热搜/搜索弹框挡住画面**：v3.4 已修复——鼠标全程停靠在窗口右侧桌面
  （最大化时停靠窗口左下角），绝不悬停搜索框/视频区。可用 `python park_verify.py`
  做回归验证（A/B 对比旧停靠点与新停靠点的截图 OCR，无账号副作用）。
- **开启 HDR 后识别不到点赞/关注状态**：v3.6 已修复——HDR 会让屏幕红色偏成粉色导致模板匹配失效，
  现已改为颜色检测（宽色域判定同时覆盖红/粉）。
  **关注按钮仍偶尔误判"已关注"**：v3.7 已修复——改为圆盘测量法（点赞数上方 162px 固定位置），
  彻底不受头像红色内容与按钮粘连的影响。可用 `python hdr_test.py` 快速核对当前识别状态。
- **误把普通视频当直播**：`LIVE_BUTTON_KEYWORDS` 只认「进入直播/直播中」，如仍有误报可收紧为 `["点击进入直播"]`。
- **按 R 后视频不消失**：把 `ADVANCE_AFTER_DISLIKE` 改为 `True`。
- **视频已点过赞再点赞会取消**：v3.6 起默认颜色几何检测已防护（HDR 也有效），无需配置。
- **视觉模式误判**：调整 `POSITIVE_PROMPTS` / `NEGATIVE_PROMPTS`（用自然英文描述画面），
  或调整 `VISION_THRESHOLD`（调高更严格、调低更宽松），改完先用 `--dry-run` 观察。
- **悬浮窗不显示**：确认系统装有带 tkinter 的 Python（官方安装包默认带），或在 `OVERLAY_PYTHON` 里写明完整路径。
- **程序总是提示"不在前台"**：确认抖音窗口没有被最小化/遮挡；点过悬浮窗后需点回抖音。

## 风险提示

自动化操作属于抖音明令禁止的行为，可能导致**账号被限流、降权或封禁**，
请自行评估风险、控制使用频率（`WATCH_TIME_*` 已内置随机拟人节奏）。
本程序仅供个人学习研究自动化与图像识别技术使用。
