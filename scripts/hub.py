#!/usr/bin/env python3
"""ai-hub 管理スクリプト（標準ライブラリのみ）

使い方:
  python3 scripts/hub.py sync [--days 7] [--json] [--fail-on-stale]
      全案件を巡回して INDEX.md を更新し、動きのない案件を列挙する
  python3 scripts/hub.py stale [--days 7] [--json]
      INDEX.md は更新せず、動きのない案件だけを列挙する
  python3 scripts/hub.py new <name> [--summary "概要"] [--repo URL]
      案件フォルダを作成し、INDEX.md を更新する
  python3 scripts/hub.py ingest (--env ISSUE_BODY | --file PATH)
      ChatGPT 等が出力した終了時の要約（Issue 本文）を logs/ と STATUS.md に反映する
      （GitHub Actions から呼ばれる。ローカルでの確認にも使える）

終了コード: 0=正常 / 1=--fail-on-stale 指定時に停滞案件あり / 2=エラー
スケジューラからは `sync --json --fail-on-stale` で呼ぶと扱いやすい。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
TEMPLATES = ROOT / "_templates"
INDEX = ROOT / "INDEX.md"

try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except Exception:  # tzdata が無い環境では端末のローカル時刻を使う
    JST = None


def now():
    return datetime.now(JST) if JST else datetime.now()


def today_jst():
    return now().date()


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
    today = today_jst()
    projects = load_all()
    INDEX.write_text(render_index(projects, today), encoding="utf-8")
    write_generated(projects)
    stale = find_stale(projects, args.days, today)
    if not args.json:
        print(f"INDEX.md・各案件の CONTEXT.md・Issue フォームを更新しました（{len(projects)}案件）")
    report_stale(stale, args.days, args.json)
    return 1 if (args.fail_on_stale and stale) else 0


def cmd_stale(args):
    stale = find_stale(load_all(), args.days, today_jst())
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
            date=today_jst().isoformat(),
        ),
        encoding="utf-8",
    )
    print(f"作成しました: projects/{name}/")
    return cmd_sync(argparse.Namespace(days=7, json=False, fail_on_stale=False))


# ---------------------------------------------------------------- CONTEXT.md
def render_context(d, p):
    """ChatGPT のプロジェクト等に貼る/添付する、作業開始用のまとめ"""
    meta_lines = [f"- 状態: {p['state']}", f"- 概要: {p['summary'] or '（未記入）'}"]
    if p["repo"]:
        meta_lines.append(f"- リポジトリ: {p['repo']}")
    meta_lines.append(f"- STATUS 更新日: {fmt(p['updated'])}")
    _, body = parse_frontmatter((d / "STATUS.md").read_text(encoding="utf-8"))
    body = re.sub(r"<!--.*?-->\s*", "", body, flags=re.S).strip()
    parts = [
        f"# 【{p['name']}】作業開始用コンテキスト",
        "",
        "<!-- 自動生成: `python3 scripts/hub.py sync` で更新。手で編集しない -->",
        f"生成日: {today_jst().isoformat()}",
        "",
        "\n".join(meta_lines),
        "",
        body,
        "",
        "## 直近のログ",
    ]
    logs = sorted(
        (f for f in (d / "logs").glob("*.md") if DATE_RE.match(f.name)), reverse=True
    )[:3]
    if not logs:
        parts.append("（ログなし）")
    for f in logs:
        text = f.read_text(encoding="utf-8").strip()
        if len(text) > 3000:
            text = text[:3000] + "\n…（以下省略）"
        parts += ["", text.replace("\n# ", "\n## ").replace("# " + f.stem, f.stem, 1)]
    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------- Issue フォーム
ISSUE_FORM_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"


def render_issue_form(names):
    opts = "\n".join(f"        - {n}" for n in names) or "        - （案件なし）"
    return f"""# 自動生成: `python3 scripts/hub.py sync` で更新。手で編集しない
name: 作業終了の記録（wrapup）
description: ChatGPT 等が出力した終了時の要約を貼ると、logs/・STATUS.md・INDEX.md に自動反映される
title: "[wrapup] "
body:
  - type: dropdown
    id: project
    attributes:
      label: 案件
      options:
{opts}
    validations:
      required: true
  - type: textarea
    id: summary
    attributes:
      label: 要約
      description: prompts/wrapup.md で出力させた内容をそのまま貼る（APIキー・個人情報は含めない）
    validations:
      required: true
