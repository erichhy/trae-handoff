# -*- coding: utf-8 -*-
"""切换任务时的提示浮窗：置顶、不抢焦点、自动消失。"""

import tkinter as tk

WIDTH, HEIGHT = 380, 120
SECONDS = 12


def main() -> None:
    root = tk.Tk()
    root.title("Trae 正在切换任务")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.96)
    root.configure(bg="#1f2430")

    sw = root.winfo_screenwidth()
    x, y = sw - WIDTH - 24, 24
    root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    title = tk.Label(
        root, text="正在切换任务", bg="#1f2430", fg="#ffffff",
        font=("Microsoft YaHei UI", 12, "bold"), anchor="w",
    )
    title.pack(fill="x", padx=16, pady=(14, 2))

    tip = tk.Label(
        root, text="请不要动鼠标和键盘，约 10 秒后自动完成",
        bg="#1f2430", fg="#c9d1d9", font=("Microsoft YaHei UI", 9),
        anchor="w", justify="left", wraplength=WIDTH - 32,
    )
    tip.pack(fill="x", padx=16)

    countdown = tk.Label(
        root, text="", bg="#1f2430", fg="#7dd3fc",
        font=("Microsoft YaHei UI", 8), anchor="e",
    )
    countdown.pack(fill="x", padx=16, pady=(4, 8))

    remain = {"v": SECONDS}

    def tick() -> None:
        remain["v"] -= 1
        if remain["v"] <= 0:
            root.destroy()
            return
        countdown.config(text=f"{remain['v']} 秒")
        root.after(1000, tick)

    countdown.config(text=f"{SECONDS} 秒")
    root.after(1000, tick)
    root.mainloop()


if __name__ == "__main__":
    main()
