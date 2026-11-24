"""Leitura do currículo em PDF num processo filho (desenho 8 da fase 4; plano T435; D231).

Os PDFs são montados aqui (`apoio.pdf`), com dados reservados; nenhum PDF é versionado. O prazo se
prova com lançador e relógio injetados, sem esperar tempo real.
"""

import faulthandler
import io
import json
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from apoio.pdf import montar_pdf
from jobot.sistema import pdf, processo

RAIZ = Path(__file__).resolve().parents[2]


class FilhoFalso:
    """Filho que só responde com `saida` (ou nunca, se `None`); conta o que recebeu. Toda espera
    tem de vir com o `timeout` curto: sem ele, um filho real travado seguraria o servidor."""

    def __init__(self, saida: bytes | None, codigo: int = 0, erro: BaseException | None = None):
        self.pid = 4242
        self.returncode: int | None = None
        self._saida = saida
        self._codigo = codigo
        self._erro = erro
        self.entradas: list[bytes | None] = []

    def communicate(
        self, input: bytes | None = None, timeout: float | None = None
    ) -> tuple[bytes, None]:
        self.entradas.append(input)
        assert timeout == pdf._FATIA_S
        if self._erro is not None:
            raise self._erro
        if self._saida is None:
            raise subprocess.TimeoutExpired("python", timeout or 0)
        self.returncode = self._codigo
        return self._saida, None


def _relogio(passo: float) -> Iterator[float]:
    agora = 0.0
    while True:
        yield agora
        agora += passo


