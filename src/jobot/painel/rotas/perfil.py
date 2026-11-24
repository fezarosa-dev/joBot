"""Aba Perfil de Configurações: dados, idiomas, habilidades, experiências, cursos e "Apagar
perfil" (desenho 8 da fase 4; T413, T434; D200, D230).

Tudo aqui é dado da pessoa e fica no computador: nenhuma rota deste módulo manda nada para fora.
O currículo em PDF (`POST /configuracoes/perfil/curriculo`, T435) é lido no processo filho de
`sistema/pdf.py` e não é guardado: nem o PDF nem o texto vão ao banco ou à pasta de dados.
As habilidades vão ao banco limpas e sem repetidos (`habilidades_do_texto`); mudar a lista
recalcula o encaixe **antes** de gravar, com a lista nova (padrões «Config»): se o recálculo
falhar, nada muda. Todo formulário da aba posta em `POST /configuracoes/perfil` (rota de
`configuracoes.py`, que chama `gravar_perfil`); o campo `secao` escolhe o que grava, e sem ele são
as habilidades (o formulário da 0.5.0). Este módulo não importa aquele.
"""

import asyncio
import logging
import re
import sqlite3
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, replace
from typing import Any, get_args
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, Response
from starlette.datastructures import FormData, UploadFile

from jobot.agenda.ia import Obter
from jobot.banco import buscas, perfil
from jobot.banco.cadastros import ler_config
from jobot.banco.ia import TarefaIA, tarefa_ia
from jobot.nucleo.ia.contrato import Falha, Motivo, Pedido, Resposta
from jobot.nucleo.ia.pedidos import pedido_perguntas, perguntas_base
from jobot.nucleo.ia.tarefas import perguntas_que_ficam
from jobot.nucleo.texto import normalizar, sem_pontas
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar
from jobot.sistema import pdf

log = logging.getLogger(__name__)

router = APIRouter(prefix="/configuracoes/perfil")

PERFIL = "/configuracoes/perfil"
TETO_HABILIDADES = 200
TETO_CARACTERES = 100
# os serviços de fora com nome no catálogo; backend desconhecido vira "outro" (nunca `KeyError`)
SERVICOS = ("anthropic", "openai", "gemini", "compativel")


def _linha(texto: str) -> str:
    """Uma linha limpa: controle vira espaço, invisível (Cf) sai, espaços simples e sem pontas."""
    limpa = "".join(
        "" if (c := unicodedata.category(ch)) == "Cf" else " " if c == "Cc" else ch for ch in texto
    )
    return " ".join(limpa.split())


def habilidades_do_texto(texto: str) -> list[str]:
    """Uma habilidade por linha, limpa por `_linha` e sem as pontas do encaixe (`sem_pontas`).
    Repetida pela forma normalizada sai e a primeira grafia fica. Mais de `TETO_HABILIDADES` ou
    uma com mais de `TETO_CARACTERES`: `ValueError`."""
    vistas: set[str] = set()
    lista: list[str] = []
    for linha in texto.splitlines():
        nome = sem_pontas(_linha(linha))
        forma = normalizar(nome)
        if forma and forma not in vistas:
            vistas.add(forma)
            lista.append(nome)
    if len(lista) > TETO_HABILIDADES or any(len(h) > TETO_CARACTERES for h in lista):
        raise ValueError("habilidades demais ou longas demais")
    return lista


def _recalcular(request: Request, con: sqlite3.Connection, lista: Sequence[str]) -> None:
    buscas.recalcular_encaixe(
        con,
        None,
        bool(ler_config(con, "regras_ocultar_ligadas")),
        hoje=relogio_do_painel(request).agora().astimezone().date(),  # o dia local (DP8)
        habilidades_perfil=list(lista),
    )


def salvar_habilidades(request: Request, con: sqlite3.Connection, lista: Sequence[str]) -> None:
    """Recalcula só se o conjunto mudou (ordem e grafia não mudam o encaixe) e grava a lista."""
    atuais = perfil.habilidades(con)
    if {normalizar(h) for h in lista} != {normalizar(h) for h in atuais}:
        _recalcular(request, con, lista)
    perfil.gravar_habilidades(con, lista, relogio_do_painel(request).agora())


