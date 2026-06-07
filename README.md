# VoiceCode 🎙️

> 本地语音转文字工具，专为 vibe coding 设计。完全离线，支持中英文，低资源占用。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## ✨ 功能特性

- **🔒 完全本地** — 无需联网，数据不上云，隐私安全
- **🌐 中英双语** — 支持中文、英文及自动语言检测
- **⚡ GPU 加速** — 自动检测 NVIDIA 显卡，使用 float16 推理；无 GPU 时自动回退 CPU
- **🖥️ 原生窗口** — 基于 pywebview，直接弹出桌面窗口，无需浏览器
- **⌨️ 全局热键** — 在任意窗口（VS Code、浏览器等）按住热键录音，松开自动识别并输入到光标处
- **📊 资源监控** — 实时显示 CPU/GPU/内存占用
- **🎛️ 可自定义** — 模型大小、语言、字体、结果模式、窗口置顶均可配置
- **💾 配置持久化** — 所有设置自动保存，重启后恢复

---

## 📸 界面预览

```
┌─────────────────────────────────────────────┐
│ VoiceCode                           就绪 ●  │
│ 推理: CPU (int8) · 模型: base · CPU: 12%    │
├─────────────────────────────────────────────┤
│ 模型: Base(推荐)  语言: 中文  字号: 中       │
│ 结果: 追加        置顶: 关                   │
│ 全局键: [Alt+Z]  [点击设置]                  │
├─────────────────────────────────────────────┤
│    🎤                                        │
│  按住 Space 开始录音                         │
│  此窗口内: 按住Space 其他窗口: 全局快捷键    │
├─────────────────────────────────────────────┤
│ 转录结果              [清空] [复制]          │
│                                             │
│ 你的语音内容会显示在这里...                  │
└─────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| Python | 3.10 或更高 |
| 内存 | ≥ 4GB（推荐 8GB） |
| 磁盘 | ≥ 500MB（模型文件） |
| GPU（可选） | NVIDIA 显卡 + CUDA 12.x（有则自动加速） |
| 麦克风 | 任意系统麦克风 |

### 一键安装

```bat
# 1. 克隆或下载项目
git clone https://github.com/your-username/voicecode.git
cd voicecode

# 2. 安装（仅首次，需几分钟）
双击 setup.bat

# 3. 启动
双击 run.bat
```

首次启动会自动从国内镜像（hf-mirror.com）下载 Whisper 模型，约 150MB。

---

## 📖 使用指南

### 基本录音

| 操作 | 效果 |
|------|------|
| 按住 `Space` | 开始录音（窗口内） |
| 松开 `Space` | 停止并识别 |
| 点击麦克风按钮 | 切换录音（鼠标操作） |

### 全局热键（在其他窗口使用）

在 VS Code、浏览器、文本编辑器等任意软件中：

1. 将光标放到目标位置
2. **按住** `Alt+Z`（默认）开始录音
3. **松开** `Alt+Z` 停止，识别结果自动输入到光标处

可在设置面板自定义热键，提供以下预设：
- `Alt+Z`（默认）
- `Alt+X`
- `Ctrl+Shift+R`
- `Ctrl+Alt+Space`
- 或点击「点击设置」自定义任意组合键

### 设置说明

| 设置项 | 说明 |
|--------|------|
| **模型** | 越大越准但越慢，推荐 Base |
| **语言** | 自动检测 / 中文 / 英文 |
| **字号** | 转录结果的显示字体大小 |
| **结果模式** | 追加（累计） / 替换（每次覆盖） |
| **置顶** | 窗口始终显示在其他软件上方 |

---

## 🤖 模型对比

| 模型 | 大小 | 速度 | 精度 | 适合场景 |
|------|------|------|------|----------|
| **Tiny** | ~75MB | 最快 | 一般 | 实时、低配机器 |
| **Base** | ~150MB | 快 ⭐推荐 | 好 | 日常使用 |
| **Small** | ~500MB | 中 | 很好 | 对准确率要求高 |
| **Medium** | ~1.5GB | 慢 | 最好 | 专业场合 |

---

## 🏗️ 项目结构

```
voicecode/
├── app.py              # Flask 后端 + Whisper 识别 + sounddevice 录音
├── main.py             # pywebview 窗口 + 全局热键（pynput）
├── requirements.txt    # Python 依赖
├── setup.bat           # 一键安装脚本
├── run.bat             # 启动快捷方式
├── config.json         # 用户配置（自动生成）
├── static/
│   └── index.html      # 前端 UI（纯 HTML/JS，无框架）
└── README.md
```

### 技术栈

| 组件 | 技术 |
|------|------|
| 语音识别 | [faster-whisper](https://github.com/SYSTRAN/faster-whisper)（OpenAI Whisper 的 4x 加速版） |
| Web 框架 | Flask + Waitress（生产级多线程 WSGI） |
| 桌面窗口 | [pywebview](https://pywebview.flowrl.com/)（WinForms + EdgeChromium） |
| 音频采集 | [sounddevice](https://python-sounddevice.readthedocs.io/)（PortAudio Python 绑定） |
| 全局热键 | [pynput](https://pynput.readthedocs.io/)（无需管理员权限） |
| GPU 推理 | CTranslate2（float16，自动检测） |

---

## 🔧 手动安装

```bash
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动
python main.py
```

---

## ❓ 常见问题

**Q: 首次启动很慢？**
A: 正在自动下载 Whisper 模型（Base 约 150MB），完成后后续启动很快。

**Q: 提示"请允许麦克风访问"？**
A: 点击 Windows 系统弹出的麦克风权限请求，允许即可。或在 Windows 设置 → 隐私 → 麦克风 中开启。

**Q: 全局热键不响应？**
A: 确认没有其他软件占用同一热键。可在设置面板更改热键。

**Q: 识别结果是繁体中文？**
A: 将语言设置为「中文」（而非「自动检测」），可引导模型输出简体。

**Q: GPU 没有被使用？**
A: 资源监控显示「推理: CPU」说明 CUDA 运行库缺失。安装 [CUDA Toolkit 12.x](https://developer.nvidia.com/cuda-downloads) 后重启。

**Q: 如何提高识别准确率？**
A: 切换到 Small 或 Medium 模型，在设置面板的「模型」下拉菜单中选择。

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) — 语音识别模型
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CTranslate2 加速推理
- [pywebview](https://github.com/r0x0r/pywebview) — Python 桌面 WebView
