import os

# Ollama Endpoint Configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Model Definitions
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:1b")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "embeddinggemma:latest")

# Groq Configuration (as fallback or optional cloud mode)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
USE_GROQ_FALLBACK = os.environ.get("USE_GROQ_FALLBACK", "false").lower() == "true"
