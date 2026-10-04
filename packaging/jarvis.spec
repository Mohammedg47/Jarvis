# PyInstaller spec: builds dist\Jarvis\Jarvis.exe (a windowed app, no console).
import os
# Run from the repo root: .venv\Scripts\pyinstaller packaging\jarvis.spec --noconfirm
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = [
    ("../jarvis/llm/prompts/*.md", "jarvis/llm/prompts"),
    ("../jarvis/ui/skins/noto/*", "jarvis/ui/skins/noto"),
]
binaries = []
hiddenimports = ["pycaw", "comtypes", "keyboard"]

# Packages that load data files, plugins or native libraries at run time.
for package in ("openwakeword", "onnxruntime", "sounddevice", "ddgs", "elevenlabs", "mss"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden
datas += collect_data_files("googleapiclient")  # API discovery documents

a = Analysis(
    ["launcher.py"],
    pathex=[os.path.abspath(os.path.join(SPECPATH, ".."))],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "ruff"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Jarvis",
    console=False,  # no terminal window: the Qt app is the interface
)
coll = COLLECT(exe, a.binaries, a.datas, name="Jarvis")
