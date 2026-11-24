"""Assistente de primeira execução: busca, segundo plano e fim (desenho 13.6; plano T53).

O segundo plano e o systemd são falsos: nenhum teste chama `systemctl` nem `distrobox` de verdade,
e o `subprocess.run` é trocado por uma armadilha. O `HOME` do teste é uma pasta temporária.
"""

import html as html_lib
import json
import os
import re
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

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from apoio.segundo_plano_falso import FalsoAgendador, FalsoLaunchctl, FalsoSistema
from apoio.semear import inserir_vaga
from apoio.site_falso import LeitorFalso
from jobot.banco import buscas, cadastros, perfil
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao
from jobot.banco.migrar import migrar
from jobot.nucleo.ia.contrato import Pedido, Resposta, limites
from jobot.nucleo.ia.falso import BackendFalso
from jobot.nucleo.modelo import Busca, Local, Modalidade, Nivel
from jobot.painel.app import criar_app
from jobot.painel.rotas.ia import Teste
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema import segundo_plano_linux
from jobot.sistema.cofre import Cofre
from jobot.sistema.segundo_plano_linux import Resultado

PORTA = 47617
PASSO_IA = "/primeira-execucao/ia"
PASSO_PERFIL = "/primeira-execucao/perfil"
PASSO_1 = "/primeira-execucao/1"
PASSO_2 = "/primeira-execucao/2"
PULAR = "/primeira-execucao/pular"
SITES = "/primeira-execucao/sites"
INTERRUPTOR = "/configuracoes/contas/falso_logado/interruptor"
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
        self.app.state.leitores = ()  # sem leitor o assistente é o de hoje; o caso novo liga um
        self.cofre = Cofre(tmp_path, CofreFalso())
        self.app.state.cofre = self.cofre
        self.app.state.modelo_local = lambda: None
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )

    def com_leitor(self) -> None:
        leitor = LeitorFalso(base="http://127.0.0.1:9")
        with closing(abrir(self.banco)) as con:
            cadastros.semear(con)
            cadastros.semear_leitores(con, [leitor])
        self.app.state.leitores = (leitor,)
        self.app.state.navegador_instalado = None

    def ligadas(self) -> list[str]:
        with closing(abrir(self.banco)) as con:
            return cadastros.fontes_com_login_ligadas(con)

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


def test_raiz_sem_a_chave_vai_para_o_passo_da_ia(cenario: Cenario) -> None:
    resposta = cenario.get("/")
    _redireciona(resposta, PASSO_IA)


def test_passo1_mostra_o_formulario(cenario: Cenario) -> None:
    resposta = cenario.get(PASSO_1)
    assert resposta.status_code == 200
    html = resposta.text
    assert f'action="{PASSO_1}"' in html
    for campo in ("cargos", "cidade", "uf", "modalidades", "niveis", "salario_min", "moeda"):
        assert f'name="{campo}"' in html
    assert f'formaction="{PULAR}"' in html
    assert 'name="csrf_token"' in html


@pytest.mark.parametrize("passo", ["0", "3", "abc", "1x", "-1"])
def test_passo_que_nao_existe_da_404(cenario: Cenario, passo: str) -> None:
    assert cenario.get(f"/primeira-execucao/{passo}").status_code == 404
    assert cenario.post(f"/primeira-execucao/{passo}").status_code == 404


@pytest.mark.parametrize("passo", [PASSO_1, PASSO_2, PULAR])
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


def _pais_marcado(html: str) -> str:
    select = re.search(r'<select\b[^>]*name="meu_pais".*?</select>', html, re.DOTALL)
    assert select is not None
    (marcado,) = re.findall(r'<option value="([A-Z]{2})"[^>]*\sselected', select.group(0))
    return str(marcado)


def test_passo1_marca_o_pais_do_accept_language(cenario: Cenario) -> None:
    assert _pais_marcado(cenario.get(PASSO_1, headers={"Accept-Language": "en-GB"}).text) == "GB"
    assert _pais_marcado(cenario.get(PASSO_1).text) == "BR"
    html = cenario.get(PASSO_1).text
    assert "Alemanha" in html_lib.unescape(html)


def test_passo1_grava_meu_pais_antes_da_busca(cenario: Cenario) -> None:
    with closing(abrir(cenario.banco)) as con:
        vaga = inserir_vaga(con, modalidade="remoto", avisos='["restrito_a_pais"]')
        con.execute(
            "INSERT INTO local_vaga (vaga_id, cidade, uf, pais) VALUES (?, NULL, NULL, 'PT')",
            (vaga,),
        )
        con.commit()
    resposta = cenario.post(PASSO_1, {"cargos": "Python", "meu_pais": "PT"})
    assert resposta.status_code == 303
    assert cenario.config("meu_pais") == "PT"
    (busca,) = cenario.buscas()
    with closing(abrir(cenario.banco)) as con:
        oculta = con.execute(
            "SELECT oculta_motivo FROM encaixe WHERE busca_id = ? AND vaga_id = ?",
            (busca.id, vaga),
        ).fetchone()
    assert oculta is not None
    assert oculta[0] is None  # com Meu país = BR a vaga de PT ficaria oculta por `pais`


@pytest.mark.parametrize(
    "dados",
    [
        {"cargos": "Python", "meu_pais": "XX"},
        {"cargos": "Python", "meu_pais": ""},
        {"cargos": "Python", "meu_pais": "pt"},
        {"cargos": "Python", "meu_pais": " PT"},
    ],
)
def test_passo1_recusa_pais_de_fora(cenario: Cenario, dados: dict[str, str]) -> None:
    assert cenario.post(PASSO_1, dados).status_code == 422
    assert cenario.config("meu_pais") is None
    assert cenario.buscas() == []
    controle = cenario.post(PASSO_1, dados | {"meu_pais": "PT"})  # a mesma entrada, país da lista
    assert controle.status_code == 303
    assert cenario.config("meu_pais") == "PT"


def test_voltar_ao_passo_1_e_trocar_o_pais_recalcula_o_encaixe_das_buscas(
    cenario: Cenario,
) -> None:
    with closing(abrir(cenario.banco)) as con:
        vaga = inserir_vaga(con, modalidade="remoto", avisos='["restrito_a_pais"]')
        con.execute(
            "INSERT INTO local_vaga (vaga_id, cidade, uf, pais) VALUES (?, NULL, NULL, 'PT')",
            (vaga,),
        )
        cur = con.execute(
            "INSERT INTO busca (nome, criada_em) VALUES ('sem cidade', '2026-11-13T12:00:00+00:00')"
        )
        busca = int(cur.lastrowid or 0)
        con.commit()
        buscas.recalcular_encaixe(con, [busca], True, hoje=date(2026, 11, 13))

    def oculta() -> object:
        with closing(abrir(cenario.banco)) as con:
            linha = con.execute(
                "SELECT oculta_motivo FROM encaixe WHERE busca_id = ? AND vaga_id = ?",
                (busca, vaga),
            ).fetchone()
        assert linha is not None
        return linha[0]

    assert oculta() == "pais"  # controle: com Meu país = BR a vaga de PT fica oculta
    resposta = cenario.post(PASSO_1, {"busca": str(busca), "meu_pais": "PT"})  # critérios vazios
    _redireciona(resposta, f"{PASSO_2}?busca={busca}")
    assert cenario.config("meu_pais") == "PT"
    assert oculta() is None


