import csv
import io
import os
import smtplib
from fastapi.responses import StreamingResponse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import pandas as pd
import re
from datetime import datetime
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

html_templates = Jinja2Templates(directory="app/templates")

load_dotenv()

smtp_port = int(os.getenv("SMTP_PORT", "587"))
smtp_server = os.getenv("SMTP_SERVER")
sender = os.getenv("EMAIL_SENDER")
password = os.getenv("EMAIL_PASSWORD")
receiver = os.getenv("EMAIL_RECEIVER")

# ----------- Parse Date --------------------
def parse_any_date(date_val):
    """Converts various date strings into a proper Python date object."""
    if not date_val:
        return None
        
    # List the formats you expect to see
    formats = [
        "%Y-%m",    # From HTML Month Picker (2026-01)
        "%m/%d/%Y", # From PDF (01/12/2026)
        "%Y-%m-%d"  # Standard Database format
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(str(date_val).strip(), fmt).date()
        except ValueError:
            continue
            
    raise ValueError(f"Could not parse date: {date_val}")

# --  Extract House number. ------------ 
def extract_house_number(address_str):
    """Extracts only the leading digits from an address string."""
    if not address_str:
        return None
    match = re.search(r'^\d+', str(address_str).strip())
    return match.group() if match else None

# ----------- Get text for specified pages ------------
def get_relevant_text(text, page_indices):
    """
    Extracts specific pages by index (0-based).
    e.g., page_indices=[2] gets the 3rd page.
    """
    pages = text.split('\f')
    result = []
    
    for idx in page_indices:
        if 0 <= idx < len(pages):
            result.append(pages[idx])
            
    return "\n".join(result) if result else text

# ------- csv to Json conversion 
def sheet_to_json(csv_file):
    # 1. Read the raw bytes
    content = csv_file.file.read()
    csv_file.file.seek(0) # Reset pointer
    
    filename = csv_file.filename.lower()
    
    try:
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            # Handle Excel files
            df = pd.read_excel(io.BytesIO(content))
        else:
            # Handle CSV files with a fallback for encoding
            try:
                df = pd.read_csv(io.BytesIO(content), encoding='utf-8')
            except UnicodeDecodeError:
                # Fallback for files saved in Excel CSV format (Latin-1)
                df = pd.read_csv(io.BytesIO(content), encoding='latin1')
        
        # Select your required columns
        df = df[["Date", "Merchant", "Description", "Amount"]]
        return df.to_dict(orient="records")
        
    except Exception as e:
        raise ValueError(f"Could not parse sheet: {str(e)}")

## ---------------- Email -----------------------------
def send_reconciliation_email(recon_logs, misc_logs, target_month):
    display_month = target_month.strftime('%B %Y')
    link_month = target_month.strftime('%Y-%m')

    # 1. Aggregate Totals
    total_actual_rent = sum(log.actual_rent for log in recon_logs)
    total_target_rent = sum(log.target_rent for log in recon_logs)
    
    total_actual_hoa = sum(log.actual_hoa for log in recon_logs)
    total_target_hoa = sum(log.target_hoa for log in recon_logs)
    
    total_actual_mort = sum(log.actual_mortgage for log in recon_logs)
    total_target_mort = sum(log.target_mortgage for log in recon_logs)

    # 2. Structure Component Data
    components = [
        {"name": "Rent Reconciliation", "actual": total_actual_rent, "target": total_target_rent, 
         "status": "MATCHED" if total_actual_rent == total_target_rent else "DISCREPANCY"},
        {"name": "HOA Fees Audit", "actual": total_actual_hoa, "target": total_target_hoa, 
         "status": "MATCHED" if total_actual_hoa == total_target_hoa else "DISCREPANCY"},
        {"name": "Mortgage Audit", "actual": total_actual_mort, "target": total_target_mort, 
         "status": "MATCHED" if total_actual_mort == total_target_mort else "DISCREPANCY"}
    ]

    # 3. Render the Template
    # Ensure html_templates is your Jinja2 Environment (e.g., Jinja2Templates)
    template = html_templates.get_template("email.html")
    html_content = template.render(
        display_month=display_month,
        link_month=link_month,
        components=components,
        misc_logs=misc_logs
    )

    # 4. Email Sending Logic
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = f"📊 Smart LLC - Reconciliation Report: {display_month}"
    msg.attach(MIMEText(html_content, 'html'))    
    
    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
        logger.debug(f"SMTP Server: {smtp_server} | Port: {smtp_port} | From: {sender} | To: {receiver}")
        server.starttls()
        server.login(sender.strip(), password.strip())
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent successfully for {display_month}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False