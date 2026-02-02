from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
import logging
import json
import smtplib
import io
import os

from sqlalchemy.orm import Session
from huggingface_hub import attach_huggingface_oauth, parse_huggingface_oauth
from fastapi.responses import HTMLResponse
from collections import defaultdict
import pandas as pd
from datetime import datetime
from sqlalchemy import extract, cast, Date
from fastapi import FastAPI, Depends, Form, File, UploadFile

# Absolute imports for your app structure
from app.extract import pdf_to_text
from app.llm import extract_with_llm
from app.reconcile import run_bank_reconciliation
from app.schemas import ExtractedDoc
from app.utils import generate_baselane_csv, get_relevant_text, sheet_to_json, parse_any_date
from app.database import SessionLocal, engine, get_db # Added get_db here
from app import models
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import csv 

html_templates = Jinja2Templates(directory="app/templates")

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

@app.post("/reconcile")
async def reconcile_endpoint(
    pdf1: UploadFile = File(...),
    pdf2: UploadFile = File(...),
    sheet_json: UploadFile = File(...),
    month_year: str = Form(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)      
):
    # logger.info(f"User {user.user_info.preferred_username} starting reconciliation")
    
    try:
        month_year_obj = parse_any_date(month_year)
    except ValueError as e:
        print(f"Date Error: {e}")
    
    # Read and extract
    content1 = await pdf1.read()
    content2 = await pdf2.read()
    bank_data = sheet_to_json(sheet_json)

    text1 = pdf_to_text(content1)
    text2 = pdf_to_text(content2)

    # GOGO: Only Page 3 (Index 2)
    relevant_text1 = get_relevant_text(text1, [2]) 
    # logger.info(f"LLM RELEVANT TEXT 1: {str(relevant_text1)}")
    
    # SURE REALTY: Only Page 1 (Index 0)
    relevant_text2 = get_relevant_text(text2, [0])
    # logger.info(f"LLM RELEVANT TEXT 2: {str(relevant_text2)}")
  
    # Pass this clean, small string to the LLM
    parsed1 = extract_with_llm(relevant_text1)
    parsed2 = extract_with_llm(relevant_text2)

    if not parsed1.get("properties"):
        logger.error("PDF 1 failed to return property data")
    
    if not parsed2.get("properties"):
        logger.error("PDF 2 failed to return property data")

    try:
        doc1 = ExtractedDoc(**parsed1)
        doc2 = ExtractedDoc(**parsed2)
    except Exception as e:
        logger.error(f"Validation Error: {e}")
        return {"error": "LLM output validation failed", "details": str(e)}

    # Extract the relevant data from Bank_data
    bank_dict = {}
    # Define the clean keys you expect from your PDF
    target_merchants = ["GOGO PROPERTY", "SURE REALTY"]

    for entry in bank_data:
        bank_merchant_name = entry.get('Merchant', '').upper()
        amount = entry.get('Amount', 0.0)
        
        for target in target_merchants:
            # If "GOGO PROPERTY" is found inside the long bank string
            if target in bank_merchant_name or target.split()[0] in bank_merchant_name:
                bank_dict[target] = amount

    # --- STEP 5: Save to Neon Database ---
    try:
        # db = SessionLocal()
        calc_totals = defaultdict(float)
        prop_counts = defaultdict(int)
        stmt_dates = {} 
        source_files = {}

        # Delete existing statements for this specific month/year 
        # so we don't get duplicates or inflated totals.
        db.query(models.RentalStatement).filter(
            extract('year', models.RentalStatement.statement_date) == month_year_obj.year,
            extract('month', models.RentalStatement.statement_date) == month_year_obj.month
        ).delete(synchronize_session=False)

        # Also delete existing summary records for this month
        db.query(models.ReconciliationSummary).filter(
            extract('year', models.ReconciliationSummary.statement_date) == month_year_obj.year,
            extract('month', models.ReconciliationSummary.statement_date) == month_year_obj.month
        ).delete(synchronize_session=False)
        
        db.commit() # Commit the deletion before adding new data

        for doc, filename in [(doc1, pdf1.filename), (doc2, pdf2.filename)]:
            merchant_name = doc.merchant_group.strip().upper()
            stmt_dates[merchant_name] = doc.statement_date
            source_files[merchant_name] = filename

            for prop in doc.properties:
                calc_net = prop.rent_paid - prop.management_fees
                calc_totals[merchant_name] += calc_net
                prop_counts[merchant_name] += 1

                new_record = models.RentalStatement(
                    statement_date=doc.statement_date, 
                    merchant_group=merchant_name,
                    address=prop.address,
                    rent_amount=prop.rent_amount,
                    rent_paid=prop.rent_paid,
                    management_fees=prop.management_fees,
                    net_income=calc_net,
                    source_file=filename
                )
                db.add(new_record)
                # Determine the merchant group for reconciliation logic

        db.commit()

        # --- STEP 6: RECONCILE ---
        result = run_bank_reconciliation(
            db=db,
            stmt_dates=stmt_dates,
            calc_totals=dict(calc_totals), 
            prop_counts=dict(prop_counts), 
            bank_data=bank_dict,
            source_files=source_files,
            target_month=month_year_obj
        )
    except Exception as e:
        logger.error(f"Database Save Error: {e}")
        db.rollback()
    finally:
        db.close()

    return RedirectResponse(url="/report?msg=success", status_code=303)

