# -*- coding: utf-8 -*-
"""把静锚打包成单文件 Windows exe（无控制台窗口）。"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "comfort_anchor.py")
DIST = os.path.join(HERE, "dist")
BUILD = os.path.join(HERE, "build")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--onefile", "--windowed",
    "--name", "ComfortAnchor",
    "--distpath", DIST,
    "--workpath", BUILD,
    "--specpath", HERE,
    "--hidden-import", "PIL.Image",
    "--hidden-import", "PIL.ImageChops",
    "--hidden-import", "PIL.ImageDraw",
    "--hidden-import", "PIL.ImageFilter",
    "--hidden-import", "PIL.ImageFont",
    "--hidden-import", "PIL.ImageTk",
    "--hidden-import", "ca_config",
    "--hidden-import", "ca_render",
    "--hidden-import", "ca_win32",
    # 本工具只用 Pillow 的 Image/ImageChops/ImageDraw，以下为无关依赖
    "--exclude-module", "numpy",
    "--exclude-module", "psutil",
    "--exclude-module", "charset_normalizer",
    "--exclude-module", "requests",
    ENTRY,
]

print("Building:", " ".join(cmd))
result = subprocess.run(cmd, cwd=HERE)
if result.returncode != 0:
    print("Build FAILED with code", result.returncode)
    sys.exit(result.returncode)

exe = os.path.join(DIST, "ComfortAnchor.exe")
if not os.path.isfile(exe):
    print("Build finished but exe not found at", exe)
    sys.exit(1)

size_mb = os.path.getsize(exe) / (1024 * 1024)
print("OK ->", exe)
print("Size: %.1f MB" % size_mb)
print("")
print("Verify the packaged build with:")
print('  "%s" --check --out "%s"' % (exe, os.path.join(HERE, "check_exe.txt")))
