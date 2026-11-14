"""Assistente de primeira execução: busca, segundo plano e fim (desenho 13.6; plano T53).

O segundo plano e o systemd são falsos: nenhum teste chama `systemctl` nem `distrobox` de verdade,
e o `subprocess.run` é trocado por uma armadilha. O `HOME` do teste é uma pasta temporária.
"""

import json
import os
import subprocess
import time
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.segundo_plano_falso import FalsoSistema
from jobot.banco import buscas
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.modelo import Busca, Local, Modalidade, Nivel
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema import segundo_plano_linux
from jobot.sistema.segundo_plano_linux import Resultado

PORTA = 47617
PASSO_1 = "/primeira-execucao/1"
PASSO_2 = "/primeira-execucao/2"
ALERTA = 'role="alert"'


class Cenario:
    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
        self.casa = tmp_path / "casa"
        self.casa.mkdir()
        self.sistema = FalsoSistema(home=str(self.casa))
        self.app: FastAPI = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso()
        self.app.state.rodar_comando = self.sistema
        self.app.state.ambiente = {"HOME": str(self.casa)}
        self.app.state.plataforma = "linux"
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )

    def na_distrobox(self, nome: str = "fedora-dev") -> None:
        self.app.state.ambiente = {"HOME": str(self.casa), "CONTAINER_ID": nome}

    def get(self, url: str, **kw: Any) -> Any:
        return self.http.get(url, **kw)

    def post(self, url: str, dados: dict[str, Any] | None = None, **kw: Any) -> Any:
        token: str = self.app.state.csrf
        return self.http.post(url, data={CAMPO_CSRF: token, **(dados or {})}, **kw)

    def config(self, chave: str) -> object:
        with closing(abrir(self.banco)) as con:
            linha = con.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
        return None if linha is None else json.loads(linha[0])

    def gravar_config(self, chave: str, valor: object) -> None:
        with closing(abrir(self.banco)) as con:
            con.execute(
                "INSERT INTO config (chave, valor) VALUES (?, ?)", (chave, json.dumps(valor))
            )
            con.commit()

    def buscas(self) -> list[Busca]:
        with closing(abrir(self.banco)) as con:
            return buscas.buscas(con)

    @property
    def servico(self) -> Path:
        return self.casa / ".config" / "systemd" / "user" / "jobot.service"

    @property
    def atalho(self) -> Path:
        return self.casa / ".local" / "share" / "applications" / "jobot.desktop"


@pytest.fixture(autouse=True)
def _sem_comando_de_verdade(monkeypatch: pytest.MonkeyPatch) -> None:
    def armadilha(*args: object, **kw: object) -> None:
        raise AssertionError(f"comando de verdade num teste: {args!r}")

    monkeypatch.setattr(subprocess, "run", armadilha)


@pytest.fixture
def cenario(tmp_path: Path) -> Cenario:
    return Cenario(tmp_path)


@pytest.fixture
def fuso_fora_de_utc() -> Iterator[None]:
    antigo = os.environ.get("TZ")
    os.environ["TZ"] = "Pacific/Auckland"  # UTC+13 em novembro
    time.tzset()
    yield
    if antigo is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = antigo
    time.tzset()


def _redireciona(resposta: Any, destino: str) -> None:
    assert resposta.status_code == 303
    assert resposta.headers.get("location") == destino


COMPLETO = {
    "cargos": "Python\nDados",
    "cidade": ["Curitiba", "", ""],
    "uf": ["PR", "", ""],
    "modalidades": "remoto",
    "niveis": "junior",
    "salario_min": "5.000,50",
    "moeda": "BRL",
    "idiomas": "pt",
}


# --- entrada ----------------------------------------------------------------------------------


def test_raiz_sem_a_chave_vai_para_o_passo_1(cenario: Cenario) -> None:
    resposta = cenario.get("/")
    _redireciona(resposta, PASSO_1)


def test_passo1_mostra_o_formulario(cenario: Cenario) -> None:
    resposta = cenario.get(PASSO_1)
    assert resposta.status_code == 200
    html = resposta.text
    assert f'action="{PASSO_1}"' in html
    for campo in ("cargos", "cidade", "uf", "modalidades", "niveis", "salario_min", "moeda"):
        assert f'name="{campo}"' in html
    assert 'name="pular"' in html
    assert 'name="csrf_token"' in html


