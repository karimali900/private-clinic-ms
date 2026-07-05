#!/usr/bin/env python3
"""Fast entry point — creates venv on first run, starts uvicorn."""
import os, sys, json, subprocess, venv, webbrowser, threading, time, socket

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FLAG = os.path.join(SCRIPT_DIR, '.venv', '.installed')
VENV_DIR = os.path.join(SCRIPT_DIR, '.venv')

def eprint(msg): print(msg, file=sys.stderr)

def banner():
    print()
    print("=" * 55)
    print("  Private Clinic — Obstetrics Management")
    print("  Maternity Care · Antenatal Visits · Follow-ups")
    print("=" * 55)

def venv_python():
    if sys.platform == 'win32':
        return os.path.join(VENV_DIR, 'Scripts', 'python.exe')
    return os.path.join(VENV_DIR, 'bin', 'python3')

def is_venv():
    return sys.prefix != sys.base_prefix

def setup_venv():
    banner()
    print("\n  [1/2] Setting up environment...")
    vp = venv_python()
    if not os.path.exists(VENV_DIR):
        print("  [ .. ] Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True)
        print("  [OK]  Virtual environment created.")
    else:
        print("  [OK]  Virtual environment found.")
    req = os.path.join(SCRIPT_DIR, 'requirements.txt')
    if os.path.exists(req) and not os.path.exists(FLAG):
        print("  [ .. ] Installing dependencies (first run, may take a few minutes)...\n")
        sys.stdout.flush()
        t0 = time.time()
        r = subprocess.run([vp, '-m', 'pip', 'install', '-r', req,
                           '--disable-pip-version-check', '-q'])
        if r.returncode == 0:
            with open(FLAG, 'w') as f: f.write('done')
            print(f"  [OK]  Dependencies installed ({time.time()-t0:.0f}s).")
        else:
            eprint("  [WARN] Some packages failed to install. Trying anyway...")
    return vp

def start_server(port):
    url = f"http://localhost:{port}/dashboard"
    # Open browser early so user sees it faster
    def open_browser():
        time.sleep(1.5)
        try: webbrowser.open(url)
        except: pass
    threading.Thread(target=open_browser, daemon=True).start()

    os.chdir(SCRIPT_DIR)
    sys.path.insert(0, SCRIPT_DIR)
    import uvicorn
    try:
        uvicorn.run("Cloud_API:app", host="0.0.0.0", port=port,
                    log_level="warning", access_log=False)
    except OSError as e:
        eprint(f"\n  [ERROR] {e}")
        eprint("  Try a different port in config.json\n")
        input("  Press Enter to exit...")
    except KeyboardInterrupt:
        print("\n  Server stopped.")

if __name__ == '__main__':
    # Quick Python check
    if sys.version_info < (3, 8):
        banner()
        eprint("\n  [ERROR] Python 3.8+ required")
        eprint(f"  Found: {sys.version_info.major}.{sys.version_info.minor}")
        sys.exit(1)

    # If not inside our venv, set it up and re-exec
    if not is_venv():
        vp = setup_venv()
        os.execl(vp, vp, os.path.abspath(__file__), *sys.argv[1:])

    # We are inside the venv — start server
    import argparse
    config_path = os.path.join(SCRIPT_DIR, "config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path) as f: config = json.load(f)
        except: pass
    parser = argparse.ArgumentParser()
    default_port = config.get("port", int(os.getenv("PORT", "5000")))
    parser.add_argument("--port", type=int, default=default_port)
    args, _ = parser.parse_known_args()
    port = args.port

    # Find a free port
    for p in range(port, port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', p)) != 0:
                port = p
                break

    banner()
    print(f"\n  [OK]  Starting on http://localhost:{port}/dashboard\n")
    start_server(port)
