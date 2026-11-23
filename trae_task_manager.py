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
import subprocess
import sys
import time

import pyautogui

from trae_handoff import ocr_words, screenshot

HERE = os.path.dirname(os.path.abspath(__file__))
POPUP_PY = os.path.join(HERE, "popup.py")
CONFIG = os.path.join(HERE, "config.json")

SIDEBAR_MAX_X = 460      # 任务列表列的最大 x
LIST_MIN_Y = 430         # 任务区起始 y
PIN_ICON_X = 515         # 行尾钉子按钮 x
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Trae 任务置顶/删除")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--task", help="任务标题关键字")
    ap.add_argument("--action", help="置顶 或 删除")
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

    if args.action != "删除":
        print("不支持的 action，只支持 置顶 / 删除")
        return 1

    # 删除流程（不可逆，执行前已由 --confirm 把关）
    # 入口：悬停任务行 -> 点「...」按钮 -> 菜单里点「删除任务」-> 确认
    popup = start_popup("正在删除任务，完成前请不要操作")
    try:
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
