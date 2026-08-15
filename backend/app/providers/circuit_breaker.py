import time


class CircuitBreaker:
    """Circuit breaker por provedor (RNF-06).

    Após `limite_falhas` falhas consecutivas, o provedor é marcado
    indisponível por `janela_segundos`. Enquanto aberto, o caller deve pular
    direto para o fallback, sem pagar o custo de timeout a cada chamada.
    """

    def __init__(self, limite_falhas: int = 3, janela_segundos: float = 300.0) -> None:
        self._limite_falhas = limite_falhas
        self._janela_segundos = janela_segundos
        self._falhas: dict[str, int] = {}
        self._aberto_ate: dict[str, float] = {}

    def disponivel(self, provedor: str) -> bool:
        aberto_ate = self._aberto_ate.get(provedor)
        if aberto_ate is None:
            return True
        if time.monotonic() >= aberto_ate:
            # janela expirou: permite nova tentativa (half-open)
            self._aberto_ate.pop(provedor, None)
            self._falhas[provedor] = 0
            return True
        return False

    def registrar_sucesso(self, provedor: str) -> None:
        self._falhas[provedor] = 0
        self._aberto_ate.pop(provedor, None)

    def registrar_falha(self, provedor: str) -> None:
        falhas = self._falhas.get(provedor, 0) + 1
        self._falhas[provedor] = falhas
        if falhas >= self._limite_falhas:
            self._aberto_ate[provedor] = time.monotonic() + self._janela_segundos
