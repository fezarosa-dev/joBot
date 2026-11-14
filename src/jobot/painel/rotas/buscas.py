"""Buscas salvas: lista, criar, editar, ligar, desligar e apagar (desenho 11.1 e 13.2; plano T52).

O formulário traz os campos do passo 1 da primeira execução (13.6) e as regras de ocultar (11.3).
Valor que a pessoa digita errado (nome, salário, cidade) volta ao formulário com a mensagem e
status 422; valor que a tela não oferece (modalidade, moeda ou regra inventadas) é 422 seco; busca
que não existe é 404 (D12). O salário vai ao banco em centavos inteiros, nunca em float.
Toda chamada de `criar_busca` e `editar_busca` leva o dia local do `Relogio` como `hoje` (DP8).
"""

import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import FormData

from jobot.banco.buscas import apagar_busca, buscas, criar_busca, editar_busca
from jobot.banco.cadastros import ler_config
from jobot.nucleo.cambio import MOEDAS
from jobot.nucleo.modelo import Busca, Idioma, Local, Modalidade, Nivel
from jobot.nucleo.tratamento.locais import ler_locais
from jobot.painel.formulario import campo_unico
from jobot.painel.rotas.vagas import relogio_do_painel
from jobot.painel.seguranca import Con, renderizar

router = APIRouter(prefix="/buscas")

BuscaId = Annotated[int, Path(ge=1, le=2**63 - 1)]  # o INTEGER do SQLite tem 64 bits com sinal
REGRAS = ("modalidade", "nivel", "salario", "idioma", "pais")  # ids de `nucleo/encaixe.py`
MODALIDADES = tuple(m for m in Modalidade if m != Modalidade.NAO_INFORMADO)
NIVEIS = tuple(n for n in Nivel if n != Nivel.NAO_INFORMADO)
IDIOMAS: tuple[Idioma, ...] = ("pt", "en", "es")
MOEDAS_DO_FORMULARIO = ("BRL", *MOEDAS)
# país -> nome que `ler_locais` entende (o formulário mostra e relê o texto da pessoa)
NOME_PAIS = {
    "PT": "Portugal",
    "US": "USA",
    "GB": "United Kingdom",
    "CA": "Canada",
    "DE": "Germany",
    "ES": "Spain",
    "FR": "France",
    "IT": "Italy",
    "NL": "Netherlands",
    "IE": "Ireland",
    "AR": "Argentina",
    "CL": "Chile",
    "CO": "Colombia",
    "MX": "Mexico",
    "UY": "Uruguay",
    "PE": "Peru",
    "IN": "India",
}
_MAX_NOME = 100
_MAX_CARGOS = 50
_MAX_CIDADES = 20
_MAX_SALARIO = 25  # letras do texto: corta antes de qualquer `int()` de número enorme
# milhar com ponto e centavos com vírgula; `[0-9]` e não `\d`, que aceita dígito de outro alfabeto
_SALARIO = re.compile(r"([0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)(?:,([0-9]{1,2}))?")


@dataclass(frozen=True)
class Formulario:
    """O que a pessoa digitou ou escolheu, como texto: volta igual ao formulário num erro."""

    nome: str = ""
    cargos: str = ""
    cidades: str = ""
    modalidade: tuple[str, ...] = ()
    nivel: tuple[str, ...] = ()
    salario: str = ""
    moeda: str = "BRL"
    idioma: tuple[str, ...] = ()
    regra: tuple[str, ...] = REGRAS  # busca nova começa com todas as regras ligadas


class _Invalido(Exception):
    """Valor digitado que a pessoa pode consertar: chave de i18n da mensagem e parâmetros."""

    def __init__(self, chave: str, **params: str) -> None:
        super().__init__(chave)
        self.chave = chave
        self.params = params


def _texto_local(local: Local) -> str:
    partes = [p for p in (local.cidade, local.uf) if p]
    if local.pais and (local.pais != "BR" or not partes):
        partes.append(NOME_PAIS.get(local.pais, "Brasil" if local.pais == "BR" else local.pais))
    return ", ".join(partes)


def _texto_centavos(centavos: int | None) -> str:
    if centavos is None:
        return ""
    inteiro, resto = divmod(centavos, 100)
    return f"{inteiro},{resto:02d}" if resto else str(inteiro)


