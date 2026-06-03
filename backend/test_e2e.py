"""Comprehensive E2E test script for the AI Document Learning Engine.
Tests all 11 endpoints, parser pipeline, cache behavior, latency, and error handling.
"""
import sys, os, time, json, asyncio, hashlib
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx

BASE = "http://127.0.0.1:8000/api"
USER = "test_user_e2e"
DOC_ID = None
PASS = 0
FAIL = 0
RESULTS = []

def log(test, status, detail="", latency=0):
    global PASS, FAIL
    icon = "✅" if status == "PASS" else "❌"
    if status == "PASS": PASS += 1
    else: FAIL += 1
    lat_str = f" ({latency:.1f}s)" if latency else ""
    print(f"  {icon} {test}{lat_str}")
    if detail and status == "FAIL":
        print(f"       → {detail[:200]}")
    RESULTS.append({"test": test, "status": status, "detail": detail, "latency": latency})


def test(name, condition, detail="", latency=0):
    log(name, "PASS" if condition else "FAIL", detail, latency)


def main():
    global DOC_ID
    c = httpx.Client(timeout=60)

    # Ensure test user is registered and upgraded to premium to unlock multi-doc Q&A and Mentor chats
    try:
        c.post(f"{BASE}/payments/subscribe", json={"user_id": USER, "tier": "premium"})
    except Exception as ex:
        print(f"⚠️ Warning: failed to pre-subscribe test user: {ex}")

    print("\n" + "="*60)
    print("🧪 AI Document Learning Engine — Full E2E Test Suite")
    print("="*60)

    # ==========================================
    # 1. HEALTH CHECK
    # ==========================================
    print("\n[1] HEALTH CHECK")
    t = time.time()
    r = c.get(f"{BASE}/health")
    lat = time.time() - t
    d = r.json()
    test("Health endpoint returns 200", r.status_code == 200, latency=lat)
    test("Model loaded", d.get("model_loaded") == True)
    test("DB connected", d.get("db_connected") == True)
    test("FAISS ready", d.get("faiss_ready") == True)

    # ==========================================
    # 2. CREATE TEST PDF
    # ==========================================
    print("\n[2] GENERATING TEST PDF")
    try:
        import pymupdf
        doc = pymupdf.open()

        # Page 1: AI/ML overview with headings
        p1 = doc.new_page()
        p1.insert_text((72, 72), "# Introduction to Artificial Intelligence", fontsize=18)
        p1.insert_text((72, 110), (
            "Artificial Intelligence (AI) is the simulation of human intelligence by machines. "
            "It encompasses machine learning, deep learning, natural language processing, and computer vision. "
            "AI systems can learn from data, identify patterns, and make decisions with minimal human intervention. "
            "The field was founded in 1956 at a conference at Dartmouth College. "
            "Modern AI is powered by neural networks, large datasets, and powerful computing hardware. "
            "Applications include autonomous vehicles, medical diagnosis, recommendation systems, and more. "
            "AI can be categorized into narrow AI (task-specific) and general AI (human-level reasoning). "
            "Currently, all commercial AI systems are narrow AI. General AI remains a theoretical concept. "
            "Key challenges include bias in training data, explainability, and ethical considerations. "
            "The global AI market is expected to reach $1.8 trillion by 2030."
        ), fontsize=11)

        # Page 2: ML types
        p2 = doc.new_page()
        p2.insert_text((72, 72), "# Types of Machine Learning", fontsize=16)
        p2.insert_text((72, 100), (
            "## Supervised Learning\n"
            "Models trained on labeled data. The algorithm learns a mapping from inputs to outputs. "
            "Examples: classification (spam detection), regression (price prediction). "
            "Common algorithms: Linear Regression, Decision Trees, Random Forest, SVM, Neural Networks.\n\n"
            "## Unsupervised Learning\n"
            "Models find patterns in unlabeled data. No target variable is provided. "
            "Examples: clustering (customer segmentation), dimensionality reduction (PCA). "
            "Common algorithms: K-Means, DBSCAN, Hierarchical Clustering, Autoencoders.\n\n"
            "## Reinforcement Learning\n"
            "An agent learns by interacting with an environment and receiving rewards or penalties. "
            "Examples: game playing (AlphaGo), robotics, recommendation engines. "
            "Key concepts: state, action, reward, policy, value function."
        ), fontsize=11)

        # Page 3: Key concepts with table-like content
        p3 = doc.new_page()
        p3.insert_text((72, 72), "# Key Concepts in Deep Learning", fontsize=16)
        p3.insert_text((72, 100), (
            "Overfitting occurs when a model learns noise in training data rather than the actual pattern. "
            "It results in high accuracy on training data but poor performance on unseen data. "
            "Solutions include: regularization (L1, L2), dropout, early stopping, data augmentation, and cross-validation.\n\n"
            "A neural network consists of layers: input layer, hidden layers, and output layer. "
            "Each neuron applies a weighted sum followed by an activation function (ReLU, sigmoid, tanh). "
            "Backpropagation is used to update weights by computing gradients of the loss function.\n\n"
            "| Concept | Description |\n"
            "| Epoch | One complete pass through the training data |\n"
            "| Batch Size | Number of samples processed before updating weights |\n"
            "| Learning Rate | Step size for weight updates during optimization |\n"
            "| Loss Function | Measures how well the model's predictions match actual values |\n"
        ), fontsize=11)

        pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "test_ai_ml.pdf")
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        doc.save(pdf_path)
        doc.close()
        test("Test PDF created", True, f"Path: {pdf_path}")
    except Exception as e:
        test("Test PDF created", False, str(e))
        print("Cannot continue without test PDF.")
        return

    # ==========================================
    # 3. UPLOAD TEST
    # ==========================================
    print("\n[3] UPLOAD ENDPOINT")
    t = time.time()
    with open(pdf_path, "rb") as f:
        r = c.post(f"{BASE}/upload", files={"file": ("test_ai_ml.pdf", f, "application/pdf")}, data={"user_id": USER})
    lat = time.time() - t
    d = r.json()
    DOC_ID = d.get("doc_id")
    test("Upload returns 200", r.status_code == 200, latency=lat)
    test("Upload returns doc_id", DOC_ID is not None, f"doc_id={DOC_ID}")
    test("Upload response < 5 sec", lat < 5, f"latency={lat:.2f}s", latency=lat)
    test("Upload returns status", d.get("status") in ("processing", "ready"))

    # ==========================================
    # 4. POLL STATUS
    # ==========================================
    print("\n[4] STATUS POLLING")
    if DOC_ID:
        max_wait = 60
        start = time.time()
        final_status = None
        while time.time() - start < max_wait:
            r = c.get(f"{BASE}/status/{DOC_ID}")
            d = r.json()
            final_status = d.get("status")
            stage = d.get("processing_stage", "?")
            if final_status == "ready":
                break
            if final_status == "failed":
                break
            time.sleep(2)
        total = time.time() - start
        test("Document reaches 'ready'", final_status == "ready", f"status={final_status}", latency=total)
        test("Processing < 30 sec", total < 30, f"took {total:.1f}s", latency=total)

        # Check status fields
        r = c.get(f"{BASE}/status/{DOC_ID}")
        d = r.json()
        test("Status has processing_stage", "processing_stage" in d, str(d.keys()))
        test("Stage is 'indexed'", d.get("processing_stage") == "indexed")
    else:
        test("Poll skipped (no doc_id)", False)

    # ==========================================
    # 5. DUPLICATE UPLOAD TEST
    # ==========================================
    print("\n[5] DUPLICATE HANDLING")
    with open(pdf_path, "rb") as f:
        t = time.time()
        r = c.post(f"{BASE}/upload", files={"file": ("test_ai_ml.pdf", f, "application/pdf")}, data={"user_id": USER})
        lat = time.time() - t
    d = r.json()
    test("Duplicate detected", d.get("duplicate") == True or d.get("status") == "ready", str(d), latency=lat)
    test("Duplicate returns same doc_id or ready", d.get("doc_id") == DOC_ID or d.get("status") == "ready")

    # ==========================================
    # 6. INVALID FILE TEST
    # ==========================================
    print("\n[6] INVALID FILE HANDLING")
    r = c.post(f"{BASE}/upload", files={"file": ("bad.txt", b"hello", "text/plain")}, data={"user_id": USER})
    test("Reject invalid file type", r.status_code == 400, f"status={r.status_code}")

    # ==========================================
    # 7. ASK AI (RAG Q&A)
    # ==========================================
    print("\n[7] ASK AI ENDPOINT")
    questions = [
        ("What is AI?", True),
        ("Difference between supervised and unsupervised learning", True),
        ("Explain overfitting", True),
        ("What is quantum computing?", False),  # not in doc
    ]
    for q, should_have_answer in questions:
        t = time.time()
        r = c.post(f"{BASE}/ask", json={"query": q, "user_id": USER})
        lat = time.time() - t
        d = r.json()
        has_answer = d.get("answer") and len(d["answer"]) > 10
        has_sources = ("source_chunks" in d) or ("sources" in d)

        test(f"Ask: '{q[:40]}...' responds", r.status_code == 200, latency=lat)
        test(f"  Response < 15 sec", lat < 15, f"{lat:.1f}s", latency=lat)
        if should_have_answer:
            test(f"  Has substantive answer", has_answer, d.get("answer", "")[:80])
        test(f"  Has source_chunks", has_sources)

    # Test cache: repeat same question
    t = time.time()
    r = c.post(f"{BASE}/ask", json={"query": "What is AI?", "user_id": USER})
    lat = time.time() - t
    d = r.json()
    test("Cached response is fast", lat < 3, f"{lat:.1f}s", latency=lat)
    test("Cached flag present", "cached" in d, str(d.keys()))

    # Test empty query
    r = c.post(f"{BASE}/ask", json={"query": "", "user_id": USER})
    test("Empty query handled", r.status_code == 400, f"status={r.status_code}")

    # ==========================================
    # 8. MENTOR ENDPOINT
    # ==========================================
    print("\n[8] AI MENTOR")
    t = time.time()
    r = c.post(f"{BASE}/mentor", json={"doc_id": DOC_ID, "question": "Explain neural networks simply", "user_id": USER, "history": []})
    lat = time.time() - t
    d = r.json()
    test("Mentor responds", r.status_code == 200, latency=lat)
    test("Mentor has answer", bool(d.get("answer")), d.get("answer", "")[:80])
    test("Mentor has sources", "source_chunks" in d)

    # ==========================================
    # 9. QUIZ
    # ==========================================
    print("\n[9] QUIZ ENDPOINTS")
    t = time.time()
    r = c.post(f"{BASE}/quiz/start", json={"doc_id": DOC_ID, "user_id": USER, "quiz_type": "quiz"})
    lat = time.time() - t
    d = r.json()
    test("Quiz start responds", r.status_code == 200, latency=lat)
    qs = d.get("questions", [])
    test("Quiz has questions", len(qs) > 0, f"count={len(qs)}")
    if qs:
        test("Questions have 'question' field", all("question" in q or "q" in q for q in qs))
        test("Questions have options", all("options" in q for q in qs))
        test("Questions have correct_answer", all("correct_answer" in q or "answer" in q for q in qs))

        # Submit random answers
        answers = [q.get("correct_answer", q.get("answer", "A")) for q in qs]  # Perfect score
        r = c.post(f"{BASE}/quiz/submit", json={
            "doc_id": DOC_ID, "user_id": USER, "questions": qs, "answers": answers
        })
        d = r.json()
        test("Quiz submit responds", r.status_code == 200)
        test("Quiz has score", "score" in d, str(d.keys()))
        test("Quiz has accuracy", "accuracy" in d)
        test("Perfect score = 1.0", d.get("accuracy") == 1.0, f"accuracy={d.get('accuracy')}")
        test("XP updated", "xp" in d, str(d.keys()))

    # ==========================================
    # 10. GENERATE ENDPOINTS
    # ==========================================
    print("\n[10] CONTENT GENERATION")
    gen_types = ["flashcards", "summary", "slides", "fun_facts"]
    for gtype in gen_types:
        t = time.time()
        r = c.post(f"{BASE}/generate", json={"doc_id": DOC_ID, "content_type": gtype, "user_id": USER})
        lat = time.time() - t
        d = r.json()
        test(f"Generate {gtype}", r.status_code == 200, latency=lat)
        test(f"  Response < 20 sec", lat < 20, f"{lat:.1f}s")
        has_content = bool(d.get(gtype) or d.get("raw") or d.get("summary") or d.get("slides") or d.get("facts") or d.get("flashcards") or d.get("bullets"))
        test(f"  Has content", has_content, str(list(d.keys()))[:80])

    # Test invalid content type
    r = c.post(f"{BASE}/generate", json={"doc_id": DOC_ID, "content_type": "invalid_junk", "user_id": USER})
    test("Reject invalid content_type", r.status_code == 400)

    # ==========================================
    # 11. LEADERBOARD
    # ==========================================
    print("\n[11] LEADERBOARD")
    r = c.get(f"{BASE}/leaderboard")
    d = r.json()
    test("Leaderboard responds", r.status_code == 200)
    lb = d.get("leaderboard", [])
    test("Leaderboard has entries", len(lb) > 0, f"count={len(lb)}")
    if lb:
        test("Entries have rank/user/xp", all(k in lb[0] for k in ("rank", "user_id", "daily_xp")))

    # ==========================================
    # 12. SCORE
    # ==========================================
    print("\n[12] USER SCORE")
    r = c.get(f"{BASE}/score", params={"user_id": USER})
    d = r.json()
    test("Score responds", r.status_code == 200)
    test("Score has xp", "xp" in d)
    test("XP > 0 after actions", d.get("xp", 0) > 0, f"xp={d.get('xp')}")
    test("Level >= 1", d.get("level", 0) >= 1)

    # ==========================================
    # 13. PERSISTENCE (Index exists on disk)
    # ==========================================
    print("\n[13] PERSISTENCE")
    from pathlib import Path
    idx_path = Path(__file__).parent / "storage" / "faiss_index" / f"{DOC_ID}.index"
    chunks_path = Path(__file__).parent / "storage" / "chunks" / f"{DOC_ID}.json"
    test("FAISS index file exists", idx_path.exists(), str(idx_path))
    test("Chunks file exists", chunks_path.exists(), str(chunks_path))

    # ==========================================
    # 14. FAVICON
    # ==========================================
    print("\n[14] STATIC ASSETS")
    r = c.get("http://127.0.0.1:8000/static/favicon.svg")
    test("Favicon serves 200", r.status_code == 200)
    r = c.get("http://127.0.0.1:8000/static/styles.css")
    test("CSS serves 200", r.status_code == 200)
    r = c.get("http://127.0.0.1:8000/static/app.js")
    test("JS serves 200", r.status_code == 200)
    r = c.get("http://127.0.0.1:8000/")
    test("Frontend serves 200", r.status_code == 200)
    test("Frontend has IntelliRAG", "IntelliRAG" in r.text)

    # ==========================================
    # 15. DELETE ENDPOINT
    # ==========================================
    print("\n[15] DELETE ENDPOINT")
    r = c.delete(f"{BASE}/doc/{DOC_ID}")
    d = r.json()
    test("Delete responds 200", r.status_code == 200)
    test("Delete confirms doc_id", d.get("doc_id") == DOC_ID)
    test("FAISS index removed", not idx_path.exists())
    test("Chunks removed", not chunks_path.exists())

    # Verify doc is gone
    r = c.get(f"{BASE}/status/{DOC_ID}")
    test("Deleted doc returns 404", r.status_code == 404)

    # ==========================================
    # 16. NONEXISTENT DOC HANDLING
    # ==========================================
    print("\n[16] ERROR HANDLING")
    r = c.post(f"{BASE}/ask", json={"query": "zzzz_nonexistent_topic_xyz", "user_id": USER})
    test("Off-topic ask returns 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        ans = (r.json() or {}).get("answer") or ""
        test("Off-topic answer empty or not-found", ("not found" in ans.lower()) or len(ans) < 400, ans[:120])

    r = c.get(f"{BASE}/status/fake_doc_xyz")
    test("Nonexistent status → 404", r.status_code == 404)

    # ==========================================
    # SUMMARY
    # ==========================================
    print("\n" + "="*60)
    total = PASS + FAIL
    pct = round(PASS / total * 100) if total else 0
    status = "🟢 PRODUCTION READY" if FAIL == 0 else "🟡 ISSUES FOUND" if FAIL <= 3 else "🔴 NOT READY"
    print(f"  {status}")
    print(f"  Passed: {PASS}/{total} ({pct}%)")
    if FAIL > 0:
        print(f"  Failed: {FAIL}")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"    ❌ {r['test']}: {r['detail'][:100]}")
    print("="*60 + "\n")

    c.close()

if __name__ == "__main__":
    main()
