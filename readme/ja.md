# AI Memory Vault · クロスツール AI 記憶ライブラリ

[English](../README.md) | [简体中文](zh-CN.md) | [日本語](ja.md) | [한국어](ko.md) | [Español](es.md) | [Português](pt-BR.md) | [Русский](ru.md)

> Claude Code / Codex / Cursor / Cline / Gemini CLI / Trae / Qoder / ZCode など、**すべての AI ツールで同じ記憶を共有**するためのディレクトリ構造 + ルール + ゲートスクリプト。
> **中核概念：ほぼゼロ設定——ローカルには何もデプロイしない。** 中身は Markdown ファイルと標準ライブラリだけで動く Python スクリプト 4 本。純粋な Markdown ディレクトリにコピーするだけで「デプロイ」完了。依存・サービス・ビルド・プレースホルダ置換は一切なし。ツールはワークスペース直下の `AGENTS.md` を自動で読み、スクリプトは記憶庫の場所を自動検出します。
>
> **Obsidian に非依存**：記憶庫の中身はただの Markdown ディレクトリ（`Memory/`）。ファイルを読み書きできるどんな Agent・どんな Markdown エディタでも使えます。作者自身は Obsidian で閲覧しています（Templater / Dataview は任意の拡張で、依存ではありません）。

**なぜ必要か**：各 AI ツールはそれぞれ独自の「記憶」を持ちます——`~/.claude/`、`~/.codex/`、`.workbuddy/memory/`、auto-memory…。ツール間で記憶は共有されず、乗り替えると記憶喪失。ツール私物フォーマットに埋もれた記憶は読めず、監査もできません。本プロジェクトは**記憶の唯一の置き場所**を、全ツールが読み書きできる 1 つの Markdown ディレクトリに集約し、ツール側には「ポインタ + 短いフック」だけを置きます。

| ディレクトリ | 内容 |
|---|---|
| [docs/](../docs/) | **設計思想**：なぜこう設計したか、全ゲートの背後にある実事故（中国語） |
| [starter/](../starter/) | **コピーしてすぐ使える骨格**：ディレクトリ構造 + ルール一式 + サンプルプロジェクト |
| [scripts/](../scripts/) | **ゲートスクリプト**：インデックス生成 / ToDo 監査 / エンコーディング検査 / 指令同期 |

## 核心理念（七か条・要約）

1. **ほぼゼロ設定** — Markdown ファイル + 標準ライブラリのみのスクリプト。ディレクトリにコピーすることがインストールの全部。
2. **記憶の置き場所は一つ** — ツール側設定には「ポインタ + 短いフック」のみ。記憶の中身は書かない。
3. **構造化された階層** — `Preferences` / `Plans` / `Decisions` / `Lessons` / `Workflows` / `Projects` ＋ `Todo.md`・`Inbox/`・`Archive/`。
4. **インデックスは派生物** — frontmatter から `mem_index.py` が生成。人は一行紹介を磨くだけで、再生成しても消えない。
5. **完了 = 移動** — 終わった ToDo は `working/completed.md` へ移し、Todo からは削除。その場で ✅ を付けない。
6. **ゲートのある工程だけ劣化しない** — 全ゲートには実事故の背書があります（[docs/04](../docs/04-演化史-门禁背后的事故.md)）。
7. **プライバシーはガードで守る** — `.gitignore` ＋ `pre-commit` フックが `Memory/` 触りのコミットを拒否。

## 一言デプロイ

以下を**任意の AI Agent にそのまま送る**だけ（Claude Code、Cursor、ファイル操作のできる Web エージェントなど）：

```text
https://github.com/star-nebula/ai-memory-vault をクローン（できなければ zip をダウンロードして展開）し、
starter/ の中身をすべて私の記憶ライブラリのワークスペースルートにコピーしてください——
既にノートライブラリがあればそのルートへ、なければ空ディレクトリを新規作成。
その後、そのディレクトリで python scripts/mem_index.py --write を実行してインデックスを生成。
最後に、ワークスペースルートの AGENTS.md と Memory/_index.md を読み、
「いつ記憶を読み、どう書くか」を私に復唱してください。
```

## 手動デプロイ

```bash
cp -r starter/* /path/to/your-vault/   # 唯一の「インストール」動作
```

置換すべきプレースホルダも、インストールすべき依存もありません。任意の後続ステップ：

```bash
python scripts/mem_index.py --write      # 各層インデックスを生成
python scripts/mem_index.py --check      # インデックス漂移ゲート
python scripts/todo_audit.py --check     # ToDo アーカイブゲート
python scripts/encoding_guard.py <path>  # エンコーディング + 制御文字ゲート
```

**AI ツールへの接続**：`starter/Memory/Workflows/AI工具自定义指令.md` に完全版（カスタム指示欄に貼る）と最小版（プロジェクトルートの `AGENTS.md` に置く）の 2 種を同梱。デフォルトは相対パス表記で、貼るだけで動きます。

## ゲートスクリプト

| スクリプト | 拦むもの |
|---|---|
| `mem_index.py` | 手管理インデックスの漂移・「逐語一致」対表の不整合・読時鮮度プロトコルの欠落 |
| `todo_audit.py` | 完了済みだが未移動の残骸・グループ名とプロジェクト dir の不一致・「Todo に移した」虚偽申告・語彙外 type |
| `encoding_guard.py` | 非 UTF-8 / BOM・AI のエスケープ食いによる裸制御文字（grep から見えなくなる地雷） |
| `sync_memory_instructions.py` | ツール指令位と単一真源の漂移・真源の制御文字汚染 |

> 詳細ドキュメント（設計思想・構造・原則・進化史）は [docs/](../docs/)（中国語）に、全体の概要は[英語版 README](../README.md) にあります。**この翻訳が遅れている場合は英語版と中国語 docs が権威です。**

## License

[MIT](../LICENSE) — 構造・ルール・スクリプトは自由にご利用ください。役に立ったら Star や Issue であなたの改造を共有してもらえると嬉しいです。
