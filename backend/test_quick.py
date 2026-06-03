"""Quick API test with AI.pdf"""
import httpx, time, json

c = httpx.Client(timeout=60)
BASE = "http://127.0.0.1:8000/api"

print("=== HEALTH ===")
r = c.get(f"{BASE}/health")
print(r.status_code, r.json())

print("\n=== UPLOAD AI.pdf ===")
with open("../AI.pdf", "rb") as f:
    t = time.time()
    r = c.post(f"{BASE}/upload", files={"file": ("AI.pdf", f, "application/pdf")}, data={"user_id": "test_user"})
    lat = time.time() - t
d = r.json()
print(f"Status: {r.status_code}, Data: {d}, Latency: {lat:.1f}s")
doc_id = d.get("doc_id")

print("\n=== POLLING STATUS ===")
for i in range(30):
    r = c.get(f"{BASE}/status/{doc_id}")
    d = r.json()
    print(f"  [{i}] status={d['status']}, stage={d.get('processing_stage','?')}")
    if d["status"] == "ready":
        break
    if d["status"] == "failed":
        print("  ERROR:", d.get("error"))
        break
    time.sleep(2)

print(f"\nFinal status: {d['status']}")

if d["status"] == "ready":
    print("\n=== ASK AI ===")
    t = time.time()
    r = c.post(f"{BASE}/ask", json={"query": "What is artificial intelligence?", "user_id": "test_user"})
    lat = time.time() - t
    data = r.json()
    print(f"Status: {r.status_code}, Latency: {lat:.1f}s")
    ans = data.get("answer", "")
    print(f"Answer: {ans[:300]}")
    print(f"Sources: {len(data.get('sources') or data.get('source_chunks') or [])} chunks")
    print(f"Cached: {data.get('cached')}")

    print("\n=== QUIZ START ===")
    t = time.time()
    r = c.post(f"{BASE}/quiz/start", json={"doc_id": doc_id, "user_id": "test_user", "quiz_type": "quiz"})
    lat = time.time() - t
    data = r.json()
    qs = data.get("questions", [])
    print(f"Status: {r.status_code}, Latency: {lat:.1f}s, Questions: {len(qs)}")
    if qs:
        print(f"Q1: {qs[0].get('q', '')[:120]}")

    print("\n=== FLASHCARDS ===")
    t = time.time()
    r = c.post(f"{BASE}/generate", json={"doc_id": doc_id, "content_type": "flashcards", "user_id": "test_user"})
    lat = time.time() - t
    data = r.json()
    fcs = data.get("flashcards", [])
    print(f"Status: {r.status_code}, Latency: {lat:.1f}s, Cards: {len(fcs)}")

    print("\n=== SUMMARY ===")
    t = time.time()
    r = c.post(f"{BASE}/generate", json={"doc_id": doc_id, "content_type": "summary", "user_id": "test_user"})
    lat = time.time() - t
    data = r.json()
    print(f"Status: {r.status_code}, Latency: {lat:.1f}s")
    summary = data.get("summary", data.get("raw", ""))
    print(f"Summary: {str(summary)[:250]}")

    print("\n=== LEADERBOARD ===")
    r = c.get(f"{BASE}/leaderboard")
    print(f"Status: {r.status_code}, Entries: {len(r.json().get('leaderboard', []))}")

    print("\n=== SCORE ===")
    r = c.get(f"{BASE}/score?user_id=test_user")
    print(f"Status: {r.status_code}, Data: {r.json()}")

    print(f"\n=== doc_id for browser testing: {doc_id} ===")

c.close()
print("\n=== DONE ===")