def frase_de_privacidade(tarefa: TarefaIA, base: str) -> dict[str, str | None]:
    """A chave da frase (`<base>desligada`, `local` ou `fora`) e, fora, o nome do serviço; a aba
    IA usa a mesma regra com as frases dela (T415)."""
    if not tarefa.ligada:
        return {"chave": base + "desligada", "servico": None}
    if tarefa.backend == "local":
        return {"chave": base + "local", "servico": None}
    nome = tarefa.backend if tarefa.backend in SERVICOS else "outro"
    return {"chave": base + "fora", "servico": "configuracoes.perfil.servico." + nome}


def _privacidade(con: sqlite3.Connection) -> dict[str, str | None]:
    """A frase de privacidade (desenho 8) pelo estado da tarefa `encaixe`; fala só do encaixe."""
    return frase_de_privacidade(tarefa_ia(con, "encaixe"), "configuracoes.perfil.privacidade.")


def _privacidade_perguntas(con: sqlite3.Connection) -> dict[str, str | None] | None:
    """Com a tarefa `perguntas` ligada, a frase dela vai junto: as habilidades e o resto do
    perfil vão naquele pedido (D233)."""
    tarefa = tarefa_ia(con, "perguntas")
    base = "configuracoes.perfil.perguntas.privacidade."
    return frase_de_privacidade(tarefa, base) if tarefa.ligada else None


# --- o resto do perfil (T434) -----------------------------------------------------------------

FORMACOES: tuple[str, ...] = get_args(perfil.Formacao)
SITUACOES: tuple[str, ...] = get_args(perfil.Situacao)
IDIOMAS_FIXOS = ("pt", "en", "es")  # A9 do mapa do perfil; o resto vai em "outro idioma"
NIVEIS = ("basico", "intermediario", "avancado", "fluente")  # vazio = não informar (não grava)
TETO_ITENS = 10  # experiências e, à parte, cursos (A5)
TETO_LINKS = 10
TETO_OUTROS = 10  # outros idiomas; a tela desenha até um a mais, vazio
_TETO = {"email": 254, "telefone": 40, "resumo": 2000, "descricao": 2000, "link": 500, "idioma": 60}
_TETO_PADRAO = 200
_MES = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_ID = re.compile(r"[1-9]\d{0,17}")  # até 18 dígitos: sempre cabe no INTEGER do SQLite
# campo do formulário de dados -> `id` do controle na tela (o erro marca o controle certo)
_IDS_DADOS = {
    "nome": "perfil-nome",
    "email": "perfil-email",
    "telefone": "perfil-telefone",
    "cidade_moradia": "perfil-cidade",
    "cargo_atual": "perfil-cargo",
    "anos_de_experiencia": "perfil-anos",
    "formacao_nivel": "perfil-formacao",
    "resumo": "perfil-resumo",
    "links": "perfil-links",
}
_CAMPOS_ITEM = {
    "experiencia": ("cargo", "empresa", "inicio", "fim", "descricao"),
    "curso": ("nome", "instituicao", "situacao", "previsao"),
}
_PREFIXO = {"experiencia": "exp", "curso": "curso"}
_ANCORA = {None: "habilidades", "dados": "sobre", "experiencia": "experiencias", "curso": "cursos"}


class _Recusa(ValueError):
    """Valor digitado errado: a página volta com o digitado, a mensagem e o controle marcado."""

    def __init__(self, chave: str, campo_id: str) -> None:
        super().__init__(chave, campo_id)
        self.chave = chave
        self.campo_id = campo_id


def _bruto(form: FormData, nome: str) -> str:
    """O texto do campo; ausente ou arquivo é formulário que a tela não manda: 422 seco."""
    valor = form.get(nome)
    if not isinstance(valor, str):
        raise HTTPException(422)
    return valor


def _texto(valor: str, campo_id: str, teto: int = _TETO_PADRAO) -> str | None:
    """Uma linha limpa; vazia = `None`; acima do teto, recusa."""
    limpo = _linha(valor)
    if len(limpo) > teto:
        raise _Recusa("configuracoes.perfil.erro.longo", campo_id)
    return limpo or None


def _bloco(valor: str, campo_id: str) -> str | None:
    """Texto de várias linhas: cada linha limpa, sem as vazias das pontas; vazio = `None`."""
    limpo = "\n".join(_linha(linha) for linha in valor.splitlines()).strip("\n")
    if len(limpo) > _TETO["resumo"]:
        raise _Recusa("configuracoes.perfil.erro.longo", campo_id)
    return limpo or None


