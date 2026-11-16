"""Detalhe da vaga e correção (desenho 13.5; plano T46).

A descrição vai ao template como texto: o Jinja escapa, nada de HTML da fonte chega ao navegador.
A correção é um `<form>` de verdade (sem JavaScript volta por 303). A rota guarda a correção e já
refaz a vaga (`reprocessar_vaga`) e o encaixe (`recalcular_encaixe`), sempre com o dia local do
`Relogio` como `hoje` (DP8), para a tela mostrar o valor novo na hora (D11). Valor que a pessoa
digita e não vale (estado, salário, texto) volta ao formulário com a mensagem e 422; valor que a
tela não oferece é 422 seco; vaga que não existe é 404 (D12).
"""

import re
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import FormData

from jobot.banco import acoes, leitura
from jobot.banco.buscas import recalcular_encaixe
from jobot.banco.cadastros import ler_config
from jobot.banco.gravacao import reprocessar_vaga
from jobot.banco.leitura import Detalhe
from jobot.nucleo.modelo import Area, Contrato, Modalidade, Nivel
from jobot.nucleo.tratamento.salario import ler_salario
from jobot.painel.consultas import (
    MAX_ID,
    busca_efetiva,
    inteiro_da_url,
    relogio_do_painel,
)
from jobot.painel.detalhe_vaga import contexto_do_detalhe
from jobot.painel.formulario import campo_unico
from jobot.painel.rotas.vagas import VagaId, com_vary
from jobot.painel.seguranca import Con, renderizar

router = APIRouter()

# valor que a tela oferece, por campo de lista; "fechada" tem só sim e não
_LISTAS: dict[str, tuple[str, ...]] = {
    "area": tuple(Area),
    "nivel": tuple(Nivel),
    "modalidade": tuple(Modalidade),
    "contrato": tuple(Contrato),
    "fechada": ("sim", "nao"),
}
CAMPOS = ("area", "nivel", "modalidade", "contrato", "uf", "salario", "fechada", "outro")
_MAX_TEXTO = 500
_UF = re.compile(r"[A-Za-z]{2}")


class _Invalido(Exception):
    """Valor digitado que a pessoa pode consertar: chave de i18n da mensagem e parâmetros."""

    def __init__(self, chave: str, **params: object) -> None:
        super().__init__(chave)
        self.chave = chave
        self.params = params


def _limpo(texto: str) -> str:
    """Sem caractere de controle (a quebra de linha fica) e sem espaço nas pontas."""
    return "".join(c for c in texto if c.isprintable() or c == "\n").strip()


def _vaga_ou_404(request: Request, con: Con, vaga_id: int, pedida: int | None = None) -> Detalhe:
    agora = relogio_do_painel(request).agora()
    vaga = leitura.detalhe(con, vaga_id, busca_efetiva(con, pedida), agora)
    if vaga is None:
        raise HTTPException(404, "vaga não existe")
    return vaga


def _contexto(
    request: Request, con: sqlite3.Connection, vaga: Detalhe, busca_url: int | None
) -> dict[str, Any]:
    hoje = relogio_do_painel(request).agora().astimezone().date()
    retorno = f"/vagas/{vaga.id}" + (f"?busca={busca_url}" if busca_url else "")
    return contexto_do_detalhe(con, vaga, hoje, retorno)


@router.get("/vagas/{vaga_id}")
async def detalhe(request: Request, con: Con, vaga_id: VagaId) -> HTMLResponse:
    busca_url = inteiro_da_url(request.query_params.get("busca"), MAX_ID)
    vaga = _vaga_ou_404(request, con, vaga_id, busca_url)
    return renderizar(request, "detalhe/pagina.html", **_contexto(request, con, vaga, busca_url))


def _atual(vaga: Detalhe) -> dict[str, str]:
    """O valor de hoje de cada campo de lista: o formulário abre com ele selecionado."""
    atual = {c: getattr(vaga, c) or "" for c in ("area", "nivel", "modalidade", "contrato")}
    return atual | {"fechada": "sim" if vaga.fechada else "nao"}