@pytest.mark.parametrize("passo", ["0", "3", "abc", "1x", "-1"])
def test_passo_que_nao_existe_da_404(cenario: Cenario, passo: str) -> None:
    assert cenario.get(f"/primeira-execucao/{passo}").status_code == 404
    assert cenario.post(f"/primeira-execucao/{passo}").status_code == 404


@pytest.mark.parametrize("passo", [PASSO_1, PASSO_2])
def test_sem_csrf_403_e_nada_grava(cenario: Cenario, passo: str) -> None:
    resposta = cenario.http.post(passo, data={"cargos": "Python", "segundo_plano": "ligar"})
    assert resposta.status_code == 403
    assert cenario.buscas() == []
    assert cenario.config("primeira_execucao_concluida") is None
    assert cenario.sistema.chamadas == []


# --- passo 1 ----------------------------------------------------------------------------------


def test_passo1_grava_a_busca_e_mostra_o_resumo(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, COMPLETO | {"modalidades": ["remoto"], "idiomas": ["pt"]})
    assert resposta.status_code == 303
    (busca,) = cenario.buscas()
    assert resposta.headers["location"] == f"{PASSO_2}?busca={busca.id}"
    assert busca.nome == "Minha primeira busca"
    assert busca.ativa
    assert busca.cargos == ("Python", "Dados")
    assert busca.cidades == (Local(cidade="Curitiba", uf="PR", pais="BR"),)
    assert busca.modalidades == (Modalidade.REMOTO,)
    assert busca.niveis == (Nivel.JUNIOR,)
    assert (busca.salario_min_centavos, busca.salario_moeda) == (500050, "BRL")
    assert busca.idiomas == ("pt",)

    html = cenario.get(resposta.headers["location"]).text
    resumo = html[html.index("data-resumo") :]
    for texto in (
        "Python",
        "Dados",
        "Curitiba, PR",
        "Remoto",
        "Júnior",
        "R$ 5.000,50",
        "Português",
    ):
        assert texto in resumo


def test_passo1_em_ingles_mostra_o_resumo_em_ingles(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, COMPLETO, headers={"Accept-Language": "en"})
    html = cenario.get(resposta.headers["location"], headers={"Accept-Language": "en"}).text
    resumo = html[html.index("data-resumo") :]
    assert "Remote" in resumo
    assert "Junior" in resumo
    assert "R$ 5,000.50" in resumo


def test_passo1_pular_nao_cria_busca(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, COMPLETO | {"pular": "1"})
    _redireciona(resposta, PASSO_2)
    assert cenario.buscas() == []
    assert "data-resumo" not in cenario.get(PASSO_2).text


def test_passo1_sem_nenhum_criterio_nao_cria_busca(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, {"cargos": "  \n ", "cidade": ["", ""], "uf": ["", ""]})
    _redireciona(resposta, PASSO_2)
    assert cenario.buscas() == []


@pytest.mark.parametrize(
    ("digitado", "centavos"),
    [
        ("5000", 500000),
        ("5.000", 500000),
        ("5.000,50", 500050),
        ("5000,5", 500050),
        ("1.234.567", 123456700),
    ],
)
def test_passo1_le_o_salario_minimo(cenario: Cenario, digitado: str, centavos: int) -> None:
    cenario.post(PASSO_1, {"cargos": "Python", "salario_min": digitado, "moeda": "BRL"})
    (busca,) = cenario.buscas()
    assert busca.salario_min_centavos == centavos


@pytest.mark.parametrize(
    "digitado", ["abc", "-5", "0", "0,00", "1e3", "5,000,00", "R$ 5000", "9" * 30]
)
def test_passo1_salario_invalido_volta_ao_formulario(cenario: Cenario, digitado: str) -> None:
    resposta = cenario.post(PASSO_1, COMPLETO | {"salario_min": digitado})
    assert resposta.status_code == 422
    assert ALERTA in resposta.text
    assert "Salário mínimo" in resposta.text
    assert "Python" in resposta.text  # o que foi digitado continua no formulário
    assert cenario.buscas() == []


