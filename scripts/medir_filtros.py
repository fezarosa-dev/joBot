"""Mede o custo dos filtros da 0.2.0 com muitas vagas (T170, D129). Fica fora do CI.

Semeia N vagas num banco novo (locais com UF, país e cidade, salários de vários tipos, datas
espalhadas em 60 dias) e cronometra `listar`, `contar_chips` e `contar_abas` sem filtro novo,
com cada filtro novo, um por vez, e com todos juntos. A saída é uma tabela: filtro, segundos
e acréscimo sobre a vista sem filtro novo.

Uso: `uv run python scripts/medir_filtros.py [--vagas 300000] [--banco CAMINHO]`. Sem
`--banco`, o banco é um arquivo temporário apagado no fim; com ele, o arquivo fica (e tem de
não existir). O banco é descartável: não aponte para o seu. Com 300 mil vagas, passe `--banco`
em disco: o `/tmp` do sistema pode ficar na RAM.
"""

import argparse
import hashlib
import sqlite3
import statistics
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import batched
from pathlib import Path

from jobot.banco.conexao import abrir
from jobot.banco.leitura import Filtros, contar_abas, contar_chips, listar
from jobot.banco.migrar import migrar

LOTE = 10_000  # vagas por transação: a memória não cresce com N
REPETICOES = 3  # vale a mediana; a primeira rodada também aquece o cache de páginas
BUSCA_ID = 1
_UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
_FONTES = ("remotive", "greenhouse", "lever", "gupy", "workday")
_AREAS = ("tecnologia", "dados", "design", "vendas", "financas")
_NIVEIS = ("estagio", "junior", "pleno", "senior")
_MODALIDADES = ("remoto", "hibrido", "presencial")
_CONTRATOS = ("clt", "pj", "estagio", "trainee")
_DESCRICAO = (
    "Vaga de {titulo} na {empresa}. Atuação com times de produto, entregas semanais, "
    "acompanhamento de métricas e boa comunicação. Benefícios e carreira conforme o nível."
)
_COTACAO_USD = 5.65


def _salario(i: int) -> tuple[object, ...]:
    """(moeda, min, max, periodo, mensal_min, min_brl, max_brl, cotacao_data, plausivel)."""
    tipo = i % 6
    if tipo == 0:  # sem salário
        return (None,) * 9
    if tipo == 1:  # USD, faixa
        usd = 3000 + (i % 50) * 100
        return (
            "USD",
            usd * 100,
            (usd + 1500) * 100,
            "mes",
            usd * 100,
            round(usd * _COTACAO_USD),
            round((usd + 1500) * _COTACAO_USD),
            "2026-11-13",
            1,
        )
    reais = 3000 + (i % 80) * 250
    if tipo == 2:  # BRL, faixa
        return (
            "BRL",
            reais * 100,
            (reais + 2000) * 100,
            "mes",
            reais * 100,
            reais,
            reais + 2000,
            None,
            1,
        )
    if tipo == 3:  # BRL, só o mínimo
        return ("BRL", reais * 100, None, "mes", reais * 100, reais, None, None, 1)
    if tipo == 4:  # BRL, só o máximo
        return ("BRL", None, reais * 100, "mes", None, None, reais, None, 1)
    return ("BRL", 90_000_000, 99_000_000, "mes", 90_000_000, 900_000, 990_000, None, 0)


def _locais(i: int) -> list[tuple[str | None, str | None, str]]:
    """(cidade, uf, pais) de cada local: sem local, só fora do Brasil, ou BR com e sem cidade."""
    if i % 20 == 0:
        return []
    if i % 10 == 1:
        locais: list[tuple[str | None, str | None, str]] = [(f"City {i % 40}", None, "US")]
    else:
        cidade = None if i % 5 == 0 else f"Cidade {i % 300}"
        locais = [(cidade, _UFS[i % len(_UFS)], "BR")]
    if i % 9 == 0:
        locais.append(("Lisboa", None, "PT"))
    return locais


def _linhas(i: int, agora: datetime) -> tuple[tuple[object, ...], ...]:
    """vaga, ocorrência, encaixe do número `i` (o id da vaga é `i + 1`)."""
    vaga_id = i + 1
    nivel = _NIVEIS[i % len(_NIVEIS)]
    titulo = f"{'Estágio em ' if nivel == 'estagio' else ''}Pessoa desenvolvedora {i}"
    empresa = f"Empresa {i % 5000}"
    url = f"https://exemplo.test/vagas/{i}"
    vista = (agora - timedelta(days=i % 60, minutes=i % 1440)).isoformat()
    publicada = None if i % 4 == 0 else (agora - timedelta(days=(i * 7) % 60)).isoformat()
    fechada = vista if i % 25 == 0 else None
    vaga = (
        vaga_id,
        hashlib.sha256(url.encode()).hexdigest(),
        titulo,
        empresa,
        _DESCRICAO.format(titulo=titulo, empresa=empresa),
        url,
        "pt",
        _AREAS[i % len(_AREAS)],
        nivel,
        _MODALIDADES[i % len(_MODALIDADES)],
        _CONTRATOS[i % len(_CONTRATOS)],
        *_salario(i),
        publicada,
        vista,
        vista,
        fechada,
        "salva" if i % 50 == 7 else "nova",
        "1",
    )
    ocorrencia = (vaga_id, _FONTES[i % len(_FONTES)], url, "{}", vista, vista, fechada)
    nota = i % 101
    nivel_encaixe = "bom" if nota >= 70 else "medio" if nota >= 40 else "fraco"
    encaixe = (BUSCA_ID, vaga_id, nota, nivel_encaixe, "[]", "idioma" if i % 40 == 0 else None)
    return vaga, ocorrencia, encaixe


