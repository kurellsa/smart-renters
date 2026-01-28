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
        result = llm_model_call(text)
        print("LLM raw result:", result)
    
        if not result or len(result) == 0:
            return {}  # or raise an error
    
        # Assume HF returns dict with "generated_text"
        gen_text = result[0].get("generated_text")
        if not gen_text:
            return {}
        
        try:
            return json.loads(gen_text)
        except json.JSONDecodeError:
            return {}  # fallback