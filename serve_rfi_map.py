#!/usr/bin/env python3
"""Serve a generated RFI map plugin locally for browser development/debugging."""

from __future__ import annotations

import argparse
import http.server
import os
import webbrowser
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a local RFI map preview server.")
    parser.add_argument("--map-dir", type=Path, default=Path(__file__).resolve().parent / "rfi-interactive-map",
                        help="Generated plugin folder (default: rfi-interactive-map)")
    parser.add_argument("--port", type=int, default=8000, help="Local port (default: 8000)")
    parser.add_argument("--open", action="store_true", help="Open the preview in your default browser")
    args = parser.parse_args()
    root = args.map_dir.resolve()
    preview = root / "preview" / "index.html"
    if not preview.is_file():
        parser.error(f"Preview not found: {preview}. Re-run build_rfi_map.py first.")
    os.chdir(root)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), http.server.SimpleHTTPRequestHandler)
    url = f"http://127.0.0.1:{args.port}/preview/"
    print(f"Preview: {url}")
    print("Press Ctrl+C to stop the server.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview server stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
