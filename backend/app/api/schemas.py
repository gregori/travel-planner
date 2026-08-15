from pydantic import BaseModel


class SessaoResposta(BaseModel):
    session_id: str
    ttl_minutos: int


class ChatRequisicao(BaseModel):
    session_id: str
    mensagem: str


class ErroDetalhe(BaseModel):
    codigo: str
    mensagem: str
    recuperavel: bool = True


class ErroResposta(BaseModel):
    erro: ErroDetalhe
