# -*- coding: utf-8 -*-
"""切换任务时的提示浮窗：置顶、不抢焦点、自动消失或常驻。"""

import argparse
import ctypes
import tkinter as tk
import winsound

WIDTH, HEIGHT = 440, 170
BG = "#1d4ed8"

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000   # 显示时不抢焦点
WS_EX_TOOLWINDOW = 0x00000080   # 不在任务栏出现


def make_no_activate(root: tk.Tk) -> None:
    """让提示窗显示时不吃焦点，否则后续点击会失效。"""
    root.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    if not hwnd:
        hwnd = root.winfo_id()
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(
        hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


def keep_previous_foreground(root: tk.Tk, prev_hwnd: int) -> None:
    """窗口显示后把前台还给原来的窗口（通常是 Trae），确保后续点击生效。"""
    def restore() -> None:
        if prev_hwnd:
            ctypes.windll.user32.SetForegroundWindow(prev_hwnd)
    root.update_idletasks()
    for delay in (30, 150, 400, 800):
        root.after(delay, restore)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=12, help="显示秒数")
    ap.add_argument("--sticky", action="store_true", help="常驻，直到进程被结束")
    ap.add_argument("--title", default="正在切换任务")
    ap.add_argument("--text", default="请不要动鼠标和键盘，约 10 秒后自动完成")
    args = ap.parse_args()

    prev_hwnd = ctypes.windll.user32.GetForegroundWindow()

    root = tk.Tk()
    root.title(args.title)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.96)
    root.configure(bg=BG)
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    sw = root.winfo_screenwidth()
    root.geometry(f"{WIDTH}x{HEIGHT}+{sw - WIDTH - 24}+24")
    make_no_activate(root)
    keep_previous_foreground(root, prev_hwnd)

    tk.Label(root, text=args.title, bg=BG, fg="#ffffff",
             font=("Microsoft YaHei UI", 16, "bold"), anchor="w").pack(
        fill="x", padx=16, pady=(14, 2))

    tk.Label(root, text=args.text, bg=BG, fg="#c9d1d9",
             font=("Microsoft YaHei UI", 11), anchor="w", justify="left",
             wraplength=WIDTH - 32).pack(fill="x", padx=16)

    countdown = tk.Label(root, text="", bg=BG, fg="#7dd3fc",
                         font=("Microsoft YaHei UI", 9), anchor="e")
    countdown.pack(fill="x", padx=16, pady=(4, 8))

    if args.sticky:
        countdown.config(text="完成后自动关闭")
    else:
        remain = {"v": args.seconds}

        def tick() -> None:
            remain["v"] -= 1
            if remain["v"] <= 0:
                root.destroy()
                return
            countdown.config(text=f"{remain['v']} 秒")
            root.after(1000, tick)

        countdown.config(text=f"{args.seconds} 秒")
        root.after(1000, tick)

    root.mainloop()


if __name__ == "__main__":
    main()
