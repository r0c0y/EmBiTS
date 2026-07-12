from database import get_db_connection
from llm_client import query_llm

def generate_hierarchical_tree_task(doc_id: str, project_id: str, text: str, title: str):
    """Generate Level 1 document summary and Level 2 project status summary."""
    # 1. Level 1 document summary
    prompt_l1 = f"Below is the complete raw text extracted from the document titled '{title}'. Write a concise, comprehensive abstractive summary of this document. Focus on key decisions, dates, actions, participants, and status updates.\n\nDOCUMENT TEXT:\n{text}"
    sys_prompt = "You are a professional technical summarizer. Create a clear summary focusing on key facts, decisions, and dates. Do not include introductory or meta remarks. Output only the summary."
    summary_l1 = query_llm(sys_prompt, prompt_l1)
    
    if not summary_l1 or "unavailable offline" in summary_l1:
        return
        
    conn = get_db_connection(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO hierarchical_summaries (id, project_id, level, summary_text, source_ids) VALUES (?, ?, 1, ?, ?)",
              (doc_id, project_id, summary_l1, doc_id))
    conn.commit()
    
    # 2. Level 2 project status summary
    c.execute("SELECT id, summary_text FROM hierarchical_summaries WHERE project_id = ? AND level = 1", (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    
    if rows:
        items = [f"Document ID: {r['id']}\nSummary: {r['summary_text']}" for r in rows]
        doc_ids = [r['id'] for r in rows]
        joined = "\n\n".join(items)
        
        prompt_l2 = f"Below are individual document summaries for all files ingested under Project '{project_id}'. Write a unified, high-level project status summary. Synthesize timelines, critical issues, and actions across all documents.\n\nDOCUMENT SUMMARIES:\n{joined}"
        summary_l2 = query_llm(sys_prompt, prompt_l2)
        if summary_l2 and "unavailable offline" not in summary_l2:
            c.execute("INSERT OR REPLACE INTO hierarchical_summaries (id, project_id, level, summary_text, source_ids) VALUES (?, ?, 2, ?, ?)",
                      (f"PROJ-{project_id}", project_id, summary_l2, ",".join(doc_ids)))
            conn.commit()
            
    conn.close()

def build_existing_hierarchical_summaries():
    """Scan database for documents lacking hierarchical summaries and generate them."""
    try:
        conn = get_db_connection(); c = conn.cursor()
        c.execute("SELECT id, project_id, transcript_text, title FROM meetings WHERE id NOT IN (SELECT id FROM hierarchical_summaries WHERE level = 1)")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        
        for r in rows:
            generate_hierarchical_tree_task(r["id"], r["project_id"], r["transcript_text"], r["title"])
    except Exception as e:
        print(f"Error building existing summaries: {e}")

def process_new_document_background(doc_id: str, project_id: str, text: str, title: str):
    """Run all background tasks for a newly uploaded document."""
    from vector_store import build_missing_embeddings
    build_missing_embeddings()
    generate_hierarchical_tree_task(doc_id, project_id, text, title)

