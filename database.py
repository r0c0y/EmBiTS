import os
from db_adapter import get_db_connection, IS_PG
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")
_initialized = False

def init_db():
    global _initialized
    if _initialized: return
    conn = get_db_connection(); c = conn.cursor()
    if not IS_PG:
        c.execute("PRAGMA foreign_keys = ON;")
    c.execute("CREATE TABLE IF NOT EXISTS meetings (id TEXT PRIMARY KEY, title TEXT, date TEXT, lot_id TEXT, department TEXT, file_path TEXT, transcript_text TEXT);")
    c.execute("CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, meeting_id TEXT, summary TEXT, status TEXT, type TEXT, FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE);")
    c.execute("CREATE TABLE IF NOT EXISTS lineage (from_node_id TEXT, to_node_id TEXT, relation_type TEXT, rationale TEXT, PRIMARY KEY (from_node_id, to_node_id));")
    c.execute("CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, username TEXT, department TEXT, action_type TEXT, details TEXT, parent_hash TEXT, current_hash TEXT);")
    if c.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]:
        _initialized = True
        conn.close()
        return
    base = os.path.dirname(__file__)
    def rf(p):
        with open(os.path.join(base, p), encoding="utf-8") as f:
            return f.read()
    ms = [
        ("SCL-555-DS-001","Design Specification","2026-01-20","LOT-2026-01","Design & TCAD","storage/spec.txt"),
        ("SCL-555-MM-001","Design Review Meeting","2026-02-10","LOT-2026-01","Design & TCAD","storage/review.txt"),
        ("SCL-555-MM-002","Shrink Approval Meeting","2026-05-15","LOT-2026-02","Design & TCAD","storage/shrink.txt"),
        ("SCL-555-FAB-001","Lot 1 Fab Run Report","2026-03-05","LOT-2026-01","Fabrication Operations","storage/fab1.txt"),
        ("SCL-555-ET-001","Wafer Sort Electrical Test","2026-03-01","LOT-2026-01","Design & TCAD","storage/wafer_test.txt"),
        ("SCL-555-PKG-001","Lot 1 Packaging Report","2026-03-12","LOT-2026-01","Packaging & Assembly","storage/pkg1.txt"),
        ("SCL-555-RL-001","HTOL Reliability Report","2026-04-01","LOT-2026-01","Quality Assurance","storage/reliability.txt"),
        ("SCL-555-QA-001","Lot 1 Quality Clearance","2026-03-20","LOT-2026-01","Quality Assurance","storage/qa1.txt"),
        ("SCL-555-MM-003","Yield Excursion Review","2026-06-01","LOT-2026-02","Quality Assurance","storage/excursion.txt"),
        ("SCL-555-FAB-002","Lot 2 Fab Run Report","2026-05-20","LOT-2026-02","Fabrication Operations","storage/lot2_fab.txt"),
        ("SCL-555-PKG-002","Lot 2 Packaging Report","2026-06-05","LOT-2026-02","Packaging & Assembly","storage/lot2_pkg.txt"),
        ("SCL-555-QA-002","Lot 2 Quality Disposition","2026-06-08","LOT-2026-02","Quality Assurance","storage/lot2_qa.txt"),
        ("SCL-555-RD-001","Post-Excursion Redesign","2026-06-10","LOT-2026-02","Design & TCAD","storage/redesign.txt"),
        ("SCL-555-RU-001","Dry Etch Recipe Update","2026-06-12","LOT-2026-02","Fabrication Operations","storage/recipe_update.txt"),
        ("SCL-555-MR-001","Mask Layout Revision","2026-06-15","LOT-2026-02","Design & TCAD","storage/mask_revision.txt")
    ]
    c.executemany("INSERT INTO meetings VALUES (?,?,?,?,?,?,?);", [(m[0],m[1],m[2],m[3],m[4],m[5],rf(m[5])) for m in ms])
    dc = [
        ("DEC-1","SCL-555-DS-001","Metal Spacing Specified: 0.25 um","Approved","Spec_Change"),
        ("DEC-2","SCL-555-MM-001","Handoff baseline specs for Lot 1 release.","Approved","Decision"),
        ("DEC-3","SCL-555-MM-002","Layout shrink to 0.18 um M1 spacing approved.","Approved","Decision"),
        ("DEC-4","SCL-555-MM-003","Yield dropped to 45.8% due to M1 bridging shorts.","Failed","Excursion"),
        ("DEC-5","SCL-555-PKG-001","Gold wire bonding: shear force 12.5g.","Approved","Spec_Change"),
        ("DEC-6","SCL-555-QA-001","Lot 1 passed HTOL reliability tests.","Approved","Decision"),
        ("DEC-7","SCL-555-ET-001","Wafer sort yield 92.3%: within spec.","Approved","Decision"),
        ("DEC-8","SCL-555-RL-001","HTOL zero failures: FIT<10, MTBF>100k hrs.","Approved","Decision"),
        ("DEC-9","SCL-555-FAB-002","Lot 2 fab used legacy CL_ETCH_M1_0.25 recipe.","Warning","Excursion"),
        ("DEC-10","SCL-555-RU-001","CL_ETCH_M1_0.18 qualified for 0.18um nodes.","Approved","Decision"),
        ("DEC-11","SCL-555-RD-001","M1 width 0.22um, spacing 0.25um for Lot 3.","Approved","Spec_Change"),
        ("DEC-12","SCL-555-PKG-002","Die attach voiding 6%: lot quarantined.","Warning","Excursion"),
        ("DEC-13","SCL-555-QA-002","Lot 2 REJECTED per SCL-QA-REJ-2026-001.","Failed","Decision"),
        ("DEC-14","SCL-555-MR-001","Mask revision: M1 0.22um, spacing 0.25um.","Approved","Spec_Change")
    ]
    c.executemany("INSERT INTO decisions VALUES (?,?,?,?,?);", dc)
    ed = [
        ("SCL-555-DS-001","SCL-555-MM-001","followed_by","Spec handoff to design review"),
        ("SCL-555-MM-001","SCL-555-FAB-001","followed_by","Design release -> Lot 1 fab"),
        ("SCL-555-MM-001","SCL-555-MM-002","followed_by","Shrink discussion for Lot 2"),
        ("SCL-555-MM-002","SCL-555-FAB-002","followed_by","Shrink approved -> Lot 2 fab"),
        ("SCL-555-FAB-001","SCL-555-ET-001","followed_by","Fab -> wafer sort electrical test"),
        ("SCL-555-ET-001","SCL-555-PKG-001","followed_by","Test clearance -> packaging"),
        ("SCL-555-PKG-001","SCL-555-RL-001","followed_by","Reliability sampling of packaged units"),
        ("SCL-555-RL-001","SCL-555-QA-001","followed_by","Reliability data -> QA clearance"),
        ("SCL-555-FAB-002","SCL-555-MM-003","triggered_by","Fab excursion -> yield review"),
        ("SCL-555-MM-002","SCL-555-MM-003","triggered_by","Shrink without recipe -> excursion"),
        ("SCL-555-MM-003","SCL-555-RD-001","triggered_by","Excursion -> redesign review"),
        ("SCL-555-MM-003","SCL-555-RU-001","triggered_by","Excursion -> dry-etch recipe fix"),
        ("SCL-555-MM-003","SCL-555-PKG-002","followed_by","Partial packaging during investigation"),
        ("SCL-555-MM-003","SCL-555-QA-002","triggered_by","Excursion -> QA disposition"),
        ("SCL-555-RD-001","SCL-555-MR-001","followed_by","Design changes -> mask tape-out"),
        ("SCL-555-RU-001","SCL-555-MR-001","followed_by","New etch capability -> mask design"),
        ("SCL-555-QA-002","SCL-555-RD-001","triggered_by","QA rejection -> redesign"),
        ("SCL-555-MM-003","SCL-555-MR-001","triggered_by","Excursion -> mask revision for Lot 3")
    ]
    c.executemany("INSERT INTO lineage VALUES (?,?,?,?);", ed)
    conn.commit(); conn.close()
    _initialized = True

if __name__ == "__main__": init_db()
