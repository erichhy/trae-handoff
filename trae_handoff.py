# -*- coding: utf-8 -*-
"""trae_handoff.py —— 在 Trae CN 里自动新建任务并发送承接语。

流程：截图 -> Windows OCR 定位「+ 新任务」与输入框 -> 点击 -> 粘贴 -> 回车 -> 校验。
关键点：中文输入法会吞掉模拟按键，所以文字一律走剪贴板粘贴，不用键盘逐字输入。

用法：
    python trae_handoff.py --file .trae/handoff/20261123-1120-signtalk-deploy.md
    python trae_handoff.py --prompt "读 .trae/handoff/xxx.md 继续"
    python trae_handoff.py --file xxx.md --dry-run    # 只定位，不点击
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import tempfile
import time

import pyautogui

HERE = os.path.dirname(os.path.abspath(__file__))
OCR_PS1 = os.path.join(HERE, "ocr.ps1")
POPUP_PY = os.path.join(HERE, "popup.py")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


# ---------- 剪贴板 ----------
def set_clipboard(text: str) -> None:
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    data = text.encode("utf-16-le") + b"\x00\x00"

    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [wt.UINT, ctypes.c_void_p]

    if not user32.OpenClipboard(None):
        raise RuntimeError("打不开剪贴板")
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise RuntimeError("GlobalAlloc 失败")
        ptr = kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("SetClipboardData 失败")
    finally:
        user32.CloseClipboard()


# ---------- 截图 + OCR ----------
def screenshot() -> str:
    # 用唯一文件名，避免上一次的截图文件被占用/损坏导致保存失败
    path = os.path.join(tempfile.gettempdir(), f"trae_handoff_{int(time.time() * 1000)}.png")
    pyautogui.screenshot().save(path)
    return path


def ocr_words(image_path: str):
    """返回 [(text, x, y, w, h), ...]，坐标为物理像素。"""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", OCR_PS1, "-ImagePath", image_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    words = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        text, x, y, w, h = parts
        try:
            words.append((text, int(x), int(y), int(w), int(h)))
        except ValueError:
            continue
    return words


def find_new_task_button(words):
    """在左侧栏顶部找「+ 新任务」，返回点击点。"""
    for i, (text, x, y, w, h) in enumerate(words):
        if text == "新" and y < 300 and x < 400:
            for text2, x2, y2, _, _ in words[i:i + 4]:
                if text2 == "务" and abs(y2 - y) < 12:
                    return x + w // 2, y + h // 2
    return None


def find_input_points(words):
    """推算输入区点击点：优先用模型选择器定位，其次用「@ 添加上下文」提示。"""
    pts = []
    for text, x, y, w, h in words:
        if (text == "Agent" or text.lower().startswith("deepseek")) and x > 600 and y > 1000:
            pts += [(x + 200, y - 120), (x + 200, y - 160)]
            break
    for text, x, y, w, h in words:
        if text == "@" and y > 600:
            pts += [(x + 400, y - 15), (x + 400, y - 60)]
            break
    pts.append((1100, 1150))
    unique = []
    for p in pts:
        if p not in unique:
            unique.append(p)
    return unique


def prompt_visible(words, prompt: str) -> bool:
    """判断 prompt 是否已出现在屏幕上；OCR 会吞标点，所以只比对字母数字。"""
    import re
    core = re.sub(r"[^A-Za-z0-9]", "", prompt)
    if len(core) < 4:
        return any(prompt[:4] in w[0] for w in words)
    probe = core[:6].lower()
    joined = "".join(re.sub(r"[^A-Za-z0-9]", "", w[0]).lower() for w in words)
    return probe in joined


def show_popup() -> None:
    """右上角弹一个不阻塞的提示窗，提醒用户别手动操作。"""
    if not os.path.exists(POPUP_PY):
        return
    try:
        subprocess.Popen(
            [sys.executable, POPUP_PY],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(0.6)
    except OSError as exc:
        print(f"[!] 提示窗没弹出来: {exc}")


# ---------- 主流程 ----------
def run(prompt: str, dry_run: bool = False, no_send: bool = False,
        no_popup: bool = False) -> int:
    if not no_popup:
        show_popup()

    shot = screenshot()
    words = ocr_words(shot)

    btn = find_new_task_button(words)
    if btn is None:
        print("[x] 没找到「+ 新任务」按钮，请确认 Trae 窗口在最前且侧边栏展开")
        return 2
    print(f"[ok] 新任务按钮位于 ({btn[0]}, {btn[1]})")

    if dry_run:
        print(f"[dry-run] 输入区候选点: {find_input_points(words)}")
        return 0

    pyautogui.click(*btn)
    time.sleep(2.5)

    shot = screenshot()
    words = ocr_words(shot)
    points = find_input_points(words)
    if not points:
        print("[x] 没找到输入框提示行（@ 添加上下文）")
        return 3

    pasted = False
    for pt in points:
        pyautogui.click(*pt)
        time.sleep(0.6)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("delete")
        time.sleep(0.4)

        set_clipboard(prompt)          # 粘贴，绕开中文输入法
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1.2)

        shot = screenshot()
        if prompt_visible(ocr_words(shot), prompt):
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

    shot = screenshot()
    word_list = ocr_words(shot)
    if prompt_visible(word_list, prompt):
        print("[ok] 已发送，交接卡已带入新任务")
        return 0
    print("[!] 发送结果未能确认，请人工看一眼新任务")
    return 4


def main() -> int:
    ap = argparse.ArgumentParser(description="Trae CN 自动新建任务并发送承接语")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt", help="直接给出发送内容")
    g.add_argument("--file", help="交接卡路径，自动拼成「读 <file> 继续」")
    ap.add_argument("--dry-run", action="store_true", help="只定位不点击")
    ap.add_argument("--no-send", action="store_true", help="建任务并粘贴，但不回车")
    ap.add_argument("--no-popup", action="store_true", help="不弹「请勿手动操作」提示窗")
    args = ap.parse_args()

    prompt = args.prompt or f"读 {args.file} 继续"
    print(f"prompt: {prompt}")
    code = run(prompt, args.dry_run, args.no_send, args.no_popup)
    if code == 0 and not args.dry_run:
        # 新任务已发出，重置轮次计数器
        guard = os.path.join(os.path.dirname(os.path.abspath(__file__)), "round_guard.py")
        if os.path.exists(guard):
            try:
                subprocess.run([sys.executable, guard, "--reset", "--dir", os.getcwd()],
                               capture_output=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                pass
    return code


if __name__ == "__main__":
    sys.exit(main())
