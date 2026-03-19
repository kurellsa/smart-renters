import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def extract_with_llm(text: str, target_month: str = None):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    # We use 70B because it's significantly smarter than 8B for tables
    model_id = "llama-3.3-70b-versatile"

    month_rule = ""
    if target_month:
        month_rule = f"""
    - TARGET MONTH: Only extract data for the rental month '{target_month}'. Ignore all other months in the table.
    - For Sure Realty statements with a monthly table: map 'Rent Paid' column → rent_paid, 'Fee to Sure Realty' column → management_fees, 'Date Received' column → statement_date.
    - For 'statement_date': if the date uses M.D.YY format (e.g., 1.3.26), interpret as Month.Day.Year and convert to MM/DD/YYYY (e.g., 01/03/2026).
    - If the target month has no data (empty row), return rent_paid=0.0 and management_fees=0.0."""

    prompt = f"""
    Return ONLY a valid JSON object. Extract rental data from the following text.

    ### CRITICAL RULES:
    - 'property_management': set this to 'GOGO PROPERTY' for GOGO document and 'SURE REALTY' for the other one.
    - 'address': set this to '2560 Coventry St.' for 'Management Detail Report' document{month_rule}

    SCHEMA:
    {{
      "statement_date": "MM/DD/YYYY",
      "property_management": str,
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