# VoiceCode 使用指南 —— 功能与设置详解

VoiceCode 是一款本地优先的桌面语音转文字软件。它录制麦克风音频，通过 `faster-whisper` / CTranslate2 在本机完成转写，并可用「按住说话」的全局快捷键把结果输入到当前应用。所有处理都在你的电脑本地完成，不离开本机。

本指南详细介绍各项功能，以及每个设置的作用。

## 快速开始

1. 安装 VoiceCode 并启动。
2. 首次启动向导会依次配置：界面/转写语言、安装本地运行依赖、检测麦克风、选择模型与硬件。
3. 选择一个模型（可先用 `base`；有 NVIDIA 显卡可用 `small`）。
4. 按住全局快捷键（默认 `Alt+Z`）说话，松开后文字会自动输入到当前窗口。

## 核心功能

### 全局快捷键口述

按住快捷键开始录音，松开即停止、转写并输入文字。快捷键可自定义（修饰键 `alt`/`ctrl`/`shift` + 字母或 `space`）。

### 实时草稿

按住快捷键录音时，转写面板会每 `partial_interval_ms`（默认 600 毫秒）刷新一次临时草稿；松开后定稿。

### 上屏方式（输入到当前应用）

转写完成后把文字输入到当前激活的应用：

- `clipboard`（Windows 默认）：复制到剪贴板并粘贴；粘贴失败时自动回退为模拟按键。
- `keystrokes`：始终用模拟按键输入（兼容大多数应用）。

`typing_delay_ms` 会在输入前加一点延迟（默认 150 毫秒），确保目标应用就绪。

### 解码预设

控制解码速度与精度的取舍：

| 预设 | 效果 |
| --- | --- |
| `fast` | beam=1、温度 0、不结合上文 —— 最快，精度略降 |
| `balanced`（默认） | 使用 `beam_size`（默认 5）与 `condition_on_previous_text` |
| `high_quality` | beam=8 并带温度退避 —— 最慢、最准 |
| `custom` | 自行设置 `beam_size` 与 `condition_on_previous_text` |

### 文本模式

对识别结果做后处理：

- `plain`：原样输出。
- `coding`：针对代码/命令做整理。
- `markdown`：按 Markdown 文档排版。
- `prompt`：针对提示词输入做整理。

### 历史记录

转写结果可保存到本地历史（`history_limit` 可设，默认 50 条，自动裁剪）。历史面板支持搜索、按语言筛选、单条删除，以及 JSON / TXT / Markdown 导出。

### 模型与模型缓存

Models 页列出所有受支持模型，包含大小、最低/推荐显存、本地化提示与缓存状态。你可以下载/加载模型，或删除已缓存模型。加载前会校验快照完整性，不完整的下载可断点续传。模型不随安装包内置——首次使用时联网下载（官方端点不可达时自动切换到 `hf-mirror.com`）。

### 扩展

在 设置 → 扩展 中按需启用：

| 扩展 | 作用 |
| --- | --- |
| `audio_io` | 启用上传/JSON 转写接口及其限制（`max_upload_mb`、`max_json_seconds`、`sample_rate`、允许的后缀）。 |
| `exporters` | `/transcribe` 的输出格式：`json`、`txt`、`srt`、`vtt`。 |
| `hotwords` | 一个热词列表，识别时会偏向精确输出这些词。 |
| `vad` | 语音活动检测引擎（`faster_whisper`、`silero` 或 `off`）与阈值（`min_silence_duration_ms`、`speech_pad_ms`、`threshold`）。 |
| `zh_normalizer` | 可选的中文繁简转换（OpenCC）与空格/标点规范化。 |
| `quality` | 可选的 WER/CER 指标（依赖 `jiwer`）。 |
| `diarization` | 基于 pyannote 的说话人分离（模型、`token_env` 如 `HF_TOKEN`、设备、最少/最多说话人）。 |
| `punctuation` | 基于 NeMo 的标点恢复（英文，`punctuation_en_bert`）。 |

需要额外依赖的扩展（Silero VAD、pyannote、NeMo、OpenCC）会在「依赖」页面安装到隔离运行目录，不污染系统 Python。

