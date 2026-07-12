from database import get_db_connection
from audit_ledger import log_audit

def create_edge(from_id, to_id, rel_type, rationale, user, dept):
    conn = get_db_connection(); c = conn.cursor()
    try:
        c.execute("INSERT INTO lineage VALUES (?,?,?,?);", (from_id, to_id, rel_type, rationale))
        conn.commit()
        log_audit(user, dept, "LINEAGE_CREATE", f"Edge {from_id} -> {to_id} ({rel_type})")
        return {"status": "created"}
    except Exception as e:
        raise Exception(f"Failed to create edge: {e}")
    finally:
        conn.close()

def delete_edge(from_id, to_id, user, dept):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("DELETE FROM lineage WHERE from_node_id=? AND to_node_id=?;", (from_id, to_id))
    if c.rowcount == 0:
        conn.close()
        raise Exception("Edge not found")
    conn.commit()
    conn.close()
    log_audit(user, dept, "LINEAGE_DELETE", f"Deleted edge {from_id} -> {to_id}")
    return {"status": "deleted"}

def get_all_nodes():
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, title, date, lot_id, department, file_path FROM meetings;")
    nodes = [dict(r) for r in c.fetchall()]
    conn.close()
    return nodes

def get_all_edges():
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT from_node_id, to_node_id, relation_type, rationale FROM lineage;")
    edges = [dict(r) for r in c.fetchall()]
    conn.close()
    return edges

def auto_edges():
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, title, date, lot_id, project_id, file_path, transcript_text FROM meetings ORDER BY date, id")
    docs = [dict(r) for r in c.fetchall()]
    edges = []
    
    # 1. Metadata and sequence linking
    by_project = {}
    for d in docs:
        by_project.setdefault(d["project_id"], []).append(d)
    for proj, proj_docs in by_project.items():
        for i, d in enumerate(proj_docs):
            for j in range(i+1, len(proj_docs)):
                nd = proj_docs[j]
                if d["lot_id"] and nd["lot_id"] and d["lot_id"] == nd["lot_id"]:
                    edges.append((d["id"], nd["id"], "followed_by", "Same lot sequence"))
                elif d["date"] and nd["date"]:
                    try:
                        d_int = int(d["date"].replace("-",""))
                        nd_int = int(nd["date"].replace("-",""))
                        if 0 < nd_int - d_int < 30000:
                            edges.append((d["id"], nd["id"], "followed_by", "Date proximity in project"))
                    except: pass

    # 2. Logseq-inspired textual reference scanner
    import re
    for d in docs:
        text = d.get("transcript_text") or ""
        if not text.strip():
            continue
        for other in docs:
            if d["id"] == other["id"]:
                continue
                
            id_pat = re.escape(other["id"])
            other_names = []
            if other.get("file_path"):
                other_names.append(other["file_path"])
                base = other["file_path"].rsplit(".", 1)[0]
                if len(base) > 5:
                    other_names.append(base)
            if other.get("title") and len(other["title"]) > 5:
                other_names.append(other["title"])
                
            matched = False
            rationale = ""
            if re.search(r"\b" + id_pat + r"\b", text):
                matched = True
                rationale = f"Mentions document ID '{other['id']}' directly in text"
            else:
                for name in other_names:
                    escaped_name = re.escape(name)
                    if re.search(r"\b" + escaped_name + r"\b", text, re.IGNORECASE):
                        matched = True
                        rationale = f"Refers to document name '{name}' in text"
                        break
            
            if matched:
                edges.append((d["id"], other["id"], "references", rationale))

    for e in edges:
        try:
            c.execute("INSERT OR IGNORE INTO lineage VALUES (?,?,?,?)", e)
        except: pass
    conn.commit(); conn.close()
