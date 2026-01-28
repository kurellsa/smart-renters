from fastapi import FastAPI, UploadFile, File
from app.extract import pdf_to_text
from app.llm import extract_with_llm
from app.reconcile import reconcile
from app.schemas import ExtractedDoc

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/reconcile")
async def reconcile_endpoint(
    pdf1: UploadFile = File(...),
    pdf2: UploadFile = File(...),
    sheet_json: UploadFile = File(...)
):
    print("FILES:", pdf1.filename, pdf2.filename, sheet_json.filename)

    text1 = pdf_to_text(await pdf1.read())
    print("PDF1 text length:", len(text1))
    
    text2 = pdf_to_text(await pdf2.read())
    print("PDF2 text length:", len(text2))

    parsed = extract_with_llm(text1)
    print("LLM output:", parsed)

    if not parsed:
        return {"error": "LLM returned empty JSON"}

    doc1 = ExtractedDoc(**parsed)


    parsed2 = extract_with_llm(text2)
    print("LLM output:", parsed2)

    if not parsed2:
        return {"error": "LLM returned empty JSON"}

    doc2 = ExtractedDoc(**parsed2)

    # result = reconcile(doc1, doc2, sheet_json)

    return {"doc1: ": doc1}