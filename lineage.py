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
