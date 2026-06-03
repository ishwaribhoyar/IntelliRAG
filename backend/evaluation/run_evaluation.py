"""IntelliRAG — Comprehensive Multi-Dataset Evaluation (Phases 2-7).
BM25-only baseline, Vector-only baseline, Hybrid system.
Answer quality, multi-dataset, trust validation.
"""
import asyncio, csv, json, os, sys, time
from pathlib import Path
from datetime import datetime
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))
BASE = Path("evaluation")

# ── Dataset B: AI/ML document (doc_cdda7fe45c88, 21 chunks) ──
DATASET_B_DOC = "doc_cdda7fe45c88"
DATASET_B = [
  {"id":"B_F01","type":"factual","query":"What is Artificial Intelligence?","expected_answer":"Artificial Intelligence is the simulation of human intelligence by machines, enabling them to perform tasks that typically require human cognition.","key_terms":["simulation","human intelligence","machines"]},
  {"id":"B_F02","type":"factual","query":"What is Narrow AI?","expected_answer":"Narrow AI is artificial intelligence designed for a specific task, such as voice assistants or image recognition. It cannot perform tasks outside its defined scope.","key_terms":["specific task","voice assistants","narrow"]},
  {"id":"B_F03","type":"factual","query":"What is General AI?","expected_answer":"General AI refers to a machine that can understand, learn, and apply intelligence across a wide range of tasks, similar to human cognitive abilities.","key_terms":["general","wide range","human cognitive"]},
  {"id":"B_F04","type":"factual","query":"What is Super AI?","expected_answer":"Super AI is a hypothetical form of AI that surpasses human intelligence in all aspects including creativity, problem-solving, and social intelligence.","key_terms":["surpasses","human intelligence","hypothetical"]},
  {"id":"B_F05","type":"factual","query":"What is supervised learning?","expected_answer":"Supervised learning is a type of machine learning where the model is trained on labeled data, learning to map inputs to known outputs.","key_terms":["supervised","labeled data","inputs","outputs"]},
  {"id":"B_F06","type":"factual","query":"What is unsupervised learning?","expected_answer":"Unsupervised learning is a type of machine learning where the model finds patterns in unlabeled data without predefined outputs.","key_terms":["unsupervised","unlabeled","patterns"]},
  {"id":"B_F07","type":"factual","query":"What is reinforcement learning?","expected_answer":"Reinforcement learning is a type of machine learning where an agent learns by interacting with an environment and receiving rewards or penalties.","key_terms":["reinforcement","agent","rewards","environment"]},
  {"id":"B_F08","type":"factual","query":"What is overfitting?","expected_answer":"Overfitting occurs when a model learns the training data too well, including noise, and performs poorly on new unseen data.","key_terms":["overfitting","noise","training data","poorly"]},
  {"id":"B_F09","type":"factual","query":"What is the bias-variance tradeoff?","expected_answer":"The bias-variance tradeoff is the balance between a model's ability to fit training data (low bias) and generalize to new data (low variance).","key_terms":["bias","variance","tradeoff","generalize"]},
  {"id":"B_F10","type":"factual","query":"What is linear regression?","expected_answer":"Linear regression is a supervised learning algorithm that models the relationship between a dependent variable and one or more independent variables using a linear equation.","key_terms":["linear regression","supervised","linear equation"]},
  {"id":"B_C01","type":"conceptual","query":"Why is AI considered transformative technology?","expected_answer":"AI is transformative because it automates cognitive tasks, enables data-driven decisions, and creates new capabilities in healthcare, finance, transportation and other domains.","key_terms":["transformative","automates","cognitive","domains"]},
  {"id":"B_C02","type":"conceptual","query":"How does a decision tree make predictions?","expected_answer":"A decision tree makes predictions by splitting data based on feature values at each node, following branches until reaching a leaf node that gives the prediction.","key_terms":["decision tree","splitting","feature","leaf node"]},
  {"id":"B_C03","type":"conceptual","query":"Why does overfitting reduce model performance?","expected_answer":"Overfitting reduces performance because the model memorizes training data patterns including noise, so it cannot generalize to new data it hasn't seen before.","key_terms":["memorizes","noise","generalize","new data"]},
  {"id":"B_C04","type":"conceptual","query":"How do neural networks learn from data?","expected_answer":"Neural networks learn by adjusting weights through backpropagation and gradient descent, minimizing the error between predicted and actual outputs across layers of neurons.","key_terms":["neural networks","weights","backpropagation","layers"]},
  {"id":"B_C05","type":"conceptual","query":"What are the limitations of current AI systems?","expected_answer":"Current AI limitations include lack of common sense reasoning, data dependency, bias in training data, inability to explain decisions, and high computational requirements.","key_terms":["limitations","common sense","bias","computational"]},
  {"id":"B_M01","type":"multi-hop","query":"How does the bias-variance tradeoff relate to overfitting and underfitting?","expected_answer":"High variance leads to overfitting (model too complex, fits noise), while high bias leads to underfitting (model too simple, misses patterns). The tradeoff is finding the right model complexity.","key_terms":["bias","variance","overfitting","underfitting","complexity"]},
  {"id":"B_M02","type":"multi-hop","query":"How do supervised and unsupervised learning differ in their approach to training data?","expected_answer":"Supervised learning requires labeled data with known outputs for training, while unsupervised learning works with unlabeled data and discovers hidden patterns or structures autonomously.","key_terms":["labeled","unlabeled","supervised","unsupervised","patterns"]},
  {"id":"B_M03","type":"multi-hop","query":"How does regularization help prevent overfitting in neural networks?","expected_answer":"Regularization adds a penalty term to the loss function that discourages complex models. This prevents the network from memorizing training data and forces it to learn generalizable patterns.","key_terms":["regularization","penalty","complex","generalize"]},
  {"id":"B_A01","type":"adversarial","query":"What is the best Python web framework?","expected_answer":"NOT_IN_DOCUMENT","key_terms":[]},
  {"id":"B_A02","type":"adversarial","query":"How do you set up a Docker container?","expected_answer":"NOT_IN_DOCUMENT","key_terms":[]}
]

