"""Upload e leitura do currículo em PDF na aba Perfil (desenho 8 da fase 4; plano T435; D231).

A rota exige o token CSRF no cabeçalho e recusa pelo `Content-Length` antes de ler o corpo; o PDF
é lido no processo filho de `sistema/pdf.py`, e nada dele fica na pasta de dados nem no banco. Os
PDFs são montados no teste (`apoio.pdf`), com dados reservados.
"""

import asyncio
import html as html_lib
import re
import tempfile
from collections.abc import Iterator, MutableMapping
from contextlib import closing
from pathlib import Path
from typing import Any, get_args

import pytest
import starlette.formparsers
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apoio.pdf import montar_pdf
from apoio.relogio import RelogioFalso
from apoio.semear import semear
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.rotas import perfil as perfil_rota
from jobot.painel.seguranca import CABECALHO_CSRF, CAMPO_CSRF
from jobot.sistema import pdf

PORTA = 47619
PERFIL = "/configuracoes/perfil"
CURRICULO = PERFIL + "/curriculo"
MARCA = "Analista Quixotesco Zebrino"  # o texto de teste: só aparece onde o PDF foi parar
AVISOS: tuple[pdf.Aviso, ...] = (
    "nao_pdf",
    "senha",
    "protegido",
    "corrompido",
    "so_imagem",
    "prazo",
)
CHAVE_AVISO = "configuracoes.perfil.curriculo.aviso."


class Painel:
    def __init__(self, tmp_path: Path) -> None:
        self.dados = tmp_path
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            semear(con)
            cadastros.semear(con)
        self.app: FastAPI = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso()
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

    def enviar(self, dados: bytes, *, nome: str = "curriculo.pdf") -> Any:
        return self.http.post(
            CURRICULO,
            files={"curriculo": (nome, dados, "application/pdf")},
            headers={CABECALHO_CSRF: self.token, "HX-Request": "true"},
        )

    def idioma(self, idioma: str) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.gravar_config(con, "idioma", idioma)


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


@pytest.fixture
def extraidos(monkeypatch: pytest.MonkeyPatch) -> list[pdf.Lido]:
    lista: list[pdf.Lido] = []
    monkeypatch.setattr(perfil_rota, "extrair_curriculo", lista.append)
    return lista


def _texto(html: str) -> str:
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _multipart(dados: bytes, extra: dict[str, str] | None = None) -> tuple[bytes, str]:
    fronteira = "fronteira-do-teste"
    cabeca = f"--{fronteira}\r\nContent-Disposition: form-data; name="
    partes = [
        f'{cabeca}"{nome}"\r\n\r\n{valor}\r\n'.encode() for nome, valor in (extra or {}).items()
    ]
    partes.append(
        f'--{fronteira}\r\nContent-Disposition: form-data; name="curriculo"; '
        f'filename="cv.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
        + dados
        + f"\r\n--{fronteira}--\r\n".encode()
    )
    return b"".join(partes), f"multipart/form-data; boundary={fronteira}"


def _chamar(app: FastAPI, cabecalhos: dict[str, str], corpo: bytes) -> tuple[int, int]:
    """Chama o app direto pelo ASGI: devolve o status e quantas vezes o corpo foi pedido."""
    lidos = 0
    status = 0

    async def receive() -> dict[str, Any]:
        nonlocal lidos
        lidos += 1
        return {"type": "http.request", "body": corpo, "more_body": False}

    async def send(mensagem: MutableMapping[str, Any]) -> None:
        nonlocal status
        if mensagem["type"] == "http.response.start":
            status = mensagem["status"]

    escopo = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": CURRICULO,
        "raw_path": CURRICULO.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in ({"host": f"127.0.0.1:{PORTA}"} | cabecalhos).items()
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", PORTA),
    }
    try:
        asyncio.run(app(escopo, receive, send))
    except Exception:  # erro do servidor vira 500, para reprovar por asserção
        status = 500
    return status, lidos


# ------------------------------------------------------------------ leitura


def test_texto_lido_chega_a_extracao_e_a_tela_diz_quanto(
    painel: Painel, extraidos: list[pdf.Lido]
) -> None:
    resposta = painel.enviar(montar_pdf([MARCA, "Curso de SQL"]))
    assert resposta.status_code == 200
    assert extraidos == [pdf.Lido(texto=f"{MARCA}\nCurso de SQL", paginas=2, total=2)]
    esperado = i18n.t("pt", "configuracoes.perfil.curriculo.lido", paginas=2, total=2)
    assert esperado in _texto(resposta.text)
    assert 'role="status"' in resposta.text
    assert "data-foco-se-livre" in resposta.text  # o foco solto vai ao resultado


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize(
    ("dados", "aviso"),
    [
        (montar_pdf([None]), "so_imagem"),
        (montar_pdf(["segredo"], senha="abre-te"), "senha"),
        (b"%PDF-1.7\n1 0 obj lixo sem fim", "corrompido"),
        (b"Curriculo em texto, nao em PDF", "nao_pdf"),
    ],
    ids=["so_imagem", "senha", "corrompido", "nao_pdf"],
)
def test_aviso_proprio_na_tela(
    painel: Painel, extraidos: list[pdf.Lido], dados: bytes, aviso: str, idioma: str
) -> None:
    painel.idioma(idioma)
    resposta = painel.enviar(dados)
    assert resposta.status_code == 200
    assert _texto(resposta.text) == i18n.t(idioma, CHAVE_AVISO + aviso)
    assert 'role="alert"' in resposta.text
    assert "data-foco-se-livre" in resposta.text
    assert extraidos == []


