from pathlib import Path

from dotenv import dotenv_values

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"


def test_env_example_nao_confunde_comentario_com_valor():
    """Regressão: comentários inline em `KEY=   # comentário` não podem virar
    o valor da variável — isso fazia o app sair do modo mock sem credencial
    real (RF-16), pois `LITEAPI_API_KEY` deixava de ser uma string vazia."""
    valores = dotenv_values(ENV_EXAMPLE)
    assert valores["LITEAPI_API_KEY"] == ""
    assert valores["SERPAPI_API_KEY"] == ""
    assert valores["GEOAPIFY_API_KEY"] == ""
    assert "#" not in (valores["LLM_MODEL_CHAIN"] or "")