@pytest.fixture
def encerrados(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    lista: list[Any] = []
    monkeypatch.setattr(processo, "encerrar_arvore", lambda filho, espera=15.0: lista.append(filho))
    return lista


def test_texto_lido_pelo_processo_filho() -> None:
    lido = pdf.ler(montar_pdf(["Analista de dados Python", "Curso de SQL"]))
    assert lido == pdf.Lido(texto="Analista de dados Python\nCurso de SQL", paginas=2, total=2)


def test_aviso_volta_do_processo_filho() -> None:
    with pytest.raises(pdf.AvisoPdf) as erro:
        pdf.ler(montar_pdf(["segredo"], senha="abre-te"))
    assert erro.value.aviso == "senha"


def test_mais_de_vinte_paginas_le_so_as_vinte_primeiras() -> None:
    total = pdf.MAX_PAGINAS + 5
    resultado = pdf.ler_bytes(montar_pdf([f"pagina {n:02d}" for n in range(1, total + 1)]))
    assert resultado["paginas"] == pdf.MAX_PAGINAS == 20
    assert resultado["total"] == total
    texto = str(resultado["texto"])
    assert "pagina 01" in texto and "pagina 20" in texto
    assert "pagina 21" not in texto and f"pagina {total}" not in texto


@pytest.mark.parametrize(
    ("dados", "aviso"),
    [
        (montar_pdf([None]), "so_imagem"),
        (montar_pdf([None, "   "]), "so_imagem"),
        (montar_pdf(["segredo"], senha="abre-te"), "senha"),
        (b"%PDF-1.7\n1 0 obj lixo sem fim", "corrompido"),
        (montar_pdf(["Analista"])[:200], "corrompido"),
        (b"Curriculo em texto, nao em PDF", "nao_pdf"),
        (b"", "nao_pdf"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "nao_pdf"),
        (b"x" * 1024 + montar_pdf(["Analista"]), "nao_pdf"),
    ],
    ids=[
        "so_imagem",
        "espacos",
        "senha",
        "corrompido",
        "cortado",
        "texto",
        "vazio",
        "png",
        "longe",
    ],
)
def test_avisos_proprios(dados: bytes, aviso: str) -> None:
    assert pdf.ler_bytes(dados) == {"aviso": aviso}


def test_pdf_cifrado_sem_senha_de_abrir_e_lido() -> None:
    # controle do aviso de senha: só a senha de dono (comum em PDF exportado) não impede a leitura
    resultado = pdf.ler_bytes(montar_pdf(["Analista"], dono="so-o-dono"))
    assert resultado == {"texto": "Analista", "paginas": 1, "total": 1}


# Sem o `cryptography` (só vem no Linux, pelo `keyring`), o `pypdf` não abre AES-256 nem AES sem
# senha de abrir: o aviso é `protegido`, não `corrompido` (D231.1). O AES-128 com senha de abrir se
# confere sem ele (MD5 e RC4) e dá `senha`. Montar o AES pede o `cryptography`.
_AES = [
    ("AES-128", "abre-te", None, "senha"),
    ("AES-256", "abre-te", None, "protegido"),
    ("AES-128", None, "so-o-dono", "protegido"),
    ("AES-256", None, "so-o-dono", "protegido"),
]
_IDS_AES = ["128_senha", "256_senha", "128_dono", "256_dono"]


def _pdf_aes(algoritmo: str, senha: str | None, dono: str | None) -> bytes:
    pytest.importorskip("cryptography")
    return montar_pdf(["Analista"], senha=senha, dono=dono, algoritmo=algoritmo)


@pytest.mark.parametrize(("algoritmo", "senha", "dono", "aviso"), _AES, ids=_IDS_AES)
def test_aes_sem_cryptography_da_aviso_de_protegido(
    algoritmo: str, senha: str | None, dono: str | None, aviso: str
) -> None:
    dados = _pdf_aes(algoritmo, senha, dono)
    # o filho de verdade, com o `cryptography` bloqueado antes de o `pypdf` escolher a cifra
    codigo = (
        "import sys; sys.modules['cryptography'] = None; from jobot.sistema import pdf; pdf.main()"
    )
    feito = subprocess.run(
        [sys.executable, "-P", "-c", codigo], input=dados, capture_output=True, timeout=60
    )
    assert json.loads(feito.stdout) == {"aviso": aviso}


@pytest.mark.parametrize(("algoritmo", "senha", "dono", "aviso"), _AES, ids=_IDS_AES)
def test_aes_com_cryptography_le_ou_pede_senha(
    algoritmo: str, senha: str | None, dono: str | None, aviso: str
) -> None:
    # controle da anterior: com o `cryptography`, só a senha de abrir impede a leitura
    resultado = pdf.ler_bytes(_pdf_aes(algoritmo, senha, dono))
    if senha:
        assert resultado == {"aviso": "senha"}
    else:
        assert resultado == {"texto": "Analista", "paginas": 1, "total": 1}


def test_texto_do_filho_tem_teto_e_sai_em_utf8_valido(monkeypatch: pytest.MonkeyPatch) -> None:
    import pypdf

    class Pagina:
        def extract_text(self) -> str:
            return "a\ud800" + "b" * pdf.TETO_TEXTO  # surrogate solto e texto demais

    class Leitor:
        is_encrypted = False
        pages = [Pagina(), Pagina()]

        def __init__(self, fluxo: object) -> None: ...

    monkeypatch.setattr(pypdf, "PdfReader", Leitor)
    resultado = pdf.ler_bytes(b"%PDF-1.7")
    texto = str(resultado["texto"])
    assert len(texto) == pdf.TETO_TEXTO == 200_000
    assert texto.startswith("a?b")
    json.dumps(resultado).encode("utf-8")  # sem surrogate solto, o UTF-8 não quebra
    assert (resultado["paginas"], resultado["total"]) == (2, 2)


def test_filho_lancado_isolado_e_em_grupo_proprio(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[list[str], dict[str, Any]]] = []

    filho = object()

    def espiao(argv: list[str], **kw: Any) -> object:
        chamadas.append((argv, kw))
        return filho

    monkeypatch.setattr(subprocess, "Popen", espiao)
    assert pdf._lancar() is filho
    assert chamadas == [
        (
            [sys.executable, "-P", "-m", "jobot.sistema.pdf"],
            {
                "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.DEVNULL,
                **processo.destacar(),
            },
        )
    ]
    assert processo.destacar()  # controle: há o que conferir (sessão ou grupo próprio)


def test_filho_tem_vigia_proprio(monkeypatch: pytest.MonkeyPatch) -> None:
    # se o servidor morre sem levar o filho, o vigia em C o encerra depois do prazo
    vigias: list[tuple[float, bool]] = []
    monkeypatch.setattr(
        faulthandler,
        "dump_traceback_later",
        lambda prazo, repeat=False, file=None, exit=False: vigias.append((prazo, exit)),
    )
    saida = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"nada")))
    monkeypatch.setattr(sys, "stdout", saida)
    pdf.main()
    assert vigias == [(pdf.PRAZO_S + 5, True)]
    assert json.loads(saida.getvalue()) == {"aviso": "nao_pdf"}


