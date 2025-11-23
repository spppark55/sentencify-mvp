from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TrainingExample(BaseModel):
    example_id: str
    recommend_session_id: str
    consistency_flag: str = "high"
    context_embedding: List[float] = Field(default_factory=list)
    macro_category_hint: Optional[str] = None
    reco_category_input: Optional[str] = None
    groundtruth_field: Optional[str] = None
    was_accepted: bool = False
    doc_id: Optional[str] = None
    context_hash: Optional[str] = None
    source_recommend_event_id: Optional[str] = None
    selected_index: Optional[int] = None
    selected_sentence_id: Optional[str] = None
    total_paraphrasing_sentence_count: Optional[int] = None
    maintenance: Optional[str] = None
    target_language: Optional[str] = None
    tone: Optional[str] = None
    llm_provider: Optional[str] = None
    response_time_ms: Optional[int] = None
    was_shadow_mode: Optional[bool] = None
    P_vec: Dict[str, float] = Field(default_factory=dict)
    P_doc: Dict[str, float] = Field(default_factory=dict)
    applied_weight_doc: float = 0.0
    doc_maturity_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
