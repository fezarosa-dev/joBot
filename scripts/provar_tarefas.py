"""Prova as três tarefas novas da 0.6.0 no modelo local baixado (T445; desenho 12 da fase 4).

Currículo (o texto de um PDF montado aqui e lido pelo leitor de produção, em processo filho),
Perguntas e Preparar candidatura, com os pedidos de produção (`pedidos.pedido_*`) e um perfil
sintético: nenhum dado de pessoa (sem nome, e-mail, telefone nem cidade). Cada tarefa vai num caso
comum e num pior caso de leitura, com o texto passando do corte do `ia.json` (o currículo e a vaga
pelo seu corte; o perfil com mais respostas e perguntas feitas do que o corte das perguntas guarda).

Anota o tempo, os tokens lidos e gerados (os `timings` que o `llama-server` põe na resposta) e se a
resposta valida no esquema. Um caso passa quando valida, cabe no prazo do produto (`prazo_s` local)
e no contexto (`CONTEXTO`: os lidos mais o `max_tokens` do pedido). `--espera-s` só alarga a espera
do cliente, para medir o tempo de verdade de quem passa do prazo; quem julga é o prazo do produto.
Sai com 0 se todo caso passou, 1 se não e 2 sem o modelo baixado. Escreve uma linha JSON por caso
e, no Actions, a tabela no resumo do job (`GITHUB_STEP_SUMMARY`).

O `provar_ia` e o `medir_modelo` vêm da mesma pasta, e o PDF é montado pelo `tests/apoio/pdf.py`
(nenhum PDF versionado).
"""

import argparse
import dataclasses
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
from medir_modelo import ENCHIMENTO, Gravador
from provar_ia import subir_local

from jobot.nucleo.ia.contrato import Backend, Falha, Pedido, limites
from jobot.nucleo.ia.pedidos import (
    pedido_candidatura,
    pedido_curriculo,
    pedido_perguntas,
    texto_curriculo,
    texto_encaixe,
)
from jobot.sistema import pdf
from jobot.sistema.llama import CONTEXTO
from jobot.sistema.pastas import pasta_de_dados

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from apoio.pdf import montar_pdf  # noqa: E402

