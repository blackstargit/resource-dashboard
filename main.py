"""
Resource Monitor - Entry Point
================================
Start the server:   python main.py
Reload dev mode:    uvicorn main:app --reload
"""
import uvicorn

from app.app import create_app
from app.core.config import HOST, PORT

# Module-level app lets uvicorn --reload discover the instance directly.
app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, reload=False)
