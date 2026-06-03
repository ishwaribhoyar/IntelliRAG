import time
import uuid
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000/api"


def reg() -> str:
    email = f"intellirag_test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(
        f"{BASE}/register",
        json={"username": email, "password": "TestPass123!", "name": "IntelliRAG Test", "email": email},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["user_id"]


def upload_one(user_id: str, pdf_path: Path) -> str:
    files = [("files[]", (pdf_path.name, pdf_path.read_bytes(), "application/pdf"))]
    r = requests.post(f"{BASE}/upload/multi", files=files, data={"user_id": user_id}, timeout=240)
    r.raise_for_status()
    accepted = r.json().get("accepted_files") or []
    if not accepted:
        raise RuntimeError(f"No accepted files: {r.json()}")
    return accepted[0]["doc_id"]


def wait_ready(doc_id: str, timeout_s: int = 180) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = requests.get(f"{BASE}/status/{doc_id}", timeout=30).json()
        if st["status"] in ("ready", "failed"):
            if st["status"] == "failed":
                raise RuntimeError(f"Doc failed: {st.get('error')} / {st.get('last_error')}")
            return
        time.sleep(0.5)
    raise TimeoutError("Timed out waiting for doc to become ready")


def main():
    storage_uploads = Path("storage") / "uploads"
    pdfs = [p for p in storage_uploads.glob("*.pdf") if p.stat().st_size > 200]
    if not pdfs:
        raise SystemExit("No sample PDFs found in storage/uploads")

    pdf = sorted(pdfs, key=lambda p: p.stat().st_size, reverse=True)[0]
    user_id = reg()
    doc_id = upload_one(user_id, pdf)
    wait_ready(doc_id)

    r = requests.post(
        f"{BASE}/quiz/start",
        json={"doc_id": doc_id, "user_id": user_id, "quiz_type": "mock_test"},
        timeout=180,
    )
    r.raise_for_status()
    d = r.json()
    q = d.get("questions", [])
    print("mock_test_questions_count:", len(q), "doc_id:", doc_id, "first_keys:", q[0].keys() if q else None, flush=True)


if __name__ == "__main__":
    main()

