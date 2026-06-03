import json
import time
import uuid
from pathlib import Path

import requests


BASE = "http://127.0.0.1:8000/api"


def register_user() -> str:
    # Fresh user so uploads are not deduplicated for the same user_id.
    email = f"intellirag_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"
    name = "IntelliRAG Test"
    res = requests.post(
        f"{BASE}/register",
        json={"username": email, "password": password, "name": name, "email": email},
        timeout=60,
    )
    res.raise_for_status()
    return res.json()["user_id"]


def upload_multi(user_id: str, pdf_paths: list[Path]) -> tuple[list[dict], list[dict]]:
    multipart_files = []
    for p in pdf_paths:
        multipart_files.append(
            (
                "files",
                (
                    p.name,
                    p.read_bytes(),
                    "application/pdf",
                ),
            )
        )

    # Using bytes avoids filesystem handle issues on Windows.
    res = requests.post(
        f"{BASE}/upload/multi",
        files=multipart_files,
        data={"user_id": user_id},
        timeout=180,
    )
    res.raise_for_status()
    payload = res.json()
    return payload.get("accepted", []), payload.get("rejected", [])


def poll_doc_states(doc_ids: list[str], max_wait_s: int = 180) -> dict:
    record = {d: {"history": [], "partially_ready_seen": False} for d in doc_ids}
    start = time.time()

    while time.time() - start < max_wait_s:
        all_ready = True
        for d in doc_ids:
            r = requests.get(f"{BASE}/status/{d}", timeout=30)
            if r.status_code != 200:
                continue
            j = r.json()
            record[d]["history"].append(
                {
                    "t": round(time.time() - start, 1),
                    "status": j.get("status"),
                    "processing_stage": j.get("processing_stage"),
                    "progress": j.get("progress"),
                    "queue_position": j.get("queue_position"),
                    "estimated_wait": j.get("estimated_wait"),
                }
            )
            if j.get("status") != "ready":
                all_ready = False
            if j.get("status") == "partially_ready":
                record[d]["partially_ready_seen"] = True

        if all_ready:
            break
        # Faster sampling early so we don't miss partially_ready/queue_position windows.
        elapsed = time.time() - start
        if elapsed < 15:
            # Very fast sampling to capture short-lived `partially_ready`.
            time.sleep(0.05)
        elif elapsed < 30:
            time.sleep(0.25)
        else:
            time.sleep(1.5)

    return record


def pick_partial_doc(record: dict) -> str | None:
    for d, info in record.items():
        for evt in info.get("history", []):
            if evt.get("status") == "partially_ready":
                return d
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
    def log(msg: str):
        # Ensure immediate visibility even when stdout is buffered.
        print(msg, flush=True)
        Path("e2e_log.txt").write_text(
            Path("e2e_log.txt").read_text(encoding="utf-8") + msg + "\n" if Path("e2e_log.txt").exists() else msg + "\n",
            encoding="utf-8",
        )

    # Locate sample PDFs from storage/uploads
    storage_uploads = Path("storage") / "uploads"
    sample_names = [
        "doc_a95db187b9c3.pdf",
        "doc_1b6348745318.pdf",
        "doc_1be4cd80dd73.pdf",
    ]
    pdf_paths = [storage_uploads / n for n in sample_names]
    missing = [str(p) for p in pdf_paths if not p.exists()]
    if missing:
        raise SystemExit(f"Missing sample PDFs: {missing}")

    # Skip tiny/invalid samples to avoid immediate ingestion failures.
    pdf_paths = [p for p in pdf_paths if p.stat().st_size > 200]
    if len(pdf_paths) < 2:
        raise SystemExit(f"Not enough valid sample PDFs after filtering: {[p.name for p in pdf_paths]}")

    user_id = register_user()
    log(f"registered user_id: {user_id}")

    accepted, rejected = upload_multi(user_id, pdf_paths)
    log(f"upload/multi accepted: {len(accepted)} rejected: {len(rejected)}")
    doc_ids = [a.get("doc_id") for a in accepted if a.get("doc_id")]
    if not doc_ids:
        raise SystemExit("No doc_ids accepted; cannot test ingestion pipeline.")

    log(f"accepted doc_ids: {doc_ids}")
    record = poll_doc_states(doc_ids, max_wait_s=180)

    for d in doc_ids:
        hist = record[d]["history"]
        final = hist[-1] if hist else None
        print(
            "\nDOC",
            d,
            "\n  partially_ready_seen=",
            record[d]["partially_ready_seen"],
            "\n  final=",
            final,
            flush=True,
        )

    partial_doc = pick_partial_doc(record)
    log(f"partial_doc_candidate: {partial_doc}")

    search_result = None
    if partial_doc:
        # Best-effort: run search soon after we first saw partially_ready.
        time.sleep(0.5)
        query = "What is machine learning?"
        search_result = run_search_user(user_id, query)
        log(f"search/user results: {len(search_result.get('results', []))}")
    else:
        log("No partially_ready observed; skipping partial search test.")

    # Save detailed trace for later inspection
    out = {
        "user_id": user_id,
        "doc_ids": doc_ids,
        "rejected": rejected,
        "record": record,
        "search_result": search_result,
    }
    Path("test_output.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log("wrote test_output.json")


if __name__ == "__main__":
    main()