def test_passo1_moeda_sem_cotacao_volta_ao_formulario(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, COMPLETO | {"moeda": "XYZ"})
    assert resposta.status_code == 422
    assert ALERTA in resposta.text
    assert cenario.buscas() == []


def test_passo1_aceita_moeda_estrangeira(cenario: Cenario) -> None:
    cenario.post(PASSO_1, {"cargos": "Python", "salario_min": "3000", "moeda": "USD"})
    (busca,) = cenario.buscas()
    assert (busca.salario_min_centavos, busca.salario_moeda) == (300000, "USD")


def test_passo1_uf_invalida_volta_ao_formulario(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, COMPLETO | {"uf": ["ZZ", "", ""]})
    assert resposta.status_code == 422
    assert ALERTA in resposta.text
    assert cenario.buscas() == []


def test_passo1_cidade_sem_uf_e_uf_sem_cidade(cenario: Cenario) -> None:
    cenario.post(PASSO_1, {"cidade": ["Recife", ""], "uf": ["", "sp"]})
    (busca,) = cenario.buscas()
    assert busca.cidades == (
        Local(cidade="Recife", uf=None, pais=None),
        Local(cidade=None, uf="SP", pais="BR"),
    )


def test_passo1_valor_fora_da_lista_e_ignorado(cenario: Cenario) -> None:
    cenario.post(
        PASSO_1,
        {
            "cargos": "Python",
            "modalidades": ["remoto", "espacial"],
            "niveis": ["deus"],
            "idiomas": ["xx", "en"],
        },
    )
    (busca,) = cenario.buscas()
    assert busca.modalidades == (Modalidade.REMOTO,)
    assert busca.niveis == ()
    assert busca.idiomas == ("en",)


def test_passo1_cargos_sem_repeticao_e_no_maximo_20(cenario: Cenario) -> None:
    linhas = ["Python", "python,  PYTHON "] + [f"cargo {n}" for n in range(30)]
    cenario.post(PASSO_1, {"cargos": "\n".join(linhas)})
    (busca,) = cenario.buscas()
    assert len(busca.cargos) == 20
    assert busca.cargos[:2] == ("Python", "cargo 0")


def test_resumo_escapa_o_que_a_pessoa_digitou(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, {"cargos": "<script>alert(1)</script>"})
    html = cenario.get(resposta.headers["location"]).text
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;alert(1)" in html


@pytest.mark.parametrize("busca", ["abc", "0", "999999", "-1", "9" * 30])
def test_passo2_com_busca_invalida_na_url_nao_mostra_resumo(cenario: Cenario, busca: str) -> None:
    resposta = cenario.get(f"{PASSO_2}?busca={busca}")
    assert resposta.status_code == 200
    assert "data-resumo" not in resposta.text