def _da_lista(valor: str, opcoes: Sequence[str]) -> str | None:
    """Lista fechada: a tela é a fonte, então valor fora é 422 seco; vazio = `None`."""
    if valor == "":
        return None
    if valor not in opcoes:
        raise HTTPException(422)
    return valor


def _mes(valor: str, campo_id: str) -> str | None:
    limpo = valor.strip()
    if limpo and not _MES.fullmatch(limpo):
        raise _Recusa("configuracoes.perfil.erro.mes", campo_id)
    return limpo or None


def _links(valor: str) -> tuple[str, ...]:
    """Um por linha, só http(s) com endereço (nunca `javascript:`), sem repetidos, até 10."""
    lista: list[str] = []
    for linha in valor.splitlines():
        link = _linha(linha)
        if not link or link in lista:
            continue
        try:
            partes = urlsplit(link)
        except ValueError:  # "http://[abc", endereço que muda com NFKC: recusa, nunca 500
            raise _Recusa("configuracoes.perfil.erro.links", "perfil-links") from None
        if partes.scheme not in ("http", "https") or not partes.netloc or len(link) > _TETO["link"]:
            raise _Recusa("configuracoes.perfil.erro.links", "perfil-links")
        lista.append(link)
    if len(lista) > TETO_LINKS:
        raise _Recusa("configuracoes.perfil.erro.links", "perfil-links")
    return tuple(lista)


def _anos(valor: str) -> int | None:
    limpo = valor.strip()
    if not limpo:
        return None
    if not limpo.isascii() or not limpo.isdigit() or int(limpo) > 60:
        raise _Recusa("configuracoes.perfil.erro.anos", "perfil-anos")
    return int(limpo)


def _idiomas(form: FormData) -> tuple[tuple[str, str], ...]:
    """Os três fixos pelo código e os outros pelo nome digitado, cada um com o nível. Nome igual
    a um código fixo sai (o fixo tem a sua lista); mais de `TETO_OUTROS`, recusa."""
    pares = [(c, n) for c in IDIOMAS_FIXOS if (n := _da_lista(_bruto(form, "idioma_" + c), NIVEIS))]
    nomes, niveis = form.getlist("outro_nome"), form.getlist("outro_nivel")
    if (
        len(nomes) != len(niveis)
        or len(nomes) > TETO_OUTROS + 1  # a tela nunca manda mais linhas que isso
        or not all(isinstance(v, str) for v in (*nomes, *niveis))
    ):
        raise HTTPException(422)
    vistos = set(IDIOMAS_FIXOS)
    for posicao, (bruto, nivel_bruto) in enumerate(zip(nomes, niveis, strict=True), start=1):
        campo_id = f"perfil-outro-{posicao}"
        nome = _texto(str(bruto), campo_id, _TETO["idioma"])
        nivel = _da_lista(str(nivel_bruto), NIVEIS)
        if nome is None:
            continue
        if nivel is None:
            raise _Recusa("configuracoes.perfil.erro.nivel", campo_id + "-nivel")
        if normalizar(nome) not in vistos:
            vistos.add(normalizar(nome))
            pares.append((nome, nivel))
            if len(vistos) > len(IDIOMAS_FIXOS) + TETO_OUTROS:
                raise _Recusa("configuracoes.perfil.erro.outros", campo_id)
    return tuple(pares)


def _comuns(form: FormData) -> dict[str, Any]:
    """Os campos que "Sobre você" e o questionário têm em comum, já conferidos."""
    valores = {c: _bruto(form, c) for c in _IDS_DADOS if c != "resumo"}
    email = _texto(valores["email"], "perfil-email", _TETO["email"])
    if email is not None and not _EMAIL.fullmatch(email):
        raise _Recusa("configuracoes.perfil.erro.email", "perfil-email")
    return {
        "nome": _texto(valores["nome"], "perfil-nome"),
        "email": email,
        "telefone": _texto(valores["telefone"], "perfil-telefone", _TETO["telefone"]),
        "cidade_moradia": _texto(valores["cidade_moradia"], "perfil-cidade"),
        "cargo_atual": _texto(valores["cargo_atual"], "perfil-cargo"),
        "anos_de_experiencia": _anos(valores["anos_de_experiencia"]),
        "formacao_nivel": _da_lista(valores["formacao_nivel"], FORMACOES),
        "links": _links(valores["links"]),
    }


