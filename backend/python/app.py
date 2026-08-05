"""Compatibility entrypoint for existing Uvicorn and deployment commands."""

from app.main import app

__all__ = ["app"]
