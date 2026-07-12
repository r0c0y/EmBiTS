import json
import urllib.request
import ssl
import os
from config import OLLAMA_BASE_URL, LLM_MODEL, GROQ_API_KEY, GROQ_MODEL, USE_GROQ_FALLBACK

def _call_ollama(messages, temperature=0.0):
    try:
        from ollama_runner import ensure_ollama_running
        ensure_ollama_running()
    except Exception:
        pass
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=30.0, context=ctx) as res:
            resp_body = json.loads(res.read().decode("utf-8"))
            return resp_body["message"]["content"]
    except Exception as e:
        print(f"Ollama call failed: {e}")
        return None

def _call_groq(messages, temperature=0.0):
    if not GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2048
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }, method="POST")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=30.0, context=ctx) as res:
            return json.loads(res.read().decode("utf-8"))["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq call failed: {e}")
        return None

def query_llm(system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    # Primary: Ollama local LLM
    res = _call_ollama(messages, temperature)
    if res:
        return res
    
    # Secondary: Fallback to Groq if permitted
    if USE_GROQ_FALLBACK:
        res = _call_groq(messages, temperature)
        if res:
            return res
            
    return "AI generation unavailable offline. Please ensure Ollama is running (`ollama serve`)."

def translate_text(text: str, target_lang: str) -> str:
    if not text:
        return ""
    sys_prompt = f"You are a professional translator. Translate the input text to {target_lang} precisely while keeping KaTeX equations, markdown structure, and citation indices unchanged. Return ONLY the translated content."
    user_prompt = f"Translate the following text into {target_lang}. Preserve all markdown formatting, bullet points, source citations (like [1], [2]), and LaTeX/KaTeX formulas ($...$, $$...$$) exactly as they are. Do not add any conversational text, notes, or explanations. Output ONLY the translation:\n\n{text}"
    return query_llm(sys_prompt, user_prompt, temperature=0.0)
