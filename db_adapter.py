import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")
IS_PG = bool(DATABASE_URL)

if IS_PG:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    class _PGCursor:
        def __init__(self, cur):
            self.cur = cur
        def execute(self, sql, params=None):
            self.cur.execute(sql.replace("?", "%s"), params or ())
            return self
        def executemany(self, sql, seq):
            for p in seq:
                self.execute(sql, p)
            return self
        def fetchone(self):
            r = self.cur.fetchone()
            return dict(r) if r else None
        def fetchall(self):
            return [dict(r) for r in self.cur.fetchall()]
        @property
        def rowcount(self): return self.cur.rowcount
        @property
        def description(self): return self.cur.description

    class _PGConn:
        def __init__(self):
            self.conn = psycopg2.connect(DATABASE_URL)
        def cursor(self):
            return _PGCursor(self.conn.cursor(cursor_factory=RealDictCursor))
        def execute(self, sql, params=None):
            return self.cursor().execute(sql, params)
        def executemany(self, sql, seq):
            return self.cursor().executemany(sql, seq)
        def commit(self): self.conn.commit()
        def close(self): self.conn.close()

    def get_db_connection():
        return _PGConn()
else:
    import sqlite3, shutil

    def get_db_connection():
        p = os.path.join(os.path.dirname(__file__), "app.db")
        if os.environ.get("VERCEL"):
            t = "/tmp/app.db"
            if not os.path.exists(t) and os.path.exists(p):
                shutil.copy(p, t)
            p = t
        conn = sqlite3.connect(p, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn
