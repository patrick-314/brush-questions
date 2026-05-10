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
        "佛脚刷题网页_半屏答题卡版",
        "web_quiz_app.py",
    ]
)
