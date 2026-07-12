import json, ssl, urllib.request, os, re
from database import get_db_connection
from conflict import detect_conflicts
from rag import build_prompt

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Check for local file fallback
for path in ["groq_key.txt", "../groq_key.txt", "../../groq_key.txt"]:
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                key = f.read().strip()
                if key and "GROQ_API_KEY" not in os.environ:
                    os.environ["GROQ_API_KEY"] = key
        except Exception:
            pass

GROQ_KEYS = [k.strip() for k in os.environ.get("GROQ_API_KEY", "").split(",") if k.strip()]

def call_groq_api(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    data = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "You are ScribeLink AI, a document analysis assistant. Analyze the provided document excerpts and answer based ONLY on the context. You must cite your sources in the text using format [1], [2], etc., corresponding to the source number provided in the context. Never use raw document IDs in your answer. Output <concise> (2-4 bullets) and <elaborate> (detailed reasoning with headers). Never fabricate information. When presenting mathematical equations, format them in standard KaTeX syntax ($...$ or $$...$$). When presenting structured data or tables, construct them using markdown table pipelines."},
            {"role": "user", "content": prompt}
        ], "temperature": 0.0, "max_tokens": 2048
    }).encode("utf-8")
    ctx = ssl._create_unverified_context()
    for key in GROQ_KEYS:
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30.0, context=ctx) as res:
                return json.loads(res.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception: pass
    return None

def translate_text(text: str, target_lang: str):
    if not text:
        return ""
    prompt = f"Translate the following text into {target_lang}. Preserve all markdown formatting, bullet points, source citations (like [1], [2]), and LaTeX/KaTeX formulas ($...$, $$...$$) exactly as they are. Do not add any conversational text, notes, or explanations. Output ONLY the translation:\n\n{text}"
    url = "https://api.groq.com/openai/v1/chat/completions"
    data = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": f"You are a professional translator. Translate the input text to {target_lang} precisely while keeping KaTeX equations, markdown structure, and citation indices unchanged. Return ONLY the translated content."},
            {"role": "user", "content": prompt}
        ], "temperature": 0.0, "max_tokens": 2048
    }).encode("utf-8")
    ctx = ssl._create_unverified_context()
    for key in GROQ_KEYS:
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30.0, context=ctx) as res:
                return json.loads(res.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception: pass
    return None

STOPWORDS = {"what", "is", "who", "the", "under", "a", "an", "and", "or", "in", "of", "to", "for", "on", "with", "at", "by", "from", "here", "there", "any", "was", "were", "been", "has", "have", "had", "do", "does", "did", "about", "how", "should", "we", "be", "able", "try"}

def tokenize(query):
    raw_tokens = [t.lower().strip("?,.!") for t in re.split(r'\W+', query) if t.strip("?,.!")]
    filtered = [t for t in raw_tokens if t not in STOPWORDS]
    return filtered if filtered else raw_tokens

def keyword_search(query, project=None, date_from=None, date_to=None, top_k=5):
    tokens = tokenize(query)
    if not tokens: return []
    conn = get_db_connection(); c = conn.cursor()
    fts_q = " OR ".join(tokens)
    sql = "SELECT c.meeting_id, c.chunk_index, c.chunk_text, m.title, m.date, m.lot_id, m.project_id, bm25(chunks_fts) as score"
    sql += " FROM chunks_fts JOIN chunks c ON chunks_fts.rowid = c.rowid JOIN meetings m ON m.id = c.meeting_id"
    params, where = [fts_q], ["chunks_fts MATCH ?"]
    if project: where.append("m.project_id = ?"); params.append(project)
    if date_from: where.append("m.date >= ?"); params.append(date_from)
    if date_to: where.append("m.date <= ?"); params.append(date_to)
    sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY bm25(chunks_fts) LIMIT ?"; params.append(top_k)
    c.execute(sql, params)
    results = [dict(r) for r in c.fetchall()]
    conn.close()
    return results

def keyword_search(query, project=None, doc_id=None, date_from=None, date_to=None, top_k=30):
    tokens = tokenize(query)
    if not tokens: return []
    conn = get_db_connection(); c = conn.cursor()
    fts_q = " OR ".join(tokens)
    sql = "SELECT c.meeting_id, c.chunk_index, c.chunk_text, m.title, m.date, m.lot_id, m.project_id, bm25(chunks_fts) as score"
    sql += " FROM chunks_fts JOIN chunks c ON chunks_fts.rowid = c.rowid JOIN meetings m ON m.id = c.meeting_id"
    params, where = [fts_q], ["chunks_fts MATCH ?"]
    if project:
        proj_list = [p.strip() for p in project.split(",") if p.strip()]
        if proj_list:
            placeholders = ",".join("?" for _ in proj_list)
            where.append(f"m.project_id IN ({placeholders})")
            params.extend(proj_list)
    if doc_id:
        doc_list = [d.strip() for d in doc_id.split(",") if d.strip()]
        if doc_list:
            placeholders = ",".join("?" for _ in doc_list)
            where.append(f"m.id IN ({placeholders})")
            params.extend(doc_list)
    if date_from: where.append("m.date >= ?"); params.append(date_from)
    if date_to: where.append("m.date <= ?"); params.append(date_to)
    sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY bm25(chunks_fts) LIMIT ?"; params.append(top_k)
    c.execute(sql, params)
    results = [dict(r) for r in c.fetchall()]
    conn.close()
    return results

def is_meta_query(query):
    q = query.lower()
    triggers = [
        "list all document", "list document", "all document", "all files",
        "show all document", "show document", "summary of all", "project list",
        "what documents", "what files", "how many files", "how many document",
        "list meetings", "all meetings"
    ]
    return any(t in q for t in triggers)

def generate_hierarchical_tree_task(doc_id: str, project_id: str, text: str, title: str):
    # 1. Level 1: Document abstractive summary
    prompt_l1 = f"""Below is the complete raw text extracted from the document titled '{title}'. 
Write a concise, comprehensive abstractive summary of this document. Focus on key decisions, dates, actions, participants, and status updates.

DOCUMENT TEXT:
{text}"""
    summary_l1 = call_groq_api(prompt_l1)
    if not summary_l1:
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Save Level 1 summary
    c.execute("INSERT OR REPLACE INTO hierarchical_summaries (id, project_id, level, summary_text, source_ids) VALUES (?, ?, 1, ?, ?)",
              (doc_id, project_id, summary_l1, doc_id))
    conn.commit()
    
    # 2. Level 2: Project-wide summary update
    c.execute("SELECT id, summary_text FROM hierarchical_summaries WHERE project_id = ? AND level = 1", (project_id,))
    rows = c.fetchall()
    
    if rows:
        level_1_items = []
        doc_ids = []
        for r in rows:
            level_1_items.append(f"Document ID: {r['id']}\nSummary: {r['summary_text']}")
            doc_ids.append(r['id'])
        
        joined_summaries = "\n\n".join(level_1_items)
        prompt_l2 = f"""Below are individual document summaries for all files ingested under Project '{project_id}'. 
Write a unified, high-level project status summary. Synthesize timelines, critical issues, and actions across all documents.

DOCUMENT SUMMARIES:
{joined_summaries}"""
        summary_l2 = call_groq_api(prompt_l2)
        if summary_l2:
            c.execute("INSERT OR REPLACE INTO hierarchical_summaries (id, project_id, level, summary_text, source_ids) VALUES (?, ?, 2, ?, ?)",
                      (f"PROJ-{project_id}", project_id, summary_l2, ",".join(doc_ids)))
            conn.commit()
            
    conn.close()

def build_existing_hierarchical_summaries():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, project_id, transcript_text, title FROM meetings WHERE id NOT IN (SELECT id FROM hierarchical_summaries WHERE level = 1)")
        rows = c.fetchall()
        conn.close()
        
        for doc_id, project_id, text, title in rows:
            generate_hierarchical_tree_task(doc_id, project_id, text, title)
    except Exception as e:
        print("Error building existing summaries:", e)

def search_hierarchical_summaries(query: str, project: str = None):
    tokens = tokenize(query)
    if not tokens: return []
    fts_q = " OR ".join(tokens)
    conn = get_db_connection(); c = conn.cursor()
    sql = "SELECT h.id, h.project_id, h.level, h.summary_text, bm25(hierarchical_summaries_fts) as score"
    sql += " FROM hierarchical_summaries_fts JOIN hierarchical_summaries h ON hierarchical_summaries_fts.rowid = h.rowid"
    params = [fts_q]
    where = ["hierarchical_summaries_fts MATCH ?"]
    if project:
        proj_list = [p.strip() for p in project.split(",") if p.strip()]
        if proj_list:
            placeholders = ",".join("?" for _ in proj_list)
            where.append(f"h.project_id IN ({placeholders})")
            params.extend(proj_list)
    sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score LIMIT 5"
    try:
        c.execute(sql, params)
        res = [dict(r) for r in c.fetchall()]
    except Exception:
        res = []
    conn.close()
    return res

def get_meta_query_context(project=None, doc_id=None, date_from=None, date_to=None):
    conn = get_db_connection(); c = conn.cursor()
    sql = "SELECT id, title, date, lot_id, project_id, file_path, ocr_markdown FROM meetings"
    where = []
    params = []
    if project:
        proj_list = [p.strip() for p in project.split(",") if p.strip()]
        if proj_list:
            placeholders = ",".join("?" for _ in proj_list)
            where.append(f"project_id IN ({placeholders})")
            params.extend(proj_list)
    if doc_id:
        doc_list = [d.strip() for d in doc_id.split(",") if d.strip()]
        if doc_list:
            placeholders = ",".join("?" for _ in doc_list)
            where.append(f"id IN ({placeholders})")
            params.extend(doc_list)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date DESC"
    c.execute(sql, params)
    rows = c.fetchall()
    
    # Pre-fetch Level 1 summaries
    c.execute("SELECT id, summary_text FROM hierarchical_summaries WHERE level = 1")
    sum_map = {r[0]: r[1] for r in c.fetchall()}
    conn.close()
    
    docs = [dict(r) for r in rows]
    parts = []
    for idx, d in enumerate(docs, 1):
        summary = sum_map.get(d["id"])
        if not summary:
            summary = (d.get("ocr_markdown") or "").strip()
            if len(summary) > 300:
                summary = summary[:300] + "..."
        if not summary:
            summary = "No content summary available."
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
    
    # Filter out image files from the context graph
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    filtered_docs = []
    for d in docs:
        fp = (d.get("file_path") or "").lower()
        if any(fp.endswith(ext) for ext in image_exts):
            continue
        filtered_docs.append(d)

    nodes = []
    for d in filtered_docs:
        nodes.append({
            "id": d["id"],
            "title": d["title"],
            "date": d["date"],
            "lot_id": d["lot_id"],
            "department": d["project_id"],
            "highlight": True
        })
        
    def get_keywords(text):
        if not text: return set()
        words = re.split(r'\W+', text.lower())
        return {w for w in words if len(w) > 4 and w not in STOPWORDS}
        
    edges = []
    for i in range(len(filtered_docs)):
        for j in range(i + 1, len(filtered_docs)):
            d1, d2 = filtered_docs[i], filtered_docs[j]
            kw1 = get_keywords(d1["transcript_text"])
            kw2 = get_keywords(d2["transcript_text"])
            
            shared_query_terms = query_terms.intersection(kw1).intersection(kw2)
            meta_reasons = []
            if d1["project_id"] and d1["project_id"] == d2["project_id"] and d1["project_id"] != "Unknown":
                meta_reasons.append(f"same project ({d1['project_id']})")
            if d1["lot_id"] and d1["lot_id"] == d2["lot_id"] and d1["lot_id"] is not None:
                meta_reasons.append(f"same lot ({d1['lot_id']})")
                
            if shared_query_terms:
                terms_str = ", ".join(shared_query_terms)
                rationale = f"Both discuss query topic(s): '{terms_str}'"
                if meta_reasons:
                    rationale += " and share " + " & ".join(meta_reasons)
                edges.append({
                    "source": d1["id"],
                    "target": d2["id"],
                    "type": "query_context",
                    "rationale": rationale
                })
            elif meta_reasons:
                edges.append({
                    "source": d1["id"],
                    "target": d2["id"],
                    "type": "metadata",
                    "rationale": "Linked via " + " & ".join(meta_reasons)
                })
                
    return {"nodes": nodes, "edges": edges, "decisions": decisions}

def execute_trace(query, project=None, doc_id=None, date_from=None, date_to=None):
    # Check if this is a meta query targeting lists/details of documents
    if is_meta_query(query):
        docs, context = get_meta_query_context(project, doc_id, date_from, date_to)
        if docs:
            out = []
            for d in docs:
                text_snippet = d.get("ocr_markdown") or "Document metadata entry."
                if len(text_snippet) > 200:
                    text_snippet = text_snippet[:200] + "..."
                out.append({
                    "meeting_id": d["id"],
                    "meeting_title": d["title"],
                    "date": d["date"],
                    "lot_id": d["lot_id"],
                    "department": d["project_id"],
                    "text": text_snippet,
                    "confidence": 1.00
                })
            prompt = build_prompt(context, query)
            answer = call_groq_api(prompt)
            if not answer:
                answer = f"<concise>\n- AI analysis unavailable. Showing list of matching documents.\n</concise>\n<elaborate>\n{context}\n</elaborate>"
            return {
                "answer": answer,
                "citations": out,
                "graph": get_context_graph(out, query),
                "conflicts": []
            }

    citations = keyword_search(query, project, doc_id, date_from, date_to, top_k=30)
    if not citations:
        if doc_id:
            conn = get_db_connection(); c = conn.cursor()
            doc_list = [d.strip() for d in doc_id.split(",") if d.strip()]
            if doc_list:
                placeholders = ",".join("?" for _ in doc_list)
                c.execute(f"SELECT c.meeting_id, c.chunk_index, c.chunk_text, m.title, m.date, m.lot_id, m.project_id FROM chunks c JOIN meetings m ON m.id = c.meeting_id WHERE m.id IN ({placeholders}) ORDER BY c.chunk_index LIMIT 30", doc_list)
                citations = [dict(r) for r in c.fetchall()]
                for cit in citations:
                    cit["score"] = 0.0
            conn.close()
        elif project:
            conn = get_db_connection(); c = conn.cursor()
            proj_list = [p.strip() for p in project.split(",") if p.strip()]
            if proj_list:
                placeholders = ",".join("?" for _ in proj_list)
                c.execute(f"SELECT c.meeting_id, c.chunk_index, c.chunk_text, m.title, m.date, m.lot_id, m.project_id FROM chunks c JOIN meetings m ON m.id = c.meeting_id WHERE m.project_id IN ({placeholders}) ORDER BY m.date DESC, c.chunk_index LIMIT 30", proj_list)
                citations = [dict(r) for r in c.fetchall()]
                for cit in citations:
                    cit["score"] = 0.0
            conn.close()

    if not citations:
        return {"answer": "No relevant documents found for your query.", "citations": [], "graph": {"nodes":[],"edges":[]}, "conflicts":[]}
        
    seen = set()
    unique_citations = []
    for c in citations:
        mid = c["meeting_id"]
        if mid not in seen:
            seen.add(mid)
            unique_citations.append(c)
            
    import math
    def get_confidence_score(bm25_score):
        abs_score = abs(bm25_score)
        try:
            conf = 1.0 - (1.0 / (1.0 + math.exp(abs_score / 10.0 - 0.5)))
            return round(max(0.01, min(0.99, conf)), 2)
        except Exception:
            return 0.50
            
    out = []
    for c in unique_citations:
        out.append({
            "meeting_id": c["meeting_id"],
            "meeting_title": c["title"],
            "date": c["date"],
            "lot_id": c["lot_id"],
            "department": c["project_id"],
            "text": c["chunk_text"],
            "confidence": get_confidence_score(c["score"])
        })
        
    # Group and consolidate chunks by document
    grouped_chunks = {}
    for c in citations[:15]:
        mid = c["meeting_id"]
        if mid not in grouped_chunks:
            grouped_chunks[mid] = []
        grouped_chunks[mid].append(c)
        
    context_parts = []
    for idx, (mid, chunks) in enumerate(grouped_chunks.items(), 1):
        chunks.sort(key=lambda x: x["chunk_index"])
        title = chunks[0]["title"]
        excerpts_str = "\n".join([f"  * Excerpt (Chunk {ch['chunk_index']}): {ch['chunk_text']}" for ch in chunks])
        context_parts.append(f"Source [{idx}] (ID: {mid}):\nDocument Title: {title}\n{excerpts_str}")
    context = "\n\n".join(context_parts)
    
    # Query and append hierarchical summaries
    summaries = search_hierarchical_summaries(query, project)
    summary_parts = []
    for s_idx, s in enumerate(summaries, 1):
        lbl = "Project-Wide Summary" if s["level"] == 2 else f"Document Summary (ID: {s['id']})"
        summary_parts.append(f"Hierarchical Summary [{s_idx}] ({lbl}):\n{s['summary_text']}")
    
    if summary_parts:
        context += "\n\n=== Hierarchical Summary Context ===\n" + "\n\n".join(summary_parts)
        
    prompt = build_prompt(context, query)
    answer = call_groq_api(prompt)
    if not answer:
        answer = f"<concise>\n- AI analysis unavailable. Showing top matching excerpts.\n</concise>\n<elaborate>\n{context[:1800]}\n</elaborate>"
        
    return {
        "answer": answer,
        "citations": out,
        "graph": get_context_graph(out, query),
        "conflicts": detect_conflicts(out)
    }
