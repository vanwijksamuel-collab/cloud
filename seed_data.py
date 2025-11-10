from __future__ import annotations

import hashlib
from pathlib import Path

from app import create_app
from app.server import ProSyncApp
from app import storage


EXAMPLE_DATA = [
    {
        "logical_name": "Zondagmorgen",
        "description": "Liturgie en liederen voor de zondagsdienst",
        "service_type": "Zondag",
    },
    {
        "logical_name": "Jeugddienst",
        "description": "Interactieve slides voor de jeugddienst",
        "service_type": "Jeugd",
    },
    {
        "logical_name": "Kerstnachtdienst",
        "description": "Kerstavondpresentatie met carols",
        "service_type": "Kerst",
    },
]


def checksum(path: Path) -> str:
    hash_md5 = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def main() -> None:
    app: ProSyncApp = create_app()
    db_path = app.db_path
    uploads_dir = Path(app.upload_folder)

    storage.init_db(db_path)

    for item in EXAMPLE_DATA:
        presentation = storage.ensure_presentation(
            db_path,
            logical_name=item["logical_name"],
            description=item["description"],
            service_type=item["service_type"],
        )
        uploads = uploads_dir / str(presentation["id"])
        uploads.mkdir(parents=True, exist_ok=True)

        for version_no in range(1, 3):
            fake_file = uploads / f"{item['logical_name'].lower()}_v{version_no}.pro7"
            fake_file.write_text(
                f"Demo inhoud voor {item['logical_name']} versie {version_no}\n",
                encoding="utf-8",
            )
            storage.add_version(
                db_path,
                presentation_id=presentation["id"],
                version_number=version_no,
                uploader_ip="127.0.0.1",
                uploader_name="seed",
                file_size=fake_file.stat().st_size,
                file_path=str(fake_file),
                original_filename=fake_file.name,
                checksum=checksum(fake_file),
                service_type=item["service_type"],
                note="Voorbeelddata",
            )

    print("Seed data geladen.")


if __name__ == "__main__":
    main()
