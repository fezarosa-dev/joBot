"""Escolhe a GPU do treino pelo menor custo total (T419; D219).

Regra do dono (2026-11-24): só Community Cloud, nunca Secure; a GPU é a de menor custo total
(preço por hora × horas previstas), mesmo que seja a mais lenta, com teto de 20 dias.

- Sem `--medir`: lê o catálogo de GPUs do RunPod (só leitura, nenhum recurso criado), junta com as
  vazões medidas (`--vazao arquivo.json`, `{"gpu": "<id do catálogo>", "por_s": <passos/s>}`),
  calcula horas × preço/h por GPU Community e imprime a tabela e a escolha. GPU sem medida
  aparece só com o preço.
- `--medir`: roda de propósito, dentro de um pod curto, uns passos do treino de verdade
  (`treinar.montar_hf`, os mesmos parâmetros do treino) e imprime a linha de vazão da GPU do pod.

    uv run python scripts/treino_laya/custo.py --vazao vazao/*.json --exemplos 40000 --epocas 2
"""

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

GRAPHQL = "https://api.runpod.io/graphql"
_CONSULTA = "query { gpuTypes { id displayName memoryInGb communityCloud communityPrice } }"
MAX_HORAS = 20 * 24  # o dono aceita até uns 20 dias se sair mais barato
MEMORIA_MIN_GB = 16  # LoRA em bf16 do 2B com 3072 tokens e lote 8


@dataclass(frozen=True)
class Gpu:
    id: str
    nome: str
    memoria_gb: int
    preco_h: float | None  # Community; None: a GPU não está na Community Cloud


@dataclass(frozen=True)
class Linha:
    gpu: Gpu
    horas: float | None
    total: float | None


def catalogo(cliente: httpx.Client, chave: str | None = None) -> list[Gpu]:
    """Preço por hora na Community Cloud de cada GPU (consulta de leitura da API do RunPod)."""
    cabecalhos = {"Authorization": f"Bearer {chave}"} if chave else {}
    resposta = cliente.post(GRAPHQL, json={"query": _CONSULTA}, headers=cabecalhos)
    resposta.raise_for_status()
    corpo = resposta.json()
    if corpo.get("errors"):
        raise RuntimeError(f"RunPod recusou a consulta: {corpo['errors']}")
    gpus = []
    for g in corpo["data"]["gpuTypes"]:
        preco = g.get("communityPrice")
        comunidade = g.get("communityCloud") and isinstance(preco, int | float) and preco > 0
        gpus.append(
            Gpu(
                g["id"],
                g["displayName"],
                int(g["memoryInGb"]),
                float(preco) if comunidade else None,
            )
        )
    return gpus


def passos_do_treino(exemplos: int, lote_efetivo: int, epocas: float) -> int:
    return math.ceil(math.ceil(exemplos / lote_efetivo) * epocas)


def escolher(
    gpus: Sequence[Gpu],
    vazoes: Mapping[str, float],
    unidades: int,
    *,
    max_horas: float = MAX_HORAS,
    memoria_min_gb: int = MEMORIA_MIN_GB,
) -> tuple[list[Linha], Linha | None]:
    """Tabela das GPUs Community com memória suficiente, da mais barata no total para a mais cara
    (sem medida no fim), e a escolhida: menor horas × preço/h dentro de `max_horas`."""
    linhas = []
    for gpu in gpus:
        if gpu.preco_h is None or gpu.memoria_gb < memoria_min_gb:
            continue  # Secure ou memória curta: nunca entra
        por_s = vazoes.get(gpu.id)
        horas = unidades / por_s / 3600 if por_s else None
        linhas.append(Linha(gpu, horas, horas * gpu.preco_h if horas is not None else None))
    linhas.sort(key=lambda x: (x.total is None, x.total or 0.0, x.gpu.preco_h or 0.0))
    cabem = [x for x in linhas if x.horas is not None and x.horas <= max_horas]
    return linhas, (cabem[0] if cabem else None)


def ler_vazoes(arquivos: Sequence[Path]) -> dict[str, float]:
    vazoes: dict[str, float] = {}
    for arquivo in arquivos:
        dado = json.loads(arquivo.read_text(encoding="utf-8"))
        vazoes[dado["gpu"]] = float(dado["por_s"])
    return vazoes


