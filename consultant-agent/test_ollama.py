import requests
import json

url = "http://localhost:11434/api/generate"
prompt = """Generate 3 WorldQuant Brain alpha expressions. Return ONLY valid JSON.

Fields: close, volume, returns
Operators: ts_rank, ts_mean, ts_std_dev
Lookback: 60

REQUIRED JSON FORMAT (no other text):
{"expressions": ["expression1", "expression2", "expression3"]}

Example:
{"expressions": ["ts_rank(close, 60)", "ts_mean(volume, 60)", "ts_std_dev(returns, 60)"]}

JSON:"""

payload = {
    "model": "gemma3:4b",
    "prompt": prompt,
    "stream": False
}

print("發送請求到 Ollama...")
response = requests.post(url, json=payload, timeout=60)
print(f"狀態碼: {response.status_code}")
result = response.json()
print(f"回應: {result.get('response', '')[:500]}")
