# Database Patterns

- PostgreSQL on Neon (serverless) — connection pool settings in database.py are tuned for this, do not change them
- No migration system — schema changes mean editing app/models.py and relying on SQLAlchemy create_all
- PropertyParameter is versioned: when updating a property, set effective_to on the old record and insert a new one
- Always filter active parameters: `.filter(PropertyParameter.effective_to == None)`
- MiscExpenseLog and PropertyReconLog are deleted + re-inserted each reconciliation run (idempotent by design)
- Never call `db.commit()` outside of a route or dedicated helper — let the caller control the transaction
