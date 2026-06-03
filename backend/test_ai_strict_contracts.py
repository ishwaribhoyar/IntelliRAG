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
    accepted = r.json().get("accepted_files") or r.json().get("accepted") or []
    if not accepted:
        raise RuntimeError(f"No accepted_files from upload: {r.json()}")
    return accepted[0]["doc_id"]


def wait_ready(doc_id: str, timeout_s: int = 180) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = requests.get(f"{BASE}/status/{doc_id}", timeout=30).json()
        if st["status"] in ("ready", "failed"):
            return st
        time.sleep(1.0)
    return {"status": "timeout"}


def main():
    storage_uploads = Path("storage") / "uploads"
    pdfs = [p for p in storage_uploads.glob("*.pdf") if p.stat().st_size > 200]
    if not pdfs:
        raise SystemExit("No valid sample PDFs found")
    pdf = sorted(pdfs, key=lambda p: p.stat().st_size, reverse=True)[0]

    user_id = reg()
    print("user_id:", user_id, flush=True)
    doc_id = upload_one(user_id, pdf)
    print("doc_id:", doc_id, "file:", pdf.name, flush=True)

    st = wait_ready(doc_id)
    print("status:", st.get("status"), "stage:", st.get("processing_stage"), flush=True)
    if st.get("status") != "ready":
        print("error:", st.get("error"), "last_error:", st.get("last_error"), flush=True)
        raise SystemExit(1)

    quiz_q = requests.post(
        f"{BASE}/quiz/start",
        json={"doc_id": doc_id, "user_id": user_id, "quiz_type": "quiz"},
        timeout=120,
    )
    quiz_q.raise_for_status()
    qdata = quiz_q.json()
    questions = qdata.get("questions", [])
    print("quiz questions:", len(questions), "first keys:", questions[0].keys() if questions else None, flush=True)

    mock = requests.post(
        f"{BASE}/quiz/start",
        json={"doc_id": doc_id, "user_id": user_id, "quiz_type": "mock_test"},
        timeout=120,
    )
    mock.raise_for_status()
    md = mock.json()
    mqs = md.get("questions", [])
    print("mock questions:", len(mqs), "first keys:", mqs[0].keys() if mqs else None, flush=True)

    flash = requests.post(
        f"{BASE}/generate",
        json={"doc_id": doc_id, "user_id": user_id, "content_type": "flashcards"},
        timeout=180,
    )
    flash.raise_for_status()
    fd = flash.json()
    cards = fd.get("flashcards", [])
    print("flashcards:", len(cards), "first:", cards[0] if cards else None, flush=True)

    summ = requests.post(
        f"{BASE}/generate",
        json={"doc_id": doc_id, "user_id": user_id, "content_type": "summary"},
        timeout=180,
    )
    summ.raise_for_status()
    sd = summ.json()
    print("summary keys:", sd.keys(), flush=True)
    print("summary bullets:", len(sd.get("bullets", [])), "explanation_len:", len(sd.get("explanation", "")), flush=True)

    print("TEST DONE", flush=True)


if __name__ == "__main__":
    main()

