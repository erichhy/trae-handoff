#!/usr/bin/env python3
"""对话轮次守卫：用文件计数器保证 25/30 轮提醒不会漏。

用法:
    python round_guard.py --bump     # 每收到一条用户消息调用一次，计数 +1
    python round_guard.py --status   # 看当前第几轮
    python round_guard.py --reset    # 新会话开始时清零

状态写在 <项目>/.trae/handoff/rounds.json，跨天自动归零。
--dir 指向项目根目录，默认当前目录。
提醒方式：25 轮弹系统通知，30 轮再弹一次并提示换任务。
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOAST = os.path.join(HERE, "toast.ps1")
WARN_25 = 25
WARN_30 = 30


def state_path(project_dir: str) -> str:
    return os.path.join(project_dir, ".trae", "handoff", "rounds.json")


def latest_card(project_dir: str) -> str:
    folder = os.path.join(project_dir, ".trae", "handoff")
    if not os.path.isdir(folder):
        return ""
    cards = [os.path.join(folder, n) for n in os.listdir(folder)
             if n.endswith(".md") and n.upper() != "TEMPLATE.MD"]
    if not cards:
        return ""
    return max(cards, key=os.path.getmtime)


def toast(title: str, text: str) -> None:
    if os.environ.get("ROUND_GUARD_NO_TOAST") or not os.path.exists(TOAST):
        return
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", TOAST,
             "-Title", title, "-Text", text],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        pass


def load(project_dir: str) -> dict:
    today = dt.date.today().isoformat()
    state = {"date": today, "round": 0, "warned25": False, "warned30": False}
    path = state_path(project_dir)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            if saved.get("date") == today:
                state.update(saved)
        except (OSError, json.JSONDecodeError):
            pass
    return state


def save(project_dir: str, state: dict) -> None:
    path = state_path(project_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser(description="对话轮次守卫")
    ap.add_argument("--dir", default=os.getcwd(), help="项目根目录（默认当前目录）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--bump", action="store_true", help="计数 +1（每条用户消息调用一次）")
    g.add_argument("--status", action="store_true", help="只显示当前轮次")
    g.add_argument("--reset", action="store_true", help="清零（新会话开始时用）")
    args = ap.parse_args()

    project_dir = os.path.abspath(args.dir)
    state = load(project_dir)

    if args.reset:
        state["round"] = 0
        state["warned25"] = False
        state["warned30"] = False
        save(project_dir, state)
        print(f"轮次已清零（{state['date']}）")
        return 0

    if args.status:
        print(f"第 {state['round']} 轮（{state['date']}）")
        card = latest_card(project_dir)
        if card:
            print("最新任务卡：" + os.path.relpath(card, project_dir))
        return 0

    state["round"] += 1
    n = state["round"]
    lines = [f"第 {n} 轮"]

    if n >= WARN_30 and not state["warned30"]:
        state["warned30"] = True
        lines.append(f"已 {WARN_30} 轮：该写交接卡并换任务了（先做完手头关键操作）")
        toast("对话已到 30 轮", "写交接卡，然后回复「切」换新任务")
    elif n >= WARN_25 and not state["warned25"]:
        state["warned25"] = True
        lines.append(f"已 {WARN_25} 轮：到 30 轮就该换任务，提前收尾")
        toast("对话已到 25 轮", "还有 5 轮，准备写交接卡")

    save(project_dir, state)

    card = latest_card(project_dir)
    if card:
        lines.append("任务卡：" + os.path.basename(card))
    print("；".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
