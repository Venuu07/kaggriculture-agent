"""Start the demo: python -m kagri.serve [--port 8000] [--no-browser]"""
from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    url = f"http://localhost:{a.port}"
    print(f"Kaggriculture Agent demo on {url}  (Ctrl+C to stop)")
    if not a.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("kagri.server:app", host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