### 安全

- HTTP API 仅绑定 `127.0.0.1`，并有进程级令牌、回环 Host/Origin 校验、CSP 与变更审计日志。
- 配置、历史与日志写入用户可写的目录；模型与可选依赖放在安装/运行目录下。

### 离线使用

设置 `VOICECODE_OFFLINE=1` 禁止下载、只使用完整本地缓存。已下载的模型可离线复用。

### 其他内置功能

- 首次启动向导（语言、运行依赖、麦克风、模型、硬件）。
- 诊断面板，支持一键导出 ZIP。
- 英语 / 简体中文 / 日语界面与转写。
- 内置扫雷（初级 / 中级 / 高级）。

## 设置详解

所有设置保存在 `config.json`（Windows：`%APPDATA%\VoiceCode\config.json`；Unix：`$XDG_CONFIG_HOME/voicecode/config.json` 或 `~/.config/voicecode/config.json`）。大多数也可以在设置页修改。

| 设置项 | 可选值 | 默认值 | 作用 |
| --- | --- | --- | --- |
| `hotkey` | 修饰键 `alt`/`ctrl`/`shift` + 字母或 `space` | `alt`+`z` | 全局按住说话快捷键。 |
| `model` | 见下方「模型」 | `base` | 加载的 Whisper 模型。 |
| `device` | `auto`、`cpu`、`cuda` | `auto` | 推理设备；`auto` 有 CUDA 用 CUDA，否则用 CPU。 |
| `compute_type` | `auto`、`default`、`int8`、`int8_float16`、`int16`、`float16`、`float32` | `auto` | 精度/量化；`auto` = CUDA 用 `float16`、CPU 用 `int8`。 |
| `decode_preset` | `fast`、`balanced`、`high_quality`、`custom` | `balanced` | 解码速度/精度预设。 |
| `beam_size` | 1–10 | 5 | 束宽（`balanced`/`custom` 使用）。 |
| `condition_on_previous_text` | 布尔 | `false` | 解码是否结合上一段文字。 |
| `partial_results` | 布尔 | `true` | 录音时显示实时草稿。 |
| `partial_interval_ms` | 200–5000 | 600 | 实时草稿刷新间隔。 |
| `vad_filter` | 布尔 | `true` | 启用静音过滤（VAD）。 |
| `language` | `auto`、`zh`、`en`、`ja` | `zh` | 转写语言；`auto` 自动检测。 |
| `ui_language` | `en`、`zh`、`ja` | `en` | 界面语言。 |
| `audio_device` | 空、索引或名称 | 空 | 麦克风；空 = 系统默认。 |
| `text_mode` | `plain`、`coding`、`markdown`、`prompt` | `plain` | 文本后处理方式。 |
| `history_enabled` | 布尔 | `true` | 是否保存转写历史。 |
| `history_limit` | 整数 | 50 | 历史最大条数（自动裁剪）。 |
| `font_size` | CSS 尺寸 | `1rem` | 转写面板字号。 |
| `theme` | `system`、`light`、`dark` | `system` | 界面主题。 |
| `append_mode` | `append`、`replace` | `append` | 新转写是追加还是替换当前文本。 |
| `typing_mode` | `clipboard`、`keystrokes` | `clipboard` | 文字上屏方式。 |
| `typing_delay_ms` | 0–5000 | 150 | 转写后输入前的延迟。 |
| `on_top` | 布尔 | `false` | 窗口是否总在最前。 |
| `onboarding` | 对象 | 未完成 | 首次启动向导状态。 |

## 模型

