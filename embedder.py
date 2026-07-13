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
    except Exception:
        return []

def get_embeddings_batch(texts: list, batch_size: int = 50) -> list:
    """Generate embeddings for multiple texts in batches using Ollama's /api/embed batch endpoint."""
    if not texts:
        return []
    
    url = f"{OLLAMA_BASE_URL}/api/embed"
    results = []
    ctx = ssl._create_unverified_context()
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        payload = {
            "model": EMBEDDING_MODEL,
            "input": batch
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30.0, context=ctx) as res:
                resp_body = json.loads(res.read().decode("utf-8"))
                embs = resp_body.get("embeddings", [])
                if len(embs) < len(batch):
                    embs.extend([[]] * (len(batch) - len(embs)))
                results.extend(embs[:len(batch)])
        except Exception as e:
            print(f"Batch embedding request failed: {e}. Falling back to individual queries.")
            batch_results = []
            for text in batch:
                emb = get_embedding(text)
                batch_results.append(emb)
            results.extend(batch_results)
            
    return results
