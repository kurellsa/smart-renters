import requests
import os
import json
import re

HF_API = "https://router.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"

HEADERS = {
    "Authorization": f"Bearer {os.environ.get('HF_TOKEN')}",
    "Content-Type": "application/json"
}

def extract_with_llm(text: str) -> dict:
    prompt = f"""
You are a data extraction engine.

Return ONLY valid JSON.
Do NOT add explanations.
If a value is missing, return null.

Schema:
{{
  "property_id": "string",
  "statement_date": "YYYY-MM-DD",
  "period": "string",
  "rent": number | null,
  "fees": number | null
}}

Text:
<<<
{text}
>>>
"""

    response = requests.post(
        HF_API,
        headers=HEADERS,
        json={"inputs": prompt},
        timeout=60
    )

    if response.status_code != 200:
        print("HF error:", response.text)
        return {}

    result = response.json()

    if not isinstance(result, list) or not result:
        return {}

    gen_text = result[0].get("generated_text", "")

    match = re.search(r"\{.*\}", gen_text, re.DOTALL)
    if not match:
        return {}

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        print("Invalid JSON:", gen_text)
        return {}