def tabela(linhas: Sequence[Linha], escolha: Linha | None) -> str:
    saida = ["| GPU | memória | US$/h (Community) | horas | US$ total |", "|---|---|---|---|---|"]
    for x in linhas:
        horas = f"{x.horas:.1f}" if x.horas is not None else "sem medida"
        total = f"{x.total:.2f}" if x.total is not None else "-"
        marca = " **(escolhida)**" if x is escolha else ""
        saida.append(
            f"| {x.gpu.nome}{marca} | {x.gpu.memoria_gb} GB | {x.gpu.preco_h:.2f} | {horas} "
            f"| {total} |"
        )
    return "\n".join(saida)


def medir(args: argparse.Namespace) -> dict[str, object]:
    """Uns passos do treino de verdade no pod; os primeiros (aquecimento) não contam."""
    import torch  # type: ignore[import-not-found]
    from montar_conjunto import ler
    from treinar import montar_hf

    treino = ler(args.dados / "treino.jsonl")[: args.lote * args.acumular * args.passos_medida]
    args.max_passos, args.epocas = args.aquecimento, 1.0
    montar_hf(args, treino, treino[:8]).train()  # aquecimento: compila e carrega
    args.max_passos, args.saida = args.passos_medida, args.saida / "medida"
    treinador = montar_hf(args, treino, treino[:8])
    comeco = time.monotonic()
    treinador.train()
    por_s = args.passos_medida / (time.monotonic() - comeco)
    return {"gpu": args.gpu or torch.cuda.get_device_name(0), "por_s": round(por_s, 4)}


def argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--medir", action="store_true", help="só dentro do pod, de propósito")
    analisador.add_argument("--vazao", type=Path, nargs="*", default=[])
    analisador.add_argument("--unidades", type=int, help="passos totais (ou use --exemplos)")
    analisador.add_argument("--exemplos", type=int, help="linhas de treino.jsonl")
    analisador.add_argument("--epocas", type=float, default=2.0)
    analisador.add_argument("--lote", type=int, default=8)
    analisador.add_argument("--acumular", type=int, default=2)
    analisador.add_argument("--max-horas", type=float, default=MAX_HORAS)
    # só para --medir (os mesmos nomes do treinar.py)
    analisador.add_argument("--dados", type=Path)
    analisador.add_argument("--saida", type=Path, default=Path("/workspace/medida"))
    analisador.add_argument("--escrever", type=Path, help="arquivo da vazão medida")
    analisador.add_argument("--gpu", help="id do catálogo, se o nome do torch for outro")
    analisador.add_argument("--passos-medida", type=int, default=30)
    analisador.add_argument("--aquecimento", type=int, default=5)
    analisador.add_argument("--taxa", type=float, default=2e-4)
    analisador.add_argument("--rank", type=int, default=16)
    analisador.add_argument("--max-tokens", type=int, default=3072)
    analisador.add_argument("--salvar-a-cada", type=int, default=10**9)
    analisador.add_argument("--base", default=None)
    return analisador.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] = os.environ,
    cliente: httpx.Client | None = None,
) -> int:
    args = argumentos(argv)
    if args.medir:
        if args.dados is None:
            print("--medir precisa de --dados (a saída do rotular.py)", file=sys.stderr)
            return 2
        if args.base is None:
            from treinar import base_do_manifesto

            args.base = base_do_manifesto()
        linha = json.dumps(medir(args))
        if args.escrever:
            args.escrever.write_text(linha + "\n", encoding="utf-8")
        print(linha, flush=True)
        return 0
    if args.unidades is None and args.exemplos is None:
        print("passe --unidades ou --exemplos", file=sys.stderr)
        return 2
    unidades = args.unidades or passos_do_treino(
        args.exemplos, args.lote * args.acumular, args.epocas
    )
    with cliente or httpx.Client(timeout=30) as http:
        gpus = catalogo(http, env.get("RUNPOD_API_KEY") or None)
    linhas, escolha = escolher(gpus, ler_vazoes(args.vazao), unidades, max_horas=args.max_horas)
    print(tabela(linhas, escolha))
    if escolha is None:
        print("\nNenhuma GPU medida cabe no teto; meça mais GPUs com --medir.", flush=True)
        return 1
    print(
        f"\nEscolha: {escolha.gpu.id} (Community), {escolha.horas:.1f} h × "
        f"US$ {escolha.gpu.preco_h:.2f}/h = US$ {escolha.total:.2f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
