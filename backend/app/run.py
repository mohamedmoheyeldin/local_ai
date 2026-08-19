from __future__ import annotations

import uvicorn

from .database import get_settings, initialize_database
from .main import app


def main() -> None:
    initialize_database()
    settings = get_settings()
    if str(settings["app_host"]) not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Refusing a non-loopback app host: remote access requires an authentication layer")
    uvicorn.run(
        app,
        host=str(settings["app_host"]),
        port=int(settings["app_port"]),
        log_level="info",
    )


if __name__ == "__main__":
    main()
