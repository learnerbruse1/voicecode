# VoiceCode ユーザーガイド —— 機能と設定の詳解

VoiceCode はローカル優先のデスクトップ音声入力アプリです。マイク音声を録音し、`faster-whisper` / CTranslate2 で端末内で文字起こしし、プッシュトゥトークのホットキーで現在のアプリに入力します。処理はすべてローカルで完結し、外部へ送信されません。

このガイドでは、各機能と各設定の役割を詳しく説明します。

## クイックスタート

1. VoiceCode をインストールして起動します。
2. 初回起動ガイドで、UI/文字起こし言語、ローカルランタイムのインストール、マイクの確認、モデルとハードウェアの選択を行います。
3. モデルを選択します（まずは `base`、NVIDIA GPU なら `small` を推奨）。
4. ホットキー（既定 `Alt+Z`）を押しながら話し、離すと文字が現在のウィンドウに入力されます。

## コア機能

### グローバルホットキーによる口述

ホットキーを押している間録音し、離すと停止・文字起こし・入力まで行われます。ホットキーは変更可能です（修飾キー `alt`/`ctrl`/`shift` + 英字または `space`）。

### リアルタイム草稿

ホットキーを押している間、文字起こしパネルに `partial_interval_ms`（既定 600 ミリ秒）ごとに仮の草稿が表示されます。離すと確定します。

### 入力方式（現在のアプリへの文字入力）

文字起こし結果を現在のアプリに入力します：

- `clipboard`（Windows 既定）：クリップボードへコピーして貼り付け。貼り付けに失敗した場合はキー入力シミュレーションへフォールバックします。
- `keystrokes`：常にキー入力シミュレーションで入力します（ほとんどのアプリで動作）。

`typing_delay_ms` で入力前の遅延を設定できます（既定 150 ミリ秒）。

### デコードプリセット

デコードの速度と精度のトレードオフを制御します：

| プリセット | 効果 |
| --- | --- |
| `fast` | beam=1・温度 0・前文条件付けなし —— 最速、精度はやや低下 |
| `balanced`（既定） | `beam_size`（既定 5）と `condition_on_previous_text` を使用 |
| `high_quality` | beam=8 で温度ラダー使用 —— 最も遅いが高精度 |
| `custom` | `beam_size` と `condition_on_previous_text` を手動設定 |

### テキストモード

認識結果への後処理：

- `plain`：そのまま出力。
- `coding`：コード・コマンド向けに整形。
- `markdown`：Markdown 文書向けに整形。
- `prompt`：プロンプト入力向けに整形。

### 履歴

文字起こし結果はローカル履歴に保存できます（`history_limit` で件数設定、既定 50 件、自動トリミング）。履歴パネルでは検索・言語フィルター・単件削除、JSON / TXT / Markdown エクスポートが可能です。

### モデルとモデルキャッシュ

Models ページには、サイズ・最小/推奨 VRAM・ローカライズされたヒント・キャッシュ状態を含む全対応モデルが表示されます。モデルのダウンロード/読み込み、キャッシュ削除ができます。読み込み前にスナップショットの整合性を検証し、不完全なダウンロードは再開できます。モデルは同梱されず、初回使用時にダウンロードされます（公式エンドポイントに到達できない場合は `hf-mirror.com` へ自動フォールバック）。

### 拡張機能

設定 → 拡張機能で個別に有効化します：

| 拡張機能 | 役割 |
| --- | --- |
| `audio_io` | アップロード/JSON 文字起こし API とその制限（`max_upload_mb`、`max_json_seconds`、`sample_rate`、許可サフィックス）。 |
| `exporters` | `/transcribe` の出力形式：`json`、`txt`、`srt`、`vtt`。 |
| `hotwords` | 認識を偏向させて正確に出力させたい用語のリスト。 |
| `vad` | 音声区間検出エンジン（`faster_whisper`、`silero`、`off`）と閾値（`min_silence_duration_ms`、`speech_pad_ms`、`threshold`）。 |
| `zh_normalizer` | OpenCC による中国語の簡繁変換と、スペース・句読点の正規化（任意）。 |
| `quality` | WER/CER 指標（`jiwer` が必要、任意）。 |
| `diarization` | pyannote による話者分離（モデル、`token_env` 例 `HF_TOKEN`、デバイス、最小/最大話者数）。 |
| `punctuation` | NeMo による句読点復元（英語、`punctuation_en_bert`）。 |

**中国語の出力字形** — 設定の「言語」パネルで、中国語の文字起こし結果の字形を選択できます：**変換しない**・**簡体字中国語**・**繁体字中国語**（設定キー `extensions.zh_normalizer.script`）。簡体字または繁体字を選ぶと OpenCC ベースの `zh_normalizer` 拡張機能が自動的に有効になります。初回使用時に「依存関係」ページで `opencc-python-reimplemented` のインストールを求められる場合があります。

