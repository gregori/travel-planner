from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SourceType = Literal["real", "estimate", "mock"]
ConfidenceLevel = Literal["high", "medium", "low"]


class Source(BaseModel):
    """A espinha dorsal da transparência (REQUIREMENTS.md §7.3).

    Todo campo monetário exibido ao usuário referencia uma Source.
    """

    type: SourceType
    provider: str
    url: str | None = None
    retrieved_at: datetime
    confidence: ConfidenceLevel
    note: str | None = None
