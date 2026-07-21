# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

VoiceCode は、ローカルでオフライン動作するデスクトップ音声入力ツールです。プログラミング、ドキュメント作成、日常のテキスト入力で利用できます。マイク音声を録音し、ローカルの Whisper モデルで文字起こしし、グローバルホットキーで現在のアプリに入力できます。

## 主な機能

- `faster-whisper` によるローカル・オフライン文字起こし
- `pywebview` ベースの Windows デスクトップ UI
- `127.0.0.1` のみにバインドするローカル Flask/Waitress API
- 押して話すグローバルホットキー
- 英語、簡体字中国語、日本語の UI 言語切り替え
- 自動検出、中国語、英語、日本語の文字起こし言語選択
- マイクデバイス選択とローカル診断パネル
- 任意で有効化できるローカル文字起こし履歴
- プレーン、コーディング、Markdown、Prompt のテキスト後処理モード
- `VOICECODE_SKIP_MODEL_LOAD=1` によるモデルなしプレビューモード
- PowerShell / cmd の UTF-8 出力対応
- ログ、例外、API エラーは英語で出力し、問題調査をしやすくする設計
- 設定はインストール先ではなくユーザーディレクトリに保存
- `python -m voicecode` と `voicecode` コマンドに対応

## 必要環境

- 主なサポート対象は Windows 10/11
- Python 3.10 以上
- マイクアクセス権限
- CUDA 推論用の NVIDIA GPU は任意

## クイックスタート

### PowerShell

```powershell
.\setup.ps1
.\run.ps1
```

### cmd.exe

```bat
setup.bat
run.bat
```

### Python パッケージとして実行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\voicecode.exe
```

または：

```powershell
python -m voicecode
```

## 設定

デフォルトの設定ファイル保存先：

- Windows：`%APPDATA%\VoiceCode\config.json`
- Linux/macOS：`$XDG_CONFIG_HOME/voicecode/config.json` または `~/.config/voicecode/config.json`

主な環境変数：

| 変数 | 用途 |
| --- | --- |
| `VOICECODE_CONFIG_FILE` | 設定ファイルの場所を上書き |
| `VOICECODE_STATIC_DIR` | Web UI の静的ファイルディレクトリを上書き |
| `VOICECODE_LOG_LEVEL` | ログレベルを設定、例：`DEBUG` |
| `PORT` | ローカル HTTP ポートを設定、デフォルトは `7788` |
| `WHISPER_MODEL` | 起動時に読み込む Whisper モデル、デフォルトは `base` |

## プライバシー

VoiceCode はローカル動作を前提に設計されています。音声は本機の `127.0.0.1` 上のローカルサービスにのみ送信され、ローカルの Whisper モデルで処理されます。

## 開発時のチェック

```powershell
python -m pytest
python -m ruff check app.py main.py tests src/voicecode
python -m mypy app.py main.py src/voicecode
python -m pip wheel . --no-deps -w dist
```

## ライセンス

MIT。詳しくは [LICENSE](LICENSE) を参照してください。
