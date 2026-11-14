"""Tela de vagas: abas, filtros, ordem, destaques e ações da vaga (desenho 13.3 a 13.5; plano T45).

Todo parâmetro de URL é lido à mão: link velho ou torto cai no padrão, nunca em 422 (RF2).
Ação que muda dados é um `<form>` de verdade: sem JavaScript volta por 303 (`voltar`), com HTMX
troca só o corpo do cartão.
"""

import json
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import QueryParams

from jobot.banco import acoes, leitura
from jobot.banco.leitura import Filtros, Fonte, Item
from jobot.nucleo.destaques import Candidata, destaques
from jobot.nucleo.relogio import Relogio, RelogioReal
from jobot.painel.seguranca import Con, de_volta, renderizar

router = APIRouter()

ABA_DESTAQUES = "destaques"
CHIPS = ("modalidade", "nivel", "area", "contrato", "uf", "fonte", "encaixe")
_ENCAIXES = ("bom", "medio", "fraco")
# rótulo do valor do chip: grupo -> prefixo da chave de i18n (None: o valor já é o texto)
_ROTULO_CHIP = {
    "modalidade": "modalidade",
    "nivel": "nivel",
    "area": "area",
    "contrato": "contrato",
    "fonte": "fonte",
    "encaixe": "vagas.encaixe",
    "motivo": "vagas.motivo",
    "status": "vagas.status",
    "uf": None,
}
_MAX_TEXTO = 100
MAX_ID = 2**31
# o INTEGER do SQLite é de 64 bits com sinal: id maior estoura em OverflowError (500)
VagaId = Annotated[int, Path(ge=1, le=2**63 - 1)]
_MAX_PAGINA = 10_000
_DESTAQUES_N = 10
# janela larga para o SQL; a de 24 h é da função pura `destaques`
_ANTES_DESTAQUES = "julianday(v.primeira_vista_em) >= julianday(:agora) - 2"


def relogio_do_painel(request: Request) -> Relogio:
    relogio: Relogio = getattr(request.app.state, "relogio", None) or RelogioReal()
    return relogio


def _config(con: sqlite3.Connection, chave: str, padrao: Any) -> Any:
    linha = con.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return padrao if linha is None else json.loads(linha[0])


def inteiro_da_url(texto: str | None, maximo: int) -> int | None:
    """Número de 1 a `maximo`; qualquer outra coisa (letra, zero, negativo, enorme) é None."""
    if texto is None or not texto.isascii() or not texto.isdigit():
        return None
    numero = int(texto)
    return numero if 1 <= numero <= maximo else None


def _texto(texto: str | None) -> str | None:
    limpo = "".join(c for c in texto or "" if c.isprintable()).strip()[:_MAX_TEXTO]
    return limpo or None


def busca_efetiva(con: sqlite3.Connection, pedida: int | None) -> int | None:
    """A busca da URL, se existir; senão a primeira ativa; sem nenhuma, None."""
    if pedida is not None and con.execute("SELECT 1 FROM busca WHERE id = ?", (pedida,)).fetchone():
        return pedida
    linha = con.execute("SELECT id FROM busca WHERE ativa = 1 ORDER BY id LIMIT 1").fetchone()
    return None if linha is None else int(linha[0])


def _sem_criterio(con: sqlite3.Connection, busca_id: int | None) -> bool:
    """Sem busca, ou busca sem cargo, lugar, modalidade, nível, idioma nem salário (11.1)."""
    if busca_id is None:
        return True
    linha = con.execute(
        "SELECT cargos, cidades, modalidades, niveis, idiomas, salario_min FROM busca WHERE id = ?",
        (busca_id,),
    ).fetchone()
    return not (linha[5] or any(json.loads(lista) for lista in linha[:5]))


@dataclass(frozen=True)
class Estado:
    """O que a URL pede, já limpo. `*_url`: veio mesmo na URL e por isso volta nos links."""

    aba: str
    busca_id: int | None
    busca_url: bool
    q: str
    chips: Mapping[str, str]
    ordem: str
    ordem_url: bool
    sem_criterio: bool
    destaques_ligados: bool

    @property
    def e_destaques(self) -> bool:
        return self.aba == ABA_DESTAQUES

    def filtros(self, pagina: int = 1) -> Filtros:
        return Filtros(
            aba=self.aba,
            busca_id=self.busca_id,
            q=self.q,
            area=self.chips.get("area"),
            nivel=self.chips.get("nivel"),
            modalidade=self.chips.get("modalidade"),
            contrato=self.chips.get("contrato"),
            uf=self.chips.get("uf"),
            fonte=self.chips.get("fonte"),
            encaixe=self.chips.get("encaixe"),
            ordem=self.ordem,
            pagina=pagina,
        )

    def url(
        self,
        *,
        aba: str | None = None,
        chips: Mapping[str, str] | None = None,
        extras: Sequence[tuple[str, str]] = (),
    ) -> str:
        """O endereço desta vista, com a aba primeiro; `chips` troca os filtros de chip."""
        escolhidos = self.chips if chips is None else chips
        pares = [("aba", aba or self.aba)]
        if self.busca_url and self.busca_id is not None:
            pares.append(("busca", str(self.busca_id)))
        if self.q:
            pares.append(("q", self.q))
        pares += [(g, escolhidos[g]) for g in CHIPS if g in escolhidos]
        if self.ordem_url:
            pares.append(("ordem", self.ordem))
        return "/vagas?" + urlencode(pares + list(extras))


