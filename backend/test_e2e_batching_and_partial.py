import json
import time
import uuid
from pathlib import Path

import requests


BASE = "http://127.0.0.1:8000/api"


def register_user() -> tuple[str, str]:
    email = f"intellirag_test_{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPass123!"
    name = "IntelliRAG Batch Test"
    res = requests.post(
        f"{BASE}/register",
        json={"username": email, "password": password, "name": name, "email": email},
        timeout=60,
    )
    res.raise_for_status()
    j = res.json()
    return j["user_id"], email


def upload_multi(user_id: str, pdf_paths: list[Path]) -> tuple[list[dict], list[dict], dict]:
    multipart_files = []
    for p in pdf_paths:
        multipart_files.append(("files", (p.name, p.read_bytes(), "application/pdf")))

    res = requests.post(
        f"{BASE}/upload/multi",
        files=multipart_files,
        data={"user_id": user_id},
        timeout=240,
    )
    res.raise_for_status()
    payload = res.json()
    return payload.get("accepted", []), payload.get("rejected", []), payload.get("queue", {})


def wait_for_user_docs_ready(user_id: str, doc_ids: list[str], max_wait_s: int = 150) -> dict:
    start = time.time()
    last_status = {d: None for d in doc_ids}
    while time.time() - start < max_wait_s:
        all_done = True
        for d in doc_ids:
            r = requests.get(f"{BASE}/status/{d}", timeout=20)
            if r.status_code != 200:
                continue
            j = r.json()
            last_status[d] = j
            if j.get("status") not in ("ready", "failed"):
                all_done = False
        if all_done:
            break
        time.sleep(1.0)
    return last_status


def poll_until_any_partially_ready(user_id: str, doc_ids: list[str], poll_s: float = 0.15, max_wait_s: int = 20) -> str | None:
    start = time.time()
    while time.time() - start < max_wait_s:
        for d in doc_ids:
            r = requests.get(f"{BASE}/status/{d}", timeout=15)
            if r.status_code != 200:
                continue
            j = r.json()
            if j.get("status") == "partially_ready":
                return d
        time.sleep(poll_s)
    return None


def run_search_user(user_id: str, query: str) -> dict:
    res = requests.post(
        f"{BASE}/search/user",
        json={"user_id": user_id, "query": query, "mode": "hybrid", "limit": 10},
        timeout=120,
    )
    res.raise_for_status()
    return res.json()


def main():
    storage_uploads = Path("storage") / "uploads"
    candidates = list(storage_uploads.glob("*.pdf"))
    pdf_paths = [p for p in candidates if p.stat().st_size > 200]
    pdf_paths = sorted(pdf_paths, key=lambda p: p.stat().st_size, reverse=True)[:2]
    if len(pdf_paths) < 2:
        raise SystemExit(f"Need at least 2 valid sample PDFs; got: {[p.name for p in pdf_paths]}")

    # Multiple fresh users so embedding requests from different documents overlap.
    num_users = 4
    users: list[dict] = []
    all_doc_ids: list[tuple[str, list[str]]] = []

    for _ in range(num_users):
        user_id, email = register_user()
        accepted, rejected, queue = upload_multi(user_id, pdf_paths)
        doc_ids = [a["doc_id"] for a in accepted if a.get("doc_id")]
        users.append(
            {
                "user_id": user_id,
                "email": email,
                "accepted": accepted,
                "rejected": rejected,
                "queue": queue,
                "doc_ids": doc_ids,
            }
        )
        all_doc_ids.append((user_id, doc_ids))

    # Pick first user for partial-search verification.
    first_user = users[0]
    user_id = first_user["user_id"]
    doc_ids = first_user["doc_ids"]

    partial_doc = poll_until_any_partially_ready(user_id, doc_ids, poll_s=0.12, max_wait_s=25)
    partial_search = None
    ready_search = None

    query = "What is machine learning?"
    if partial_doc:
        partial_search = run_search_user(user_id, query)

        # Wait for partial doc to become ready (or failed) then search again.
        t0 = time.time()
        while time.time() - t0 < 60:
            st = requests.get(f"{BASE}/status/{partial_doc}", timeout=20).json()
            if st.get("status") == "ready":
                break
            if st.get("status") == "failed":
                break
            time.sleep(0.8)
        ready_search = run_search_user(user_id, query)

    # Now finish ingestion for all users.
    final_states = []
    for uid, dids in all_doc_ids:
        final_states.append({"user_id": uid, "states": wait_for_user_docs_ready(uid, dids)})

    out = {"sample_pdfs": [p.name for p in pdf_paths], "users": users, "partial_doc": partial_doc, "partial_search": partial_search, "ready_search": ready_search, "final_states": final_states}
    Path("test_output_batching.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote test_output_batching.json", flush=True)


if __name__ == "__main__":
    main()

