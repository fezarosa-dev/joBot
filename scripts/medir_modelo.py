"""Mede o modelo local baixado (T410; desenho 12 da fase 4): tokens/s de leitura e de geração e o
tempo por vaga, com vagas do tamanho do corte do `ia.json` (o pior caso de leitura).

Sobe o `llama-server` de `jobot ferramentas baixar ia-local` (a pasta de dados de `JOBOT_DADOS`),
manda pelo `ClienteCompativel` de produção (o mesmo corpo do `encaixe`) vagas longas montadas com
as descrições do conjunto de ouro, cada uma diferente (o cache do prompt não pula a leitura), e lê
os `timings` que o `llama-server` põe na resposta. Escreve uma linha JSON por vaga e, no Actions,
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
from jobot.sistema.pastas import pasta_de_dados

VAGAS = 3


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


def vagas_longas(vagas: Sequence[Mapping[str, Any]], n: int = VAGAS) -> list[tuple[str, str]]:
    """`n` vagas com a descrição do tamanho exato do corte (começo + fim), cada uma começando numa
    vaga diferente do conjunto de ouro."""
    corte = limites()["tarefas"]["encaixe"]["corte"]
    tamanho = corte["inicio"] + corte["fim"]
    longas = []
    for i in range(n):
        ordem = [*vagas[i:], *vagas[:i]]
        texto = ""
        while len(texto) < tamanho:
            texto += "\n\n".join(v["descricao"] for v in ordem) + "\n\n"
        longas.append((ordem[0]["titulo"], texto[:tamanho]))
    return longas


def _numero(timings: Mapping[str, Any] | None, chave: str) -> Any:
    return timings.get(chave) if timings else None


def medir(
    backend: ClienteCompativel,
    gravador: Gravador,
    modelo: str,
    vagas: Sequence[tuple[str, str]],
    *,
    relogio: Callable[[], float] = time.monotonic,
) -> list[Medida]:
    """Uma medida por vaga; a falha da vaga (`formato`, `contexto`) ainda mede; a do backend
    sobe."""
    medidas = []
    for titulo, descricao in vagas:
        comeco = relogio()
        try:
            backend.pedir(pedido_encaixe(texto_encaixe(titulo, descricao), "local", modelo))
        except Falha as falha:
            if falha.backend_ou_vaga == "backend":
                raise
            print(f"{titulo}: falha {falha.motivo}", flush=True)
        segundos = relogio() - comeco
        timings = gravador.timings[-1] if gravador.timings else None
        medidas.append(
            Medida(
                segundos,
                _numero(timings, "prompt_n"),
                _numero(timings, "prompt_per_second"),
                _numero(timings, "predicted_n"),
                _numero(timings, "predicted_per_second"),
            )
        )
    return medidas


def _media(valores: Sequence[float | None]) -> str:
    certos = [v for v in valores if v is not None]
    return f"{sum(certos) / len(certos):.1f}" if certos else "?"


def resumo(medidas: Sequence[Medida], rotulo: str, modelo: str, *, carga_s: float) -> str:
    segundos = [m.segundos for m in medidas]
    return (
        "\n| sistema | modelo | subida (s) | leitura (tok/s) | geração (tok/s) "
        "| s por vaga longa (média) | s (máx) |\n|---|---|---|---|---|---|---|\n"
        f"| {rotulo} | {modelo} | {carga_s:.1f} | {_media([m.leitura_tps for m in medidas])} | "
        f"{_media([m.geracao_tps for m in medidas])} | {_media(segundos)} | "
        f"{max(segundos, default=0.0):.1f} |"
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
