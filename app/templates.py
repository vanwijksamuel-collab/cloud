from __future__ import annotations

import html
from datetime import datetime
from typing import Iterable, List, Optional, Tuple


PALETTE = [
    "#2563eb",
    "#db2777",
    "#0f766e",
    "#f97316",
    "#7c3aed",
    "#1d4ed8",
]


def service_color(service_type: Optional[str]) -> str:
    if not service_type:
        return "#6b7280"
    return PALETTE[abs(hash(service_type)) % len(PALETTE)]


def render_base(
    *,
    title: str,
    content: str,
    service_types: Iterable[str],
    message: Optional[Tuple[str, str]],
) -> str:
    message_html = ""
    if message:
        category, text = message
        message_html = (
            f"<div class=\"space-y-2\"><div class=\"alert alert-{html.escape(category)}\">"
            f"{html.escape(text)}" "</div></div>"
        )

    datalist_options = "\n".join(
        f"<option value=\"{html.escape(service)}\"></option>" for service in service_types
    )

    return f"""
<!doctype html>
<html lang=\"nl\" class=\"h-full bg-slate-100\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{html.escape(title)}</title>
    <link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap\">
    <link rel=\"stylesheet\" href=\"/static/css/styles.css\" />
    <script defer src=\"/static/js/app.js\"></script>
  </head>
  <body class=\"min-h-full font-sans text-slate-800\">
    <header class=\"bg-white shadow-sm\">
      <div class=\"mx-auto flex max-w-6xl items-center justify-between px-4 py-6\">
        <div>
          <h1 class=\"text-2xl font-semibold text-slate-900\">ProSync — Presentaties delen voor <span class=\"text-blue-600\">[Kerknaam]</span></h1>
          <p class=\"text-sm text-slate-500\">Vind, download en beheer al je ProPresenter-bestanden op één plek.</p>
        </div>
        <div>
          <a href=\"#upload\" class=\"btn-primary\" data-open-upload>Inloggen / Uploaden</a>
        </div>
      </div>
    </header>
    <main class=\"mx-auto max-w-6xl px-4 py-8\">
      {message_html}
      {content}
    </main>
    <footer class=\"border-t border-slate-200 bg-white\">
      <div class=\"mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500\">
        <p>Alleen .pro, .pro5, .pro6 en .pro7 bestandstypen. Max 500 MB per upload.</p>
        <p>
          <a href=\"mailto:beheer@example.com\" class=\"text-blue-600 hover:underline\">Contact beheer</a>
          · <a href=\"/health\" class=\"text-blue-600 hover:underline\">Health/status</a>
          · <a href=\"/admin/backup\" class=\"text-blue-600 hover:underline\">Backup / export</a>
        </p>
      </div>
    </footer>
    {render_upload_modal(datalist_options)}
  </body>
</html>
"""


