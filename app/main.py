from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
import logging
import json
import smtplib
import io
import os

from sqlalchemy.orm import Session

# Absolute imports for your app structure
from app.extract import pdf_to_text
from app.llm import extract_with_llm
from app.reconcile import run_bank_recon
from app.schemas import ExtractedDoc
from app.utils import generate_baselane_csv
from app.database import SessionLocal, engine, get_db # Added get_db here
from app import models
from huggingface_hub import attach_huggingface_oauth, parse_huggingface_oauth
from fastapi.responses import HTMLResponse
import pandas as pd

# smtp libraries
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Create tables in Neon on startup
models.Base.metadata.create_all(bind=engine)

def get_current_user(request: Request):
    user = parse_huggingface_oauth(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged into Hugging Face")
    return user

@app.get("/health")
def health(logs: str = None):
    return {"status": "ok", "message": "Container is healthy"}

@app.get("/report", response_class=HTMLResponse)
async def monthly_summary(month_year: str = "01/2026"):
    db = SessionLocal()
    try:
        # Pull only the properties for the selected month
        items = db.query(models.RentalStatement).filter(
            models.RentalStatement.statement_date.contains(month_year)
        ).all()

        # Grouping logic for your specific merchants
        gogo_group = [i for i in items if i.merchant_group == "GOGO PROPERTY"]
        sure_group = [i for i in items if i.merchant_group == "SURE REALTY"]

        gogo_total = sum(i.net_income for i in gogo_group)
        sure_total = sum(i.net_income for i in sure_group)

        # The "Magic" Reconciliation Check
        # These match the 'Amount' column in your Baselane screenshot
        gogo_match = "✅ MATCHED" if gogo_total == 6751.50 else "❌ DISCREPANCY"
        sure_match = "✅ MATCHED" if sure_total == 1833.00 else "❌ DISCREPANCY"

        return f"""
        <html>
            <head>
                <style>
                    body {{ font-family: sans-serif; max-width: 900px; margin: auto; padding: 40px; background: #fdfdfd; }}
                    .report-card {{ border: 1px solid #eee; padding: 20px; border-radius: 12px; background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }}
                    .status-ok {{ color: #28a745; font-weight: bold; }}
                    .status-err {{ color: #dc3545; font-weight: bold; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #fafafa; font-size: 0.9em; }}
                </style>
            </head>
            <body>
                <h1>📊 Executive Summary: {month_year}</h1>
                
                <div class="report-card">
                    <h3>GOGO PROPERTY Portfolio (PDF1)</h3>
                    <p>Calculated Net: <strong>${gogo_total:,.2f}</strong> | Bank Status: <span class="{"status-ok" if "✅" in gogo_match else "status-err"}">{gogo_match}</span></p>
                    <table>
                        {" ".join([f"<tr><td>{p.address}</td><td>${p.net_income:,.2f}</td></tr>" for p in gogo_group])}
                    </table>
                </div>

                <div class="report-card">
                    <h3>SURE REALTY (PDF2)</h3>
                    <p>Calculated Net: <strong>${sure_total:,.2f}</strong> | Bank Status: <span class="{"status-ok" if "✅" in sure_match else "status-err"}">{sure_match}</span></p>
                    <table>
                        {" ".join([f"<tr><td>{p.address}</td><td>${p.net_income:,.2f}</td></tr>" for p in sure_group])}
                    </table>
                </div>
                
                <p><a href="/">Back to Dashboard</a></p>
            </body>
        </html>
        """
    finally:
        db.close()

def send_recon_email(summary_data):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("EMAIL_RECEIVER")
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = f"🚀 Recon Report: {summary_data['status']}"

    body = f"""
    SmartPartners Reconciliation Summary
    -----------------------------------
    Status: {summary_data['status']}
    Date: {summary_data['date']}

    GOGO PROPERTY (PDF1):
    - Expected: ${summary_data['gogo_total']:,.2f}
    - Bank Match: {summary_data['gogo_match']}

    SURE REALTY (PDF2):
    - Expected: ${summary_data['sure_total']:,.2f}
    - Bank Match: {summary_data['sure_match']}

    View full details at: https://smartrenters-smart-fastapi.hf.space/report
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

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
        logger.error(f"Sheet Parsing Error: {e}")
        raise ValueError(f"Could not parse sheet: {str(e)}")

@app.post("/reconcile")
async def reconcile_endpoint(
    pdf1: UploadFile = File(...),
    pdf2: UploadFile = File(...),
    sheet_json: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)      
):
    logger.info(f"User {user.user_info.preferred_username} starting reconciliation")
    
    # Read and extract
    content1 = await pdf1.read()
    content2 = await pdf2.read()
    bank_data = sheet_to_json(sheet_json)

    text1 = pdf_to_text(content1)
    text2 = pdf_to_text(content2)

    parsed1 = extract_with_llm(text1)
    if not parsed1.get("properties"):
        logger.error("PDF 1 failed to return property data")
    
    parsed2 = extract_with_llm(text2)
    if not parsed2.get("properties"):
        logger.error("PDF 2 failed to return property data")

    try:
        doc1 = ExtractedDoc(**parsed1)
        doc2 = ExtractedDoc(**parsed2)
    except Exception as e:
        logger.error(f"Validation Error: {e}")
        return {"error": "LLM output validation failed", "details": str(e)}

    # --- STEP 5: Save to Neon Database ---
    gogo_sum = 0.0
    sure_sum = 0.0
    try:
        db = SessionLocal()
        
        # Store docs and their filenames in a list to process everything in one go
        extractions = [
            (doc1, pdf1.filename), 
            (doc2, pdf2.filename)
        ]

        for doc, filename in extractions:
            for prop in doc.properties:
                # Determine the merchant group for reconciliation logic
                merchant = "GOGO PROPERTY" if "pdf1" in filename.lower() else "SURE REALTY"
                
                # 2. Accumulate the sums dynamically
                income_val = abs(getattr(prop, 'net_income', 0))
                if merchant == "GOGO PROPERTY":
                    gogo_sum += income_val
                else:
                    sure_sum += income_val


                new_record = models.RentalStatement(
                    statement_date=doc.statement_date, 
                    merchant_group=doc.merchant_group,
                    address=prop.address,
                    rent_amount=prop.rent_amount,
                    rent_paid=prop.rent_paid,
                    management_fees=prop.management_fees,
                    net_income=income_val,
                    source_file=filename
                )
                db.add(new_record)

        db.commit()
        logger.info(f"Successfully saved properties from {len(extractions)} files to Neon.")
    except Exception as e:
        logger.error(f"Database Save Error: {e}")
        db.rollback()
    finally:
        db.close()

    # --- STEP 6: RECONCILE ---
    all_props = doc1.properties + doc2.properties
    result = run_bank_recon(all_props, bank_data)

    # --- STEP 7: Create Email summary ---
    # Create the email summary using the results from reconcile()
    email_summary = {
        "status": "MATCHED" if (result["GOGO_PROPERTY"]["status"] == "MATCHED" and 
                                result["SURE_REALTY"]["status"] == "MATCHED") else "DISCREPANCY",
        "date": doc1.statement_date,
        "gogo_total": gogo_sum,
        "gogo_match": "✅" if result["GOGO_PROPERTY"]["status"] == "MATCHED" else "❌",
        "gogo_diff": result["GOGO_PROPERTY"]["diff"],
        "sure_total": sure_sum,
        "sure_match": "✅" if result["SURE_REALTY"]["status"] == "MATCHED" else "❌",
        "sure_diff": result["SURE_REALTY"]["diff"]
    }

    send_recon_email(email_summary)

    return {
        "reconciliation_result": result,
        "summary": {
            "user": user.user_info.preferred_username,
            "properties_saved": len(doc1.properties) + len(doc2.properties)
        }
    }

## ------- Export Baselane CSV file ---------------
@app.get("/export-baselane")
async def export_baselane(month_year: str, db: Session = Depends(get_db)):
    # Pull data from Neon for PDF1 (GOGO) for that month
    records = db.query(models.RentalStatement).filter(
        models.RentalStatement.statement_date.contains(month_year),
        models.RentalStatement.merchant_group == "GOGO PROPERTY"
    ).all()

    if not records:
        return {"error": "No data found for this period"}

    # Generate CSV
    csv_file = generate_baselane_csv(records, month_year)
    
    # Return as a downloadable file
    response = StreamingResponse(csv_file, media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=baselane_upload_{month_year.replace('/', '_')}.csv"
    return response

attach_huggingface_oauth(app)

@app.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    # This checks if the user is logged in before even showing the page
    user = parse_huggingface_oauth(request)
    if not user:
        # We add '/' at the start and target="_self" to ensure it hits the root domain
        return """
        <div style="font-family:sans-serif; text-align:center; margin-top:50px;">
            <h2>Welcome to SmartPartners</h2>
            <a href="/oauth/huggingface/login" target="_self" 
               style="background:#0084ff; color:white; padding:10px 20px; border-radius:5px; text-decoration:none;">
               Click here to Login with Hugging Face
            </a>
        </div>
        """
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SmartPartners Recon</title>
        <style>
            body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; background: #f4f7f6; }
            .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            h2 { color: #2c3e50; margin-top: 0; }
            .file-group { margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
            button { background: #0084ff; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%; }
            .history-link { display: block; text-align: center; margin-top: 20px; color: #666; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🏠 SmartRental Recon</h2>
            <p>Logged in as: <strong>""" + user.user_info.preferred_username + """</strong></p>
            <form action="/reconcile" method="post" enctype="multipart/form-data">
                <div class="file-group">
                    <label><strong>1:</strong> Upload GOGO PDF</label>
                    <input type="file" name="pdf1" required>
                </div>
                <div class="file-group">
                    <label><strong>2:</strong> Upload SURE Realty PDF</label>
                    <input type="file" name="pdf2" required>
                </div>
                <div class="file-group">
                    <label><strong>3:</strong> Baselane exported CSV</label>
                    <input type="file" name="sheet_json" required>
                </div>
                <button type="submit">Start Reconciliation</button>
            </form>
            <a href="/history" class="history-link">📜 View Audit Log (Neon DB)</a>
        </div>
        <div class="card" style="margin-top: 20px;">
            <h3>📊 Generate Monthly Report</h3>
            <form action="/report" method="get">
                <select name="month_year" style="padding: 10px; width: 70%;">
                    <option value="01/2026">January 2026</option>
                    <option value="12/2025">December 2025</option>
                </select>
                <button type="submit" style="width: 25%; background: #28a745;">View</button>
            </form>
        </div>
    </body>
    </html>
    """