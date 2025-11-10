import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event


db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Presentation(db.Model, TimestampMixin):
    __tablename__ = "presentations"

    id = db.Column(db.Integer, primary_key=True)
    logical_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    service_type = db.Column(db.String(120), nullable=True)
    latest_version_id = db.Column(db.Integer, db.ForeignKey("presentation_versions.id"), nullable=True)

    versions = db.relationship(
        "PresentationVersion",
        backref="presentation",
        cascade="all, delete-orphan",
        order_by="PresentationVersion.version_number.desc()",
    )


class PresentationVersion(db.Model, TimestampMixin):
    __tablename__ = "presentation_versions"

    id = db.Column(db.Integer, primary_key=True)
    presentation_id = db.Column(db.Integer, db.ForeignKey("presentations.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    uploader_ip = db.Column(db.String(64), nullable=True)
    uploader_name = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    checksum = db.Column(db.String(64), nullable=False)
    service_type = db.Column(db.String(120), nullable=True)
    note = db.Column(db.Text, nullable=True)


Presentation.latest_version = db.relationship(
    PresentationVersion,
    primaryjoin=Presentation.latest_version_id == PresentationVersion.id,
    uselist=False,
    post_update=True,
)


@event.listens_for(Presentation, "before_update")
def receive_before_update(mapper, connection, target):
    target.updated_at = datetime.utcnow()


@event.listens_for(PresentationVersion, "before_update")
def receive_before_update_version(mapper, connection, target):
    target.updated_at = datetime.utcnow()


def migrate_database():
    from flask import current_app

    db_path = current_app.config.get("SQLALCHEMY_DATABASE_URI", "sqlite:///prosync.db")
    if db_path.startswith("sqlite"):
        filename = db_path.split("///", 1)[-1]
        directory = os.path.dirname(filename)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    db.create_all()
