from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import ReconciliationSummary, PropertyParameter
from app.utils import send_reconciliation_email
from datetime import date

def run_reconciliation(db: Session, stmt_dates: dict, calc_totals: dict, prop_counts: dict, bank_amounts: dict, bank_data: dict, source_files: dict, target_month: date):
    
    ## 1. Macro Reconciliation at summary level
    reconcile_summary = {}

    for merchant, pdf_total in calc_totals.items():
        bank_total = bank_amounts.get(merchant, 0.0)
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
    
    # 3. Micro Reconciliation (at Property level)
    targets = db.query(PropertyParameter).filter(PropertyParameter.effective_to == None).all()

    for prop in targets:
        # Filter bank data for this property (using a simplified address match)
        addr_key = prop.address.split()[0]  # Matches "1047" from "1047 MILLISON PL"
        prop_txs = bank_data[bank_data['Description'].str.contains(addr_key, case=False, na=False)]
        
        # Sum Actuals by Category
        actual_r = prop_txs[prop_txs['Category'].str.contains('Rent', na=False)]['Amount'].sum()
        actual_m = abs(prop_txs[prop_txs['Category'].str.contains('Mortgage', na=False)]['Amount'].sum())
        actual_h = abs(prop_txs[prop_txs['Category'].str.contains('HOA', na=False)]['Amount'].sum())

        # Logic to determine status
        v_rent = actual_r - prop.expected_rent
        status = "MATCHED" if v_rent == 0 else "DISCREPANCY"

        # Save to detailed log
        db.add(PropertyReconLog(
            month_year=target_month,
            address=prop.address,
            target_rent=prop.expected_rent,
            actual_rent=actual_r,
            rent_variance=v_rent,
            target_mortgage=prop.mortgage_payment,
            actual_mortgage=actual_m,
            target_hoa=prop.hoa_fee,
            actual_hoa=actual_h,
            status=status
        ))

    # 4. Misc Expenses (Requirement 4)
    # Filter for anything that isn't Rent, Mortgage, or HOA
    known_cats = ['Rent', 'Mortgage', 'HOA']
    misc_df = bank_df[~bank_df['Category'].str.contains('|'.join(known_cats), case=False, na=False)]
    
    # You can return these to the UI or save them to a 'MiscLog' table
    misc_list = misc_df.to_dict(orient='records')

    db.commit()

    # 3. Trigger Email
    send_reconciliation_email(reconcile_summary, target_month)

    return {"status": "Complete", "misc": misc_list}

    
