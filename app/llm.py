import os
import json
from huggingface_hub import InferenceClient

# Initialize client using the HF_TOKEN from your Space's Secrets
client = InferenceClient(api_key=os.getenv("HF_TOKEN"))

def extract_with_llm(text: str):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a data extraction tool. Extract property management data into JSON. "
                "Format: {'statement_date': str, 'address': str, 'rent': float, 'fee': float, 'net_income': float}. "
                "Do not perform any calculations. Return ONLY the raw JSON object. No conversational text."
            )
        },
        {
            "role": "user",
            "content": f"Extract data from this text:\n\n{text}"
        }
    ]

    # Llama-3.2-3B is highly optimized for this "chat" style request
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.2-3B-Instruct",
        messages=messages,
        max_tokens=1000,
        response_format={"type": "json_object"} 
    )

    content = response.choices[0].message.content
    return json.loads(content)