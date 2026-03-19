"""One-time migration: add management fee columns to property_recon_log."""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
if not url:
    raise SystemExit("DATABASE_URL not set in .env")

conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

columns = [
    ("target_mgmt_fee",   "FLOAT DEFAULT 0.0"),
    ("actual_mgmt_fee",   "FLOAT DEFAULT 0.0"),
    ("mgmt_fee_variance", "FLOAT DEFAULT 0.0"),
]

for col, col_type in columns:
    cur.execute(f"""
        ALTER TABLE property_recon_log
        ADD COLUMN IF NOT EXISTS {col} {col_type};
    """)
    print(f"  OK  added column: {col}")

cur.close()
conn.close()
print("\nMigration complete.")
