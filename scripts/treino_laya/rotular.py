"""Rotula o conjunto do Laya com um modelo professor (T419; D219).

O professor é um modelo aberto maior (Qwen3.5 de 27 a 32B, ou o maior que couber na GPU) servido
por vLLM ou `llama-server` no próprio pod, com a API compatível com a da OpenAI. Cada vaga vai com
o pedido de produção do `encaixe` (`pedidos.pedido_encaixe`) e o esquema `SaidaEncaixe`; a resposta
passa pelo pydantic (`contrato.conferir`, dentro do cliente) e pela anti-invenção
(`tarefas.pede_da_vaga`). Fica fora a vaga cuja resposta não valida no esquema ou fica vazia.

Lê só o que `montar_conjunto.py` escreveu (nunca o gabarito do dono) e recusa vaga do conjunto de
ouro. Retoma sozinho: `<saida>/<lado>.rotulos.jsonl` recebe uma linha por vaga e a vaga já
rotulada não é pedida de novo (a última linha cortada por uma queda é refeita). No fim escreve
`<saida>/<lado>.jsonl` com os exemplos de habilidades e de "verdadeiro ou falso"
(`montar_conjunto.exemplo_habilidades` e `perguntas_vf`).

Falha do servidor numa vaga (prazo, serviço fora) é tentada `TENTATIVAS` vezes; depois a vaga fica
marcada como pulada (`"pulada": "<motivo>"`) e a rodada segue, mas `MAX_PULADAS_SEGUIDAS` vagas
puladas em seguida param a rodada (o servidor caiu). Se as `PRIMEIRAS_VAZIAS` primeiras vagas da
rodada vierem todas vazias, a rodada para: o servidor ou o modelo está mal configurado.

    uv run python scripts/treino_laya/rotular.py --conjunto $DADOS/conjunto \
        --saida $DADOS/rotulado --endereco http://127.0.0.1:8000/v1 --modelo <nome servido>
"""

import argparse
import dataclasses
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
    conferir_saida,
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
PRAZO_S = 300.0  # o professor de 27 a 32B numa GPU barata passa fácil dos 60 s do "fora"
TENTATIVAS = 3  # falhas seguidas do servidor na mesma vaga antes de pulá-la
MAX_PULADAS_SEGUIDAS = 5  # puladas em seguida: o servidor caiu, a rodada para
PRIMEIRAS_VAZIAS = 20  # as primeiras da rodada todas vazias: servidor mal configurado
ANDAMENTO = 50  # uma linha de andamento a cada tantas vagas


class ProfessorMalConfigurado(Exception):
    """As primeiras vagas da rodada vieram todas vazias."""


def reparar(rotulos: Path) -> None:
    """Tira a última linha que não abre (cortada por uma queda) e garante o fim de linha, para a
    próxima linha não colar na anterior."""
    if not rotulos.exists():
        return
    texto = rotulos.read_text(encoding="utf-8")
    if not texto or texto.endswith("\n"):
        return
    corpo, _, ultima = texto.rpartition("\n")
    try:
        json.loads(ultima)
    except json.JSONDecodeError:
        rotulos.write_text(corpo + "\n" if corpo else "", encoding="utf-8")
    else:
        rotulos.write_text(texto + "\n", encoding="utf-8")


def _pedir(backend: Backend, pedido: Any) -> list[str] | Falha:
    """O `pede` cru quando o servidor respondeu (vazio: fora do esquema, recusa, contexto); a
    última `Falha` depois de `TENTATIVAS` falhas do servidor."""
    falha = Falha("servico_fora")
    for _ in range(TENTATIVAS):
        try:
            resposta = backend.pedir(pedido)
        except Falha as erro:
            if erro.backend_ou_vaga == "vaga":
                return []
            falha = erro
        else:
            return list(resposta.dados["pede"])
    return falha


