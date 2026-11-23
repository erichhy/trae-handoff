# -*- coding: utf-8 -*-
"""trae_task_manager.py —— 按标题定位 Trae 任务，执行置顶 / 删除。

置顶：悬停任务行，点行尾钉子按钮。
删除：打开任务 -> 点右上角「...」-> 菜单里点「删除」-> 如有二次确认再点一次。

用法：
    python trae_task_manager.py --list
    python trae_task_manager.py --task "Install FlyClaw" --action 置顶
    python trae_task_manager.py --task "signtalk" --action 删除 --confirm
    python trae_task_manager.py --probe-menu          # 打开某任务后探测「...」菜单内容
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

import pyautogui

from trae_handoff import ocr_words, screenshot, set_clipboard

HERE = os.path.dirname(os.path.abspath(__file__))
POPUP_PY = os.path.join(HERE, "popup.py")
CONFIG = os.path.join(HERE, "config.json")

SIDEBAR_MAX_X = 460      # 任务列表列的最大 x
LIST_MIN_Y = 280         # 任务区起始 y（置顶标题在 284 附近，之前是导航区）
PIN_ICON_X = 506         # 行尾钉子按钮 x（像素实测中心）
MORE_ICON_X = 543        # 行尾「...」菜单按钮 x（悬停后出现）


def load_dot():
    """读取校准后的「...」坐标，没有就用默认值。"""
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            data = json.load(fh)
        return int(data["dot_x"]), int(data["dot_y"])
    except (OSError, ValueError, KeyError):
        return DOT_X, DOT_Y


def save_dot(x: int, y: int) -> None:
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump({"dot_x": x, "dot_y": y}, fh, ensure_ascii=False, indent=2)


def start_popup(text: str):
    try:
        return subprocess.Popen(
            [sys.executable, POPUP_PY, "--sticky", "--title", "正在处理任务", "--text", text],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return None


def stop_popup(proc) -> None:
    if proc is not None and proc.poll() is None:
        proc.terminate()


def _is_meta_line(title: str) -> bool:
    """判断是不是「置顶 6」「任务完成 · 19:03」这类附属行，不是任务标题。"""
    compact = title.replace(" ", "")
    if not compact:
        return True
    if compact.startswith("置顶") and compact[2:].isdigit():
        return True
    if "任务完成" in compact:
        return True
    return not any(ch.isalpha() or "\u4e00" <= ch <= "\u9fff" for ch in compact)


def list_tasks():
    words = ocr_words(screenshot())
    items = [(y, x, text) for text, x, y, w, h in words
             if x < SIDEBAR_MAX_X and y > LIST_MIN_Y and len(text.strip()) > 1]
    items.sort()
    rows = []
    for y, x, text in items:
        if rows and y - rows[-1][0] <= 14:
            rows[-1][1].append((x, text))
        else:
            rows.append([y, [(x, text)]])
    result = []
    for y, parts in rows:
        parts.sort()
        title = " ".join(t for _, t in parts)
        if _is_meta_line(title):
            continue
        result.append((y, title))
    return result


def find_row(title_key: str):
    matches = [(y, t) for y, t in list_tasks() if title_key.lower() in t.lower()]
    if not matches:
        return None
    matches.sort(key=lambda m: (m[1].strip().lower() != title_key.strip().lower(), len(m[1])))
    return matches[0][0]


def menu_words():
    # 右键菜单出现在任务行附近（左侧），不限定 x>1200
    return [(t, x, y, w, h) for t, x, y, w, h in ocr_words(screenshot())]


def click_menu_item(label: str) -> bool:
    """按子串匹配点击菜单项（OCR 会把「删除任务」拆成 删/除/任/务）。"""
    for text, x, y, w, h in menu_words():
        if label in text:
            pyautogui.click(x + w // 2, y + h // 2)
            time.sleep(1.2)
            return True
    return False


def click_delete_in_menu(task_y: int) -> bool:
    """在「...」菜单里找「删除任务」并点击（它在 task_y 下方约 300px）。"""
    for text, x, y, w, h in menu_words():
        if "删" in text and task_y + 250 <= y <= task_y + 360:
            pyautogui.click(x + w // 2, y + h // 2)
            time.sleep(1.2)
            return True
    return False


def click_confirm_delete() -> bool:
    """删除后的确认对话框里点「删除」（居中弹窗，避开右上角提示窗）。"""
    for text, x, y, w, h in menu_words():
        # 排除右上角常驻提示窗（x>1700 或 y<200）
        if "删" in text and 600 <= x <= 1700 and y > 200:
            pyautogui.click(x + w // 2, y + h // 2)
            time.sleep(1.2)
            return True
    return False


def ensure_menu_space(title_key: str, y: int) -> int:
    """菜单向下展开约需 320px；任务太靠下会被屏幕截断，先置顶把它移到顶部。"""
    if y <= 1000:
        return y
    pyautogui.moveTo(300, y)
    time.sleep(0.8)
    pyautogui.moveTo(PIN_ICON_X, y)
    time.sleep(0.4)
    pyautogui.click(PIN_ICON_X, y)
    time.sleep(1.6)
    new_y = find_row(title_key)
    return new_y if new_y is not None else y


def _flat_text(words) -> str:
    """把 OCR 词拼成一整串（只留字母数字、转小写），用于统计 token 出现次数。"""
    return "".join(re.sub(r"[^A-Za-z0-9]", "", t).lower() for t, *_ in words)


def _probe_tokens(content: str, limit: int = 4):
    """从内容里挑几个只在文中出现一次的英文/数字 token，作为「是否贴进去」的指纹。

    粘贴长文后输入框只露出末尾几行，所以优先取结尾部分的 token，取不够再从全文补。
    """
    tail = content[-300:]
    tokens = []
    for scope in (tail, content):
        flat = re.sub(r"[^A-Za-z0-9]", "", scope).lower()
        for tok in re.findall(r"[A-Za-z0-9]{6,}", scope):
            low = tok.lower()
            if flat.count(low) == 1 and low not in tokens:
                tokens.append(low)
        if len(tokens) >= limit:
            break
    return tokens[:limit]


def _input_candidates(words):
    """输入框候选点：优先按模型选择器推导，其次按屏幕比例兜底。"""
    width, height = pyautogui.size()
    pts = []
    for text, x, y, w, h in words:
        low = text.lower()
        if (low.startswith("deepseek") or low == "agent") and x > width * 0.25 and y > height * 0.5:
            pts += [(x + 380, y - 42), (x + 120, y - 42), (x + 380, y - 80)]
            break
    pts += [(int(width * 0.6), height - 160), (int(width * 0.6), height - 200),
            (int(width * 0.45), height - 170)]
    unique = []
    for p in pts:
        if p not in unique:
            unique.append(p)
    return unique


def send_message(title_key: str, content: str, no_send: bool = False) -> int:
    """打开指定任务，把 content 粘贴到输入框并发送（用于把交接卡写进已有任务）。"""
    y = find_row(title_key)
    if y is None:
        print(f"[x] 没找到标题包含「{title_key}」的任务")
        return 2
    print(f"[ok] 找到任务行 y={y}")

    probes = _probe_tokens(content)
    print(f"[ok] 校验指纹: {probes}")

    popup = start_popup("正在写入内容，请不要动鼠标键盘")
    try:
        pyautogui.click(300, y)
        time.sleep(3.0)

        base = _flat_text(ocr_words(screenshot()))
        points = _input_candidates(ocr_words(screenshot()))
        pasted = False
        for pt in points:
            pyautogui.click(*pt)
            time.sleep(0.6)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.press("delete")
            time.sleep(0.4)
            set_clipboard(content)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(1.6)

            now = _flat_text(ocr_words(screenshot()))
            hit = [p for p in probes if now.count(p) > base.count(p)]
            if hit:
                print(f"[ok] 已贴入输入框（命中 {hit}）")
                pasted = True
                break
            print(f"[!] 点 ({pt[0]}, {pt[1]}) 没能贴进去，换下一个候选点")

        if not pasted:
            print("[x] 粘贴失败：没找到可聚焦的输入框")
            return 3
        if no_send:
            print("[ok] 已粘贴，未发送（--no-send）")
            return 0

        pyautogui.press("enter")
        time.sleep(3.0)

        now = _flat_text(ocr_words(screenshot()))
        hit = [p for p in probes if now.count(p) > base.count(p)]
        if hit:
            print(f"[ok] 已发送，任务里能看到内容（命中 {hit}）")
            return 0
        print("[!] 已回车，但没在屏幕上确认到内容，请人工看一眼该任务")
        return 4
    finally:
        stop_popup(popup)


def main() -> int:
    ap = argparse.ArgumentParser(description="Trae 任务置顶/删除")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--task", help="任务标题关键字")
    ap.add_argument("--action", help="置顶 / 删除 / 发消息")
    ap.add_argument("--file", help="发消息时读取的文件（交接卡）")
    ap.add_argument("--text", help="发消息时直接给内容")
    ap.add_argument("--no-send", action="store_true", help="发消息时只粘贴不回车")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true", help="删除必须带上")
    ap.add_argument("--probe-menu", action="store_true", help="打开菜单并打印识别到的菜单项")
    ap.add_argument("--calibrate", action="store_true", help="把当前鼠标位置记为「...」按钮坐标")
    ap.add_argument("--dot-x", type=int, default=None)
    ap.add_argument("--dot-y", type=int, default=None)
    args = ap.parse_args()

    if args.calibrate:
        x, y = pyautogui.position()
        save_dot(x, y)
        print(f"[ok] 已记录「...」按钮坐标: ({x}, {y})")
        return 0

    cfg_x, cfg_y = load_dot()
    args.dot_x = args.dot_x if args.dot_x is not None else cfg_x
    args.dot_y = args.dot_y if args.dot_y is not None else cfg_y

    if args.list:
        for y, title in list_tasks():
            print(f"y={y:<5} {title}")
        return 0

    if not args.task or not args.action:
        print("需要 --task 和 --action")
        return 1
    if args.action == "删除" and not args.confirm and not args.probe_menu:
        print("删除操作不可恢复，请加 --confirm")
        return 1

    y = find_row(args.task)
    if y is None:
        print(f"[x] 没找到标题包含「{args.task}」的任务")
        return 2
    print(f"[ok] 找到任务行 y={y}")
    if args.dry_run:
        return 0

    if args.action == "置顶":
        popup = start_popup("正在置顶任务，请不要动鼠标键盘")
        try:
            pyautogui.moveTo(300, y)
            time.sleep(0.8)
            pyautogui.moveTo(PIN_ICON_X, y)
            time.sleep(0.4)
            pyautogui.click(PIN_ICON_X, y)
            time.sleep(1.5)
        finally:
            stop_popup(popup)
        print("[ok] 已点钉子，看左侧「置顶」数量是否变化")
        return 0

    if args.action == "发消息":
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                content = fh.read().strip()
        elif args.text:
            content = args.text
        else:
            print("发消息需要 --file 或 --text")
            return 1
        if args.dry_run:
            y = find_row(args.task)
            print(f"[dry-run] 目标行 y={y}，内容 {len(content)} 字")
            return 0
        return send_message(args.task, content, args.no_send)

    if args.action != "删除":
        print("不支持的 action，只支持 置顶 / 删除")
        return 1

    # 删除流程（不可逆，执行前已由 --confirm 把关）
    # 入口：悬停任务行 -> 点「...」按钮 -> 菜单里点「删除任务」-> 确认
    popup = start_popup("正在删除任务，完成前请不要操作")
    try:
        # 任务在列表底部时菜单会被屏幕截断，先置顶移到顶部
        y = ensure_menu_space(args.task, y)
        if y is None:
            print(f"[x] 定位失败「{args.task}」")
            return 2
        print(f"[ok] 任务已就位 y={y}")

        pyautogui.moveTo(300, y)
        time.sleep(0.9)
        pyautogui.moveTo(MORE_ICON_X, y)
        time.sleep(0.4)
        pyautogui.click(MORE_ICON_X, y)
        time.sleep(1.2)

        if args.probe_menu:
            print("[menu] 「...」菜单识别到的文字：")
            for text, x, yy, w, h in menu_words():
                if y <= yy <= y + 380:
                    print(f"  ({x},{yy}) {text}")
            pyautogui.press("escape")
            return 0

        if not click_delete_in_menu(y):
            print("[x] 菜单里没找到「删除任务」，已中止（未删除任何东西）")
            for text, x, yy, w, h in menu_words():
                if y <= yy <= y + 380:
                    print(f"  候选: ({x},{yy}) {text}")
            return 3

        # 确认对话框（如果有）
        time.sleep(0.8)
        click_confirm_delete()
        time.sleep(1.5)
    finally:
        stop_popup(popup)
    print("[ok] 删除流程结束，请确认左侧列表是否已消失")
    return 0


if __name__ == "__main__":
    sys.exit(main())
