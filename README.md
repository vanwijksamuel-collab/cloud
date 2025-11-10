# ProSync kerk-cloud

Een compacte WSGI-applicatie op basis van de Python-standaardbibliotheek waarmee kerkteams ProPresenter-presentaties kunnen uploaden, beheren en delen.

## Features
- Publieke overzichtspagina met zoeken, filteren en sorteren.
- Volledige versiegeschiedenis per presentatie inclusief restore-actie.
- Uploads met drag & drop, voortgangsbalk, validatie en metagegevens.
- Downloadlinks per presentatie en per versie (met kopieerknop).
- Automatische logging, checksums, health-endpoint en zip-backup.

## Vereisten
- Python 3.11+

## Installatie & start
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
python -m app.main
```
De app maakt automatisch een SQLite database (`prosync.db`) en bewaart uploads onder `uploads/`.

## Seed data (optioneel)
Voer `python seed_data.py` uit om een paar voorbeeldpresentaties toe te voegen.
