# Sentencify Phase1 Context Pack (for Gemini)

Copy-paste this entire document into Gemini before asking questions about Phase 1. It contains the minimum context the model needs to validate the v2.2 design alignment and to reason about Phase 1.5 extensions.

## 1. Project layout (depth ≤ 3)

```text
sentencify-mvp
|- api/
|  |- app/
|  |  |- qdrant/
|  |  |  |- __init__.py
|  |  |  |- client.py
|  |  |  |- collection.py
|  |  |  |- init_data.py
|  |  |  |- insert_spec.py
|  |  |  +- service.py
|  |  |- utils/
|  |  |  |- __init__.py
|  |  |  +- embedding.py
|  |  |- auth.py
|  |  |- consumer.py
|  |  |- main.py
|  |  +- prompts.py
|  |- Dockerfile
|  +- requirements.txt
|- frontend/
|  +- src/ (App.jsx, Editor.jsx, Sidebar.jsx, etc.)
|- data/
|  +- import/
|- docker/
|- docs/
|  |- phase1/
|  +- test/
+- scripts/
```

> The backend logic we care about lives in `api/app`. `frontend/src` holds the React editor shell but is not needed for the Gemini review.

## 2. DTOs & schema definitions (`api/app/main.py:24-78`)

```python
class RecommendRequest(BaseModel):
    doc_id: str
    user_id: str
    selected_text: str
    context_prev: Optional[str] = None
    context_next: Optional[str] = None
    field: Optional[str] = None
    language: Optional[str] = None
    intensity: Optional[str] = None
    user_prompt: Optional[str] = None


class RecommendOption(BaseModel):
    category: str
    language: str
    intensity: str


class RecommendResponse(BaseModel):
    insert_id: str
    recommend_session_id: str
    reco_options: list[RecommendOption]
    P_rule: Dict[str, float]
    P_vec: Dict[str, float]
    context_hash: str
    model_version: str
    api_version: str
    schema_version: str
    embedding_version: str
```

- Request DTO matches PART 3 spec (doc/user/context fields + optional metadata).
- Response DTO includes `recommend_session_id`, `model_version`, `api_version`, `schema_version`, and `embedding_version`.
- Event payloads reuse the same primitives. Key ones are inline in the handler:

```python
a_event = {
    "event": "editor_recommend_options",
    "insert_id": insert_id,
    "recommend_session_id": recommend_session_id,
    "doc_id": req.doc_id,
    "user_id": req.user_id,
    "context_hash": context_hash,
    "reco_options": [o.model_dump() for o in reco_options],
    "P_rule": p_rule,
    "P_vec": p_vec,
    "model_version": model_version,
    "api_version": api_version,
    "schema_version": schema_version,
    "embedding_version": embedding_version,
    ...
}

e_event = {
    "event": "context_block",
    "doc_id": req.doc_id,
    "user_id": req.user_id,
    "context_hash": context_hash,
    "context_full": context_full,
    "embedding_version": embedding_version,
    ...
}
```

These blocks satisfy the A (`editor_recommend_options`) and E (`context_block`) schema requirements for Phase 1.

## 3. Recommendation service core (`api/app/main.py:270-378`)

```python
@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest) -> RecommendResponse:
    insert_id = str(uuid.uuid4())
    recommend_session_id = str(uuid.uuid4())

    context_full = build_context_full(req.context_prev, req.selected_text, req.context_next)
    context_hash = build_context_hash(req.doc_id, context_full)

    p_rule: Dict[str, float] = {"thesis": 0.5, "email": 0.3, "article": 0.2}

    try:
        embedding = get_embedding(context_full)
        p_vec = compute_p_vec(embedding, limit=15)
    except Exception:
        p_vec = {"thesis": 0.7, "email": 0.2, "article": 0.1}

    final_scores: Dict[str, float] = {}
    for k in set(p_rule) | set(p_vec):
        final_scores[k] = 0.5 * p_rule.get(k, 0.0) + 0.5 * p_vec.get(k, 0.0)

    best_category = max(final_scores, key=final_scores.get)
    language = req.language or "ko"
    intensity = req.intensity or "moderate"

    reco_options = [
        RecommendOption(category=best_category, language=language, intensity=intensity)
    ]
    ...
    return RecommendResponse(... as above ...)
```

Key points Gemini should notice:

1. **Context building**: `build_context_full` stitches the selected span with surrounding text, and `build_context_hash` fingerprints `(doc_id + context)` for deduplication.
2. **Embeddings**: `get_embedding` calls the lazily loaded `EmbeddingService` (KLUE/BERT) in `api/app/utils/embedding.py`.
3. **Vector scores**: `compute_p_vec` calls Qdrant (below) and normalizes scores to probabilities.
4. **Rule + vector fusion**: `P_rule` is a stub weight table; `P_vec` is blended via equal weights into `final_scores`.
5. **Reco option assembly**: For Phase 1 we emit a single option seeded by the dominant score.
6. **Versioning**: Handler pins `model_version`, `api_version`, `schema_version`, and `embedding_version` constants for traceability.

Supporting vector code (`api/app/qdrant/service.py`) that Gemini may need:

```python
def compute_p_vec(query_vector, limit=15):
    results = search_vector(query_vector, limit)
    category_scores = defaultdict(float)
    for hit in results:
        category = hit.payload.get("field")
        if category:
            category_scores[category] += hit.score
    total = sum(category_scores.values())
    if total > 0:
        return {k: v / total for k, v in category_scores.items()}
    return {}
```

And the embedding helper (`api/app/utils/embedding.py`):

```python
class EmbeddingService:
    def load_model(self):
        self.tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
        self.model = AutoModel.from_pretrained("klue/bert-base")

    def get_embedding(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        with torch.no_grad():
            output = self.model(**inputs)
        embedding = output.last_hidden_state[:, 0, :].squeeze().numpy()
        return embedding.tolist()
```

## 4. Event publishing (A/I/E plus editor events) (`api/app/main.py:206-267`)

```python
def produce_a_event(payload: Dict) -> None:
    append_jsonl("a.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        producer.send("editor_recommend_options", value=payload)


def produce_i_event(payload: Dict) -> None:
    append_jsonl("i.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        producer.send("model_score", value=payload)


def produce_e_event(payload: Dict) -> None:
    append_jsonl("e.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        producer.send("context_block", value=payload)
```

- Each producer writes to a local JSONL log for observability, then synchronously publishes to Kafka (`get_kafka_producer` returns `None` when Kafka is disabled so the API path stays non-blocking).
- Additional helpers (`produce_b_event`, `produce_c_event`, `produce_k_event`) cover paraphrasing telemetry, but are outside the Phase 1 recommend scope.

## 5. API endpoint flow (controller)

- `@app.post("/recommend", response_model=RecommendResponse)` in `api/app/main.py` wires FastAPI to the service logic shown above.
- Request handling order:
  1. Generate `insert_id` + `recommend_session_id`.
  2. Build context + hash, compute stubbed `P_rule` and vector-based `P_vec`.
  3. Return `RecommendResponse` immediately while emitting `editor_recommend_options`, `model_score`, and `context_block` events via the producer helpers.
- Downstream APIs such as `/paraphrase` and `/log` already exist and can be referenced for Phase 1.5 if Gemini needs more context.

This pack contains exactly what Gemini asked for: folder map, DTO/schema definitions, the heart of the recommendation logic, the vector + embedding helpers, the async producer layer, and the controller entry point. Copy it verbatim to guarantee the model understands Phase 1 before you discuss roadmap questions.
