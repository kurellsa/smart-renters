from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
import logging
import json
from sqlalchemy.orm import Session

# Absolute imports for your app structure
from app.extract import pdf_to_text
from app.llm import extract_with_llm
from app.reconcile import reconcile
from app.schemas import ExtractedDoc
from app.database import SessionLocal, engine, get_db # Added get_db here
from app import models
from huggingface_hub import attach_huggingface_oauth, parse_huggingface_oauth
from fastapi.responses import HTMLResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Create tables in Neon on startup
models.Base.metadata.create_all(bind=engine)

# Attach OAuth
attach_huggingface_oauth(app)

def get_current_user(request: Request):
    user = parse_huggingface_oauth(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged into Hugging Face")
    return user

@app.get("/")
def health(logs: str = None):
    return {"status": "ok", "message": "Container is healthy"}

@app.get("/history")
def get_history(db: Session = Depends(get_db), user=Depends(get_current_user)):
    statements = db.query(models.RentalStatement).order_by(models.RentalStatement.created_at.desc()).limit(10).all()
    return statements

@app.post("/reconcile")
async def reconcile_endpoint(
    pdf1: UploadFile = File(...),
    pdf2: UploadFile = File(...),
    sheet_json: UploadFile = File(...), # Added missing comma
    user=Depends(get_current_user),
    db: Session = Depends(get_db)      # Added db dependency
):
    logger.info(f"User {user.user_info.preferred_username} starting reconciliation")
    
    # Read and extract
    content1 = await pdf1.read()
    content2 = await pdf2.read()
    sheet_content = await sheet_json.read()

    text1 = pdf_to_text(content1)
    text2 = pdf_to_text(content2)

    parsed1 = extract_with_llm(text1)
    parsed2 = extract_with_llm(text2)

    try:
        doc1 = ExtractedDoc(**parsed1)
        doc2 = ExtractedDoc(**parsed2)
    except Exception as e:
        logger.error(f"Validation Error: {e}")
        return {"error": "LLM output validation failed", "details": str(e)}

    # Parse Baselane JSON
    try:
        bank_data = json.loads(sheet_content)
    except Exception as e:
        return {"error": "Invalid bank JSON file"}

    # --- STEP 5: Save to Neon Database ---
    try:
        # Saving properties from both PDFs
        for doc in [doc1, doc2]:
            for prop in doc.properties:
                new_record = models.RentalStatement(
                    property_name=prop.address,
                    rent_amount=prop.rent,
                    fees=prop.fees,
                    net_income=doc.net_income,
                    raw_json=parsed1 if doc == doc1 else parsed2
                )
                db.add(new_record)
        db.commit()
    except Exception as e:
        logger.error(f"Database Save Error: {e}")
        db.rollback()

    # --- STEP 6: RECONCILE ---
    result = reconcile(doc1, doc2, bank_data)
    
    return {
        "reconciliation_result": result,
        "summary": {
            "user": user.user_info.preferred_username,
            "properties_saved": len(doc1.properties) + len(doc2.properties)
        }
    }

@app.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    # This checks if the user is logged in before even showing the page
    user = parse_huggingface_oauth(request)
    if not user:
        return f'<a href="/login/huggingface">Click here to Login with Hugging Face to access SmartPartners</a>'

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
                    <label><strong>Step 1:</strong> Current Month PDF</label>
                    <input type="file" name="pdf1" required>
                </div>
                <div class="file-group">
                    <label><strong>Step 2:</strong> Previous Month PDF (Optional)</label>
                    <input type="file" name="pdf2" required>
                </div>
                <div class="file-group">
                    <label><strong>Step 3:</strong> Baselane Bank Export (JSON)</label>
                    <input type="file" name="sheet_json" required>
                </div>
                <button type="submit">Start Reconciliation</button>
            </form>
            <a href="/history" class="history-link">📜 View Audit Log (Neon DB)</a>
        </div>
    </body>
    </html>
    """