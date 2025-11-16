from fastapi import FastAPI
from pydantic import BaseModel
import uuid

class Context(BaseModel):
    prev: str | None = None
    next: str | None = None

class RecommendRequest(BaseModel):
    doc_id: str
    user_id: str
    selected_text: str
    context: Context

class RecommendOption(BaseModel):
    category: str
    strength: str | None = None

class RecommendResponse(BaseModel):
    insert_id: str
    recommend_session_id: str
    reco_options: list[RecommendOption]

app = FastAPI()

@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    insert_id = str(uuid.uuid4())
    recommend_session_id = str(uuid.uuid4())
    options = [
        RecommendOption(category="thesis", strength="moderate"),
        RecommendOption(category="email", strength="weak"),
    ]

    return RecommendResponse(
        insert_id=insert_id,
        recommend_session_id=recommend_session_id,
        reco_options=options,
    )