# Ground truth chunk IDs for Dataset B (doc_cdda7fe45c88, manually mapped)
GT_B = {
    "B_F01": ["c_4607acce81eb"],
    "B_F02": ["c_bfdf3888fb26"],
    "B_F03": ["c_443ed199d028"],
    "B_F04": ["c_b0d93a84cad4"],
    "B_F05": ["c_6363ec1cd5e7", "c_ec76e4bfaa4e"],
    "B_F06": ["c_3be36929dc30", "c_25d7f11d4b81"],
    "B_F07": ["c_850eb5f84c66"],
    "B_F08": ["c_4be191accf35"],
    "B_F09": ["c_27adbfae6f16"],
    "B_F10": ["c_56466a6f0e45"],
    "B_C01": ["c_3da2e4be9c12", "c_4607acce81eb"],
    "B_C02": ["c_4e3b6f90284d"],
    "B_C03": ["c_4be191accf35", "c_27adbfae6f16"],
    "B_C04": ["c_fad9e495bfc4"],
    "B_C05": ["c_b48373026fe5"],
    "B_M01": ["c_27adbfae6f16", "c_4be191accf35", "c_e437c0ea41d9"],
    "B_M02": ["c_6363ec1cd5e7", "c_3be36929dc30"],
    "B_M03": ["c_fad9e495bfc4", "c_4be191accf35"],
}

