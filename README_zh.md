# VoiceCode

![VoiceCode 图标](assets/voicecode-icon.png)

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

**当前版本：v0.3.1**

VoiceCode 是一款本地优先的桌面语音转文字工具，适合编程、写作和提示词输入。它使用 faster-whisper / CTranslate2 在本机完成转写，并可通过全局按住说话快捷键把结果输入到当前应用。

## 使用指南

每个功能与设置的详细说明，请参阅[使用指南](docs/GUIDE_zh.md)（简体中文）、[User Guide](docs/GUIDE.md)（English）和[ユーザーガイド](docs/GUIDE_ja.md)（日本語）。

## 主要功能

- Windows 桌面界面，支持英语、简体中文和日语实时切换。
- 首次启动向导可配置界面语言、转写语言、麦克风、模型和硬件。
- 自动检测 NVIDIA CUDA，失败时安全回退到 CPU int8。
- 模型、可选依赖和下载缓存集中保存在安装目录的 `runtime` 文件夹。
- 支持模型缓存管理、转写历史、诊断导出和可配置扩展；模型下载会显示已下载大小、预计大小、速度、耗时和停滞状态。
- 支持日语特化的 Kotoba Whisper v2.0 模型（日语识别比 large-v3 更准、体积约一半）和高速的 Distil Whisper Large v3.5 模型；每个模型选择按钮都有本地化提示。
- 本地 API 仅绑定 `127.0.0.1`，并具有请求令牌和 Host/Origin 防护。
- 录音时实时显示部分转写草稿，松键后定稿。
- 剪贴板上屏：转写文本通过剪贴板粘贴进当前应用，失败自动回退模拟按键，延迟可配置。
- 解码预设：快速 / 均衡 / 高准确，或自定义 beam 与「结合上文」。
- 转写历史自动裁剪到配置的上限。
- Windows 单实例运行；重复启动会唤醒已有窗口，不会争抢端口。
- 内置扫雷提供初级、中级和高级三种难度；安装包不包含纸牌游戏内容。

## Windows 安装

普通用户推荐使用：

```text
VoiceCode-v0.3.1-Windows-x64-Setup.exe
```

安装向导允许自主选择安装目录。默认路径为：

```text
%LOCALAPPDATA%\Programs\VoiceCode
```

安装程序包含核心依赖和独立的 Python/pip 运行时，用户无需另外安装 Python。安装后的重要目录：

```text
<安装目录>\VoiceCode.exe
<安装目录>\runtime\python
<安装目录>\runtime\dependencies
<安装目录>\runtime\models
<安装目录>\runtime\cache
```

后续从应用中安装的可选依赖、Whisper 模型以及 Hugging Face/pip 缓存都会保存在所选安装目录中。配置、日志和历史记录仍保存在当前 Windows 用户的可写配置目录中。卸载会删除安装器管理的程序文件，但会保留用户下载的模型和其他运行时数据，便于重装后继续使用；如需彻底删除，请在卸载后手动删除残留的 `runtime` 目录。安装版静态界面只包含扫雷及其 `games.js` 资源。

v0.2.0 安装版已于 **2026 年 7 月 24 日**完成完整功能验证，并于 **2026 年 7 月 25 日**重新构建和验证仅保留扫雷的安装包；本次复验覆盖自定义路径安装、三语资源、嵌入式 pip、纸牌内容清理和卸载，原完整验证还覆盖覆盖安装、单实例、缓存模型、转写与重装。详见[最终验证记录](docs/RELEASE_VALIDATION_0.2.0.md)。当前本地验证产物尚未签名，公开发布前仍需完成代码签名与签名后复验。

## 从源码运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[runtime,dev]"
.\.venv\Scripts\python.exe -m voicecode
```

## 语言切换

可在首次启动向导或“设置”页面中切换英语、中文和日语。v0.2.0 修复了中日文显示为问号，以及从中日文切回英文不生效的问题。

翻译文件位于：

```text
src/voicecode/static/i18n/en.json
src/voicecode/static/i18n/zh.json
src/voicecode/static/i18n/ja.json
```

修改静态资源后必须运行：

```powershell
python -X utf8 tools/sync_static.py
```

## 数据位置

- 配置：`%APPDATA%\VoiceCode\config.json`
- 日志：`%APPDATA%\VoiceCode\logs\voicecode.log`
- 历史：配置目录中的 `history.jsonl`
- 安装版模型与依赖：`<安装目录>\runtime`

## 构建安装程序

需要 Windows x64、CPython 3.12 x64 和 Inno Setup 6：

```powershell
python -m pip install -e ".[runtime,dev]"
python -X utf8 tools/generate_icon.py
python -X utf8 packaging/windows/build_windows_installer.py
```

构建脚本会在进入耗时的 PyInstaller 阶段前下载并校验嵌入式 Python 与 `get-pip.py`，下载缓存保存在 `build/windows/downloads/`，失败时会重试并使用原子临时文件。

输出目录：

```text
dist/windows/installer/
```

可在一次性测试环境中执行自动安装检查：

```powershell
python -X utf8 packaging/windows/verify_windows_installer.py `
  --installer dist/windows/installer/VoiceCode-v0.3.1-Windows-x64-Setup.exe `
  --install-dir "$env:TEMP\VoiceCode-installer-smoke" `
  --version 0.3.1 `
  --skip-launch `
  --uninstall
```

详细说明见 [Windows 安装程序构建](docs/WINDOWS_INSTALLER.md)。

## 发布前检查

```powershell
python -m ruff format --check app.py main.py tests src/voicecode packaging/windows tools
python -m ruff check app.py main.py tests src/voicecode packaging/windows tools
python -m mypy app.py main.py src/voicecode
python -X utf8 -m pytest -q
python -X utf8 tools/sync_static.py --check
```

## 文档

- [API](docs/API.md)
- [架构](docs/ARCHITECTURE.md)
- [配置](docs/CONFIGURATION.md)
- [开发指南](docs/DEVELOPMENT.md)
- [打包指南](docs/PACKAGING.md)
- [发布流程](docs/RELEASING.md)
- [Windows 安装程序](docs/WINDOWS_INSTALLER.md)
- [v0.2.0 最终验证记录](docs/RELEASE_VALIDATION_0.2.0.md)
- [故障排查](docs/TROUBLESHOOTING.md)

## 许可证

MIT，详见 [LICENSE](LICENSE)。
## 最新桌面端改进

VoiceCode 现在会在显示“加载”前严格验证模型缓存，并直接从已验证的本地快照加载；不完整下载会保持“部分缓存”状态并继续下载。错误详情支持可靠复制，启动时可清理占用本地端口的无窗口残留进程。顶部栏仅显示 CPU、GPU、内存摘要，完整硬件信息移动到设置页。扫雷新增高级模式（16 × 30，99 雷），新增界面文字均适配英文、简体中文和日文。此外，faster-whisper 升级到 1.2.x（Silero VAD v6），新增日语特化的 Kotoba Whisper v2.0 模型和高速的 Distil Whisper Large v3.5 模型，并在模型选择按钮上提供本地化提示。

本阶段还新增：录音时实时部分转写预览；基于剪贴板的上屏（含模拟按键回退与可配置延迟）；解码预设（快速 / 均衡 / 高准确 / 自定义）；历史自动裁剪；自适应状态轮询；依赖状态与 Hugging Face 端点的进程内缓存；以及模型加载后的 best-effort 预热（可用 `VOICECODE_SKIP_WARMUP` 关闭）。
