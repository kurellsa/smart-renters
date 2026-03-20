import logging
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import date
from typing import List
import re
from app.models import PropertyParameter, PropertyReconLog, MiscExpenseLog, RentalStatement
from app.schemas import PropertyDetail
from app.utils import extract_house_number, send_reconciliation_email

logger = logging.getLogger(__name__)

def run_reconciliation(db: Session, bank_df: pd.DataFrame, extracted_props: List[PropertyDetail], target_month: date):
    # --- 1. PRE-RECONCILIATION CLEANUP ---
    # Preserve user comments from existing recon logs before deleting
    existing_recon = db.query(PropertyReconLog).filter(
        extract('month', PropertyReconLog.month_year) == target_month.month,
        extract('year', PropertyReconLog.month_year) == target_month.year
    ).all()
    saved_recon_comments = {
        r.address: r.user_comment
        for r in existing_recon if r.user_comment
    }

    # Preserve user comments from existing misc logs before deleting
    existing_misc = db.query(MiscExpenseLog).filter(
        extract('month', MiscExpenseLog.month_year) == target_month.month,
        extract('year', MiscExpenseLog.month_year) == target_month.year
    ).all()
    saved_comments = {
        (m.description, m.amount): m.user_comment
        for m in existing_misc if m.user_comment
    }

    try:
        for model in [PropertyReconLog, MiscExpenseLog]:
            db.query(model).filter(
                extract('month', model.month_year) == target_month.month,
                extract('year', model.month_year) == target_month.year
            ).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup failed: {e}")
    
    # Pre-calculate bank totals by Merchant (e.g., 'GOGO PROPERTY...', 'Sure Realty...')
    bank_totals = bank_df.groupby('Merchant')['Amount'].sum().to_dict()

    # --- 3. CORE RECONCILIATION LOOP ---
    prop_master = db.query(PropertyParameter).filter(PropertyParameter.effective_to == None).all()
    all_house_nums = [p.address.split()[0] for p in prop_master]

    # 1. Initialize an empty list to store logs for the email
    recon_logs = []

    try:
        for prop in prop_master:
            addr_num = prop.address.split()[0] # e.g., "2560"
    
            # 2. Find match in PDF data by comparing ONLY the house numbers
            match = next((
                p for p in extracted_props 
                if p.address.split()[0] == addr_num
            ), None)

            actual_rent = match.rent_paid if match else 0.0
            actual_mgmt_fee = match.management_fees if match else 0.0
            manager_name = prop.property_management
            
            # B. Bank Deductions (HOA & Mortgage) via Description Search
            # Filter bank rows for this property's house number
            prop_txs = bank_df[bank_df['Description'].str.contains(addr_num, case=False, na=False)]
            
            actual_hoa = float(abs(prop_txs[prop_txs['Merchant'].str.contains('HOA', case=False, na=False)]['Amount'].sum()))
            actual_mortgage = float(abs(prop_txs[prop_txs['Merchant'].str.contains('Mortgage', case=False, na=False)]['Amount'].sum()))

            # C. Bulk Rent Deposit Check
            # Find the bank transaction for this property's manager
            merchant_key = next((m for m in bank_totals.keys() if manager_name.lower() in m.lower()), None)
            bank_net_deposit = bank_totals.get(merchant_key, 0.0) if merchant_key else 0.0

            # D. Status Determination
            v_rent = float(actual_rent - prop.expected_rent)
            v_mort = float(actual_mortgage - prop.mortgage_payment)

            # Special case: 407 Wards Creek Way HOA is quarterly
            if "407" in addr_num and actual_hoa == 0:
                v_hoa = 0.0 # Mark as matched for quarterly logic if payment exists
            else:
                v_hoa = float(actual_hoa - prop.hoa_fee)

            v_mgmt = float(actual_mgmt_fee - prop.management_fee)

            status = "MATCHED" if (v_rent == 0 and v_hoa == 0 and v_mort == 0 and v_mgmt == 0) else "DISCREPANCY"
            if actual_rent == 0 and actual_hoa == 0: status = "MISSING"

            log_entry = PropertyReconLog(
                month_year=target_month,
                address=prop.address,
                property_management=manager_name,
                target_rent=prop.expected_rent,
                actual_rent=actual_rent,
                rent_variance=v_rent,
                target_hoa=prop.hoa_fee,
                actual_hoa=actual_hoa,
                hoa_variance=v_hoa,
                target_mortgage=prop.mortgage_payment,
                actual_mortgage=actual_mortgage,
                mortgage_variance=v_mort,
                target_mgmt_fee=prop.management_fee,
                actual_mgmt_fee=actual_mgmt_fee,
                mgmt_fee_variance=v_mgmt,
                bank_deposit_total=bank_net_deposit,
                status=status,
                user_comment=saved_recon_comments.get(prop.address)
            )

            # Add to list AND the DB session
            recon_logs.append(log_entry)
            db.add(log_entry)

        # --- 4. MISCELLANEOUS EXPENSES ---
        misc_logs = []

        pattern = '|'.join(all_house_nums)
        # Exclude rows that are: (1) HOA/Mortgage for a known property, OR (2) management company deposits
        has_house_num = bank_df['Description'].str.contains(pattern, case=False, na=False)
        is_hoa_or_mortgage = bank_df['Merchant'].str.contains('HOA|Mortgage', case=False, na=False)
        is_mgmt_company = bank_df['Merchant'].str.contains('GOGO PROPERTY|Sure Realty', case=False, na=False)
        misc_df = bank_df[
            ~(has_house_num & is_hoa_or_mortgage) &
            ~is_mgmt_company
        ]

        for _, row in misc_df.iterrows():
            comment_key = (row['Description'], row['Amount'])
            misc_entry = MiscExpenseLog(
                month_year=target_month,
                date_cleared=row['Date'],
                description=row['Description'],
                amount=row['Amount'],
                category_suggestion=row.get('Merchant', 'Misc'),
                user_comment=saved_comments.get(comment_key)
            )
            db.add(misc_entry)
            misc_logs.append(misc_entry)

        db.commit()

        # Trigger Email
        send_reconciliation_email(recon_logs=recon_logs, misc_logs=misc_logs, target_month=target_month)

    except Exception as e:
        db.rollback()
        logger.error(f"Reconciliation Failed: {e}")
