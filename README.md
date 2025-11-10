# ProSync kerk-cloud

Een compacte Flask-applicatie waarmee kerkteams ProPresenter-presentaties kunnen uploaden, beheren en delen.

## Features
- Publieke overzichtspagina met zoeken, filteren en sorteren.
- Volledige versiegeschiedenis per presentatie inclusief restore-actie.
- Uploads met drag & drop, voortgangsbalk, validatie en metagegevens.
- Downloadlinks per presentatie en per versie (met kopieerknop).
- Automatische logging, checksums, health-endpoint en zip-backup.

## Vereisten
- Python 3.11+
- Pipenv/pip om dependencies te installeren.

## Installatie & start
```bash
pip install -r requirements.txt
export FLASK_APP=app.main:app
flask --app app.main run --host=0.0.0.0 --port=8000
```
De app maakt automatisch een SQLite database (`prosync.db`) en bewaart uploads onder `uploads/`.

## Seed data (optioneel)
Voer `python seed_data.py` uit om een paar voorbeeldpresentaties toe te voegen.
