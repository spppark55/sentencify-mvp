from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: str
    preferred_category_vector: List[float] = Field(default_factory=list)
    preferred_strength_vector: List[float] = Field(default_factory=list)
    recommend_accept_rate: float = 0.0
    paraphrase_execution_count: int = 0
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    schema_version: str = "v2.4"
