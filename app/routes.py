import hashlib
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import func, or_

from .database import Presentation, PresentationVersion, db

bp = Blueprint("core", __name__)


def _service_type_palette(service_type: str) -> str:
    palette = [
        "#2563eb",
        "#db2777",
        "#0f766e",
        "#f97316",
        "#7c3aed",
        "#1d4ed8",
    ]
    if not service_type:
        return "#6b7280"
    index = abs(hash(service_type)) % len(palette)
    return palette[index]


@bp.app_template_filter("servicetag")
def service_tag_color(service_type: str) -> str:
    return _service_type_palette(service_type)


@bp.route("/")
def index():
    query = Presentation.query

    search_term = request.args.get("q", "").strip()
    service_filter = request.args.get("service", "").strip()
    start_date = request.args.get("start", "").strip()
    end_date = request.args.get("end", "").strip()
    sort = request.args.get("sort", "newest")

    if search_term:
        like_term = f"%{search_term}%"
        query = query.filter(
            or_(
                Presentation.logical_name.ilike(like_term),
                Presentation.description.ilike(like_term),
            )
        )

    if service_filter:
        query = query.filter(Presentation.service_type == service_filter)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Presentation.created_at >= start_dt)
        except ValueError:
            flash("Ongeldige startdatum", "warning")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Presentation.created_at <= end_dt)
        except ValueError:
            flash("Ongeldige einddatum", "warning")

    if sort == "oldest":
        query = query.order_by(Presentation.created_at.asc())
    elif sort == "size":
        subquery = (
            db.session.query(
                PresentationVersion.presentation_id.label("pid"),
                func.max(PresentationVersion.file_size).label("max_size"),
            )
            .group_by(PresentationVersion.presentation_id)
            .subquery()
        )
        query = query.join(subquery, Presentation.id == subquery.c.pid).order_by(subquery.c.max_size.desc())
    else:
        query = query.order_by(Presentation.created_at.desc())

    presentations = query.all()

    service_types = [
        row[0]
        for row in db.session.query(Presentation.service_type)
        .distinct()
        .filter(Presentation.service_type.isnot(None))
    ]

    return render_template(
        "index.html",
        presentations=presentations,
        service_types=sorted(service_types),
        search_term=search_term,
        service_filter=service_filter,
        sort=sort,
        start_date=start_date,
        end_date=end_date,
    )


@bp.route("/presentations/<int:presentation_id>")
def presentation_detail(presentation_id: int):
    presentation = Presentation.query.get_or_404(presentation_id)
    versions = (
        PresentationVersion.query.filter_by(presentation_id=presentation.id)
        .order_by(PresentationVersion.version_number.desc())
        .all()
    )
    service_types = [
        row[0]
        for row in db.session.query(Presentation.service_type)
        .distinct()
        .filter(Presentation.service_type.isnot(None))
    ]
    return render_template(
        "detail.html",
        presentation=presentation,
        versions=versions,
        service_types=sorted(service_types),
    )


@bp.route("/presentations/<int:presentation_id>/download/latest")
def download_latest(presentation_id: int):
    presentation = Presentation.query.get_or_404(presentation_id)
    version = presentation.latest_version or (
        PresentationVersion.query.filter_by(presentation_id=presentation.id)
        .order_by(PresentationVersion.version_number.desc())
        .first()
    )
    if not version:
        flash("Geen versies beschikbaar", "warning")
        return redirect(url_for("core.index"))
    file_path = Path(version.file_path)
    if not file_path.exists():
        flash("Bestand niet gevonden", "danger")
        return redirect(url_for("core.presentation_detail", presentation_id=presentation.id))
    return send_file(file_path, as_attachment=True, download_name=version.original_filename)


@bp.route("/presentations/versions/<int:version_id>/download")
def download_version(version_id: int):
    version = PresentationVersion.query.get_or_404(version_id)
    file_path = Path(version.file_path)
    if not file_path.exists():
        flash("Bestand niet gevonden", "danger")
        return redirect(url_for("core.presentation_detail", presentation_id=version.presentation_id))
    return send_file(file_path, as_attachment=True, download_name=version.original_filename)


def _next_version_number(presentation: Presentation) -> int:
    latest = (
        PresentationVersion.query.filter_by(presentation_id=presentation.id)
        .order_by(PresentationVersion.version_number.desc())
        .first()
    )
    if latest:
        return latest.version_number + 1
    return 1


def _save_file(file_storage, upload_dir: Path) -> tuple[str, int, str]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    filename = file_storage.filename or "upload.pro"
    safe_name = f"{timestamp}_{filename}"
    destination = upload_dir / safe_name
    file_storage.save(destination)
    file_size = destination.stat().st_size
    checksum = _checksum(destination)
    return str(destination), file_size, checksum


