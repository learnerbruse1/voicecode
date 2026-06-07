@echo off
chcp 65001 >/dev/null
echo ========================================
echo   VoiceCode - 本地语音转文字工具
echo ========================================
echo.

python --version >/dev/null 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist .venv (
    echo [1/3] 创建虚拟环境...
    python -m venv .venv
)

echo [2/3] 安装依赖（首次需要几分钟）...
.venv\Scripts\pip install -q --upgrade pip
.venv\Scripts\pip install -q -r requirements.txt

echo [3/3] 完成！
echo.
echo 运行方式：双击 run.bat 启动
echo 首次启动会自动下载 Whisper base 模型（约 150MB）
echo.
pause