def semear(con: sqlite3.Connection, vagas: int, agora: datetime) -> None:
    """Grava as vagas em lotes, com `executemany` sobre geradores: nada de lista com N linhas."""
    con.execute("PRAGMA synchronous=OFF")  # banco descartável
    con.executemany(
        "INSERT INTO fonte (chave, leva) VALUES (?, 'A')", [(chave,) for chave in _FONTES]
    )
    con.execute(
        "INSERT INTO busca (id, nome, criada_em) VALUES (?, 'Medição', ?)",
        (BUSCA_ID, agora.isoformat()),
    )
    for lote in batched(range(vagas), LOTE, strict=False):
        linhas = [_linhas(i, agora) for i in lote]
        con.executemany(
            "INSERT INTO vaga (id, url_hash, titulo, empresa, descricao_texto, url, idioma, area,"
            " nivel, modalidade, contrato, sal_moeda, sal_min, sal_max, sal_periodo,"
            " sal_mensal_min, sal_mensal_min_brl, sal_mensal_max_brl, sal_cotacao_data,"
            " sal_plausivel, publicada_em, primeira_vista_em, ultima_vista_em, fechada_em,"
            " status, versao_regras) VALUES (" + ", ".join("?" * 26) + ")",
            (v for v, _, _ in linhas),
        )
        con.executemany(
            "INSERT INTO ocorrencia (vaga_id, fonte, url, coletada, primeira_vista_em,"
            " ultima_vista_em, sumiu_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (o for _, o, _ in linhas),
        )
        con.executemany(
            "INSERT INTO encaixe (busca_id, vaga_id, nota, nivel, motivos, oculta_motivo)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (e for _, _, e in linhas),
        )
        con.executemany(
            "INSERT INTO local_vaga (vaga_id, cidade, uf, pais) VALUES (?, ?, ?, ?)",
            ((i + 1, *local) for i in lote for local in _locais(i)),
        )
        con.commit()


def _cenarios() -> list[tuple[str, Filtros]]:
    base = Filtros(busca_id=BUSCA_ID)
    return [
        ("sem filtro novo", base),
        ("país", replace(base, pais="US")),
        ("UF", replace(base, uf="SP")),
        ("cidade", replace(base, cidade="cidade 7")),
        ("empresa", replace(base, empresa="empresa 12")),
        ("publicada há 7 dias", replace(base, publicada="7d")),
        ("não pode ter", replace(base, excluir="estagio")),
        ("salário: só de", replace(base, sal_de_brl=8000)),
        ("salário: só até", replace(base, sal_ate_brl=8000)),
        ("salário: de e até", replace(base, sal_de_brl=5000, sal_ate_brl=15000)),
        ("salário: com sem salário", replace(base, sal_de_brl=8000, sem_salario=True)),
        (
            "todos juntos",
            replace(
                base,
                pais="BR",
                uf="SP",
                cidade="cidade",
                empresa="empresa",
                publicada="30d",
                excluir="estagio",
                sal_de_brl=5000,
                sal_ate_brl=15000,
            ),
        ),
    ]


def _segundos(acao: Callable[[], object]) -> float:
    inicio = time.perf_counter()
    acao()
    return time.perf_counter() - inicio


def _medir(con: sqlite3.Connection, f: Filtros, agora: datetime) -> tuple[float, float, float]:
    """Mediana de `listar`, `contar_chips` e `contar_abas` (cada uma, em segundos)."""
    medidas = [
        (
            _segundos(lambda: listar(con, f, agora)),
            _segundos(lambda: contar_chips(con, f, agora)),
            _segundos(lambda: contar_abas(con, BUSCA_ID, agora)),
        )
        for _ in range(REPETICOES)
    ]
    listas, chips, abas = (statistics.median(coluna) for coluna in zip(*medidas, strict=True))
    return listas, chips, abas


def _executar(caminho: Path, vagas: int) -> None:
    agora = datetime.now(UTC)
    con = abrir(caminho)
    try:
        migrar(con, caminho)
        inicio = time.perf_counter()
        semear(con, vagas, agora)
        print(f"{vagas} vagas semeadas em {time.perf_counter() - inicio:.1f} s")
        print(f"{'filtro':<26}{'listar':>9}{'chips':>9}{'abas':>9}{'total':>9}{'acréscimo':>11}")
        base = 0.0
        for nome, f in _cenarios():
            listas, chips, abas = _medir(con, f, agora)
            total = listas + chips + abas
            if nome == "sem filtro novo":
                base = total
            print(
                f"{nome:<26}{listas:>9.3f}{chips:>9.3f}{abas:>9.3f}{total:>9.3f}"
                f"{total - base:>+11.3f}"
            )
    finally:
        con.close()


def main(argv: Sequence[str] | None = None) -> int:
    pergunta = argparse.ArgumentParser(description="Mede os filtros com muitas vagas.")
    pergunta.add_argument("--vagas", type=int, default=300_000, help="vagas a semear")
    pergunta.add_argument("--banco", type=Path, help="banco novo e descartável (fica no disco)")
    args = pergunta.parse_args(argv)
    if args.vagas < 1:
        print("--vagas precisa ser maior que zero", file=sys.stderr)
        return 2
    if args.banco is not None and args.banco.exists():
        print(f"{args.banco} já existe; aponte para um arquivo novo", file=sys.stderr)
        return 2
    if args.banco is not None:
        _executar(args.banco, args.vagas)
    else:
        with tempfile.TemporaryDirectory(prefix="jobot-medir-") as pasta:
            _executar(Path(pasta) / "medir.db", args.vagas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
