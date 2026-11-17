"""Prova a tarefa `encaixe` com o conjunto de ouro (T410; desenho 12 da fase 4).

Para cada vaga de `tests/fixtures/ia/ouro_habilidades.json`, monta o pedido de produção
(`pedidos.pedido_encaixe`), passa a resposta pela anti-invenção (`tarefas.pede_da_vaga`) e conta os
itens esperados achados (comparação por `normalizar`, como o encaixe casa as habilidades). Meta
(proposta do desenho): pelo menos 80% dos itens esperados e nenhuma vaga com `pede` vazio. Sai com
0 na meta, 1 abaixo dela ou com falha do backend e 2 sem a chave ou sem o modelo baixado.

Sem `--backend`, sobe o `llama-server` baixado por `jobot ferramentas baixar ia-local` (a pasta de
dados de `JOBOT_DADOS`). Com `--backend openai|gemini|compativel|anthropic`, quem tem a chave
roda à mão: `JOBOT_IA_CHAVE=... uv run python scripts/provar_ia.py --backend openai --modelo
<nome>` (a variável muda com `--chave-env`; o `compativel` leva `--endereco`). A chave nunca vai no
argv nem no resumo.

Escreve uma linha por vaga com o que faltou, uma linha JSON no fim e, no Actions, uma linha no
resumo do job (`GITHUB_STEP_SUMMARY`).
"""

import argparse
import json
import os
import platform
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from jobot.cli.ferramentas import caminhos_local
from jobot.nucleo.ia.anthropic import ClienteAnthropic
from jobot.nucleo.ia.compativel_openai import ENDERECOS, ClienteCompativel
from jobot.nucleo.ia.contrato import Backend, Falha
from jobot.nucleo.ia.pedidos import pedido_encaixe, texto_encaixe
from jobot.nucleo.ia.tarefas import pede_da_vaga
from jobot.nucleo.texto import normalizar
from jobot.sistema.llama import FalhaLlama, Llama
from jobot.sistema.pastas import pasta_de_dados

OURO = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ia" / "ouro_habilidades.json"
META = 0.8
BACKENDS = ("local", "openai", "gemini", "compativel", "anthropic")

Montado = tuple[Backend, str, Callable[[], None]]


@dataclass
class Resultado:
    esperados: int = 0
    achados: int = 0
    vazias: int = 0  # vagas com `pede` vazio depois da anti-invenção (ou com falha da vaga)
    tempos: list[float] = field(default_factory=list)
    faltas: list[tuple[str, list[str]]] = field(default_factory=list)

    @property
    def acerto(self) -> float:
        return self.achados / self.esperados if self.esperados else 0.0

    @property
    def passou(self) -> bool:
        return self.acerto >= META and self.vazias == 0


def avaliar(
    backend: Backend,
    nome: str,
    modelo: str,
    vagas: Sequence[Mapping[str, Any]],
    *,
    relogio: Callable[[], float] = time.monotonic,
) -> Resultado:
    """Falha da vaga (`formato`, `contexto`, `recusa`) conta como `pede` vazio; a do backend
    sobe."""
    resultado = Resultado()
    for vaga in vagas:
        texto = texto_encaixe(vaga["titulo"], vaga["descricao"])
        comeco = relogio()
        try:
            pede = backend.pedir(pedido_encaixe(texto, nome, modelo)).dados["pede"]
        except Falha as falha:
            if falha.backend_ou_vaga == "backend":
                raise
            print(f"{vaga['titulo']}: falha {falha.motivo}", flush=True)
            pede = []
        resultado.tempos.append(relogio() - comeco)
        achados = {normalizar(x) for x in pede_da_vaga(pede, texto.texto)}
        faltou = [x for x in vaga["esperado"] if normalizar(x) not in achados]
        resultado.esperados += len(vaga["esperado"])
        resultado.achados += len(vaga["esperado"]) - len(faltou)
        resultado.vazias += not achados
        if faltou:
            resultado.faltas.append((vaga["titulo"], faltou))
            print(f"{vaga['titulo']}: faltou {faltou}; veio {pede}", flush=True)
    return resultado


