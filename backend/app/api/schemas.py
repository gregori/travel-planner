from pydantic import BaseModel


class SessionResponse(BaseModel):
    session_id: str
    ttl_minutes: int


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    recoverable: bool = True


class ErrorResponse(BaseModel):
    error: ErrorDetail