def _formulario_de(b: Busca) -> Formulario:
    return Formulario(
        nome=b.nome,
        cargos="\n".join(b.cargos),
        cidades="\n".join(_texto_local(c) for c in b.cidades),
        modalidade=tuple(m.value for m in b.modalidades),
        nivel=tuple(n.value for n in b.niveis),
        salario=_texto_centavos(b.salario_min_centavos),
        moeda=b.salario_moeda or "BRL",
        idioma=tuple(b.idiomas),
        regra=tuple(r for r in REGRAS if b.regras_ocultar.get(r, True)),
    )


def _varios(form: FormData, campo: str) -> tuple[str, ...]:
    return tuple(v for v in form.getlist(campo) if isinstance(v, str))


async def _ler(request: Request) -> Formulario:
    form = await request.form()
    return Formulario(
        nome=campo_unico(form, "nome"),
        cargos=campo_unico(form, "cargos"),
        cidades=campo_unico(form, "cidades"),
        modalidade=_varios(form, "modalidade"),
        nivel=_varios(form, "nivel"),
        salario=campo_unico(form, "salario"),
        moeda=campo_unico(form, "moeda"),
        idioma=_varios(form, "idioma"),
        regra=_varios(form, "regra"),
    )


def _escolhidas[T: str](escolhidos: Sequence[str], oferecidas: Sequence[T]) -> tuple[T, ...]:
    """Os valores escolhidos, na ordem da tela; algum que a tela não oferece é 422 seco."""
    if not set(escolhidos) <= set(oferecidas):
        raise HTTPException(422, "valor que a tela não oferece")
    return tuple(o for o in oferecidas if o in escolhidos)


def _centavos(texto: str) -> int | None:
    texto = texto.strip()
    if not texto:
        return None
    achado = _SALARIO.fullmatch(texto) if len(texto) <= _MAX_SALARIO else None
    if achado is None:
        raise _Invalido("buscas.erro.salario")
    inteiro, centavos = achado.groups()
    return int(inteiro.replace(".", "")) * 100 + int((centavos or "").ljust(2, "0"))


def _cidades(texto: str) -> tuple[Local, ...]:
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    if len(linhas) > _MAX_CIDADES:
        raise _Invalido("buscas.erro.cidades_n")
    locais: list[Local] = []
    for linha in linhas:
        lidos = ler_locais([linha])
        if not lidos or lidos == (Local(),):
            raise _Invalido("buscas.erro.cidade", linha=linha)
        locais += lidos
    return tuple(dict.fromkeys(locais))


def _montar(f: Formulario, *, id: int | None = None, ativa: bool = True) -> Busca:
    nome = f.nome.strip()
    if not nome or len(nome) > _MAX_NOME:
        raise _Invalido("buscas.erro.nome")
    cargos = tuple(dict.fromkeys(c for c in (p.strip() for p in re.split(r"[\n,]", f.cargos)) if c))
    if len(cargos) > _MAX_CARGOS or any(len(c) > _MAX_NOME for c in cargos):
        raise _Invalido("buscas.erro.cargos")
    cidades = _cidades(f.cidades)
    modalidades = _escolhidas(f.modalidade, [m.value for m in MODALIDADES])
    niveis = _escolhidas(f.nivel, [n.value for n in NIVEIS])
    idiomas = _escolhidas(f.idioma, IDIOMAS)
    ligadas = _escolhidas(f.regra, REGRAS)
    if f.moeda not in MOEDAS_DO_FORMULARIO:
        raise HTTPException(422, "valor que a tela não oferece")
    minimo = _centavos(f.salario)
    return Busca(
        id=id,
        nome=nome,
        ativa=ativa,
        cargos=cargos,
        cidades=cidades,
        modalidades=tuple(Modalidade(m) for m in modalidades),
        niveis=tuple(Nivel(n) for n in niveis),
        salario_min_centavos=minimo,
        salario_moeda=None if minimo is None else f.moeda,
        idiomas=idiomas,
        regras_ocultar={r: r in ligadas for r in REGRAS},
    )


def _resumo(b: Busca) -> dict[str, Any]:
    return {
        "busca": b,
        "cidades": [_texto_local(c) for c in b.cidades],
        "desligadas": [r for r in REGRAS if not b.regras_ocultar.get(r, True)],
    }


def _opcoes() -> dict[str, Any]:
    return {
        "modalidades": [m.value for m in MODALIDADES],
        "niveis": [n.value for n in NIVEIS],
        "idiomas": IDIOMAS,
        "moedas": MOEDAS_DO_FORMULARIO,
        "regras": REGRAS,
    }