# Ground truth chunk IDs for Dataset A (doc_11c024ccf162, manually mapped)
GT_A = {
    "F01":["c_7ecfd4d5f417","c_289a9189d17b","c_bbbcc3794f4b"],
    "F02":["c_b380c1ac25e1","c_a9a432bcb4ed","c_a8f2b3df765f"],
    "F03":["c_330946c99287","c_3e073f2e8068"],
    "F04":["c_1885dd7ad9ed","c_f7f6a75df9ca","c_1786c6e7c6b5"],
    "F05":["c_f98efd97da26","c_247b99b9f807","c_65afd418a661"],
    "F06":["c_163bc99577a9","c_c04916c1c3b0","c_42b5d0777bac"],
    "F07":["c_62d796bd0cac","c_c8588286ab34"],
    "F08":["c_ec46c94c0ddd","c_be85e2e96ce0"],
    "F09":["c_c8fc3127f857","c_04b548a90061","c_10e30c065703"],
    "F10":["c_8a69e4135a24"],
    "F11":["c_ada4f094fa36","c_b493bbcf8aa7","c_ba93f31ca99b","c_dc4c132ada07"],
    "F12":["c_89f1194d0242","c_e8adb0cd837c","c_8b74381372c0"],
    "F13":["c_c0549b0e58d7","c_4cbba995df38"],
    "F14":["c_86ef97d2bbf3"],
    "F15":["c_f745092d9032","c_46b68418ea0b"],
    "F16":["c_45137df2249f","c_041eb6f37d44"],
    "F17":["c_10e30c065703","c_04b548a90061","c_0c5ad41bf610","c_c8fc3127f857"],
    "F18":["c_a8f2b3df765f","c_a9a432bcb4ed","c_b380c1ac25e1"],
    "F19":["c_8f957d0fa5b8","c_1786c6e7c6b5"],
    "F20":["c_81f45b6ad4f0"],
    "C01":["c_cc85062c89c2","c_5c284b0d92ec","c_be7c85cde112"],
    "C02":["c_330946c99287","c_a9a432bcb4ed"],
    "C03":["c_6d7f19fba0d4","c_752e7bf0b413","c_9aada2bb5c3b"],
    "C04":["c_c8fc3127f857","c_04b548a90061","c_a9f1b8d0eabd"],
    "C05":["c_65afd418a661","c_601d5c3a7412","c_247b99b9f807"],
    "C06":["c_ada4f094fa36","c_ba93f31ca99b","c_b493bbcf8aa7"],
    "C07":["c_f7f6a75df9ca","c_1786c6e7c6b5"],
    "C08":["c_c04916c1c3b0","c_42b5d0777bac"],
    "C09":["c_8edfe7c26f68","c_54b5171e2ea6"],
    "C10":["c_a9a432bcb4ed","c_a8f2b3df765f","c_330946c99287","c_b380c1ac25e1"],
    "C11":["c_cc85062c89c2","c_5c284b0d92ec"],
    "C12":["c_c0549b0e58d7","c_4cbba995df38"],
    "C13":["c_89f1194d0242","c_e8adb0cd837c","c_8b74381372c0"],
    "C14":["c_c8fc3127f857","c_a9f1b8d0eabd","c_0c5ad41bf610"],
    "C15":["c_65afd418a661","c_247b99b9f807","c_f98efd97da26"],
    "C16":["c_d154c587830d","c_70ee780b2762","c_2c071b5b9408"],
    "C17":["c_6d7f19fba0d4","c_330946c99287","c_b380c1ac25e1"],
    "C18":["c_55ff91cba487","c_b493bbcf8aa7","c_ba93f31ca99b","c_dc4c132ada07"],
    "C19":["c_c8588286ab34","c_62d796bd0cac"],
    "C20":["c_83e0c0bcd842","c_4d1cb3b03136"],
    "M01":["c_752e7bf0b413","c_9aada2bb5c3b","c_330946c99287"],
    "M02":["c_c8fc3127f857","c_04b548a90061","c_a8f2b3df765f"],
    "M03":["c_54b5171e2ea6","c_8edfe7c26f68","c_247b99b9f807"],
    "M04":["c_83e0c0bcd842","c_a8f2b3df765f","c_4d1cb3b03136"],
    "M05":["c_1786c6e7c6b5","c_f7f6a75df9ca","c_330946c99287"],
    "M06":["c_4cbba995df38","c_c0549b0e58d7","c_8edfe7c26f68","c_2c071b5b9408"],
    "M07":["c_752e7bf0b413","c_6d7f19fba0d4","c_9aada2bb5c3b"],
    "M08":["c_ada4f094fa36","c_e8adb0cd837c","c_cc85062c89c2"],
    "M09":["c_c8588286ab34","c_62d796bd0cac"],
    "M10":["c_45137df2249f","c_041eb6f37d44","c_a8f2b3df765f"],
}