def dados_do_form(form: FormData) -> perfil.Dados:
    """Os `Dados` do formulário "Sobre você". Campo vazio apaga o valor (D226.1)."""
    comuns = _comuns(form)
    resumo = _bloco(_bruto(form, "resumo"), "perfil-resumo")
    return perfil.Dados(**comuns, resumo=resumo, idiomas_falados=_idiomas(form))


def _dados_na_tela(dados: perfil.Dados) -> dict[str, Any]:
    """Os dados gravados como a tela os mostra: textos, os três idiomas fixos e os outros."""
    fixos = {c: n for c, n in dados.idiomas_falados if c in IDIOMAS_FIXOS}
    outros = [(c, n) for c, n in dados.idiomas_falados if c not in IDIOMAS_FIXOS]
    return {
        **{c: "" for c in _IDS_DADOS},
        **{c: str(v) for c in _IDS_DADOS if (v := getattr(dados, c, None)) is not None},
        "links": "\n".join(dados.links),
        "idiomas": {c: fixos.get(c, "") for c in IDIOMAS_FIXOS},
        "outros": outros + ([("", "")] if len(outros) < TETO_OUTROS else []),
    }


def _dados_digitados(form: FormData) -> dict[str, Any]:
    """O que foi digitado, para a página do erro devolver ao formulário."""
    texto = {c: str(form.get(c) or "").strip() for c in _IDS_DADOS}
    outros = list(zip(form.getlist("outro_nome"), form.getlist("outro_nivel"), strict=False))
    return texto | {
        "idiomas": {c: str(form.get("idioma_" + c) or "") for c in IDIOMAS_FIXOS},
        "outros": [(str(n).strip(), str(v)) for n, v in outros] or [("", "")],
    }


def _id_do_item(form: FormData) -> int | None:
    bruto = _bruto(form, "id")
    if bruto == "":
        return None
    if not _ID.fullmatch(bruto):
        raise HTTPException(422)
    return int(bruto)


def _experiencia(form: FormData, id_: int | None, prefixo: str) -> perfil.Experiencia:
    cargo = _texto(_bruto(form, "cargo"), prefixo + "-cargo")
    if cargo is None:
        raise _Recusa("configuracoes.perfil.erro.cargo", prefixo + "-cargo")
    inicio = _mes(_bruto(form, "inicio"), prefixo + "-inicio")
    fim = _mes(_bruto(form, "fim"), prefixo + "-fim")
    if inicio and fim and inicio > fim:
        raise _Recusa("configuracoes.perfil.erro.mes", prefixo + "-fim")
    return perfil.Experiencia(
        cargo,
        _texto(_bruto(form, "empresa"), prefixo + "-empresa"),
        inicio,
        fim,
        _bloco(_bruto(form, "descricao"), prefixo + "-descricao"),
        id_,
    )


def _curso(form: FormData, id_: int | None, prefixo: str) -> perfil.Curso:
    nome = _texto(_bruto(form, "nome"), prefixo + "-nome")
    if nome is None:
        raise _Recusa("configuracoes.perfil.erro.curso", prefixo + "-nome")
    return perfil.Curso(
        nome,
        _texto(_bruto(form, "instituicao"), prefixo + "-instituicao"),
        _da_lista(_bruto(form, "situacao"), SITUACOES),  # type: ignore[arg-type]
        _mes(_bruto(form, "previsao"), prefixo + "-previsao"),
        id_,
    )


def _gravar_item(con: sqlite3.Connection, secao: str, form: FormData) -> None:
    """Nova, editada ou tirada (o botão `tirar`). Editar a que já saiu: 404, não a traz de volta.
    O item que saiu e o teto vêm antes da conferência dos campos (duas abas abertas)."""
    id_ = _id_do_item(form)
    experiencia = secao == "experiencia"
    if "tirar" in form:
        if id_ is None:
            raise HTTPException(422)
        (perfil.apagar_experiencia if experiencia else perfil.apagar_curso)(con, id_)
        return
    prefixo = f"{_PREFIXO[secao]}-{id_ if id_ is not None else 'nova'}"
    ids = [i.id for i in (perfil.experiencias(con) if experiencia else perfil.cursos(con))]
    if id_ is not None and id_ not in ids:
        raise HTTPException(404)
    if id_ is None and len(ids) >= TETO_ITENS:
        raise _Recusa("configuracoes.perfil.erro.itens", prefixo + "-" + _CAMPOS_ITEM[secao][0])
    if experiencia:
        exp = _experiencia(form, id_, prefixo)
    else:
        curso = _curso(form, id_, prefixo)
    gravado = (
        perfil.gravar_experiencia(con, exp) if experiencia else perfil.gravar_curso(con, curso)
    )
    if gravado is None:
        raise HTTPException(404)


