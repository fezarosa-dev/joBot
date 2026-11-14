"""Vigia semanal das fontes (T84, ADR 0018, decisão 20; escolhas do redator na D31).

Script de CI: roda só no GitHub Actions (`.github/workflows/vigia.yml`), fora do pacote `jobot`.
Testa de verdade um escopo de cada fonte pública, no ritmo e com os limites da ADR 0004, com no
máximo `VIGIA_MAX_PEDIDOS` pedidos por fonte, e abre, atualiza, reabre ou fecha uma issue por
fonte quando ela quebra ou volta. Não tem banco: chama `escopos`, `coletar` e `detalhar` do
coletor direto, sem o executor da T16 (que pede `Historico`), e copia dele a regra do detalhe.

É a única exceção à regra de `Authorization` das Global Constraints: o `GITHUB_TOKEN` vai só em
pedido a `api.github.com`, pelo `ApiGithub`; o `ClienteEducado` das fontes nunca o recebe.

Uso: `GITHUB_TOKEN=... GITHUB_REPOSITORY=dono/repo uv run python scripts/vigia.py`.
"""

import asyncio
import copy
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from typing import Any, Literal, Protocol
from urllib.parse import quote

import httpx

from jobot.banco.cadastros import empresas_iniciais
from jobot.nucleo.coletores.base import (
    Coletor,
    ContextoColeta,
    Estado,
    LimiteEscopo,
    UrlListada,
)
from jobot.nucleo.coletores.executor import (
    PARA_DETALHES,  # do executor: a regra do detalhe é a mesma, sem cópia que divirja
    PRAZO_ESCOPO_S,
    motivo_do_detalhe,
    motivo_do_escopo,
)
from jobot.nucleo.coletores.registro import descobrir
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio, RelogioReal

FONTES_FORA = frozenset({"eureca", "abler", "gupy"})  # termos restritivos (ADR 0004)
VIGIA_MAX_PEDIDOS = 5
VIGIA_MAX_DETALHES = 2
TERMOS = ("developer",)
PAISES = ("BR",)
AUTOR_DO_VIGIA = "github-actions[bot]"  # o usuário do GITHUB_TOKEN
ROTULO = "fonte-quebrada"
API = "https://api.github.com"
MAX_PAGINAS_API = 10

# Cada chave `saude.*` de `comum.json` está em exatamente um dos dois (teste): chave nova obriga
# a decidir. Abrir issue depende também do estado (ver `quebrou`).
ABRE_ISSUE = frozenset({"saude.formato_mudou", "saude.excecao"})
SO_RESUMO = frozenset(
    {
        "saude.bloqueio",  # o Actions roda de IP de datacenter
        "saude.empresa_nao_encontrada",
        "saude.tempo_esgotado",
        "saude.erro_de_rede",
        "saude.resposta_grande",
        "saude.listagem_incompleta",
        "saude.zero_inesperado",  # quem a produz é o executor, que o vigia não usa
        "saude.parcial_n",
        "saude.sem_detalhe_n",
        "saude.cota",
        "saude.intervalo",
        "saude.parou_429",
        "saude.limite_atingido",
        "saude.orcamento",
    }
)
_SEM_DETALHE = "saude.sem_detalhe_n:"
# linha do corpo da issue aberta por detalhe quebrado
_DETALHE_SIM = "- detalhe quebrado / broken detail: sim / yes"
_DETALHE_NAO = "- detalhe quebrado / broken detail: -"
_VAZIO = ContextoColeta((), (), ())
_SEM_DATA = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Resultado:
    fonte: str
    estado: Estado | Literal["nao_vigiada"]
    motivo: str | None = None
    escopo: str | None = None
    listadas: int = 0  # itens que o `coletar` listou (VagaColetada e UrlListada)
    vagas: int = 0  # vagas lidas: as do `coletar` mais as que o `detalhar` devolveu
    pedidos: int = 0
    escopo_unico: bool = False
    detalhe_quebrado: bool = False
    detalhe_ok: bool = False  # o `detalhar` rodou nesta vigia e devolveu ao menos uma vaga


