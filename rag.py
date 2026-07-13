SYSTEM_PROMPT = "You are ScribeLink AI, a document analysis assistant. Analyze excerpts and answer based ONLY on the context. Cite sources as [SourceNumber]. Never use raw document IDs. Output <concise> and <elaborate> sections. Never fabricate."

def build_prompt(context, query):
    return f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer with <concise> and <elaborate>. Cite sources as [1], [2] etc. No HTML."