def test_prazo_encerra_a_arvore_do_filho(encerrados: list[Any]) -> None:
    filho = FilhoFalso(None)
    relogio = _relogio(10.0)  # 0, 10, 20, 30: o prazo de 30 s vence na quarta olhada
    with pytest.raises(pdf.AvisoPdf) as erro:
        pdf.ler(b"%PDF-1.7", lancar=lambda: filho, agora=lambda: next(relogio))
    assert erro.value.aviso == "prazo"
    assert encerrados == [filho]
    # o PDF vai uma vez só, na primeira espera; as seguintes só leem a saída
    assert filho.entradas == [b"%PDF-1.7", None, None]


def test_antes_do_prazo_espera_a_resposta(encerrados: list[Any]) -> None:
    respostas: list[bytes | None] = [None, None, json.dumps({"aviso": "senha"}).encode()]

    class Lento(FilhoFalso):
        def communicate(
            self, input: bytes | None = None, timeout: float | None = None
        ) -> tuple[bytes, None]:
            self._saida = respostas.pop(0)
            return super().communicate(input, timeout)

    filho = Lento(None)
    relogio = _relogio(14.0)  # 0, 14, 28: ainda dentro dos 30 s
    with pytest.raises(pdf.AvisoPdf) as erro:
        pdf.ler(b"%PDF-1.7", lancar=lambda: filho, agora=lambda: next(relogio))
    assert erro.value.aviso == "senha"
    assert encerrados == []


def test_interrompido_encerra_o_filho_e_relanca(encerrados: list[Any]) -> None:
    filho = FilhoFalso(None, erro=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        pdf.ler(b"%PDF-1.7", lancar=lambda: filho, agora=lambda: 0.0)
    assert encerrados == [filho]


@pytest.mark.parametrize(
    ("saida", "codigo"),
    [
        (b"nao e json", 0),
        (b'{"texto": 3, "paginas": 1, "total": 1}', 0),
        (b'{"aviso": "inventado"}', 0),
        (b'{"texto": "ok", "paginas": 1, "total": 1}', 1),
        (b"", -9),
    ],
    ids=["lixo", "tipo", "aviso_desconhecido", "saiu_com_erro", "morto"],
)
def test_resposta_estranha_do_filho_e_corrompido(
    saida: bytes, codigo: int, encerrados: list[Any]
) -> None:
    with pytest.raises(pdf.AvisoPdf) as erro:
        pdf.ler(b"%PDF-1.7", lancar=lambda: FilhoFalso(saida, codigo), agora=lambda: 0.0)
    assert erro.value.aviso == "corrompido"


def test_resposta_certa_do_filho_falso() -> None:
    # controle da anterior: a mesma montagem com a resposta certa vira `Lido`
    saida = json.dumps({"texto": "ok", "paginas": 1, "total": 3}).encode()
    lido = pdf.ler(b"%PDF-1.7", lancar=lambda: FilhoFalso(saida), agora=lambda: 0.0)
    assert lido == pdf.Lido(texto="ok", paginas=1, total=3)


def test_pypdf_fixado_no_pyproject() -> None:
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert "pypdf==7.1.1" in pyproject["project"]["dependencies"]
