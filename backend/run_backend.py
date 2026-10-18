"""
HealerPlus 2.0 - Standalone Backend Server Runner
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def main():
    print("=" * 70)
    print("   HEALERPLUS 2.0 - HEALTHCARE BLOCKCHAIN & AI SECURITY PLATFORM")
    print("=" * 70)
    print("Starting FastAPI Backend Server on http://127.0.0.1:8000 ...")

    try:
        import uvicorn
        from backend.app.main import app
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except ImportError:
        print("[!] Uvicorn not found. Running built-in HTTP server fallback...")
        import http.server
        import socketserver

        PORT = 8000
        Handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Serving at http://127.0.0.1:{PORT}")
            httpd.serve_forever()

if __name__ == "__main__":
    main()
