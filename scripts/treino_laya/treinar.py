"""Treina o Laya: LoRA sobre o Qwen3.5 2B do manifesto (T419; D219).

O modelo base é o original do GGUF `2b` de `nucleo/dados/ia_local.json` (`origem`). O treino lê o
que `rotular.py` escreveu (`treino.jsonl` e `validacao.jsonl`, conversa em `prompt`/`completion`;
o erro só conta na resposta) e grava um checkpoint a cada `--salvar-a-cada` passos. O pod da
Community Cloud pode cair: rodar de novo com a mesma `--saida` retoma do último checkpoint inteiro
(`ultimo_checkpoint`). Antes de treinar, confere que nenhum exemplo traz vaga do conjunto de ouro.

`exportar` junta o LoRA ao modelo, converte para GGUF com o `llama.cpp` da mesma versão do
manifesto (`convert_hf_to_gguf.py` e `llama-quantize`), quantiza em Q4_K_M e escreve
`<saida>/manifesto_laya.json` no formato de `ia_local.json` (com o sha256 e o tamanho).

As dependências do treino ficam em `scripts/treino_laya/requirements.txt`, fora do joBot:

    uv run --with-requirements scripts/treino_laya/requirements.txt \
        python scripts/treino_laya/treinar.py treinar --dados rotulado --saida /workspace/laya
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from montar_conjunto import Recusa, conferir_caminho, conferir_sem_ouro, descricoes_do_ouro, ler

RAIZ = Path(__file__).resolve().parents[2]
MANIFESTO = RAIZ / "src" / "jobot" / "nucleo" / "dados" / "ia_local.json"
_CHECKPOINT = re.compile(r"checkpoint-(\d+)")
# o `Trainer` grava este arquivo por último no checkpoint: sem ele, a gravação foi cortada
_COMPLETO = "trainer_state.json"


class Treinador(Protocol):
    def train(self, resume_from_checkpoint: str | None = None) -> Any: ...

    def save_model(self, output_dir: str | None = None) -> None: ...


def base_do_manifesto(manifesto: Path = MANIFESTO) -> str:
    """O repositório do modelo original do GGUF `2b` ("Qwen/Qwen3.5-2B (Qwen), GGUF ...")."""
    origem: str = json.loads(manifesto.read_text(encoding="utf-8"))["modelos"]["2b"]["origem"]
    return origem.split(" ", 1)[0]


def ultimo_checkpoint(pasta: Path) -> Path | None:
    """O checkpoint inteiro de maior passo em `pasta`; o cortado pela queda fica de fora."""
    inteiros = [
        (int(m[1]), p)
        for p in (pasta.iterdir() if pasta.is_dir() else ())
        if (m := _CHECKPOINT.fullmatch(p.name)) and (p / _COMPLETO).is_file()
    ]
    return max(inteiros)[1] if inteiros else None


def montar_hf(args: argparse.Namespace, treino: list[Any], validacao: list[Any]) -> Treinador:
    """O `SFTTrainer` do TRL com LoRA. Importado aqui: os testes não têm torch."""
    from datasets import Dataset  # type: ignore[import-not-found]
    from peft import LoraConfig  # type: ignore[import-not-found]
    from trl import SFTConfig, SFTTrainer  # type: ignore[import-not-found]

    def so_conversa(exemplos: list[Any]) -> Dataset:
        return Dataset.from_list(
            [{"prompt": e["prompt"], "completion": e["completion"]} for e in exemplos]
        )

    config = SFTConfig(
        output_dir=str(args.saida),
        num_train_epochs=args.epocas,
        max_steps=args.max_passos,
        per_device_train_batch_size=args.lote,
        gradient_accumulation_steps=args.acumular,
        learning_rate=args.taxa,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=True,
        logging_steps=10,
        save_strategy="steps",
        save_steps=args.salvar_a_cada,
        save_total_limit=3,
        eval_strategy="steps",
        eval_steps=args.salvar_a_cada,
        max_length=args.max_tokens,
        seed=42,
        report_to=[],
    )
    lora = LoraConfig(
        r=args.rank,
        lora_alpha=2 * args.rank,
        lora_dropout=0.05,
        target_modules="all-linear",
        task_type="CAUSAL_LM",
    )
    treinador: Treinador = SFTTrainer(
        model=args.base,
        args=config,
        train_dataset=so_conversa(treino),
        eval_dataset=so_conversa(validacao),
        peft_config=lora,
    )
    return treinador


def treinar(
    args: argparse.Namespace,
    montar: Callable[[argparse.Namespace, list[Any], list[Any]], Treinador] = montar_hf,
) -> Path:
    """Treina (ou retoma) e grava o LoRA final em `<saida>/lora`."""
    saida = conferir_caminho(args.saida)
    treino, validacao = ler(args.dados / "treino.jsonl"), ler(args.dados / "validacao.jsonl")
    conferir_sem_ouro([*treino, *validacao], descricoes_do_ouro())
    saida.mkdir(parents=True, exist_ok=True)
    retomar = ultimo_checkpoint(saida)
    print(f"retomando de {retomar}" if retomar else "começando do zero", flush=True)
    treinador = montar(args, treino, validacao)
    treinador.train(resume_from_checkpoint=str(retomar) if retomar else None)
    final = saida / "lora"
    treinador.save_model(str(final))
    return final


def sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        while bloco := arquivo.read(1 << 20):
            resumo.update(bloco)
    return resumo.hexdigest()


def entrada_manifesto(gguf: Path, url: str, base: str) -> dict[str, Any]:
    """A entrada do modelo no formato de `ia_local.json` (`modelos.<nome>`)."""
    return {
        "nome": gguf.stem,
        "arquivo": gguf.name,
        "url": url,
        "tamanho": gguf.stat().st_size,
        "sha256": sha256(gguf),
        "licenca": "Apache-2.0",
        "origem": f"{base} (Qwen), ajuste LoRA do joBot (scripts/treino_laya)",
    }


def exportar(args: argparse.Namespace) -> Path:
    """Junta o LoRA, converte para GGUF f16, quantiza em Q4_K_M e escreve o manifesto."""
    from peft import AutoPeftModelForCausalLM
    from transformers import AutoTokenizer  # type: ignore[import-not-found]

    saida, llama = conferir_caminho(args.saida), conferir_caminho(args.llama_cpp)
    junto = saida / "junto"
    modelo = AutoPeftModelForCausalLM.from_pretrained(str(saida / "lora")).merge_and_unload()
    modelo.save_pretrained(str(junto))
    AutoTokenizer.from_pretrained(args.base).save_pretrained(str(junto))
    f16 = saida / "laya-2b-f16.gguf"
    gguf = saida / "Laya-2B-Q4_K_M.gguf"
    conversor = llama / "convert_hf_to_gguf.py"
    subprocess.run(
        [sys.executable, str(conversor), str(junto), "--outfile", str(f16), "--outtype", "f16"],
        check=True,
    )
    quantizar = llama / "build" / "bin" / "llama-quantize"
    subprocess.run([str(quantizar), str(f16), str(gguf), "Q4_K_M"], check=True)
    entrada = entrada_manifesto(gguf, args.url, args.base)
    (saida / "manifesto_laya.json").write_text(
        json.dumps({"laya": entrada}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(entrada, ensure_ascii=False), flush=True)
    return gguf


def argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = analisador.add_subparsers(dest="passo", required=True)
    t = sub.add_parser("treinar", help="LoRA com checkpoint e retomada")
    t.add_argument("--dados", type=Path, required=True, help="a saída do rotular.py")
    t.add_argument("--epocas", type=float, default=2.0)
    t.add_argument("--max-passos", type=int, default=-1, help="-1: pelas épocas")
    t.add_argument("--lote", type=int, default=8)
    t.add_argument("--acumular", type=int, default=2)
    t.add_argument("--taxa", type=float, default=2e-4)
    t.add_argument("--rank", type=int, default=16)
    t.add_argument("--max-tokens", type=int, default=3072)
    t.add_argument("--salvar-a-cada", type=int, default=100)
    e = sub.add_parser("exportar", help="GGUF Q4_K_M com sha256")
    e.add_argument("--llama-cpp", type=Path, required=True, help="clone do llama.cpp, já feito")
    e.add_argument("--url", required=True, help="onde o GGUF será publicado (com versão fixa)")
    for p in (t, e):
        p.add_argument("--saida", type=Path, required=True)
        p.add_argument("--base", default=base_do_manifesto())
    return analisador.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = argumentos(argv)
    try:
        if args.passo == "treinar":
            print(f"LoRA em {treinar(args)}")
        else:
            print(f"GGUF em {exportar(args)}")
    except Recusa as recusa:
        print(f"recusado: {recusa}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
