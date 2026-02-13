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
from sqlalchemy import extract, cast, Date, func
from fastapi import FastAPI, Depends, Form, File, UploadFile

# Absolute imports for your app structure
from app.extract import pdf_to_text
from app.llm import extract_with_llm
from app.reconcile import run_reconciliation
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
    bank_bytes = await sheet_json.read()
    bank_df = pd.read_csv(io.BytesIO(bank_bytes))

    text1 = pdf_to_text(content1)
    text2 = pdf_to_text(content2)

    # GOGO: Only Page 3 (Index 2)
    relevant_text1 = get_relevant_text(text1, [2]) 
    
    # SURE REALTY: Only Page 1 (Index 0)
    relevant_text2 = get_relevant_text(text2, [0])
  
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

    # Inject the manager name into each property so the data isn't lost
    for p in doc1.properties:
        p.property_management = doc1.property_management

    for p in doc2.properties:
        p.property_management = doc2.property_management

    ## Merge both PDF properties for reconciliation
    all_props = doc1.properties + doc2.properties

    # --- STEP 5: Save to Neon Database ---
    try:
        # 1. DELETE existing records for the month (Prevent Duplicates)
        db.query(models.RentalStatement).filter(
            extract('year', models.RentalStatement.statement_date) == month_year_obj.year,
            extract('month', models.RentalStatement.statement_date) == month_year_obj.month
        ).delete(synchronize_session=False)
        
        for doc, filename in [(doc1, pdf1.filename), (doc2, pdf2.filename)]:
            
            stmt_date_obj = parse_any_date(doc.statement_date)
            property_management = doc.property_management.strip().upper()

            for prop in doc.properties:
                calc_net = float(prop.rent_paid - prop.management_fees) # Ensure float, not numpy

                new_record = models.RentalStatement(
                    statement_date=stmt_date_obj, 
                    property_management=property_management,
                    address=prop.address,
                    rent_amount=prop.rent_amount,
                    rent_paid=prop.rent_paid,
                    management_fees=prop.management_fees,
                    net_income=calc_net,
                    source_file=filename
                )
                db.add(new_record)

        db.commit()

        # --- STEP 6: RECONCILE ---
        result = run_reconciliation(
            db=db,
            bank_df=bank_df,
            extracted_props=all_props,
            target_month=month_year_obj
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Reconciliation Endpoint Error: {str(e)}")
        return {"error": "Processing failed", "details": str(e)}

    month_str = month_year_obj.strftime("%Y-%m")
    return RedirectResponse(url=f"/report?month_year={month_str}&msg=success", status_code=303)

# ------------------ Report ----------------
@app.get("/report", response_class=HTMLResponse)
async def unified_dashboard(
    request: Request,
    month_year: str = None, # Default to current month
    property_management: str = None,
    db: Session = Depends(get_db)
):
    # 1. Base Query for the Table
    query = db.query(models.RentalStatement)

    # 1. Initialize variables with defaults to prevent "Undefined" errors
    total_collected = 0.0
    total_expected = 0.0
    rent_percent = 0
    hoa_percent = 0
    mortgage_percent = 0
    hoa_verified = 0
    total_props = 0

    if not month_year:
        # Look for the most recent month in the Recon Log
        latest_recon = db.query(func.max(models.PropertyReconLog.month_year)).scalar()
        if latest_recon:
            month_year = latest_recon.strftime("%Y-%m")
        else:
            # Fallback if DB is totally empty
            month_year = datetime.utcnow().strftime("%Y-%m")
    
    year_val, month_val = map(int, month_year.split("-"))

    query = query.filter(
        extract('year', models.RentalStatement.statement_date) == year_val,
        extract('month', models.RentalStatement.statement_date) == month_val
    )
    # 2. Summary Logic (Executive Cards)
    # We fetch all for the month to calculate the cards regardless of the prop management filter
    summary_items = query.all()
    
    # Group totals for the cards
    gogo_group = [i for i in summary_items if i.property_management == "GOGO PROPERTY"]
    sure_group = [i for i in summary_items if i.property_management == "SURE REALTY"]
    
    gogo_total = sum((i.rent_paid - i.management_fees) for i in gogo_group)
    sure_total = sum((i.rent_paid - i.management_fees) for i in sure_group)

    # Reconciliation Logic (Comparing to Bank)
    gogo_match = "✅ MATCHED" if gogo_total == 6751.50 else "❌ DISCREPANCY"
    sure_match = "✅ MATCHED" if sure_total == 1833.00 else "❌ DISCREPANCY"

    # 3. Final Table Filtering (if a specific property management is selected)
    if property_management:
        query = query.filter(models.RentalStatement.property_management == property_management.upper())
    
    statements = query.order_by(models.RentalStatement.statement_date.desc()).all()

    return html_templates.TemplateResponse("dashboard.html", {
        "request": request,
        "statements": statements,
        "gogo_total": gogo_total,
        "gogo_match": gogo_match,
        "sure_total": sure_total,
        "sure_match": sure_match,
        "selected_month": month_year,
        "selected_property_management": property_management,
        "username": "smartrenters" 
    })
# ---------------- Audit Log --------------------
@app.get("/history")
async def audit_log(
    request: Request, 
    month_year: str = None, 
    property_management: str = None, 
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

    # Filter by property_management
    if property_management:
        query = query.filter(models.RentalStatement.property_management == property_management)

    # Filter by Property (Partial match search)
    if property_name:
        query = query.filter(models.RentalStatement.address.ilike(f"%{property_name}%"))

    statements = query.order_by(models.RentalStatement.statement_date.desc()).all()

    return html_templates.TemplateResponse("history.html", {
        "request": request,
        "statements": statements,
        "selected_month": month_year,
        "selected_property_management": property_management,
        "property_query": property_name
    })

## ------- Export Baselane CSV file ---------------
@app.get("/export/baselane")
def export_baselane(
    property_management: str = None, 
    month_year: str = None, # Expected format "YYYY-MM"
    db: Session = Depends(get_db)
):
    query = db.query(models.RentalStatement)

    # Apply Filters
    if property_management:
        query = query.filter(models.RentalStatement.property_management == property_management.upper())
    
    if month_year:
        year, month = map(int, month_year.split("-"))
        query = query.filter(
            extract('year', models.RentalStatement.statement_date) == year,
            extract('month', models.RentalStatement.statement_date) == month
        )

    records = query.all()
    
    #For Notes columns - Just to differentiate other txns in baselane
    notes_val = f"ManualUpload {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    current_date_str = datetime.now().strftime('%b %d %Y')

    # Generate CSV with virtual category splitting
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Account", "Description", "Amount", "Category", "Property", "Notes"])
    
    total_net_income = 0.0

    for rec in records:
        # 1. Rent Row
        writer.writerow([
            rec.statement_date.strftime('%b %d %Y'),
            "Manually Added",
            f"Rent - {rec.property_management}",
            f"{rec.rent_paid:.2f}",
            "Rents",
            rec.address,
            notes_val
        ])
        total_net_income += float(rec.rent_paid)

        # 2. Management Fee Row (if exists)
        if rec.management_fees != 0:
            writer.writerow([
                rec.statement_date.strftime('%b %d %Y'),
                "Manually Added",
                f"Fee - {rec.property_management}",
                f"-{abs(rec.management_fees):.2f}",
                "Management Fees",
                rec.address,
                notes_val
            ])
            total_net_income -= float(abs(rec.management_fees))

    # 3. Add Additional Summary Row
    # ["Date", "Account", "Description", "Amount", "Category", "Property", "Notes"]
    writer.writerow([
        current_date_str,
        "Total deposit",
        "Manual Adjustment",
        f"-{abs(total_net_income):.2f}",
        "Bank transaction",
        "",  # Property left blank
        notes_val
    ])

    output.seek(0)
    filename = f"baselane_{property_management or 'all'}_{month_year or 'export'}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

## ------- Load PropertyMaster table -----------------------------
@app.post("/parameters/upload")
async def upload_parameters(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        # Read the uploaded file
        df = pd.read_csv(file.file) # or pd.read_csv if using CSV
        
        # 1. Close out current active parameters (Set effective_to to today)
        db.query(models.PropertyParameter).filter(
            models.PropertyParameter.effective_to == None
        ).update({"effective_to": datetime.utcnow().date()})

        # 2. Loop through spreadsheet rows and insert new ones
        for _, row in df.iterrows():
            new_param = models.PropertyParameter(
                property_management=str(row['Property_Management']),
                address=row['Property'],
                expected_rent=row['Rental_Income'],
                management_fee=row['Management_Fee'],
                mortgage_payment=row['Mortgage_Payment'],
                hoa_fee=row['HOA'],
                hoa_frequency=row['HOA_Frequency'],
                hoa_account_no=str(row['HOA_Account_No']),
                hoa_phone_no=str(row['HOA_Phone_No']),
                notes=str(row['Notes']),
                effective_from=datetime.utcnow().date()
            )
            db.add(new_param)
        
        db.commit()
        return RedirectResponse(url="/parameters?msg=updated", status_code=303)
    except Exception as e:
        # This will print the error in your VS Code / Terminal console
        print(f"ERROR BULK LOADING: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 
## ------- Report to view Property Parameters --------------------
@app.get("/parameters")
async def view_parameters(request: Request, db: Session = Depends(get_db)):
    try:
        # 1. Fetch parameters (ensure the table exists!)
        parameters = db.query(models.PropertyParameter).filter(
            models.PropertyParameter.effective_to == None
        ).all()
        
        # 2. Safety check for count
        property_count = len(parameters) if parameters else 0

        return html_templates.TemplateResponse("parameters.html", {
            "request": request,
            "username": "smartrenters", # Ensure this matches your index.html
            "parameters": parameters,
            "property_count": property_count
        })
    except Exception as e:
        # This will print the error in your VS Code / Terminal console
        print(f"ERROR LOADING PROPERTY MASTER: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
## ------- Report by property_management and Month/Year. ---------------
@app.get("/report/details")
def view_detailed_report(
    property_management: str = None, 
    month_year: str = None, 
    db: Session = Depends(get_db)
):
    query = db.query(models.RentalStatement)

    if property_management:
        query = query.filter(models.RentalStatement.property_management == property_management.upper())

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
async def upload_page(
    request: Request, 
    month_year: str = None, 
    db: Session = Depends(get_db)
):
    user = parse_huggingface_oauth(request)
    if not user:
        return html_templates.TemplateResponse("login.html", {"request": request})

    # 1. Smart Date Logic: Default to the most recent data available
    if not month_year:
        latest = db.query(func.max(models.PropertyReconLog.month_year)).scalar()
        month_year = latest.strftime("%Y-%m") if latest else datetime.utcnow().strftime("%Y-%m")

    try:
        year_val, month_val = map(int, month_year.split("-"))
    except (ValueError, AttributeError):
        now = datetime.utcnow()
        year_val, month_val = now.year, now.month

    # 2. Query the Recon Logs for the Summary Gauges
    recon_logs = db.query(models.PropertyReconLog).filter(
        extract('year', models.PropertyReconLog.month_year) == year_val,
        extract('month', models.PropertyReconLog.month_year) == month_val
    ).all()

    # 3. Fetch Miscellaneous Expenses for the same period
    misc_logs = db.query(models.MiscExpenseLog).filter(
        extract('year', models.MiscExpenseLog.month_year) == year_val,
        extract('month', models.MiscExpenseLog.month_year) == month_val
    ).all()

    # 4. Aggregate Data with Consistent Wording
    # --- Rent ---
    actual_rent = sum(log.actual_rent for log in recon_logs) if recon_logs else 0.0
    target_rent = sum(log.target_rent for log in recon_logs) if recon_logs else 0.0
    rent_percent = (actual_rent / target_rent * 100) if target_rent > 0 else 0

    # --- HOA ---
    actual_hoa = sum(log.actual_hoa for log in recon_logs) if recon_logs else 0.0
    target_hoa = sum(log.target_hoa for log in recon_logs) if recon_logs else 0.0
    hoa_verified = sum(1 for log in recon_logs if log.hoa_variance == 0) if recon_logs else 0
    total_props = len(recon_logs)
    hoa_percent = (hoa_verified / total_props * 100) if total_props > 0 else 0

    # --- Mortgage ---
    actual_mort = sum(log.actual_mortgage for log in recon_logs) if recon_logs else 0.0
    target_mort = sum(log.target_mortgage for log in recon_logs) if recon_logs else 0.0
    mort_verified = sum(1 for log in recon_logs if log.mortgage_variance == 0) if recon_logs else 0
    mortgage_percent = (mort_verified / total_props * 100) if total_props > 0 else 0

    # 4. Return Data to index.html
    return html_templates.TemplateResponse("index.html", {
        "request": request,
        "username": user.user_info.preferred_username,
        "selected_month": month_year,
        "recon_logs": recon_logs,
        "misc_logs": misc_logs,
        "rent_percent": int(rent_percent),
        "actual_rent": actual_rent,
        "target_rent": target_rent,
        "hoa_percent": int(hoa_percent),
        "hoa_verified": hoa_verified,
        "actual_hoa": actual_hoa,
        "target_hoa": target_hoa,
        "total_props": total_props,
        "mortgage_percent": int(mortgage_percent),
        "actual_mort": actual_mort,
        "target_mort": target_mort
    })