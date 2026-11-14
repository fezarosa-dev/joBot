"""`jobot avaliar-rotulos <caminho> [--relatorio <arquivo.md>]` (desenho 10.7).

`<caminho>` é a pasta do gabarito: `bruto/*.jsonl` (as vagas) e `rotulos.jsonl` (os rótulos
certos). O gabarito fica fora do repositório; o relatório nunca leva texto de vaga.
"""

import argparse
import json
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from jobot.nucleo.modelo import VagaTratada
from jobot.nucleo.tratamento.medicao import (
    Esperado,
    Medicao,
    esperado_da_linha,
    medir,
    vaga_do_bruto,
)
from jobot.nucleo.tratamento.tratar import tratar


def _linhas(arquivo: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    for n, texto in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        if not texto.strip():
            continue
        try:
            linha = json.loads(texto)
            if not isinstance(linha, dict):
                raise ValueError("a linha não é um objeto JSON")
        except ValueError as erro:  # inclui JSONDecodeError
            raise ValueError(f"{arquivo.name}, linha {n}: {erro}") from erro
        yield n, linha


def _vagas(bruto: Path) -> dict[str, VagaTratada]:
    vagas: dict[str, VagaTratada] = {}
    # só os .jsonl direto na pasta: as pastas de cache ao lado ficam de fora
    for arquivo in sorted(p for p in bruto.glob("*.jsonl") if p.is_file()):
        for n, linha in _linhas(arquivo):
            try:
                vagas[str(linha["id"])] = tratar(vaga_do_bruto(linha))
            except (KeyError, ValueError) as erro:
                raise ValueError(f"{arquivo.name}, linha {n}: {erro}") from erro
    return vagas


def _rotulos(arquivo: Path) -> dict[str, Esperado]:
    rotulos: dict[str, Esperado] = {}
    for n, linha in _linhas(arquivo):
        try:
            id_, esperado = esperado_da_linha(linha)
        except ValueError as erro:
            raise ValueError(f"{arquivo.name}, linha {n}: {erro}") from erro
        rotulos[id_] = esperado
    return rotulos


def _porcento(parte: int | float, todo: int | float) -> str:
    return f"{100 * parte / todo:.1f}".replace(".", ",") + "%"


def relatorio(medicao: Medicao, amostra: int, hoje: date) -> str:
    """Markdown com números e nada mais: nenhum texto de vaga."""
    data = hoje.isoformat()
    linhas = [
        "# Rótulos medidos",
        "",
        f"Medição de {data} contra o gabarito, com {amostra} vagas.",
        "",
        "| Rótulo | Acerto | Amostra | Data |",
        "|---|---|---|---|",
    ]
    for nome, a in medicao.por_rotulo.items():
        linhas.append(f"| {nome} | {_porcento(a.certos, a.total)} | {a.total} | {data} |")
    linhas += [
        "",
        f"Vagas no Brasil: {_porcento(medicao.proporcao_br, 1)} (campo `pais` de `rotulos.jsonl`).",
        "",
        "Modalidade e contrato foram medidos sem o campo declarado pela fonte: "
        "na coleta real, o declarado vence o texto.",
        "",
    ]
    return "\n".join(linhas)


def _medir(raiz: Path) -> tuple[Medicao, int]:
    bruto, rotulos = raiz / "bruto", raiz / "rotulos.jsonl"
    if not bruto.is_dir():
        raise ValueError(f"não achei a pasta {bruto}")
    if not rotulos.is_file():
        raise ValueError(f"não achei o arquivo {rotulos}")
    medicao = medir(_vagas(bruto), _rotulos(rotulos))
    amostra = next(iter(medicao.por_rotulo.values())).total
    if amostra == 0:
        raise ValueError("nenhuma vaga do bruto tem rótulo em rotulos.jsonl")
    return medicao, amostra


def executar(args: argparse.Namespace) -> int:
    raiz = Path(args.caminho)
    if not raiz.exists():
        print(f"O gabarito não está neste computador: {raiz} não existe.")
        return 0
    try:
        medicao, amostra = _medir(raiz)
        if args.relatorio:
            Path(args.relatorio).write_text(
                relatorio(medicao, amostra, date.today()), encoding="utf-8"
            )
    except (ValueError, OSError) as erro:
        print(f"jobot: {erro}", file=sys.stderr)
        return 1
    for nome, a in medicao.por_rotulo.items():
        print(f"{nome:<12}{a.certos}/{a.total}  {_porcento(a.certos, a.total)}")
    if medicao.erros:
        print(f"\nErros ({len(medicao.erros)}): id, rótulo, esperado, obtido")
        for e in medicao.erros:
            print(f"{e.id}  {e.rotulo}  {e.esperado}  {e.obtido}")
    return 0
