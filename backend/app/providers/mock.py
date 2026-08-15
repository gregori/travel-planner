import json
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.models.common import Fonte
from app.models.plan import Atividade, CotacaoCambio, OpcaoHospedagem, OpcaoVoo, SugestaoRefeicao
from app.providers.base import (
    CriteriosAtracoes,
    CriteriosCambio,
    CriteriosHospedagem,
    CriteriosRestaurantes,
    CriteriosVoo,
    ResultadoBusca,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _slug(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return normalizado.strip().lower()


def _carregar(nome_arquivo: str) -> dict:
    with open(FIXTURES_DIR / nome_arquivo, encoding="utf-8") as f:
        return json.load(f)


def _fonte_mock(observacao: str | None = None) -> Fonte:
    return Fonte(
        tipo="mock",
        provedor="fixture",
        url=None,
        consultado_em=datetime.now(UTC),
        confianca="baixa",
        observacao=observacao or "Dado simulado — sem credencial de provedor real configurada.",
    )


class MockHospedagemProvider:
    def __init__(self) -> None:
        self._dados = _carregar("hospedagem.json")

    async def buscar(self, criterios: CriteriosHospedagem) -> ResultadoBusca[OpcaoHospedagem]:
        cidade_slug = _slug(criterios.cidade)
        registros = self._dados.get(cidade_slug)
        if not registros:
            registros = self._gerar_generico(criterios.cidade)
        itens = [
            OpcaoHospedagem(
                nome=r["nome"],
                tipo=r["tipo"],
                preco_por_noite=Decimal(str(r["preco_por_noite"])),
                moeda=r["moeda"],
                localizacao=r["localizacao"],
                avaliacao=r.get("avaliacao"),
                link=r.get("link"),
                fonte=_fonte_mock(),
            )
            for r in registros
        ]
        return ResultadoBusca(itens=itens)

    @staticmethod
    def _gerar_generico(cidade: str) -> list[dict]:
        return [
            {
                "nome": f"Hotel Central {cidade}",
                "tipo": "hotel",
                "preco_por_noite": 350,
                "moeda": "BRL",
                "localizacao": f"Centro, {cidade}",
                "avaliacao": 4.1,
                "link": None,
            },
            {
                "nome": f"Pousada {cidade}",
                "tipo": "pousada",
                "preco_por_noite": 220,
                "moeda": "BRL",
                "localizacao": f"Região central, {cidade}",
                "avaliacao": 4.0,
                "link": None,
            },
            {
                "nome": f"{cidade} Suites Turísticas",
                "tipo": "apart-hotel",
                "preco_por_noite": 290,
                "moeda": "BRL",
                "localizacao": f"Zona turística, {cidade}",
                "avaliacao": 4.2,
                "link": None,
            },
        ]


class MockAtracoesProvider:
    def __init__(self) -> None:
        self._dados = _carregar("atracoes.json")

    async def buscar(self, criterios: CriteriosAtracoes) -> ResultadoBusca[Atividade]:
        cidade_slug = _slug(criterios.cidade)
        registros = self._dados.get(cidade_slug)
        if not registros:
            registros = self._gerar_generico(criterios.cidade)
        interesses = {i.lower() for i in criterios.interesses}
        if interesses:
            filtrados = [
                r for r in registros if interesses.intersection({i.lower() for i in r.get("interesses", [])})
            ]
            registros = filtrados or registros
        itens = [
            Atividade(
                titulo=r["titulo"],
                descricao=r.get("descricao"),
                regiao=r.get("regiao"),
                duracao_min=r.get("duracao_min"),
                custo_estimado=Decimal(str(r.get("custo_estimado", 0))),
                fonte=_fonte_mock(),
            )
            for r in registros
        ]
        return ResultadoBusca(itens=itens)

    @staticmethod
    def _gerar_generico(cidade: str) -> list[dict]:
        return [
            {
                "titulo": f"City tour por {cidade}",
                "descricao": "Passeio guiado pelos principais pontos da cidade.",
                "regiao": "Centro",
                "duracao_min": 120,
                "custo_estimado": 30,
                "interesses": ["cultural"],
            },
            {
                "titulo": f"Museu principal de {cidade}",
                "descricao": "Acervo histórico e cultural local.",
                "regiao": "Centro",
                "duracao_min": 90,
                "custo_estimado": 15,
                "interesses": ["cultural"],
            },
            {
                "titulo": f"Mirante de {cidade}",
                "descricao": "Vista panorâmica, boa opção de tarde livre.",
                "regiao": "Centro",
                "duracao_min": 60,
                "custo_estimado": 0,
                "interesses": ["natureza", "familia"],
            },
        ]


class MockRestaurantesProvider:
    def __init__(self) -> None:
        self._dados = _carregar("restaurantes.json")

    async def buscar(self, criterios: CriteriosRestaurantes) -> ResultadoBusca[SugestaoRefeicao]:
        cidade_slug = _slug(criterios.cidade)
        registros = self._dados.get(cidade_slug)
        if not registros:
            registros = self._gerar_generico(criterios.cidade)

        restricoes_norm = {_slug(r) for r in criterios.restricoes}
        itens: list[SugestaoRefeicao] = []
        for r in registros:
            atendidas = {_slug(a) for a in r.get("restricoes_atendidas", [])}
            if restricoes_norm and not restricoes_norm.issubset(atendidas):
                continue
            if restricoes_norm:
                compat = f"Atende: {', '.join(sorted(criterios.restricoes))}."
            else:
                compat = "Sem restrições alimentares informadas para verificar."
            itens.append(
                SugestaoRefeicao(
                    nome=r["nome"],
                    tipo_refeicao=r["tipo_refeicao"],
                    culinaria=r.get("culinaria"),
                    faixa_preco=r.get("faixa_preco"),
                    compatibilidade=compat,
                    localizacao=r.get("localizacao"),
                    link=r.get("link"),
                    fonte=_fonte_mock(),
                )
            )

        motivo_vazio = None
        if not itens and restricoes_norm:
            motivo_vazio = (
                f"Nenhum restaurante mockado para {criterios.cidade} atende a todas as "
                f"restrições: {', '.join(criterios.restricoes)}."
            )
        return ResultadoBusca(itens=itens, motivo_vazio=motivo_vazio)

    @staticmethod
    def _gerar_generico(cidade: str) -> list[dict]:
        return [
            {
                "nome": f"Restaurante Central de {cidade}",
                "tipo_refeicao": "almoço/jantar",
                "culinaria": "regional",
                "faixa_preco": "€€",
                "restricoes_atendidas": ["vegetariano"],
                "localizacao": f"Centro, {cidade}",
            },
            {
                "nome": f"Casa {cidade}",
                "tipo_refeicao": "jantar",
                "culinaria": "contemporânea",
                "faixa_preco": "€€€",
                "restricoes_atendidas": [],
                "localizacao": f"Zona nobre, {cidade}",
            },
        ]


class WebFlightEstimatorMock:
    """Estimador de voos. RF-12: preço de voo é **sempre** uma faixa rotulada
    ``estimativa`` — nunca ``real``, mesmo quando a busca web está disponível,
    pois não há API de precificação de passagens com garantia de exatidão."""

    def __init__(self) -> None:
        self._dados = _carregar("voos.json")

    async def estimar(self, criterios: CriteriosVoo) -> ResultadoBusca[OpcaoVoo]:
        chave = f"{_slug(criterios.origem)}-{_slug(criterios.destino)}"
        registro = self._dados.get(chave) or self._dados["_default"]
        fonte = Fonte(
            tipo="estimativa",
            provedor="web",
            url=None,
            consultado_em=datetime.now(UTC),
            confianca="media" if chave in self._dados else "baixa",
            observacao="Estimativa por pesquisa web/histórico de rota; faixa, não valor fechado.",
        )
        opcoes = [
            OpcaoVoo(
                companhia=cia,
                origem=criterios.origem,
                destino=criterios.destino,
                preco_min=Decimal(str(registro["preco_min"])),
                preco_max=Decimal(str(registro["preco_max"])),
                moeda=registro["moeda"],
                duracao_horas=registro.get("duracao_horas"),
                escalas=registro.get("escalas", 0),
                fonte=fonte,
            )
            for cia in registro["companhias"]
        ]
        if len(opcoes) >= 2:
            opcoes[0].recomendada = True
            opcoes[0].justificativa = "Menor preço médio e sem escalas na rota estimada."
        return ResultadoBusca(itens=opcoes)


class ExchangeRateProviderMock:
    def __init__(self) -> None:
        self._dados = _carregar("cambio.json")

    async def cotar(self, criterios: CriteriosCambio) -> CotacaoCambio | None:
        if criterios.moeda_origem == criterios.moeda_destino:
            taxa = Decimal("1.0")
        else:
            chave = f"{criterios.moeda_origem}-{criterios.moeda_destino}"
            taxa_raw = self._dados.get(chave)
            if taxa_raw is None:
                return None
            taxa = Decimal(str(taxa_raw))
        return CotacaoCambio(
            moeda_origem=criterios.moeda_origem,
            moeda_destino=criterios.moeda_destino,
            taxa=taxa,
            fonte=_fonte_mock("Taxa mock — não usar para conversão financeira real."),
        )