async def gravar_perfil(
    request: Request, con: sqlite3.Connection, form: FormData
) -> str | tuple[int, dict[str, Any]]:
    """Grava a seção de `form`; devolve o endereço do 303 ou o status e o contexto do erro."""
    secao = form.get("secao")
    try:
        if secao is None:
            texto = _bruto(form, "habilidades")
            try:
                lista = habilidades_do_texto(texto)
            except ValueError:  # a página volta com o que foi digitado, e nada é gravado
                return 422, {
                    "habilidades_texto": texto,
                    "erro": "configuracoes.perfil.erro.grande",
                    "erro_campo": "campo-habilidades",
                }
            salvar_habilidades(request, con, lista)
        elif secao == "dados":
            perfil.gravar_dados(con, dados_do_form(form), relogio_do_painel(request).agora())
        elif secao in _CAMPOS_ITEM:
            _gravar_item(con, str(secao), form)
        else:
            raise HTTPException(422)
    except _Recusa as recusa:
        contexto: dict[str, Any] = {"erro": recusa.chave, "erro_campo": recusa.campo_id}
        if secao == "dados":
            return 422, contexto | {"dados_tela": _dados_digitados(form)}
        prefixo = recusa.campo_id.rsplit("-", 1)[0]
        digitado = {c: str(form.get(c) or "").strip() for c in _CAMPOS_ITEM[str(secao)]}
        return 422, contexto | {"erro_item": prefixo, "item_digitado": digitado}
    ancora = _ANCORA[None if secao is None else str(secao)]  # volta à seção, não ao alto (D230.1)
    return f"{PERFIL}?salvo=1#perfil-{ancora}"


def _item_na_tela(item: perfil.Experiencia | perfil.Curso) -> dict[str, str]:
    return {k: "" if v is None else str(v) for k, v in vars(item).items()}


async def contexto_perfil(request: Request, con: Con) -> dict[str, Any]:
    atuais = perfil.habilidades(con)
    return {
        "habilidades_texto": "\n".join(atuais),
        "tem_perfil": perfil.existe(con),
        "privacidade": _privacidade(con),
        "privacidade_perguntas": _privacidade_perguntas(con),
        "apagado": request.query_params.get("apagado") == "1",
        "dados_tela": _dados_na_tela(perfil.dados(con)),
        "experiencias": [_item_na_tela(e) for e in perfil.experiencias(con)],
        "cursos": [_item_na_tela(c) for c in perfil.cursos(con)],
        "formacoes": FORMACOES,
        "situacoes": SITUACOES,
        "idiomas_fixos": IDIOMAS_FIXOS,
        "niveis": NIVEIS,
        "teto_itens": TETO_ITENS,
        "teto": _TETO,
        "erro_campo": None,
        "erro_item": None,
        "item_digitado": None,
    }


@router.get("/apagar/confirmar")
async def apagar_pergunta(request: Request) -> Response:
    """Sem JavaScript: a pergunta do alerta numa página; o GET não apaga nada (T307)."""
    return renderizar(
        request,
        "confirmar.html",
        titulo=("configuracoes.perfil.apagar.pergunta", {}),
        texto="configuracoes.perfil.apagar.explicacao",
        rotulo="comum.apagar",
        acao=PERFIL + "/apagar",
        voltar=PERFIL,
    )


@router.post("/apagar")
async def apagar(request: Request, con: Con) -> Response:
    """Apaga a linha do perfil; `habilidades_vaga` fica (desenho 8). Recalcula antes, sem nada."""
    _recalcular(request, con, [])
    perfil.apagar_perfil(con)
    return RedirectResponse(PERFIL + "?apagado=1", 303)


# --- o currículo em PDF (T435; D231) ----------------------------------------------------------

_CURRICULO = "configuracoes/_curriculo.html"


def extrair_curriculo(lido: pdf.Lido) -> None:
    """Onde o texto lido entra na extração dos campos (tarefa `curriculo`, T436). O texto só vive
    neste pedido: nada aqui o guarda."""


