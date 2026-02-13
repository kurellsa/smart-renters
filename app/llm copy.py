import os
import json
from groq import Groq

def extract_with_llm(text: str):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # We use 70B because it's significantly smarter than 8B for tables
    model_id = "llama-3.3-70b-versatile"

    prompt = f"""
    Return ONLY a valid JSON object. Extract rental data from the following text.
    
    ### CRITICAL RULES:
    - 'merchant_group': set this to 'GOGO PROPERTY' for GOGO document and 'SURE REALTY' for the other one.
    - 'address': set this to '2560 Coventry St.' for 'Management Detail Report' document
 
    SCHEMA:
    {{
      "statement_date": "MM/DD/YYYY",
      "merchant_group": str,
      "properties": [
        {{ "address": "str", "rent_amount": 0.0, "rent_paid": 0.0, "management_fees": 0.0 }}
      ]
    }}

    TEXT:
    {text}
    """

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=model_id,
        response_format={"type": "json_object"} # Forces JSON
    )

    return json.loads(chat_completion.choices[0].message.content)