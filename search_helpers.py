import re
from database import get_db_connection

STOPWORDS = {"what", "is", "who", "the", "under", "a", "an", "and", "or", "in", "of", "to", "for", "on", "with", "at", "by", "from", "here", "there", "any", "was", "were", "been", "has", "have", "had", "do", "does", "did", "about", "how", "should", "we", "be", "able", "try"}

def tokenize(query):
    raw_tokens = [t.lower().strip("?,.!") for t in re.split(r'\W+', query) if t.strip("?,.!")]
    filtered = [t for t in raw_tokens if t not in STOPWORDS]
    return filtered if filtered else raw_tokens

def get_meta_query_context(project=None, doc_id=None, date_from=None, date_to=None):
    conn = get_db_connection(); c = conn.cursor()
    sql = "SELECT id, title, date, lot_id, project_id, file_path, ocr_markdown FROM meetings"
    where, params = [], []
    if project:
        proj_list = [p.strip() for p in project.split(",") if p.strip()]
        if proj_list:
            where.append(f"project_id IN ({','.join('?' for _ in proj_list)})")
            params.extend(proj_list)
    if doc_id:
        doc_list = [d.strip() for d in doc_id.split(",") if d.strip()]
        if doc_list:
            where.append(f"id IN ({','.join('?' for _ in doc_list)})")
            params.extend(doc_list)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date DESC"
    c.execute(sql, params)
    rows = c.fetchall()
    
    c.execute("SELECT id, summary_text FROM hierarchical_summaries WHERE level = 1")
    sum_map = {r[0] if isinstance(r, tuple) else r["id"]: r[1] if isinstance(r, tuple) else r["summary_text"] for r in c.fetchall()}
    conn.close()
    
    docs = [dict(r) for r in rows]
    parts = []
    for idx, d in enumerate(docs, 1):
        summary = sum_map.get(d["id"]) or (d.get("ocr_markdown") or "").strip()
        if len(summary) > 300: summary = summary[:300] + "..."
        if not summary: summary = "No content summary available."
        parts.append(f"Source [{idx}] (ID: {d['id']}):\nTitle: {d['title']} | Date: {d['date']} | Project: {d['project_id']} | Lot: {d['lot_id']}\nContent Summary: {summary}")
    return docs, "\n\n".join(parts)

def get_context_graph(citations, query=""):
    unique_ids = list({c["meeting_id"] for c in citations})
    if not unique_ids:
        return {"nodes": [], "edges": [], "decisions": []}
        
    conn = get_db_connection(); c = conn.cursor()
    placeholders = ",".join("?" for _ in unique_ids)
    c.execute(f"SELECT id, title, date, lot_id, project_id, file_path, transcript_text FROM meetings WHERE id IN ({placeholders})", unique_ids)
    docs = [dict(r) for r in c.fetchall()]
    
    c.execute(f"SELECT d.id, d.meeting_id, d.summary, d.status, d.type, m.title meeting_title FROM decisions d JOIN meetings m ON d.meeting_id=m.id WHERE d.meeting_id IN ({placeholders})", unique_ids)
    decisions = [dict(r) for r in c.fetchall()]
    conn.close()
    
    query_terms = set(tokenize(query))
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    filtered_docs = [d for d in docs if not any((d.get("file_path") or "").lower().endswith(ext) for ext in image_exts)]

    nodes = [{"id": d["id"], "title": d["title"], "date": d["date"], "lot_id": d["lot_id"], "department": d["project_id"], "highlight": True} for d in filtered_docs]
    
    def get_keywords(text):
        if not text: return set()
        return {w for w in re.split(r'\W+', text.lower()) if len(w) > 4 and w not in STOPWORDS}
        
    edges = []
    for i in range(len(filtered_docs)):
        for j in range(i + 1, len(filtered_docs)):
            d1, d2 = filtered_docs[i], filtered_docs[j]
            kw1, kw2 = get_keywords(d1["transcript_text"]), get_keywords(d2["transcript_text"])
            shared_query_terms = query_terms.intersection(kw1).intersection(kw2)
            meta_reasons = []
            if d1["project_id"] and d1["project_id"] == d2["project_id"] and d1["project_id"] != "Unknown":
                meta_reasons.append(f"same project ({d1['project_id']})")
            if d1["lot_id"] and d1["lot_id"] == d2["lot_id"] and d1["lot_id"] is not None:
                meta_reasons.append(f"same lot ({d1['lot_id']})")
                
            if shared_query_terms:
                rationale = f"Both discuss query topic(s): '{', '.join(shared_query_terms)}'"
                if meta_reasons: rationale += " and share " + " & ".join(meta_reasons)
                edges.append({"source": d1["id"], "target": d2["id"], "type": "query_context", "rationale": rationale})
            elif meta_reasons:
                edges.append({"source": d1["id"], "target": d2["id"], "type": "metadata", "rationale": "Linked via " + " & ".join(meta_reasons)})
                
    return {"nodes": nodes, "edges": edges, "decisions": decisions}