async def run_system(doc_id, query, system_type):
    """Run a single query through a specific system configuration."""
    from app.retrieval.hybrid import hybrid_retrieve
    from app.indexing.vector_index import search_vector
    from app.rag.embedder import embed_single
    from app.state import bm25_indexes, chunk_store

    q_emb = embed_single(query)
    t0 = time.time()

    if system_type == "vector":
        chunks = await search_vector(doc_id, q_emb, top_k=5)
    elif system_type == "bm25":
        bm25 = bm25_indexes.get(doc_id)
        if bm25:
            raw = bm25.search(query, top_k=5)  # returns list[tuple(chunk_id, score)]
            # Convert to dicts by looking up chunk text
            all_chunks = {c["chunk_id"]: c for c in chunk_store.get(doc_id, [])}
            chunks = []
            for cid, score in raw:
                ch = all_chunks.get(cid, {})
                chunks.append({"chunk_id": cid, "score": score, "text": ch.get("text","")})
        else:
            chunks = []
    elif system_type == "hybrid":
        chunks = await hybrid_retrieve(doc_id, query, top_k=5)
    else:
        chunks = []

    latency = (time.time() - t0) * 1000
    ids = [c.get("chunk_id","") if isinstance(c, dict) else "" for c in chunks]
    texts = [c.get("text","")[:150] if isinstance(c, dict) else "" for c in chunks]
    scores = [c.get("rrf_score", c.get("score", 0)) if isinstance(c, dict) else 0 for c in chunks]
    return ids, texts, scores, latency


