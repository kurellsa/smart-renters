from fastapi import FastAPI, UploadFile, File, HTTPException
import logging
import json
import pprint
from app.extract import pdf_to_text
from app.llm import extract_with_llm
from app.reconcile import reconcile
from app.schemas import ExtractedDoc

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/")
def health(logs: str = None): # Accept the 'logs' parameter HF sends
    return {"status": "ok", "message": "Container is healthy"}

@app.post("/reconcile")
async def reconcile_endpoint(
    pdf1: UploadFile = File(...),
    pdf2: UploadFile = File(...),
    sheet_json: UploadFile = File(...)
):
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

    # --- STEP 5: RECONCILE ---
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