def _chave(motivo: str | None) -> str:
    return (motivo or "").split(":", 1)[0]


def quebrou(r: Resultado) -> bool:
    """A fonte quebrou e merece issue (D31); o resto só entra no resumo do job."""
    chave = _chave(r.motivo)
    if chave == "saude.formato_mudou" and r.estado in ("falhou", "parcial"):
        return True
    if chave == "saude.excecao" and r.estado == "falhou":
        return True
    if r.escopo_unico and r.estado == "ok" and r.listadas == 0:
        return True  # parser quebrado sem erro; nas outras fontes zero vaga pode ser normal
    return r.detalhe_quebrado


def _voltou(r: Resultado) -> bool:
    """A fonte leu a lista sem quebra; "falhou" e "no_limite" não dizem se ela voltou."""
    return not quebrou(r) and r.estado in ("ok", "sem_mudanca", "parcial")


def _vigiadas(todos: Iterable[str]) -> list[str]:
    return sorted(set(todos) - FONTES_FORA)


def fontes_vigiadas() -> list[str]:
    return _vigiadas(descobrir())


def contexto_da_fonte(fonte: str, empresas: Sequence[Empresa]) -> ContextoColeta:
    """Contexto fixo (D31): `developer`, `BR` e só a primeira empresa da fonte, se houver."""
    primeira = next((e for e in empresas if e.fonte == fonte), None)
    return ContextoColeta(() if primeira is None else (primeira,), TERMOS, PAISES)


def escopo_unico(coletor: Coletor) -> bool:
    """Um escopo só com o contexto vazio: não depende de empresa, termo nem país."""
    return len(copy.copy(coletor).escopos(_VAZIO)) == 1  # cópia: `escopos` guarda estado (D60)


class _SemValidadores:
    """O vigia não tem banco: nenhum pedido é condicional."""

    def ler(self, url: str) -> Validadores | None:
        return None


async def _uma_fonte(
    chave: str, original: Coletor, cliente: ClienteEducado, relogio: Relogio, ctx: ContextoColeta
) -> Resultado:
    coletor = copy.copy(original)  # D50/D60: `escopos` e `coletar` na mesma instância, só nossa
    try:
        unico = escopo_unico(original)
        escopos = list(coletor.escopos(ctx))
    except Exception as erro:
        return Resultado(chave, "falhou", motivo_do_escopo(erro))
    if not escopos:
        return Resultado(chave, "nao_vigiada")
    escopo = escopos[0]
    limite = coletor.por_escopo.get(escopo, LimiteEscopo())
    maximo = VIGIA_MAX_PEDIDOS
    if coletor.max_pedidos is not None:
        maximo = min(maximo, coletor.max_pedidos)
    http = cliente.escopo(
        espera_s=coletor.espera_s if limite.espera_s is None else limite.espera_s,
        condicional=False,
        max_pedidos=maximo,
        para_no_429=limite.para_no_429,
    )
    inicio = relogio.agora()
    detalhadas = sem_detalhe = comuns = tentados = 0
    erro_detalhe: str | None = None
    try:
        async with asyncio.timeout(PRAZO_ESCOPO_S):
            resultado = await coletor.coletar(escopo, http)
            unicas: dict[str, UrlListada] = {}
            for u in resultado.vagas:
                if isinstance(u, UrlListada):
                    unicas.setdefault(u.url, u)  # como o executor: vale a primeira repetida
            # como o executor: as mais recentes primeiro, as sem data por último
            ordem = sorted(
                unicas.values(), key=lambda u: u.atualizada_em or _SEM_DATA, reverse=True
            )
            for item in ordem[:VIGIA_MAX_DETALHES]:
                tentados += 1
                try:
                    vaga = await coletor.detalhar(item, http)
                except PARA_DETALHES as erro:
                    erro_detalhe = motivo_do_detalhe(erro)
                    break
                except Exception as erro:  # só esta URL
                    motivo_erro = motivo_do_detalhe(erro)
                    comuns += _chave(motivo_erro) == "saude.excecao"
                    erro_detalhe = erro_detalhe or motivo_erro
                    continue
                if vaga is None:
                    sem_detalhe += 1
                else:
                    detalhadas += 1
        if relogio.agora() - inicio > timedelta(seconds=PRAZO_ESCOPO_S):
            raise TimeoutError  # o prazo pelo relógio injetado, como no executor
    except TimeoutError:
        return Resultado(
            chave,
            "falhou",
            "saude.tempo_esgotado",
            escopo,
            pedidos=http.pedidos,
            escopo_unico=unico,
        )
    except Exception as erro:  # só o nome do tipo, nunca o texto da exceção
        return Resultado(
            chave,
            "falhou",
            motivo_do_escopo(erro),
            escopo,
            pedidos=http.pedidos,
            escopo_unico=unico,
        )
    motivo = resultado.motivo
    if motivo is None or motivo.startswith(
        _SEM_DETALHE
    ):  # o motivo do coletor vence, como no executor
        if erro_detalhe is not None:
            motivo = erro_detalhe
        elif sem_detalhe:
            n_antes = int(motivo.removeprefix(_SEM_DETALHE)) if motivo else 0
            motivo = f"{_SEM_DETALHE}{n_antes + sem_detalhe}"
    vagas = sum(isinstance(v, VagaColetada) for v in resultado.vagas) + detalhadas
    # D31: em fonte de escopo único, todo detalhe tentado quebrou (erro comum ou None); um erro
    # de parada conta como tentado sem quebrar, então nunca abre issue
    quebrado = tentados > 0 and comuns + sem_detalhe == tentados and vagas == 0
    return Resultado(
        chave,
        resultado.estado,
        motivo,
        escopo,
        listadas=len(resultado.vagas),
        vagas=vagas,
        pedidos=http.pedidos,
        escopo_unico=unico,
        detalhe_quebrado=unico and quebrado,
        detalhe_ok=detalhadas > 0,
    )


