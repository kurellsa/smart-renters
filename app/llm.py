import os
import json
from huggingface_hub import InferenceClient

# Initialize client (uses HF_TOKEN from your Space's Secrets)
client = InferenceClient(api_key=os.getenv("HF_TOKEN"))

def extract_with_llm(text: str):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a specialized data extractor. Extract property details into JSON. "
                "Format: {'properties': [{'name': str, 'rent': float, 'fee': float}], 'net_total': float}. "
                "Return ONLY the raw JSON object. No markdown, no preamble."
            )
        },
        {
            "role": "user",
            "content": f"Extract data from this text:\n\n{text}"
        }
    ]

    # Using chat_completion to avoid the ValueError
    response = client.chat.completions.create(
        model="mistralai/Mistral-7B-Instruct-v0.3",
        messages=messages,
        max_tokens=1000,
        response_format={"type": "json_object"} # Forces JSON mode
    )

    # Parse the response
    content = response.choices[0].message.content
    return json.loads(content)