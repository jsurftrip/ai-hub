# 【pipes】作業開始用コンテキスト

<!-- 自動生成: `python3 scripts/hub.py sync` で更新。手で編集しない -->
生成日: 2026-10-06

- 状態: active
- 概要: PIPES.jp 自動化: TDnetの第三者割当情報を取得→PIPES判定→記事生成。ダッシュボードとPDFファクトチェックまで実装済み、WP自動投稿は停止中
- リポジトリ: https://github.com/jsurftrip/pipes-automation
- STATUS 更新日: 2026-03-17

# pipes

## 現状
- GitHub Actions で1日3回（9:30/12:00/18:00 JST）TDnet をスキャンし、PIPES判定を実行（`main.py`）
- ダッシュボード（`dashboard/`）に記事レビュー・TDnet詳細・WP下書き管理・即時スキャンを実装済み
- PDFファクトチェック機能を追加済み（2026-03-17）
- WordPress への自動投稿は停止中。記事生成とWP下書きUIまで（最終コミット 2026-03-17）

## 次の作業
- [ ] 途中になっている作業の続きを確認し、ここに具体的に書く（要ユーザー記入）

## 決定事項
| 日付 | 決定 | 理由 |
|---|---|---|

## 関連リンク
- https://github.com/jsurftrip/pipes-automation

## 直近のログ
（ログなし）
