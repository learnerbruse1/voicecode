# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

VoiceCode は、コーディング、文章作成、プロンプト作成向けのローカル優先デスクトップ音声文字起こしアプリです。マイク音声を録音し、`faster-whisper` / CTranslate2 でローカルに文字起こしします。

## 主な機能

- Whisper 互換モデルによるローカル文字起こし。
- NVIDIA CUDA の自動検出と CPU への安全なフォールバック。
- 推論デバイス設定：`auto`、`cpu`、`cuda`。
- 計算精度設定：`auto`、`int8`、`float16`、`float32`、`int8_float16`。
- `127.0.0.1` のみにバインドするローカル API。
- `pywebview` デスクトップ UI、`pynput` グローバルホットキー、`sounddevice` マイク録音。
- ファイルアップロードや統合向けの `/transcribe` API。
- 設定、ログ、履歴はユーザー書き込み可能なディレクトリに保存。

## インストールと実行

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m voicecode
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m voicecode
```

このリポジトリにはワンクリックインストーラースクリプトや生成済みインストーラー成果物は含めません。標準的な Python 仮想環境を使用してください。

## CPU / NVIDIA GPU

既定では、CTranslate2 が CUDA GPU を検出すると `cuda/float16` を使用し、検出できない場合は `cpu/int8` を使用します。CUDA 推論が失敗した場合も `cpu/int8` にフォールバックします。

詳しい API と開発情報は [docs/API.md](docs/API.md)、[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) を参照してください。

## License

MIT. See [LICENSE](LICENSE).
