Add a new FastAPI route to this project for: $ARGUMENTS

Steps:
1. Read app/main.py to understand existing route patterns
2. Read app/models.py and app/schemas.py for relevant data shapes
3. Add any needed Pydantic schema to schemas.py
4. Add the route to main.py — keep it thin, move heavy logic to a helper module
5. Use `db: Session = Depends(get_db)` for any database access
6. Use `logger` for logging, never `print()`
7. Return appropriate response type (HTMLResponse, JSONResponse, StreamingResponse)