def test_passo1_passa_o_dia_local_ao_criar_a_busca(
    cenario: Cenario, fuso_fora_de_utc: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    agora = datetime(2026, 11, 13, 23, 0, tzinfo=UTC)  # em Auckland já é dia 14
    cenario.app.state.relogio = RelogioFalso(agora)
    chamadas: list[tuple[datetime, dict[str, Any]]] = []
    real = buscas.criar_busca

    def espiao(con: Any, busca: Busca, quando: datetime, **kw: Any) -> int:
        chamadas.append((quando, kw))
        return real(con, busca, quando, **kw)

    monkeypatch.setattr(buscas, "criar_busca", espiao)
    assert cenario.post(PASSO_1, {"cargos": "Python"}).status_code == 303
    ((quando, kw),) = chamadas
    assert quando == agora
    assert quando.utcoffset() is not None
    assert kw["hoje"] == date(2026, 11, 14)
    assert kw["hoje"] != quando.date()  # o dia em UTC seria o 13
    assert kw["regras_ligadas"] is True


# --- passo 2 ----------------------------------------------------------------------------------


def test_passo2_dentro_da_distrobox_diz_o_container(cenario: Cenario) -> None:
    cenario.na_distrobox("fedora-dev")
    html = cenario.get(PASSO_2).text
    assert 'data-container="fedora-dev"' in html
    assert "fedora-dev" in html


def test_passo2_fora_da_distrobox_nao_fala_de_container(cenario: Cenario) -> None:
    assert "data-container" not in cenario.get(PASSO_2).text


def test_passo2_liga_o_segundo_plano(cenario: Cenario) -> None:
    cenario.na_distrobox("fedora-dev")
    resposta = cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1")
    assert ("enable", "--now", "jobot.service") in cenario.sistema.systemctl()
    assert "fedora-dev" in cenario.servico.read_text(encoding="utf-8")
    assert cenario.atalho.exists()
    assert cenario.config("segundo_plano") is True
    assert cenario.config("primeira_execucao_concluida") is True


def test_passo2_desligado_cria_atalho(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1")
    assert cenario.atalho.exists()  # DR-37
    assert "Exec=" in cenario.atalho.read_text(encoding="utf-8")
    assert not cenario.servico.exists()
    assert all(c[0] != "enable" for c in cenario.sistema.systemctl())
    assert cenario.config("segundo_plano") is False
    assert cenario.config("primeira_execucao_concluida") is True


def test_passo2_desligar_depois_de_ligado_desliga_o_servico(cenario: Cenario) -> None:
    cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    assert cenario.servico.exists()
    cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    assert ("disable", "--now", "jobot.service") in cenario.sistema.systemctl()
    assert not cenario.servico.exists()
    assert cenario.config("segundo_plano") is False


def test_passo2_recusa_no_meio_e_depois_desligar_limpa_o_servico(cenario: Cenario) -> None:
    # o ligar grava o arquivo do serviço antes do `enable --now`; a recusa deixa isso para trás
    cenario.sistema.falha_em["enable"] = Resultado(1, "", "boom")
    recusa = cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    assert ALERTA in recusa.text
    assert cenario.servico.exists()
    assert cenario.config("segundo_plano") is None  # a config não foi gravada
    resposta = cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1")
    assert ("disable", "--now", "jobot.service") in cenario.sistema.systemctl()
    assert not cenario.servico.exists()
    assert cenario.config("segundo_plano") is False


def test_passo2_recusa_e_erro_mantem_o_resumo_da_busca(
    cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    cenario.post(PASSO_1, COMPLETO)
    (busca,) = cenario.buscas()
    assert f'name="busca" value="{busca.id}"' in cenario.get(f"{PASSO_2}?busca={busca.id}").text
    cenario.sistema.systemd_ok = False
    recusa = cenario.post(PASSO_2, {"segundo_plano": "ligar", "busca": str(busca.id)})
    assert "data-resumo" in recusa.text
    assert "Dados" in recusa.text
    assert f'name="busca" value="{busca.id}"' in recusa.text  # a segunda tentativa também leva

    def quebrar(*args: object, **kw: object) -> None:
        raise PermissionError("sem permissão")

    monkeypatch.setattr(segundo_plano_linux, "ligar", quebrar)
    erro = cenario.post(PASSO_2, {"segundo_plano": "ligar", "busca": str(busca.id)})
    assert "data-resumo" in erro.text
    assert "Dados" in erro.text


def test_passo2_sem_escolha_valida_nao_conclui(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_2, {"segundo_plano": "talvez"})
    assert resposta.status_code == 422
    assert cenario.config("primeira_execucao_concluida") is None
    assert cenario.sistema.chamadas == []


RECUSAS = {
    "sem_host_exec": (
        "não consegui falar com o sistema de fora: faltam "
        "o distrobox-host-exec ou o distrobox-enter",
        "could not reach the host system: distrobox-host-exec or distrobox-enter is missing",
    ),
    "systemd_nao_responde": (
        "o systemd do usuário não responde",
        "the user systemd is not responding",
    ),
    "home_diferente": (
        "a pasta pessoal do container não é a do sistema",
        "the container home folder is not the host home folder",
    ),
    "systemctl_falhou": (
        "o systemctl daemon-reload falhou: Failed to connect to bus",
        "systemctl daemon-reload failed: Failed to connect to bus",
    ),
}


def _provocar(cenario: Cenario, motivo: str) -> None:
    if motivo == "sem_host_exec":
        cenario.na_distrobox()
        cenario.sistema.tem_enter = False
    elif motivo == "systemd_nao_responde":
        cenario.sistema.systemd_ok = False
    elif motivo == "home_diferente":
        cenario.na_distrobox()
        cenario.sistema.home = "/outra/pasta"
    else:
        cenario.sistema.falha_em["daemon-reload"] = Resultado(1, "", "Failed to connect to bus")


@pytest.mark.parametrize("motivo", sorted(RECUSAS))
@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_passo2_recusa_mostra_o_motivo_traduzido(
    cenario: Cenario, motivo: str, idioma: str
) -> None:
    _provocar(cenario, motivo)
    resposta = cenario.post(
        PASSO_2, {"segundo_plano": "ligar"}, headers={"Accept-Language": idioma}
    )
    assert resposta.status_code == 200
    assert ALERTA in resposta.text
    assert RECUSAS[motivo][0 if idioma == "pt" else 1] in resposta.text
    assert f"segundo_plano.{motivo}" not in resposta.text  # nunca a chave crua
    assert cenario.config("primeira_execucao_concluida") is None
    assert cenario.config("segundo_plano") is None


def test_passo2_recusa_deixa_escolher_de_novo(cenario: Cenario) -> None:
    cenario.sistema.systemd_ok = False
    recusa = cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    assert 'name="segundo_plano"' in recusa.text
    resposta = cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    assert resposta.status_code == 303
    assert cenario.config("primeira_execucao_concluida") is True


def test_passo2_erro_do_sistema_de_arquivos_nao_estoura(
    cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    def quebrar(*args: object, **kw: object) -> None:
        raise PermissionError("sem permissão")

    monkeypatch.setattr(segundo_plano_linux, "ligar", quebrar)
    resposta = cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    assert resposta.status_code == 200
    assert ALERTA in resposta.text
    assert "sem permissão" in resposta.text
    assert cenario.config("primeira_execucao_concluida") is None


def test_fora_do_linux_o_passo2_vem_desativado(cenario: Cenario) -> None:
    cenario.app.state.plataforma = "darwin"
    html = cenario.get(PASSO_2).text
    assert "data-desativado" in html
    resposta = cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1")
    assert cenario.sistema.chamadas == []
    assert not cenario.atalho.exists()
    assert cenario.config("segundo_plano") is False
    assert cenario.config("primeira_execucao_concluida") is True


def test_no_linux_o_passo2_nao_vem_desativado(cenario: Cenario) -> None:
    assert "data-desativado" not in cenario.get(PASSO_2).text


# --- fim --------------------------------------------------------------------------------------


def test_fim_oferece_buscar_agora_e_vai_para_destaques(cenario: Cenario) -> None:
    cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    html = cenario.get(f"{PASSO_2}?feito=1").text
    assert 'method="post" action="/buscar-agora"' in html
    assert 'name="csrf_token"' in html
    assert 'href="/vagas?aba=destaques"' in html
    assert cenario.get("/").headers["location"] == "/vagas?aba=destaques"


def test_fim_sem_ter_concluido_mostra_o_passo_2(cenario: Cenario) -> None:
    html = cenario.get(f"{PASSO_2}?feito=1").text
    assert "/buscar-agora" not in html
    assert 'name="segundo_plano"' in html


def test_catalogos_do_assistente_tem_as_mesmas_chaves_e_o_texto_do_sistema() -> None:
    base = Path(__file__).parents[2] / "src" / "jobot" / "painel" / "i18n"
    pt = json.loads((base / "pt" / "primeira_execucao.json").read_text(encoding="utf-8"))
    en = json.loads((base / "en" / "primeira_execucao.json").read_text(encoding="utf-8"))
    assert set(pt) == set(en)
    for chave, texto in segundo_plano_linux._TEXTOS.items():
        assert pt[chave] == texto  # o pt é igual ao texto da linha de comando
        assert en[chave] != pt[chave]
    assert "{comando}" in en["segundo_plano.systemctl_falhou"]
    assert "{saida}" in en["segundo_plano.systemctl_falhou"]