def _aviso(request: Request, chave: str, status: int = 200) -> Response:
    resposta = renderizar(request, _CURRICULO, aviso="configuracoes.perfil.curriculo." + chave)
    resposta.status_code = status
    return resposta


@router.post("/curriculo")
async def ler_curriculo(request: Request) -> Response:
    """Lê o PDF enviado. O token CSRF veio no cabeçalho (`exigir_csrf` não lê o corpo de um
    upload); o tamanho se confere pelo `Content-Length` antes de ler o corpo, e o temporário do
    Starlette (acima de 1 MB vai ao disco) fecha ao sair do `async with`."""
    tamanho = request.headers.get("content-length", "")
    # chunked manda sobre o Content-Length (o h11 aceita os dois): o tamanho declarado não vale
    if "transfer-encoding" in request.headers or not (tamanho.isascii() and tamanho.isdigit()):
        return _aviso(request, "sem_tamanho", 411)
    if int(tamanho) > pdf.TETO_BYTES:
        return _aviso(request, "grande", 413)
    async with request.form(max_files=1, max_fields=0) as form:
        arquivo = form.get("curriculo")
        if not isinstance(arquivo, UploadFile):
            raise HTTPException(422)
        dados = await arquivo.read()
    try:
        lido = await run_in_threadpool(pdf.ler, dados)
    except pdf.AvisoPdf as aviso:
        return _aviso(request, "aviso." + aviso.aviso)
    extrair_curriculo(lido)
    return renderizar(request, _CURRICULO, lido=lido)


# --- questionário e perguntas de lacuna (T437; desenho 8; D233) -------------------------------

PERGUNTAS = PERFIL + "/perguntas"
# As perguntas só se acumulam (D233.5): no teto a IA não pede mais, e a página mostra só até ele
# (as das candidaturas, T438, podem passar), então o POST nunca manda mais pares que isto.
TETO_PERGUNTAS = 100
TETO_RESPOSTAS = TETO_PERGUNTAS  # pares pergunta/resposta que a tela manda num POST
# por cima do prazo do pedido: no local, a subida do `llama-server` (como o teste ao ligar,
# `ia.FOLGA_TESTE_S`); fora, só a leitura do cofre. Passou disso, `tempo_esgotado`
FOLGA_IA_S = {"local": 150.0, "fora": 10.0}


def _base_na_tela(idioma: str) -> list[dict[str, str | None]]:
    return [
        {"id": p["id"], "campo": p.get("campo"), "onde": p.get("onde"), "texto": p.get(idioma)}
        for p in perguntas_base()
    ]


def _feitas(perguntas: Sequence[perfil.PerguntaPerfil]) -> list[str]:
    """As perguntas que a IA não deve repetir: as base, nos dois idiomas, e as já gravadas."""
    return [p[i] for p in perguntas_base() for i in ("pt", "en")] + [p.pergunta for p in perguntas]


def _perguntas_na_tela(
    perguntas: Sequence[perfil.PerguntaPerfil], digitadas: dict[str, str] | None = None
) -> list[dict[str, str]]:
    return [
        {
            "chave": p.chave,
            "pergunta": p.pergunta,
            "por_que": p.por_que or "",
            "resposta": (digitadas or {}).get(p.chave, p.resposta or ""),
        }
        for p in perguntas
    ]


async def contexto_perguntas(request: Request, con: Con) -> dict[str, Any]:
    tarefa = tarefa_ia(con, "perguntas")
    sugeridas = request.query_params.get("sugeridas", "")
    return {
        "perguntas_base": _base_na_tela(idioma_do_pedido(request)),
        "dados_tela": _dados_na_tela(perfil.dados(con)),
        "habilidades_texto": "\n".join(perfil.habilidades(con)),
        "perguntas_ia": _perguntas_na_tela(perfil.perguntas(con)[:TETO_PERGUNTAS]),
        "perguntas_ligada": tarefa.ligada,
        "teto_perguntas": TETO_PERGUNTAS,
        "em_curso": request.query_params.get("em_curso") == "1",
        "perguntas_privacidade": frase_de_privacidade(
            tarefa, "configuracoes.perfil.perguntas.privacidade."
        ),
        "perguntas_falha": None,
        # só um número de 0 a 5 vai à página; o resto da URL não
        "sugeridas": int(sugeridas) if sugeridas in ("0", "1", "2", "3", "4", "5") else None,
        "formacoes": FORMACOES,
        "niveis": NIVEIS,
        "idiomas_fixos": IDIOMAS_FIXOS,
        "teto": _TETO,
        "erro_campo": None,
    }


