import subprocess
import sys


subprocess.check_call(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "高通量刷题",
        "web_quiz_app.py",
    ]
)
