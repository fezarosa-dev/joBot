"""Curva e pesos do progresso da busca (puro, sem relógio próprio)."""

from collections.abc import Mapping, Sequence

PESOS: Mapping[str, int] = {"coleta": 80, "detalhes": 12, "cotacoes": 3, "encaixe": 5}
EXPOENTE = 1.5  # D216: rápida no começo, freando aos poucos
TETO = 0.99
PASSO_S = 2.0
RESTO = 0.9


def pesos_da_execucao(etapas: Sequence[str]) -> dict[str, float]:
    """Pesos só das etapas pedidas, na ordem de `PESOS`, somando 1,0."""
    if not etapas:
        raise ValueError("sem etapas")
    desconhecidas = set(etapas) - set(PESOS)
    if desconhecidas:
        raise ValueError(f"etapa desconhecida: {sorted(desconhecidas)}")
    uteis = [e for e in PESOS if e in etapas]
    soma = sum(PESOS[e] for e in uteis)
    return {e: PESOS[e] / soma for e in uteis}


def _faixa(pesos: Mapping[str, float], etapa: str) -> tuple[float, float]:
    """Começo e fim da etapa em `p`."""
    inicio = 0.0
    for chave, peso in pesos.items():
        if chave == etapa:
            return inicio, min(1.0, inicio + peso)
        inicio += peso
    raise ValueError(f"etapa fora da execução: {etapa}")


def fracao(
    pesos: Mapping[str, float], etapa: str, feitas: int | None, total: int | None
) -> tuple[float, float]:
    """`(p, B)`: andamento da busca em 0..1 e o fim da etapa atual."""
    if etapa == "fim":
        return 1.0, 1.0
    if etapa == "preparando":
        return 0.0, _faixa(pesos, next(iter(pesos)))[1]
    if etapa == "regras":
        # as regras rodam depois dos detalhes: contam como o começo da etapa seguinte
        ordem = list(PESOS)
        seguintes = [k for k in pesos if ordem.index(k) > ordem.index("detalhes")]
        if not seguintes:
            return 1.0, 1.0
        etapa, feitas, total = seguintes[0], None, None
    inicio, fim = _faixa(pesos, etapa)
    if feitas is None or total is None or total <= 0:
        return inicio, fim
    return inicio + (fim - inicio) * min(max(feitas, 0), total) / total, fim


def curva(p: float) -> float:
    """Rápida no começo e freando sem degrau até o fim (D216, pedido do dono)."""
    return float(1 - (1 - p) ** EXPOENTE)


def valor_mostrado(
    p: float, fim_da_etapa: float, partida: float, parado_s: float, *, fechada: bool
) -> float:
    """Valor da barra: nunca desce e, com a etapa parada, só se aproxima do fim dela.

    O avanço lento é contínuo desde o primeiro instante (D216): a cada `PASSO_S` o que falta
    até o fim da etapa cai a `RESTO`, sem espera antes nem degrau entre um passo e outro.
    """
    if fechada:
        return 1.0
    limite = curva(fim_da_etapa)
    resto = float(RESTO ** (parado_s / PASSO_S))
    v = max(curva(p), partida, limite - (limite - partida) * resto)
    return min(v, limite, TETO)


def partida_nova(valor_antes: float, p_novo: float) -> float:
    return max(curva(p_novo), valor_antes)