def test_passo1_com_busca_invalida_nao_grava_meu_pais(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, {"cargos": "Python", "meu_pais": "PT", "salario_min": "abc"})
    assert resposta.status_code == 422
    assert cenario.config("meu_pais") is None
    assert cenario.buscas() == []


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


def test_voltar_ao_passo_1_edita_a_mesma_busca(
    cenario: Cenario, fuso_fora_de_utc: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    agora = datetime(2026, 11, 13, 23, 0, tzinfo=UTC)  # em Auckland já é dia 14
    cenario.app.state.relogio = RelogioFalso(agora)
    resposta = cenario.post(PASSO_1, COMPLETO | {"modalidades": ["remoto"], "idiomas": ["pt"]})
    (primeira,) = cenario.buscas()
    html = cenario.get(resposta.headers["location"]).text
    assert f'href="{PASSO_1}?busca={primeira.id}"' in html  # o link "voltar" leva o id

    formulario = cenario.get(f"{PASSO_1}?busca={primeira.id}").text
    assert "Python" in formulario  # o formulário volta preenchido
    assert "5000,50" in formulario
    assert f'name="busca" value="{primeira.id}"' in formulario

    chamadas: list[dict[str, Any]] = []
    real = buscas.editar_busca

    def espiao(con: Any, busca: Busca, **kw: Any) -> None:
        chamadas.append(kw)
        real(con, busca, **kw)

    monkeypatch.setattr(buscas, "editar_busca", espiao)
    segunda = cenario.post(
        PASSO_1, COMPLETO | {"cargos": "Rust", "busca": str(primeira.id), "idiomas": ["pt"]}
    )
    _redireciona(segunda, f"{PASSO_2}?busca={primeira.id}")
    (editada,) = cenario.buscas()  # continua uma busca só
    assert editada.id == primeira.id
    assert editada.cargos == ("Rust",)
    assert editada.nome == primeira.nome
    assert editada.criada_em == primeira.criada_em
    ((kw,),) = [(c,) for c in chamadas]
    assert kw["hoje"] == date(2026, 11, 14)
    assert kw["hoje"] != agora.date()  # o dia em UTC seria o 13


def test_voltar_ao_passo_1_com_busca_que_nao_existe_da_404_e_nao_cria(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_1, COMPLETO | {"busca": "999"})
    assert resposta.status_code == 404
    assert cenario.buscas() == []
    assert 'name="busca"' not in cenario.get(f"{PASSO_1}?busca=999").text


def test_voltar_ao_passo_1_com_salario_invalido_mantem_a_busca_no_formulario(
    cenario: Cenario,
) -> None:
    cenario.post(PASSO_1, COMPLETO)
    (busca,) = cenario.buscas()
    resposta = cenario.post(PASSO_1, COMPLETO | {"busca": str(busca.id), "salario_min": "abc"})
    assert resposta.status_code == 422
    assert f'name="busca" value="{busca.id}"' in resposta.text  # a nova tentativa também edita
    assert cenario.buscas() == [busca]


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


def test_nao_ligar_com_falha_conclui_com_aviso(cenario: Cenario) -> None:
    cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    assert cenario.servico.exists()
    cenario.sistema.falha_em["disable"] = Resultado(1, "", "boom")
    resposta = cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1&aviso=systemctl_falhou")  # D49 (b): não prende
    assert cenario.config("primeira_execucao_concluida") is True
    assert cenario.config("segundo_plano") is False
    assert "boom" not in cenario.get(resposta.headers["location"]).text  # a saída fica no log


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
        "O systemctl daemon-reload falhou. Os detalhes ficaram no jobot.log.",
        "systemctl daemon-reload failed. The details are in jobot.log.",
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
    assert "sem permissão" not in resposta.text  # o texto da exceção fica no log (D106)
    assert "Não consegui gravar os arquivos do serviço" in resposta.text
    assert cenario.config("primeira_execucao_concluida") is None


def test_fora_do_linux_o_passo2_vem_desativado(cenario: Cenario) -> None:
    cenario.app.state.plataforma = "freebsd14"  # nem Linux nem Windows
    html = cenario.get(PASSO_2).text
    assert "data-desativado" in html
    assert "chega numa próxima versão" in html
    resposta = cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1")
    assert cenario.sistema.chamadas == []
    assert not cenario.atalho.exists()
    assert cenario.config("segundo_plano") is False
    assert cenario.config("primeira_execucao_concluida") is True


def test_no_linux_o_passo2_nao_vem_desativado(cenario: Cenario) -> None:
    assert "data-desativado" not in cenario.get(PASSO_2).text


def _no_windows(cenario: Cenario) -> FalsoAgendador:
    agendador = FalsoAgendador()
    cenario.app.state.plataforma = "win32"
    cenario.app.state.rodar_comando = agendador
    return agendador


def test_no_windows_o_passo2_liga_pelo_agendador(cenario: Cenario) -> None:
    agendador = _no_windows(cenario)
    html = cenario.get(PASSO_2).text
    assert "data-desativado" not in html
    assert "próxima versão" not in html
    resposta = cenario.post(PASSO_2, {"segundo_plano": "ligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1")
    assert agendador.existe and agendador.chamadas[0][:2] == ("schtasks", "/Create")
    assert not cenario.atalho.exists()  # no Windows o atalho é do instalador
    assert cenario.config("segundo_plano") is True


def test_no_windows_nao_ligar_apaga_a_tarefa_sem_atalho(cenario: Cenario) -> None:
    agendador = _no_windows(cenario)
    agendador.existe = True
    resposta = cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1")
    assert not agendador.existe
    assert not cenario.atalho.exists()
    assert cenario.config("segundo_plano") is False


def test_no_windows_falha_ao_apagar_a_tarefa_avisa_sem_prender(cenario: Cenario) -> None:
    agendador = _no_windows(cenario)
    agendador.existe = True
    agendador.falha_em["/Delete"] = Resultado(1, erro="Acesso negado.")
    resposta = cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1&aviso=schtasks_falhou")
    fim = cenario.get(resposta.headers["location"]).text
    assert "o Agendador de Tarefas não conseguiu apagar a tarefa do joBot" in fim
    assert cenario.config("primeira_execucao_concluida") is True


def test_no_mac_falha_ao_tirar_o_servico_avisa_sem_prender(cenario: Cenario) -> None:
    launchctl = FalsoLaunchctl(carregado=True)
    cenario.app.state.plataforma = "darwin"
    cenario.app.state.rodar_comando = launchctl
    assert "próxima versão" not in cenario.get(PASSO_2).text
    launchctl.falha_em["bootout"] = Resultado(1, erro="Boot-out failed: 1")
    resposta = cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    _redireciona(resposta, f"{PASSO_2}?feito=1&aviso=launchctl_falhou")
    fim = cenario.get(resposta.headers["location"]).text
    assert "o launchd não conseguiu tirar o serviço do joBot" in fim
    assert not cenario.atalho.exists()  # no Mac o app vem do .dmg
    assert cenario.config("primeira_execucao_concluida") is True


# --- fim --------------------------------------------------------------------------------------


def test_fim_oferece_buscar_agora_e_vai_para_destaques(cenario: Cenario) -> None:
    cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    # o Buscar agora do fim é o da casca (T49, T107); o conteúdo só leva o link para as vagas
    html = cenario.get(f"{PASSO_2}?feito=1").text.split('id="conteudo"')[1]
    assert "/buscar-agora" not in html
    assert 'href="/vagas?aba=destaques"' in html
    assert cenario.get("/").headers["location"] == "/vagas?aba=destaques"


def test_tela_final_tem_um_so_botao_buscar_agora(cenario: Cenario) -> None:
    cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    html = cenario.get(f"{PASSO_2}?feito=1").text
    assert html.count('action="/buscar-agora"') == 1
    assert html.count(">Buscar agora<") == 1
    assert "Tudo pronto" in html


def test_fim_sem_ter_concluido_mostra_o_passo_2(cenario: Cenario) -> None:
    html = cenario.get(f"{PASSO_2}?feito=1").text
    # a casca de toda página tem o Buscar agora (T49); o do fim fica no conteúdo
    assert "/buscar-agora" not in html.split('id="conteudo"')[1]
    assert 'name="segundo_plano"' in html


def _carregar_sem_repetir(caminho: Path) -> dict[str, str]:
    def sem_repetir(pares: list[tuple[str, str]]) -> dict[str, str]:
        chaves = [chave for chave, _ in pares]
        repetidas = sorted({c for c in chaves if chaves.count(c) > 1})
        assert not repetidas, f"chave repetida em {caminho.name}: {repetidas}"
        return dict(pares)

    dados: dict[str, str] = json.loads(
        caminho.read_text(encoding="utf-8"), object_pairs_hook=sem_repetir
    )
    return dados


def test_carregar_sem_repetir_recusa_chave_repetida(tmp_path: Path) -> None:
    repetido = tmp_path / "repetido.json"
    repetido.write_text('{"a": "1", "b": "2", "a": "3"}', encoding="utf-8")
    with pytest.raises(AssertionError, match=r"chave repetida em repetido.json: \['a'\]"):
        _carregar_sem_repetir(repetido)
    limpo = tmp_path / "limpo.json"  # controle: sem repetição carrega
    limpo.write_text('{"a": "1", "b": "2"}', encoding="utf-8")
    assert _carregar_sem_repetir(limpo) == {"a": "1", "b": "2"}


def test_catalogos_do_assistente_tem_as_mesmas_chaves_e_o_texto_do_sistema() -> None:
    base = Path(__file__).parents[2] / "src" / "jobot" / "painel" / "i18n"
    pt = _carregar_sem_repetir(base / "pt" / "primeira_execucao.json")
    en = _carregar_sem_repetir(base / "en" / "primeira_execucao.json")
    assert set(pt) == set(en)
    # a linha de comando mostra a saída; a tela só diz onde achá-la (T159, T337)
    falhas = {f"segundo_plano.{p}_falhou" for p in ("systemctl", "schtasks", "launchctl")}
    for chave, texto in segundo_plano_linux._TEXTOS.items():
        if chave in falhas:
            assert "{saida}" in texto
            continue
        assert pt[chave] == texto  # o pt é igual ao texto da linha de comando
        assert en[chave] != pt[chave]
    for catalogo in (pt, en):
        for chave in falhas:
            assert "{comando}" in catalogo[chave]
            assert "{saida}" not in catalogo[chave]


@pytest.mark.parametrize(
    ("idioma", "trecho"),
    [("pt", "variações do mesmo cargo"), ("en", "variations of the same title")],
)
def test_passo1_dica_de_cargos_sugere_variacoes(cenario: Cenario, idioma: str, trecho: str) -> None:
    html = cenario.get(PASSO_1, headers={"Accept-Language": idioma}).text
    assert trecho in html
    assert "sysadmin" in html


# --- passo "Sites com login" (T241; D137.9 a D137.11 e D137.15) ---------------------------------


def _caminho_do_passo_1(cenario: Cenario, caminho: str) -> tuple[Any, str]:
    """A resposta do `POST` do passo 1 por cada um dos três caminhos, e o que ela leva na URL."""
    if caminho == "vazio":
        return cenario.post(PASSO_1, {"cargos": "  \n ", "cidade": ["", ""], "uf": ["", ""]}), ""
    if caminho == "criada":
        resposta = cenario.post(PASSO_1, COMPLETO)
        return resposta, f"?busca={cenario.buscas()[0].id}"
    cenario.post(PASSO_1, COMPLETO)
    (busca,) = cenario.buscas()
    resposta = cenario.post(PASSO_1, COMPLETO | {"cargos": "Rust", "busca": str(busca.id)})
    return resposta, f"?busca={busca.id}"


CAMINHOS_DO_PASSO_1 = ["vazio", "criada", "editada"]


@pytest.mark.parametrize("caminho", CAMINHOS_DO_PASSO_1)
def test_passo_1_vai_aos_sites_com_leitor(cenario: Cenario, caminho: str) -> None:
    cenario.com_leitor()
    resposta, busca = _caminho_do_passo_1(cenario, caminho)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith(SITES)
    assert ("busca=" in resposta.headers["location"]) == bool(busca)


@pytest.mark.parametrize("caminho", CAMINHOS_DO_PASSO_1)
def test_sem_leitor_o_assistente_nao_muda(cenario: Cenario, caminho: str) -> None:
    resposta, busca = _caminho_do_passo_1(cenario, caminho)
    _redireciona(resposta, PASSO_2 + busca)
    assert cenario.get(SITES).status_code == 404
    assert cenario.post(SITES, {"continuar": "1"}).status_code == 404


@pytest.mark.parametrize(
    ("idioma", "leitor", "url", "frase"),
    [
        ("pt", True, PASSO_IA, "Passo 1 de 5"),
        ("pt", True, PASSO_PERFIL, "Passo 2 de 5"),
        ("pt", True, PASSO_1, "Passo 3 de 5"),
        ("pt", True, SITES, "Passo 4 de 5"),
        ("pt", True, PASSO_2, "Passo 5 de 5"),
        ("en", True, SITES, "Step 4 of 5"),
        ("pt", False, PASSO_IA, "Passo 1 de 4"),
        ("pt", False, PASSO_PERFIL, "Passo 2 de 4"),
        ("pt", False, PASSO_1, "Passo 3 de 4"),
        ("pt", False, PASSO_2, "Passo 4 de 4"),
        ("en", False, PASSO_2, "Step 4 of 4"),
    ],
)
def test_contagem_de_passos(
    cenario: Cenario, idioma: str, leitor: bool, url: str, frase: str
) -> None:
    if leitor:
        cenario.com_leitor()
    html = cenario.get(url, headers={"Accept-Language": idioma}).text
    assert frase in html
    if url == PASSO_2:  # o último número é o do segundo plano, não o do passo da busca
        assert 'name="segundo_plano"' in html


def test_passo_sites_mostra_o_cartao(cenario: Cenario) -> None:
    cenario.com_leitor()
    html = cenario.get(SITES).text
    assert "Site falso" in html
    assert INTERRUPTOR in html and 'role="switch"' in html
    assert "/configuracoes/ferramentas/navegador/baixar" in html  # o fragmento da T240
    assert 'href="/configuracoes/ferramentas"' not in html  # o cartão está aqui, sem link
    assert 'id="status-sites"' in html
    assert "/static/css/configuracoes.css" in html
    assert "horarios" not in html  # os horários ficam em Configurações (D137.10)
    # T275 (D139.27): o mesmo cartão da aba Contas, com o selo, e o título de sempre
    assert re.search(r'<span class="selo selo-desligado">\s*Desligado\s*</span>', html)
    assert "Sites com login (opcional)" in html


@pytest.mark.parametrize("achado", [None, "chromium"])
def test_passo_sites_sem_navegador_desliga_o_login(cenario: Cenario, achado: str | None) -> None:
    """Desenho 5.7 (D166): sem navegador, o "Fazer login agora" do cartão sai desabilitado e
    descrito por uma frase do próprio passo, sem link para Ferramentas (o baixar está acima)."""
    cenario.com_leitor()
    cenario.app.state.navegador_instalado = achado
    html = cenario.get(SITES).text
    botao = re.search(
        r'<button\b[^>]*hx-post="/configuracoes/contas/falso_logado/login"[^>]*>', html
    )
    assert botao is not None
    frase = re.search(r'<p\b[^>]*\bid="contas-sem-navegador"[^>]*>([^<]*)</p>', html)
    if achado is None:
        assert re.search(r"\sdisabled[\s>]", botao[0])
        assert 'aria-describedby="contas-sem-navegador"' in botao[0]
        assert frase is not None and "baixe o navegador acima" in frase[1]
    else:
        assert "aria-describedby" not in botao[0] and frase is None


def test_continuar_segue_ao_segundo_plano(cenario: Cenario) -> None:
    cenario.com_leitor()
    cenario.post(PASSO_1, COMPLETO)
    (busca,) = cenario.buscas()
    resposta = cenario.post(SITES, {"continuar": "1", "busca": str(busca.id)})
    _redireciona(resposta, f"{PASSO_2}?busca={busca.id}")
    _redireciona(cenario.post(SITES, {"continuar": "1"}), PASSO_2)


def test_continuar_mantem_o_que_a_pessoa_ligou(cenario: Cenario) -> None:
    cenario.com_leitor()
    cenario.post(INTERRUPTOR, {"ligada": "on"})
    _redireciona(cenario.post(SITES, {"continuar": "1"}), PASSO_2)
    assert cenario.ligadas() == ["falso_logado"]


def test_busca_invalida_na_url_dos_sites_cai_fora(cenario: Cenario) -> None:
    cenario.com_leitor()
    cenario.post(PASSO_1, COMPLETO)
    (busca,) = cenario.buscas()
    existente = str(busca.id)
    # controle positivo: com a busca que existe o destino a leva
    _redireciona(
        cenario.post(SITES, {"continuar": "1", "busca": existente}), f"{PASSO_2}?busca={existente}"
    )
    html = cenario.get(f"{SITES}?busca={existente}").text
    assert f'name="busca" value="{existente}"' in html
    assert f'href="{PASSO_1}?busca={existente}"' in html
    for ruim in ("abc", "999", "0", "-1", "9" * 30):
        _redireciona(cenario.post(SITES, {"continuar": "1", "busca": ruim}), PASSO_2)
        html = cenario.get(f"{SITES}?busca={ruim}").text
        assert 'name="busca"' not in html
        assert f"{PASSO_1}?busca" not in html  # (o seletor de tema repete a URL do pedido)
        assert f'href="{PASSO_1}"' in html


def test_voltar_do_segundo_plano_vai_aos_sites(cenario: Cenario) -> None:
    cenario.com_leitor()
    cenario.post(PASSO_1, COMPLETO)
    (busca,) = cenario.buscas()
    segundo = cenario.get(f"{PASSO_2}?busca={busca.id}").text
    assert f'href="{SITES}?busca={busca.id}"' in segundo
    sites = cenario.get(f"{SITES}?busca={busca.id}").text
    assert f'href="{PASSO_1}?busca={busca.id}"' in sites
    assert "Voltar ao passo 4" in segundo  # o número do passo anterior vem do assistente
    assert "Voltar ao passo 3" in sites
    # sem resumo os dois links vão sem o `?busca=`
    assert f'href="{SITES}"' in cenario.get(PASSO_2).text
    assert f'href="{PASSO_1}"' in cenario.get(SITES).text
    assert 'name="busca"' not in cenario.get(SITES).text


def test_voltar_em_ingles_diz_a_frase_inteira(cenario: Cenario) -> None:
    cenario.com_leitor()
    cenario.post(PASSO_1, COMPLETO)
    ingles = {"Accept-Language": "en"}
    assert "Back to Step 4" in cenario.get(PASSO_2, headers=ingles).text
    assert "Back to Step 3" in cenario.get(SITES, headers=ingles).text


def test_voltar_do_segundo_plano_sem_leitor_vai_ao_passo_1(cenario: Cenario) -> None:
    cenario.post(PASSO_1, COMPLETO)
    (busca,) = cenario.buscas()
    html = cenario.get(f"{PASSO_2}?busca={busca.id}").text
    assert f'href="{PASSO_1}?busca={busca.id}"' in html
    assert "Voltar ao passo 3" in html
    assert 'href="/primeira-execucao/sites' not in html
    assert 'href="/primeira-execucao/1"' in cenario.get(PASSO_2).text


# --- Pular e os botões do pé (T263; D143.18, D143.40, E17) ---------------------------------------


def test_pular_grava_os_padroes(cenario: Cenario) -> None:
    _redireciona(cenario.post(PULAR, headers={"Accept-Language": "en-GB"}), "/vagas")
    assert cenario.config("meu_pais") == "GB"
    assert cenario.config("segundo_plano") is False
    assert cenario.config("primeira_execucao_concluida") is True
    assert cenario.buscas() == []  # a busca fica sem critério
    assert cenario.atalho.exists()  # como o "Não ligar agora": o atalho do menu sai mesmo assim
    assert not cenario.servico.exists()
    assert all(c[0] != "enable" for c in cenario.sistema.systemctl())


def test_pular_leva_o_pais_do_formulario_e_so_grava_se_nao_houver(cenario: Cenario) -> None:
    cenario.post(PULAR, {"meu_pais": "PT"}, headers={"Accept-Language": "en-GB"})
    assert cenario.config("meu_pais") == "PT"
    cenario.post(PULAR, {"meu_pais": "US"})
    assert cenario.config("meu_pais") == "PT"  # o que já estava gravado fica


def test_pular_com_pais_de_fora_da_lista_nao_grava_nada(cenario: Cenario) -> None:
    assert cenario.post(PULAR, {"meu_pais": "XX"}).status_code == 422
    assert cenario.config("meu_pais") is None
    assert cenario.config("primeira_execucao_concluida") is None


@pytest.mark.parametrize("com_leitor", [False, True])
@pytest.mark.parametrize("de_onde", [PASSO_1, SITES, PASSO_2])
def test_pular_responde_em_qualquer_passo(cenario: Cenario, com_leitor: bool, de_onde: str) -> None:
    if com_leitor:
        cenario.com_leitor()
    elif de_onde == SITES:
        pytest.skip("sem leitor o passo dos sites não existe")
    assert cenario.get(de_onde).status_code == 200
    _redireciona(cenario.post(PULAR), "/vagas")  # não cai no 404 de `/{passo}`
    assert cenario.config("primeira_execucao_concluida") is True
    assert cenario.get("/").headers["location"] == "/vagas?aba=destaques"  # a raiz não volta


def test_pular_com_atalho_que_falha_segue(
    cenario: Cenario, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def quebrar(*args: object, **kw: object) -> None:
        raise OSError("disco cheio")

    monkeypatch.setattr(segundo_plano_linux, "criar_atalho", quebrar)
    with caplog.at_level("WARNING"):
        resposta = cenario.post(PULAR)
    _redireciona(resposta, "/vagas")
    assert "disco cheio" in caplog.text  # o detalhe vai para o log
    assert cenario.config("segundo_plano") is False
    assert cenario.config("primeira_execucao_concluida") is True


def test_pular_fora_do_linux_nao_mexe_no_sistema(cenario: Cenario) -> None:
    cenario.app.state.plataforma = "freebsd14"  # nem Linux, nem Windows, nem Mac
    _redireciona(cenario.post(PULAR), "/vagas")
    assert cenario.sistema.chamadas == []
    assert not cenario.atalho.exists()
    assert cenario.config("primeira_execucao_concluida") is True


def test_pular_nao_liga_site_com_login(cenario: Cenario) -> None:
    cenario.com_leitor()
    _redireciona(cenario.post(PULAR), "/vagas")
    assert cenario.ligadas() == []


def test_pular_desliga_o_site_que_a_pessoa_ligou(cenario: Cenario) -> None:
    """D137.10, ADR 0011 e plano da fase 2 (E10): Pular deixa os padrões, sem site com login."""
    cenario.com_leitor()
    cenario.post(INTERRUPTOR, {"ligada": "on"})
    assert cenario.ligadas() == ["falso_logado"]
    _redireciona(cenario.post(PULAR), "/vagas")
    assert cenario.ligadas() == []


@pytest.mark.parametrize(("idioma", "pular"), [("pt", "Pular tudo"), ("en", "Skip all")])
def test_pular_em_todo_passo(cenario: Cenario, idioma: str, pular: str) -> None:
    """O Pular do pé conclui o assistente inteiro: "Pular tudo", para não se confundir com o
    "Pular este passo" do Perfil (T439)."""
    cenario.com_leitor()
    for url in (PASSO_IA, PASSO_PERFIL, PASSO_1, SITES, PASSO_2):
        html = cenario.get(url, headers={"Accept-Language": idioma}).text
        assert html.count(f'formaction="{PULAR}"') == 1, url
        botao = re.search(rf'<button[^>]*formaction="{PULAR}"[^>]*>\s*([^<]*?)\s*</button>', html)
        assert botao is not None and botao.group(1) == pular, url


@pytest.mark.parametrize(
    ("idioma", "continuar", "concluir"),
    [("pt", "Continuar", "Concluir"), ("en", "Continue", "Finish")],
)
def test_continuar_e_concluir_no_pe(
    cenario: Cenario, idioma: str, continuar: str, concluir: str
) -> None:
    cenario.com_leitor()
    cabecalho = {"Accept-Language": idioma}
    for url in (PASSO_1, SITES):
        pe = cenario.get(url, headers=cabecalho).text.split('class="assistente-pe"')[1]
        assert f">{continuar}<" in pe and f">{concluir}<" not in pe, url
    pe = cenario.get(PASSO_2, headers=cabecalho).text.split('class="assistente-pe"')[1]
    assert f">{concluir}<" in pe and f">{continuar}<" not in pe
    # o pé fica fora do formulário e os botões o apontam por `form=` (só o conteúdo rola, E17)
    assert 'form="assistente-form"' in pe


@pytest.mark.parametrize("url", [PASSO_1, SITES, PASSO_2])
def test_assistente_sem_botoes_da_barra(cenario: Cenario, url: str) -> None:
    cenario.com_leitor()
    html = cenario.get(url).text
    assert "<aside" not in html
    assert "/buscar-agora" not in html and 'action="/sair"' not in html
    assert 'id="andamento"' not in html


def test_pronto_usa_o_componente_da_barra(cenario: Cenario) -> None:
    """A primeira busca usa o componente da casca (T252), sem cópia na página (T266; D143.69)."""
    cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    with closing(abrir(cenario.banco)) as con:
        assert (
            abrir_execucao(con, "busca", "agenda", datetime(2026, 11, 13, tzinfo=UTC)) is not None
        )
    html = cenario.get(f"{PASSO_2}?feito=1").text
    assert html.count("progressbar") == 0  # sem barra própria: a da casca vem por HTMX
    assert 'hx-get="/execucao/atual?so_rodando=1"' in html.split("</header>")[0]
    fragmento = cenario.get("/execucao/atual?so_rodando=1", headers={"HX-Request": "true"}).text
    assert fragmento.count('role="progressbar"') == 1  # um só componente na página


def test_tudo_pronto_mostra_buscar_agora_na_barra(cenario: Cenario) -> None:
    cenario.post(PASSO_2, {"segundo_plano": "desligar"})
    html = cenario.get(f"{PASSO_2}?feito=1").text
    cabeca = html.split("</header>")[0]
    assert 'action="/buscar-agora"' in cabeca and 'id="andamento"' in cabeca
    assert 'class="assistente-pe"' not in html  # a tela final não tem pé de passo


# --- passos IA e Perfil (desenho 10.4 da fase 4; T439; D235) -----------------------------------

CHAVE_ANTHROPIC = "sk-ant-teste-0123456789"
# o formulário do passo Perfil como a tela o manda, vazio (campo que falta é 422 seco)
PERFIL_VAZIO = dict.fromkeys(
    (
        "nome", "email", "telefone", "cidade_moradia", "cargo_atual", "anos_de_experiencia",
        "formacao_nivel", "links", "habilidades", "idioma_pt", "idioma_en", "idioma_es",
    ),
    "",
)  # fmt: skip


def _texto_de(resposta: Any) -> str:
    return html_lib.unescape(re.sub(r"\s+", " ", resposta.text))


def _tarefas(cenario: Cenario) -> object:
    return cenario.config("ia_tarefas")


def _gravar_perfil(cenario: Cenario, **campos: Any) -> None:
    with closing(abrir(cenario.banco)) as con:
        perfil.gravar_dados(con, perfil.Dados(**campos), datetime(2026, 11, 24, tzinfo=UTC))


def test_quem_ja_passou_pelo_assistente_nao_volta(cenario: Cenario) -> None:
    _redireciona(cenario.get("/"), PASSO_IA)  # controle: sem a chave, a raiz leva ao assistente
    _redireciona(cenario.get("/panorama"), PASSO_IA)
    cenario.gravar_config("primeira_execucao_concluida", True)
    assert cenario.get("/").headers["location"].startswith("/vagas")
    assert cenario.get("/panorama").status_code == 200


@pytest.mark.parametrize(("url", "proximo"), [(PASSO_IA, PASSO_PERFIL), (PASSO_PERFIL, PASSO_1)])
def test_ia_e_perfil_vem_antes_da_busca_e_tem_pular(
    cenario: Cenario, url: str, proximo: str
) -> None:
    html = cenario.get(url).text
    assert f'formaction="{PULAR}"' in html  # o Pular de todo passo (T263) segue
    assert f'action="{url}"' in html and 'name="csrf_token"' in html
    if url == PASSO_PERFIL:  # e o Pular só deste passo, que não grava nada
        assert re.search(rf'<a [^>]*href="{proximo}"[^>]*>\s*Pular este passo', html)
    else:  # na IA, pular é uma das escolhas, marcada sem IA ligada
        assert re.search(r'<input type="radio" name="ia" value="nenhum" checked', html)


def test_passo_ia_mostra_os_atalhos_com_o_custo(cenario: Cenario) -> None:
    cenario.app.state.modelo_local = lambda: "qwen3-4b"
    texto = _texto_de(cenario.get(PASSO_IA, headers={"Accept-Language": "pt"}))
    assert "Modelo local (grátis, roda no seu PC)" in texto
    assert "Serviço pago (sua chave)" in texto
    assert "Agora não: seguir sem IA" in texto
    assert "até 200 pedidos por dia" in texto  # o custo à vista, com o teto do laço
    assert "Modelo baixado: qwen3-4b." in texto
    ingles = _texto_de(cenario.get(PASSO_IA, headers={"Accept-Language": "en"}))
    assert "Local model (free, runs on your PC)" in ingles
    assert "Paid service (your key)" in ingles
    assert "up to 200 requests a day" in ingles
    # o consentimento fala do currículo, a tarefa que o atalho liga e a que mais leva dado pessoal
    assert "O texto do currículo, sem e-mail, telefone e CPF, vai quando você manda ler." in texto
    assert "Your résumé text, without email, phone and CPF, goes when you ask to read it." in ingles


def test_passo_ia_sem_modelo_local_desativa_a_opcao(cenario: Cenario) -> None:
    html = cenario.get(PASSO_IA).text
    assert re.search(r'<input type="radio" name="ia" value="local" disabled', html)
    assert "Configurações › Ferramentas › Modelo local de IA" in html_lib.unescape(html)
    # baixar só não basta: a dica diz onde ligar depois
    assert "Configurações › IA, em Tudo offline" in html_lib.unescape(html)
    ingles = html_lib.unescape(cenario.get(PASSO_IA, headers={"Accept-Language": "en"}).text)
    assert "Settings › AI, under All offline" in ingles
    resposta = cenario.post(PASSO_IA, {"ia": "local"})
    assert resposta.status_code == 422
    assert "O modelo local ainda não foi baixado" in _texto_de(resposta)
    assert _tarefas(cenario) is None


def test_passo_ia_tudo_local_sem_o_modelo_marca_agora_nao(cenario: Cenario) -> None:
    local = {"ligada": True, "backend": "local", "modelo": "qwen3-4b"}
    cenario.gravar_config("ia_tarefas", dict.fromkeys(limites()["tarefas"], local))
    cenario.app.state.modelo_local = lambda: "qwen3-4b"  # controle: com o modelo, vem marcado
    assert re.search(r'name="ia" value="local" checked', cenario.get(PASSO_IA).text)
    cenario.app.state.modelo_local = lambda: None  # o modelo sumiu: a opção vem só desativada
    html = cenario.get(PASSO_IA).text
    assert re.search(r'name="ia" value="local" disabled aria', html)
    assert re.search(r'name="ia" value="nenhum" checked', html)


def test_passo_ia_local_liga_tudo_no_modelo_baixado(cenario: Cenario) -> None:
    cenario.app.state.modelo_local = lambda: "qwen3-4b"
    _redireciona(cenario.post(PASSO_IA, {"ia": "local"}), PASSO_PERFIL)
    tarefas = _tarefas(cenario)
    assert isinstance(tarefas, dict) and tarefas
    assert all(
        t == {"ligada": True, "backend": "local", "modelo": "qwen3-4b"} for t in tarefas.values()
    )
    html = cenario.get(PASSO_IA).text  # voltando, a escolha gravada vem marcada
    assert re.search(r'<input type="radio" name="ia" value="local" checked', html)


def test_passo_ia_pago_guarda_a_chave_e_liga_o_claude_sem_segunda_confirmacao(
    cenario: Cenario,
) -> None:
    resposta = cenario.post(PASSO_IA, {"ia": "pago", "chave": CHAVE_ANTHROPIC})
    _redireciona(resposta, PASSO_PERFIL)  # o custo já estava à vista no passo
    assert cenario.cofre.ler("ia_anthropic") == (CHAVE_ANTHROPIC, "sistema")
    tarefas = _tarefas(cenario)
    assert isinstance(tarefas, dict) and tarefas
    assert all(t["ligada"] and t["backend"] == "anthropic" for t in tarefas.values())
    html = cenario.get(PASSO_IA).text
    assert CHAVE_ANTHROPIC not in html  # a chave nunca volta à tela
    assert "Já há uma chave guardada" in html
    assert re.search(r'<input type="radio" name="ia" value="pago" checked', html)
    # com a chave guardada, o campo vazio usa a mesma
    _redireciona(cenario.post(PASSO_IA, {"ia": "pago", "chave": ""}), PASSO_PERFIL)


def test_passo_ia_pago_sem_chave_nao_liga_nada(cenario: Cenario) -> None:
    resposta = cenario.post(PASSO_IA, {"ia": "pago", "chave": ""})
    assert resposta.status_code == 422
    assert "Digite a chave da API da Anthropic." in _texto_de(resposta)
    assert 'aria-invalid="true"' in resposta.text
    assert _tarefas(cenario) is None


def test_passo_ia_chave_invalida_nao_volta_nem_grava(cenario: Cenario) -> None:
    segredo = "segredo com espaco 12345"
    resposta = cenario.post(PASSO_IA, {"ia": "pago", "chave": segredo})
    assert resposta.status_code == 422
    assert segredo not in resposta.text
    assert "A chave precisa ter de 8 a 512 caracteres" in _texto_de(resposta)
    assert cenario.cofre.ler("ia_anthropic") is None
    assert _tarefas(cenario) is None


def test_passo_ia_agora_nao_deixa_a_ia_como_esta(cenario: Cenario) -> None:
    ligada = {"encaixe": {"ligada": True, "backend": "local", "modelo": "qwen3-4b"}}
    cenario.gravar_config("ia_tarefas", ligada)
    cenario.app.state.modelo_local = lambda: "qwen3-4b"
    _redireciona(cenario.post(PASSO_IA, {"ia": "nenhum"}), PASSO_PERFIL)
    assert _tarefas(cenario) == ligada


@pytest.mark.parametrize("valor", ["", "claude", "LOCAL"])
def test_passo_ia_escolha_fora_da_lista_e_422(cenario: Cenario, valor: str) -> None:
    assert cenario.post(PASSO_IA, {"ia": valor}).status_code == 422
    assert cenario.post(PASSO_IA, {}).status_code == 422
    _redireciona(cenario.post(PASSO_IA, {"ia": "nenhum"}), PASSO_PERFIL)  # controle


def test_passo_perfil_grava_as_respostas_e_segue_para_a_busca(cenario: Cenario) -> None:
    html = cenario.get(PASSO_PERFIL).text
    for campo in ("cargo_atual", "cidade_moradia", "habilidades", "anos_de_experiencia"):
        assert f'name="{campo}"' in html
    dados = {"cargo_atual": "Analista de dados", "cidade_moradia": "Curitiba", "habilidades": "SQL"}
    _redireciona(cenario.post(PASSO_PERFIL, PERFIL_VAZIO | dados), PASSO_1)
    with closing(abrir(cenario.banco)) as con:
        gravado = perfil.dados(con)
        assert (gravado.cargo_atual, gravado.cidade_moradia) == ("Analista de dados", "Curitiba")
        assert perfil.habilidades(con) == ["SQL"]


def test_passo_perfil_com_erro_volta_com_o_digitado(cenario: Cenario) -> None:
    errado = {"cargo_atual": "Dev", "anos_de_experiencia": "999"}
    resposta = cenario.post(PASSO_PERFIL, PERFIL_VAZIO | errado)
    assert resposta.status_code == 422
    assert 'value="Dev"' in resposta.text and 'aria-invalid="true"' in resposta.text
    assert 'id="config-erro"' in resposta.text
    with closing(abrir(cenario.banco)) as con:
        assert perfil.dados(con).cargo_atual is None


def test_passo_perfil_sugere_perguntas_so_com_a_tarefa_ligada(cenario: Cenario) -> None:
    assert 'name="sugerir"' not in cenario.get(PASSO_PERFIL).text
    tarefa = {"perguntas": {"ligada": True, "backend": "anthropic", "modelo": "claude-sonnet-5-5"}}
    cenario.gravar_config("ia_tarefas", tarefa)
    html = cenario.get(PASSO_PERFIL).text
    botao = re.search(r'<button [^>]*name="sugerir"[^>]*>', html)
    assert botao and 'form="assistente-form"' in botao.group(0)
    # o Enter num campo aciona o primeiro botão do formulário: o Continuar, nunca o sugerir
    continuar = html.index('form="assistente-form" class="botao botao-primario"')
    assert html.index('class="assistente-pe"') < continuar < botao.start()
    # sem a fábrica do `serve`, a sugestão falha: as respostas ficam e a página diz por quê
    resposta = cenario.post(PASSO_PERFIL, PERFIL_VAZIO | {"cargo_atual": "Dev", "sugerir": "1"})
    assert resposta.status_code == 200
    assert "a IA não sugeriu perguntas" in _texto_de(resposta)
    with closing(abrir(cenario.banco)) as con:
        assert perfil.dados(con).cargo_atual == "Dev"


def test_passo_de_busca_chega_com_cargo_e_cidade_do_perfil(cenario: Cenario) -> None:
    _gravar_perfil(cenario, cargo_atual="Analista de dados", cidade_moradia="Curitiba")
    html = cenario.get(PASSO_1).text
    assert re.search(r'<textarea id="cargos"[^>]*>Analista de dados</textarea>', html)
    assert '<input type="text" name="cidade" value="Curitiba"' in html
    assert '<option value="PR" selected>' in html
    # a busca já gravada vale sobre o perfil (o Voltar edita a mesma busca)
    cenario.post(PASSO_1, COMPLETO)
    busca_id = cenario.buscas()[0].id
    voltando = cenario.get(f"{PASSO_1}?busca={busca_id}").text
    assert ">Python\nDados</textarea>" in voltando and "Analista de dados" not in voltando


def test_cidade_do_perfil_que_nao_se_entende_vai_como_esta(cenario: Cenario) -> None:
    _gravar_perfil(cenario, cidade_moradia="Vila Quixotesca")
    html = cenario.get(PASSO_1).text
    assert '<input type="text" name="cidade" value="Vila Quixotesca"' in html
    assert '<option value="PR" selected>' not in html


def test_voltar_leva_a_busca_pelos_passos_novos(cenario: Cenario) -> None:
    cenario.post(PASSO_1, COMPLETO)
    busca_id = cenario.buscas()[0].id
    assert (
        f'href="{PASSO_PERFIL}?busca={busca_id}"' in cenario.get(f"{PASSO_1}?busca={busca_id}").text
    )
    perfil_html = cenario.get(f"{PASSO_PERFIL}?busca={busca_id}").text
    assert f'href="{PASSO_IA}?busca={busca_id}"' in perfil_html
    assert f'<input type="hidden" name="busca" value="{busca_id}">' in perfil_html
    seguir = cenario.post(PASSO_PERFIL, PERFIL_VAZIO | {"busca": str(busca_id)})
    _redireciona(seguir, f"{PASSO_1}?busca={busca_id}")
    _redireciona(
        cenario.post(PASSO_IA, {"ia": "nenhum", "busca": str(busca_id)}),
        f"{PASSO_PERFIL}?busca={busca_id}",
    )
    _redireciona(cenario.post(PASSO_IA, {"ia": "nenhum", "busca": "999"}), PASSO_PERFIL)
    assert len(cenario.buscas()) == 1


def test_curriculo_no_assistente_grava_e_volta_ao_passo(cenario: Cenario) -> None:
    url = PASSO_PERFIL + "/curriculo"
    campos = [("secao", "curriculo"), ("item", "cargo_atual"), ("usar", "cargo_atual")]
    resposta = cenario.post(url, dict([*campos, ("cargo_atual.valor", "Dev")]))
    _redireciona(resposta, PASSO_PERFIL + "?curriculo=1")
    with closing(abrir(cenario.banco)) as con:
        assert perfil.dados(con).cargo_atual == "Dev"
    texto = _texto_de(cenario.get(PASSO_PERFIL + "?curriculo=1"))
    assert "Currículo salvo no perfil" in texto
    # nada escolhido: volta ao passo com o aviso, e a revisão aponta para o assistente
    errado = cenario.post(
        url, {"secao": "curriculo", "item": "cargo_atual", "cargo_atual.valor": "X"}
    )
    assert errado.status_code == 422
    assert f'action="{url}"' in errado.text
    # as outras seções são da aba Perfil: um "Sobre você" inteiro não grava por aqui
    sobre = PERFIL_VAZIO | {"secao": "dados", "resumo": "", "cargo_atual": "Y"}
    assert cenario.post(url, sobre).status_code == 422
    with closing(abrir(cenario.banco)) as con:
        assert perfil.dados(con).cargo_atual == "Dev"


@pytest.mark.parametrize("escolha", ["local", "pago"])
def test_passo_ia_agora_nao_desliga_o_que_o_assistente_ligou(
    cenario: Cenario, escolha: str
) -> None:
    """Quem escolheu, se arrependeu, voltou e marcou "seguir sem IA" segue sem IA (T439)."""
    cenario.app.state.modelo_local = lambda: "qwen3-4b"
    chave = CHAVE_ANTHROPIC if escolha == "pago" else ""
    _redireciona(cenario.post(PASSO_IA, {"ia": escolha, "chave": chave}), PASSO_PERFIL)
    tarefas = _tarefas(cenario)
    assert isinstance(tarefas, dict) and all(t["ligada"] for t in tarefas.values())  # controle
    _redireciona(cenario.post(PASSO_IA, {"ia": "nenhum"}), PASSO_PERFIL)
    tarefas = _tarefas(cenario)
    assert isinstance(tarefas, dict) and tarefas
    assert not any(t["ligada"] for t in tarefas.values())
    assert re.search(r'name="ia" value="nenhum" checked', cenario.get(PASSO_IA).text)


@pytest.mark.parametrize("escolha", ["nenhum", "local"])
def test_passo_ia_chave_sem_o_pago_volta_sem_gravar(cenario: Cenario, escolha: str) -> None:
    """A chave digitada com outro rádio marcado não some calada nem liga o pago sozinha: a
    escolha é a confirmação do custo (T439)."""
    cenario.app.state.modelo_local = lambda: "qwen3-4b"  # o local valeria: quem recusa é a chave
    resposta = cenario.post(PASSO_IA, {"ia": escolha, "chave": CHAVE_ANTHROPIC})
    assert resposta.status_code == 422
    assert "Você digitou uma chave: marque Serviço pago ou apague a chave." in _texto_de(resposta)
    assert CHAVE_ANTHROPIC not in resposta.text
    assert re.search(r'id="ia-chave"[^>]*aria-invalid="true"', resposta.text)
    assert re.search(rf'name="ia" value="{escolha}" checked', resposta.text)
    assert cenario.cofre.ler("ia_anthropic") is None
    assert _tarefas(cenario) is None
    ingles = cenario.post(
        PASSO_IA, {"ia": escolha, "chave": CHAVE_ANTHROPIC}, headers={"Accept-Language": "en"}
    )
    assert "You typed a key: choose Paid service or clear the key." in _texto_de(ingles)
    # controle: só espaço não é chave
    _redireciona(cenario.post(PASSO_IA, {"ia": escolha, "chave": "  "}), PASSO_PERFIL)


def test_passo_ia_chave_nova_refaz_o_teste_ao_ligar(cenario: Cenario) -> None:
    """Como na aba Serviços: chave nova com o Claude já ligado volta os pares dele ao teste."""
    _redireciona(cenario.post(PASSO_IA, {"ia": "pago", "chave": CHAVE_ANTHROPIC}), PASSO_PERFIL)
    tarefas = _tarefas(cenario)
    assert isinstance(tarefas, dict)
    pares = {("anthropic", t["modelo"]) for t in tarefas.values()}
    cenario.app.state.ia_testes = dict.fromkeys(pares, Teste("falhou"))  # o da chave antiga
    _redireciona(cenario.post(PASSO_IA, {"ia": "pago", "chave": ""}), PASSO_PERFIL)
    assert set(cenario.app.state.ia_testes) == pares  # controle: sem chave nova, o teste fica
    nova = {"ia": "pago", "chave": "sk-ant-outra-0123456789"}
    _redireciona(cenario.post(PASSO_IA, nova), PASSO_PERFIL)
    assert cenario.cofre.ler("ia_anthropic") == ("sk-ant-outra-0123456789", "sistema")
    assert not set(cenario.app.state.ia_testes) & pares


def test_passo_perfil_nao_diz_que_fica_no_computador_com_a_ia_paga(cenario: Cenario) -> None:
    _redireciona(cenario.post(PASSO_IA, {"ia": "pago", "chave": CHAVE_ANTHROPIC}), PASSO_PERFIL)
    for idioma, local in (("pt", "fica no seu computador"), ("en", "stays on your computer")):
        texto = _texto_de(cenario.get(PASSO_PERFIL, headers={"Accept-Language": idioma}))
        assert "Anthropic" in texto  # controle: a frase de para onde vai o currículo está lá
        assert local not in texto


class _IaFalsa:
    """`app.state.ia` falsa: responde o pronto e não manda nada a ninguém."""

    def __init__(self, prontas: list[Any]) -> None:
        self.falso = BackendFalso(prontas)

    def __call__(self, backend: str, modelo: str) -> _IaFalsa:
        return self

    def pedir(self, pedido: Pedido) -> Resposta:
        return self.falso.pedir(pedido)

    def fechar(self) -> None:
        pass


def test_passo_perfil_sugerir_volta_ao_passo_com_as_perguntas(cenario: Cenario) -> None:
    tarefa = {"perguntas": {"ligada": True, "backend": "anthropic", "modelo": "claude-sonnet-5-5"}}
    cenario.gravar_config("ia_tarefas", tarefa)
    sugeridas = {
        "perguntas": [
            {"pergunta": "Que ferramentas de BI você usa?", "por_que": "Vagas de dados pedem BI."},
            {"pergunta": "Você tem certificações?", "por_que": "Ajudam na triagem."},
        ]
    }
    cenario.app.state.ia = _IaFalsa([sugeridas, sugeridas])
    resposta = cenario.post(PASSO_PERFIL, PERFIL_VAZIO | {"cargo_atual": "Dev", "sugerir": "1"})
    _redireciona(resposta, PASSO_PERFIL + "?sugeridas=2#perguntas-ia")
    texto = _texto_de(cenario.get(PASSO_PERFIL + "?sugeridas=2"))
    assert "Que ferramentas de BI você usa?" in texto
    # com a busca, o endereço do passo a leva junto
    cenario.post(PASSO_1, COMPLETO)
    busca_id = cenario.buscas()[0].id
    dados = PERFIL_VAZIO | {"cargo_atual": "Dev", "sugerir": "1", "busca": str(busca_id)}
    destino = f"{PASSO_PERFIL}?sugeridas=0&busca={busca_id}#perguntas-ia"
    _redireciona(cenario.post(PASSO_PERFIL, dados), destino)
