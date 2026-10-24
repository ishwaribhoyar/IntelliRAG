"""Root entrypoint for deployment platforms (Render, Railway, Heroku).

Allows running either:
    uvicorn main:app --host 0.0.0.0 --port $PORT
from repo root, or:
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
from backend directory.
"""
import os
import sys
from pathlib import Path

# Add backend directory to sys.path so app.* imports resolve from root
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
