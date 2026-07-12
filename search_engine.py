import math
from database import get_db_connection
from conflict import detect_conflicts
from rag import build_prompt
from llm_client import query_llm
from embedder import get_embedding
from vector_store import vector_search
from search_helpers import tokenize, get_meta_query_context, get_context_graph

def is_meta_query(query):
    q = query.lower()
    triggers = ["list all document", "list document", "all document", "all files", "show all document", "show document", "summary of all", "project list", "what documents", "what files", "how many files", "how many document", "list meetings", "all meetings"]
    return any(t in q for t in triggers)

def keyword_search(query, project=None, doc_id=None, top_k=30):
    tokens = tokenize(query)
    if not tokens: return []
    conn = get_db_connection(); c = conn.cursor()
    fts_q = " OR ".join(tokens)
    sql = "SELECT c.id, c.meeting_id, c.chunk_index, c.chunk_text, m.title, m.date, m.lot_id, m.project_id, bm25(chunks_fts) as score FROM chunks_fts JOIN chunks c ON chunks_fts.rowid = c.rowid JOIN meetings m ON m.id = c.meeting_id"
    params, where = [fts_q], ["chunks_fts MATCH ?"]
    if project:
        proj_list = [p.strip() for p in project.split(",") if p.strip()]
        if proj_list:
            where.append(f"m.project_id IN ({','.join('?' for _ in proj_list)})")
            params.extend(proj_list)
    if doc_id:
        doc_list = [d.strip() for d in doc_id.split(",") if d.strip()]
        if doc_list:
            where.append(f"m.id IN ({','.join('?' for _ in doc_list)})")
            params.extend(doc_list)
    sql += " WHERE " + " AND ".join(where) + " ORDER BY bm25(chunks_fts) LIMIT ?"; params.append(top_k)
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def hybrid_search(query, project=None, doc_id=None, top_k=15) -> list:
    """Combine FTS5 BM25 search and Vector Search using Reciprocal Rank Fusion (RRF)."""
    # 1. Run FTS Search
    fts_results = keyword_search(query, project, doc_id, top_k=30)
    
    # 2. Run Vector Search
    query_vec = get_embedding(query)
    vector_results = vector_search(query_vec, project, doc_id, top_k=30) if query_vec else []
    
    # 3. Apply Reciprocal Rank Fusion (RRF)
    rrf_scores = {}
    doc_map = {}
    
    for rank, item in enumerate(fts_results, 1):
        cid = item["id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
        doc_map[cid] = item
        
    for rank, item in enumerate(vector_results, 1):
        cid = item["id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
        # Ensure we have the dict item, preference to vector metadata if not in FTS
        if cid not in doc_map:
            doc_map[cid] = item
            
    # Sort by RRF score
    sorted_cids = sorted(rrf_scores.keys(), key=lambda x: -rrf_scores[x])
    
    results = []
    for cid in sorted_cids[:top_k]:
        item = doc_map[cid].copy()
        # Custom normalized score for UI visualization (0.0 - 1.0)
        item["score"] = round(min(0.99, rrf_scores[cid] * 30), 2)
        results.append(item)
        
    return results

def execute_trace(query, project=None, doc_id=None, date_from=None, date_to=None):
    if is_meta_query(query):
        docs, context = get_meta_query_context(project, doc_id, date_from, date_to)
        out = [{"meeting_id": d["id"], "meeting_title": d["title"], "date": d["date"], "lot_id": d["lot_id"], "department": d["project_id"], "text": (d.get("ocr_markdown") or "Metadata entry")[:200] + "...", "confidence": 1.0} for d in docs]
        ans = query_llm("You are ScribeLink AI. Analyze the context and write the answer.", build_prompt(context, query))
        return {"answer": ans, "citations": out, "graph": get_context_graph(out, query), "conflicts": []}

    citations = hybrid_search(query, project, doc_id, top_k=15)
    if not citations:
        return {"answer": "No relevant documents found.", "citations": [], "graph": {"nodes":[], "edges":[]}, "conflicts":[]}
        
    # Build unique citation entries by document
    seen, out = set(), []
    for c in citations:
        mid = c["meeting_id"]
        if mid not in seen:
            seen.add(mid)
            out.append({"meeting_id": mid, "meeting_title": c["title"], "date": c["date"], "lot_id": c["lot_id"], "department": c["project_id"], "text": c["chunk_text"], "confidence": c.get("score", 0.5)})
            
    # Consolidate top chunks for context and sort chronologically
    grouped = {}
    for c in citations[:10]:
        grouped.setdefault(c["meeting_id"], []).append(c)
    
    grouped_docs = []
    for mid, chunks in grouped.items():
        chunks.sort(key=lambda x: x["chunk_index"])
        doc_date = chunks[0].get("date") or "0000-00-00"
        grouped_docs.append({
            "meeting_id": mid,
            "date": doc_date,
            "title": chunks[0]["title"],
            "chunks": chunks
        })
    
    # Sort chronologically (oldest to newest)
    grouped_docs.sort(key=lambda x: x["date"])
    
    parts = []
    for idx, doc in enumerate(grouped_docs, 1):
        is_latest = " (LATEST REVISION / OVERRIDE SOURCE)" if idx == len(grouped_docs) else ""
        excerpts = "\n".join([f"  * Excerpt (Chunk {ch['chunk_index']}): {ch['chunk_text']}" for ch in doc["chunks"]])
        parts.append(f"Source [{idx}] (ID: {doc['meeting_id']}):\nDocument Title: {doc['title']}\nDocument Date: {doc['date']}{is_latest}\n{excerpts}")
    context = "\n\n".join(parts)
    
    # Check for hierarchical summaries context
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, level, summary_text FROM hierarchical_summaries WHERE level = 1")
    sum_parts = [f"Summary (Doc ID: {r[0]}): {r[2]}" for r in c.fetchall() if r[0] in seen]
    conn.close()
    if sum_parts:
        context += "\n\n=== Hierarchical Summary Context ===\n" + "\n\n".join(sum_parts)
        
    sys_prompt = "You are ScribeLink AI, a document analysis assistant. Analyze the excerpts and answer based ONLY on context. Chunks are sorted chronologically (oldest to newest). If different sources contain contradicting decisions, tasks, or specifications for the same topic, you MUST prioritize the newer document (marked as LATEST REVISION / OVERRIDE SOURCE) and note that it overrides the older information. Cite matching sources as [1], [2] corresponding to their source number. Never use raw document IDs. You MUST format your response by wrapping your sections in XML tags like this: <concise>- bullet 1\n- bullet 2</concise> and <elaborate>detailed reasoning with headers</elaborate>. Format equations in KaTeX ($...$ or $$...$$). Tables in markdown."
    ans = query_llm(sys_prompt, build_prompt(context, query))
    
    # ponytail: post-process local LLM output to guarantee XML tags for UI compatibility
    import re
    has_actual_tags = bool(re.search(r"<concise>.*?</concise>", ans, re.DOTALL)) and bool(re.search(r"<elaborate>.*?</elaborate>", ans, re.DOTALL))
    if ans and not has_actual_tags:
        clean_ans = ans.replace("<concise>", "").replace("</concise>", "").replace("<elaborate>", "").replace("</elaborate>", "")
        bullets = [line.strip().lstrip("-* ") for line in clean_ans.split("\n") if line.strip().startswith(("*", "-"))]
        concise_part = "\n".join(f"- {b}" for b in bullets[:3]) if bullets else f"- {clean_ans[:200].strip()}..."
        ans = f"<concise>\n{concise_part}\n</concise>\n<elaborate>\n{clean_ans.strip()}\n</elaborate>"
        
    return {"answer": ans, "citations": out, "graph": get_context_graph(out, query), "conflicts": detect_conflicts(out)}
