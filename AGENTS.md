# AGENTS.md（Codex など、リポジトリを読めるAI向け）

運用ルールの本体は [`CLAUDE.md`](CLAUDE.md)。このリポジトリで作業する場合は、必ず先に読んで従うこと。

要点:
- 開始時: `INDEX.md` → 対象案件の `STATUS.md` → `logs/` 直近を読む。
- 終了時: `logs/YYYY-MM-DD.md` に追記 → `STATUS.md` 更新 → `python3 scripts/hub.py sync`。
- APIキー・個人情報・`raw/` はコミットしない。

リポジトリを読めない AI（ChatGPT / Gemini の Web チャットなど）は [`prompts/`](prompts/) のコピペ用プロンプトを使う。
