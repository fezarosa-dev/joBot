import random
from collections.abc import Mapping

import pytest

from jobot.nucleo import andamento
from jobot.nucleo.andamento import (
    PESOS,
    TETO,
    curva,
    fracao,
    partida_nova,
    pesos_da_execucao,
    valor_mostrado,
)
from jobot.nucleo.http import MAX_RETRY_AFTER_S

TODAS = list(PESOS)


def test_curva_nas_pontas() -> None:
    assert curva(0.0) == 0.0
    assert curva(1.0) == 1.0


def test_curva_comeca_rapida_e_vai_freando() -> None:
    # D216: rápida no começo e freando aos poucos, sem degrau (o passo encolhe sempre)
    grade = [i / 100 for i in range(101)]
    valores = [curva(p) for p in grade]
    passos = [b - a for a, b in zip(valores, valores[1:], strict=False)]
    assert all(passo > 0 for passo in passos)
    assert all(a > b for a, b in zip(passos, passos[1:], strict=False))
    assert all(curva(p) > p for p in grade[1:-1])


def test_pesos_somam_um_sem_uma_etapa() -> None:
    pesos = pesos_da_execucao(["coleta", "encaixe"])
    assert list(pesos) == ["coleta", "encaixe"]
    assert sum(pesos.values()) == pytest.approx(1.0)
    assert pesos["coleta"] / pesos["encaixe"] == pytest.approx(80 / 5)
    assert fracao(pesos, "encaixe", None, None)[0] == pytest.approx(80 / 85)


