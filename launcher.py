import subprocess
import webbrowser
import time

subprocess.Popen([
    "streamlit",
    "run",
    "app.py",
    "--server.headless=true"
])

time.sleep(3)

webbrowser.open("http://localhost:8501")