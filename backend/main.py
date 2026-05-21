"""Backend entrypoint — delegates to the new app factory in app/main.py.

Kept at the package root so existing `uvicorn main:app` commands keep working.
"""

from app.main import app  # noqa: F401


if __name__ == "__main__":
    import uvicorn

    from app.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
