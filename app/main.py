from fastapi import FastAPI, UploadFile, File
from extract import pdf_to_text
from llm import extract_with_llm
from reconcile import reconcile
from schemas import ExtractedDoc

app = FastAPI()

@app.post("/reconcile")
async def reconcile_endpoint(
    pdf1: UploadFile = File(...),
    pdf2: UploadFile = File(...),
    sheet_json: dict = None
):
    text1 = pdf_to_text(await pdf1.read())
    text2 = pdf_to_text(await pdf2.read())

    doc1 = ExtractedDoc(**extract_with_llm(text1))
    doc2 = ExtractedDoc(**extract_with_llm(text2))

    result = reconcile(doc1, doc2, sheet_json)

    return result