from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model_chain: str = "openrouter/auto"

    booking_api_key: str | None = None
    tripadvisor_api_key: str | None = None
    exchange_api_url: str = "https://api.frankfurter.app"

    session_ttl_minutes: int = 60
    max_tool_calls_per_session: int = 25
    max_tokens_per_session: int = 200_000
    cache_ttl_minutes: int = 15

    rate_limit_per_minute: int = 30

    @property
    def model_chain_list(self) -> list[str]:
        return [m.strip() for m in self.llm_model_chain.split(",") if m.strip()]


def get_settings() -> Settings:
    return Settings()