"""


def write_generated(projects):
    """案件ごとの CONTEXT.md と Issue フォームを再生成する"""
    for p in projects:
        d = PROJECTS / p["id"]
        if (d / "STATUS.md").exists():
            (d / "CONTEXT.md").write_text(render_context(d, p), encoding="utf-8")
    ISSUE_FORM_DIR.mkdir(parents=True, exist_ok=True)
    (ISSUE_FORM_DIR / "wrapup.yml").write_text(
        render_issue_form(sorted(p["id"] for p in projects)), encoding="utf-8"
    )


# ---------------------------------------------------------------- ingest
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9\-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S{6,})"
)
SECTION_KEYS = {"やったこと": "done", "決めたこと": "decided", "次回へ": "next", "現状": "current"}
KV_KEYS = {"使ったAI": "ai", "概要": "summary", "状態": "state"}
VALID_STATES = set(STATE_ORDER)


class IngestError(Exception):
    pass


def split_issue_form(body):
    """Issue フォームの '### ラベル' 区切りを辞書にする"""
    fields, key, buf = {}, None, []
    for line in body.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if key is not None:
                fields[key] = "\n".join(buf).strip()
            key, buf = m.group(1), []
        else:
            buf.append(line)
    if key is not None:
        fields[key] = "\n".join(buf).strip()
    return fields


def parse_summary(text):
    """ChatGPT 出力（prompts/wrapup.md の形式）を読む。区切りは ASCII/全角コロン・見出し・太字に寛容"""
    kv, sections, cur = {}, {k: [] for k in SECTION_KEYS.values()}, None
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if line.lstrip().startswith("```"):  # ChatGPT が付けるコードブロックの囲み
            continue
        head = re.sub(r"^[#\s>*\-]*|[*\s]*$", "", line)
        head = re.sub(r"[:：]\s*$", "", head)
        if head in SECTION_KEYS and not re.match(r"^\s*[-*]\s", line):
            cur = SECTION_KEYS[head]
            continue
        m = re.match(r"^\s*[*]*(使ったAI|概要|状態)[*]*\s*[:：]\s*(.*)$", line)
        if m:
            kv[KV_KEYS[m.group(1)]] = re.sub(r"\*+", "", m.group(2)).strip()
            cur = None
            continue
        m = re.match(r"^\s*[*]*(やったこと|決めたこと|次回へ|現状)[*]*\s*[:：]\s*(.+)$", line)
        if m:  # 「やったこと: xxx」と同じ行に書かれた場合
            cur = SECTION_KEYS[m.group(1)]
            sections[cur].append(m.group(2).strip())
            continue
        if cur and line.strip():
            sections[cur].append(line)
    return kv, sections


def bullets(lines):
    out = []
    for l in lines:
        s = re.sub(r"^\s*(?:[-*・]|\d+[.)])\s*(?:\[[ xX]\]\s*)?", "", l).strip()
        if s and s not in ("-", "…", "...", "なし"):
            out.append(s)
    return out


def replace_section(body, title, new_text):
    """'## title' 見出し配下を new_text に置き換える（無ければ末尾に追加）"""
    pat = re.compile(rf"(^##\s*{re.escape(title)}[^\n]*\n)(.*?)(?=^##\s|\Z)", re.S | re.M)
    m = pat.search(body)
    if m:
        return body[: m.start(2)] + new_text.rstrip() + "\n\n" + body[m.end(2):]
    return body.rstrip() + f"\n\n## {title}\n{new_text.rstrip()}\n"


def add_decisions(body, rows):
    if not rows:
        return body
    pat = re.compile(r"(^##\s*決定事項[^\n]*\n)(.*?)(?=^##\s|\Z)", re.S | re.M)
    m = pat.search(body)
    header = "| 日付 | 決定 | 理由 |\n|---|---|---|\n"
    if not m:
        return body.rstrip() + "\n\n## 決定事項\n" + header + "\n".join(rows) + "\n"
    sect = m.group(2).rstrip()
    if "|---" not in sect:
        sect = (sect + "\n" if sect else "") + header.rstrip()
    return body[: m.start(2)] + sect + "\n" + "\n".join(rows) + "\n\n" + body[m.end(2):]


def set_frontmatter(text, **kv):
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*(?:\n|$))", text, re.S)
    if not m:
        raise IngestError("STATUS.md の frontmatter が見つかりません")
    lines = m.group(2).split("\n")
    for k, v in kv.items():
        for i, l in enumerate(lines):
            if re.match(rf"^{k}\s*:", l):
                lines[i] = f"{k}: {v}"
                break
        else:
            lines.append(f"{k}: {v}")
    return m.group(1) + "\n".join(lines) + m.group(3) + text[m.end():]


def esc_cell(s):
    return s.replace("|", "\\|").replace("\n", " ").strip()


def ingest_text(body):
    fields = split_issue_form(body)
    text = fields.get("要約", body)
    proj = fields.get("案件", "").strip()
    if not proj:
        m = re.search(r"^\s*案件\s*[:：]\s*(\S+)", text, re.M)
        proj = m.group(1) if m else ""
    if not NAME_RE.match(proj) or not (PROJECTS / proj / "STATUS.md").exists():
        raise IngestError(f"案件「{proj or '未指定'}」が見つかりません")
    if SECRET_RE.search(text):
        raise IngestError("APIキー・パスワード・トークンらしき文字列が含まれているため、記録を中止しました。削除して再投稿してください")

    kv, sec = parse_summary(text)
    done, decided, nxt = bullets(sec["done"]), bullets(sec["decided"]), bullets(sec["next"])
    current = "\n".join(sec["current"]).strip()
    missing = [n for n, v in (("やったこと", done), ("次回へ", nxt)) if not v]
    if missing:
        raise IngestError("形式が読み取れません。必須項目がありません: " + "、".join(missing)
                          + "（prompts/wrapup.md の形式で出力させてください）")
    state = kv.get("state", "").lower()
    if state and state not in VALID_STATES:
        raise IngestError(f"状態は {'/'.join(sorted(VALID_STATES))} のいずれかにしてください: {state}")

    n, today = now(), today_jst().isoformat()
    ai = kv.get("ai") or "ChatGPT"
    d = PROJECTS / proj

    # --- logs
    logf = d / "logs" / f"{today}.md"
    block = [f"### {n:%H:%M} {ai}（Issue経由）", "**やったこと**"]
    block += [f"- {x}" for x in done]
    if decided:
        block += ["", "**決めたこと**"] + [f"- {x}" for x in decided]
    block += ["", "**次回へ**"] + [f"- {x}" for x in nxt]
    prev = logf.read_text(encoding="utf-8").rstrip() + "\n\n" if logf.exists() else f"# {today}\n\n"
    logf.write_text(prev + "\n".join(block) + "\n", encoding="utf-8")

    # --- STATUS
    st = (d / "STATUS.md").read_text(encoding="utf-8")
    fm = {"updated": today}
    if kv.get("summary"):
        fm["summary"] = kv["summary"].replace("\n", " ")
    if state:
        fm["state"] = state
    st = set_frontmatter(st, **fm)
    if current:
        st = replace_section(st, "現状", current)
    st = replace_section(st, "次の作業", "\n".join(f"- [ ] {x}" for x in nxt))
    rows = []
    for x in decided:
        what, _, why = x.partition("|") if "|" in x else x.partition("（")
        rows.append(f"| {today} | {esc_cell(what)} | {esc_cell(why.rstrip('）'))} |")
    st = add_decisions(st, rows)
    (d / "STATUS.md").write_text(st, encoding="utf-8")
    return proj, today, ai


def cmd_ingest(args):
    if args.env:
        body = os.environ.get(args.env, "")
    else:
        body = Path(args.file).read_text(encoding="utf-8")
    try:
        proj, today, ai = ingest_text(body)
    except IngestError as e:
        print(f"❌ 記録できませんでした: {e}")
        return 2
    cmd_sync(argparse.Namespace(days=7, json=False, fail_on_stale=False))
    print(f"✅ 案件「{proj}」に {today} の記録を追加しました（{ai}）。"
          f"STATUS.md・INDEX.md・CONTEXT.md を更新済みです。")
    return 0


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

    p = sub.add_parser("ingest", help="終了時の要約（Issue 本文）を反映")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--env", help="本文が入っている環境変数名")
    g.add_argument("--file", help="本文のファイル")
    p.set_defaults(func=cmd_ingest)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