def _pagina(
    request: Request,
    con: sqlite3.Connection,
    f: Formulario,
    erro: _Invalido | None = None,
    *,
    status: int = 200,
) -> HTMLResponse:
    """A lista com o formulário de busca nova (com o que a pessoa já digitou, se deu erro)."""
    resposta = renderizar(
        request,
        "buscas/lista.html",
        buscas=[_resumo(b) for b in buscas(con)],
        f=f,
        erro=erro,
        acao="/buscas",
        **_opcoes(),
    )
    resposta.status_code = status
    return resposta


def _pagina_de_edicao(
    request: Request, atual: Busca, f: Formulario, erro: _Invalido | None = None, *, status: int
) -> HTMLResponse:
    resposta = renderizar(
        request,
        "buscas/editar.html",
        busca=atual,
        f=f,
        erro=erro,
        acao=f"/buscas/{atual.id}",
        **_opcoes(),
    )
    resposta.status_code = status
    return resposta


def _achar(con: sqlite3.Connection, busca_id: int) -> Busca:
    achada = next((b for b in buscas(con) if b.id == busca_id), None)
    if achada is None:
        raise HTTPException(404, "busca não existe")
    return achada


def _gravar(request: Request, con: sqlite3.Connection, busca: Busca, *, nova: bool) -> None:
    """Cria ou edita; o encaixe da própria busca já sai recalculado com o dia local (DP8)."""
    agora = relogio_do_painel(request).agora()
    hoje = agora.astimezone().date()
    ligadas = bool(ler_config(con, "regras_ocultar_ligadas"))
    if nova:
        criar_busca(con, busca, agora, regras_ligadas=ligadas, hoje=hoje)
    else:
        editar_busca(con, busca, regras_ligadas=ligadas, hoje=hoje)


@router.get("")
async def lista(request: Request, con: Con) -> HTMLResponse:
    return _pagina(request, con, Formulario())


@router.post("")
async def criar(request: Request, con: Con) -> Response:
    f = await _ler(request)
    try:
        _gravar(request, con, _montar(f), nova=True)
    except _Invalido as erro:
        return _pagina(request, con, f, erro, status=422)
    except ValueError:  # o banco recusou o valor (salário fora do alcance)
        return _pagina(request, con, f, _Invalido("buscas.erro.valor"), status=422)
    return RedirectResponse("/buscas", status_code=303)


@router.get("/{busca_id}")
async def editar_formulario(request: Request, con: Con, busca_id: BuscaId) -> HTMLResponse:
    atual = _achar(con, busca_id)
    return _pagina_de_edicao(request, atual, _formulario_de(atual), status=200)


@router.post("/{busca_id}")
async def editar(request: Request, con: Con, busca_id: BuscaId) -> Response:
    atual = _achar(con, busca_id)
    f = await _ler(request)
    try:
        _gravar(request, con, _montar(f, id=busca_id, ativa=atual.ativa), nova=False)
    except _Invalido as erro:
        return _pagina_de_edicao(request, atual, f, erro, status=422)
    except ValueError:
        return _pagina_de_edicao(request, atual, f, _Invalido("buscas.erro.valor"), status=422)
    except LookupError as erro:  # apagada entre a leitura e a gravação
        raise HTTPException(404, "busca não existe") from erro
    return RedirectResponse("/buscas", status_code=303)


async def _ligar(request: Request, con: sqlite3.Connection, busca_id: int, ativa: bool) -> Response:
    atual = _achar(con, busca_id)
    try:
        _gravar(request, con, replace(atual, ativa=ativa), nova=False)
    except ValueError as erro:  # o banco recusa o valor que já estava gravado (moeda sem cotação)
        raise HTTPException(422, "o banco recusou o valor da busca") from erro
    except LookupError as erro:
        raise HTTPException(404, "busca não existe") from erro
    return RedirectResponse("/buscas", status_code=303)


@router.post("/{busca_id}/ligar")
async def ligar(request: Request, con: Con, busca_id: BuscaId) -> Response:
    return await _ligar(request, con, busca_id, True)


@router.post("/{busca_id}/desligar")
async def desligar(request: Request, con: Con, busca_id: BuscaId) -> Response:
    return await _ligar(request, con, busca_id, False)


@router.post("/{busca_id}/apagar")
async def apagar(con: Con, busca_id: BuscaId) -> Response:
    try:
        apagar_busca(con, busca_id)
    except LookupError as erro:
        raise HTTPException(404, "busca não existe") from erro
    return RedirectResponse("/buscas", status_code=303)
