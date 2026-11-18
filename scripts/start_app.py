"""Start a detached local Streamlit server, then open the app when ready."""
import argparse
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:18502/'


def healthy():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(URL + '_stcore/health', timeout=1) as response:
            return response.status == 200 and response.read().strip() == b'ok'
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    process = None
    if not healthy():
        folder = ROOT / '.local_runtime'
        folder.mkdir(exist_ok=True)
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP |
                 subprocess.CREATE_BREAKAWAY_FROM_JOB) if sys.platform == 'win32' else 0
        command = [sys.executable, '-m', 'streamlit', 'run', str(ROOT/'app.py'),
                   '--server.address', '127.0.0.1', '--server.port', '18502',
                   '--server.headless', 'true', '--browser.gatherUsageStats', 'false',
                   '--server.runOnSave', 'true']
        with (folder/'server.log').open('ab') as log:
            process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, close_fds=True,
                creationflags=flags, start_new_session=sys.platform != 'win32')
        (folder/'server.pid').write_text(str(process.pid), encoding='ascii')
        deadline = time.monotonic()+30
        while not healthy():
            if process.poll() is not None or time.monotonic() >= deadline:
                raise SystemExit(f'App could not start. See: {folder / "server.log"}')
            time.sleep(.3)
    print(f'App ready: {URL}')
    if not args.no_browser:
        webbrowser.open(URL)


if __name__ == '__main__':
    main()
