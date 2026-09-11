"""Stop only this project's Python app.py process; leave other apps alone."""
import sys
from pathlib import Path
import psutil

root = Path(__file__).resolve().parent
executables = {Path(sys.executable).resolve(), Path(sys._base_executable).resolve()}
stopped = []
for process in psutil.process_iter(['pid', 'exe', 'cmdline', 'cwd']):
    try:
        info = process.info
        if not info['cmdline'] or not info['cwd'] or not info['exe']:
            continue
        if Path(info['cwd']).resolve() != root or Path(info['exe']).resolve() not in executables:
            continue
        if not any(Path(arg).name in ('app.py', 'app_v2.py') for arg in info['cmdline'][1:]):
            continue
        process.terminate()
        process.wait(timeout=10)
        stopped.append(info['pid'])
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue
print('Stopped this project demo: ' + str(stopped) if stopped else 'No running demo for this project was found.')