def _respostas(form: FormData) -> list[tuple[str, str | None]]:
    """Os pares (chave, resposta) das perguntas; resposta vazia = `None` (apaga)."""
    chaves, textos = form.getlist("pergunta_chave"), form.getlist("pergunta_resposta")
    if (
        len(chaves) != len(textos)
        or len(chaves) > TETO_RESPOSTAS
        or not all(isinstance(v, str) for v in (*chaves, *textos))
    ):
        raise HTTPException(422)
    return [
        (str(c), _bloco(str(t), f"pergunta-{n}"))
        for n, (c, t) in enumerate(zip(chaves, textos, strict=True), start=1)
    ]


def _dados_das_perguntas(form: FormData, atuais: perfil.Dados) -> perfil.Dados:
    """Os campos do questionário por cima dos gravados: o resumo e os outros idiomas ficam."""
    fixos = [(c, n) for c in IDIOMAS_FIXOS if (n := _da_lista(_bruto(form, "idioma_" + c), NIVEIS))]
    outros = [par for par in atuais.idiomas_falados if par[0] not in IDIOMAS_FIXOS]
    return replace(atuais, **_comuns(form), idiomas_falados=tuple(fixos + outros))


async def gravar_perguntas(
    request: Request, con: sqlite3.Connection, form: FormData
) -> str | tuple[int, dict[str, Any]]:
    """Grava as respostas do questionário (perfil, habilidades e perguntas) e, com `sugerir`,
    pede as perguntas de lacuna. Devolve o endereço do 303 ou o status e o contexto da página.
    Tudo é conferido antes de gravar: com um campo errado, nada muda."""
    try:
        novos = _dados_das_perguntas(form, perfil.dados(con))
        try:
            lista = habilidades_do_texto(_bruto(form, "habilidades"))
        except ValueError:
            raise _Recusa("configuracoes.perfil.erro.grande", "campo-habilidades") from None
        respostas = _respostas(form)
    except _Recusa as recusa:
        chaves, textos = form.getlist("pergunta_chave"), form.getlist("pergunta_resposta")
        digitadas = dict(zip(chaves, textos, strict=False))  # a tela manda em pares
        return 422, {
            "erro": recusa.chave,
            "erro_campo": recusa.campo_id,
            "dados_tela": _dados_digitados(form),
            "habilidades_texto": str(form.get("habilidades") or ""),
            "perguntas_ia": _perguntas_na_tela(
                perfil.perguntas(con)[:TETO_PERGUNTAS],
                {str(c): str(t) for c, t in digitadas.items()},
            ),
        }
    agora = relogio_do_painel(request).agora()
    salvar_habilidades(request, con, lista)
    perfil.gravar_dados(con, novos, agora)
    guardadas = {p.chave: p.resposta for p in perfil.perguntas(con)}
    for chave, resposta in respostas:
        if chave in guardadas and guardadas[chave] != resposta:
            perfil.responder_pergunta(con, chave, resposta, agora)
    if "sugerir" not in form:
        return PERGUNTAS + "?salvo=1#perguntas-ia"
    return await _sugerir(request, con)


def _trava_perguntas(request: Request) -> asyncio.Lock:
    estado = request.app.state
    if getattr(estado, "ia_trava_perguntas", None) is None:
        estado.ia_trava_perguntas = asyncio.Lock()
    trava: asyncio.Lock = estado.ia_trava_perguntas
    return trava


def chave_da_falha(motivo: Motivo, backend: str) -> str:
    """O texto do motivo, com o da Anthropic à parte (D192.3), como no teste ao ligar."""
    especial = motivo == "chave_recusada" and backend == "anthropic"
    return "configuracoes.ia.falha." + motivo + (".anthropic" if especial else "")