def _ler_estado(params: QueryParams, con: sqlite3.Connection) -> Estado:
    ligados = bool(_config(con, "destaques_ligados", True))
    validas = {*leitura.ABAS, *([ABA_DESTAQUES] if ligados else [])}
    pedida_aba = params.get("aba") or ""
    aba = pedida_aba if pedida_aba in validas else (ABA_DESTAQUES if ligados else "todas")
    pedida = inteiro_da_url(params.get("busca"), MAX_ID)
    busca_id = busca_efetiva(con, pedida)
    sem = _sem_criterio(con, busca_id)
    pedida_ordem = params.get("ordem") or ""
    ordem_url = pedida_ordem in leitura.ORDENS
    ordem = pedida_ordem if ordem_url else ("recentes" if sem else "encaixe")
    return Estado(
        aba=aba,
        busca_id=busca_id,
        busca_url=pedida is not None and busca_id == pedida,
        q=_texto(params.get("q")) or "",
        chips={g: v for g in CHIPS if (v := _texto(params.get(g)))},
        ordem=ordem,
        ordem_url=ordem_url,
        sem_criterio=sem,
        destaques_ligados=ligados,
    )


def utc_do_banco(texto: str) -> datetime | None:
    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return data if data.tzinfo else data.replace(tzinfo=UTC)


def _ids_destaques(con: sqlite3.Connection, busca_id: int | None, agora: datetime) -> list[int]:
    """As vagas da aba Destaques: só abertas, não ocultas e novas (a função pura faz o resto)."""
    quantas = _config(con, "destaques_n", _DESTAQUES_N)
    if not isinstance(quantas, int) or isinstance(quantas, bool) or quantas < 1:
        quantas = _DESTAQUES_N
    linhas = con.execute(
        "SELECT v.id, v.empresa, e.nota, v.publicada_em, v.primeira_vista_em"
        " FROM vaga v LEFT JOIN encaixe e ON e.vaga_id = v.id AND e.busca_id = :busca"
        f" WHERE {leitura.ABAS['novas']} AND {_ANTES_DESTAQUES}",
        # o dia de calendário é o do fuso local (mesma regra do `leitura`)
        {
            "agora": agora.isoformat(),
            "hoje": agora.astimezone().date().isoformat(),
            "busca": busca_id,
        },
    ).fetchall()
    candidatas = []
    for vaga_id, empresa, nota, publicada, primeira in linhas:
        vista = utc_do_banco(primeira)
        if vista is not None:
            candidata = Candidata(
                vaga_id=vaga_id,
                empresa=empresa,
                nota=nota,
                publicada_em=utc_do_banco(publicada) if publicada else None,
                primeira_vista_em=vista,
            )
            candidatas.append(candidata)
    return [c.vaga_id for c in destaques(candidatas, agora, quantas)]


def _unicas(fontes: Sequence[Fonte]) -> list[Fonte]:
    """Uma fonte por nome: a mesma fonte em dois escopos aparece uma vez."""
    vistas: dict[str, Fonte] = {}
    for f in fontes:
        vistas.setdefault(f.fonte, f)
    return list(vistas.values())


def _fontes(con: sqlite3.Connection, ids: Sequence[int]) -> dict[int, list[Fonte]]:
    """As fontes das ocorrências abertas de cada vaga (todas, se a vaga fechou), como no detalhe."""
    por_vaga: dict[int, list[Fonte]] = {i: [] for i in ids}
    if not ids:
        return por_vaga
    marcas = ", ".join("?" * len(ids))  # só interrogações: os ids vão como parâmetros
    cur = con.execute(
        f"SELECT o.vaga_id, o.fonte, o.url FROM ocorrencia o WHERE o.vaga_id IN ({marcas})"
        " AND (o.sumiu_em IS NULL OR NOT EXISTS (SELECT 1 FROM ocorrencia a"
        " WHERE a.vaga_id = o.vaga_id AND a.sumiu_em IS NULL))"
        " ORDER BY o.primeira_vista_em, o.id",
        list(ids),
    )
    for vaga_id, fonte, url in cur:
        por_vaga[vaga_id].append(Fonte(fonte=fonte, url=url, url_candidatura=None))
    return {i: _unicas(fs) for i, fs in por_vaga.items()}


