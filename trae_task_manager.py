# -*- coding: utf-8 -*-
"""trae_task_manager.py —— 按标题定位 Trae 任务，执行置顶 / 删除等菜单操作。

做法：截图 + Windows OCR 找任务标题所在行 -> 右键 -> 再 OCR 找菜单项文字 -> 点击。
菜单项文字由 --action 指定（例如 置顶 / 删除），所以界面文案变了只要改参数。

用法：
    python trae_task_manager.py --list
    python trae_task_manager.py --task "Install FlyClaw" --action 置顶 --dry-run
    python trae_task_manager.py --task "Install FlyClaw" --action 删除 --confirm
"""

import argparse
import sys
import time

import pyautogui

from trae_handoff import ocr_words, screenshot

SIDEBAR_MAX_X = 460      # 任务列表所在列的最大 x
LIST_MIN_Y = 430         # 任务区起始 y（避开顶部导航）


def list_tasks():
    words = ocr_words(screenshot())
    rows = {}
    for text, x, y, w, h in words:
        if x < SIDEBAR_MAX_X and y > LIST_MIN_Y and len(text.strip()) > 1:
            key = y // 20
            rows.setdefault(key, []).append((x, text, y))
    result = []
    for _, items in sorted(rows.items()):
        items.sort()
        title = " ".join(t for _, t, _ in items)
        if not any(ch.isalpha() or "\u4e00" <= ch <= "\u9fff" for ch in title):
            continue  # 跳过纯时间戳行
        y = min(y for _, _, y in items)
        result.append((y, title))
    return result


def find_row(title_key: str):
    for y, text in list_tasks():
        if title_key.lower() in text.lower():
            return y
    return None


def find_text(label: str, words, min_y=None):
    for text, x, y, w, h in words:
        if text.strip() == label and (min_y is None or y >= min_y):
            return x + w // 2, y + h // 2
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Trae 任务置顶/删除")
    ap.add_argument("--list", action="store_true", help="打印任务列表")
    ap.add_argument("--task", help="任务标题关键字")
    ap.add_argument("--action", help="要点击的菜单项文字，如 置顶 / 删除")
    ap.add_argument("--dry-run", action="store_true", help="只定位不点击")
    ap.add_argument("--confirm", action="store_true", help="删除类操作必须带上")
    args = ap.parse_args()

    if args.list:
        for y, title in list_tasks():
            print(f"y={y:<5} {title}")
        return 0

    if not args.task or not args.action:
        print("需要 --task 和 --action")
        return 1
    if args.action == "删除" and not args.confirm:
        print("删除操作不可恢复，请加 --confirm")
        return 1

    y = find_row(args.task)
    if y is None:
        print(f"[x] 没找到标题包含「{args.task}」的任务")
        return 2
    print(f"[ok] 找到任务行 y={y}")

    if args.dry_run:
        return 0

    pyautogui.click(150, y, button="right")
    time.sleep(1.0)
    shot = screenshot()
    words = ocr_words(shot)
    hit = find_text(args.action, words, min_y=y - 80)
    if hit is None:
        print(f"[x] 右键后没在菜单里找到「{args.action}」")
        print("     当前识别到的文字：")
        for text, x, yy, w, h in words:
            if yy > y - 120 and yy < y + 400:
                print(f"     ({x},{yy}) {text}")
        pyautogui.press("escape")
        return 3

    pyautogui.click(*hit)
    time.sleep(1.5)
    print(f"[ok] 已点击「{args.action}」，请确认结果")
    return 0


if __name__ == "__main__":
    sys.exit(main())
