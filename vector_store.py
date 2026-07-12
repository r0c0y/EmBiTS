import struct
import math
from db_adapter import get_db_connection

def pack_vector(vec: list) -> bytes:
    if not vec: return b""
    return struct.pack(f"{len(vec)}f", *vec)

def unpack_vector(blob: bytes) -> list:
    if not blob: return []
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))

def init_vector_table():
    conn = get_db_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS chunk_embeddings (chunk_id TEXT PRIMARY KEY, embedding BLOB)")
    conn.commit(); conn.close()

def save_embedding(chunk_id: str, embedding: list):
    if not embedding: return
    blob = pack_vector(embedding)
    conn = get_db_connection(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)", (chunk_id, blob))
    conn.commit(); conn.close()

def get_embedding_by_id(chunk_id: str) -> list:
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT embedding FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,))
    row = c.fetchone()
    conn.close()
    if row:
        blob = row[0] if isinstance(row, tuple) else row["embedding"]
        return unpack_vector(blob)
    return []

def cosine_similarity(v1: list, v2: list) -> float:
    if not v1 or not v2 or len(v1) != len(v2): return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    return dot / (n1 * n2) if n1 > 0 and n2 > 0 else 0.0

def vector_search(query_vec: list, project_id: str = None, doc_id: str = None, top_k: int = 10) -> list:
    """Perform vector similarity search over SQLite database."""
    if not query_vec: return []
    conn = get_db_connection(); c = conn.cursor()
    
    # 1. Retrieve all candidate chunks with their text and metadata
    sql = "SELECT c.id, c.meeting_id, c.chunk_index, c.chunk_text, c.page_number, m.title, m.date, m.lot_id, m.project_id FROM chunks c JOIN meetings m ON c.meeting_id = m.id"
    params = []
    where = []
    if project_id:
        proj_list = [p.strip() for p in project_id.split(",") if p.strip()]
        if proj_list:
            where.append(f"m.project_id IN ({','.join('?' for _ in proj_list)})")
            params.extend(proj_list)
    if doc_id:
        doc_list = [d.strip() for d in doc_id.split(",") if d.strip()]
        if doc_list:
            where.append(f"m.id IN ({','.join('?' for _ in doc_list)})")
            params.extend(doc_list)
    if where:
        sql += " WHERE " + " AND ".join(where)
        
    c.execute(sql, params)
    candidates = [dict(r) for r in c.fetchall()]
    
    if not candidates:
        conn.close()
        return []
        
    # 2. Get embeddings for these candidate chunks
    cids = [cand["id"] for cand in candidates]
    placeholders = ",".join("?" for _ in cids)
    c.execute(f"SELECT chunk_id, embedding FROM chunk_embeddings WHERE chunk_id IN ({placeholders})", cids)
    embs = {r[0] if isinstance(r, tuple) else r["chunk_id"]: unpack_vector(r[1] if isinstance(r, tuple) else r["embedding"]) for r in c.fetchall()}
    conn.close()
    
    # 3. Calculate similarity score
    scored_candidates = []
    for cand in candidates:
        emb = embs.get(cand["id"])
        if emb:
            score = cosine_similarity(query_vec, emb)
            scored_candidates.append((score, cand))
            
    scored_candidates.sort(key=lambda x: -x[0])
    results = []
    for score, cand in scored_candidates[:top_k]:
        cand_copy = cand.copy()
        cand_copy["score"] = score
        results.append(cand_copy)
        
    return results

def build_missing_embeddings():
    """Find any text chunks that are missing embeddings and generate them."""
    from embedder import get_embedding
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, chunk_text FROM chunks WHERE id NOT IN (SELECT chunk_id FROM chunk_embeddings)")
    missing = [dict(r) for r in c.fetchall()]
    conn.close()
    
    if not missing:
        return
        
    print(f"Generating local vector embeddings for {len(missing)} text chunks...")
    for idx, item in enumerate(missing, 1):
        vec = get_embedding(item["chunk_text"])
        if vec:
            save_embedding(item["id"], vec)
            if idx % 10 == 0 or idx == len(missing):
                print(f"Vectorized {idx}/{len(missing)} chunks.")
        else:
            print("Warning: Local embedding model is not responding. Skipping chunk vectorization.")
            break

