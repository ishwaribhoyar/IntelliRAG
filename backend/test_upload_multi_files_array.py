import time
import uuid
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000/api"


def register_user() -> str:
    email = f"intellirag_test_{uuid.uuid4().hex[:10]}@example.com"
    payload = {
        "username": email,
        "password": "TestPass123!",
        "name": "IntelliRAG Multi files[] Test",
        "email": email,
    }
    res = requests.post(f"{BASE}/register", json=payload, timeout=60)
    res.raise_for_status()
    return res.json()["user_id"]


def main():
    storage_uploads = Path("storage") / "uploads"
    # Pick 2 valid sample PDFs (>200 bytes)
    pdf_paths = [p for p in storage_uploads.glob("*.pdf") if p.stat().st_size > 200]
    pdf_paths = sorted(pdf_paths, key=lambda p: p.stat().st_size)[:2]
    if len(pdf_paths) < 2:
        raise SystemExit(f"Need at least 2 valid sample PDFs; got {len(pdf_paths)}")

    user_id = register_user()
    files = []
    for p in pdf_paths:
        files.append(
            (
                "files[]",
                (p.name, p.read_bytes(), "application/pdf"),
            )
        )

    res = requests.post(
        f"{BASE}/upload/multi",
        files=files,
        data={"user_id": user_id},
        timeout=240,
    )
    if not res.ok:
        print("upload/multi failed:", res.status_code)
        try:
            print(res.json())
        except Exception:
            print(res.text)
        return
    payload = res.json()

    accepted = payload.get("accepted_files") or payload.get("accepted") or []
    doc_ids = [a.get("doc_id") for a in accepted if a.get("doc_id")]
    print("uploaded via files[] -> doc_ids:", doc_ids)

    # Wait until both are ready/failed
    start = time.time()
    while time.time() - start < 200:
        all_done = True
        for d in doc_ids:
            st = requests.get(f"{BASE}/status/{d}", timeout=20).json()
            if st.get("status") not in ("ready", "failed"):
                all_done = False
        if all_done:
            break
        time.sleep(1.5)

    for d in doc_ids:
        st = requests.get(f"{BASE}/status/{d}", timeout=20).json()
        print(d, "final status:", st.get("status"), "stage:", st.get("processing_stage"))

    print("DONE")


if __name__ == "__main__":
    main()

