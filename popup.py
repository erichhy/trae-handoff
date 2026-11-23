# -*- coding: utf-8 -*-
"""切换任务时的提示浮窗：置顶、不抢焦点、自动消失或常驻。"""

import argparse
import tkinter as tk
import winsound

WIDTH, HEIGHT = 440, 170
BG = "#1d4ed8"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=12, help="显示秒数")
    ap.add_argument("--sticky", action="store_true", help="常驻，直到进程被结束")
    ap.add_argument("--title", default="正在切换任务")
    ap.add_argument("--text", default="请不要动鼠标和键盘，约 10 秒后自动完成")
    args = ap.parse_args()

    root = tk.Tk()
    root.title(args.title)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.96)
    root.configure(bg=BG)
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    sw = root.winfo_screenwidth()
    root.geometry(f"{WIDTH}x{HEIGHT}+{sw - WIDTH - 24}+24")

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