def render_upload_modal(datalist_options: str) -> str:
    return f"""
<div id=\"upload-modal\" class=\"modal hidden\" aria-hidden=\"true\" role=\"dialog\">
  <div class=\"modal-backdrop\" data-close-upload></div>
  <div class=\"modal-content\" role=\"document\">
    <header class=\"modal-header\">
      <h2 class=\"text-lg font-semibold text-slate-900\">Upload presentatie</h2>
      <button class=\"modal-close\" type=\"button\" data-close-upload aria-label=\"Sluiten\">×</button>
    </header>
    <form id=\"upload-form\" class=\"space-y-4\" action=\"/upload\" method=\"post\" enctype=\"multipart/form-data\">
      <div class=\"dropzone\" data-dropzone>
        <input id=\"file-input\" type=\"file\" name=\"file\" accept=\".pro,.pro5,.pro6,.pro7\" required hidden />
        <p class=\"text-center text-sm text-slate-500\">
          Sleep je bestand hierheen of <button class=\"text-blue-600\" type=\"button\" data-trigger-file>Kies bestand</button>
        </p>
        <p id=\"selected-file\" class=\"mt-2 text-center text-xs text-slate-400\"></p>
      </div>
      <div>
        <label class=\"form-label\" for=\"logical_name\">Logical name</label>
        <input class=\"form-input\" id=\"logical_name\" name=\"logical_name\" placeholder=\"Auto afgeleid van bestandsnaam\" />
      </div>
      <div>
        <label class=\"form-label\" for=\"service_type\">Diensttype</label>
        <input class=\"form-input\" id=\"service_type\" name=\"service_type\" list=\"service-types\" placeholder=\"Bijv. Zondag\" />
        <datalist id=\"service-types\">
          {datalist_options}
        </datalist>
      </div>
      <div>
        <label class=\"form-label\" for=\"description\">Beschrijving</label>
        <textarea class=\"form-input\" id=\"description\" name=\"description\" rows=\"2\" placeholder=\"Korte omschrijving\"></textarea>
      </div>
      <div>
        <label class=\"form-label\" for=\"note\">Notitie</label>
        <textarea class=\"form-input\" id=\"note\" name=\"note\" rows=\"2\" placeholder=\"Interne notities voor deze upload\"></textarea>
      </div>
      <div>
        <label class=\"form-label\" for=\"uploader_name\">Uploader naam</label>
        <input class=\"form-input\" id=\"uploader_name\" name=\"uploader_name\" placeholder=\"Optioneel\" />
      </div>
      <div>
        <label class=\"form-label\" for=\"action\">Uploadmodus</label>
        <select class=\"form-input\" id=\"action\" name=\"action\">
          <option value=\"new\" selected>Nieuwe versie</option>
          <option value=\"replace\">Vervang nieuwste</option>
        </select>
      </div>
      <div class=\"modal-footer\">
        <button type=\"button\" class=\"btn-secondary\" data-close-upload>Annuleer</button>
        <button type=\"submit\" class=\"btn-primary\">Uploaden</button>
      </div>
      <div id=\"upload-progress\" class=\"progress hidden\">
        <div class=\"progress-bar\" role=\"progressbar\" style=\"width:0%\"></div>
      </div>
    </form>
  </div>
</div>
"""