| 模型 | 大小 | 最低/推荐显存 | 说明 |
| --- | --- | --- | --- |
| `tiny` | ~75 MB | 1 / 2 GB | 最快；适合快速测试与很旧硬件。 |
| `base` | ~150 MB | 1 / 2 GB | CPU 日常听写默认。 |
| `small` | ~500 MB | 2 / 4 GB | 多数笔记本与入门 GPU 的均衡选择。 |
| `medium` | ~1.5 GB | 5 / 6 GB | 高精度；需 6GB+ 显存或较强 CPU。 |
| `large-v3` | ~3 GB | 10 / 12 GB | 多语言精度最高。 |
| `large-v3-turbo` | ~3 GB | 6 / 8 GB | 最新官方 Whisper；快且精度接近。 |
| `distil-large-v3` | ~1.5 GB | 6 / 8 GB | 高速蒸馏大模型。 |
| `distil-whisper/distil-large-v3.5-ct2` | ~1.5 GB | 6 / 8 GB | 蒸馏 v3.5，接近 large-v3 精度，英语强。 |
| `kotoba-tech/kotoba-whisper-v2.0-faster` | ~1.5 GB | 6 / 8 GB | 日语特化；日语比 large-v3 更准、体积约一半。 |

速度/精度建议：

- 6GB+ 显卡、英文：`distil-whisper/distil-large-v3.5-ct2` 或 `large-v3-turbo`。
- 日文：`kotoba-tech/kotoba-whisper-v2.0-faster`（转写语言选择「日语」效果最佳）。
- 纯 CPU：`base`/`tiny` + 预设 `fast` + 设备 `cpu`。
- 提升速度的两大开关：关闭 `partial_results`、使用预设 `fast`。

## 环境变量

| 变量 | 作用 |
| --- | --- |
| `WHISPER_MODEL` | 启动模型（默认 `base`）。 |
| `WHISPER_DEVICE` | 首选设备（`auto`、`cpu`、`cuda`）。 |
| `WHISPER_COMPUTE_TYPE` | 首选计算类型（`auto`、`int8`、`float16` 等）。 |
| `WHISPER_CPU_THREADS` | CPU 工作线程数（封顶到逻辑核心数）。 |
| `VOICECODE_CONFIG_FILE` | 覆盖配置文件路径。 |
| `VOICECODE_STATIC_DIR` | 覆盖静态界面目录。 |
| `VOICECODE_RUNTIME_DIR` | 覆盖运行目录（模型/依赖/缓存）。 |
| `VOICECODE_MODEL_DIR` | 覆盖模型下载/缓存根目录。 |
| `VOICECODE_OFFLINE` | `1` = 仅使用本地缓存模型。 |
| `VOICECODE_SKIP_MODEL_LOAD` | `1` = 启动时不加载模型。 |
| `VOICECODE_SKIP_WARMUP` | `1` = 跳过加载后预热。 |
| `VOICECODE_TRANSCRIBE_TIMEOUT` | 转写看门狗超时（秒，默认 120）。 |
| `VOICECODE_API_TOKEN` / `VOICECODE_DISABLE_API_TOKEN` | 覆盖或禁用本地 API 令牌。 |
| `PORT` | HTTP 端口（默认 7788）。 |
| `HF_ENDPOINT` | 显式指定 Hugging Face 端点。 |
| `HF_HUB_ETAG_TIMEOUT` / `HF_HUB_DOWNLOAD_TIMEOUT` | HF 元数据/下载超时。 |
| `HF_HUB_DISABLE_XET` | 禁用 Xet/CAS 传输（安装包默认禁用）。 |
| `VOICECODE_DEP_DIR` | 隔离依赖安装目录。 |
| `VOICECODE_LOG_LEVEL` | 日志级别（默认 `INFO`）。 |

## 性能

- NVIDIA GPU（6GB+）：用 `float16`；按语言选 `large-v3-turbo`/`distil-large-v3.5` 或 `kotoba`。
- 低显存 GPU：用 `small`/`base`；显存不足时应用会自动回退 CPU int8。
- CPU：用 `int8`；可调 `WHISPER_CPU_THREADS`；优先 `base`/`tiny` + 预设 `fast`。
- 若 GPU 转写挂起或失败，VoiceCode 会自动重载模型到 CPU int8（看门狗超时默认 120 秒，可用 `VOICECODE_TRANSCRIBE_TIMEOUT` 调整）。

## 相关文档

- [API 参考](API.md)
- [配置说明](CONFIGURATION.md)
- [故障排查](TROUBLESHOOTING.md)
- [Windows 安装程序](WINDOWS_INSTALLER.md)