import os
from flask import Flask

from .database import db, migrate_database


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("PROSYNC_SECRET", "change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("PROSYNC_DATABASE", "sqlite:///prosync.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    upload_folder = os.environ.get("PROSYNC_UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder
    app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("PROSYNC_MAX_UPLOAD", 500 * 1024 * 1024))
    app.config["UPLOAD_EXTENSIONS"] = {".pro", ".pro5", ".pro6", ".pro7"}

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    with app.app_context():
        migrate_database()
        from .routes import bp

        app.register_blueprint(bp)

    return app
