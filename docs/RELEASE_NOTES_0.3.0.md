# VoiceCode v0.3.0 — 新模型与 faster-whisper 升级

发布日期：**2026 年 8 月 10 日**

VoiceCode v0.3.0 在 v0.2.0 安装版的基础上，升级了转写引擎，新增两个高质量开源模型，并为模型选择按钮增加了三语提示。

## 下载

### Windows x64 安装程序

`VoiceCode-v0.3.0-Windows-x64-Setup.exe`

- 文件大小：`125,328,173` 字节
- SHA-256：

```text
0D385C1156D8719B82F48C79D6CFA7B8C48B393E26A7EFDE07099F20D2F7DC35
```

> **重要提示：** 当前构建尚未进行 Authenticode 代码签名，Windows 可能显示 SmartScreen 或“未知发布者”提示。正式发布前签名后，文件大小和 SHA-256 会变化，请重新生成校验值。

## 主要更新

### 转写引擎

- faster-whisper 升级到 1.2.x（Silero VAD v6、distil-large-v3.5 内置别名等改进）。

### 新增模型

- 日语特化 `kotoba-tech/kotoba-whisper-v2.0-faster`：日语识别比 large-v3 更准、体积约一半。
- 高速 `distil-whisper/distil-large-v3.5-ct2`：接近 large-v3 精度，速度约为 6 倍。

### 界面

- 模型选择按钮（设置页、首次启动向导、Models 页）新增本地化提示（英语 / 简体中文 / 日语）。

## 安装与验证

- 沿用 v0.2.0 的 Windows x64 安装程序：可选安装目录、内置 Python/pip，模型与可选依赖统一存放在 `<安装目录>\runtime`。
- 自动化验证通过：12 个必需文件、嵌入式 pip 26.2.1、三语目录各 394 条、扫雷载荷、静默卸载。
- 手动冒烟通过：应用启动、`/health` PID 校验、`/models` 返回全部 9 个模型、tiny 模型 CPU int8 下载并初始化到 ready、转写接口返回 200。
- 本构建未签名；正式发布仍需时间戳代码签名与签名后复验。