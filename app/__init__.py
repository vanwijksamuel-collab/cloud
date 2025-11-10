import os
from typing import Optional

from .server import ProSyncApp


def create_app(config: Optional[dict] = None) -> ProSyncApp:
    settings = {
        "DATABASE_PATH": os.environ.get("PROSYNC_DATABASE", os.path.join(os.getcwd(), "prosync.db")),
        "UPLOAD_FOLDER": os.environ.get("PROSYNC_UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads")),
        "MAX_UPLOAD_SIZE": int(os.environ.get("PROSYNC_MAX_UPLOAD", 500 * 1024 * 1024)),
        "UPLOAD_EXTENSIONS": {".pro", ".pro5", ".pro6", ".pro7"},
        "LOG_PATH": os.environ.get("PROSYNC_UPLOAD_LOG", os.path.join(os.getcwd(), "logs", "uploads.log")),
        "BACKUP_DIR": os.environ.get("PROSYNC_BACKUP_DIR", os.path.join(os.getcwd(), "backups")),
    }

    if config:
        settings.update(config)

    app = ProSyncApp(settings)
    return app
