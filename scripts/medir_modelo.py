"""Mede o modelo local baixado (T410; desenho 12 da fase 4): tokens/s de leitura e de geração, o
tempo por vaga e o acerto, com vagas do tamanho do corte do `ia.json` (o pior caso de leitura).

Sobe o `llama-server` de `jobot ferramentas baixar ia-local` (a pasta de dados de `JOBOT_DADOS`),
manda pelo `ClienteCompativel` de produção (o mesmo corpo do `encaixe`) vagas longas: o texto de
enchimento (`ENCHIMENTO`, sobre uma empresa fictícia, sem nenhuma habilidade pedida) e, no fim, a
descrição de uma vaga do conjunto de ouro, uma diferente por vez (o título muda logo no começo e o
cache do prompt não pula a leitura). Lê os `timings` que o `llama-server` põe na resposta e conta
os itens esperados achados, como o `provar_ia`. Escreve uma linha JSON por vaga e, no Actions,
a tabela no resumo do job (`GITHUB_STEP_SUMMARY`). Sai com 1 só se o backend falhar.

O `provar_ia` vem da mesma pasta (`python scripts/medir_modelo.py` põe a pasta no path).
"""

import argparse
import json
import os
import platform
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from provar_ia import OURO, subir_local

from jobot.nucleo.ia.compativel_openai import ClienteCompativel
from jobot.nucleo.ia.contrato import Falha, limites
from jobot.nucleo.ia.pedidos import pedido_encaixe, texto_encaixe
from jobot.nucleo.ia.tarefas import pede_da_vaga
from jobot.nucleo.texto import normalizar
from jobot.sistema.pastas import pasta_de_dados

VAGAS = 5
ENCHIMENTO = (
    "Sobre a empresa: somos uma empresa fictícia de tecnologia com escritórios em várias cidades, "
    "fundada por um grupo de amigos que queria resolver problemas do dia a dia de pequenos "
    "negócios. Nossa cultura valoriza a autonomia, a conversa franca e o aprendizado contínuo. "
    "Trabalhamos em times pequenos, com reuniões curtas e muito espaço para propor ideias. "
    "Benefícios: vale-refeição, auxílio para home office, horário flexível, day off no "
    "aniversário e um orçamento anual para cursos. Nosso processo seletivo tem uma conversa com o "
    "time, uma etapa prática curta e uma conversa final; respondemos a todas as candidaturas. "
)


class Gravador(httpx.BaseTransport):
    """Transporte que lê a resposta inteira, guarda os `timings` do `llama-server` e devolve uma
    resposta com o mesmo corpo para o cliente seguir como sempre."""

    def __init__(self, interno: httpx.BaseTransport) -> None:
        self._interno = interno
        self.timings: list[dict[str, Any] | None] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resposta = self._interno.handle_request(request)
        try:
            corpo = resposta.read()
        finally:
            resposta.close()
        try:
            timings = json.loads(corpo).get("timings")
        except ValueError, AttributeError:
            timings = None
        self.timings.append(timings if isinstance(timings, dict) else None)
        # o corpo já veio decodificado e inteiro: os cabeçalhos de transporte não valem mais
        fora = {"content-encoding", "content-length", "transfer-encoding"}
        cabecalhos = [(k, v) for k, v in resposta.headers.items() if k.lower() not in fora]
        return httpx.Response(resposta.status_code, headers=cabecalhos, content=corpo)

    def close(self) -> None:
        self._interno.close()


@dataclass(frozen=True)
class Medida:
    segundos: float
    leitura_n: int | None
    leitura_tps: float | None
    geracao_n: int | None
    geracao_tps: float | None
    itens: int  # o `pede` depois da anti-invenção
    achados: int
    esperados: int


Longa = tuple[str, str, list[str]]  # título, descrição e o esperado


