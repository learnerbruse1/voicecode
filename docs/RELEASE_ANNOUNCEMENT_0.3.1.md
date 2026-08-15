# VoiceCode v0.3.1 发布说明

**发布日期：2026-08-10** ｜ **版本：v0.3.1** ｜ **许可：MIT**

VoiceCode 是一款**本地优先**的桌面语音转文字（口述）软件：录制麦克风音频 → 本机实时转写 → 自动输入到当前应用。支持全局「按住说话」快捷键、多语言（中/英/日）、离线使用。所有音频处理都在本地完成，不上传云端。

## 下载

**Windows x64 安装程序**

- 文件：`VoiceCode-v0.3.1-Windows-x64-Setup.exe`
- 大小：`125,338,121` 字节（约 119.5 MB）
- SHA-256：`EC5878FDDFDA2970459FB184BD57788CEB00A0C3305AAFC3E024EB7E7CD570AA`
- 下载地址：`<粘贴你的下载链接>`

> ⚠️ **重要提示**
> - 本构建**尚未进行 Authenticode 代码签名**，Windows 可能显示 SmartScreen /「未知发布者」提示。签名后文件大小与哈希会变化，请以实际文件重新计算。
> - 安装包**不内置模型**：首次使用时需联网下载所选模型（官方端点不可达时自动切换到镜像）。
> - 系统要求：Windows 10/11 x64；转写可选 NVIDIA GPU（CUDA）或纯 CPU。

## 本版更新内容

### 🔧 稳定性（重点）
- 修复 **GPU 转写失败/卡死后录音按钮与应用整体冻结**的问题：转写改为串行工作线程 + 120 秒看门狗超时；原生推理期间不再长期持有模型锁；出错或超时自动**弃用坏模型并回退 CPU int8**，无需重启即可恢复。
- 模型恢复**粘滞到 CPU**：避免 CUDA 机器在 GPU 连续失败后反复切回坏模型；预热超时即标记坏模型、任意推理异常都会触发恢复。
- 关闭「处理中」遮罩会中止在途请求并复位界面，按钮不再卡死。

### 🛡️ 健壮性
- 模型预热（warm-up）有界（30 秒）且不持锁，启动/切换模型不再可能卡死。
- 前端状态/统计/实时草稿轮询增加超时保护。
- 转写失败日志从 debug 提升为 warning，便于排查。

### 💻 兼容性
- `WHISPER_CPU_THREADS` 封顶到逻辑核心数，`cpu_count()` 异常安全兜底。
- 首启推荐模型按显存动态选择（低显存 GPU 推荐 `base`）。
- 支持无 NVIDIA GPU 的机器自动走 CPU int8；低显存自动回退。

### ✨ 新功能与模型
- 升级 **faster-whisper 1.2.x**（Silero VAD v6）。
- 新增日语特化模型 **Kotoba Whisper v2.0**（日语识别比 large-v3 更准、体积约一半）。
- 新增高速模型 **Distil Whisper Large v3.5**（接近 large-v3 精度、约 6 倍速度）。
- 模型选择按钮新增**三语提示**（英文 / 简体中文 / 日语）。

## 支持的模型

| 模型 | 大小 | 最低/推荐显存 | 适用场景 |
| --- | --- | --- | --- |
| tiny | ~75 MB | 1 / 2 GB | 最快，低配硬件 |
| base | ~150 MB | 1 / 2 GB | CPU 日常听写默认 |
| small | ~500 MB | 2 / 4 GB | 均衡之选 |
| medium | ~1.5 GB | 5 / 6 GB | 高精度 |
| large-v3 | ~3 GB | 10 / 12 GB | 多语言最高精度 |
| large-v3-turbo | ~3 GB | 6 / 8 GB | 最新官方，快且准 |
| distil-large-v3 | ~1.5 GB | 6 / 8 GB | 高速蒸馏 |
| distil-whisper/distil-large-v3.5-ct2 | ~1.5 GB | 6 / 8 GB | 英语快而准 |
| kotoba-tech/kotoba-whisper-v2.0-faster | ~1.5 GB | 6 / 8 GB | 日语特化 |