async def rodar(
    cliente: ClienteEducado,
    relogio: Relogio,
    *,
    coletores: Mapping[str, Coletor] | None = None,
    empresas: Sequence[Empresa] | None = None,
) -> list[Resultado]:
    """Um escopo por fonte vigiada, uma fonte de cada vez; a exceção de uma não para as outras."""
    todos = descobrir() if coletores is None else coletores
    lista = empresas_iniciais() if empresas is None else empresas
    resultados = []
    for chave in _vigiadas(todos):
        ctx = contexto_da_fonte(chave, lista)
        resultados.append(await _uma_fonte(chave, todos[chave], cliente, relogio, ctx))
    return resultados


def resumo(resultados: Sequence[Resultado]) -> str:
    """Tabela em Markdown para o resumo do job; só chaves, contagens e o nome do tipo de erro."""
    linhas = [
        "# Vigia das fontes",
        "",
        "| fonte | estado | motivo | listadas | vagas | pedidos | issue |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        estado = "não vigiada" if r.estado == "nao_vigiada" else r.estado
        issue = "abre" if quebrou(r) else ""
        linhas.append(
            f"| {r.fonte} | {estado} | {r.motivo or ''} | {r.listadas} | {r.vagas} "
            f"| {r.pedidos} | {issue} |"
        )
    return "\n".join(linhas) + "\n"


# --- issues -----------------------------------------------------------------------------------


class Api(Protocol):
    async def issues(self) -> list[dict[str, Any]]: ...
    async def eventos(self, n: int) -> list[dict[str, Any]]: ...
    async def comentarios(self, n: int) -> list[dict[str, Any]]: ...
    async def criar(self, titulo: str, corpo: str) -> None: ...
    async def editar(self, n: int, campos: Mapping[str, str]) -> None: ...
    async def comentar(self, n: int, corpo: str) -> None: ...


def _marca(fonte: str, sufixo: str = "") -> str:
    return f"<!-- vigia:{fonte}{sufixo} -->"


def _autor(item: Mapping[str, Any], campo: str = "user") -> str | None:
    pessoa = item.get(campo)
    return pessoa.get("login") if isinstance(pessoa, dict) else None


def _do_vigia(item: Mapping[str, Any]) -> bool:
    """Marca e rótulo qualquer pessoa escreve em repositório público: o autor decide."""
    if "pull_request" in item or _autor(item) != AUTOR_DO_VIGIA:
        return False
    rotulos = item.get("labels") or []
    return any(isinstance(r, dict) and r.get("name") == ROTULO for r in rotulos)


def _titulo(r: Resultado) -> str:
    return f"Fonte quebrada / broken source: {r.fonte}"


def _corpo(r: Resultado) -> str:
    """Só a chave do motivo, o tipo do erro e contagens: nenhum conteúdo de vaga."""
    return "\n".join(
        [
            _marca(r.fonte),
            f"O vigia semanal achou a fonte `{r.fonte}` quebrada.",
            f"The weekly watcher found the source `{r.fonte}` broken.",
            "",
            f"- estado / state: `{r.estado}`",
            f"- motivo / reason: `{r.motivo or '-'}`",
            f"- itens listados / listed items: {r.listadas}",
            _DETALHE_SIM if r.detalhe_quebrado else _DETALHE_NAO,
            "",
            "Esta issue é atualizada toda semana e fechada quando a fonte volta.",
            "This issue is updated every week and closed when the source comes back.",
        ]
    )


def _ultimo_fechamento(eventos: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    fechados = [e for e in eventos if e.get("event") == "closed"]
    return fechados[-1] if fechados else None


async def _quebrada(r: Resultado, issue: Mapping[str, Any] | None, api: Api) -> None:
    corpo = _corpo(r)
    if issue is None:
        await api.criar(_titulo(r), corpo)
        return
    n = int(issue["number"])
    if issue.get("state") == "open":
        await api.editar(n, {"body": corpo})
        return
    fechamento = _ultimo_fechamento(await api.eventos(n))
    if fechamento is not None and _autor(fechamento, "actor") == AUTOR_DO_VIGIA:
        await api.editar(n, {"state": "open", "body": corpo})  # o vigia fechou: reabre
        return
    # fechada por pessoa: não reabre nem abre outra; avisa uma vez por fechamento
    desde = str(fechamento.get("created_at") or "") if fechamento else ""
    visto = _marca(r.fonte, ":visto")
    ja_avisou = any(
        _autor(c) == AUTOR_DO_VIGIA
        and visto in str(c.get("body") or "")
        and str(c.get("created_at") or "") >= desde
        for c in await api.comentarios(n)
    )
    if not ja_avisou:
        await api.comentar(
            n,
            f"{visto}\nA fonte continua quebrando (`{r.motivo or r.estado}`); "
            "como uma pessoa fechou esta issue, o vigia não a reabre.\n"
            "The source is still broken; since a person closed this issue, the watcher "
            "does not reopen it.",
        )


async def atualizar_issues(resultados: Sequence[Resultado], api: Api) -> None:
    """Uma issue por fonte: abre, atualiza, reabre (se o vigia fechou) ou fecha quando volta.

    Fonte "não vigiada" não mexe em issue nenhuma; issue que não é do vigia nunca é tocada.
    """
    do_vigia = [i for i in await api.issues() if _do_vigia(i)]
    for r in resultados:
        if r.estado == "nao_vigiada":
            continue
        marca = _marca(r.fonte)
        dela = max(
            (i for i in do_vigia if marca in str(i.get("body") or "")),
            key=lambda i: int(i["number"]),
            default=None,
        )
        if quebrou(r):
            await _quebrada(r, dela, api)
        elif dela is not None and dela.get("state") == "open" and _voltou(r):
            # issue por detalhe quebrado só fecha se o detalhe rodou agora e funcionou
            if _DETALHE_SIM in str(dela.get("body") or "") and not r.detalhe_ok:
                continue
            n = int(dela["number"])
            await api.comentar(
                n,
                f"{_marca(r.fonte, ':voltou')}\nA fonte voltou a funcionar. / The source is back.",
            )
            await api.editar(n, {"state": "closed"})


async def _so_api(pedido: httpx.Request) -> None:
    """O token só sai para `api.github.com` em https (inclusive no `Link rel=next`)."""
    url = pedido.url
    if url.scheme != "https" or url.host != "api.github.com" or url.port or url.userinfo:
        raise ValueError(f"pedido fora da API do GitHub: {url}")


class ApiGithub:
    """Cliente da API de issues do GitHub, separado do `ClienteEducado` das fontes."""

    def __init__(
        self, token: str, repositorio: str, transporte: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repositorio) or ".." in repositorio:
            raise ValueError(f"repositório fora do formato dono/nome: {repositorio!r}")
        dono, nome = repositorio.split("/")
        self._base = f"/repos/{quote(dono)}/{quote(nome)}"
        self._cliente = httpx.AsyncClient(
            base_url=API,
            transport=transporte,
            timeout=30.0,
            follow_redirects=False,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "joBot-vigia",
            },
            event_hooks={"request": [_so_api]},
        )

    async def fechar(self) -> None:
        await self._cliente.aclose()

    async def _listar(self, caminho: str, params: Mapping[str, str]) -> list[dict[str, Any]]:
        """Segue o `Link rel=next` com teto de páginas; o gancho recusa outro host."""
        itens: list[dict[str, Any]] = []
        url: str = f"{self._base}{caminho}"
        consulta: Mapping[str, str] | None = {"per_page": "100", **params}
        vistas: set[str] = set()
        for _ in range(MAX_PAGINAS_API):
            resposta = await self._cliente.get(url, params=consulta)
            resposta.raise_for_status()
            vistas.add(str(resposta.request.url))
            pagina = resposta.json()
            if not isinstance(pagina, list):
                raise ValueError(f"resposta inesperada da API em {caminho}")
            itens.extend(i for i in pagina if isinstance(i, dict))
            proxima = resposta.links.get("next", {}).get("url")
            if not proxima or proxima in vistas:
                break
            url, consulta = proxima, None
        return itens

    async def issues(self) -> list[dict[str, Any]]:
        # só o rótulo filtra na API; o autor quem decide é `_do_vigia`
        return await self._listar("/issues", {"state": "all", "labels": ROTULO})

    async def eventos(self, n: int) -> list[dict[str, Any]]:
        return await self._listar(f"/issues/{n}/events", {})

    async def comentarios(self, n: int) -> list[dict[str, Any]]:
        return await self._listar(f"/issues/{n}/comments", {})

    async def _enviar(self, metodo: str, caminho: str, corpo: Mapping[str, Any]) -> None:
        resposta = await self._cliente.request(metodo, f"{self._base}{caminho}", json=corpo)
        resposta.raise_for_status()

    async def criar(self, titulo: str, corpo: str) -> None:
        await self._enviar("POST", "/issues", {"title": titulo, "body": corpo, "labels": [ROTULO]})

    async def editar(self, n: int, campos: Mapping[str, str]) -> None:
        await self._enviar("PATCH", f"/issues/{n}", dict(campos))

    async def comentar(self, n: int, corpo: str) -> None:
        await self._enviar("POST", f"/issues/{n}/comments", {"body": corpo})


async def _principal() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    repositorio = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repositorio:
        print("vigia: faltam GITHUB_TOKEN e GITHUB_REPOSITORY", file=sys.stderr)
        return 1
    relogio = RelogioReal()
    cliente = ClienteEducado(None, relogio, _SemValidadores(), version("jobot"))
    api = ApiGithub(token, repositorio)
    try:
        resultados = await rodar(cliente, relogio)
        texto = resumo(resultados)
        print(texto)
        destino = os.environ.get("GITHUB_STEP_SUMMARY")
        if destino:
            with open(destino, "a", encoding="utf-8") as arquivo:
                arquivo.write(texto)
        await atualizar_issues(resultados, api)
    finally:
        await cliente.fechar()
        await api.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_principal()))
