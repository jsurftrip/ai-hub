# ai-hub 運用ルール

複数のAIツール・複数の端末・複数の案件の「現在地と経緯」を一元管理するリポジトリ。
どのAIがどの端末で作業しても、ここを読めば続きから始められる状態を保つ。

## 構成
```
INDEX.md                 全案件の一覧と現状（自動生成。手で編集しない）
projects/<案件>/
  STATUS.md              現状・次の作業・決定事項（先頭の frontmatter が INDEX に転記される）
  logs/YYYY-MM-DD.md     日付ごとの作業要約
  raw/                   チャット生ログ（git 対象外・端末ローカル）
_templates/              STATUS.md / log.md のひな形
scripts/hub.py           INDEX 更新・停滞検出・案件追加
```

## 作業開始時（必須）
1. `INDEX.md` を読み、全体と今日の対象案件を把握する。
2. 対象案件の `projects/<案件>/STATUS.md` を読む。
3. 同案件の `logs/` の直近 1〜3 件を読む。
4. 案件が不明なら、推測せずユーザーに確認する。
5. 読んだ内容を踏まえ、現在地を1〜2行で復唱してから作業に入る。

## 作業終了時（必須）
作業が一区切りついたら、ユーザーに言われなくても次を行う（`/wrapup` でも可）。
1. `logs/YYYY-MM-DD.md` に追記する（なければ `_templates/log.md` から作る）。
   同日に複数回作業したら、見出し `### HH:MM AI名（端末）` で追記する。上書きしない。
2. `STATUS.md` を更新する。
   - 「現状」を最新にする
   - 「次の作業」を、次に着手する順に整える（最初の1項目が INDEX に出る）
   - 決定事項があれば表に追加する
   - frontmatter の `summary`（1行）・`state`・`updated`（今日の日付）を更新する
3. `python3 scripts/hub.py sync` を実行して INDEX.md を更新する。
4. 変更をコミットし、push する（push 前にユーザーへ確認する）。

## 書き方
- 要約は簡潔に。ログは1回あたり数行〜十数行。会話の全文は書かない。
- 「なぜそう決めたか」を決定事項に残す。経緯が追えなくなるのが最大の損失。
- 日付は `YYYY-MM-DD`。日本語で書く。
- 他の案件の STATUS.md を勝手に書き換えない。

## 絶対に書かない・コミットしない
- APIキー、トークン、パスワード、秘密鍵、`.env` の中身
- 個人情報（氏名・メール・電話・住所・顧客データ）。必要なら「顧客A」など匿名化する
- `raw/` 配下のファイル（.gitignore 済みだが、`git add -f` もしない）
- 秘密情報らしきものを見つけたら、書く前に止めてユーザーに知らせる

## コマンド
- `/wrapup [案件名] [補足]` … 作業終了時の記録（ログ追記・STATUS更新・INDEX更新）
- `/new-project <案件名> [概要]` … 案件を追加
- `python3 scripts/hub.py sync [--days 7] [--json] [--fail-on-stale]` … INDEX更新 + 停滞案件の列挙
- `python3 scripts/hub.py stale` … 停滞案件の列挙のみ
- Claude Code 以外のAI向け: `AGENTS.md` と `prompts/`

## 運用の使い分け
- **Claude Code（メイン）**: 開始時は CLAUDE.md のルールで自動的に読む。終了時は `/wrapup`。
- **ChatGPT（プロジェクト機能）**: 開始時は `projects/<案件>/CONTEXT.md`（自動生成）を貼る。
  終了時は「終了」と言って出力させた要約を、GitHub の Issue フォーム「作業終了の記録」に貼る
  → `.github/workflows/ingest-wrapup.yml` が logs/・STATUS.md・INDEX.md に反映する。
  指示文は `prompts/chatgpt-project-instructions.md`。
- ChatGPT 側の要約を Claude Code で記録したい場合は `/wrapup <案件> （要約を貼る）` でも可。
- `CONTEXT.md` と `.github/ISSUE_TEMPLATE/wrapup.yml` は自動生成物。`hub.py sync` で更新される（手で編集しない）。
- 案件を追加したら必ず `hub.py sync`（`/new-project` は自動で実行する）。Issue フォームの案件一覧が更新される。
