# Trae 自动换任务（Context Handoff）

给 Trae CN 的长对话做「到点就换班」：写一张交接卡，自动开一个新任务，把交接卡带进去，旧对话原样保留在历史里。

## 为什么需要

长对话每一轮都会把整段历史重新发给模型，越聊越贵。手动开新任务又会丢上下文。这个工具把「换任务」变成一条命令：

```bash
python trae_handoff.py --file .trae/handoff/20261123-1120-signtalk-deploy.md
```

它会自动点击「+ 新任务」、把 `读 <交接卡> 继续` 粘进输入框并回车。新对话读到交接卡就能接着干活。

## 工作流

1. 第 25 轮：助手提醒「可以换任务了」。
2. 第 30 轮：助手写交接卡 `.trae/handoff/<日期>-<主题>.md`（8 个字段：目标/已完成/当前状态/关键文件/待办/约束/失败方案/下一步）。
3. 运行本工具自动开新任务并发送承接语。
4. 旧对话不删，随时可以回看。

配套的助手规则见 [rules/user_rules.md](rules/user_rules.md)，交接卡样板见 [handoff_template.md](handoff_template.md)。

## 环境要求

- Windows 10 1903+（用到系统自带 OCR，中文语言包）
- Python 3.9+，安装 `pyautogui`：`pip install pyautogui pillow`
- Trae CN 窗口可见、侧边栏展开（不要最小化）

## 用法

```bash
# 指定交接卡，自动拼「读 xxx 继续」
python trae_handoff.py --file .trae/handoff/20261123-1120-signtalk-deploy.md

# 直接给一句话
python trae_handoff.py --prompt "读 docs/plan.md 继续"

# 只定位按钮和输入框，不点击
python trae_handoff.py --file xxx.md --dry-run

# 建任务并粘贴，但不回车（先人工看一眼）
python trae_handoff.py --file xxx.md --no-send

# 不弹「请勿手动操作」提示窗
python trae_handoff.py --file xxx.md --no-popup
```

执行时会在屏幕右上角弹一个 12 秒的置顶浮窗，提醒用户「请不要动鼠标和键盘」——因为这时脚本正在点击和粘贴，手动操作会抢焦点导致失败。

## 实现要点（踩过的坑）

- **模拟键盘会被中文输入法吞掉**：逐字输入字母会变成拼音候选（屏幕上出现「这这这/啧啧啧」），文字根本没进输入框。所以文本一律走剪贴板 `Ctrl+V`，绕开输入法。
- **窗口截图坐标是物理像素**：高 DPI（150%）下逻辑坐标会差 1.5 倍。脚本用截图 + Windows OCR 拿物理坐标，直接交给 pyautogui，避免换算错误。
- **不要随便按 Esc**：在新任务页按 Esc 可能让页面回到上一状态，导致后续点击落空。
- **OCR 会吞标点**：校验时只比对字母数字，别拿带 `/` `-` 的整串去匹配。
- **Electron 没有 UI 自动化树**：只能靠 OCR + 坐标，所以界面改版时定位会失效，需要重新校准。
- **提示浮窗要放在右上角**：置顶窗口如果压住侧边栏或输入框，点击会被浮窗吃掉。`popup.py` 固定在右上角、无边框、自动关闭。

## 任务置顶

`trae_task_manager.py` 按标题找到任务行，悬停后点行尾的钉子按钮置顶：

```bash
python trae_task_manager.py --list
python trae_task_manager.py --task "Continue Signtalk Deployment" --action 置顶
```

删除：先把鼠标停到任务视图右上角的「...」按钮上，运行一次校准，脚本会记住坐标：

```bash
python trae_task_manager.py --calibrate
python trae_task_manager.py --task "signtalk" --action 删除 --confirm
```

执行删除时会弹常驻提示窗「正在删除任务，完成前请不要操作」，流程结束自动关闭；菜单里找不到「删除」会直接中止。

## 已知限制

- 只针对 Trae CN 的中文界面；换语言或大改版需要改定位逻辑。
- 多显示器 / 缩放比例变化时需要重新跑一次 `--dry-run` 看坐标。
- 不会替你判断「该不该换任务」，阈值由助手规则控制。

## License

MIT