def test_prazo_vencido_vira_aviso(
    painel: Painel, extraidos: list[pdf.Lido], monkeypatch: pytest.MonkeyPatch
) -> None:
    def vencido(dados: bytes) -> pdf.Lido:
        raise pdf.AvisoPdf("prazo")

    monkeypatch.setattr(pdf, "ler", vencido)
    resposta = painel.enviar(montar_pdf([MARCA]))
    assert _texto(resposta.text) == i18n.t("pt", CHAVE_AVISO + "prazo")
    assert extraidos == []


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_todo_aviso_tem_texto_proprio(idioma: str) -> None:
    textos = [i18n.t(idioma, CHAVE_AVISO + aviso) for aviso in AVISOS]
    assert all(not texto.startswith(CHAVE_AVISO) for texto in textos)
    assert len(set(textos)) == len(AVISOS)
    assert set(AVISOS) == set(get_args(pdf.Aviso))


def test_formulario_do_curriculo_mostra_a_espera(painel: Painel) -> None:
    html = painel.http.get(PERFIL).text
    achado = re.search(r'<form[^>]*hx-post="/configuracoes/perfil/curriculo".*?</form>', html, re.S)
    assert achado is not None
    form = achado.group(0)
    # a leitura leva até 30 s: o botão diz que está lendo (o HTMX marca o botão, não o form)
    assert 'hx-indicator="find button"' in form
    assert '<span class="botao-espera">Lendo o currículo…</span>' in form
    assert "data-limpar-alvo" in form  # envio novo tira o resultado do anterior
    # os filhos já têm role="status" e role="alert": sem aria-live em volta, nada se lê duas vezes
    assert '<div id="perfil-curriculo-resultado"></div>' in html


def test_sem_o_arquivo_e_422(painel: Painel, extraidos: list[pdf.Lido]) -> None:
    corpo, tipo = _multipart(b"")
    corpo = corpo.replace(b'name="curriculo"', b'name="outro"')
    resposta = painel.http.post(
        CURRICULO, content=corpo, headers={"content-type": tipo, CABECALHO_CSRF: painel.token}
    )
    assert resposta.status_code == 422
    assert extraidos == []


# ------------------------------------------------------------------ recusas antes de ler o corpo


def test_acima_de_5_mb_recusado_antes_de_ler_o_corpo(painel: Painel) -> None:
    corpo, tipo = _multipart(montar_pdf([MARCA]))
    cabecalhos = {"content-type": tipo, CABECALHO_CSRF: painel.token, "hx-request": "true"}
    grande = cabecalhos | {"content-length": str(pdf.TETO_BYTES + 1)}
    assert _chamar(painel.app, grande, corpo) == (413, 0)
    # controle: no teto, o mesmo pedido lê o corpo e chega à leitura
    no_teto = cabecalhos | {"content-length": str(len(corpo))}
    assert len(corpo) <= pdf.TETO_BYTES
    assert _chamar(painel.app, no_teto, corpo) == (200, 1)


def test_acima_de_5_mb_diz_o_motivo(painel: Painel) -> None:
    resposta = painel.enviar(b"%PDF-1.7\n" + b"0" * pdf.TETO_BYTES)
    assert resposta.status_code == 413
    texto = i18n.t("pt", "configuracoes.perfil.curriculo.grande")
    # o aviso de erro do `app.js` lê o `data-aviso-erro` do 4xx
    achado = re.search(r"<p\b[^>]*data-aviso-erro[^>]*>([^<]*)</p>", resposta.text)
    assert achado is not None and html_lib.unescape(achado.group(1)) == texto


def test_sem_content_length_recusado_antes_de_ler_o_corpo(painel: Painel) -> None:
    corpo, tipo = _multipart(montar_pdf([MARCA]))
    cabecalhos = {"content-type": tipo, CABECALHO_CSRF: painel.token}
    assert _chamar(painel.app, cabecalhos, corpo) == (411, 0)
    assert _chamar(painel.app, cabecalhos | {"content-length": "1e3"}, corpo) == (411, 0)
    # chunked com Content-Length: o h11 aceita, o chunked manda e o tamanho declarado não vale
    chunked = cabecalhos | {"content-length": str(len(corpo)), "transfer-encoding": "chunked"}
    assert _chamar(painel.app, chunked, corpo) == (411, 0)


