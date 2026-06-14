import unittest
import os
import shutil
from fastapi.testclient import TestClient
from main import app
from database import DB_PATH, init_db

class TestHostedApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Remove old test database if exists
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()
        cls.client = TestClient(app)

    def test_1_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ScribeLink", response.text)

    def test_2_projects(self):
        response = self.client.get("/api/projects")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("lots", data)
        self.assertIn("projects", data)
        self.assertEqual(len(data["lots"]), 2)

    def test_3_search(self):
        response = self.client.post(
            "/api/search",
            data={
                "query": "Why did Lot 2 yield drop?",
                "department": "",
                "user": "Dr. A. K. Sharma",
                "user_dept": "Design & TCAD"
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("answer", data)
        self.assertIn("citations", data)
        self.assertIn("graph", data)
        self.assertTrue(len(data["citations"]) > 0)
        self.assertIn("yield", data["answer"].lower())

    def test_4_upload_and_audit(self):
        # Create a mock text file
        mock_file = "test_minutes.txt"
        with open(mock_file, "w") as f:
            f.write("DOCUMENT ID: SCL-555-TEST-001\nDATE: 2026-06-14\nDEPARTMENT: Design & TCAD\nLOT ID: LOT-2026-01\n\nTest content for validation.")
            
        try:
            with open(mock_file, "rb") as f:
                response = self.client.post(
                    "/api/upload",
                    data={
                        "lot_id": "LOT-2026-01",
                        "user": "Test User",
                        "user_dept": "Design & TCAD"
                    },
                    files={"file": (mock_file, f, "text/plain")}
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "success")
            
            # Verify audit logs
            response = self.client.get("/api/audit_logs")
            self.assertEqual(response.status_code, 200)
            logs = response.json()["logs"]
            self.assertTrue(any(l["action_type"] == "UPLOAD" for l in logs))
        finally:
            if os.path.exists(mock_file):
                os.remove(mock_file)

    def test_5_get_document(self):
        response = self.client.get("/api/document/SCL-555-DS-001")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "SCL-555-DS-001")
        self.assertIn("DESIGN RULE MANUAL", data["transcript_text"])

if __name__ == "__main__":
    unittest.main()
