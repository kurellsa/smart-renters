import os
import json
from huggingface_hub import InferenceClient

client = InferenceClient(api_key=os.getenv("HF_TOKEN"))

def extract_with_llm(text: str):
    # Manually format the prompt for Mistral Instruct
    prompt = f"<s>[INST] You are a data extractor. Extract property data from the text below into a JSON object.\n" \
             f"Format: {{'properties': [{{'name': str, 'rent': float, 'fee': float}}], 'net_total': float}}\n" \
             f"Text: {text} [/INST]"

    # Use text_generation instead of chat.completions
    response = client.text_generation(
        model="mistralai/Mistral-7B-Instruct-v0.3",
        prompt=prompt,
        max_new_tokens=1000,
        stop_sequences=["[/INST]", "</s>"]
    )

    # Clean the string (remove any accidental markdown formatting)
    clean_json = response.strip()
    if "```json" in clean_json:
        clean_json = clean_json.split("```json")[1].split("```")[0]
    elif "```" in clean_json:
        clean_json = clean_json.split("```")[1].split("```")[0]

    return json.loads(clean_json)