def test_sem_cabecalho_csrf_recusado_sem_ler_o_formulario(painel: Painel) -> None:
    # o token certo no corpo não vale: o upload não cai no `request.form()` do `exigir_csrf`
    corpo, tipo = _multipart(montar_pdf([MARCA]), {CAMPO_CSRF: painel.token})
    cabecalhos = {"content-type": tipo, "content-length": str(len(corpo))}
    assert _chamar(painel.app, cabecalhos, corpo) == (403, 0)
    errado = cabecalhos | {CABECALHO_CSRF: "outro"}
    assert _chamar(painel.app, errado, corpo) == (403, 0)
    maiusculas = cabecalhos | {
        "content-type": tipo.replace("multipart/form-data", "Multipart/Form-Data")
    }
    assert _chamar(painel.app, maiusculas, corpo) == (403, 0)
    # controle: com o cabeçalho, o mesmo pedido lê o corpo
    assert _chamar(painel.app, cabecalhos | {CABECALHO_CSRF: painel.token}, corpo)[1] == 1


def test_outro_site_recusado_sem_ler_o_corpo(painel: Painel) -> None:
    # vale para todo POST, também o urlencoded: a origem se confere antes do `request.form()`
    corpo = f"{CAMPO_CSRF}={painel.token}".encode()
    cabecalhos = {
        "content-type": "application/x-www-form-urlencoded",
        "content-length": str(len(corpo)),
    }
    assert _chamar(painel.app, cabecalhos | {"sec-fetch-site": "cross-site"}, corpo) == (403, 0)
    assert _chamar(painel.app, cabecalhos | {"origin": "http://outro.example"}, corpo) == (403, 0)
    # controle: do próprio painel, o mesmo pedido lê o corpo
    proprio = cabecalhos | {"origin": f"http://127.0.0.1:{PORTA}", "sec-fetch-site": "same-origin"}
    assert _chamar(painel.app, proprio, corpo)[1] >= 1


def test_campo_ou_arquivo_a_mais_e_400(painel: Painel, extraidos: list[pdf.Lido]) -> None:
    dados = montar_pdf([MARCA])
    corpo, tipo = _multipart(dados, {"outro": "x"})
    com_campo = painel.http.post(
        CURRICULO, content=corpo, headers={"content-type": tipo, CABECALHO_CSRF: painel.token}
    )
    assert com_campo.status_code == 400
    dois = painel.http.post(
        CURRICULO,
        files=[
            ("curriculo", ("a.pdf", dados, "application/pdf")),
            ("curriculo", ("b.pdf", dados, "application/pdf")),
        ],
        headers={CABECALHO_CSRF: painel.token},
    )
    assert dois.status_code == 400
    assert extraidos == []
    assert painel.enviar(dados).status_code == 200  # controle: um arquivo só passa


def test_formulario_comum_segue_com_o_token_no_corpo(painel: Painel) -> None:
    # o formulário sem JavaScript (urlencoded) continua valendo pelo campo `csrf_token`
    resposta = painel.http.post(PERFIL, data={CAMPO_CSRF: painel.token, "habilidades": "Python"})
    assert resposta.status_code == 303


# ------------------------------------------------------------------ guardas


def _arquivos(raiz: Path) -> Iterator[Path]:
    return (p for p in raiz.rglob("*") if p.is_file())


def test_nada_do_pdf_fica_na_pasta_de_dados_nem_no_banco(
    painel: Painel, extraidos: list[pdf.Lido]
) -> None:
    dados = montar_pdf([MARCA])
    assert painel.enviar(dados).status_code == 200
    # controle: o texto chegou à extração, então a busca abaixo o acharia se ele ficasse
    assert [lido.texto for lido in extraidos] == [MARCA]
    assert MARCA.encode() in dados
    for arquivo in _arquivos(painel.dados):
        conteudo = arquivo.read_bytes()
        assert MARCA.encode() not in conteudo, arquivo
        assert MARCA.encode("utf-16-le") not in conteudo, arquivo
    with closing(abrir(painel.banco)) as con:
        despejo = "\n".join(con.iterdump())
    assert MARCA not in despejo


def test_temporario_do_upload_some_ao_fim_do_pedido(
    painel: Painel, extraidos: list[pdf.Lido], monkeypatch: pytest.MonkeyPatch
) -> None:
    criados: list[Any] = []

    class Gravado(tempfile.SpooledTemporaryFile):  # type: ignore[type-arg]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            criados.append(self)

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", Gravado)
    dados = montar_pdf([MARCA], enchimento=1024 * 1024 + 1)  # acima de 1 MB vai ao disco
    assert painel.enviar(dados).status_code == 200
    assert [lido.texto for lido in extraidos] == [MARCA]
    assert len(criados) == 1
    assert criados[0]._rolled  # controle: foi mesmo ao disco
    assert criados[0].closed
