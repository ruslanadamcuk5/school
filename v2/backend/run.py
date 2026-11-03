"""Run the v2 ASGI application.

    uvicorn school_api.main:app --host 0.0.0.0 --port 8000
"""
from school_api.main import app, run  # noqa: F401

if __name__ == "__main__":
    run()
