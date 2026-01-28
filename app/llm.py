import requests
import os
import json

HF_API = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
HEADERS = {
    "Authorization": f"Bearer {os.environ['HF_TOKEN']}"
}

def extract_with_llm(text: str) -> dict:
    prompt = f"""
You are a data extraction engine.

Extract ONLY the following JSON.
If a value is missing, return null.
Do NOT calculate or infer values.
Return valid JSON only.

Schema:
{{
  "property_id": string,
  "statement_date":date
  "period": string,
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
        json={"inputs": prompt}
    )

    result = response.json()
    
    def extract_with_llm(text):
    result = llm_model_call(text)  # your HF call
    if not result or len(result) == 0:
        raise ValueError("LLM returned empty result")
    
    # Depending on HF response format
    if "generated_text" in result[0]:
        return eval(result[0]["generated_text"])
    else:
        raise ValueError(f"Unexpected LLM output format: {result}")

    return json.loads(result[0]["generated_text"])