def test_pesos_seguem_a_ordem_de_pesos_e_somam_um() -> None:
    pesos = pesos_da_execucao(["encaixe", "coleta", "cotacoes", "detalhes"])
    assert list(pesos) == TODAS
    assert sum(pesos.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("etapas", [[], ["coleta", "inexistente"]])
def test_pesos_da_execucao_recusa_lista_vazia_ou_etapa_desconhecida(etapas: list[str]) -> None:
    with pytest.raises(ValueError):
        pesos_da_execucao(etapas)


def test_fracao_dentro_da_etapa_com_contagem() -> None:
    pesos = pesos_da_execucao(TODAS)
    p0, b0 = fracao(pesos, "coleta", 0, 10)
    p5, b5 = fracao(pesos, "coleta", 5, 10)
    assert p0 == 0.0
    assert p5 == pytest.approx(0.8 * 0.5)
    assert b0 == b5 == pytest.approx(0.8)
    p, b = fracao(pesos, "detalhes", 1, 4)
    assert p == pytest.approx(0.8 + 0.12 * 0.25)
    assert b == pytest.approx(0.92)


@pytest.mark.parametrize(("feitas", "total"), [(None, None), (3, None), (None, 3), (3, 0), (0, 0)])
def test_etapa_sem_contagem_fica_no_comeco(feitas: int | None, total: int | None) -> None:
    pesos = pesos_da_execucao(TODAS)
    p, b = fracao(pesos, "detalhes", feitas, total)
    assert p == pytest.approx(0.8)
    assert b == pytest.approx(0.92)


def test_feitas_alem_do_total_nao_passa_do_fim_da_etapa() -> None:
    pesos = pesos_da_execucao(TODAS)
    p, b = fracao(pesos, "coleta", 99, 10)
    assert p == pytest.approx(0.8)
    assert b == pytest.approx(0.8)


def test_preparando_e_fim() -> None:
    pesos = pesos_da_execucao(TODAS)
    ini, fim = fracao(pesos, "preparando", None, None)
    assert ini == 0.0
    assert fim == pytest.approx(0.8)
    assert fracao(pesos, "fim", None, None) == (1.0, 1.0)
    sem_coleta_primeiro = pesos_da_execucao(["detalhes", "encaixe"])
    assert fracao(sem_coleta_primeiro, "preparando", None, None)[1] == pytest.approx(12 / 17)


def test_etapa_desconhecida_na_fracao_levanta() -> None:
    pesos = pesos_da_execucao(["coleta", "encaixe"])
    with pytest.raises(ValueError):
        fracao(pesos, "detalhes", None, None)


def test_regras_contam_na_etapa_seguinte() -> None:
    quatro = pesos_da_execucao(TODAS)
    assert fracao(quatro, "regras", None, None) == fracao(quatro, "cotacoes", None, None)
    assert fracao(quatro, "regras", None, None)[0] == pytest.approx(0.92)
    sem_cotacoes = pesos_da_execucao(["coleta", "detalhes", "encaixe"])
    assert fracao(sem_cotacoes, "regras", None, None) == fracao(sem_cotacoes, "encaixe", None, None)
    assert fracao(sem_cotacoes, "regras", None, None)[0] == pytest.approx(92 / 97)


def test_valor_nunca_desce() -> None:
    pesos = pesos_da_execucao(TODAS)
    # (etapa, feitas, total) por pergunta; a etapa muda e o contador sobe em degraus
    roteiro: list[tuple[str, int | None, int | None]] = [("preparando", None, None)] * 3
    roteiro += [("coleta", min(i // 4, 10), 10) for i in range(30)]
    roteiro += [("detalhes", 1, 2)] * 8 + [("regras", None, None)] * 6
    roteiro += [("encaixe", 2, 5)] * 8 + [("fim", None, None)] * 5
    assert len(roteiro) >= 60

    anterior = 0.0
    partida = 0.0
    visto = None
    parado_s = 0.0
    for i, (etapa, feitas, total) in enumerate(roteiro):
        p, b = fracao(pesos, etapa, feitas, total)
        chave = (etapa, feitas, total)
        if chave != visto:
            partida = partida_nova(anterior, p)
            parado_s = 0.0
            visto = chave
        ultima = i == len(roteiro) - 1
        valor = valor_mostrado(p, b, partida, parado_s, fechada=etapa == "fim" and ultima)
        assert valor >= anterior, (i, etapa, valor, anterior)
        anterior = valor
        parado_s += 2.0
    assert anterior == 1.0


def test_valor_nunca_desce_com_degraus_aleatorios_e_nunca_passa_da_etapa() -> None:
    sorteio = random.Random(244)
    pesos = pesos_da_execucao(TODAS)
    etapas = ["coleta", "detalhes", "cotacoes", "encaixe"]
    for _ in range(200):
        anterior, partida, parado_s, visto = 0.0, 0.0, 0.0, None
        ix, feitas = 0, 0
        for _ in range(60):
            if sorteio.random() < 0.15:
                feitas += sorteio.randint(1, 3)
            if sorteio.random() < 0.05 and ix < len(etapas) - 1:
                ix, feitas = ix + 1, 0
            etapa, total = etapas[ix], 8
            p, b = fracao(pesos, etapa, min(feitas, total), total)
            if (etapa, p) != visto:
                partida, parado_s, visto = partida_nova(anterior, p), 0.0, (etapa, p)
            valor = valor_mostrado(p, b, partida, parado_s, fechada=False)
            assert anterior <= valor <= min(curva(b), TETO)
            anterior = valor
            parado_s += sorteio.choice([2.0, 2.0, 7.0, 300.0])
        assert anterior > 0.1


def test_avanco_lento_nunca_passa_do_limite() -> None:
    p, b = 0.6, 0.8
    partida = curva(p)
    limite = curva(b)
    for s in range(0, 3601):
        assert valor_mostrado(p, b, partida, float(s), fechada=False) <= limite
    for s in range(5, int(MAX_RETRY_AFTER_S) + 1):
        v = valor_mostrado(p, b, partida, float(s), fechada=False)
        assert curva(p) < v < limite, s
    assert valor_mostrado(p, b, partida, 0.0, fechada=False) == max(curva(p), partida)


def test_avanco_lento_sem_parada_nem_degrau() -> None:
    # D216: anda desde o primeiro instante, sempre um pouco, e nunca dá salto
    p, b = 0.6, 0.8
    partida = curva(p)
    valores = [valor_mostrado(p, b, partida, s / 10, fechada=False) for s in range(0, 600)]
    passos = [y - x for x, y in zip(valores, valores[1:], strict=False)]
    assert all(passo > 0 for passo in passos)
    assert max(passos) < 0.005
    assert all(x >= y for x, y in zip(passos, passos[1:], strict=False))


def test_avanco_lento_cresce_com_o_tempo_parado() -> None:
    p, b = 0.6, 0.8
    anteriores = [valor_mostrado(p, b, curva(p), float(s), fechada=False) for s in range(0, 700)]
    assert all(x <= y for x, y in zip(anteriores, anteriores[1:], strict=False))
    assert anteriores[100] > anteriores[10] > anteriores[0]


def test_avanco_lento_fecha_o_resto_a_cada_passo() -> None:
    p, b = 0.6, 0.8
    partida, limite = curva(p), curva(b)
    # o que falta cai a 0,9 a cada 2 s, contínuo: 20 s = 10 passos, 21 s = 10,5
    esperado = limite - (limite - partida) * 0.9**10
    assert valor_mostrado(p, b, partida, 20.0, fechada=False) == pytest.approx(esperado)
    meio = limite - (limite - partida) * 0.9**10.5
    assert valor_mostrado(p, b, partida, 21.0, fechada=False) == pytest.approx(meio)


def test_teto_ate_fechar() -> None:
    assert valor_mostrado(1.0, 1.0, 0.99, 999, fechada=False) <= TETO
    assert valor_mostrado(1.0, 1.0, 0.99, 999, fechada=True) == 1.0


def test_partida_nova_nunca_menor() -> None:
    assert partida_nova(0.7, 0.5) == 0.7
    assert partida_nova(0.1, 0.5) == curva(0.5)


def test_constantes_da_proposta() -> None:
    pesos: Mapping[str, int] = andamento.PESOS
    assert list(pesos.items()) == [
        ("coleta", 80),
        ("detalhes", 12),
        ("cotacoes", 3),
        ("encaixe", 5),
    ]
    assert andamento.EXPOENTE == 1.5
