import os
import json
import logging
import re
from venv import logger
from huggingface_hub import InferenceClient

# Initialize client using the HF_TOKEN from your Space's Secrets
client = InferenceClient(api_key=os.getenv("HF_TOKEN"))

def extract_with_llm(text: str):
    # Detailed mapping instructions to handle the different PDF naming conventions
    system_prompt = (
        "You are a Senior Real Estate Accountant. Your goal is to extract property data "
        "and normalize it into a standard JSON format, regardless of the source PDF's layout."
    )
    
    user_prompt = f"""
        Extract data from the following text and return ONLY a valid JSON object. 
        Do not include any preamble, notes, or markdown formatting blocks.

        ### MAPPING RULES:
        - 'address': For addresses like 'PANDIAN:COVENTRY2560...', use '2560 Coventry St'.
        - PDF1: 'Rent Income' -> rent_paid, 'Net income' -> net_income.
        - PDF2: 'Income' -> rent_amount, 'Equity' -> rent_paid & net_income (use absolute value).
        - PDF2: For addresses like 'PANDIAN:COVENTRY2560...', use property name as '2560 Coventry St'.

        ### MERCHANT RULES:
        - 'Millison' or 'Wards Creek' -> 'GOGO PROPERTY'
        - 'PANDIAN' or 'Coventry' -> 'SURE REALTY'

        ### STRICT OUTPUT SCHEMA:
        {{
            "statement_date": "MM/DD/YYYY",
            "merchant_group": "string",
            "properties": [
                {{
                    "address": "string",
                    "rent_amount": 0.0,
                    "rent_paid": 0.0,
                    "management_fees": 0.0,
                    "net_income": 0.0
                }}
            ]
        }}
    ### TEXT TO EXTRACT:
    {text}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # Llama-3.2-3B is highly optimized for this "chat" style request
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.2-3B-Instruct",
        messages=messages,
        max_tokens=1000,
        response_format={"type": "json_object"} 
    )

    content = response.choices[0].message.content
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        content_clean = match.group(0)
    else:
        content_clean = content # Fallback
        
    return json.loads(content_clean)