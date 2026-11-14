# AGENTS.md

## コミット

コミットメッセージは日本語で書く。

コミット済みの履歴を書き換える操作は、必要だと判断した時も実行せず、提案して指示を仰ぐ。

## push

push はユーザーの指示を待つ。

## テスト

テストは Blender の background モードで実行する。`make test` を使う。Blender のパスが環境と違うときは `BLENDER_EXE` を上書きする。

## 静的チェック

`ruff check src/ tests/` と `ty check src/` を通してからコミットする。
