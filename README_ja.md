# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

VoiceCode は、ローカルでオフライン動作するデスクトップ音声入力ツールです。プログラミング、ドキュメント作成、日常のテキスト入力に利用できます。マイク音声を録音し、ローカルの Whisper モデルで文字起こしし、グローバルなプッシュトゥトーク・ホットキーで現在のアプリに入力できます。

## 主な機能

- faster-whisper によるローカル・オフライン文字起こし
- pywebview ベースの Windows デスクトップ UI
- 127.0.0.1 のみにバインドするローカル Flask/Waitress API
- グローバルなプッシュトゥトーク・ホットキー
- 英語、簡体字中国語、日本語の UI 切り替え
- 文字起こし言語：自動検出、中国語、英語、日本語
- モデルなしプレビューモード：VOICECODE_SKIP_MODEL_LOAD=1
- Plain、Coding、Markdown、Prompt のテキスト後処理モード
- 任意のローカル履歴、マイク選択、診断パネル
- インストール先を選択できる Windows 標準インストーラー
- パッケージ版では将来のモデルダウンロードとキャッシュをインストール先に集約

## 一般ユーザー向けインストール

推奨インストーラー：

~~~text
packaging/installer/Output/VoiceCode-0.1.0-windows-x86_64-setup.exe
~~~

インストール時にインストール先フォルダーを選択できます。既定値は：

~~~text
%LOCALAPPDATA%\Programs\VoiceCode
~~~

インストーラーを使う場合、ユーザーが Python を別途インストールする必要はありません。Python ランタイム、Python パッケージ、ネイティブ依存関係はインストール先に配置されます。将来 Hugging Face / faster-whisper がダウンロードするモデルとキャッシュは以下に保存されます：

~~~text
<install-dir>\runtime\cache
<install-dir>\runtime\models
~~~

これにより、アプリ本体と大きなランタイムファイルを同じ場所にまとめ、バックアップ、移動、削除を簡単にできます。

## 開発実行

PowerShell：

~~~powershell
.\setup.ps1
.\run.ps1
~~~

cmd.exe：

~~~bat
setup.bat
run.bat
~~~

Python パッケージとして実行：

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\voicecode.exe
~~~

または：

~~~powershell
python -m voicecode
~~~

## 設定とランタイムデータ

- Windows の設定既定値：%APPDATA%\VoiceCode\config.json
- Windows のログ既定値：%APPDATA%\VoiceCode\logs\voicecode.log
- 文字起こし履歴の既定値：設定ファイルの近くにある history.jsonl
- パッケージ版のモデルとダウンロードキャッシュ既定値：<install-dir>\runtime

主な環境変数：VOICECODE_CONFIG_FILE、VOICECODE_STATIC_DIR、VOICECODE_RUNTIME_DIR、VOICECODE_MODEL_DIR、VOICECODE_LOG_FILE、VOICECODE_HISTORY_FILE、VOICECODE_SKIP_MODEL_LOAD、VOICECODE_ENABLE_TRAY、PORT、WHISPER_MODEL。

## Windows インストーラーのビルド

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1
~~~

出力：

~~~text
packaging\installer\dist\VoiceCode\
packaging\installer\Output\VoiceCode-0.1.0-windows-x86_64-setup.exe
~~~

Inno Setup がない場合は one-folder アプリのみ作成できます：

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1 -SkipInno
~~~

## 最終リリース検証

現在のリリース候補は以下を通過しています：

- ruff format --check
- ruff check
- mypy
- pytest（35 passed）
- py_compile
- wheel ビルド
- PyInstaller one-folder ビルド
- Inno Setup インストーラービルド
- カスタムディレクトリへのサイレントインストール/アンインストール smoke test

API 入力検証では、不正な JSON、JSON null、object 以外の payload、boolean と integer の混同、不正なホットキー修飾キー、重複起動、モデル再読み込み競合、録音キャンセル順序などの境界もカバーしています。

## プライバシー

VoiceCode はローカル動作を前提に設計されています。音声はローカルマシン上の 127.0.0.1 のサービスにのみ送信され、ローカルの Whisper モデルで処理されます。文字起こし履歴、ログ、設定、モデルキャッシュはローカルファイルであり、VoiceCode がアップロードすることはありません。

## ライセンス

MIT。詳細は [LICENSE](LICENSE) を参照してください。
