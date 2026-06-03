# IntelliRAG — Features

## Core Features

### 1. Document Ingestion
- Multi-format upload: PDF, Excel (.xlsx)
- Adaptive parser routing (PyMuPDF / Docling / OCR)
- Header/footer removal, line-break fixing, whitespace normalization
- Heading hierarchy detection (H1/H2/H3) with page tracking
- Duplicate file detection via MD5 hash

### 2. Hierarchical Chunking
- **Parent chunks**: Section-level summaries for broad retrieval
- **Child chunks**: Paragraph-level segments (200–350 words, adaptive)
- **Table chunks**: Markdown tables converted to Entity→Attribute→Value format
- Adaptive sizing: merge small (<100 words), split large (>500 words)
- Rich metadata: section, page, level, type, parent_id, word_count

### 3. Dual Indexing
- **FAISS** vector index (cosine similarity, MiniLM 384-dim embeddings)
- **BM25** keyword index (pure-Python, TF-IDF with length normalization)
- Both persisted to disk, loaded lazily, LRU-evicted at 50-doc limit

### 4. Hybrid Retrieval (RRF)
- Multi-query expansion (3 weighted variants per query)
- Vector + BM25 search combined via Reciprocal Rank Fusion
- Dynamic weighting: short queries → BM25-heavy; long → vector-heavy
- Deduplication and score accumulation

### 5. Query Intelligence
- Rule-based classifier: factual / analytical / procedural / comparison
- Automatic routing: decides vector/BM25 weights, top-k, RRF constant
- Complexity estimation for reranker triggering

### 6. Conditional Reranker
- Uses Sarvam-M LLM for relevance scoring (no extra model download)
- Only triggered when top scores are close or many candidates exist
- Scores each candidate 0–10, re-sorts by relevance

### 7. MMR Diversity Filter
- Removes near-duplicate chunks (cosine similarity > 0.85)
- Balances relevance vs diversity (λ = 0.7)
- Ensures topic coverage across sections

### 8. Context Optimization
- Token-safe truncation (1500 token budget)
- Prefers child chunks (detail) over parent chunks (summary)
- Partial chunk inclusion for maximum context utilization

---

## AI Features

### 9. RAG Q&A (/ask)
- Answer grounded in document context only
- Source citations with chunk ID, section, page, preview
- Confidence scoring (high/medium/low)
- Fallback response when confidence is too low

### 10. AI Mentor Mode (/mentor)
- Step-by-step explanation
- Conversation history support (multi-turn)
- Follow-up question generation
- Gentle correction of wrong answers

### 11. Content Generation (/generate)
- **Flashcards**: 10 Q&A pairs
- **Summary**: Paragraph + 5–7 bullets
- **Slides**: 5–7 presentation slides
- **Fun Facts**: 5 non-obvious insights
- **Rapid Fire**: 10 quick Q&A (1–3 word answers)
- **True/False**: 10 statements
- **Fill-in-the-Blanks**: 10 sentences

### 12. Quiz & Mock Test
- Quiz: 5 MCQs (2 easy, 2 medium, 1 hard)
- Mock Test: 15 MCQs (6/6/3 difficulty distribution)
- Per-question evaluation with correct/incorrect details

---

## Search Engine Mode (/search)

### 13. Three Search Modes
1. **Keyword** → BM25 only, returns ranked chunks (fastest)
2. **Hybrid** → RRF fusion, returns ranked chunks (balanced)
3. **AI** → Full pipeline with LLM answer (most accurate)
4. **Auto** → Short query → keyword; long → AI

---

## Personalization

### 14. Weakness Detection (/weakness)
- Per-user per-topic accuracy tracking
- Weak topics identified (accuracy < 60%)
- Study recommendations generated per weak area
- Topic accuracy dashboard (strong/moderate/weak status)

---

## Content Library

### 15. Subject-Based Library (/library)
- Organize documents by subject
- Pre-indexed content for instant access
- Teacher flow: select subject → load pre-built indexes
- CRUD: add/list/remove documents from subjects

---

## Gamification

### 16. XP & Leveling
| Action | XP |
|---|---|
| Upload | +20 |
| Ask/Generate | +5 |
| Quiz complete | +50 |
| Correct answer | +10 |
| Daily streak | +30 |

### 17. Level System
| Level | Title | XP Required |
|---|---|---|
| 1 | Beginner | 0 |
| 2 | Learner | 100 |
| 3 | Scholar | 300 |
| 4 | Expert | 700 |
| 5 | Master | 1500 |

### 18. Leaderboard
- Daily XP ranking
- Automatic daily reset
- In-memory cache for instant response

---

## Trust & Safety

### 19. Confidence Scoring
- Based on retrieval quality, chunk count, LLM self-assessment
- Three levels: high / medium / low
- Fallback response when confidence is too low to answer reliably

### 20. No Hallucination
- All prompts enforce context-only answers
- BASE_CONSTRAINT prevents external knowledge
- CoT stripping removes reasoning blocks from LLM output

---

## Performance

| Operation | Target |
|---|---|
| Upload validation | < 200ms |
| Document pipeline | 3–8s (background) |
| FAISS search | < 5ms |
| BM25 search | < 10ms |
| Full hybrid retrieval | < 300ms |
| LLM response | 1–4s |
| Cache hit | < 5ms |
| Leaderboard | < 1ms |