追加パッケージが必要な拡張機能（Silero VAD、pyannote、NeMo、OpenCC）は、依存関係ページから隔離されたランタイムディレクトリへインストールされ、システムの Python は汚染しません。

### セキュリティ

- HTTP API は `127.0.0.1` のみにバインドされ、プロセス単位のトークン、ループバック Host/Origin 検証、CSP、変更監査ログで保護されています。
- 設定・履歴・ログはユーザー書き込み可能なパスに保存され、モデルとオプションパッケージはインストール/ランタイムディレクトリ配下に置かれます。

### オフライン利用

`VOICECODE_OFFLINE=1` を設定するとダウンロードを禁止し、完全なローカルキャッシュのみを使用します。ダウンロード済みモデルはオフラインで再利用できます。

### その他の内蔵機能

- 初回起動ガイド（言語、ランタイム、マイク、モデル、ハードウェア）。
- 診断パネルとワンクリック ZIP エクスポート。
- 英語 / 簡体字中国語 / 日本語の UI と文字起こし。
- 内蔵マインスイーパー（初級 / 中級 / 上級）。

## 設定リファレンス

設定は `config.json` に保存されます（Windows：`%APPDATA%\VoiceCode\config.json`、Unix：`$XDG_CONFIG_HOME/voicecode/config.json` または `~/.config/voicecode/config.json`）。多くは設定画面でも変更できます。

| 設定 | 値 | 既定 | 役割 |
| --- | --- | --- | --- |
| `hotkey` | 修飾キー `alt`/`ctrl`/`shift` + 英字または `space` | `alt`+`z` | グローバルなプッシュトゥトークホットキー。 |
| `model` | 下記「モデル」参照 | `base` | 読み込む Whisper モデル。 |
| `device` | `auto`、`cpu`、`cuda` | `auto` | 推論デバイス。`auto` は CUDA があれば CUDA、なければ CPU。 |
| `compute_type` | `auto`、`default`、`int8`、`int8_float16`、`int16`、`float16`、`float32` | `auto` | 精度/量子化。`auto` = CUDA で `float16`、CPU で `int8`。 |
| `decode_preset` | `fast`、`balanced`、`high_quality`、`custom` | `balanced` | デコード速度/精度プリセット。 |
| `beam_size` | 1–10 | 5 | ビーム幅（`balanced`/`custom` で使用）。 |
| `condition_on_previous_text` | 真偽値 | `false` | 前のセグメントのテキストを条件付けに使うか。 |
| `partial_results` | 真偽値 | `true` | 録音中のリアルタイム草稿表示。 |
| `partial_interval_ms` | 200–5000 | 600 | 草稿の更新間隔。 |
| `vad_filter` | 真偽値 | `true` | 無音フィルタリング（VAD）を有効化。 |
| `language` | `auto`、`zh`、`en`、`ja` | `zh` | 文字起こし言語。`auto` は自動検出。 |
| `ui_language` | `en`、`zh`、`ja` | `en` | インターフェース言語。 |
| `audio_device` | 空、インデックス、または名称 | 空 | マイク。空 = システム既定。 |
| `text_mode` | `plain`、`coding`、`markdown`、`prompt` | `plain` | テキストの後処理。 |
| `history_enabled` | 真偽値 | `true` | 履歴へ保存するか。 |
| `history_limit` | 整数 | 50 | 履歴の最大件数（自動トリミング）。 |
| `font_size` | CSS サイズ | `1rem` | 文字起こしパネルの文字サイズ。 |
| `theme` | `system`、`light`、`dark` | `system` | UI テーマ。 |
| `append_mode` | `append`、`replace` | `append` | 新しい結果を追記するか置き換えるか。 |
| `typing_mode` | `clipboard`、`keystrokes` | `clipboard` | 現在のアプリへの入力方式。 |
| `typing_delay_ms` | 0–5000 | 150 | 文字起こし後に入力するまでの遅延。 |
| `on_top` | 真偽値 | `false` | ウィンドウを常に最前面に置くか。 |
| `onboarding` | オブジェクト | 未完了 | 初回起動ガイドの状態。 |

## モデル

