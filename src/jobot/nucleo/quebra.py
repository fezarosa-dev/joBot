"""Motivos de quebra de fonte e o link "reportar problema" (ADR 0018, decisão 20).

O link só abre o modelo de issue do repositório com a fonte e o motivo já preenchidos; o joBot
não envia nada sozinho (ADR 0014). Cada chave `saude.*` do catálogo está em exatamente um dos
dois conjuntos: chave nova de motivo obriga a decidir se gera o link.
"""

from urllib.parse import quote, urlencode

URL_REPOSITORIO = "https://github.com/fezarosa-dev/joBot"

# quebras que a comunidade pode consertar: formato, bloqueio, rede
MOTIVOS_DE_QUEBRA: frozenset[str] = frozenset(
    {
        "saude.formato_mudou",
        "saude.zero_inesperado",
        "saude.empresa_nao_encontrada",
        "saude.bloqueio",
        "saude.tempo_esgotado",
        "saude.erro_de_rede",
        "saude.resposta_grande",
        "saude.listagem_incompleta",
    }
)
# exceção inesperada, contadores e estados de limite de ritmo: não são defeito da fonte
FORA_DO_LINK: frozenset[str] = frozenset(
    {
        "saude.excecao",
        "saude.parcial_n",
        "saude.sem_detalhe_n",
        "saude.cota",
        "saude.intervalo",
        "saude.parou_429",
        "saude.limite_atingido",
        "saude.orcamento",
    }
)


def link_reportar(fonte: str, motivo: str) -> str | None:
    """URL do modelo `fonte-quebrou.yml` com `fonte` e `motivo`; `None` fora do conjunto fechado.

    `motivo` pode vir como `chave:valor` (regra do executor): só a chave conta e só ela vai na URL.
    Em fonte por empresa, `fonte` é `<fonte>/<identificador>`. Os valores vão por `quote`, então
    `&`, `#`, `%`, espaço e quebra de linha do identificador nunca viram parâmetro novo.
    """
    chave = motivo.partition(":")[0]
    if chave not in MOTIVOS_DE_QUEBRA:
        return None
    consulta = urlencode(
        {"template": "fonte-quebrou.yml", "fonte": fonte, "motivo": chave}, quote_via=quote
    )
    return f"{URL_REPOSITORIO}/issues/new?{consulta}"