def vagas_longas(vagas: Sequence[Mapping[str, Any]], n: int = VAGAS) -> list[Longa]:
    """As `n` primeiras vagas do conjunto de ouro com a descrição do tamanho exato do corte
    (começo + fim): o enchimento repetido e, no fim, a descrição da vaga."""
    corte = limites()["tarefas"]["encaixe"]["corte"]
    tamanho = corte["inicio"] + corte["fim"]
    longas = []
    for vaga in vagas[:n]:
        fim = "\n\n" + vaga["descricao"]
        falta = tamanho - len(fim)
        enchimento = (ENCHIMENTO * (falta // len(ENCHIMENTO) + 1))[:falta]
        longas.append((vaga["titulo"], enchimento + fim, list(vaga["esperado"])))
    return longas


def _numero(timings: Mapping[str, Any] | None, chave: str) -> Any:
    return timings.get(chave) if timings else None


def medir(
    backend: ClienteCompativel,
    gravador: Gravador,
    modelo: str,
    vagas: Sequence[Longa],
    *,
    relogio: Callable[[], float] = time.monotonic,
) -> list[Medida]:
    """Uma medida por vaga; a falha da vaga (`formato`, `contexto`) ainda mede; a do backend
    sobe."""
    medidas = []
    for titulo, descricao, esperado in vagas:
        texto = texto_encaixe(titulo, descricao)
        comeco = relogio()
        try:
            pede = backend.pedir(pedido_encaixe(texto, "local", modelo)).dados["pede"]
        except Falha as falha:
            if falha.backend_ou_vaga == "backend":
                raise
            print(f"{titulo}: falha {falha.motivo}", flush=True)
            pede = []
        segundos = relogio() - comeco
        ficam = {normalizar(x) for x in pede_da_vaga(pede, texto.texto)}
        if not ficam >= {normalizar(x) for x in esperado}:
            print(f"{titulo}: veio {pede}", flush=True)
        timings = gravador.timings[-1] if gravador.timings else None
        medidas.append(
            Medida(
                segundos,
                _numero(timings, "prompt_n"),
                _numero(timings, "prompt_per_second"),
                _numero(timings, "predicted_n"),
                _numero(timings, "predicted_per_second"),
                len(ficam),
                sum(normalizar(x) in ficam for x in esperado),
                len(esperado),
            )
        )
    return medidas


def _media(valores: Sequence[float | None]) -> str:
    certos = [v for v in valores if v is not None]
    return f"{sum(certos) / len(certos):.1f}" if certos else "?"


def resumo(medidas: Sequence[Medida], rotulo: str, modelo: str, *, carga_s: float) -> str:
    segundos = [m.segundos for m in medidas]
    achados, esperados = sum(m.achados for m in medidas), sum(m.esperados for m in medidas)
    acerto = achados / esperados if esperados else 0.0
    return (
        "\n| sistema | modelo | subida (s) | leitura (tok/s) | geração (tok/s) "
        "| s por vaga longa (média) | s (máx) | acerto nas longas |\n"
        "|---|---|---|---|---|---|---|---|\n"
        f"| {rotulo} | {modelo} | {carga_s:.1f} | {_media([m.leitura_tps for m in medidas])} | "
        f"{_media([m.geracao_tps for m in medidas])} | {_media(segundos)} | "
        f"{max(segundos, default=0.0):.1f} | {acerto:.0%} ({achados}/{esperados}) |"
    )


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] = os.environ) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--vagas", type=int, default=VAGAS)
    analisador.add_argument("--rotulo", default=f"{platform.system()} {platform.machine()}")
    args = analisador.parse_args(argv)
    vagas = vagas_longas(json.loads(Path(OURO).read_text(encoding="utf-8"))["vagas"], args.vagas)
    gravador = Gravador(httpx.HTTPTransport())
    cliente = httpx.Client(transport=gravador, trust_env=False, follow_redirects=False)
    try:
        (backend, modelo, fechar), carga = subir_local(pasta_de_dados(env), cliente)
    except Falha as falha:
        print(f"não deu para subir o modelo local: {falha.motivo}", file=sys.stderr)
        return 1
    try:
        assert isinstance(backend, ClienteCompativel)
        medidas = medir(backend, gravador, modelo, vagas)
    except Falha as falha:
        print(f"o backend falhou: {falha.motivo}", file=sys.stderr)
        return 1
    finally:
        fechar()
    for medida in medidas:
        print(json.dumps({"rotulo": args.rotulo, "modelo": modelo, **medida.__dict__}), flush=True)
    texto = resumo(medidas, args.rotulo, modelo, carga_s=carga)
    print(texto, flush=True)
    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as saida:
            saida.write(texto + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
