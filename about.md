# 🚀 AI DOCUMENT RETRIEVAL & LEARNING SYSTEM

## (Advanced RAG + Evaluation + Personalization Engine)

---

# 🧠 1. SYSTEM IDENTITY

This system is a **retrieval-first AI architecture** designed to:

* extract knowledge from documents
* retrieve relevant information with high accuracy
* generate grounded responses
* evaluate performance
* adapt to user learning behavior

---

## ❌ What it is NOT

* chatbot
* simple PDF QA tool
* prompt-based system

---

## ✅ What it IS

> A **multi-layer AI system combining Information Retrieval (IR), LLM reasoning, and evaluation-driven optimization**

---

# 🧱 2. SYSTEM LAYERS (HIGH-LEVEL)

```
DATA LAYER
→ Documents + Content Library

PROCESSING LAYER
→ Parsing → Chunking → Indexing

RETRIEVAL LAYER
→ Hybrid Search + Reranking

REASONING LAYER
→ LLM (Sarvam)

CONTROL LAYER
→ Query Routing + Context Filtering

TRUST LAYER
→ Confidence + Citations

EVALUATION LAYER
→ Metrics + Ablation

APPLICATION LAYER
→ Quiz + Weakness + Search + Library
```

---

# ⚙️ 3. DATA INGESTION SYSTEM

---

## 3.1 Multi-Parser Design

Purpose:

* handle all document types reliably

### Components:

* PyMuPDF → fast extraction
* Docling → structured fallback
* OCR → scanned documents

---

## 3.2 Cleaning Pipeline

Before structuring:

* remove headers/footers
* fix line breaks
* normalize whitespace

---

## 3.3 Structured Output

```
{
  "doc_id": "",
  "sections": [
    {
      "heading": "",
      "level": "h1/h2/h3",
      "content": "",
      "page": 1
    }
  ]
}
```

---

## 🔥 Importance

If parsing is wrong:
→ chunking fails
→ retrieval fails
→ system collapses

---

# ⚙️ 4. HIERARCHICAL CHUNKING SYSTEM

---

## 4.1 Concept

Chunking transforms raw text into **retrievable units of meaning**.

---

## 4.2 Hierarchical Model

```
Parent Chunk → Section Summary
Child Chunks → Paragraphs
```

---

## 4.3 Adaptive Chunk Size

| Size    | Action |
| ------- | ------ |
| <100    | merge  |
| 200–350 | ideal  |
| >500    | split  |

---

## 4.4 Chunk Quality Rules

Each chunk must:

* be independently understandable
* contain full idea
* not break sentences
* answer at least one question

---

## 4.5 Table Processing (Critical)

Tables are converted into structured text:

```
Entity: Supervised Learning  
Attribute: Data Type  
Value: Labeled Data
```

---

## 4.6 Metadata

```
{
  "text": "...",
  "doc_id": "...",
  "section": "...",
  "page": 2,
  "level": "h2",
  "type": "text/table"
}
```

---

## 🎯 Output

* high-quality semantic units
* structured and retrievable knowledge

---

# ⚙️ 5. INDEXING SYSTEM

---

## 5.1 Embeddings

* Model: `bge-small-en`
* Converts text → vectors

---

## 5.2 FAISS (Vector Index)

* enables semantic search
* finds meaning-based matches

---

## 5.3 BM25 (Keyword Index)

* exact keyword matching
* strong for definitions

---

## 5.4 Table Index

* separate index for structured data

---

## 🔥 Why Multiple Indexes?

| System      | Strength        |
| ----------- | --------------- |
| FAISS       | meaning         |
| BM25        | keywords        |
| Table Index | structured data |

---

# ⚙️ 6. RETRIEVAL SYSTEM

---

## 6.1 Hybrid Retrieval

Combines:

* vector search
* BM25

---

## 6.2 RRF (Reciprocal Rank Fusion)

```
Score = 1 / (k + rank)
```

---

## 6.3 Dynamic Top-K

* short queries → small k
* vague queries → large k

---

## 🎯 Outcome

* higher recall
* better coverage

---

# ⚙️ 7. QUERY INTELLIGENCE LAYER

---

## 7.1 Query Classification