def _formulario(
    request: Request, vaga: Detalhe, form: FormData | None = None, erro: _Invalido | None = None
) -> HTMLResponse:
    """O formulário; com `form`, devolve o que a pessoa digitou (campo, valores e comentário)."""
    f: dict[str, Any] = {"campo": "", "comentario": "", "valores": {}}
    if form is not None:
        f = {
            "campo": campo_unico(form, "campo"),
            "comentario": campo_unico(form, "comentario"),
            "valores": {c: campo_unico(form, f"valor_{c}") for c in CAMPOS},
        }
    # com HTMX (o link do detalhe) volta só o sheet; sem ele, a página de sempre, que também
    # recebe o 422 do POST e quem não tem JavaScript. Voltar no navegador (restauração do
    # histórico) também pede a página inteira, como a lista de vagas
    cabecalho = request.headers
    restaurando = cabecalho.get("hx-history-restore-request") == "true"
    sheet = form is None and cabecalho.get("hx-request") == "true" and not restaurando
    resposta = renderizar(
        request,
        "detalhe/correcao_sheet.html" if sheet else "detalhe/correcao.html",
        vaga=vaga,
        campos=CAMPOS,
        listas=_LISTAS,
        atual=_atual(vaga),
        f=f,
        erro=erro,
    )
    return com_vary(resposta)  # o mesmo endereço tem duas respostas: o cache precisa saber


@router.get("/vagas/{vaga_id}/correcao")
async def formulario(request: Request, con: Con, vaga_id: VagaId) -> HTMLResponse:
    return _formulario(request, _vaga_ou_404(request, con, vaga_id))


def _salario_legivel(con: sqlite3.Connection, vaga_id: int, texto: str) -> bool:
    """Lê o salário como o reprocessamento lê (D11): o texto sozinho, com a moeda, com o idioma."""
    moeda, idioma = con.execute(
        "SELECT sal_moeda, idioma FROM vaga WHERE id = ?", (vaga_id,)
    ).fetchone()
    tentativas = [(texto, "outro"), (texto, idioma)]
    if moeda is not None:
        tentativas.insert(1, (f"{moeda} {texto}", "outro"))
    return any(ler_salario(t, None, i) is not None for t, i in tentativas)


def _validar(con: sqlite3.Connection, vaga_id: int, campo: str, valor: str) -> str:
    """O valor a guardar. Fora do que a tela oferece é 422 seco; texto ruim volta ao formulário."""
    if campo in _LISTAS:
        if valor not in _LISTAS[campo]:
            raise HTTPException(422, f"valor fora da lista: {campo}")
        return valor
    if len(valor) > _MAX_TEXTO:
        raise _Invalido("detalhe.correcao.erro.longo", max=_MAX_TEXTO)
    if campo == "uf" and not _UF.fullmatch(valor):
        raise _Invalido("detalhe.correcao.erro.uf")
    if campo == "uf":
        return valor.upper()
    if campo == "salario" and valor and not _salario_legivel(con, vaga_id, valor):
        raise _Invalido("detalhe.correcao.erro.salario")
    if campo == "outro" and not valor:
        raise _Invalido("detalhe.correcao.erro.outro")
    return valor


@router.post("/vagas/{vaga_id}/correcao")
async def corrigir(request: Request, con: Con, vaga_id: VagaId) -> Response:
    vaga = _vaga_ou_404(request, con, vaga_id)
    form = await request.form()
    campo = campo_unico(form, "campo")
    if campo not in CAMPOS:
        raise HTTPException(422, "campo que não se corrige")
    comentario = _limpo(campo_unico(form, "comentario"))
    try:
        valor = _validar(con, vaga_id, campo, _limpo(campo_unico(form, f"valor_{campo}")))
        if len(comentario) > _MAX_TEXTO:
            raise _Invalido("detalhe.correcao.erro.comentario", max=_MAX_TEXTO)
    except _Invalido as erro:
        pagina = _formulario(request, vaga, form, erro)
        pagina.status_code = 422
        return pagina
    agora = relogio_do_painel(request).agora()
    hoje = agora.astimezone().date()
    try:
        try:
            acoes.corrigir(con, vaga_id, campo, valor, comentario or None, agora)
        except ValueError as erro:  # só a gravação: depois dela a correção já está guardada
            raise HTTPException(422, str(erro)) from erro
        reprocessar_vaga(con, vaga_id, hoje=hoje)
        regras = bool(ler_config(con, "regras_ocultar_ligadas"))
        recalcular_encaixe(con, None, regras, hoje=hoje, vaga_id=vaga_id)
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return RedirectResponse(f"/vagas/{vaga_id}", status_code=303)
