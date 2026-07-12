import json
import urllib.request
import ssl
from config import OLLAMA_BASE_URL, EMBEDDING_MODEL

def get_embedding(text: str) -> list:
    """Generate text embeddings using Ollama local endpoints."""
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {
        "model": EMBEDDING_MODEL,
        "prompt": text
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=15.0, context=ctx) as res:
            resp_body = json.loads(res.read().decode("utf-8"))
            return resp_body.get("embedding", [])
    except Exception as e:
        print(f"Ollama embedding failed for model '{EMBEDDING_MODEL}': {e}")
        return []
