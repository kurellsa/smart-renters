from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import ReconciliationSummary
from app.utils import send_reconciliation_email
from datetime import date

def run_bank_reconciliation(db: Session, stmt_dates: dict, calc_totals: dict, prop_counts: dict, bank_data: dict, source_files: dict, target_month: date):
    reconcile_summary = {}

    for merchant, pdf_total in calc_totals.items():
        bank_total = bank_data.get(merchant, 0.0)
        diff = pdf_total - bank_total
        status = "MATCHED" if abs(diff) < 0.01 else "DISCREPANCY"

        # 2. Load the Table (ReconciliationLog)
        new_log = ReconciliationSummary(
            statement_date=stmt_dates.get(merchant, "Unknown"),
            merchant_group=merchant,
            statement_total=pdf_total,
            bank_transaction=bank_total,
            difference=diff,
            status=status,
            property_count=prop_counts.get(merchant, 0),
            source_file=source_files.get(merchant, "Unknown")
        )
        db.add(new_log)
        
        reconcile_summary[merchant] = {
            "status": status, 
            "pdf_total": pdf_total, 
            "bank_total": bank_total, 
            "diff": diff
        }

    db.commit() # Save logs to DB
    
    # 3. Trigger Email
    send_reconciliation_email(reconcile_summary, target_month)
    
    return reconcile_summary
