import json
import os
from huggingface_hub import InferenceClient

# This client uses Hugging Face's free serverless infrastructure
# Ensure you have a 'Read' or 'Write' token in your HF Secrets
client = InferenceClient(
    model="mistralai/Mistral-7B-Instruct-v0.3", 
    token=os.getenv("HF_TOKEN")
)

def extract_with_llm(text: str):
    prompt = f"<s>[INST] Extract property data from this text into a JSON object. " \
             f"Structure: {{'properties': [{{'name': '', 'rent': 0.0, 'fee': 0.0}}], 'net_total': 0.0}}. " \
             f"Text: {text} [/INST]"

    response = client.text_generation(
        prompt,
        max_new_tokens=500,
        return_full_text=False
    )
    
    # Simple cleanup in case the model adds extra text
    raw_content = response.strip()
    if "```json" in raw_content:
        raw_content = raw_content.split("```json")[1].split("```")[0]
    
    return json.loads(raw_content)