def subir_local(dados: Path, cliente: httpx.Client | None = None) -> tuple[Montado, float]:
    """Sobe o `llama-server` do modelo baixado; devolve o backend e o tempo da subida (a carga do
    modelo conta: o `/health` só dá 200 depois dela)."""
    programa, gguf, nome = caminhos_local(dados)
    llama = Llama(dados, programa, gguf)
    comeco = time.monotonic()
    try:
        endereco, chave = llama.subir()
    except FalhaLlama as falha:
        raise Falha(falha.motivo) from None  # os motivos do `llama.py` são os do contrato
    carga = time.monotonic() - comeco
    backend = ClienteCompativel("local", endereco, chave, cliente=cliente)

    def fechar() -> None:
        backend.fechar()
        llama.encerrar()

    return (backend, nome, fechar), carga


def montar_backend(
    args: argparse.Namespace, env: Mapping[str, str], *, cliente: httpx.Client | None = None
) -> Montado:
    if args.backend == "local":
        montado, carga = subir_local(pasta_de_dados(env), cliente)
        print(f"llama-server pronto em {carga:.1f} s", flush=True)
        return montado
    chave = env.get(args.chave_env, "").strip() or None
    if not args.modelo or (chave is None and args.backend != "compativel"):
        raise Falha("sem_chave")
    if args.backend == "anthropic":
        assert chave is not None
        anthropic = ClienteAnthropic(chave, cliente)
        return anthropic, args.modelo, anthropic.close
    endereco = args.endereco if args.backend == "compativel" else ENDERECOS[args.backend]
    compativel = ClienteCompativel(args.backend, endereco or "", chave, cliente=cliente)
    return compativel, args.modelo, compativel.fechar


def argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--backend", choices=BACKENDS, default="local")
    analisador.add_argument("--modelo", default="", help="nome do modelo (fora do local)")
    analisador.add_argument("--endereco", default="", help="endereço do compatível (/v1)")
    analisador.add_argument("--chave-env", default="JOBOT_IA_CHAVE", help="variável com a chave")
    analisador.add_argument("--ouro", type=Path, default=OURO)
    analisador.add_argument("--rotulo", default=f"{platform.system()} {platform.machine()}")
    return analisador.parse_args(argv)


def linha_resumo(rotulo: str, backend: str, modelo: str, r: Resultado) -> str:
    media = sum(r.tempos) / len(r.tempos) if r.tempos else 0.0
    return (
        f"| {rotulo} | {backend} | {modelo} | {r.acerto:.0%} ({r.achados}/{r.esperados}) | "
        f"{r.vazias} | {media:.1f} | {max(r.tempos, default=0.0):.1f} | "
        f"{'passou' if r.passou else 'abaixo da meta'} |"
    )


def _no_resumo(env: Mapping[str, str], texto: str) -> None:
    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resumo:
            resumo.write(texto + "\n")


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] = os.environ,
    montar: Callable[[argparse.Namespace, Mapping[str, str]], Montado] = montar_backend,
) -> int:
    args = argumentos(argv)
    vagas = json.loads(args.ouro.read_text(encoding="utf-8"))["vagas"]
    try:
        backend, modelo, fechar = montar(args, env)
    except Falha as falha:
        print(f"não deu para montar o backend: {falha.motivo}", file=sys.stderr)
        return 2
    try:
        resultado = avaliar(backend, args.backend, modelo, vagas)
    except Falha as falha:
        print(f"o backend falhou: {falha.motivo}", file=sys.stderr)
        return 1
    finally:
        fechar()
    _no_resumo(
        env,
        "\n| sistema | backend | modelo | acerto | `pede` vazio | s por vaga (média) | s (máx) "
        "| meta |\n|---|---|---|---|---|---|---|---|\n"
        + linha_resumo(args.rotulo, args.backend, modelo, resultado),
    )
    media = sum(resultado.tempos) / len(resultado.tempos) if resultado.tempos else 0.0
    linha = {
        "rotulo": args.rotulo,
        "backend": args.backend,
        "modelo": modelo,
        "acerto": resultado.acerto,
        "achados": resultado.achados,
        "esperados": resultado.esperados,
        "vazias": resultado.vazias,
        "s_por_vaga": round(media, 2),
        "s_max": round(max(resultado.tempos, default=0.0), 2),
        "passou": resultado.passou,
    }
    print(json.dumps(linha, ensure_ascii=False), flush=True)
    return 0 if resultado.passou else 1


if __name__ == "__main__":
    sys.exit(main())