def _id_html(valor: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", valor)


def _ordem_chip(grupo: str, valor: str) -> int:
    return _ENCAIXES.index(valor) if grupo == "encaixe" and valor in _ENCAIXES else 0


def _grupos(con: sqlite3.Connection, estado: Estado, agora: datetime) -> list[dict[str, Any]]:
    """Os chips com contagem. Motivo (Ocultas) e situação (Candidatei) só contam: sem filtro."""
    contagens = leitura.contar_chips(con, estado.filtros(), agora)
    grupos: list[dict[str, Any]] = []
    for nome in (*CHIPS, "motivo", "status"):
        interativo = nome in CHIPS
        valores = dict(contagens.get(nome, {}))
        escolhido = estado.chips.get(nome)
        if interativo and escolhido and escolhido not in valores:
            valores[escolhido] = 0  # filtro sem nenhuma vaga continua visível, para desligar
        if not valores:
            continue
        # encaixe vai de bom a fraco; os outros, do mais contado para o menos
        ordenados = sorted(
            valores.items(), key=lambda kv: (_ordem_chip(nome, kv[0]), -kv[1], kv[0])
        )
        prefixo = _ROTULO_CHIP[nome]
        chips = []
        for valor, n in ordenados:
            ligado = escolhido == valor
            trocados = {k: v for k, v in estado.chips.items() if k != nome}
            chips.append(
                {
                    "id": _id_html(valor),
                    "valor": valor,
                    "chave": f"{prefixo}.{valor}" if prefixo else "",
                    "n": n,
                    "pressionado": ligado,
                    "url": estado.url(chips=trocados if ligado else {**trocados, nome: valor}),
                }
            )
        grupos.append({"nome": nome, "interativo": interativo, "chips": chips})
    return grupos


def _seletor(con: sqlite3.Connection, estado: Estado) -> list[dict[str, Any]]:
    """As buscas ativas (e a da URL, mesmo desligada), cada uma com a vista atual trocada nela."""
    linhas = con.execute(
        "SELECT id, nome FROM busca WHERE ativa = 1 OR id = ? ORDER BY id", (estado.busca_id,)
    ).fetchall()
    if len(linhas) < 2:
        return []
    return [
        {
            "nome": nome,
            "atual": id_ == estado.busca_id,
            "url": replace(estado, busca_id=id_, busca_url=True).url(),
        }
        for id_, nome in linhas
    ]


def _contexto_pagina(con: sqlite3.Connection, estado: Estado, agora: datetime) -> dict[str, Any]:
    ids_destaques = _ids_destaques(con, estado.busca_id, agora) if estado.destaques_ligados else []
    contagens = leitura.contar_abas(con, estado.busca_id, agora)
    chaves = [*([ABA_DESTAQUES] if estado.destaques_ligados else []), *leitura.ABAS]
    abas = [
        {
            "chave": chave,
            "n": len(ids_destaques) if chave == ABA_DESTAQUES else contagens[chave],
            "atual": chave == estado.aba,
            "url": estado.url(aba=chave, chips={}),
        }
        for chave in chaves
    ]
    itens: Sequence[Item]
    mais_url = None
    grupos: list[dict[str, Any]] = []
    if estado.e_destaques:
        achados = [leitura.detalhe(con, i, estado.busca_id, agora) for i in ids_destaques]
        detalhes = [d for d in achados if d is not None]
        itens = detalhes
        fontes = {d.id: _unicas(d.fontes) for d in detalhes}
    else:
        pagina = leitura.listar(con, estado.filtros(), agora)
        itens = pagina.itens
        fontes = _fontes(con, [i.id for i in itens])
        grupos = _grupos(con, estado, agora)
        if pagina.tem_mais:
            mais_url = estado.url(extras=[("pagina", "2")])
    return {
        "abas": abas,
        "seletor": _seletor(con, estado),
        "grupos": grupos,
        "itens": itens,
        "fontes": fontes,
        "mais_url": mais_url,
        "proxima": 2,
        "ordens": list(leitura.ORDENS),
        "ordem": estado.ordem,
        "q": estado.q,
        "sem_criterio": estado.sem_criterio,
        "e_destaques": estado.e_destaques,
        "aba_da_busca": "todas" if estado.e_destaques else estado.aba,
        "campos_ocultos": [(g, v) for g in CHIPS if (v := estado.chips.get(g))],
        "busca_id": estado.busca_id,
        "busca_na_url": estado.busca_url,
        "retorno": estado.url(),
        "marcar_foco": False,
    }


def _vary(resposta: HTMLResponse) -> HTMLResponse:
    resposta.headers["Vary"] = "HX-Request, HX-History-Restore-Request"
    return resposta


@router.get("/")
async def raiz(con: Con) -> RedirectResponse:
    if not _config(con, "primeira_execucao_concluida", False):
        return RedirectResponse("/primeira-execucao/1", status_code=303)
    aba = ABA_DESTAQUES if _config(con, "destaques_ligados", True) else "todas"
    return RedirectResponse(f"/vagas?aba={aba}", status_code=303)


@router.get("/vagas")
async def vagas(request: Request, con: Con) -> HTMLResponse:
    estado = _ler_estado(request.query_params, con)
    agora = relogio_do_painel(request).agora()
    cabecalho = request.headers
    restaurando = cabecalho.get("hx-history-restore-request") == "true"
    parcial = cabecalho.get("hx-request") == "true" and not restaurando
    pagina = inteiro_da_url(request.query_params.get("pagina"), _MAX_PAGINA) or 1
    if parcial and pagina > 1 and not estado.e_destaques:
        # "carregar mais": só os cartões novos e o botão da página seguinte
        lista = leitura.listar(con, estado.filtros(pagina), agora)
        seguinte = estado.url(extras=[("pagina", str(pagina + 1))])
        return _vary(
            renderizar(
                request,
                "vagas/mais.html",
                itens=lista.itens,
                fontes=_fontes(con, [i.id for i in lista.itens]),
                mais_url=seguinte if lista.tem_mais else None,
                proxima=pagina + 1,
                marcar_foco=True,
                retorno=estado.url(),
                busca_id=estado.busca_id,
            )
        )
    contexto = _contexto_pagina(con, estado, agora)
    modelo = "vagas/miolo.html" if parcial else "vagas/pagina.html"
    return _vary(renderizar(request, modelo, **contexto))


def _aplicar(request: Request, acao: Callable[[datetime], None]) -> None:
    """Roda a ação do `acoes`: vaga que não existe é 404; valor ou estado inválido, 422."""
    try:
        acao(relogio_do_painel(request).agora())
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from erro


def _resposta(
    request: Request, con: sqlite3.Connection, vaga_id: int, voltar: str, busca: str
) -> Response:
    """HTMX recebe o corpo novo do cartão; sem HTMX, a pessoa volta para a página de onde veio."""
    if request.headers.get("hx-request") != "true":
        return de_volta(voltar)
    busca_id = busca_efetiva(con, inteiro_da_url(busca, MAX_ID))
    vaga = leitura.detalhe(con, vaga_id, busca_id, relogio_do_painel(request).agora())
    if vaga is None:
        raise HTTPException(404, "vaga não existe")
    return renderizar(
        request,
        "vagas/corpo.html",
        item=vaga,
        fontes={vaga.id: _unicas(vaga.fontes)},
        retorno=voltar,
        busca_id=busca_id,
        foco=True,
    )


@router.post("/vagas/{vaga_id}/status")
async def mudar_status(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    status: Annotated[str, Form()],
    voltar: Annotated[str, Form()] = "/",
    busca: Annotated[str, Form()] = "",
) -> Response:
    _aplicar(request, lambda agora: acoes.mudar_status(con, vaga_id, status, agora))
    return _resposta(request, con, vaga_id, voltar, busca)


@router.post("/vagas/{vaga_id}/ocultar")
async def ocultar(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    voltar: Annotated[str, Form()] = "/",
    busca: Annotated[str, Form()] = "",
) -> Response:
    _aplicar(request, lambda agora: acoes.ocultar(con, vaga_id, agora))
    return _resposta(request, con, vaga_id, voltar, busca)


@router.post("/vagas/{vaga_id}/mostrar")
async def mostrar(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    voltar: Annotated[str, Form()] = "/",
    busca: Annotated[str, Form()] = "",
) -> Response:
    """ "Trazer de volta" (ocultada à mão) ou "mostrar mesmo assim" (ocultada por regra)."""
    linha = con.execute("SELECT oculta_manual FROM vaga WHERE id = ?", (vaga_id,)).fetchone()
    if linha is None:
        raise HTTPException(404, "vaga não existe")
    acao = acoes.trazer_de_volta if linha[0] == 1 else acoes.mostrar
    _aplicar(request, lambda agora: acao(con, vaga_id, agora))
    return _resposta(request, con, vaga_id, voltar, busca)
