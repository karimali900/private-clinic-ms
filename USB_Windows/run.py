#!/usr/bin/env python3
import os, sys, json, subprocess, venv, webbrowser, threading, time, socket

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def eprint(msg): print(msg, file=sys.stderr)

def banner():
    print()
    print("=" * 55)
    print("  Private Clinic — Obstetrics Management")
    print("  Maternity Care · Antenatal Visits · Follow-ups")
    print("=" * 55)

def read_config():
    import argparse
    p = os.path.join(SCRIPT_DIR, "config.json")
    config = {}
    if os.path.exists(p):
        try:
            with open(p) as f: config = json.load(f)
        except: pass
    parser = argparse.ArgumentParser()
    default_port = config.get("port", int(os.getenv("PORT", "5000")))
    parser.add_argument("--port", type=int, default=default_port)
    args, _ = parser.parse_known_args()
    config["port"] = args.port
    return config

def find_free_port(start):
    for p in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', p)) != 0: return p
    return start

def check_python():
    if sys.version_info < (3, 8):
        banner()
        eprint("\n  [ERROR] Python 3.8 or newer required")
        eprint(f"  Found: Python {sys.version_info.major}.{sys.version_info.minor}")
        eprint("  Download: https://www.python.org/downloads/\n")
        sys.exit(1)

def is_venv():
    return sys.prefix != sys.base_prefix

def venv_python_path(venv_dir):
    return os.path.join(venv_dir, 'Scripts', 'python.exe') if sys.platform == 'win32' \
        else os.path.join(venv_dir, 'bin', 'python3')

def setup_venv():
    banner()
    print("\n  [1/2] Setting up environment...")
    venv_dir = os.path.join(SCRIPT_DIR, '.venv')
    flag = os.path.join(venv_dir, '.installed')
    vp = venv_python_path(venv_dir)

    if not os.path.exists(venv_dir):
        print("  [ .. ] Creating virtual environment...")
        venv.create(venv_dir, with_pip=True)
        print("  [OK]  Virtual environment created.")
    else:
        print("  [OK]  Virtual environment found.")

    req = os.path.join(SCRIPT_DIR, 'requirements.txt')
    if os.path.exists(req) and not os.path.exists(flag):
        print("  [ .. ] Installing dependencies (first run)...\n")
        sys.stdout.flush()
        r = subprocess.run([vp, '-m', 'pip', 'install', '-r', req, '--disable-pip-version-check', '-q'])
        if r.returncode == 0:
            with open(flag, 'w') as f: f.write('done')
            print("  [OK]  Dependencies installed.")
        else:
            eprint("  [WARN] Some packages failed to install.")
            eprint("  Trying to start anyway...")

    return vp

def start_server(port):
    url = f"http://localhost:{port}/dashboard"
    print(f"\n  Opening: {url}")
    print("  Press Ctrl+C to stop\n")

    def open_browser():
        time.sleep(2)
        try: webbrowser.open(url)
        except: pass
    threading.Thread(target=open_browser, daemon=True).start()

    os.chdir(SCRIPT_DIR)
    import uvicorn
    try:
        uvicorn.run("Cloud_API:app", host="0.0.0.0", port=port, log_level="info")
    except OSError as e:
        eprint(f"\n  [ERROR] {e}")
        eprint("  Try a different port in config.json\n")
        input("  Press Enter to exit...")
    except KeyboardInterrupt:
        print("\n  Server stopped.")

if __name__ == '__main__':
    check_python()

    if not is_venv():
        vp = setup_venv()
        print(f"  [INFO] Starting application...")
        os.execl(vp, vp, os.path.abspath(__file__), *sys.argv[1:])

    config = read_config()
    port = find_free_port(config.get("port", int(os.getenv("PORT", "5000"))))
    configured = config.get("port", 5000)
    if port != configured:
        print(f"\n  [INFO] Port {configured} in use, using {port}")
        print(f"  [INFO] Update config.json to {port} for persistence")

    banner()
    print("\n  [OK]  Environment ready")
    start_server(port)
