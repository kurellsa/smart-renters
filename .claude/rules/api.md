# FastAPI Patterns

- DB sessions: `db: Session = Depends(get_db)` — never `SessionLocal()` directly
- Routes live in `app/main.py` — keep them thin, delegate logic to modules
- Use `logger = logging.getLogger(__name__)` — never `print()`
- Imports are absolute: `from app.module import thing`
- Pydantic schemas for all request/response validation go in `app/schemas.py`
- Responses: use `HTMLResponse` for templates, `StreamingResponse` for file downloads
- File uploads use `UploadFile` with `await file.read()` for async reading
