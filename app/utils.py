import csv
import io
import os
import smtplib
from fastapi.responses import StreamingResponse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import pandas as pd
from datetime import datetime
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

html_templates = Jinja2Templates(directory="app/templates")

load_dotenv()

smtp_port = os.getenv("SMTP_PORT")
smtp_server = os.getenv("SMTP_SERVER")
sender = os.getenv("EMAIL_SENDER")
password = os.getenv("EMAIL_PASSWORD")
receiver = os.getenv("EMAIL_RECEIVER")

def parse_pdf_date(date_str):
    # Adjust the format string ("%m/%d/%Y") to match your PDF's format
    # e.g., "01/12/2026" -> datetime object
    try:
        return datetime.strptime(date_str.strip(), "%m/%d/%Y").date()
    except ValueError:
        # Fallback if different format
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()

# ---------- Generate Report to upload into Baselane --------------------- #
def generate_baselane_csv(records):
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Baselane specific headers
    writer.writerow(["Date", "Account", "Description", "Amount", "Category", "Property"])
    
    for rec in records:
        # Row 1: The Rent (Income)
        writer.writerow([
            rec.statement_date.strftime('%b %d %Y'),
            "Manually Added - Imported",
            f"Rent Received - {rec.merchant_group}",
            f"{rec.rent_paid:.2f}",
            "Rents",
            rec.address
        ])
        
        # Row 2: The Management Fee (Expense)
        # Only add if there is actually a fee
        if rec.management_fees != 0:
            writer.writerow([
                rec.statement_date.strftime('%b %d %Y'),
                "Manually Added - Imported",
                f"Management Fee - {rec.merchant_group}",
                f"-{abs(rec.management_fees):.2f}",
                "Management Fees",
                rec.address
            ])
    
    output.seek(0)
    return output

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
        df = df[["Date", "Merchant", "Amount"]]
        return df.to_dict(orient="records")
        
    except Exception as e:
        raise ValueError(f"Could not parse sheet: {str(e)}")

# ----------------- Email Notification ---------------------
def send_reconciliation_email(summary_data, target_month):

    display_month = target_month.strftime('%B %Y')
    link_month = target_month.strftime('%Y-%m')

    # 2. Render the HTML using Jinja2
    template = html_templates.get_template("email.html")
    html_content = template.render(
        display_month=display_month,
        link_month=link_month,
        summary_data=summary_data
    )

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = f"Reconciliation Report for {display_month}"

    # Build an HTML Table for the body
    rows = ""
    for merchant, data in summary_data.items():
        status_color = "green" if data['status'] == "MATCHED" else "red"
        rows += f"""
        <tr>
            <td>{merchant}</td>
            <td>${data['pdf_total']:.2f}</td>
            <td>${data['bank_total']:.2f}</td>
            <td style="color: {status_color};"><b>{data['status']}</b></td>
        </tr>
        """

    msg.attach(MIMEText(html_content, 'html'))    
    
    try:
        # 1. Connect with a clear timeout
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.set_debuglevel(0) # Change to 1 if you want to see the chat in logs
        
        # 2. Identify and Start Encryption
        server.ehlo() 
        server.starttls()
        
        # 3. Identify AGAIN (Crucial for Gmail after STARTTLS)
        server.ehlo() 
        
        # 4. Login and Send
        # Make sure .strip() is used to remove accidental spaces/newlines
        server.login(sender.strip(), password.strip())
        server.send_message(msg)
        server.quit()

        print("✅ Email sent successfully!")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ Authentication Failed: Check your App Password or SENDER_EMAIL.")
    except Exception as e:
        print(f"❌ Email Error: {e}")
    return False
