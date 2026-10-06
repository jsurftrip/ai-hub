---
name: pipes
summary: PIPES.jp 自動化: TDnetの第三者割当情報を取得→PIPES判定→記事生成。ダッシュボードとPDFファクトチェックまで実装済み、WP自動投稿は停止中
state: active
updated: 2026-03-17
repo: https://github.com/jsurftrip/pipes-automation
---
<!-- frontmatter は INDEX.md に転記される。1行で書く。
     state: active / waiting（相手待ち）/ paused（保留）/ done（完了）
     updated: 内容を更新した日（YYYY-MM-DD）。STATUS を書き換えたら必ず更新する -->

# pipes

## 現状
<!-- ※ pipes-automation の git 履歴から Claude が下書きした内容。実態と違えば直す -->
- GitHub Actions で1日3回（9:30/12:00/18:00 JST）TDnet をスキャンし、PIPES判定を実行（`main.py`）
- ダッシュボード（`dashboard/`）に記事レビュー・TDnet詳細・WP下書き管理・即時スキャンを実装済み
- PDFファクトチェック機能を追加済み（2026-03-17）
- WordPress への自動投稿は停止中。記事生成とWP下書きUIまで（最終コミット 2026-03-17）

## 次の作業
<!-- 最初の1項目が INDEX.md に出る。優先度の高い順 -->
- [ ] 途中になっている作業の続きを確認し、ここに具体的に書く（要ユーザー記入）

## 決定事項
<!-- 決めたことと理由。覆したら取り消し線で残し、新しい行を足す -->
| 日付 | 決定 | 理由 |
|---|---|---|

## 関連リンク
- https://github.com/jsurftrip/pipes-automation
<!-- リポジトリ、ドキュメント、チケットなど。APIキー・パスワード・個人情報は書かない -->
