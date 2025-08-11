from app.settings import DEBUG, SERVER_SETTINGS

if __name__ == "__main__":
    from granian import Granian  # pyright: ignore[reportPrivateImportUsage]
    from granian.constants import Interfaces

    Granian(
        "app.main:app",
        address=SERVER_SETTINGS.host,
        port=SERVER_SETTINGS.port,
        reload=DEBUG,
        interface=Interfaces.ASGI,
        workers=SERVER_SETTINGS.workers,
    ).serve()
