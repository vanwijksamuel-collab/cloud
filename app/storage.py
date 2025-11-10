import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS presentations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        logical_name TEXT NOT NULL,
        description TEXT,
        service_type TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        latest_version_id INTEGER,
        UNIQUE(logical_name)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS presentation_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        presentation_id INTEGER NOT NULL,
        version_number INTEGER NOT NULL,
        uploader_ip TEXT,
        uploader_name TEXT,
        file_size INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        checksum TEXT NOT NULL,
        service_type TEXT,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(presentation_id) REFERENCES presentations(id)
    );
    """,
]


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        for statement in SCHEMA:
            conn.execute(statement)
        conn.commit()


@contextmanager
def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_service_types(db_path: str) -> List[str]:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT DISTINCT service_type FROM presentations WHERE service_type IS NOT NULL ORDER BY service_type"
        )
        return [row[0] for row in cursor.fetchall()]


def search_presentations(
    db_path: str,
    *,
    search: str = "",
    service: str = "",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    sort: str = "newest",
) -> List[Dict]:
    clauses = []
    params: List = []

    if search:
        clauses.append("(p.logical_name LIKE ? OR p.description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])
    if service:
        clauses.append("p.service_type = ?")
        params.append(service)
    if start:
        clauses.append("p.created_at >= ?")
        params.append(start.isoformat())
    if end:
        clauses.append("p.created_at <= ?")
        params.append(end.isoformat())

    where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""

    order_sql = "ORDER BY p.updated_at DESC"
    if sort == "oldest":
        order_sql = "ORDER BY p.created_at ASC"
    elif sort == "size":
        order_sql = "ORDER BY latest_size DESC"

    query = f"""
        SELECT p.*, v.file_size AS latest_size, v.created_at AS latest_uploaded_at
        FROM presentations p
        LEFT JOIN presentation_versions v ON v.id = p.latest_version_id
        {where_sql}
        {order_sql}
    """

    with connect(db_path) as conn:
        cursor = conn.execute(query, params)
        presentations = [dict(row) for row in cursor.fetchall()]

    return presentations


def get_presentation(db_path: str, presentation_id: int) -> Optional[Dict]:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM presentations WHERE id = ?",
            (presentation_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        presentation = dict(row)
        if presentation.get("latest_version_id"):
            v_cursor = conn.execute(
                "SELECT * FROM presentation_versions WHERE id = ?",
                (presentation["latest_version_id"],),
            )
            latest_row = v_cursor.fetchone()
            if latest_row:
                presentation["latest_version"] = dict(latest_row)
        return presentation


def list_versions(db_path: str, presentation_id: int) -> List[Dict]:
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT * FROM presentation_versions
            WHERE presentation_id = ?
            ORDER BY version_number DESC
            """,
            (presentation_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def ensure_presentation(
    db_path: str,
    *,
    logical_name: str,
    description: Optional[str],
    service_type: Optional[str],
) -> Dict:
    now = datetime.utcnow().isoformat()
    with connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM presentations WHERE logical_name = ?",
            (logical_name,),
        )
        row = cursor.fetchone()
        if row:
            presentation = dict(row)
            updates = []
            params: List = []
            if description:
                updates.append("description = ?")
                params.append(description)
            if service_type:
                updates.append("service_type = ?")
                params.append(service_type)
            if updates:
                updates.append("updated_at = ?")
                params.append(now)
                params.append(presentation["id"])
                conn.execute(
                    f"UPDATE presentations SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                presentation.update(
                    {
                        "description": description or presentation.get("description"),
                        "service_type": service_type or presentation.get("service_type"),
                        "updated_at": now,
                    }
                )
            return presentation

        cursor = conn.execute(
            """
            INSERT INTO presentations (logical_name, description, service_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (logical_name, description, service_type, now, now),
        )
        new_id = cursor.lastrowid
        cursor = conn.execute("SELECT * FROM presentations WHERE id = ?", (new_id,))
        return dict(cursor.fetchone())


def next_version_number(db_path: str, presentation_id: int) -> int:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT MAX(version_number) FROM presentation_versions WHERE presentation_id = ?",
            (presentation_id,),
        )
        row = cursor.fetchone()
        if row and row[0]:
            return row[0] + 1
        return 1


def add_version(
    db_path: str,
    *,
    presentation_id: int,
    version_number: int,
    uploader_ip: Optional[str],
    uploader_name: Optional[str],
    file_size: int,
    file_path: str,
    original_filename: str,
    checksum: str,
    service_type: Optional[str],
    note: Optional[str],
) -> Dict:
    now = datetime.utcnow().isoformat()
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO presentation_versions (
                presentation_id,
                version_number,
                uploader_ip,
                uploader_name,
                file_size,
                file_path,
                original_filename,
                checksum,
                service_type,
                note,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                presentation_id,
                version_number,
                uploader_ip,
                uploader_name,
                file_size,
                file_path,
                original_filename,
                checksum,
                service_type,
                note,
                now,
            ),
        )
        version_id = cursor.lastrowid
        conn.execute(
            "UPDATE presentations SET latest_version_id = ?, updated_at = ? WHERE id = ?",
            (version_id, now, presentation_id),
        )
        cursor = conn.execute(
            "SELECT * FROM presentation_versions WHERE id = ?",
            (version_id,),
        )
        return dict(cursor.fetchone())


def get_version(db_path: str, version_id: int) -> Optional[Dict]:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM presentation_versions WHERE id = ?",
            (version_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def total_counts(db_path: str) -> Tuple[int, int, int]:
    with connect(db_path) as conn:
        presentations = conn.execute("SELECT COUNT(*) FROM presentations").fetchone()[0]
        versions = conn.execute("SELECT COUNT(*) FROM presentation_versions").fetchone()[0]
        total_size = (
            conn.execute("SELECT COALESCE(SUM(file_size), 0) FROM presentation_versions").fetchone()[0]
        )
    return presentations, versions, total_size