CURRICULO = (
    "Resumo\n"
    "Desenvolvedora backend com 6 anos de experiência em Python e bancos de dados relacionais.\n"
    "Experiência\n"
    "Desenvolvedora Python Pleno - Loja Fictícia Ltda - 2021-03 até o momento\n"
    "Mantive APIs em FastAPI e PostgreSQL; reduzi em 40% o tempo de resposta do catálogo.\n"
    "Desenvolvedora Júnior - Serviços Exemplo S.A. - 2018-02 a 2021-02\n"
    "Automatizei relatórios com Python e pandas e escrevi testes com pytest.",
    "Formação\n"
    "Tecnologia em Análise e Desenvolvimento de Sistemas - Faculdade Exemplo - 2014 a 2017\n"
    "Cursos\n"
    "AWS Cloud Practitioner - Escola Online Exemplo - concluído\n"
    "Pós-graduação em Engenharia de Dados - Universidade Fictícia - cursando, previsão 2027-06\n"
    "Idiomas\n"
    "Inglês avançado; espanhol básico\n"
    "Habilidades\n"
    "Python, FastAPI, Django, PostgreSQL, Docker, Git, pytest, SQL",
)
# o pior caso: projetos até passar do corte do currículo local (12000 caracteres), 8 por página
_PROJETOS = [
    f"Projeto {n}: integração de pagamentos para o Cliente Fictício {n}, com Python, filas e "
    "testes automatizados; documentei a API e acompanhei a implantação em produção."
    for n in range(1, 97)
]
CURRICULO_LONGO = (
    *CURRICULO,
    *("\n".join(_PROJETOS[i : i + 8]) for i in range(0, len(_PROJETOS), 8)),
)
VAGA = (
    "Pessoa Desenvolvedora Python Pleno",
    "Buscamos uma pessoa desenvolvedora Python para o time de pagamentos.\n"
    "Requisitos: Python, FastAPI, PostgreSQL, Docker e testes automatizados.\n"
    "Diferenciais: Kubernetes, mensageria e inglês para conversar com o time de fora.\n"
    "Modelo híbrido, dois dias por semana no escritório.",
)
_CORTE_VAGA = sum(limites()["tarefas"]["encaixe"]["corte"].values())
VAGA_LONGA = (VAGA[0], (ENCHIMENTO * (_CORTE_VAGA // len(ENCHIMENTO) + 2)) + "\n\n" + VAGA[1])
PERFIL: dict[str, object] = {
    "cargo_atual": "Desenvolvedora Python Pleno",
    "anos_de_experiencia": 6,
    "formacao_nivel": "graduacao",
    "habilidades": ["Python", "FastAPI", "Django", "PostgreSQL", "Docker", "Git", "pytest"],
    "idiomas_falados": [["inglês", "avançado"], ["espanhol", "básico"]],
    "resumo": "Desenvolvedora backend com foco em APIs e bancos de dados.",
    "experiencias": [
        {
            "cargo": "Desenvolvedora Python Pleno",
            "empresa": "Loja Fictícia Ltda",
            "inicio": "2021-03",
            "fim": None,
            "descricao": "APIs em FastAPI e PostgreSQL; catálogo 40% mais rápido.",
        },
        {
            "cargo": "Desenvolvedora Júnior",
            "empresa": "Serviços Exemplo S.A.",
            "inicio": "2018-02",
            "fim": "2021-02",
            "descricao": "Relatórios automatizados com Python e pandas.",
        },
    ],
    "cursos": [
        {
            "nome": "Pós-graduação em Engenharia de Dados",
            "instituicao": "Universidade Fictícia",
            "situacao": "cursando",
            "previsao": "2027-06",
        }
    ],
    "respostas": [
        {"pergunta": "Aceita trabalho híbrido?", "resposta": "Sim, até três dias por semana."}
    ],
    "perguntas_feitas": ["Aceita trabalho híbrido?"],
}
# o pior caso: mais respostas e perguntas feitas do que o corte das perguntas guarda
PERFIL_LONGO: dict[str, object] = PERFIL | {
    "respostas": [
        {
            "pergunta": f"Como foi o projeto {n} de integração de pagamentos?",
            "resposta": f"No projeto {n} cuidei das filas, dos testes automatizados e da "
            "documentação da API, e acompanhei a implantação com o time de operações. Depois "
            "da entrega, medi os erros por uma semana e ajustei os alertas com o time.",
        }
        for n in range(1, 41)
    ],
    "perguntas_feitas": [f"Usou alguma ferramenta nova no projeto {n}?" for n in range(1, 71)],
}


@dataclass(frozen=True)
class Caso:
    nome: str
    pedido: Pedido


def casos(modelo: str, ler: Callable[[bytes], pdf.Lido] = pdf.ler) -> list[Caso]:
    """Os pedidos de produção do backend `local`, na ordem da tabela."""
    curriculos = [
        pedido_curriculo(
            texto_curriculo(ler(montar_pdf([*paginas])).texto, "local"), "local", modelo
        )
        for paginas in (CURRICULO, CURRICULO_LONGO)
    ]
    perguntas = [pedido_perguntas(p, "pt", "local", modelo) for p in (PERFIL, PERFIL_LONGO)]
    candidaturas = [
        pedido_candidatura(texto_encaixe(*vaga), perfil, "pt", "local", modelo)
        for vaga, perfil in ((VAGA, PERFIL), (VAGA_LONGA, PERFIL_LONGO))
    ]
    nomes = ("curriculo", "curriculo_longo", "perguntas", "perguntas_longo", "candidatura")
    pedidos = (*curriculos, *perguntas, *candidaturas)
    return [Caso(n, p) for n, p in zip((*nomes, "candidatura_longa"), pedidos, strict=True)]


@dataclass(frozen=True)
class Medida:
    caso: str
    tarefa: str
    segundos: float
    leitura_n: int | None
    geracao_n: int | None
    max_tokens: int
    prazo_s: float
    motivo: str | None  # a `Falha`; None = a resposta validou no esquema

    @property
    def valida(self) -> bool:
        return self.motivo is None

    @property
    def no_prazo(self) -> bool:
        return self.segundos <= self.prazo_s

    @property
    def cabe(self) -> bool:
        """Sem os `timings` não se sabe: não passa (nada de número inventado)."""
        return self.leitura_n is not None and self.leitura_n + self.max_tokens <= CONTEXTO

    @property
    def passou(self) -> bool:
        return self.valida and self.no_prazo and self.cabe


def _numero(timings: Mapping[str, Any] | None, chave: str) -> int | None:
    valor = timings.get(chave) if timings else None
    return valor if isinstance(valor, int) else None


def provar(
    backend: Backend,
    casos: Sequence[Caso],
    timings: list[dict[str, Any] | None],
    *,
    relogio: Callable[[], float] = time.monotonic,
    espera_s: float | None = None,
) -> list[Medida]:
    """Uma medida por caso; toda `Falha` (do backend ou da vaga) é anotada e o caso seguinte
    roda. `timings` é a lista do `Gravador`, esvaziada antes de cada pedido."""
    medidas = []
    for caso in casos:
        pedido = caso.pedido
        if espera_s is not None:
            pedido = dataclasses.replace(pedido, prazo_s=espera_s)
        timings.clear()
        motivo = None
        comeco = relogio()
        try:
            backend.pedir(pedido)
        except Falha as falha:
            motivo = falha.motivo
        segundos = relogio() - comeco
        anotado = timings[-1] if timings else None
        medidas.append(
            Medida(
                caso.nome,
                pedido.tarefa,
                segundos,
                _numero(anotado, "prompt_n"),
                _numero(anotado, "predicted_n"),
                pedido.max_tokens,
                caso.pedido.prazo_s,
                motivo,
            )
        )
        print(json.dumps({**dataclasses.asdict(medidas[-1]), "passou": medidas[-1].passou}))
    return medidas


def _ou(valor: int | None) -> str:
    return "?" if valor is None else str(valor)


def tabela(rotulo: str, modelo: str, medidas: Sequence[Medida]) -> str:
    linhas = [
        f"\n**Tarefas novas no modelo local ({modelo})**\n",
        "| sistema | caso | s | prazo (s) | lidos | gerados | max_tokens "
        f"| lidos + max ≤ {CONTEXTO} | esquema | resultado |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in medidas:
        linhas.append(
            f"| {rotulo} | {m.caso} | {m.segundos:.1f} | {m.prazo_s:.0f} | {_ou(m.leitura_n)} | "
            f"{_ou(m.geracao_n)} | {m.max_tokens} | {'sim' if m.cabe else 'não'} | "
            f"{'valida' if m.valida else m.motivo} | {'passou' if m.passou else 'não passou'} |"
        )
    return "\n".join(linhas)


Montado = tuple[Backend, str, Callable[[], None], list[dict[str, Any] | None]]


def montar_local(env: Mapping[str, str]) -> Montado:
    gravador = Gravador(httpx.HTTPTransport())
    cliente = httpx.Client(transport=gravador, trust_env=False, follow_redirects=False)
    (backend, modelo, fechar), carga = subir_local(pasta_de_dados(env), cliente)
    print(f"llama-server pronto em {carga:.1f} s", flush=True)
    return backend, modelo, fechar, gravador.timings


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] = os.environ,
    montar: Callable[[Mapping[str, str]], Montado] = montar_local,
) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--rotulo", default=f"{platform.system()} {platform.machine()}")
    analisador.add_argument("--espera-s", type=float, default=None, help="só para medir")
    args = analisador.parse_args(argv)
    try:
        backend, modelo, fechar, timings = montar(env)
    except Falha as falha:
        print(f"não deu para subir o modelo local: {falha.motivo}", file=sys.stderr)
        return 2
    try:
        medidas = provar(backend, casos(modelo), timings, espera_s=args.espera_s)
    finally:
        fechar()
    texto = tabela(args.rotulo, modelo, medidas)
    print(texto, flush=True)
    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as saida:
            saida.write(texto + "\n")
    return 0 if all(m.passou for m in medidas) else 1


if __name__ == "__main__":
    sys.exit(main())
