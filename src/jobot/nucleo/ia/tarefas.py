"""Tarefas da IA (desenho 5.2 e 9 da fase 4): esquema de saída, `VERSAO` e a conferência no código.

O modelo pode inventar ou obedecer a um texto de terceiros (vaga, currículo); a conferência aqui
não confia na resposta: o `encaixe` fica só com o que está na vaga, o `curriculo` marca o que não
está no texto, as `perguntas` tiram o que não serve e a `candidatura` tira de `usou` o que não foi
enviado, calcula `tem` e `faltam` no código e avisa quando a carta cita o que falta (D228)."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from jobot.nucleo.encaixe import casar
from jobot.nucleo.texto import normalizar, sem_pontas

# Sobe quando o texto do pedido (`pedidos.py`) ou o esquema da tarefa mudam: a chave do laço muda e
# a vaga é pedida de novo (desenho 5.1 e 5.4).
VERSAO = {"encaixe": 1, "curriculo": 1, "perguntas": 1, "candidatura": 1}
_FECHADO = ConfigDict(extra="forbid")


class SaidaEncaixe(BaseModel):
    """O que o modelo devolve no `encaixe`: só o que a vaga pede. `tem` e `faltam` são do código."""

    model_config = _FECHADO
    pede: list[Annotated[str, Field(max_length=60)]] = Field(max_length=30)


def _aparece(forma: str, alvo: str) -> bool:
    """`forma` (já normalizada) está em `alvo` como palavra inteira: "Java" não casa em
    "JavaScript", nem "C" em "C++" ou "C#"."""
    return re.search(rf"(?<![\w+#]){re.escape(forma)}(?![\w+#])", alvo) is not None


def pede_da_vaga(pede: list[str], texto: str) -> list[str]:
    """Anti-invenção: fica só o item que aparece, normalizado e como palavra inteira, no texto
    enviado ao modelo (`TextoVaga.texto`); repetidos e vazios saem, na ordem da resposta."""
    alvo = normalizar(texto)
    vistos: set[str] = set()
    ficam = []
    for item in pede:
        limpo = sem_pontas(item)
        forma = normalizar(limpo)
        if not forma or forma in vistos:
            continue
        if _aparece(forma, alvo):
            vistos.add(forma)
            ficam.append(limpo)
    return ficam


# ---- curriculo (desenho 8) ----------------------------------------------------------------------
# Os campos e tetos são os da aba Perfil (T434): o que a IA lê vai para o formulário, que a pessoa
# confere e salva. Nome, e-mail, telefone e cidade ficam de fora: o e-mail e o telefone saem do
# texto antes do pedido e voltam pelo regex local (desenho 8); o nome e a cidade a pessoa escreve.
_TEXTO = Annotated[str, Field(max_length=200)]
_LONGO = Annotated[str, Field(max_length=2000)]
_MES = Annotated[str, Field(max_length=20)]  # AAAA-MM; outro formato vem marcado, não reprovado
Formacao = Literal["medio", "tecnico", "graduacao", "pos_graduacao", "mestrado", "doutorado"]
Situacao = Literal["concluido", "cursando", "trancado"]
Nivel = Literal["basico", "intermediario", "avancado", "fluente"]


class IdiomaLido(BaseModel):
    model_config = _FECHADO
    idioma: Annotated[str, Field(max_length=60)]
    nivel: Nivel | None = None


class ExperienciaLida(BaseModel):
    model_config = _FECHADO
    cargo: _TEXTO
    empresa: _TEXTO | None = None
    inicio: _MES | None = None
    fim: _MES | None = None  # None = o emprego de hoje
    descricao: _LONGO | None = None


class CursoLido(BaseModel):
    model_config = _FECHADO
    nome: _TEXTO
    instituicao: _TEXTO | None = None
    situacao: Situacao | None = None
    previsao: _MES | None = None


class SaidaCurriculo(BaseModel):
    """O que o modelo lê do texto do currículo: os campos da lista permitida do perfil."""

    model_config = _FECHADO
    cargo_atual: _TEXTO | None = None
    anos_de_experiencia: Annotated[int, Field(ge=0, le=60)] | None = None
    formacao_nivel: Formacao | None = None
    resumo: _LONGO | None = None
    habilidades: list[Annotated[str, Field(max_length=60)]] = Field(default=[], max_length=50)
    idiomas_falados: list[IdiomaLido] = Field(default=[], max_length=10)
    experiencias: list[ExperienciaLida] = Field(default=[], max_length=10)
    cursos: list[CursoLido] = Field(default=[], max_length=10)


_DATAS = frozenset({"inicio", "fim", "previsao"})
_AAAA_MM = re.compile(r"((?:19|20)\d\d)-(?:0[1-9]|1[0-2])")


def _sem_traco(texto: str) -> str:
    # "Pós-Graduação", "pos_graduacao" e "pós graduação" comparam iguais.
    return " ".join(re.sub(r"[-_\u2010-\u2015]", " ", normalizar(texto)).split())


def _achou(campo: str, valor: object, alvo: str) -> bool:
    """O valor está no texto: texto e escolha fechada como palavra inteira, número inteiro como
    número, data pelo ano (o mês não é conferido). Data fora de AAAA-MM conta como não achada."""
    # shortcut: escolha fechada só pela palavra do valor em português ("graduacao", "fluente"):
    # currículo em inglês ("Bachelor", "fluent") vem marcado; sinônimos por idioma quando pesar.
    if isinstance(valor, int):
        return _aparece(str(valor), alvo)
    if not isinstance(valor, str):
        return False
    if campo in _DATAS:
        data = _AAAA_MM.fullmatch(valor.strip())
        return data is not None and _aparece(data[1], alvo)
    forma = _sem_traco(sem_pontas(valor))
    return bool(forma) and _aparece(forma, alvo)


def _vazio(valor: object) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def nao_achei(dados: Mapping[str, Any], texto: str) -> frozenset[str]:
    """Os caminhos (`cargo_atual`, `habilidades.1`, `experiencias.0.empresa`) dos valores da
    resposta do `curriculo` (já conferida pelo esquema) que não aparecem, normalizados, no texto
    enviado: a tela os marca "não achei no currículo" e os deixa fora do "Aprovar todas"."""
    alvo = _sem_traco(texto)
    marcados: set[str] = set()

    def conferir(caminho: str, campo: str, valor: object) -> None:
        if isinstance(valor, list):
            for i, item in enumerate(valor):
                conferir(f"{caminho}.{i}", campo, item)
        elif isinstance(valor, Mapping):
            for chave, sub in valor.items():
                conferir(f"{caminho}.{chave}", chave, sub)
        elif not _vazio(valor) and not _achou(campo, valor, alvo):
            marcados.add(caminho)

    for campo, valor in dados.items():
        conferir(campo, campo, valor)
    return frozenset(marcados)


# ---- perguntas (desenho 5.2 e 8) ----------------------------------------------------------------

_PERGUNTA_MAX = 200  # acima disto a pergunta sai (desenho 5.2); o esquema só segura o absurdo
_PERGUNTA = Annotated[str, Field(max_length=1000)]


class PerguntaSugerida(BaseModel):
    model_config = _FECHADO
    pergunta: _PERGUNTA
    por_que: Annotated[str, Field(max_length=300)]


class SaidaPerguntas(BaseModel):
    """Até 5 perguntas de lacuna, cada uma com o porquê."""

    model_config = _FECHADO
    perguntas: list[PerguntaSugerida] = Field(max_length=5)


# shortcut: endereço com esquema, "www." ou terminado num destes domínios (em minúsculas, para
# "ASP.NET" ficar); "golpe.xyz" sem esquema passa, mas não vira link: a tela só mostra texto.
_URL = re.compile(
    r"(?i:\b(?:https?|ftp|mailto|javascript|data|file|tel):|\bwww\.)"
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|br|ly|gov|edu|info)(?![\w-])"
)


def _forma_pergunta(texto: str) -> str:
    return normalizar(sem_pontas(texto))


def _pergunta_serve(pergunta: str, por_que: str) -> bool:
    return (
        len(pergunta) <= _PERGUNTA_MAX
        and len(pergunta.splitlines()) == 1
        and not _URL.search(pergunta)
        and not _URL.search(por_que)
    )


def perguntas_que_ficam(
    itens: Sequence[Mapping[str, Any]], feitas: Sequence[str]
) -> list[dict[str, str]]:
    """As perguntas sugeridas que servem, na ordem da resposta: sai a repetida (entre elas ou já
    feita, normalizada), a de mais de uma linha, a de mais de 200 caracteres e a que leva URL (na
    pergunta ou no porquê)."""
    vistas = {_forma_pergunta(f) for f in feitas}
    ficam = []
    for item in itens:
        pergunta, por_que = item["pergunta"].strip(), item.get("por_que") or ""
        forma = _forma_pergunta(pergunta)
        if forma not in vistas and _pergunta_serve(pergunta, por_que):
            vistas.add(forma)
            ficam.append({"pergunta": pergunta, "por_que": por_que})
    return ficam


# ---- candidatura (desenho 9) --------------------------------------------------------------------


class SaidaCandidatura(BaseModel):
    """Carta e resumo no idioma pedido, até 5 perguntas para o perfil e as chaves do perfil que
    a IA diz ter usado. `tem` e `faltam` não vêm do modelo: são do código (desenho 5.5)."""

    model_config = _FECHADO
    idioma: Literal["pt", "en", "es"]
    carta: Annotated[str, Field(max_length=5000)]
    resumo: _LONGO
    perguntar: list[_PERGUNTA] = Field(default=[], max_length=5)
    usou: list[Annotated[str, Field(max_length=60)]] = Field(default=[], max_length=20)


@dataclass(frozen=True)
class Candidatura:
    """O preparo conferido, pronto para `preparo_candidatura`; `citados` são os itens de `faltam`
    que a carta ou o resumo citam (o aviso da tela)."""

    idioma: str
    carta: str
    resumo: str
    tem: tuple[str, ...]
    faltam: tuple[str, ...]
    perguntar: tuple[str, ...]
    usou: tuple[str, ...]
    citados: tuple[str, ...]


def conferir_candidatura(
    dados: Mapping[str, Any],
    enviados: Mapping[str, object],
    pede: Sequence[str] | None,
    feitas: Sequence[str],
) -> Candidatura:
    """`dados`: a resposta conferida pelo esquema. `enviados`: o que foi no bloco PERFIL
    (`pedidos.dados_para("candidatura", ...)`, sem os vazios). `pede`: o que a vaga pede, do
    `encaixe` (`None` sem resultado). `feitas`: as perguntas do perfil que já existem."""
    habilidades = enviados.get("habilidades")
    meu = [h for h in habilidades if isinstance(h, str)] if isinstance(habilidades, list) else []
    tem, faltam = casar(pede or (), meu)
    texto = normalizar(f"{dados['carta']}\n{dados['resumo']}")
    usou = dict.fromkeys(c for c in dados["usou"] if c in enviados)
    perguntar = perguntas_que_ficam([{"pergunta": p} for p in dados["perguntar"]], feitas)
    return Candidatura(
        idioma=dados["idioma"],
        carta=dados["carta"],
        resumo=dados["resumo"],
        tem=tem,
        faltam=faltam,
        perguntar=tuple(p["pergunta"] for p in perguntar),
        usou=tuple(usou),
        citados=tuple(f for f in faltam if _aparece(normalizar(f), texto)),
    )