async def evaluate_dataset(doc_id, dataset, gt_map, label):
    """Full evaluation on one dataset across all 3 systems."""
    from app.state import chunk_store, bm25_indexes
    from app.indexing.builder import load_indexes
    from app.indexing.bm25_index import load_bm25_index
    from app.rag.embedder import embed_single, get_model
    from app.evaluation.metrics import recall_at_k, mrr
    from sentence_transformers import util as st_util

    await load_indexes(doc_id)
    bm25 = load_bm25_index(doc_id)
    if bm25: bm25_indexes[doc_id] = bm25
    model = get_model()

    systems = ["bm25", "vector", "hybrid"]
    results = {s: {"r3":[],"r5":[],"mrr":[],"lats":[],"sims":[],"covs":[]} for s in systems}
    details = []
    trust_data = []

    for item in dataset:
        qid, q, qtype = item["id"], item["query"], item["type"]
        expected = item["expected_answer"]
        gold = gt_map.get(qid, [])
        is_adv = qtype == "adversarial"
        keys = item.get("key_terms", [])

        for sys_type in systems:
            ids, texts, scores, lat = await run_system(doc_id, q, sys_type)
            results[sys_type]["lats"].append(lat)

            if not is_adv and gold:
                results[sys_type]["r3"].append(recall_at_k(ids, gold, 3))
                results[sys_type]["r5"].append(recall_at_k(ids, gold, 5))
                results[sys_type]["mrr"].append(mrr(ids, gold))

            # Semantic similarity (answer quality proxy)
            if not is_adv and texts and expected != "NOT_IN_DOCUMENT":
                best = texts[0]
                sim = float(st_util.cos_sim(
                    model.encode(best, convert_to_tensor=True),
                    model.encode(expected, convert_to_tensor=True)
                )[0][0])
                results[sys_type]["sims"].append(sim)

            # Key term coverage
            if keys and texts:
                all_t = " ".join(t.lower() for t in texts[:3])
                cov = sum(1 for k in keys if k.lower() in all_t) / len(keys)
                results[sys_type]["covs"].append(cov)

        # Trust validation (hybrid only)
        h_ids, h_texts, h_scores, h_lat = await run_system(doc_id, q, "hybrid")
        v_ids, _, v_scores, _ = await run_system(doc_id, q, "vector")
        top_vec = v_scores[0] if v_scores else 0
        top_rrf = h_scores[0] if h_scores else 0
        overlap = len(set(v_ids[:3]) & set(h_ids[:3])) / 3
        conf = 0.4*min(top_vec/0.5,1) + 0.3*min(top_rrf/0.1,1) + 0.3*overlap
        conf_level = "high" if conf>0.7 else ("medium" if conf>0.4 else "low")

        correct = False
        if is_adv:
            correct = top_vec < 0.25  # Should refuse
        elif gold:
            correct = recall_at_k(h_ids, gold, 5) > 0

        trust_data.append({"id":qid,"type":qtype,"confidence":round(conf,3),"level":conf_level,"correct":correct})

        # Detailed log (hybrid)
        sim_h = results["hybrid"]["sims"][-1] if results["hybrid"]["sims"] and not is_adv else 0
        cov_h = results["hybrid"]["covs"][-1] if results["hybrid"]["covs"] else 0
        details.append({
            "id":qid,"query":q,"type":qtype,
            "hybrid_ids":h_ids[:3],"vector_ids":v_ids[:3],
            "semantic_sim":round(sim_h,4),"coverage":round(cov_h,3),
            "confidence":round(conf,3),"level":conf_level,
            "correct":correct,"latency":round(h_lat,1)
        })

    avg = lambda l: round(sum(l)/max(len(l),1), 4) if l else 0
    pct = lambda n,d: round(n/max(d,1)*100, 1)

    # Compile per-system metrics
    compiled = {}
    for s in systems:
        r = results[s]
        sl = sorted(r["lats"])
        hall = sum(1 for sim,cov in zip(r["sims"],r["covs"]) if sim<0.3 and cov<0.3) if r["sims"] else 0
        compiled[s] = {
            "recall3": avg(r["r3"]), "recall5": avg(r["r5"]), "mrr": avg(r["mrr"]),
            "avg_sim": avg(r["sims"]), "avg_cov": avg(r["covs"]),
            "hallucination_pct": pct(hall, len(r["sims"])) if r["sims"] else 0,
            "avg_lat": round(np.mean(r["lats"]),1) if r["lats"] else 0,
            "p50_lat": round(sl[len(sl)//2],1) if sl else 0,
            "p95_lat": round(sl[int(len(sl)*0.95)],1) if sl else 0,
        }

    # Trust validation
    trust = {}
    for level in ["high","medium","low"]:
        items = [t for t in trust_data if t["level"]==level]
        trust[level] = {"count":len(items),"correct":sum(1 for t in items if t["correct"]),
                        "accuracy":pct(sum(1 for t in items if t["correct"]),len(items))}

    # Per-type breakdown
    per_type = {}
    for qtype in ["factual","conceptual","multi-hop"]:
        type_items = [d for d in details if d["type"]==qtype]
        per_type[qtype] = {
            "count": len(type_items),
            "avg_sim": avg([d["semantic_sim"] for d in type_items]),
            "avg_cov": avg([d["coverage"] for d in type_items]),
            "correct_pct": pct(sum(1 for d in type_items if d["correct"]), len(type_items)),
        }

    # Answer correctness
    in_scope = [d for d in details if d["type"] != "adversarial"]
    # Factual: key term presence in top chunk
    # Conceptual/multi-hop: semantic similarity > threshold
    correct_answers = 0
    for d in in_scope:
        if d["type"] == "factual":
            correct_answers += 1 if d["coverage"] >= 0.5 else 0
        else:
            correct_answers += 1 if d["semantic_sim"] >= 0.4 else 0
    answer_accuracy = pct(correct_answers, len(in_scope))

    adv = [d for d in details if d["type"] == "adversarial"]
    return {
        "dataset": label, "doc_id": doc_id, "queries": len(dataset),
        "systems": compiled, "trust": trust, "per_type": per_type,
        "adversarial": {"total":len(adv),"correct":sum(1 for d in adv if d["correct"])},
        "answer_accuracy": answer_accuracy,
        "details": details
    }


async def main():
    from app.rag.embedder import warmup
    warmup()

    ds_a = json.load(open(BASE/"data/dataset.json"))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*70}\n  COMPREHENSIVE EVALUATION (3 Systems x 2 Datasets)\n{'='*70}")

    # Dataset A
    print(f"\n  [A] Python Textbook (doc_11c024ccf162) — {len(ds_a)} queries")
    res_a = await evaluate_dataset("doc_11c024ccf162", ds_a, GT_A, "Python Textbook")

    # Dataset B
    print(f"\n  [B] AI/ML Notes ({DATASET_B_DOC}) — {len(DATASET_B)} queries")
    res_b = await evaluate_dataset(DATASET_B_DOC, DATASET_B, GT_B, "AI/ML Notes")

    # Print results
    for res in [res_a, res_b]:
        print(f"\n  [{res['dataset']}]")
        for s in ["bm25","vector","hybrid"]:
            m = res["systems"][s]
            print(f"  {s:8s} | R@3={m['recall3']} R@5={m['recall5']} MRR={m['mrr']} | Sim={m['avg_sim']} Cov={m['avg_cov']} Hall={m['hallucination_pct']}% | Lat={m['avg_lat']}ms p50={m['p50_lat']} p95={m['p95_lat']}")
        print(f"  Trust: {res['trust']}")
        print(f"  Per-type: {res['per_type']}")

    # Save
    combined = {"timestamp":ts, "datasets":[
        {k:v for k,v in res_a.items() if k!="details"},
        {k:v for k,v in res_b.items() if k!="details"},
    ]}
    # Cross-dataset average (hybrid only, Dataset A has GT)
    ha, hb = res_a["systems"]["hybrid"], res_b["systems"]["hybrid"]
    combined["cross_dataset"] = {
        "hybrid_avg_sim": round((ha["avg_sim"]+hb["avg_sim"])/2, 4),
        "hybrid_avg_lat": round((ha["avg_lat"]+hb["avg_lat"])/2, 1),
    }

    with open(BASE/"reports/metrics.json","w") as f: json.dump(combined, f, indent=2)
    with open(BASE/"logs/run.json","w") as f: json.dump({"a":res_a["details"],"b":res_b["details"]}, f, indent=2)

    # Comparison CSV
    with open(BASE/"reports/comparison.csv","w",newline="") as f:
        w = csv.writer(f)
        w.writerow(["Dataset","System","Recall@3","Recall@5","MRR","Semantic_Sim","Key_Coverage","Hallucination%","Avg_Latency_ms","p50","p95"])
        for res in [res_a, res_b]:
            for s in ["bm25","vector","hybrid"]:
                m = res["systems"][s]
                w.writerow([res["dataset"],s,m["recall3"],m["recall5"],m["mrr"],m["avg_sim"],m["avg_cov"],m["hallucination_pct"],m["avg_lat"],m["p50_lat"],m["p95_lat"]])

    # Failures
    failures = []
    for d in res_a["details"]:
        if d["type"]!="adversarial" and not d["correct"]:
            failures.append({**d, "cat":"retrieval_miss"})
        elif d["type"]=="adversarial" and not d["correct"]:
            failures.append({**d, "cat":"false_positive"})
        elif d["semantic_sim"]<0.3 and d["coverage"]<0.3 and d["type"]!="adversarial":
            failures.append({**d, "cat":"hallucination_risk"})

    with open(BASE/"reports/failures.md","w") as f:
        f.write(f"# Failure Analysis\n\n**{len(failures)} failures** / {len(res_a['details'])} queries (Dataset A)\n\n")
        cats = {}
        for fl in failures: cats[fl["cat"]] = cats.get(fl["cat"],0)+1
        f.write("| Category | Count |\n|:---|:---:|\n")
        for c,n in cats.items(): f.write(f"| {c} | {n} |\n")
        f.write(f"\n## Examples\n\n")
        for fl in failures[:15]:
            f.write(f"### {fl['id']}: {fl['query'][:60]}\n")
            f.write(f"- Type: {fl['type']} | Category: {fl['cat']}\n")
            f.write(f"- Semantic Sim: {fl['semantic_sim']} | Coverage: {fl['coverage']}\n")
            f.write(f"- Confidence: {fl['confidence']} ({fl['level']})\n\n")

    # Trust formula
    with open(BASE/"reports/trust_formula.md","w") as f:
        f.write("# Trust Layer Validation\n\n")
        f.write("## Formula\n```\nconfidence = 0.4 * norm_vec + 0.3 * norm_rrf + 0.3 * agreement\n```\n\n")
        f.write("## Calibration Results (Dataset A)\n\n| Level | Threshold | Count | Correct | Accuracy |\n|:---|:---:|:---:|:---:|:---:|\n")
        for lv in ["high","medium","low"]:
            t = res_a["trust"][lv]
            th = "> 0.7" if lv=="high" else ("0.4-0.7" if lv=="medium" else "< 0.4")
            f.write(f"| {lv} | {th} | {t['count']} | {t['correct']} | {t['accuracy']}% |\n")

    print(f"\n  All saved to evaluation/")
    print(f"\n{'='*70}\n  DONE\n{'='*70}")

asyncio.run(main())
