#!/usr/bin/env python3
"""ai-hub 管理スクリプト（標準ライブラリのみ）

使い方:
  python3 scripts/hub.py sync [--days 7] [--json] [--fail-on-stale]
      全案件を巡回して INDEX.md を更新し、動きのない案件を列挙する
  python3 scripts/hub.py stale [--days 7] [--json]
      INDEX.md は更新せず、動きのない案件だけを列挙する
  python3 scripts/hub.py new <name> [--summary "概要"] [--repo URL]
      案件フォルダを作成し、INDEX.md を更新する

終了コード: 0=正常 / 1=--fail-on-stale 指定時に停滞案件あり / 2=エラー
スケジューラからは `sync --json --fail-on-stale` で呼ぶと扱いやすい。
"""
import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
TEMPLATES = ROOT / "_templates"
INDEX = ROOT / "INDEX.md"

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
# 停滞判定から除外する状態
INACTIVE_STATES = {"done", "paused"}
STATE_ORDER = {"active": 0, "waiting": 1, "paused": 2, "done": 3}


def parse_frontmatter(text):
    """先頭の --- ... --- を key: value の辞書として読む（単純な1行形式のみ）"""
    meta = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def first_next_action(body):
    """「## 次の作業」直下の最初の項目を返す"""
    m = re.search(r"^##\s*次の作業\s*\n(.*?)(?=^##\s|\Z)", body, re.S | re.M)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        s = re.sub(r"^[-*]\s*(\[[ xX]\]\s*)?", "", line.strip())
        if s and not s.startswith("<!--"):
            return s
    return ""


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def load_project(d):
    status = d / "STATUS.md"
    meta, body = ({}, "")
    if status.exists():
        meta, body = parse_frontmatter(status.read_text(encoding="utf-8"))
    log_dates = []
    logs = d / "logs"
    if logs.is_dir():
        for f in logs.iterdir():
            m = DATE_RE.match(f.name)
            if m and parse_date(m.group(1)):
                log_dates.append(parse_date(m.group(1)))
    updated = parse_date(meta.get("updated"))
    last_log = max(log_dates) if log_dates else None
    candidates = [x for x in (updated, last_log) if x]
    last_activity = max(candidates) if candidates else None
    return {
        "id": d.name,
        "name": meta.get("name") or d.name,
        "summary": meta.get("summary", ""),
        "state": meta.get("state", "active"),
        "repo": meta.get("repo", ""),
        "updated": updated,
        "last_log": last_log,
        "last_activity": last_activity,
        "next": first_next_action(body),
        "missing_status": not status.exists(),
    }


def load_all():
    if not PROJECTS.is_dir():
        return []
    projects = [load_project(d) for d in sorted(PROJECTS.iterdir()) if d.is_dir()]
    projects.sort(key=lambda p: (STATE_ORDER.get(p["state"], 9), p["id"]))
    return projects


def find_stale(projects, days, today):
    stale = []
    for p in projects:
        if p["state"] in INACTIVE_STATES:
            continue
        la = p["last_activity"]
        idle = (today - la).days if la else None
        if idle is None or idle >= days:
            stale.append({**p, "idle_days": idle})
    return stale


def fmt(d):
    return d.isoformat() if d else "-"


def render_index(projects, today):
    lines = [
        "# INDEX",
        "",
        "<!-- 自動生成: `python3 scripts/hub.py sync` で更新。手で編集しない -->",
        f"最終更新: {today.isoformat()}　／　案件数: {len(projects)}",
        "",
    ]
    for p in projects:
        lines.append(f"## {p['name']}（{p['state']}）")
        lines.append(f"- 概要: {p['summary'] or '（未記入）'}")
        lines.append(f"- 次の作業: {p['next'] or '（未記入）'}")
        lines.append(
            f"- 最終動き: {fmt(p['last_activity'])}"
            f"（STATUS {fmt(p['updated'])} / 最新ログ {fmt(p['last_log'])}）"
            f" → [`projects/{p['id']}/STATUS.md`](projects/{p['id']}/STATUS.md)"
        )
        lines.append("")
    return "\n".join(lines)


def report_stale(stale, days, as_json):
    if as_json:
        out = [
            {
                "id": p["id"],
                "state": p["state"],
                "last_activity": fmt(p["last_activity"]),
                "idle_days": p["idle_days"],
            }
            for p in stale
        ]
        print(json.dumps({"threshold_days": days, "stale": out}, ensure_ascii=False))
        return
    if not stale:
        print(f"停滞案件なし（{days}日以上動きのない案件はありません）")
        return
    print(f"{days}日以上動きのない案件: {len(stale)}件")
    for p in stale:
        idle = f"{p['idle_days']}日" if p["idle_days"] is not None else "不明"
        print(f"  - {p['id']} [{p['state']}] 最終動き {fmt(p['last_activity'])}（{idle}）")


def cmd_sync(args):
    today = date.today()
    projects = load_all()
    INDEX.write_text(render_index(projects, today), encoding="utf-8")
    stale = find_stale(projects, args.days, today)
    if not args.json:
        print(f"INDEX.md を更新しました（{len(projects)}案件）")
    report_stale(stale, args.days, args.json)
    return 1 if (args.fail_on_stale and stale) else 0


def cmd_stale(args):
    stale = find_stale(load_all(), args.days, date.today())
    report_stale(stale, args.days, args.json)
    return 0


def render_template(path, **kw):
    text = path.read_text(encoding="utf-8")
    for k, v in kw.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def cmd_new(args):
    name = args.name
    if not NAME_RE.match(name):
        print("案件名は英小文字・数字・-・_ のみ（先頭は英数字）で指定してください", file=sys.stderr)
        return 2
    d = PROJECTS / name
    if d.exists():
        print(f"既に存在します: {d.relative_to(ROOT)}", file=sys.stderr)
        return 2
    (d / "logs").mkdir(parents=True)
    (d / "raw").mkdir()
    (d / "logs" / ".gitkeep").touch()
    (d / "raw" / ".gitkeep").touch()
    (d / "STATUS.md").write_text(
        render_template(
            TEMPLATES / "STATUS.md",
            name=name,
            summary=args.summary or "（未記入）",
            repo=args.repo or "",
            date=date.today().isoformat(),
        ),
        encoding="utf-8",
    )
    print(f"作成しました: projects/{name}/")
    return cmd_sync(argparse.Namespace(days=7, json=False, fail_on_stale=False))


def main():
    ap = argparse.ArgumentParser(description="ai-hub 管理スクリプト")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sync", help="INDEX.md 更新 + 停滞案件の列挙")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    p.add_argument("--fail-on-stale", action="store_true")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("stale", help="停滞案件の列挙のみ")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_stale)

    p = sub.add_parser("new", help="案件を追加")
    p.add_argument("name")
    p.add_argument("--summary", default="")
    p.add_argument("--repo", default="")
    p.set_defaults(func=cmd_new)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
