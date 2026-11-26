#!/usr/bin/env python3
"""对话轮次与日期跨度守卫：用文件计数器保证提醒不会漏。

用法:
    python round_guard.py --bump     # 每收到一条用户消息调用一次，计数 +1
    python round_guard.py --status   # 看当前第几轮、这段对话跨了几天
    python round_guard.py --reset    # 新会话开始时清零（同时重置起始日期）

状态写在 <项目>/.trae/handoff/rounds.json。
  - 轮次按自然日计：跨天归零，避免把几天的旧计数算进来
  - 起始日期跨天保留：这是"这段对话聊了多久"的唯一可靠记录
  - 3 天提醒收尾，7 天提示立即换任务
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
SPAN_WARN = 3      # 跨满 3 天提醒收尾
SPAN_FORCE = 7     # 跨满 7 天提示立即换任务


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
    state = {"start_date": today, "date": today, "round": 0,
             "warned25": False, "warned30": False,
             "warned_span3": False, "warned_span7": False}
    path = state_path(project_dir)
    if not os.path.exists(path):
        return state
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, json.JSONDecodeError):
        return state
    # 起始日期与跨天提醒标记跨天保留：它们描述的是整段对话，不是今天
    if saved.get("start_date") or saved.get("date"):
        state["start_date"] = saved.get("start_date") or saved["date"]
        state["warned_span3"] = bool(saved.get("warned_span3"))
        state["warned_span7"] = bool(saved.get("warned_span7"))
    # 轮次只在同一天内累加
    if saved.get("date") == today:
        for k in ("round", "warned25", "warned30"):
            if k in saved:
                state[k] = saved[k]
    return state


def span_days(state: dict) -> int:
    """这段对话从起始日期到今天跨了几天（起始当天为 0）。"""
    try:
        start = dt.date.fromisoformat(state["start_date"])
    except (TypeError, ValueError):
        return 0
    return (dt.date.today() - start).days


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
        today = dt.date.today().isoformat()
        state.update(start_date=today, date=today, round=0,
                     warned25=False, warned30=False,
                     warned_span3=False, warned_span7=False)
        save(project_dir, state)
        print(f"轮次已清零（{today}，起始日期同步重置）")
        return 0

    span = span_days(state)
    if args.status:
        print(f"第 {state['round']} 轮（{state['date']}）")
        print(f"对话第 {span} 天（起始 {state['start_date']}）")
        card = latest_card(project_dir)
        if card:
            print("最新任务卡：" + os.path.relpath(card, project_dir))
        return 0

    state["round"] += 1
    n = state["round"]
    lines = [f"第 {n} 轮", f"对话第 {span} 天（起始 {state['start_date']}）"]

    if n >= WARN_30 and not state["warned30"]:
        state["warned30"] = True
        lines.append(f"已 {WARN_30} 轮：该写交接卡并换任务了（先做完手头关键操作）")
        toast("对话已到 30 轮", "写交接卡，然后回复「切」换新任务")
    elif n >= WARN_25 and not state["warned25"]:
        state["warned25"] = True
        lines.append(f"已 {WARN_25} 轮：到 30 轮就该换任务，提前收尾")
        toast("对话已到 25 轮", "还有 5 轮，准备写交接卡")

    if span >= SPAN_FORCE and not state["warned_span7"]:
        state["warned_span7"] = True
        lines.append(f"⚠ 已跨 {span} 天：收尾后立即换任务，别再长下去")
        toast(f"对话已跨 {span} 天",
              "立即写交接卡换任务（先做完手头关键操作）")
    elif span >= SPAN_WARN and not state["warned_span3"]:
        state["warned_span3"] = True
        lines.append(f"⚠ 已跨 {span} 天：建议写交接卡换任务，回复「切」立即执行")
        toast(f"对话已跨 {span} 天",
              "建议写交接卡换任务，回复「切」立即执行")

    save(project_dir, state)

    card = latest_card(project_dir)
    if card:
        lines.append("任务卡：" + os.path.basename(card))
    print("；".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
