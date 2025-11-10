"""Seedbestand dat een aantal voorbeeldpresentaties toevoegt."""

from datetime import datetime
import hashlib
from pathlib import Path

from app import create_app
from app.database import Presentation, PresentationVersion, db

app = create_app()


def add_version(presentation: Presentation, filename: str, size: int, service_type: str, note: str, uploader: str):
    uploads_dir = Path(app.config["UPLOAD_FOLDER"]) / str(presentation.id)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    fake_file = uploads_dir / filename
    fake_file.write_bytes(b"0" * size)
    checksum = hashlib.md5(fake_file.read_bytes()).hexdigest()
    version = PresentationVersion(
        presentation_id=presentation.id,
        version_number=len(presentation.versions) + 1,
        uploader_ip="127.0.0.1",
        uploader_name=uploader,
        file_size=fake_file.stat().st_size,
        file_path=str(fake_file),
        original_filename=filename,
        checksum=checksum,
        service_type=service_type,
        note=note,
    )
    db.session.add(version)
    presentation.latest_version = version


def run():
    with app.app_context():
        if Presentation.query.count():
            print("Database bevat al data; seed wordt overgeslagen.")
            return

        services = [
            ("Zondagmorgen", "Wekelijkse eredienst"),
            ("Jeugddienst", "Creatieve avond met jeugd"),
            ("Kerstnachtdienst", "Speciale kerstviering"),
        ]

        for index, (service, description) in enumerate(services, start=1):
            presentation = Presentation(
                logical_name=f"Presentatie {index}",
                description=description,
                service_type=service,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(presentation)
            db.session.flush()
            add_version(
                presentation,
                filename=f"demo_{index}.pro6",
                size=1024 * 1024 * (index + 1),
                service_type=service,
                note="Voorbeeldversie",
                uploader="Seeder",
            )
        db.session.commit()
        print("Seeddata toegevoegd.")


if __name__ == "__main__":
    run()