| モデル | サイズ | 最小/推奨 VRAM | 説明 |
| --- | --- | --- | --- |
| `tiny` | 約 75 MB | 1 / 2 GB | 最速。簡単なテストや非常に古いハードウェア向け。 |
| `base` | 約 150 MB | 1 / 2 GB | CPU での日常的な文字起こしの既定。 |
| `small` | 約 500 MB | 2 / 4 GB | 一般的なノート PC やエントリー GPU 向けのバランス型。 |
| `medium` | 約 1.5 GB | 5 / 6 GB | 高精度。6GB 以上の VRAM または高性能 CPU が必要。 |
| `large-v3` | 約 3 GB | 10 / 12 GB | 多言語で最高精度。 |
| `large-v3-turbo` | 約 3 GB | 6 / 8 GB | 最新の公式 Whisper。高速で精度もほぼ同等。 |
| `distil-large-v3` | 約 1.5 GB | 6 / 8 GB | 高速な蒸留大モデル。 |
| `distil-whisper/distil-large-v3.5-ct2` | 約 1.5 GB | 6 / 8 GB | 蒸留 v3.5。large-v3 に迫る精度、英語に強い。 |
| `kotoba-tech/kotoba-whisper-v2.0-faster` | 約 1.5 GB | 6 / 8 GB | 日本語最適化。日本語では large-v3 より高精度でサイズ約半分。 |

速度/精度のヒント：

- 6GB 以上の GPU・英語：`distil-whisper/distil-large-v3.5-ct2` または `large-v3-turbo`。
- 日本語：`kotoba-tech/kotoba-whisper-v2.0-faster`（文字起こし言語は日本語を推奨）。
- CPU のみ：`base`/`tiny` + プリセット `fast` + デバイス `cpu`。
- 速度を上げる最大の 2 点：`partial_results` をオフ、プリセット `fast` を使用。

## 環境変数

| 変数 | 役割 |
| --- | --- |
| `WHISPER_MODEL` | 起動モデル（既定 `base`）。 |
| `WHISPER_DEVICE` | 優先デバイス（`auto`、`cpu`、`cuda`）。 |
| `WHISPER_COMPUTE_TYPE` | 優先計算タイプ（`auto`、`int8`、`float16` など）。 |
| `WHISPER_CPU_THREADS` | CPU ワーカースレッド数（論理コア数に上限）。 |
| `VOICECODE_CONFIG_FILE` | 設定ファイルのパスを上書き。 |
| `VOICECODE_STATIC_DIR` | 静的 UI ディレクトリを上書き。 |
| `VOICECODE_RUNTIME_DIR` | ランタイムディレクトリ（モデル/依存/キャッシュ）を上書き。 |
| `VOICECODE_MODEL_DIR` | モデルのダウンロード/キャッシュルートを上書き。 |
| `VOICECODE_OFFLINE` | `1` = キャッシュ済みモデルのみ使用。 |
| `VOICECODE_SKIP_MODEL_LOAD` | `1` = モデルを読み込まず UI/API を起動。 |
| `VOICECODE_SKIP_WARMUP` | `1` = 読み込み後のウォームアップをスキップ。 |
| `VOICECODE_TRANSCRIBE_TIMEOUT` | 文字起こしウォッチドッグのタイムアウト（秒、既定 120）。 |
| `VOICECODE_API_TOKEN` / `VOICECODE_DISABLE_API_TOKEN` | ローカル API トークンの上書き/無効化。 |
| `PORT` | HTTP ポート（既定 7788）。 |
| `HF_ENDPOINT` | Hugging Face エンドポイントを明示指定。 |
| `HF_HUB_ETAG_TIMEOUT` / `HF_HUB_DOWNLOAD_TIMEOUT` | HF メタデータ/ダウンロードのタイムアウト。 |
| `HF_HUB_DISABLE_XET` | Xet/CAS 転送を無効化（パッケージ版の既定は無効）。 |
| `VOICECODE_DEP_DIR` | 隔離された依存インストールディレクトリ。 |
| `VOICECODE_LOG_LEVEL` | ログレベル（既定 `INFO`）。 |

## パフォーマンス

- NVIDIA GPU（6GB 以上）：`float16` を使用。言語に応じて `large-v3-turbo`/`distil-large-v3.5` または `kotoba` を選択。
- VRAM が少ない GPU：`small`/`base` を使用。VRAM 不足時は自動で CPU int8 にフォールバックします。
- CPU：`int8` を使用。`WHISPER_CPU_THREADS` を調整し、`base`/`tiny` + プリセット `fast` を推奨。
- GPU の文字起こしがハング/失敗した場合、VoiceCode はモデルを CPU int8 で自動的に再読み込みします（ウォッチドッグのタイムアウトは既定 120 秒、`VOICECODE_TRANSCRIBE_TIMEOUT` で変更可）。

## 関連ドキュメント

- [API リファレンス](API.md)
- [設定の説明](CONFIGURATION.md)
- [トラブルシューティング](TROUBLESHOOTING.md)
- [Windows インストーラー](WINDOWS_INSTALLER.md)