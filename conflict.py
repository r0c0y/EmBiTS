import re
from database import get_db_connection

PATTERNS = {
    "M1 Min Width": [r"Metal\s*1\s*(?:Minimum\s+)?(?:Line\s+)?Width[:\s][^\n]*?([\d.]+)\s*um"],
    "M1 Min Spacing": [r"Metal\s*1\s*(?:Minimum\s+)?Spacing[:\s][^\n]*?([\d.]+)\s*um"],
    "M1 Thickness": [r"Metal\s*1\s*Thickness[:\s][^\n]*?([\d,]+)\s*Angstrom"],
    "Gate Oxide Thickness": [r"Gate\s*Oxide\s*Thickness[:\s][^\n]*?([\d]+)\s*Angstrom"],
    "Wafer Sort Yield": [
        r"Wafer\s*Sort\s*Yield[:\s][^%\n]*?([\d.]+)%",
        r"Wafer\s*Sort\s*Yield[:\s][^%\n]*?\n\s*[^%\n]*?([\d.]+)%",
        r"([\d.]+)%[^.\n]*?Wafer\s*Sort\s*Yield",
    ],
    "M2 Min Width": [r"Metal\s*2\s*(?:Minimum\s+)?(?:Line\s+)?Width[:\s][^\n]*?([\d.]+)\s*um"],
    "M2 Min Spacing": [r"Metal\s*2\s*(?:Minimum\s+)?Spacing[:\s][^\n]*?([\d.]+)\s*um"],
}

def detect_conflicts(citations):
    conn = get_db_connection(); cur = conn.cursor()
    cids = {c["meeting_id"] for c in citations}
    if "SCL-555-DS-001" not in cids:
        citations = list(citations) + [{"meeting_id": "SCL-555-DS-001", "meeting_title": "Design Specification"}]
    params = {}
    for c in citations:
        cur.execute("SELECT transcript_text FROM meetings WHERE id=?", (c["meeting_id"],))
        row = cur.fetchone()
        full = dict(row).get("transcript_text", "") if row else ""
        if not full:
            continue
        for para in full.split("\n\n"):
            for pname, patterns in PATTERNS.items():
                for pat in patterns:
                    for m in re.finditer(pat, para, re.IGNORECASE):
                        s = max(0, m.start()-30); e = min(len(para), m.end()+30)
                        params.setdefault(pname, []).append({
                            "value": m.group(1).replace(",", ""),
                            "doc_id": c["meeting_id"],
                            "title": c["meeting_title"],
                            "snippet": para[s:e].strip()
                        })
    conn.close()
    return [{"parameter": p, "values": v} for p, v in params.items() if len({x["value"] for x in v}) > 1]
