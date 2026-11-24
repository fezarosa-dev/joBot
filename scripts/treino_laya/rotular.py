"""Rotula o conjunto do Laya com um modelo professor (T419; D219).

O professor é um modelo aberto maior (Qwen3.5 de 27 a 32B, ou o maior que couber na GPU) servido
por vLLM ou `llama-server` no próprio pod, com a API compatível com a da OpenAI. Cada vaga vai com
o pedido de produção do `encaixe` (`pedidos.pedido_encaixe`) e o esquema `SaidaEncaixe`; a resposta
passa pelo pydantic (`contrato.conferir`, dentro do cliente) e pela anti-invenção
(`tarefas.pede_da_vaga`). Fica fora a vaga cuja resposta não valida no esquema ou fica vazia.

Lê só o que `montar_conjunto.py` escreveu (nunca o gabarito do dono) e recusa vaga do conjunto de
ouro. Retoma sozinho: `<saida>/<lado>.rotulos.jsonl` recebe uma linha por vaga e a vaga já
rotulada não é pedida de novo. No fim escreve `<saida>/<lado>.jsonl` com os exemplos de
habilidades e de "verdadeiro ou falso" (`montar_conjunto.exemplo_habilidades` e `perguntas_vf`).

    uv run python scripts/treino_laya/rotular.py --conjunto conjunto --saida rotulado \
        --endereco http://127.0.0.1:8000/v1 --modelo <nome servido>
"""

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from montar_conjunto import (
    Recusa,
    conferir_caminho,
    conferir_sem_ouro,
    descricoes_do_ouro,
    e_do_ouro,
    exemplo_habilidades,
    ler,
    perguntas_vf,
)

from jobot.nucleo.ia.compativel_openai import ClienteCompativel
from jobot.nucleo.ia.contrato import Backend, Falha
from jobot.nucleo.ia.pedidos import pedido_encaixe, texto_encaixe
from jobot.nucleo.ia.tarefas import pede_da_vaga

LADOS = ("treino", "validacao")


def rotular_lado(
    backend: Backend,
    modelo: str,
    registros: Sequence[Mapping[str, Any]],
    rotulos: Path,
    ouro: Sequence[str],
) -> tuple[int, int]:
    """Acrescenta em `rotulos` uma linha `{"id", "pede"}` por vaga nova. Devolve (rotuladas,
    descartadas). Falha do backend sobe (a próxima rodada retoma de onde parou)."""
    feitos = {r["id"] for r in ler(rotulos)} if rotulos.exists() else set()
    novos = descartados = 0
    with open(rotulos, "a", encoding="utf-8") as saida:
        for registro in registros:
            if registro["id"] in feitos:
                continue
            if e_do_ouro(f"{registro['titulo']}\n{registro['descricao']}", ouro):
                raise Recusa(f"vaga {registro['id']!r} é do conjunto de ouro")
            texto = texto_encaixe(registro["titulo"], registro["descricao"])
            try:
                resposta = backend.pedir(pedido_encaixe(texto, "compativel", modelo))
            except Falha as falha:
                if falha.backend_ou_vaga == "backend":
                    raise
                pede: list[str] = []  # não validou no esquema (ou recusa, contexto)
            else:
                pede = pede_da_vaga(resposta.dados["pede"], texto.texto)
            saida.write(json.dumps({"id": registro["id"], "pede": pede}, ensure_ascii=False))
            saida.write("\n")
            saida.flush()
            novos += bool(pede)
            descartados += not pede
    return novos, descartados


def exemplos_do_lado(
    registros: Sequence[Mapping[str, Any]], rotulos: Mapping[str, list[str]]
) -> list[dict[str, Any]]:
    """Habilidades e "verdadeiro ou falso" das vagas com `pede` não vazio; as falsas vêm das
    outras vagas do mesmo lado (nada atravessa treino e validação)."""
    com_rotulo = [r for r in registros if rotulos.get(r["id"])]
    todos = sorted({x for r in com_rotulo for x in rotulos[r["id"]]})
    exemplos = []
    for registro in com_rotulo:
        pede = rotulos[registro["id"]]
        exemplos.append(exemplo_habilidades(registro, pede))
        exemplos += perguntas_vf(registro, pede, [x for x in todos if x not in pede])
    return exemplos


def argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--conjunto", type=Path, required=True)
    analisador.add_argument("--saida", type=Path, required=True)
    analisador.add_argument("--endereco", default="http://127.0.0.1:8000/v1")
    analisador.add_argument("--modelo", required=True, help="o nome que o servidor mostra")
    analisador.add_argument("--chave-env", default="JOBOT_IA_CHAVE")
    return analisador.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] = os.environ,
    montar: Callable[[argparse.Namespace, Mapping[str, str]], Backend] | None = None,
) -> int:
    args = argumentos(argv)
    try:
        conjunto, saida = conferir_caminho(args.conjunto), conferir_caminho(args.saida)
        saida.mkdir(parents=True, exist_ok=True)
        ouro = descricoes_do_ouro()
        backend = (
            montar(args, env)
            if montar
            else ClienteCompativel(
                "compativel", args.endereco, env.get(args.chave_env, "").strip() or None
            )
        )
        for nome in LADOS:
            registros = ler(conjunto / f"{nome}.jsonl")
            comeco = time.monotonic()
            novos, fora = rotular_lado(
                backend, args.modelo, registros, saida / f"{nome}.rotulos.jsonl", ouro
            )
            gasto = time.monotonic() - comeco
            print(f"{nome}: {novos} rotuladas, {fora} fora, {gasto:.0f} s", flush=True)
            rotulos = {r["id"]: r["pede"] for r in ler(saida / f"{nome}.rotulos.jsonl")}
            exemplos = exemplos_do_lado(registros, rotulos)
            conferir_sem_ouro(exemplos, ouro)
            with open(saida / f"{nome}.jsonl", "w", encoding="utf-8") as arquivo:
                for exemplo in exemplos:
                    arquivo.write(json.dumps(exemplo, ensure_ascii=False) + "\n")
    except Recusa as recusa:
        print(f"recusado: {recusa}", file=sys.stderr)
        return 2
    except Falha as falha:
        print(f"o professor falhou ({falha.motivo}); rode de novo para retomar", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