def _checksum(path: Path) -> str:
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


@bp.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    logical_name = request.form.get("logical_name")
    service_type = request.form.get("service_type") or None
    description = request.form.get("description")
    note = request.form.get("note")
    action = request.form.get("action", "new")
    uploader_name = request.form.get("uploader_name")

    if not file or file.filename == "":
        flash("Geen bestand geselecteerd", "danger")
        return redirect(request.referrer or url_for("core.index"))

    extension = Path(file.filename).suffix.lower()
    allowed = current_app.config["UPLOAD_EXTENSIONS"]
    if extension not in allowed:
        flash("Bestandstype niet toegestaan", "danger")
        return redirect(request.referrer or url_for("core.index"))

    logical_name = logical_name or Path(file.filename).stem

    presentation = Presentation.query.filter_by(logical_name=logical_name).first()
    if not presentation:
        presentation = Presentation(
            logical_name=logical_name,
            description=description,
            service_type=service_type,
        )
        db.session.add(presentation)
        db.session.flush()
    else:
        if description:
            presentation.description = description
        if service_type:
            presentation.service_type = service_type

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]) / str(presentation.id)
    file_path, file_size, checksum = _save_file(file, upload_folder)
    version_number = _next_version_number(presentation)

    version = PresentationVersion(
        presentation_id=presentation.id,
        version_number=version_number,
        uploader_ip=request.remote_addr,
        uploader_name=uploader_name,
        file_size=file_size,
        file_path=file_path,
        original_filename=file.filename,
        checksum=checksum,
        service_type=service_type or presentation.service_type,
        note=note,
    )
    db.session.add(version)
    presentation.latest_version = version
    presentation.updated_at = datetime.utcnow()

    db.session.commit()

    _log_upload(presentation.logical_name, version, action)

    flash("Upload geslaagd", "success")
    return redirect(url_for("core.presentation_detail", presentation_id=presentation.id))


def _log_upload(logical_name: str, version: PresentationVersion, action: str) -> None:
    log_line = (
        f"{datetime.utcnow().isoformat()} | presentation={logical_name} | version={version.version_number} | "
        f"filename={version.original_filename} | action={action} | ip={version.uploader_ip} | service={version.service_type}\n"
    )
    log_path = Path(current_app.config.get("UPLOAD_LOG", Path("logs") / "uploads.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(log_line)


@bp.route("/presentations/versions/<int:version_id>/restore", methods=["POST"])
def restore_version(version_id: int):
    version = PresentationVersion.query.get_or_404(version_id)
    presentation = version.presentation

    source_path = Path(version.file_path)
    if not source_path.exists():
        flash("Bestand niet gevonden voor deze versie", "danger")
        return redirect(url_for("core.presentation_detail", presentation_id=presentation.id))

    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"]) / str(presentation.id)
    new_path = uploads_dir / f"restore_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{source_path.name}"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, new_path)

    new_version = PresentationVersion(
        presentation_id=presentation.id,
        version_number=_next_version_number(presentation),
        uploader_ip=request.remote_addr,
        uploader_name="restore",
        file_size=new_path.stat().st_size,
        file_path=str(new_path),
        original_filename=version.original_filename,
        checksum=_checksum(new_path),
        service_type=version.service_type,
        note=f"Restore van versie {version.version_number}",
    )
    db.session.add(new_version)
    presentation.latest_version = new_version
    presentation.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Versie hersteld", "success")
    return redirect(url_for("core.presentation_detail", presentation_id=presentation.id))


@bp.route("/admin/backup")
def backup():
    db_path = current_app.config["SQLALCHEMY_DATABASE_URI"].split("///", 1)[-1]
    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
    backup_dir = Path(current_app.config.get("BACKUP_DIR", "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    archive_name = backup_dir / f"prosync_backup_{timestamp}.zip"

    with zipfile.ZipFile(archive_name, "w", zipfile.ZIP_DEFLATED) as archive:
        if os.path.exists(db_path):
            archive.write(db_path, arcname="database.sqlite")
        for file_path in uploads_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, arcname=str(file_path.relative_to(uploads_dir.parent)))

    return send_file(archive_name, as_attachment=True)


@bp.route("/health")
def health():
    total_presentations = Presentation.query.count()
    total_versions = PresentationVersion.query.count()
    total_size = db.session.query(func.sum(PresentationVersion.file_size)).scalar() or 0

    return jsonify(
        status="ok",
        presentations=total_presentations,
        versions=total_versions,
        total_storage_bytes=total_size,
    )


@bp.app_template_global()
def share_link(version):
    if isinstance(version, PresentationVersion):
        return url_for("core.download_version", version_id=version.id, _external=True)
    return url_for("core.download_latest", presentation_id=version.id, _external=True)
