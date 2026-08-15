import time


class CircuitBreaker:
    """Circuit breaker por provedor (RNF-06).

    Após `failure_threshold` falhas consecutivas, o provedor é marcado
    indisponível por `window_seconds`. Enquanto aberto, o caller deve pular
    direto para o fallback, sem pagar o custo de timeout a cada chamada.
    """

    def __init__(self, failure_threshold: int = 3, window_seconds: float = 300.0) -> None:
        self._failure_threshold = failure_threshold
        self._window_seconds = window_seconds
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def is_available(self, provider: str) -> bool:
        open_until = self._open_until.get(provider)
        if open_until is None:
            return True
        if time.monotonic() >= open_until:
            # janela expirou: permite nova tentativa (half-open)
            self._open_until.pop(provider, None)
            self._failures[provider] = 0
            return True
        return False

    def record_success(self, provider: str) -> None:
        self._failures[provider] = 0
        self._open_until.pop(provider, None)

    def record_failure(self, provider: str) -> None:
        failures = self._failures.get(provider, 0) + 1
        self._failures[provider] = failures
        if failures >= self._failure_threshold:
            self._open_until[provider] = time.monotonic() + self._window_seconds
