# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

VoiceCode 是一个本地离线运行的桌面语音转文字工具，适合在编程、写文档和日常输入场景中使用。它可以录制麦克风音频，使用本地 Whisper 模型转写文本，并通过全局快捷键把结果输入到当前应用。

## 主要功能

- 使用 `faster-whisper` 进行本地离线转录
- Windows 桌面界面，基于 `pywebview`
- 本地 Flask/Waitress API，仅绑定 `127.0.0.1`
- 支持全局按住说话快捷键
- 支持英文、简体中文、日语界面切换
- 支持自动检测、中文、英文、日语转录语言
- 麦克风设备选择和本地诊断面板
- 可选本地转录历史记录
- 普通、编程、Markdown、Prompt 文本后处理模式
- 通过 `VOICECODE_SKIP_MODEL_LOAD=1` 支持无模型预览
- PowerShell 和 cmd UTF-8 输出适配
- 日志、异常和 API 错误信息保持英文，方便跨语言排查
- 配置写入用户目录，不写入安装目录
- 支持 `python -m voicecode` 和 `voicecode` 命令入口

## 环境要求

- Windows 10/11 是主要支持目标
- Python 3.10 或更高版本
- 麦克风权限
- 可选 NVIDIA GPU 用于 CUDA 推理

## 快速开始

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

### Python 包方式

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\voicecode.exe
```

也可以运行：

```powershell
python -m voicecode
```

## 配置

默认配置路径：

- Windows：`%APPDATA%\VoiceCode\config.json`
- Linux/macOS：`$XDG_CONFIG_HOME/voicecode/config.json` 或 `~/.config/voicecode/config.json`

常用环境变量：

| 变量 | 作用 |
| --- | --- |
| `VOICECODE_CONFIG_FILE` | 覆盖配置文件路径 |
| `VOICECODE_STATIC_DIR` | 覆盖 Web UI 静态文件目录 |
| `VOICECODE_LOG_LEVEL` | 设置日志等级，例如 `DEBUG` |
| `PORT` | 设置本地 HTTP 端口，默认 `7788` |
| `WHISPER_MODEL` | 设置启动时加载的 Whisper 模型，默认 `base` |

## 隐私

VoiceCode 设计为本地运行。音频只发送到本机 `127.0.0.1` 上的本地服务，并由本地 Whisper 模型处理。

## 开发检查

```powershell
python -m pytest
python -m ruff check app.py main.py tests src/voicecode
python -m mypy app.py main.py src/voicecode
python -m pip wheel . --no-deps -w dist
```

## 许可证

MIT。详见 [LICENSE](LICENSE)。