def rotular_lado(
    backend: Backend,
    modelo: str,
    registros: Sequence[Mapping[str, Any]],
    rotulos: Path,
    ouro: Sequence[str],
    prazo_s: float = PRAZO_S,
) -> tuple[int, int]:
    """Acrescenta em `rotulos` uma linha `{"id", "pede"}` por vaga nova (com `"pulada"` quando o
    servidor falhou `TENTATIVAS` vezes nela). Devolve (rotuladas, descartadas). A falha que para a
    rodada sobe; a próxima rodada retoma de onde parou."""
    reparar(rotulos)
    feitos = {r["id"] for r in ler(rotulos)} if rotulos.exists() else set()
    novos = descartados = vistas = 0
    # as puladas só são gravadas quando outra vaga dá certo depois delas: se a rodada parar porque
    # o servidor caiu, elas são pedidas de novo na próxima
    puladas: list[dict[str, Any]] = []
    with open(rotulos, "a", encoding="utf-8") as saida:
        for registro in registros:
            if registro["id"] in feitos:
                continue
            if e_do_ouro(f"{registro['titulo']}\n{registro['descricao']}", ouro):
                raise Recusa(f"vaga {registro['id']!r} é do conjunto de ouro")
            texto = texto_encaixe(registro["titulo"], registro["descricao"])
            pedido = dataclasses.replace(
                pedido_encaixe(texto, "compativel", modelo), prazo_s=prazo_s
            )
            bruto = _pedir(backend, pedido)
            if isinstance(bruto, Falha):
                puladas.append({"id": registro["id"], "pede": [], "pulada": bruto.motivo})
                if len(puladas) >= MAX_PULADAS_SEGUIDAS:
                    raise bruto
                continue
            linhas = [*puladas, {"id": registro["id"], "pede": pede_da_vaga(bruto, texto.texto)}]
            saida.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in linhas)
            saida.flush()
            novos += bool(linhas[-1]["pede"])
            descartados += len(linhas) - bool(linhas[-1]["pede"])
            vistas += len(linhas)
            puladas.clear()
            if vistas >= PRIMEIRAS_VAZIAS and not novos:
                raise ProfessorMalConfigurado(
                    f"as {vistas} primeiras vagas vieram vazias; confira o servidor e o modelo"
                )
            if vistas % ANDAMENTO < len(linhas):
                print(f"  {rotulos.name}: {vistas} vagas nesta rodada", flush=True)
        saida.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in puladas)
    return novos, descartados + len(puladas)


def exemplos_do_lado(
    registros: Sequence[Mapping[str, Any]], rotulos: Mapping[str, list[str]]
) -> list[dict[str, Any]]:
    """Habilidades e "verdadeiro ou falso" das vagas com `pede` não vazio; as falsas vêm das
    outras vagas do mesmo lado (nada atravessa treino e validação). Os itens do lado são juntados
    uma vez; cada vaga custa o mesmo, qualquer que seja o tamanho do lado."""
    com_rotulo = [r for r in registros if rotulos.get(r["id"])]
    todos = sorted({x for r in com_rotulo for x in rotulos[r["id"]]})
    exemplos = []
    for n, registro in enumerate(com_rotulo, 1):
        pede = rotulos[registro["id"]]
        exemplos.append(exemplo_habilidades(registro, pede))
        exemplos += perguntas_vf(registro, pede, todos)
        if n % 1000 == 0:
            print(f"  exemplos: {n}/{len(com_rotulo)} vagas", flush=True)
    return exemplos


def argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--conjunto", type=Path, required=True)
    analisador.add_argument("--saida", type=Path, required=True)
    analisador.add_argument("--endereco", default="http://127.0.0.1:8000/v1")
    analisador.add_argument("--modelo", required=True, help="o nome que o servidor mostra")
    analisador.add_argument("--chave-env", default="JOBOT_IA_CHAVE")
    analisador.add_argument("--prazo", type=float, default=PRAZO_S, help="segundos por vaga")
    return analisador.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] = os.environ,
    montar: Callable[[argparse.Namespace, Mapping[str, str]], Backend] | None = None,
) -> int:
    args = argumentos(argv)
    try:
        conjunto, saida = conferir_caminho(args.conjunto), conferir_saida(args.saida)
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
                backend, args.modelo, registros, saida / f"{nome}.rotulos.jsonl", ouro, args.prazo
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
    except ProfessorMalConfigurado as erro:
        print(f"parado: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
