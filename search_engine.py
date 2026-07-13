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
    sql = "SELECT c.id, c.meeting_id, c.chunk_index, c.chunk_text, c.page_number, m.title, m.date, m.lot_id, m.project_id, LENGTH(m.transcript_text) as doc_len, bm25(chunks_fts) as score FROM chunks_fts JOIN chunks c ON chunks_fts.rowid = c.rowid JOIN meetings m ON m.id = c.meeting_id"
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
    sql += " WHERE " + " AND " . join(where) + " ORDER BY bm25(chunks_fts) LIMIT ?"; params.append(top_k)
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    
    # If FTS returns nothing but query terms might match document titles,
    # fall back to title-matched documents
    if not rows and tokens:
        titles_sql = "SELECT m.id as meeting_id, m.title, m.date, m.lot_id, m.project_id, LENGTH(m.transcript_text) as doc_len FROM meetings m WHERE 1=1"
        title_params = []
        if project:
            proj_list = [p.strip() for p in project.split(",") if p.strip()]
            if proj_list:
                titles_sql += f" AND m.project_id IN ({','.join('?' for _ in proj_list)})"
                title_params.extend(proj_list)
        if doc_id:
            doc_list = [d.strip() for d in doc_id.split(",") if d.strip()]
            if doc_list:
                titles_sql += f" AND m.id IN ({','.join('?' for _ in doc_list)})"
                title_params.extend(doc_list)
        c.execute(titles_sql, title_params)
        for r in c.fetchall():
            title_lower = (r["title"] or "").lower()
            title_matches = sum(1 for t in tokens if t in title_lower)
            if title_matches >= 2 or (title_matches >= 1 and len(tokens) <= 3):
                # Create a synthetic entry using the first chunk of this doc
                c.execute("SELECT id, chunk_index, chunk_text, page_number FROM chunks WHERE meeting_id=? ORDER BY chunk_index LIMIT 1", (r["meeting_id"],))
                ch = c.fetchone()
                if ch:
                    rows.append({
                        "id": ch["id"],
                        "meeting_id": r["meeting_id"],
                        "chunk_index": ch["chunk_index"],
                        "chunk_text": ch["chunk_text"],
                        "page_number": ch["page_number"] or 1,
                        "title": r["title"],
                        "date": r["date"],
                        "lot_id": r["lot_id"],
                        "project_id": r["project_id"],
                        "doc_len": r["doc_len"] or 1,
                        "score": title_matches * 10.0,
                        "_title_match": title_matches,
                        "_is_title_fallback": True
                    })
    
    conn.close()

    # Title boost + length normalization for all results
    query_lower = query.lower()
    for r in rows:
        if r.get("_is_title_fallback"):
            continue
        title = (r.get("title") or "").lower()
        title_matches = sum(1 for t in tokens if t in title)
        doc_len = r.get("doc_len") or 1
        length_norm = 1.0 / max(1.0, (doc_len / 1000) ** 0.3)
        title_bonus = title_matches * 5.0
        r["score"] = float(r["score"]) * length_norm + title_bonus
        r["_title_match"] = title_matches

    rows.sort(key=lambda x: -x["score"])
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
    selected_doc_ids = []
    if doc_id:
        selected_doc_ids = [d.strip() for d in doc_id.split(",") if d.strip()]

    if is_meta_query(query):
        docs, context = get_meta_query_context(project, doc_id, date_from, date_to)
        out = [{"meeting_id": d["id"], "meeting_title": d["title"], "date": d["date"], "lot_id": d["lot_id"], "department": d["project_id"], "text": (d.get("ocr_markdown") or "Metadata entry")[:200] + "...", "confidence": 1.0} for d in docs]
        ans = query_llm("You are ScribeLink AI. Analyze the context and write the answer.", build_prompt(context, query))
        return {"answer": ans, "citations": out, "graph": get_context_graph(out, query, selected_doc_ids), "conflicts": []}

    citations = hybrid_search(query, project, doc_id, top_k=15)
    if not citations:
        if selected_doc_ids:
            return {"answer": "No relevant text matching the query was found in the selected documents.", "citations": [], "graph": get_context_graph([], query, selected_doc_ids), "conflicts": []}
        return {"answer": "No relevant documents found.", "citations": [], "graph": {"nodes":[], "edges":[]}, "conflicts":[]}
        
    # Build unique citation entries by document
    seen, out = set(), []
    for c in citations:
        mid = c["meeting_id"]
        if mid not in seen:
            seen.add(mid)
            # Prepend document title to citation text for context
            title = c["title"]
            full_text = c["chunk_text"]
            enriched_text = f"[Document: {title}] {full_text}"
            out.append({
                "meeting_id": mid,
                "meeting_title": title,
                "date": c["date"],
                "lot_id": c["lot_id"],
                "department": c["project_id"],
                "text": enriched_text,
                "page_number": c.get("page_number") or 1,
                "confidence": c.get("score", 0.5)
            })
            
    # Consolidate top chunks for context - per-document limit with query relevance boost
    from search_helpers import tokenize
    query_terms = set(tokenize(query))
    
    # Score each citation by query relevance (include title in matching)
    for c in citations:
        c_text = ((c.get("title") or "") + " " + (c.get("chunk_text") or ""))
        c_tokens = set(tokenize(c_text))
        overlap = len(query_terms & c_tokens)
        overlap_ratio = overlap / max(len(query_terms), 1)
        c["_qscore"] = c.get("score", 0) * 0.3 + overlap_ratio * 0.7
    
    citations.sort(key=lambda x: -x.get("_qscore", 0))
    
    grouped = {}
    for c in citations[:12]:
        mid = c["meeting_id"]
        if mid not in grouped:
            grouped[mid] = {"chunks": [], "max_qscore": c.get("_qscore", 0)}
        if len(grouped[mid]["chunks"]) < 3:
            grouped[mid]["chunks"].append(c)
            grouped[mid]["max_qscore"] = max(grouped[mid]["max_qscore"], c.get("_qscore", 0))
    
    grouped_docs = []
    for mid, data in grouped.items():
        chunks = data["chunks"]
        chunks.sort(key=lambda x: x["chunk_index"])
        doc_date = chunks[0].get("date") or "0000-00-00"
        grouped_docs.append({
            "meeting_id": mid,
            "date": doc_date,
            "title": chunks[0]["title"],
            "chunks": chunks,
            "_max_qscore": data["max_qscore"]
        })
    
    # Sort chronologically (oldest to newest), but put the most query-relevant source first
    grouped_docs.sort(key=lambda x: x.get("_max_qscore", 0), reverse=True)

    # Then sort chunks within each doc chronologically
    for doc in grouped_docs:
        doc["chunks"].sort(key=lambda x: x["chunk_index"])

    # Fetch hierarchical summaries (level 1 = per-doc)
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, level, summary_text FROM hierarchical_summaries WHERE level = 1")
    sum_map = {r[0]: r[2] for r in c.fetchall()}
    conn.close()

    parts = []
    for idx, doc in enumerate(grouped_docs, 1):
        is_latest = " (LATEST REVISION / OVERRIDE SOURCE)" if idx == len(grouped_docs) else ""
        title_line = f"Document Title: {doc['title']}"
        
        # Put hierarchical summary BEFORE chunk excerpts
        doc_summary = sum_map.get(doc["meeting_id"])
        summary_part = f"\n  * Summary: {doc_summary}" if doc_summary else ""
        
        excerpts = "\n".join([f"  * Excerpt (Chunk {ch['chunk_index']}, Page {ch.get('page_number') or 1}): {ch['chunk_text']}" for ch in doc["chunks"]])
        parts.append(f"Source [{idx}] (ID: {doc['meeting_id']}):\n{title_line}\nDocument Date: {doc['date']}{is_latest}{summary_part}\n{excerpts}")
    context = "\n\n".join(parts)

    # No separate hierarchical context block at the end — already embedded per-source above
        
    sys_prompt = """You are ScribeLink AI, a precise document analysis assistant.

RULES (follow strictly):
1. Answer ONLY based on the provided context. NEVER fabricate.
2. Each source in the context has a Document Title. Use the title to determine which sources are relevant to the user's query. Focus your answer on the sources whose titles match the query topic.
3. If a source's title clearly matches the query topic, prioritize it. If a source's title is unrelated to the query, mention it only if it directly answers the query.
4. Chunks are sorted by relevance (most relevant first), not chronologically.
5. The LATEST document is the OVERRIDE source — if contradictions exist, the newest one wins.
6. Cite sources as [SourceNumber] (e.g. [1], [2]) matching the source numbers in excerpts.
7. NEVER use raw document IDs like DOC-XXXXXXXX.
8. NEVER output raw HTML tags, DO NOT include `<html>`, `<body>`, `<div>`, or any HTML markup.
9. NEVER output raw document IDs or internal file paths.
10. Use clean Markdown only.

OUTPUT FORMAT:
Wrap your response in these XML tags:
  <concise>
  A detailed synthesis directly answering the query. Use paragraphs, **bold**, bullet points, and markdown tables with proper spacing for readability.
  </concise>
  <elaborate>
  A deep-dive chronological analysis showing exactly how decisions evolved, tracing each step with [SourceNumber] citations.
  </elaborate>

Use KaTeX for equations ($...$ or $$...$$) and plain markdown tables. Keep it clean and professional."""
    ans = query_llm(sys_prompt, build_prompt(context, query))
    
    # ponytail: post-process local LLM output to guarantee XML tags for UI compatibility
    import re
    has_actual_tags = bool(re.search(r"<concise>.*?</concise>", ans, re.DOTALL)) and bool(re.search(r"<elaborate>.*?</elaborate>", ans, re.DOTALL))
    if ans and not has_actual_tags:
        clean_ans = ans.replace("<concise>", "").replace("</concise>", "").replace("<elaborate>", "").replace("</elaborate>", "")
        bullets = [line.strip().lstrip("-* ") for line in clean_ans.split("\n") if line.strip().startswith(("*", "-"))]
        concise_part = "\n".join(f"- {b}" for b in bullets[:3]) if bullets else f"- {clean_ans[:200].strip()}..."
        ans = f"<concise>\n{concise_part}\n</concise>\n<elaborate>\n{clean_ans.strip()}\n</elaborate>"
        
    return {"answer": ans, "citations": out, "graph": get_context_graph(out, query, selected_doc_ids), "conflicts": detect_conflicts(out)}
