## Quick context

- This is a small Flask web app that renders HTML forms, stores form payloads in a local SQLite DB, and generates Word (.docx) reports using docxtpl.
- Single main app entry: `app.py`. Templates live in `templates/`. The persistent SQLite DB is `instance/debitur.db`.

## Architecture (big picture)

- app.py is the canonical source of truth: it defines the DB model (`Debitur`), product categories (`PRODUCT_CATEGORIES`), request handlers (routes), and business logic (calculation + formatting).
- Product-based routing: each product key in `PRODUCT_CATEGORIES` maps to a form template (`template_form`) and a .docx template (`template_docx`). Example key: `prapurna_reguler`.
- Data flow: form POST -> `/simpan` converts/cleans numeric fields -> JSON-stored payload in `Debitur.data_lengkap` -> `/generate/<id>` reads payload, runs calculations (RPC/DSR), renders Docx via `docxtpl` and returns .docx file.

## Developer workflows (how to run & debug)

1. Install deps:

   pip install -r requirements.txt

2. Run locally:

   python app.py

   - The app auto-creates the SQLite DB (`instance/debitur.db`) on first run (`db.create_all()` in `app.py`).
   - The main process opens a browser (Timer -> webbrowser.open) when running locally.

3. Debugging tips:

- Exceptions during save or generation are printed to console and often returned as 500 responses. Check the console for stack traces.
- Calculation logic lives in `/generate/<id>` (see `calculate_pmt`, RPC/DSR blocks). If numbers look wrong, inspect `NOMINAL_KEYS` and the string cleaning in `/simpan`.

## Project-specific conventions & patterns

- Data storage: full form payload is serialized JSON and stored in `Debitur.data_lengkap` (text). Individual fields are not separate columns except `nama_pemohon`, `no_ktp`, `kategori`.
- Numeric formatting: the app expects numbers entered with '.' as thousands separators; before saving the code strips `.` for keys listed in `NOMINAL_KEYS`.
- Date formatting: `DATE_KEYS` lists form fields that the app converts from `YYYY-MM-DD` to `DD <IndonesianMonth> YYYY` before rendering the docx.
- Product extension: to add a new product, update `PRODUCT_CATEGORIES` in `app.py` with keys `template_form` (an HTML under `templates/`) and `template_docx` (a .docx file expected at the repo root).

## Integration points & external deps

- SQLite via Flask-SQLAlchemy (`requirements.txt`). DB file: `instance/debitur.db`.
- docxtpl for templating Word documents (`DocxTemplate`). Expected template files: e.g. `template_prapurna_reguler.docx`, or fallback `template_kredit.docx`.
- Upload endpoint `/upload_template` saves uploaded .docx to app root using the filename defined in `PRODUCT_CATEGORIES[kategori]['template_docx']`.

## Files to reference when coding

- `app.py` — main code, routes, model, calculations.
- `templates/*.html` — form templates (example: `form_prapurna_reguler.html`, `form_prapurna_takeover.html`), index and riwayat pages.
- `instance/debitur.db` — runtime SQLite DB (delete to reset state).
- `requirements.txt` — required packages: Flask, Flask-SQLAlchemy, docxtpl.

## Practical examples for agents

- To add a new product "x": add an entry in `PRODUCT_CATEGORIES`:

  'x': { 'nama': '...', 'template_form': 'form_x.html', 'template_docx': 'template_x.docx' }

  - Add `templates/form_x.html` following existing form patterns.
  - Provide `template_x.docx` at repo root or upload via `/admin`.

- To debug wrong currency formatting: check `NOMINAL_KEYS` and the cleaning loop in `/simpan` (removes '.'), then the formatting loop in `/generate/<id>` which re-adds '.' as thousands separator.

## Safety & small maintenance notes

- `SECRET_KEY` and `debug=True` are hard-coded in `app.py`. Treat these as secrets in a real deployment; remove `debug=True` and set `SECRET_KEY` via env var for production.
- The app stores sensitive personal fields (KTP numbers) in plain SQLite. If you extend or export data, follow data protection rules.

## What this file *doesn't* cover

- No test suite or CI config discovered. There are no unit tests or automated lint/format steps in the repo.

---

If any of the above is unclear or you'd like added examples (for example, a sample `form_x.html` snippet or a checklist for adding a docx template), tell me which section to expand and I'll update this file.