## 快速上手

1. 安装并启动，按向导选择语言、模型与硬件。
2. 按住默认快捷键 `Alt+Z` 说话，松开即自动输入文字。
3. 想更快？设置里把「解码预设」选为 **Fast**，并关闭「实时草稿」；GPU 不稳定时把设备设为 **CPU**。

## 文档

- [用户指南（功能与设置详解）](GUIDE.md) ｜ [使用指南（中文）](GUIDE_zh.md) ｜ [ユーザーガイド（日本語）](GUIDE_ja.md)
- [API 参考](API.md) ｜ [故障排查](TROUBLESHOOTING.md) ｜ [更新日志](../CHANGELOG.md)

---
# VoiceCode v0.3.1 Release Notes (English)

**Release date: 2026-08-10** ｜ **Version: v0.3.1** ｜ **License: MIT**

VoiceCode is a **local-first** desktop speech-to-text app: record your microphone, transcribe on-device in real time, and type the result into the active app. It supports a global push-to-talk hotkey, multilingual UI (EN / 中文 / 日本語), and offline use. All audio stays on your machine.

## Download

**Windows x64 Installer**

- File: `VoiceCode-v0.3.1-Windows-x64-Setup.exe`
- Size: `125,338,121` bytes (~119.5 MB)
- SHA-256: `EC5878FDDFDA2970459FB184BD57788CEB00A0C3305AAFC3E024EB7E7CD570AA`
- URL: `<paste your download link>`

> ⚠️ **Note**: this build is **not Authenticode code-signed** yet — Windows may show a SmartScreen / "Unknown publisher" prompt. The installer does **not** bundle models; the first use downloads the selected model (a mirror is used automatically if the official endpoint is unreachable). Requirements: Windows 10/11 x64; optional NVIDIA GPU (CUDA) or CPU-only.

## What's new

### Stability
- Fixed the recording/UI freeze after a failed or hung GPU transcription: serial transcription worker + 120 s watchdog, the model lock is never held across native inference, and failed/timed-out models are discarded and reloaded on CPU int8 automatically — no restart needed.
- Model recovery is **sticky to CPU** (no oscillating back into a poisoned GPU model); a timed-out warm-up marks the model as failed, and any inference exception triggers recovery.
- Closing the "processing" overlay aborts the in-flight request and resets the UI.

### Robustness
- Bounded model warm-up (30 s, no lock held across the native call).
- Frontend status/stats/draft polling now use bounded request timeouts.
- Failed partial transcriptions are logged at warning level.

### Compatibility
- `WHISPER_CPU_THREADS` is capped to logical cores; `cpu_count()` failures fall back safely.
- First-run model recommendation is VRAM-aware (low-VRAM GPUs get `base`).
- CPU-only machines and low-VRAM GPUs fall back automatically.

### Features & models
- Upgraded **faster-whisper 1.2.x** (Silero VAD v6).
- New Japanese-optimized **Kotoba Whisper v2.0** (more accurate than large-v3 on Japanese, half the size).
- New fast **Distil Whisper Large v3.5** (near large-v3 accuracy at ~6x speed).
- Localized hints on every model-selection button (EN / 中文 / 日本語).

## Quick start

1. Install, launch, and follow the first-run guide (language, model, hardware).
2. Hold `Alt+Z`, speak, release — the text is typed automatically.
3. For speed: set the decode preset to **Fast** and disable live drafts; if GPU is unstable, set the device to **CPU**.

## Docs

- [User Guide](GUIDE.md) ｜ [使用指南（中文）](GUIDE_zh.md) ｜ [ユーザーガイド（日本語）](GUIDE_ja.md)
- [API](API.md) ｜ [Troubleshooting](TROUBLESHOOTING.md) ｜ [Changelog](../CHANGELOG.md)