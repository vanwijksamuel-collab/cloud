import cgi
import hashlib
import json
import mimetypes
import shutil
import zipfile
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode

from wsgiref.util import FileWrapper

from . import storage
from .templates import render_detail, render_index


class Response:
    def __init__(
        self,
        status: int,
        *,
        body: Optional[bytes] = None,
        headers: Optional[List[Tuple[str, str]]] = None,
        body_iter: Optional[Iterable[bytes]] = None,
        close: Optional[Callable[[], None]] = None,
    ) -> None:
        self.status = status
        self.body = body
        self.headers = headers or []
        self.body_iter = body_iter
        self.close = close

    def start(self, start_response: Callable) -> Iterable[bytes]:
        status_line = f"{self.status} {HTTPStatus(self.status).phrase}"
        start_response(status_line, self.headers)
        if self.body_iter is not None:
            return self.body_iter
        if self.body is None:
            return [b""]
        return [self.body]

    def finish(self) -> None:
        if self.close:
            self.close()


class ProSyncApp:
    def __init__(self, config: Dict) -> None:
        self.config = config
        self.db_path = config["DATABASE_PATH"]
        self.upload_folder = Path(config["UPLOAD_FOLDER"])
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        Path(self.config["LOG_PATH"]).parent.mkdir(parents=True, exist_ok=True)
        Path(self.config["BACKUP_DIR"]).mkdir(parents=True, exist_ok=True)
        storage.init_db(self.db_path)

    # WSGI entry point
    def __call__(self, environ, start_response):
        try:
            response = self.handle_request(environ)
        except Exception as exc:  # pragma: no cover - fail-safe
            body = json.dumps({"error": "internal server error", "details": str(exc)}).encode("utf-8")
            response = Response(
                500,
                body=body,
                headers=[("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
            )
        try:
            iterable = response.start(start_response)
            for chunk in iterable:
                yield chunk
        finally:
            response.finish()

    # Request router
    def handle_request(self, environ) -> Response:
        method = environ["REQUEST_METHOD"].upper()
        path = environ.get("PATH_INFO", "")

        if path.startswith("/static/") and method == "GET":
            return self.serve_static(path)

        query = parse_qs(environ.get("QUERY_STRING", ""))
        filters = {key: values[0] for key, values in query.items() if values}

        if path == "/" and method == "GET":
            return self.index(environ, filters)
        if path.startswith("/presentations/") and method == "GET":
            return self.presentations_get(environ, path, filters)
        if path == "/upload" and method == "POST":
            return self.upload(environ)
        if path.startswith("/presentations/versions/"):
            return self.version_routes(environ, path, method)
        if path == "/admin/backup" and method == "GET":
            return self.backup()
        if path == "/health" and method == "GET":
            return self.health()

        return self.not_found()

    # Route handlers
    def index(self, environ, filters: Dict[str, str]) -> Response:
        message = self.extract_message(filters)
        try:
            start = datetime.fromisoformat(filters["start"]) if filters.get("start") else None
        except ValueError:
            return self.redirect("/?" + urlencode({"msg": "Ongeldige startdatum", "cat": "warning"}))
        try:
            end = datetime.fromisoformat(filters["end"]) if filters.get("end") else None
        except ValueError:
            return self.redirect("/?" + urlencode({"msg": "Ongeldige einddatum", "cat": "warning"}))

        presentations = storage.search_presentations(
            self.db_path,
            search=filters.get("q", ""),
            service=filters.get("service", ""),
            start=start,
            end=end,
            sort=filters.get("sort", "newest"),
        )
        service_types = storage.get_service_types(self.db_path)
        body = render_index(
            presentations=presentations,
            service_types=service_types,
            filters=filters,
            message=message,
            base_url=self.base_url(environ),
        ).encode("utf-8")
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ]
        return Response(200, body=body, headers=headers)

    def presentations_get(self, environ, path: str, filters: Dict[str, str]) -> Response:
        parts = path.strip("/").split("/")
        if len(parts) == 2:
            try:
                presentation_id = int(parts[1])
            except ValueError:
                return self.not_found()
            presentation = storage.get_presentation(self.db_path, presentation_id)
            if not presentation:
                return self.not_found()
            versions = storage.list_versions(self.db_path, presentation_id)
            message = self.extract_message(filters)
            service_types = storage.get_service_types(self.db_path)
            body = render_detail(
                presentation=presentation,
                versions=versions,
                service_types=service_types,
                message=message,
                base_url=self.base_url(environ),
            ).encode("utf-8")
            headers = [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ]
            return Response(200, body=body, headers=headers)
        if len(parts) == 3 and parts[2] == "download" and path.endswith("/download/latest"):
            try:
                presentation_id = int(parts[1])
            except ValueError:
                return self.not_found()
            return self.download_latest(presentation_id)
        return self.not_found()

    def version_routes(self, environ, path: str, method: str) -> Response:
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            return self.not_found()
        try:
            version_id = int(parts[2])
        except ValueError:
            return self.not_found()

        if len(parts) == 4 and parts[3] == "download" and method == "GET":
            return self.download_version(version_id)
        if len(parts) == 4 and parts[3] == "restore" and method == "POST":
            return self.restore_version(version_id)
        return self.not_found()

    def upload(self, environ) -> Response:
        content_length = int(environ.get("CONTENT_LENGTH", "0") or 0)
        max_size = self.config["MAX_UPLOAD_SIZE"]
        if content_length > max_size:
            return self.redirect("/?" + urlencode({"msg": "Bestand te groot", "cat": "danger"}))

        form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)

        file_item = form["file"] if "file" in form else None
        if not file_item or not getattr(file_item, "filename", ""):
            return self.redirect("/?" + urlencode({"msg": "Geen bestand geselecteerd", "cat": "danger"}))

        extension = Path(file_item.filename).suffix.lower()
        if extension not in self.config["UPLOAD_EXTENSIONS"]:
            return self.redirect("/?" + urlencode({"msg": "Bestandstype niet toegestaan", "cat": "danger"}))

        logical_name = form.getfirst("logical_name") or Path(file_item.filename).stem
        service_type = form.getfirst("service_type") or None
        description = form.getfirst("description") or None
        note = form.getfirst("note") or None
        action = form.getfirst("action") or "new"
        uploader_name = form.getfirst("uploader_name") or None

        presentation = storage.ensure_presentation(
            self.db_path,
            logical_name=logical_name,
            description=description,
            service_type=service_type,
        )

        presentation_dir = self.upload_folder / str(presentation["id"])
        presentation_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        safe_name = f"{timestamp}_{Path(file_item.filename).name}"
        destination = presentation_dir / safe_name

        with open(destination, "wb") as output:
            shutil.copyfileobj(file_item.file, output)
        file_size = destination.stat().st_size
        checksum = self.calculate_checksum(destination)

        version_number = storage.next_version_number(self.db_path, presentation["id"])
        version = storage.add_version(
            self.db_path,
            presentation_id=presentation["id"],
            version_number=version_number,
            uploader_ip=environ.get("REMOTE_ADDR"),
            uploader_name=uploader_name,
            file_size=file_size,
            file_path=str(destination),
            original_filename=file_item.filename,
            checksum=checksum,
            service_type=service_type or presentation.get("service_type"),
            note=note,
        )

        self.log_upload(presentation["logical_name"], version, action)

        return self.redirect(
            f"/presentations/{presentation['id']}?"
            + urlencode({"msg": "Upload geslaagd", "cat": "success"})
        )

    def download_latest(self, presentation_id: int) -> Response:
        presentation = storage.get_presentation(self.db_path, presentation_id)
        if not presentation:
            return self.not_found()
        latest_id = presentation.get("latest_version_id")
        if not latest_id:
            return self.redirect("/?" + urlencode({"msg": "Geen versies beschikbaar", "cat": "warning"}))
        return self.send_file_for_version(latest_id)

    def download_version(self, version_id: int) -> Response:
        return self.send_file_for_version(version_id)

    def send_file_for_version(self, version_id: int) -> Response:
        version = storage.get_version(self.db_path, version_id)
        if not version:
            return self.not_found()
        file_path = Path(version["file_path"])
        if not file_path.exists():
            location = (
                f"/presentations/{version['presentation_id']}?"
                + urlencode({"msg": "Bestand niet gevonden", "cat": "danger"})
            )
            return self.redirect(location)
        file = open(file_path, "rb")
        wrapper = FileWrapper(file)
        headers = [
            ("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"),
            ("Content-Disposition", f"attachment; filename=\"{Path(version['original_filename']).name}\""),
            ("Content-Length", str(file_path.stat().st_size)),
        ]
        return Response(200, headers=headers, body_iter=wrapper, close=file.close)

    def restore_version(self, version_id: int) -> Response:
        version = storage.get_version(self.db_path, version_id)
        if not version:
            return self.not_found()
        source_path = Path(version["file_path"])
        if not source_path.exists():
            location = (
                f"/presentations/{version['presentation_id']}?"
                + urlencode({"msg": "Bestand niet gevonden voor deze versie", "cat": "danger"})
            )
            return self.redirect(location)

        presentation_dir = self.upload_folder / str(version["presentation_id"])
        presentation_dir.mkdir(parents=True, exist_ok=True)
        restored_name = (
            f"restore_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{source_path.name}"
        )
        destination = presentation_dir / restored_name
        shutil.copy2(source_path, destination)

        version_number = storage.next_version_number(self.db_path, version["presentation_id"])
        storage.add_version(
            self.db_path,
            presentation_id=version["presentation_id"],
            version_number=version_number,
            uploader_ip=None,
            uploader_name="restore",
            file_size=destination.stat().st_size,
            file_path=str(destination),
            original_filename=version["original_filename"],
            checksum=self.calculate_checksum(destination),
            service_type=version.get("service_type"),
            note=f"Restore van versie {version['version_number']}",
        )

        location = (
            f"/presentations/{version['presentation_id']}?"
            + urlencode({"msg": "Versie hersteld", "cat": "success"})
        )
        return self.redirect(location)

    def backup(self) -> Response:
        db_path = Path(self.db_path)
        uploads_dir = self.upload_folder
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        archive_name = Path(self.config["BACKUP_DIR"]) / f"prosync_backup_{timestamp}.zip"

        with zipfile.ZipFile(archive_name, "w", zipfile.ZIP_DEFLATED) as archive:
            if db_path.exists():
                archive.write(db_path, arcname="database.sqlite")
            if uploads_dir.exists():
                for item in uploads_dir.rglob("*"):
                    if item.is_file():
                        archive.write(item, arcname=str(item.relative_to(uploads_dir.parent)))

        file = open(archive_name, "rb")
        headers = [
            ("Content-Type", "application/zip"),
            ("Content-Disposition", f"attachment; filename=\"{archive_name.name}\""),
            ("Content-Length", str(archive_name.stat().st_size)),
        ]
        return Response(200, headers=headers, body_iter=FileWrapper(file), close=file.close)

    def health(self) -> Response:
        counts = storage.total_counts(self.db_path)
        payload = json.dumps(
            {
                "status": "ok",
                "presentations": counts[0],
                "versions": counts[1],
                "total_storage_bytes": counts[2],
            }
        ).encode("utf-8")
        headers = [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(payload))),
        ]
        return Response(200, body=payload, headers=headers)

    def not_found(self) -> Response:
        body = b"<h1>404 Niet gevonden</h1>"
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ]
        return Response(404, body=body, headers=headers)

    def redirect(self, location: str) -> Response:
        headers = [("Location", location)]
        return Response(303, headers=headers)

    def extract_message(self, filters: Dict[str, str]) -> Optional[Tuple[str, str]]:
        if "msg" in filters:
            return filters.get("cat", "info"), filters["msg"]
        return None

    def base_url(self, environ) -> str:
        scheme = environ.get("wsgi.url_scheme", "http")
        host = environ.get("HTTP_HOST") or environ.get("SERVER_NAME")
        if not host:
            return f"{scheme}://localhost"
        return f"{scheme}://{host}"

    def serve_static(self, path: str) -> Response:
        static_root = Path(__file__).resolve().parent / "static"
        relative = path[len("/static/"):]
        target = static_root / relative
        if not target.exists() or not target.is_file():
            return self.not_found()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        headers = [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
        ]
        return Response(200, body=body, headers=headers)

    def calculate_checksum(self, path: Path) -> str:
        hash_md5 = hashlib.md5()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def log_upload(self, logical_name: str, version: dict, action: str) -> None:
        log_line = (
            f"{datetime.utcnow().isoformat()} | presentation={logical_name} | version={version['version_number']} | "
            f"filename={version['original_filename']} | action={action} | ip={version.get('uploader_ip')} | service={version.get('service_type')}\n"
        )
        log_path = Path(self.config["LOG_PATH"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(log_line)