def render_index(
    *,
    presentations: List[dict],
    service_types: Iterable[str],
    filters: dict,
    message: Optional[Tuple[str, str]],
    base_url: str,
) -> str:
    def format_size(value: Optional[int]) -> str:
        if not value:
            return "Onbekend"
        return f"{value / 1024 / 1024:.2f} MB"

    cards = []
    for presentation in presentations:
        service = html.escape(presentation.get("service_type") or "Onbekend")
        logical_name = html.escape(presentation.get("logical_name", ""))
        description = html.escape(presentation.get("description") or "Geen beschrijving")
        updated_at = format_datetime(presentation.get("updated_at"))
        latest_size = format_size(presentation.get("latest_size"))
        share_url = f"{base_url}/presentations/{presentation['id']}"
        download_url = f"/presentations/{presentation['id']}/download/latest"
        detail_url = f"/presentations/{presentation['id']}"
        cards.append(
            f"""
      <article class=\"presentation-card\">
        <header class=\"flex items-center justify-between\">
          <h2 class=\"text-xl font-semibold text-slate-900\">{logical_name}</h2>
          <span class=\"service-tag\" style=\"--tag-color: {service_color(presentation.get('service_type'))}\">{service}</span>
        </header>
        <p class=\"mt-2 text-sm text-slate-600\">{description}</p>
        <dl class=\"mt-3 grid grid-cols-2 gap-2 text-sm\">
          <div>
            <dt class=\"text-slate-500\">Laatst geüpdatet</dt>
            <dd class=\"font-medium\">{updated_at}</dd>
          </div>
          <div>
            <dt class=\"text-slate-500\">Grootte (laatste)</dt>
            <dd class=\"font-medium\">{latest_size}</dd>
          </div>
        </dl>
        <div class=\"mt-4 flex flex-wrap gap-2\">
          <a class=\"btn-primary\" href=\"{download_url}\">Download nieuwste</a>
          <a class=\"btn-secondary\" href=\"{detail_url}\">Bekijk versies</a>
          <button class=\"btn-secondary\" type=\"button\" data-copy=\"{html.escape(share_url)}\">Deel link</button>
        </div>
      </article>
            """
        )

    cards_html = "\n".join(cards)
    if not cards:
        cards_html = (
            "<div class=\"rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-slate-500\">"
            "Nog geen presentaties gevonden. Gebruik de uploadknop om te beginnen." "</div>"
        )

    service_options = "".join(
        f"<option value=\"{html.escape(service)}\" {'selected' if filters.get('service') == service else ''}>{html.escape(service)}</option>"
        for service in service_types
    )

    sort = filters.get("sort", "newest")

    content = f"""
<section class=\"rounded-xl bg-white p-6 shadow-sm\">
  <form method=\"get\" class=\"grid gap-4 md:grid-cols-4\">
    <div class=\"md:col-span-2\">
      <label class=\"form-label\">Zoeken</label>
      <input type=\"search\" name=\"q\" value=\"{html.escape(filters.get('q', ''))}\" placeholder=\"Naam, beschrijving of dienst\" class=\"form-input\" />
    </div>
    <div>
      <label class=\"form-label\">Diensttype</label>
      <select name=\"service\" class=\"form-input\">
        <option value=\"\">Alle</option>
        {service_options}
      </select>
    </div>
    <div>
      <label class=\"form-label\">Sortering</label>
      <select name=\"sort\" class=\"form-input\">
        <option value=\"newest\" {'selected' if sort == 'newest' else ''}>Nieuwste eerst</option>
        <option value=\"oldest\" {'selected' if sort == 'oldest' else ''}>Oudste eerst</option>
        <option value=\"size\" {'selected' if sort == 'size' else ''}>Grootste bestanden</option>
      </select>
    </div>
    <div>
      <label class=\"form-label\">Van datum</label>
      <input type=\"date\" name=\"start\" value=\"{html.escape(filters.get('start', ''))}\" class=\"form-input\" />
    </div>
    <div>
      <label class=\"form-label\">Tot datum</label>
      <input type=\"date\" name=\"end\" value=\"{html.escape(filters.get('end', ''))}\" class=\"form-input\" />
    </div>
    <div class=\"md:col-span-4 flex items-end justify-end gap-2\">
      <a href=\"/\" class=\"btn-secondary\">Reset</a>
      <button type=\"submit\" class=\"btn-primary\">Toepassen</button>
    </div>
  </form>
</section>
<section class=\"mt-6 grid gap-4 lg:grid-cols-2\">
  {cards_html}
</section>
"""
    return render_base(
        title="ProSync — Overzicht",
        content=content,
        service_types=service_types,
        message=message,
    )