* factual
* conceptual
* multi-hop

---

## 7.2 Query Routing

| Type       | Strategy     |
| ---------- | ------------ |
| factual    | BM25-heavy   |
| conceptual | vector-heavy |
| multi-hop  | multi-query  |

---

## 7.3 Multi-Query Generation

Generates variations to improve recall.

---

# ⚙️ 8. RERANKING SYSTEM

---

## Purpose:

Refine retrieved results.

---

## Method:

* `bge-reranker-base`

---

## Conditional Execution:

* high confidence → skip
* low confidence → rerank

---

## 🎯 Outcome:

* improved precision

---

# ⚙️ 9. CONTEXT OPTIMIZATION

---

## 9.1 MMR (Maximal Marginal Relevance)

* removes duplicate chunks
* ensures diversity

---

## 9.2 Token Control

* limits context size
* prioritizes relevance

---

# ⚙️ 10. LLM GENERATION (SARVAM)

---

## Input:

* filtered chunks

---

## Output:

```
Answer
Source (page/section)
Confidence
```

---

## Constraint:

> Only answer from provided context

---

# ⚙️ 11. TRUST LAYER

---

## 11.1 Confidence Score

Based on:

* retrieval score
* reranker score
* agreement between chunks

---

## 11.2 Confidence Levels

| Score   | Meaning |
| ------- | ------- |
| >0.8    | High    |
| 0.5–0.8 | Medium  |
| <0.5    | Low     |

---

## 11.3 Fallback

```
Not enough context
```

---

## 🎯 Purpose:

* reduce hallucination
* increase reliability

---

# ⚙️ 12. EVALUATION SYSTEM (CORE DIFFERENTIATOR)

---

## Dataset:

* 50+ questions
* includes:

  * easy
  * ambiguous
  * multi-hop
  * table queries
  * missing answers

---

## Metrics:

* Recall@k
* MRR
* Accuracy
* Hallucination rate
* Not Found Accuracy
* Latency

---

## Ablation Study:

| System    | Recall | Accuracy |
| --------- | ------ | -------- |
| Baseline  | Low    | Medium   |
| Hybrid    | Higher | Better   |
| +Reranker | High   | High     |
| +Rewrite  | Best   | Best     |

---

## 🎯 Purpose:

Prove system improvement

---

# ⚙️ 13. PERSONALIZATION LAYER

---

## Weakness Detection

Tracks:

* quiz performance
* topic accuracy

---

## Output:

```
Weak Topics:
- Overfitting
- Neural Networks

Recommendation:
- Review notes
- Practice quiz
```

---

# ⚙️ 14. CONTENT LIBRARY SYSTEM

---

## Purpose:

Preloaded subjects (no repeated uploads)

---

## Structure:

```
Subjects → Documents → Indexed Data
```

---

## Benefit:

* faster access
* scalable

---

# ⚙️ 15. SEARCH ENGINE LAYER

---

## Modes:

### Keyword Search:

* BM25

### Hybrid Search:

* BM25 + FAISS

### AI Mode:

* full RAG pipeline

---

## Behavior:

* short query → search results
* long query → AI answer

---

# ⚙️ 16. LATENCY ENGINEERING

---

Track:

* embedding time
* retrieval time
* reranking time
* LLM time

---

Optimize:

* caching
* batching

---

# ⚙️ 17. SCALABILITY DESIGN (THEORETICAL)

---

* FAISS IVF indexing
* vector DB (Qdrant/Weaviate)
* async ingestion
* distributed systems

---

# 🚀 FINAL SYSTEM CAPABILITIES

---

## System can:

* understand documents
* retrieve relevant knowledge
* generate grounded answers
* evaluate itself
* adapt to user performance
* scale for real-world use

---

# 🧠 FINAL POSITIONING

This system represents:

> **AI Systems Engineering (not just AI usage)**

---

# 🏁 FINAL CONCLUSION

This project demonstrates:

* deep understanding of retrieval systems
* ability to optimize AI pipelines
* evaluation-driven engineering
* real-world AI system design

---

# 🔥 FINAL STATEMENT

> This is not a project.
> This is a **production-grade AI retrieval system blueprint**
