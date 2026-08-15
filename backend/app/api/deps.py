from fastapi import Request

from app.config import Settings
from app.llm.base import LLMClient
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_provider_registry(request: Request) -> ProviderRegistry:
    return request.app.state.provider_registry


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client
