# Security Rules

- NEVER read, log, display, or commit the .env file or any of its values
- .env contains live credentials: Neon DB, Groq API key, Gmail app password — treat as production secrets
- LLM prompt inputs contain PDF text which may include PII — never log prompt contents
- File uploads: validate type before processing — only accept PDF (application/pdf) and CSV files
- Never force push to main branch
- Never hardcode credentials, connection strings, or API keys in source files
