from fastapi import FastAPI, UploadFile, File, HTTPException
import logging
import json
import pprint
from app.extract import pdf_to_text
from app.llm import extract_with_llm
from app.reconcile import reconcile
from app.schemas import ExtractedDoc
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models
from huggingface_hub import attach_huggingface_oauth, parse_huggingface_oauth
from fastapi import Request, Depends

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Create the tables in Neon if they don't exist
models.Base.metadata.create_all(bind=engine)

# 1. Attach the OAuth logic to your app
attach_huggingface_oauth(app)

# 2. Create a "User Check" dependency
def get_current_user(request: Request):
    user = parse_huggingface_oauth(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged into Hugging Face")
    return user

@app.get("/")
def health(logs: str = None): # Accept the 'logs' parameter HF sends
    return {"status": "ok", "message": "Container is healthy"}

@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    statements = db.query(models.RentalStatement).order_by(models.RentalStatement.created_at.desc()).limit(10).all()
    return statements

@app.post("/reconcile")
async def reconcile_endpoint(
    pdf1: UploadFile = File(...),
    pdf2: UploadFile = File(...),
    sheet_json: UploadFile = File(...)
    user=Depends(get_current_user) # Only logged-in users get past here
):
    logger.info(f"User {user.user_info.preferred_username} is running reconciliation")
    # --- STEP 1: LOG RAW FILE DATA ---
    logger.info("="*50)
    logger.info(f"STARTING RECONCILIATION: {pdf1.filename}, {pdf2.filename}")
    
    # Read files
    content1 = await pdf1.read()
    content2 = await pdf2.read()
    sheet_content = await sheet_json.read()

    # Convert PDF to text
    text1 = pdf_to_text(content1)
    text2 = pdf_to_text(content2)
    
    logger.info(f"PDF1 Extracted Text Length: {len(text1)} chars")
    logger.info(f"PDF2 Extracted Text Length: {len(text2)} chars")

    # --- STEP 2: DEBUG LLM PARSING (PDF 1) ---
    logger.info("--- Parsing PDF1 with LLM ---")
    parsed1 = extract_with_llm(text1)
    
    # Pretty-print the raw JSON returned by LLM to your logs
    logger.info(f"RAW LLM JSON (PDF1):\n{json.dumps(parsed1, indent=2)}")

    try:
        doc1 = ExtractedDoc(**parsed1)
    except Exception as e:
        logger.error(f"Pydantic Validation Error for PDF1: {e}")
        return {"error": "PDF1 data structure invalid", "raw_llm_output": parsed1}

    # --- STEP 3: DEBUG LLM PARSING (PDF 2) ---
    logger.info("--- Parsing PDF2 with LLM ---")
    parsed2 = extract_with_llm(text2)
    logger.info(f"RAW LLM JSON (PDF2):\n{json.dumps(parsed2, indent=2)}")

    try:
        doc2 = ExtractedDoc(**parsed2)
    except Exception as e:
        logger.error(f"Pydantic Validation Error for PDF2: {e}")
        return {"error": "PDF2 data structure invalid", "raw_llm_output": parsed2}

    # --- STEP 4: DEBUG SHEET JSON ---
    try:
        bank_data = json.loads(sheet_content)
        logger.info(f"Bank JSON Loaded (First 2 entries): {json.dumps(bank_data[:2], indent=2)}")
    except Exception as e:
        logger.error(f"Failed to parse sheet_json: {e}")
        return {"error": "sheet_json is not valid JSON"}

    # --- STEP 5: Save to Neon Database ---
    # --- STEP 5: Save to Neon Database ---
    db = SessionLocal()
    try:
        # Loop through properties if you want to save all of them
        for prop in doc1.properties:
            new_record = models.RentalStatement(
                property_name=prop.address,
                rent_amount=prop.rent,
                fees=prop.fees,
                net_income=doc1.net_income,
                raw_json=parsed1
            )
            db.add(new_record)
        db.commit()
        logger.info("Successfully saved PDF1 data to Neon.")
    except Exception as e:
        logger.error(f"Database Save Error: {e}")
        db.rollback()
    finally:
        db.close()

    # --- STEP 6: RECONCILE ---
    logger.info("--- Starting Final Reconciliation Logic ---")
    result = reconcile(doc1, doc2, bank_data)
    
    logger.info(f"Final Result: {result}")
    logger.info("="*50)

    # Return everything so you can see it in your browser/curl
    return {
        "reconciliation_result": result,
        "debug": {
            "doc1_parsed": doc1.dict(),
            "doc2_parsed": doc2.dict(),
            "bank_data_count": len(bank_data)
        }
    }