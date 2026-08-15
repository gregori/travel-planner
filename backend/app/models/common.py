from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TipoFonte = Literal["real", "estimativa", "mock"]
NivelConfianca = Literal["alta", "media", "baixa"]


class Fonte(BaseModel):
    """A espinha dorsal da transparência (REQUIREMENTS.md §7.3).

    Todo campo monetário exibido ao usuário referencia uma Fonte.
    """

    tipo: TipoFonte
    provedor: str
    url: str | None = None
    consultado_em: datetime
    confianca: NivelConfianca
    observacao: str | None = None
