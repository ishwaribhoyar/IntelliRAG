# 🚀 AI DOCUMENT RETRIEVAL SYSTEM

## COMPLETE SYSTEM FLOW + DATA FLOW + USER FLOW (DETAILED)

---

# 🧠 1. SYSTEM FLOW (END-TO-END INTERNAL PIPELINE)

---

## 🔷 PHASE A — INGESTION FLOW (UPLOAD → INDEX READY)

---

### Step 1: File Input

User uploads:

* PDF
* Excel
  OR
  Teacher selects from content library

---

### Step 2: Parser Routing

System decides:

```
If clean text → PyMuPDF  
If structured complex → Docling  
If scanned → OCR  
```

---

### Step 3: Raw Extraction

Output:

* raw text
* layout blocks
* tables

---

### Step 4: Cleaning Pipeline

Operations:

* remove headers/footers
* fix broken lines
* normalize spacing

---

### Step 5: Structure Builder

Convert to:

```
Section-based hierarchy:
H1 → H2 → H3
```

---

### Step 6: Structured JSON

```
{
  doc_id,
  sections: [
    { heading, level, content, page }
  ]
}
```

---

### Step 7: Hierarchical Chunking

#### Parent Layer:

* section summary

#### Child Layer:

* paragraph chunks

---

### Step 8: Adaptive Chunk Processing

Rules:

* <100 words → merge
* 200–350 → ideal
* > 500 → split

---

### Step 9: Table Processing

Convert:

```
Table → structured text
Entity → Attribute → Value
```

---

### Step 10: Metadata Injection

Each chunk gets:

```
doc_id
section
page
level
type
```

---

### Step 11: Embedding Generation

Each chunk:

```
text → vector (BGE model)
```

---

### Step 12: Indexing

Stored into:

* FAISS (vector index)
* BM25 (keyword index)
* Table index (separate)
* SQLite (metadata store)

---

### 🔥 OUTPUT OF INGESTION:

```
Document → Fully indexed → Retrieval-ready
```

---

# 🔷 PHASE B — QUERY FLOW (CORE RAG PIPELINE)

---

### Step 1: User Query Input

Types:

* keyword
* question
* conceptual

---

### Step 2: Query Classification

```
factual / conceptual / multi-hop
```

---

### Step 3: Query Routing

System decides:

* factual → BM25-heavy
* conceptual → vector-heavy
* multi-hop → multi-query

---

### Step 4: Query Expansion

Generate:

```
Original + 2–3 variations
```

---

### Step 5: Retrieval (Parallel)

#### Vector Search:

* FAISS → top k

#### Keyword Search:

* BM25 → top k

#### Table Search:

* if query type matches

---

### Step 6: Hybrid Fusion (RRF)

```
Combine rankings:
score = 1 / (k + rank)
```

---

### Step 7: Candidate Pool

```
Top 20–30 chunks
```

---

### Step 8: Conditional Reranking

```
If low confidence → apply reranker
Else → skip
```

---

### Step 9: MMR (Diversity Selection)

* remove duplicates
* ensure coverage

---

### Step 10: Context Filtering

* enforce token limit
* select best chunks

---

### Step 11: LLM Processing (Sarvam)

Input:

* filtered chunks
* strict prompt

---

### Step 12: Answer Generation

Output:

```
Answer
Source (page + section)
Confidence score
```

---

### Step 13: Trust Layer

If confidence low:

```
Return → "Not enough context"
```

---

### 🔥 OUTPUT:

```
Grounded Answer (no hallucination)
```

---

# 🔷 PHASE C — POST-QUERY ANALYSIS FLOW

---

### Step 1: Interaction Logging

Store:

* query
* retrieved chunks
* response
* latency

---

### Step 2: Quiz / Test Performance

Track:

* correct answers
* incorrect answers
* topic

---

### Step 3: Weakness Detection

```
accuracy < 50% → weak
```

---

### Step 4: Recommendation Engine

Suggest:

* topics to review
* practice questions

---

---

# 🧬 2. DATA FLOW (HOW DATA MOVES INTERNALLY)

---

# 🔹 A. INGESTION DATA FLOW

```
PDF → Raw Text → Clean Text → Structured JSON → Chunks → Embeddings → Indexes
```

---

### Transformation Levels:

| Stage      | Data Type  |
| ---------- | ---------- |
| Upload     | binary     |
| Parsed     | raw text   |
| Structured | JSON       |
| Chunked    | text units |
| Embedded   | vectors    |
| Indexed    | searchable |

---

# 🔹 B. RETRIEVAL DATA FLOW

```
Query → Query Variants → Embeddings → Search → Ranked Chunks → Filtered Context → LLM
```

---

# 🔹 C. STORAGE FLOW

---

### SQLite Stores:

* metadata
* user performance
* logs

---

### FAISS Stores:

* vector embeddings

---

### BM25 Stores:

* tokenized corpus

---

### Table Index:

* structured facts

---

---

# 🔹 D. OUTPUT DATA FLOW

```
Chunks → Context → LLM → Answer → Confidence → UI
```

---

---

# 👤 3. USER FLOW (REAL USER INTERACTION)

---

# 🔷 FLOW 1 — STUDENT

---

### Step 1: Entry

* login / register
* select subject OR upload document

---

### Step 2: System Ready

* document indexed
* dashboard shown

---

### Step 3: Interaction Options

User can:

* Ask AI
* Search topic
* Take quiz
* View summary

---

### Step 4: Ask AI Flow

```
User → query → answer → source → confidence
```

---

### Step 5: Quiz Flow

```
Start quiz → answer questions → submit → score
```

---

### Step 6: Weakness Analysis

```
System → identifies weak topics → suggests improvement
```

---

### Step 7: Continuous Loop

```
Learn → Test → Improve → Repeat
```

---

# 🔷 FLOW 2 — TEACHER

---

### Step 1: Select Subject

* from content library

---

### Step 2: Start System

* pre-indexed data loaded

---

### Step 3: Monitor

* student performance
* weak topics

---

---

# 🔷 FLOW 3 — SEARCH ENGINE MODE

---

### Input Types:

#### Keyword:

→ BM25 results

#### Question:

→ AI answer

---

### Output:

* snippets
* clickable sections
* AI explanation

---

---

# 🔥 FINAL SYSTEM BEHAVIOR

---

## System behaves like:

* search engine (fast lookup)
* AI tutor (explanation)
* evaluation system (feedback)
* learning platform (progress tracking)

---

# 🧠 FINAL UNDERSTANDING

---

## SYSTEM FLOW = how components interact

## DATA FLOW = how information transforms

## USER FLOW = how humans interact

---

# 🚀 FINAL STATEMENT

> This system is a full-stack AI pipeline combining
> **data processing + retrieval + reasoning + evaluation + personalization**

---

# 🏁 END RESULT

A system that:

* understands documents
* retrieves accurate knowledge
* explains concepts
* evaluates users
* adapts learning

---

This is **not a feature-based system**
This is a **pipeline-driven AI system**
