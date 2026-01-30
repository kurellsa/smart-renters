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
        Extract data from the following property statement text.

        ### MAPPING RULES:
        1. 'address': Normalize the property address .
        6. For addresses like 'PANDIAN:COVENTRY2560...', use property name as '2560 Coventry St'.

        ### SPECIAL LAYOUT INSTRUCTIONS:
        - The text may contain multiple properties listed side-by-side in columns, usually on Page 3 for PDF1
        - Ensure each property address is matched ONLY with the values directly below it for PDF1
        - PDF1 Synonyms: 'Rent Income' -> rent_paid, 'Management Fees' -> fees, 'Statement date' --> statement_date
        - PDF1 Synonyms: 'Net income' -> net_income, use the 'Net income' on page 3 for each property
        - PDF2 Synonyms: 'Run Date' --> statement_date, 'Income' -> rent_amount, 'Management Fees' -> fees.
        - PDF2 Synonyms: 'Equity' -> rent_paid, use its absolute value for rent_paid and net_income.
        Merchant Tagging: 
        - If the text mentions 'Millison' or 'Wards Creek', set merchant_group to 'GOGO PROPERTY'.
        - If the text mentions 'PANDIAN' or 'Coventry', set merchant_group to 'SURE REALTY'.

        ### OUTPUT SCHEMA:
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

    Return ONLY raw JSON.
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