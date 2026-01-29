import requests, os, json

HF_API = "https://router.huggingface.co/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {os.environ['HF_TOKEN']}",
    "Content-Type": "application/json"
}

def extract_with_llm(text: str) -> dict:
    prompt = f"""
Return ONLY valid JSON.
No explanation. No markdown.

Schema:
{{
  "property_id": string,
  "statement_date": string,
  "period": string,
  "rent": number | null,
  "fees": number | null
}}

Text:
{text}
"""

    payload = {
        "model": "HuggingFaceH4/zephyr-7b-alpha",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
        "max_tokens": 512
    }

    response = requests.post(
        HF_API,
        headers=HEADERS,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        print("HF error:", response.text)
        return {}

    data = response.json()
    print("HF raw response:", data)

    try:
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print("Parse error:", e)
        return {}