"""
Music Player — 打包脚本
执行: python build.py
输出: dist/Music Player Setup.exe (安装包)
"""
import os
import sys
import subprocess
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "Music Player"
APP_ICON = os.path.join(PROJECT_DIR, "app_icon.ico")
MAIN_SCRIPT = os.path.join(PROJECT_DIR, "main.py")

# ---- 确保依赖已安装 ----
print("[1/5] 检查依赖...")
deps = ["PyQt5", "pygame", "yt-dlp", "mutagen", "requests", "pyinstaller"]
for dep in deps:
    try:
        __import__(dep.replace("-", "_"))
    except ImportError:
        print(f"  安装 {dep}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

# ---- 生成图标 ----
print("[2/5] 确保程序图标...")
if not os.path.exists(APP_ICON):
    # Regenerate icon if missing
    from PIL import Image, ImageDraw
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Mushroom stem
    draw.rounded_rectangle(
        [(size*0.30, size*0.55), (size*0.70, size*0.82)],
        radius=15, fill=(245, 235, 200, 255))
    # Red cap
    draw.ellipse(
        [(size*0.08, size*0.05), (size*0.92, size*0.66)],
        fill=(220, 30, 30, 255))
    draw.rectangle(
        [(size*0.08, size*0.60), (size*0.92, size*0.70)],
        fill=(220, 30, 30, 255))
    # White spots
    for cx, cy, r in [(0.35,0.22,0.07),(0.65,0.28,0.08),(0.50,0.42,0.06)]:
        x0, y0 = (cx-r)*size, (cy-r)*size
        x1, y1 = (cx+r)*size, (cy+r)*size
        draw.ellipse([(x0,y0),(x1,y1)], fill=(255,255,255,240))
    # Eyes
    for ex in [0.38, 0.62]:
        draw.ellipse([(ex*size-10, size*0.52-6), (ex*size+10, size*0.52+12)], fill=(30,30,30,255))
        draw.ellipse([(ex*size-4, size*0.52-2), (ex*size+2, size*0.52+6)], fill=(255,255,255,200))
    img.save(APP_ICON, format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])

# ---- 清理旧构建 ----
print("[3/5] 清理旧文件...")
for d in ["build", "dist"]:
    path = os.path.join(PROJECT_DIR, d)
    if os.path.exists(path):
        shutil.rmtree(path)

# ---- PyInstaller 构建 ----
print("[4/5] 打包程序...")
pyinstaller_args = [
    sys.executable, "-m", "PyInstaller",
    "--name", APP_NAME,
    "--icon", APP_ICON,
    "--windowed",            # 无控制台窗口
    "--onedir",              # 目录模式 — 不解压到TEMP，所有文件在安装目录
    "--add-data", f"ui{os.pathsep}ui",
    "--add-data", f"engine{os.pathsep}engine",
    "--add-data", f"models{os.pathsep}models",
    "--add-data", f"utils{os.pathsep}utils",
    "--hidden-import", "PyQt5.QtCore",
    "--hidden-import", "PyQt5.QtGui",
    "--hidden-import", "PyQt5.QtWidgets",
    "--hidden-import", "pygame",
    "--hidden-import", "mutagen",
    "--hidden-import", "requests",
    "--clean",
    "--noconfirm",
    MAIN_SCRIPT,
]

result = subprocess.run(pyinstaller_args, cwd=PROJECT_DIR)
if result.returncode != 0:
    print("打包失败!")
    sys.exit(1)

# ---- 创建 NSIS 安装包 ----
print("[5/5] 生成安装包...")
dist_dir = os.path.join(PROJECT_DIR, "dist")
app_dir = os.path.join(dist_dir, APP_NAME)  # onedir output folder
exe_path = os.path.join(app_dir, f"{APP_NAME}.exe")

# 预创建 data/downloads 目录
data_dir = os.path.join(app_dir, "data", "downloads")
os.makedirs(data_dir, exist_ok=True)

# 生成 NSIS 安装脚本 — 安装到可写目录，无需管理员权限
nsi_content = f'''
; Music Player NSIS Installer Script
Unicode true
!include "MUI2.nsh"

Name "{APP_NAME}"
OutFile "{dist_dir}\\{APP_NAME} Setup.exe"
InstallDir "$LOCALAPPDATA\\{APP_NAME}"
RequestExecutionLevel user

!define MUI_ICON "{APP_ICON}"
!define MUI_UNICON "{APP_ICON}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "{app_dir}\\*"
    CreateShortCut "$DESKTOP\\{APP_NAME}.lnk" "$INSTDIR\\{APP_NAME}.exe"
    CreateDirectory "$SMPROGRAMS\\{APP_NAME}"
    CreateShortCut "$SMPROGRAMS\\{APP_NAME}\\{APP_NAME}.lnk" "$INSTDIR\\{APP_NAME}.exe"
    CreateShortCut "$SMPROGRAMS\\{APP_NAME}\\卸载.lnk" "$INSTDIR\\Uninstall.exe"
    WriteUninstaller "$INSTDIR\\Uninstall.exe"
SectionEnd

Section "Uninstall"
    RMDir /r "$INSTDIR\\data"
    Delete "$INSTDIR\\{APP_NAME}.exe"
    Delete "$INSTDIR\\*.*"
    Delete "$INSTDIR\\Uninstall.exe"
    Delete "$DESKTOP\\{APP_NAME}.lnk"
    Delete "$SMPROGRAMS\\{APP_NAME}\\*.lnk"
    RMDir "$SMPROGRAMS\\{APP_NAME}"
    RMDir "$INSTDIR"
SectionEnd
'''

nsi_path = os.path.join(dist_dir, "setup.nsi")
with open(nsi_path, "w", encoding="utf-8") as f:
    f.write(nsi_content)

# 尝试调用 makensis
nsis_exe = r"C:\Program Files (x86)\NSIS\makensis.exe"
if os.path.exists(nsis_exe):
    subprocess.run([nsis_exe, nsi_path], cwd=dist_dir)
    setup_exe = os.path.join(dist_dir, f"{APP_NAME} Setup.exe")
    if os.path.exists(setup_exe):
        print(f"\n✓ 安装包已生成: {setup_exe}")
    else:
        print(f"\n⚠ NSIS 构建失败，请手动安装 NSIS")
        print(f"  程序目录: {app_dir}")
else:
    print(f"\n⚠ 未找到 NSIS (makensis.exe)，跳过安装包生成")
    print(f"  程序目录: {app_dir}")
    print(f"  可直接运行: {exe_path}")
    print(f"  如需安装包，请安装 NSIS: https://nsis.sourceforge.io/")

print(f"\n===== 打包完成 =====")
print(f"  安装目录: %LOCALAPPDATA%\\{APP_NAME}\\")
print(f"  数据目录: %LOCALAPPDATA%\\{APP_NAME}\\data\\")
print(f"  下载目录: %LOCALAPPDATA%\\{APP_NAME}\\data\\downloads\\")
