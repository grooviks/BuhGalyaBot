"""PyCharm-friendly entry point for the local API server."""

import uvicorn

from buhgalya.app_logging import configure_logging


def main() -> None:
    configure_logging()
    uvicorn.run(
        "buhgalya.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_config=None,
    )


if __name__ == "__main__":
    main()
