# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

VoiceCode 是一个本地优先的桌面语音转文字应用，面向编程、写作和提示词草稿场景。它通过麦克风录音，使用 `faster-whisper` / CTranslate2 在本地转写，并可通过全局按住说话热键把结果输入到当前应用。

## 主要特性

- 基于 Whisper 兼容模型的本地语音转文字。
- 自动检测 NVIDIA CUDA，并在 GPU 初始化或推理失败时安全回退到 CPU。
- 可配置推理设备：`auto`、`cpu`、`cuda`。
- 可配置计算精度：`auto`、`int8`、`float16`、`float32`、`int8_float16`。
- 面向 Windows、macOS、Linux 的标准 Python 开源项目结构。
- 本地 API 仅绑定 `127.0.0.1`。
- 使用 `pywebview` 提供桌面 UI，`pynput` 提供全局热键，`sounddevice` 采集麦克风。
- 提供 `/transcribe` 接口，便于文件上传、测试和外部集成。
- 配置、日志、历史记录都写入用户可写目录，不写入安装包目录。

## 安装运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m voicecode
```

Linux/macOS：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m voicecode
```

本仓库已移除一键安装脚本和生成的安装器产物，推荐使用标准 Python 虚拟环境和包管理流程。

## CPU / NVIDIA GPU 适配

默认策略：如果 CTranslate2 能检测到 CUDA 设备，则使用 `cuda/float16`；否则使用 `cpu/int8`。如果 CUDA 推理运行时失败，应用会自动回退到 `cpu/int8`，保证语音转文字功能仍可用。

常用环境变量：

| 变量 | 说明 |
| --- | --- |
| `WHISPER_MODEL` | 启动模型：`tiny`、`base`、`small`、`medium`、`large-v3`、`distil-large-v3` |
| `WHISPER_DEVICE` | 推理设备：`auto`、`cpu`、`cuda` |
| `WHISPER_COMPUTE_TYPE` | 计算精度：`auto`、`int8`、`float16`、`float32`、`int8_float16` |
| `WHISPER_CPU_THREADS` | CPU 推理线程数 |
| `VOICECODE_MODEL_DIR` | 模型缓存目录 |
| `VOICECODE_OFFLINE` | 只使用本地缓存模型 |
| `VOICECODE_SKIP_MODEL_LOAD` | 启动 UI 但跳过模型加载，适合预览和测试 |

建议：CPU 环境使用 `base` 或 `small`；NVIDIA GPU 环境可使用 `small`、`medium`、`large-v3` 或 `distil-large-v3`。

## 开发检查

```powershell
python -m ruff format --check app.py main.py tests src/voicecode
python -m ruff check app.py main.py tests src/voicecode
python -m mypy app.py main.py src/voicecode
python -X utf8 -m pytest -q
```

## API 与文档

接口说明见 [docs/API.md](docs/API.md)。架构说明见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，开发指南见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

## 许可证

MIT。详见 [LICENSE](LICENSE)。