# ------------------ Report ----------------
@app.get("/report", response_class=HTMLResponse)
async def unified_dashboard(
    request: Request,
    month_year: str = "2026-01", # Default to current month
    merchant: str = None,
    db: Session = Depends(get_db)
):
    # 1. Base Query for the Table
    query = db.query(models.RentalStatement)
    
    # Apply Date Filtering
    if month_year:
        year_val, month_val = map(int, month_year.split("-"))

    query = query.filter(
        extract('year', models.RentalStatement.statement_date) == year_val,
        extract('month', models.RentalStatement.statement_date) == month_val
    )
    # 2. Summary Logic (Executive Cards)
    # We fetch all for the month to calculate the cards regardless of the merchant filter
    summary_items = query.all()
    
    # Group totals for the cards
    gogo_group = [i for i in summary_items if i.merchant_group == "GOGO PROPERTY"]
    sure_group = [i for i in summary_items if i.merchant_group == "SURE REALTY"]
    
    gogo_total = sum((i.rent_paid - i.management_fees) for i in gogo_group)
    sure_total = sum((i.rent_paid - i.management_fees) for i in sure_group)

    # Reconciliation Logic (Comparing to Bank)
    # Ideally, these bank numbers come from your ReconciliationSummary table
    gogo_match = "✅ MATCHED" if gogo_total == 6751.50 else "❌ DISCREPANCY"
    sure_match = "✅ MATCHED" if sure_total == 1833.00 else "❌ DISCREPANCY"

    # 3. Final Table Filtering (if a specific merchant is selected)
    if merchant:
        query = query.filter(models.RentalStatement.merchant_group == merchant.upper())
    
    statements = query.order_by(models.RentalStatement.statement_date.desc()).all()

    return html_templates.TemplateResponse("dashboard.html", {
        "request": request,
        "statements": statements,
        "gogo_total": gogo_total,
        "gogo_match": gogo_match,
        "sure_total": sure_total,
        "sure_match": sure_match,
        "selected_month": month_year,
        "selected_merchant": merchant
    })

# ---------------- Audit Log --------------------
@app.get("/history")
async def audit_log(
    request: Request, 
    month_year: str = None, 
    merchant: str = None, 
    property_name: str = None, 
    db: Session = Depends(get_db)
):
    query = db.query(models.RentalStatement)

    # Filter by Month/Year
    if month_year:
        year_val, month_val = map(int, month_year.split("-"))
        query = query.filter(
            extract('year', models.RentalStatement.statement_date) == year_val,
            extract('month', models.RentalStatement.statement_date) == month_val
        )

    # Filter by Merchant Group
    if merchant:
        query = query.filter(models.RentalStatement.merchant_group == merchant)

    # Filter by Property (Partial match search)
    if property_name:
        query = query.filter(models.RentalStatement.address.ilike(f"%{property_name}%"))

    statements = query.order_by(models.RentalStatement.statement_date.desc()).all()

    return html_templates.TemplateResponse("history.html", {
        "request": request,
        "statements": statements,
        "selected_month": month_year,
        "selected_merchant": merchant,
        "property_query": property_name
    })

## ------- Export Baselane CSV file ---------------
@app.get("/export/baselane")
def export_baselane(
    merchant: str = None, 
    month_year: str = None, # Expected format "YYYY-MM"
    db: Session = Depends(get_db)
):
    query = db.query(models.RentalStatement)

    # Apply Filters
    if merchant:
        query = query.filter(models.RentalStatement.merchant_group == merchant.upper())
    
    if month_year:
        year, month = map(int, month_year.split("-"))
        query = query.filter(
            extract('year', models.RentalStatement.statement_date) == year,
            extract('month', models.RentalStatement.statement_date) == month
        )

    records = query.all()
    
    # Generate CSV with virtual category splitting
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Account", "Description", "Amount", "Category", "Property"])
    
    for rec in records:
        # 1. Rent Row
        writer.writerow([
            rec.statement_date.strftime('%b %d %Y'),
            "Manually Added",
            f"Rent - {rec.merchant_group}",
            f"{rec.rent_paid:.2f}",
            "Rents",
            rec.address
        ])
        # 2. Management Fee Row (if exists)
        if rec.management_fees != 0:
            writer.writerow([
                rec.statement_date.strftime('%b %d %Y'),
                "Manually Added",
                f"Fee - {rec.merchant_group}",
                f"-{abs(rec.management_fees):.2f}",
                "Management Fees",
                rec.address
            ])
            
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=baselane_{merchant or 'all'}.csv"}
    )

## ------- Report by Merchant Group and Month/Year. ---------------
@app.get("/report/details")
def view_detailed_report(
    merchant: str = None, 
    month_year: str = None, 
    db: Session = Depends(get_db)
):
    query = db.query(models.RentalStatement)

    if merchant:
        query = query.filter(models.RentalStatement.merchant_group == merchant.upper())

    if month_year:
        year, month = map(int, month_year.split("-"))
        query = query.filter(
            extract('year', models.RentalStatement.statement_date) == year,
            extract('month', models.RentalStatement.statement_date) == month
        )

    statements = query.order_by(models.RentalStatement.statement_date.desc()).all()
    
    # This returns the data to your frontend
    return {
        "count": len(statements),
        "data": statements
    }

attach_huggingface_oauth(app)
# ------------- Home Page ------------------
@app.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    user = parse_huggingface_oauth(request)
    
    if not user:
        # 2. Use the unique name here
        return html_templates.TemplateResponse("login.html", {"request": request})
    
    return html_templates.TemplateResponse("index.html", {
        "request": request,
        "username": user.user_info.preferred_username
    })

