# VoiceCode

![VoiceCode アイコン](assets/voicecode-icon.png)

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

**現在のバージョン：v0.2.0**

VoiceCode は、プログラミング、文章作成、プロンプト入力向けのローカル優先デスクトップ音声入力アプリです。faster-whisper / CTranslate2 を使用して端末内で文字起こしを行い、グローバルなプッシュトゥトーク・ホットキーで現在のアプリへ入力できます。

## 主な機能

- 英語、簡体字中国語、日本語を切り替えられる Windows デスクトップ UI。
- 表示言語、文字起こし言語、マイク、モデル、ハードウェアを設定する初回起動ガイド。
- NVIDIA CUDA の自動検出と、安全な CPU int8 フォールバック。
- モデル、オプション依存関係、ダウンロードキャッシュをインストール先の `runtime` フォルダーに集約。
- モデルキャッシュ管理、文字起こし履歴、診断エクスポート、設定可能な拡張機能。モデル取得時はサイズ、速度、経過時間、停止状態を表示します。
- `127.0.0.1` のみにバインドされ、トークンと Host/Origin 検証で保護されたローカル API。
- Windows では単一インスタンスで動作し、二重起動時は既存ウィンドウを復元。

## Windows へのインストール

一般ユーザーには次のインストーラーを推奨します。

```text
VoiceCode-v0.2.0-Windows-x64-Setup.exe
```

セットアップ画面でインストール先を選択できます。既定値は次のとおりです。

```text
%LOCALAPPDATA%\Programs\VoiceCode
```

インストーラーにはコア依存関係と独立した Python/pip ランタイムが含まれるため、Python を別途インストールする必要はありません。

```text
<インストール先>\VoiceCode.exe
<インストール先>\runtime\python
<インストール先>\runtime\dependencies
<インストール先>\runtime\models
<インストール先>\runtime\cache
```

アプリから追加した依存関係、Whisper モデル、Hugging Face/pip キャッシュは、すべて選択したインストール先に保存されます。設定、ログ、履歴は Windows ユーザーごとの書き込み可能な設定ディレクトリに保存されます。アンインストールではセットアップが管理するプログラムファイルを削除しますが、ユーザーがダウンロードしたモデルなどのランタイムデータは再インストール用に残ります。完全削除する場合は、アンインストール後に残った `runtime` ディレクトリを手動で削除してください。

v0.2.0 インストーラーは **2026 年 7 月 24 日**に、カスタムパス、上書きインストール、単一インスタンス、3 言語リソース、組み込み pip、キャッシュ済みモデル、文字起こし、アンインストール、再インストールまで検証済みです。詳細は[最終検証記録](docs/RELEASE_VALIDATION_0.2.0.md)を参照してください。ローカルで検証した成果物は未署名のため、公開前にコード署名と署名後の再検証が必要です。

## ソースから実行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[runtime,dev]"
.\.venv\Scripts\python.exe -m voicecode
```

## 言語の切り替え

初回起動ガイドまたは「設定」ページから英語、中国語、日本語を切り替えられます。v0.2.0 では、中国語・日本語が疑問符で表示される問題と、中国語・日本語から英語へ戻せない問題を修正しました。

翻訳ファイル：

```text
src/voicecode/static/i18n/en.json
src/voicecode/static/i18n/zh.json
src/voicecode/static/i18n/ja.json
```

静的ファイルを変更した後は、次を実行してください。

```powershell
python -X utf8 tools/sync_static.py
```

## データの保存場所

- 設定：`%APPDATA%\VoiceCode\config.json`
- ログ：`%APPDATA%\VoiceCode\logs\voicecode.log`
- 履歴：設定ディレクトリ内の `history.jsonl`
- インストール版のモデルと依存関係：`<インストール先>\runtime`

## Windows インストーラーのビルド

Windows x64、CPython 3.12 x64、Inno Setup 6 が必要です。

```powershell
python -m pip install -e ".[runtime,dev]"
python -X utf8 tools/generate_icon.py
python -X utf8 packaging/windows/build_windows_installer.py
```

ビルドスクリプトは、時間のかかる PyInstaller 処理の前に組み込み Python と `get-pip.py` をダウンロードして検証します。ダウンロードは `build/windows/downloads/` にキャッシュされ、失敗時は原子的な一時ファイルを使って再試行されます。

出力先：

```text
dist/windows/installer/
```

使い捨てのテスト環境では、次の自動インストール検証を実行できます。

```powershell
python -X utf8 packaging/windows/verify_windows_installer.py `
  --installer dist/windows/installer/VoiceCode-v0.2.0-Windows-x64-Setup.exe `
  --install-dir "$env:TEMP\VoiceCode-installer-smoke" `
  --version 0.2.0 `
  --skip-launch `
  --uninstall
```

詳細は [Windows Installer Build](docs/WINDOWS_INSTALLER.md) を参照してください。

## リリース前チェック

```powershell
python -m ruff format --check app.py main.py tests src/voicecode packaging/windows tools
python -m ruff check app.py main.py tests src/voicecode packaging/windows tools
python -m mypy app.py main.py src/voicecode
python -X utf8 -m pytest -q
python -X utf8 tools/sync_static.py --check
```

## ドキュメント

- [API](docs/API.md)
- [アーキテクチャ](docs/ARCHITECTURE.md)
- [設定](docs/CONFIGURATION.md)
- [開発ガイド](docs/DEVELOPMENT.md)
- [パッケージング](docs/PACKAGING.md)
- [リリース手順](docs/RELEASING.md)
- [Windows インストーラー](docs/WINDOWS_INSTALLER.md)
- [v0.2.0 最終検証記録](docs/RELEASE_VALIDATION_0.2.0.md)
- [トラブルシューティング](docs/TROUBLESHOOTING.md)

## ライセンス

MIT。詳細は [LICENSE](LICENSE) を参照してください。
## 最近のデスクトップ改善

VoiceCode は「読み込み」を表示する前にモデルキャッシュを厳密に検証し、検証済みのローカルスナップショットから直接読み込みます。不完全なダウンロードは部分キャッシュとして扱い、再開できます。エラー詳細のコピー、ローカルポートを保持するウィンドウなし残留プロセスの回復にも対応しました。上部バーには CPU・GPU・メモリの概要のみを表示し、詳細は設定画面に移動しました。マインスイーパーには上級（16 × 30、地雷 99 個）を追加し、新しい UI 文言は英語・簡体字中国語・日本語に対応しています。
