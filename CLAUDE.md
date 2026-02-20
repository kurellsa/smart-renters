# SmartRental — Claude Instructions

## What This App Does
Rental property reconciliation system. Extracts payment data from 2 property managers'
PDF statements, compares against bank transactions, generates reports + Baselane CSV exports.

## Stack
- FastAPI + Python 3.13, Uvicorn (port 7860 for HuggingFace Spaces)
- PostgreSQL (Neon serverless) via SQLAlchemy ORM
- Groq API — Llama 3.3-70B for PDF data extraction
- PyMuPDF for PDF → text
- Jinja2 templates + Bootstrap 5
- HuggingFace OAuth for auth
- Docker deployment (Dockerfile at root)

## Key Files
- app/main.py       — all FastAPI routes
- app/models.py     — 4 DB tables: RentalStatement, PropertyParameter, PropertyReconLog, MiscExpenseLog
- app/schemas.py    — Pydantic validation schemas
- app/database.py   — DB session, get_db dependency
- app/llm.py        — Groq extraction → returns JSON {statement_date, property_management, properties[]}
- app/extract.py    — PDF → text via PyMuPDF (pages separated by \f)
- app/reconcile.py  — core reconciliation logic
- app/utils.py      — generate_baselane_csv, sheet_to_json, parse_any_date, send_reconciliation_email
- app/templates/    — index.html (upload UI), dashboard.html (report), history.html, parameters.html

## Critical Business Rules — DO NOT Change Without Discussion
- Exactly 2 property managers: "GOGO PROPERTY" and "SURE REALTY"
- Properties matched by house number (first digits in address string) — fragile but intentional
- Hard-coded reconciliation targets in main.py: GOGO=$6,751.50, SURE=$1,833.00 — intentional
- "407 Wards Creek Way" has quarterly HOA — the special case in reconcile.py is correct
- LLM prompt in llm.py maps "2560 Coventry St." — do not alter without testing

## Known Issues — Leave Alone Unless Explicitly Asked
- `app/llm copy.py` — old backup file, ignore completely
- Duplicate imports in main.py — pre-existing, do not "fix"
- schemas.py and models.py both define PropertyDetail — known duplication, do not merge

## Conventions
- DB sessions: ALWAYS use `get_db` dependency, NEVER call `SessionLocal()` directly
- Imports: absolute only (`from app.module import ...`)
- Logging: use module-level `logger = logging.getLogger(__name__)`, never `print()`
- Routes: keep thin — move heavy logic to dedicated modules
- Run locally: `uvicorn app.main:app --reload`

## Security — CRITICAL
- `.env` contains live credentials (DB, Groq API key, Gmail password). NEVER read it aloud,
  log its contents, display values, or commit it.
- LLM prompts may contain PDF data with PII — never log prompt contents
- File uploads: validate type before processing (PDF or CSV only)

## Git Workflow
- `origin` → GitHub (https://github.com/kurellsa/smart-renters) — source of truth
- `hf` → HuggingFace Spaces — live deployment (emergency manual push only)
- Develop on feature branches, open PRs to merge into `main`
- Merging to `main` triggers GitHub Actions → auto-deploys to HuggingFace Spaces
- Workflow file: `.github/workflows/deploy.yml` (uses HF_TOKEN GitHub secret)
- Never push directly to `hf` unless the GitHub Action is broken

## Environment Variables (loaded from .env via python-dotenv)
DATABASE_URL, GROQ_API_KEY, SMTP_SERVER, SMTP_PORT,
EMAIL_SENDER, EMAIL_RECEIVER, EMAIL_PASSWORD, HF_TOKEN, SECRET_KEY
