# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

VoiceCode 是一款本地离线运行的桌面语音转文字工具，适合编程、文档写作和日常输入。它会录制本机麦克风音频，使用本地 Whisper 模型转写文本，并可通过全局按住说话快捷键把结果输入到当前应用。

## 主要功能

- 使用 faster-whisper 进行本地离线转写
- 基于 pywebview 的 Windows 桌面界面
- 本地 Flask/Waitress API，仅绑定 127.0.0.1
- 全局按住说话快捷键
- 英文、简体中文、日文 UI 切换
- 转写语言支持自动检测、中文、英文、日文
- 支持无模型预览模式：VOICECODE_SKIP_MODEL_LOAD=1
- 普通文本、代码、Markdown、Prompt 后处理模式
- 可选本地转写历史、麦克风选择和诊断面板
- Windows 标准安装器，安装时可选择安装目录
- 打包版会把后续模型下载和缓存集中到安装目录下

## 普通用户安装

推荐使用 Windows 安装器：

~~~text
packaging/installer/Output/VoiceCode-0.1.0-windows-x86_64-setup.exe
~~~

双击安装器后，可在向导中选择安装路径。默认路径为：

~~~text
%LOCALAPPDATA%\Programs\VoiceCode
~~~

使用安装器时，用户不需要单独安装 Python。Python 运行时、Python 包和原生依赖都会放在安装目录中。未来 Hugging Face / faster-whisper 下载的模型和缓存会写入：

~~~text
<安装目录>\runtime\cache
<安装目录>\runtime\models
~~~

这样应用本体和大体积运行时文件都集中在同一个目录下，便于备份、迁移或删除。

## 开发运行

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

Python 包方式：

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\voicecode.exe
~~~

也可以运行：

~~~powershell
python -m voicecode
~~~

## 配置和运行时数据

- Windows 配置默认位置：%APPDATA%\VoiceCode\config.json
- Windows 日志默认位置：%APPDATA%\VoiceCode\logs\voicecode.log
- 转写历史默认位置：配置目录旁的 history.jsonl
- 打包版模型和下载缓存默认位置：<安装目录>\runtime

常用环境变量：VOICECODE_CONFIG_FILE、VOICECODE_STATIC_DIR、VOICECODE_RUNTIME_DIR、VOICECODE_MODEL_DIR、VOICECODE_LOG_FILE、VOICECODE_HISTORY_FILE、VOICECODE_SKIP_MODEL_LOAD、VOICECODE_ENABLE_TRAY、PORT、WHISPER_MODEL。

## 构建 Windows 安装器

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1
~~~

输出：

~~~text
packaging\installer\dist\VoiceCode\
packaging\installer\Output\VoiceCode-0.1.0-windows-x86_64-setup.exe
~~~

如果没有 Inno Setup，只构建 one-folder 应用：

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1 -SkipInno
~~~

## 最终发布验证

当前发布候选已通过：

- ruff format --check
- ruff check
- mypy
- pytest（35 passed）
- py_compile
- wheel 构建
- PyInstaller one-folder 构建
- Inno Setup 安装器构建
- 自定义目录静默安装/卸载 smoke test

API 输入校验已覆盖畸形 JSON、JSON null、非 object payload、布尔值伪装整数、非法热键修饰键、重复启动、模型重载竞态和录音取消顺序等边界。

## 隐私

VoiceCode 设计为本地运行。音频只发送到本机 127.0.0.1 上的本地服务，并由本地 Whisper 模型处理。转写历史、日志、配置和模型缓存均为本地文件，VoiceCode 不会主动上传它们。

## 许可证

MIT。详见 [LICENSE](LICENSE)。
