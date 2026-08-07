import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "control_service.main:app",
        host=os.getenv("CONTROL_SERVICE_HOST", "0.0.0.0"),
        port=int(os.getenv("CONTROL_SERVICE_PORT", "8010")),
        reload=os.getenv("CONTROL_SERVICE_RELOAD", "0").lower() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    main()