def render_detail(
    *,
    presentation: dict,
    versions: List[dict],
    service_types: Iterable[str],
    message: Optional[Tuple[str, str]],
    base_url: str,
) -> str:
    logical_name = html.escape(presentation.get("logical_name", ""))
    description = html.escape(presentation.get("description") or "Geen beschrijving beschikbaar.")
    service = html.escape(presentation.get("service_type") or "Onbekend")
    created_at = format_datetime(presentation.get("created_at"))
    updated_at = format_datetime(presentation.get("updated_at"))

    latest = presentation.get("latest_version", {}) or {}
    latest_uploader = latest.get("uploader_name") or latest.get("uploader_ip") or "Onbekend"
    latest_uploader = html.escape(latest_uploader)
    share_url = f"{base_url}/presentations/{presentation['id']}"

    rows = []
    for version in versions:
        uploader = html.escape(version.get("uploader_name") or "Onbekend")
        uploader_ip = html.escape(version.get("uploader_ip") or "")
        filename = html.escape(version.get("original_filename") or "")
        size_mb = f"{(version.get('file_size', 0) / 1024 / 1024):.2f} MB"
        checksum = html.escape(version.get("checksum") or "")
        note = html.escape(version.get("note") or "—")
        created = format_datetime(version.get("created_at"))
        download_url = f"/presentations/versions/{version['id']}/download"
        share_version = f"{base_url}/presentations/versions/{version['id']}/download"
        restore_url = f"/presentations/versions/{version['id']}/restore"
        rows.append(
            f"""
        <tr>
          <td class=\"px-4 py-3 font-semibold\">v{version.get('version_number')}</td>
          <td class=\"px-4 py-3\">{created}</td>
          <td class=\"px-4 py-3\">
            <div class=\"font-medium text-slate-800\">{uploader}</div>
            <div class=\"text-xs text-slate-500\">{uploader_ip}</div>
          </td>
          <td class=\"px-4 py-3\">
            <div class=\"font-medium text-slate-800\">{filename}</div>
            <div class=\"text-xs text-slate-500\">{size_mb}</div>
          </td>
          <td class=\"px-4 py-3 text-xs font-mono text-slate-500\">{checksum}</td>
          <td class=\"px-4 py-3 text-slate-600\">{note}</td>
          <td class=\"px-4 py-3 text-right\">
            <div class=\"flex justify-end gap-2\">
              <a class=\"btn-secondary\" href=\"{download_url}\">Download</a>
              <button class=\"btn-secondary\" type=\"button\" data-copy=\"{html.escape(share_version)}\">Deel</button>
              <form method=\"post\" action=\"{restore_url}\" onsubmit=\"return confirm('Weet je zeker dat je deze versie wilt herstellen?')\">
                <button class=\"btn-primary\" type=\"submit\">Restore</button>
              </form>
            </div>
          </td>
        </tr>
            """
        )

    rows_html = "\n".join(rows) if rows else ""

    content = f"""
<nav class=\"mb-4 text-sm text-slate-500\">
  <a href=\"/\" class=\"text-blue-600 hover:underline\">← Terug naar overzicht</a>
</nav>
<section class=\"rounded-xl bg-white p-6 shadow-sm\">
  <header class=\"flex flex-wrap items-start justify-between gap-4\">
    <div>
      <h2 class=\"text-2xl font-semibold text-slate-900\">{logical_name}</h2>
      <p class=\"mt-1 text-sm text-slate-600\">{description}</p>
    </div>
    <div class=\"flex flex-col items-end gap-2\">
      <span class=\"service-tag service-tag-lg\" style=\"--tag-color: {service_color(presentation.get('service_type'))}\">{service}</span>
      <button class=\"btn-secondary\" type=\"button\" data-copy=\"{html.escape(share_url)}\">Deel presentatie</button>
    </div>
  </header>
  <dl class=\"mt-6 grid gap-4 sm:grid-cols-3\">
    <div>
      <dt class=\"text-xs uppercase tracking-wide text-slate-500\">Aangemaakt</dt>
      <dd class=\"text-sm font-medium text-slate-800\">{created_at}</dd>
    </div>
    <div>
      <dt class=\"text-xs uppercase tracking-wide text-slate-500\">Laatste update</dt>
      <dd class=\"text-sm font-medium text-slate-800\">{updated_at}</dd>
    </div>
    <div>
      <dt class=\"text-xs uppercase tracking-wide text-slate-500\">Laatste uploader</dt>
      <dd class=\"text-sm font-medium text-slate-800\">{latest_uploader}</dd>
    </div>
  </dl>
</section>
<section class=\"mt-6 overflow-hidden rounded-xl bg-white shadow-sm\">
  <div class=\"overflow-x-auto\">
    <table class=\"min-w-full divide-y divide-slate-200 text-sm\">
      <thead class=\"bg-slate-50 text-xs uppercase tracking-wide text-slate-500\">
        <tr>
          <th class=\"px-4 py-3 text-left\">Versie</th>
          <th class=\"px-4 py-3 text-left\">Datum</th>
          <th class=\"px-4 py-3 text-left\">Uploader</th>
          <th class=\"px-4 py-3 text-left\">Bestand</th>
          <th class=\"px-4 py-3 text-left\">Checksum</th>
          <th class=\"px-4 py-3 text-left\">Notitie</th>
          <th class=\"px-4 py-3 text-right\">Acties</th>
        </tr>
      </thead>
      <tbody class=\"divide-y divide-slate-200 bg-white\">
        {rows_html}
      </tbody>
    </table>
  </div>
</section>
"""
    return render_base(
        title=f"ProSync — {presentation.get('logical_name', '')}",
        content=content,
        service_types=service_types,
        message=message,
    )


def format_datetime(value: Optional[str]) -> str:
    if not value:
        return "Onbekend"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return value
