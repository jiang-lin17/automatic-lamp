@echo off
REM ========================================================
REM  automatic-lamp · 一键打包 Windows exe
REM  用法：双击本文件 或 命令行执行 build_exe.bat
REM  产物：dist/automatic-lamp.exe（单文件，双击即运行）
REM ========================================================

echo.
echo 🏮 automatic-lamp · 打包脚本
echo ========================================================

REM 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 安装 PyInstaller（如果没装）
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo 📦 安装 PyInstaller...
    pip install pyinstaller
)

REM 安装项目依赖
echo 📦 安装项目依赖...
pip install -r requirements.txt

REM 清理旧产物
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 打包（单文件 + 无黑框）
echo 🔨 开始打包...
pyinstaller --noconfirm --onefile --windowed ^
    --name "automatic-lamp" ^
    --collect-submodules src ^
    --collect-submodules reportlab ^
    gui_config.py

if %errorlevel% neq 0 (
    echo ❌ 打包失败
    pause
    exit /b 1
)

echo.
echo ✅ 打包完成！产物在 dist\automatic-lamp.exe
echo.
echo 📂 可以直接双击运行 dist\automatic-lamp.exe
echo    或把它拷到任何 Windows 电脑上双击运行
echo.
pause
