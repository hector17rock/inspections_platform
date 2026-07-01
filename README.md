# Inspections Platform
A lightweight inspection/audit portal built with **FastAPI** and **server-rendered HTML** (Jinja2). It stores data in **SQLite**, generates **PDF reports**, and ships a small **PWA** experience (manifest + service worker).

This README intentionally avoids using brand/company names.

## What’s in this repo
### High-level architecture
- **Backend**: FastAPI app with route handlers and service modules.
- **Frontend**: Jinja templates + static assets (JS, PWA files, images, uploads).

### Directory layout
- `Backend/`
  - `main.py`: FastAPI app and routes
  - `paths.py`: repo-relative path helpers (points to `Frontend/static` and `Frontend/templates`)
  - `*_service.py`: domain logic (audits, availability, CCTV, etc.)
  - `requirements.txt`: runtime dependencies (pip)
  - `audits.db`: SQLite database file (local/dev)
  - `audits_archive/`: generated exports (PDF/TXT)
- `Frontend/`
  - `templates/`: Jinja2 HTML templates
  - `static/`: static files (JS bundles, icons, manifest, service worker, images, uploads)

## Features
- Live operational dashboard (store-scoped) with periodic refresh.
- Inspection/audit workflows:
  - list, create, view details, delete
  - PDF export/download
- Availability inspection workflow with:
  - modular evaluation cards
  - item-level details (UPC/QTY, on-hand vs physical, value calculations)
  - barcode SVG rendering for print-friendly pages
- CCTV investigation workflow:
  - timeline/events
  - optional photo uploads
  - PDF generation
- PWA basics:
  - `Frontend/static/manifest.json`
  - `Frontend/static/sw.js` (simple caching strategy)

## Requirements
- Python 3.13+

## Quickstart (local)
From the repository root:
1) Create a virtual environment:
- `python3 -m venv Backend/.venv`
2) Install dependencies:
- `Backend/.venv/bin/pip install -U pip`
- `Backend/.venv/bin/pip install -r Backend/requirements.txt`
3) Run the server (development):
- `cd Backend && ../Backend/.venv/bin/uvicorn main:app --reload`
4) Open in your browser:
- http://127.0.0.1:8000/

## Configuration
See `Backend/config.py`.

Common settings:
- `USE_MOCK_DATA`: toggles mock/demo data vs real API integration.
- `REFRESH_INTERVAL_SEC`: dashboard refresh interval.

Security note:
- Do not commit real credentials. Use environment variables or a local, untracked file.

## Data storage
### SQLite database
- Default DB file: `Backend/audits.db`
- Tables are created automatically on startup (see `*_service.py` init functions).

Reset (local/dev):
- Stop the server
- Delete `Backend/audits.db`
- Restart the server (tables will be recreated)

### Generated files
- Exports: `Backend/audits_archive/`
  - TXT summaries
  - PDF reports (generated with `fpdf2`)
- Uploaded images: `Frontend/static/uploads/` (served as `/static/uploads/...`)

## Key endpoints
UI pages:
- `GET /`: main portal landing page
- `GET /orders-dashboard`: live dashboard page
- `GET /audits`: audit list
- `GET /audits/new`: new audit form
- `GET /audits/{id}`: audit detail
- `GET /cctv`: CCTV list
- `GET /cctv/new`: CCTV form
- `GET /cctv/{id}`: CCTV detail
- `GET /availability`: availability list
- `GET /availability/new`: availability form
- `GET /availability/{id}`: availability detail

Downloads and utilities:
- `GET /audits/{id}/pdf`: download audit PDF
- `GET /cctv/{id}/pdf`: download CCTV PDF
- `GET /availability/{id}/pdf`: download availability PDF
- `GET /availability/barcode/{upc}`: barcode SVG
- `GET /validate-store?store=####`: store validation
- `GET /debug-db`: basic DB debug info (dev helper)

Partials:
- `GET /orders?store=####`: HTML partial used by the live dashboard

## Corporate typography (Bogle)
The UI is configured to use **Bogle** through `Frontend/static/corporate-font.css`.

Two modes:
- **Local install**: if Bogle is installed on the system, the browser will use it.
- **Bundled webfonts** (license required): add these files:
  - `Frontend/static/fonts/Bogle-Regular.woff2`
  - `Frontend/static/fonts/Bogle-Bold.woff2`
  - `Frontend/static/fonts/Bogle-Black.woff2`

If you see 404s for the `.woff2` files in the server logs, it means the webfont files have not been added yet.

## PWA / caching notes
- Service worker: `Frontend/static/sw.js`
- If you change static assets and the browser keeps old styles/scripts:
  - hard refresh the page
  - or clear site data (storage + cache)
  - or unregister the service worker for the site

## PDF generation
This project uses two approaches depending on the page:
- Server-side PDF generation via `fpdf2` (download endpoints).
- Client-side HTML → PDF via `html2pdf.bundle.min.js` for print-friendly pages.

## Troubleshooting
### Server starts but pages fail to render
- Ensure `Frontend/templates/` exists and contains the expected templates.
- Ensure `Frontend/static/` exists and is mounted at `/static`.
- The backend resolves these paths via `Backend/paths.py`.

### Font not applied
- Confirm templates include `/static/corporate-font.css`.
- If you want bundled fonts, add the `.woff2` files under `Frontend/static/fonts/`.

### Reset local data
- Delete `Backend/audits.db` (local/dev only).

## Development notes
- The backend is intentionally simple (no separate SPA build). Templates and static files are served directly.
- Keep large binary uploads out of the repo unless you intentionally want them versioned.