async def _sugerir(request: Request, con: sqlite3.Connection) -> str | tuple[int, dict[str, Any]]:
    tarefa = tarefa_ia(con, "perguntas")
    if not tarefa.ligada:  # desligada noutra aba depois de a página abrir
        return 200, {"perguntas_falha": "configuracoes.perfil.perguntas.desligada"}
    if len(perfil.perguntas(con)) >= TETO_PERGUNTAS:  # D233.5: sem "Tirar", o teto para o pedido
        return 200, {"perguntas_falha": "configuracoes.perfil.perguntas.cheio"}
    trava = _trava_perguntas(request)
    if trava.locked():  # clique duplo: as respostas já gravaram; as sugestões chegam com o 1º
        return PERGUNTAS + "?em_curso=1#perguntas-ia"
    async with trava:  # livre: não suspende, então a checagem acima vale
        perguntas = perfil.perguntas(con)
        fontes = asdict(perfil.dados(con)) | {
            "habilidades": perfil.habilidades(con),
            "experiencias": perfil.experiencias(con),
            "cursos": perfil.cursos(con),
            "respostas": [p for p in perguntas if p.resposta],  # só as respondidas (D227.6)
            "perguntas_feitas": _feitas(perguntas),
        }
        idioma = idioma_do_pedido(request)
        pedido = pedido_perguntas(fontes, idioma, tarefa.backend, tarefa.modelo)
        try:
            resposta = await pedir_ia(request, tarefa, pedido)
        except Falha as falha:
            return 200, {"perguntas_falha": chave_da_falha(falha.motivo, tarefa.backend)}
        ficam = perguntas_que_ficam(resposta.dados["perguntas"], _feitas(perguntas))
        ficam = ficam[: max(TETO_PERGUNTAS - len(perguntas), 0)]
        agora = relogio_do_painel(request).agora()
        for p in ficam:
            chave = "ia:" + normalizar(p["pergunta"])
            perfil.gravar_pergunta(
                con, chave, p["pergunta"], "ia", agora, por_que=p["por_que"] or None
            )
    return f"{PERGUNTAS}?sugeridas={len(ficam)}#perguntas-ia"


async def pedir_ia(request: Request, tarefa: TarefaIA, pedido: Pedido) -> Resposta:
    """Uma chamada à IA sob pedido, fora do laço: o backend da fábrica do `serve`
    (`app.state.ia`) numa thread, com prazo. Erro fora do contrato vai ao log e vira
    `servico_fora`; o log só leva tarefa, backend, modelo, duração e motivo (desenho 5.3)."""
    obter: Obter | None = getattr(request.app.state, "ia", None)
    relogio = relogio_do_painel(request)
    inicio = relogio.agora()
    motivo = "ok"
    futuro: asyncio.Future[Resposta] | None = None
    try:
        if obter is None:  # o app sem o `serve` não tem a fábrica
            raise Falha("servico_fora")
        futuro = asyncio.ensure_future(_pedir(obter, tarefa, pedido))
        folga = FOLGA_IA_S["local" if tarefa.backend == "local" else "fora"]
        feitas, _ = await asyncio.wait({futuro}, timeout=pedido.prazo_s + folga)
        if not feitas:  # a thread presa segue até o próprio prazo; a página não espera
            raise Falha("tempo_esgotado")
        return futuro.result()
    except Falha as falha:
        motivo = falha.motivo
        raise
    except Exception:
        motivo = "servico_fora"
        log.exception("ia %s %s: erro fora do contrato", pedido.tarefa, tarefa.backend)
        raise Falha("servico_fora") from None
    finally:
        if futuro is not None:
            futuro.cancel()  # terminado, não faz nada; senão fecha o cliente (o `finally` dele)
        segundos = (relogio.agora() - inicio).total_seconds()
        log.info(
            "ia %s %s %s: %s em %.1f s",
            pedido.tarefa,
            tarefa.backend,
            tarefa.modelo,
            motivo,
            segundos,
        )


async def _pedir(obter: Obter, tarefa: TarefaIA, pedido: Pedido) -> Resposta:
    criando = asyncio.ensure_future(asyncio.to_thread(obter, tarefa.backend, tarefa.modelo))
    try:
        backend = await asyncio.shield(criando)
    except asyncio.CancelledError:  # o prazo venceu na criação: fecha o backend quando ela acabar
        criando.add_done_callback(_fechar_ao_criar)
        raise
    try:
        return await asyncio.to_thread(backend.pedir, pedido)
    finally:
        backend.fechar()


def _fechar_ao_criar(criando: asyncio.Future[Any]) -> None:
    if not criando.cancelled() and criando.exception() is None:
        criando.result().fechar()
