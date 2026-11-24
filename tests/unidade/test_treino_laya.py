"""Regras duras do treino do Laya (T419; D219): `scripts/treino_laya/`, sem rede nem GPU."""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
import pytest

from jobot.banco.migrar import migrar
from jobot.nucleo.ia.contrato import Falha, Pedido, Resposta, conferir
from jobot.nucleo.ia.tarefas import SaidaEncaixe

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "scripts" / "treino_laya"
OURO = RAIZ / "tests" / "fixtures" / "ia" / "ouro_habilidades.json"


def _script(nome: str) -> ModuleType:
    # os scripts se importam entre si como na linha de comando (a pasta do script no path)
    if nome in sys.modules:
        return sys.modules[nome]
    spec = importlib.util.spec_from_file_location(nome, PASTA / f"{nome}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


montar = _script("montar_conjunto")
rotular = _script("rotular")
treinar = _script("treinar")
custo = _script("custo")

LONGA = (
    " Vamos construir sistemas de pagamento com times pequenos e autonomia. Requisitos: Python, "
    "PostgreSQL, Docker e testes automatizados. Trabalho remoto com encontros mensais. "
) * 2


def _banco(tmp_path: Path, vagas: list[dict[str, Any]], com_login: tuple[str, ...] = ()) -> Path:
    """Banco do joBot com as migrações de verdade; cada vaga traz `fontes`."""
    caminho = tmp_path / "jobot.db"
    with closing(sqlite3.connect(caminho)) as con:
        migrar(con, caminho)
        todas = {f for v in vagas for f in v["fontes"]} | set(com_login)
        for chave in sorted(todas):
            con.execute(
                "INSERT INTO fonte (chave, leva, com_login) VALUES (?, 'A', ?)",
                (chave, int(chave in com_login)),
            )
        for i, v in enumerate(vagas):
            cur = con.execute(
                "INSERT INTO vaga (url_hash, titulo, empresa, descricao_texto, url,"
                " primeira_vista_em, ultima_vista_em, versao_regras)"
                " VALUES (?, ?, ?, ?, ?, '2026-11-24', '2026-11-24', '1')",
                (
                    v.get("hash", f"h{i:04d}"),
                    v.get("titulo", f"Dev {i}"),
                    v.get("empresa", f"Empresa {i}"),
                    v.get("descricao", LONGA),
                    f"https://exemplo.invalid/{i}",
                ),
            )
            for fonte in v["fontes"]:
                con.execute(
                    "INSERT INTO ocorrencia (vaga_id, fonte, url, coletada, primeira_vista_em,"
                    " ultima_vista_em) VALUES (?, ?, 'https://exemplo.invalid', '{}',"
                    " '2026-11-24', '2026-11-24')",
                    (cur.lastrowid, fonte),
                )
        con.commit()
    return caminho


def _ids(lados: dict[str, list[dict[str, Any]]]) -> set[str]:
    return {r["id"] for v in lados.values() for r in v}


# --- montar_conjunto.py -----------------------------------------------------------------------


def test_lista_de_fontes_e_vazia_por_padrao(tmp_path: Path) -> None:
    banco = _banco(tmp_path, [{"fontes": ["remotive"]}])
    saida = tmp_path / "conjunto"
    base = ["montar", "--banco", str(banco), "--saida", str(saida), "--sem-gabarito"]
    assert montar.main(base) == 2
    assert not saida.exists()
    # controle: a mesma montagem com a fonte liberada escreve a vaga
    args = [*base, "--fonte", "remotive"]
    assert montar.main(args) == 0
    linhas = [*(saida / "treino.jsonl").read_text().splitlines()]
    linhas += (saida / "validacao.jsonl").read_text().splitlines()
    assert [json.loads(x)["id"] for x in linhas] == ["h0000"]


def test_so_coletor_publico_entra_na_lista() -> None:
    with pytest.raises(montar.Recusa, match="linkedin"):
        montar.conferir_fontes(["remotive", "linkedin"], ["remotive", "greenhouse"])
    assert montar.conferir_fontes(["remotive"], ["remotive", "greenhouse"]) == {"remotive"}


def test_vaga_de_site_com_login_nunca_entra(tmp_path: Path) -> None:
    banco = _banco(
        tmp_path,
        [{"fontes": ["remotive", "linkedin"]}, {"fontes": ["remotive"]}, {"fontes": ["gupy"]}],
        com_login=("linkedin",),
    )
    # mesmo liberada por engano, a fonte com login tira a vaga; fonte fora da lista também
    lados = montar.montar(banco, frozenset({"remotive", "linkedin"}))
    assert _ids(lados) == {"h0001"}


def test_hashes_do_dono_tiram_as_vagas(tmp_path: Path) -> None:
    banco = _banco(tmp_path, [{"fontes": ["remotive"]}, {"fontes": ["remotive"]}])
    hashes = tmp_path / "fora.txt"
    hashes.write_text("# gabarito\nH0000\n")
    lados = montar.montar(banco, frozenset({"remotive"}), montar.ler_hashes(hashes))
    assert _ids(lados) == {"h0001"}


@pytest.mark.parametrize("pasta", ["joBot-dados", "dados_locais", "JOBOT-DADOS"])
def test_caminho_do_gabarito_e_recusado(tmp_path: Path, pasta: str) -> None:
    proibido = tmp_path / pasta / "jobot.db"
    with pytest.raises(montar.Recusa):
        montar.conferir_caminho(proibido)
    args = ["--banco", str(proibido), "--saida", str(tmp_path / "s"), "--fonte", "remotive"]
    assert montar.main(["montar", *args, "--sem-gabarito"]) == 2
    assert not (tmp_path / "s").exists()
    banco = _banco(tmp_path, [{"fontes": ["remotive"]}])
    saida = ["--saida", str(tmp_path / pasta / "s"), "--fonte", "remotive", "--sem-gabarito"]
    assert montar.main(["montar", "--banco", str(banco), *saida]) == 2
    assert not (tmp_path / pasta / "s").exists()
    # controle: caminho comum passa
    assert montar.conferir_caminho(tmp_path / "x" / "jobot.db") == tmp_path / "x" / "jobot.db"


def test_contato_sai_do_texto(tmp_path: Path) -> None:
    descricao = (
        LONGA + "\nRecrutadora: Maria Souza\nDúvidas: vagas.maria@empresa.com.br ou "
        "(11) 98888-7777.\nEnviar para: Joana Lima"
    )
    banco = _banco(tmp_path, [{"fontes": ["remotive"], "descricao": descricao}])
    (registro,) = [r for v in montar.montar(banco, frozenset({"remotive"})).values() for r in v]
    texto = registro["descricao"]
    for pessoal in ("Maria", "Souza", "vagas.maria", "98888", "Joana", "Lima"):
        assert pessoal not in texto
    assert "Python, PostgreSQL, Docker" in texto  # controle: o resto fica


def test_duplicadas_ficam_do_mesmo_lado(tmp_path: Path) -> None:
    vagas = []
    for i in range(60):  # a mesma vaga em duas fontes: dois url_hash, mesma empresa e título
        par = {"titulo": f"Dev Python {i}", "empresa": f"Empresa {i}"}
        vagas += [
            {**par, "hash": f"a{i}", "fontes": ["remotive"]},
            {**par, "hash": f"b{i}", "fontes": ["gupy"], "titulo": f"dev  python {i}"},
        ]
    lados = montar.montar(_banco(tmp_path, vagas), frozenset({"remotive", "gupy"}))
    assert lados["treino"] and lados["validacao"]
    for i in range(60):
        lado = {n for n, v in lados.items() for r in v if r["id"] in (f"a{i}", f"b{i}")}
        assert len(lado) == 1, f"par {i} dividido"


def test_vaga_do_ouro_nunca_entra_no_conjunto(tmp_path: Path) -> None:
    ouro = json.loads(OURO.read_text(encoding="utf-8"))["vagas"][0]
    banco = _banco(
        tmp_path,
        [
            {"fontes": ["remotive"], "titulo": ouro["titulo"], "descricao": ouro["descricao"] * 3},
            {"fontes": ["remotive"]},
        ],
    )
    lados = montar.montar(banco, frozenset({"remotive"}), ouro=montar.descricoes_do_ouro())
    assert _ids(lados) == {"h0001"}


def test_treino_para_com_exemplo_do_ouro(tmp_path: Path) -> None:
    ouro = json.loads(OURO.read_text(encoding="utf-8"))["vagas"][1]
    do_ouro = montar.exemplo_habilidades(
        {"id": "x", "titulo": ouro["titulo"], "descricao": ouro["descricao"]}, ["HTML"]
    )
    comum = montar.exemplo_habilidades({"id": "y", "titulo": "Dev", "descricao": LONGA}, ["Python"])
    montar.conferir_sem_ouro([comum], montar.descricoes_do_ouro())  # controle
    with pytest.raises(montar.Recusa, match="ouro"):
        montar.conferir_sem_ouro([comum, do_ouro], montar.descricoes_do_ouro())


def test_exemplos_no_esquema_da_tarefa_e_vf_falsa_fora_do_texto() -> None:
    registro = {"id": "v1", "titulo": "Dev", "descricao": LONGA}
    exemplo = montar.exemplo_habilidades(registro, ["Python", "Docker"])
    resposta = json.loads(exemplo["completion"][0]["content"])
    assert SaidaEncaixe.model_validate(resposta).pede == ["Python", "Docker"]
    assert [m["role"] for m in exemplo["prompt"]] == ["system", "user"]
    vf = montar.perguntas_vf(registro, ["Python"], ["Docker", "Kotlin"])
    respostas = [
        (
            e["prompt"][1]["content"].rsplit("Item: ", 1)[1],
            json.loads(e["completion"][0]["content"]),
        )
        for e in vf
    ]
    # Docker está escrito na vaga: nunca vira pergunta falsa
    assert respostas == [("Python", {"resposta": True}), ("Kotlin", {"resposta": False})]


@pytest.mark.parametrize(
    ("trecho", "pessoais"),
    [
        ("Fale com Maria Souza pelo portal.", ("Maria", "Souza")),
        ("Recrutadora responsável: Ana Paula Ribeiro", ("Ana", "Paula", "Ribeiro")),
        ("Reach out to John Smith with questions.", ("John", "Smith")),
        ("Você vai responder ao CTO Carlos Pereira.", ("Carlos", "Pereira")),
        ("WhatsApp 11987654321 ou @maria_recruta", ("11987654321", "maria_recruta")),
        ("Meu perfil: linkedin.com/in/joana-lima", ("joana", "lima")),
        ("Telegram: t.me/recruta_bia", ("recruta_bia",)),
    ],
)
def test_contato_em_texto_corrido_sai(trecho: str, pessoais: tuple[str, ...]) -> None:
    texto = montar.limpar(f"Requisitos: Python e Go.\n{trecho}\nTrabalho remoto.")
    for pessoal in pessoais:
        assert pessoal not in texto, texto
    assert "Requisitos: Python e Go." in texto and "Trabalho remoto." in texto


@pytest.mark.parametrize(
    ("trecho", "fica"),
    [
        (
            "Contato: Fulano | Requisitos: Python, Django e PostgreSQL",
            "Python, Django e PostgreSQL",
        ),
        ("Contact: Jane. Requirements: Go and Rust.", "Requirements: Go and Rust."),
        (
            "Experiência em contato com clientes e responder a incidentes.",
            "Experiência em contato com clientes e responder a incidentes.",
        ),
        ("Vaga com Node.js e AWS.", "Vaga com Node.js e AWS."),
    ],
)
def test_contato_corta_so_ate_o_fim_da_frase(trecho: str, fica: str) -> None:
    assert fica in montar.limpar(trecho)


def test_resto_de_dado_pessoal_tira_a_vaga(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    banco = _banco(
        tmp_path,
        [
            {"fontes": ["remotive"], "descricao": LONGA + " Envie para vagas@empresa.com"},
            {"fontes": ["remotive"]},
        ],
    )
    monkeypatch.setattr(montar, "limpar", lambda texto: texto)  # a limpeza deixou passar
    assert _ids(montar.montar(banco, frozenset({"remotive"}))) == {"h0001"}


def test_montar_exige_a_lista_do_dono_ou_a_decisao_e_conta_os_hashes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    banco = _banco(tmp_path, [{"fontes": ["remotive"]}, {"fontes": ["remotive"]}])
    base = ["montar", "--banco", str(banco), "--saida", str(tmp_path / "c"), "--fonte", "remotive"]
    for sem_escolha in ([], ["--sem-gabarito", "--excluir", str(tmp_path / "x")]):
        with pytest.raises(SystemExit):
            montar.main([*base, *sem_escolha])
    hashes = tmp_path / "fora.txt"
    hashes.write_text("h0000\nnao_existe\n")
    assert montar.main([*base, "--excluir", str(hashes)]) == 0
    erro = capsys.readouterr().err
    assert "2 hashes lidos, 1 casaram" in erro and "aviso" not in erro
    hashes.write_text("h0000,h0001\n")  # formato errado: nenhum casa
    assert montar.main([*base, "--excluir", str(hashes)]) == 0
    assert "aviso: nenhum hash" in capsys.readouterr().err
    assert montar.main([*base, "--sem-gabarito"]) == 0
    assert "hashes" not in capsys.readouterr().err


def test_saida_dentro_do_repositorio_e_recusada(tmp_path: Path) -> None:
    banco = _banco(tmp_path, [{"fontes": ["remotive"]}])
    dentro = RAIZ / "conjunto_teste"
    args = ["--banco", str(banco), "--saida", str(dentro), "--fonte", "remotive", "--sem-gabarito"]
    assert montar.main(["montar", *args]) == 2
    assert montar.main(["coletar", "--dados", str(dentro), "--fonte", "remotive"]) == 2
    assert not dentro.exists()
    with pytest.raises(montar.Recusa, match="repositório"):
        montar.conferir_saida(RAIZ / "src")
    assert montar.conferir_saida(tmp_path / "fora") == tmp_path / "fora"  # controle


def test_leituras_recusam_o_caminho_do_gabarito(tmp_path: Path) -> None:
    pasta = tmp_path / "joBot-dados"
    pasta.mkdir()
    (pasta / "treino.jsonl").write_text('{"id": "x"}\n')
    (pasta / "fora.txt").write_text("h0000\n")
    with pytest.raises(montar.Recusa):
        montar.ler(pasta / "treino.jsonl")
    with pytest.raises(montar.Recusa):
        montar.ler_hashes(pasta / "fora.txt")


def test_coleta_liga_so_as_fontes_publicas_permitidas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jobot.banco.cadastros import fontes
    from jobot.nucleo.http import ClienteEducado
    from jobot.nucleo.leitores.registro import LEITORES

    visto: dict[str, Any] = {}

    async def busca_falsa(con: sqlite3.Connection, cliente: Any, relogio: Any, quando: str) -> int:
        visto["ligadas"] = {f.chave for f in fontes(con) if f.ligada}
        visto["caminho"] = con.execute("PRAGMA database_list").fetchone()[2]
        visto["cliente"] = cliente
        return 7

    monkeypatch.setattr(montar, "executar_busca", busca_falsa)
    login = LEITORES[0].chave
    permitidas = frozenset({"remotive", "greenhouse", login})  # a com login entrou por engano
    assert asyncio.run(montar._buscar(tmp_path, permitidas)) == 7
    assert visto["ligadas"] == {"remotive", "greenhouse"}
    assert Path(visto["caminho"]) == tmp_path / "jobot.db"
    assert isinstance(visto["cliente"], ClienteEducado)
    assert visto["cliente"]._ua.startswith("joBot/")


# --- rotular.py -------------------------------------------------------------------------------


class _Professor:
    def __init__(self, respostas: list[object]) -> None:
        self.respostas = respostas
        self.pedidos: list[Pedido] = []

    def pedir(self, pedido: Pedido) -> Resposta:
        self.pedidos.append(pedido)
        dado = self.respostas.pop(0)
        if isinstance(dado, Falha):
            raise dado
        return conferir(pedido, dado, "compativel")


def _registros(n: int) -> list[dict[str, Any]]:
    return [{"id": f"v{i}", "titulo": "Dev", "descricao": LONGA} for i in range(n)]


def _linhas(caminho: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in caminho.read_text().splitlines()]


def test_rotular_descarta_o_que_nao_valida_pula_e_retoma(tmp_path: Path) -> None:
    falhas: list[object] = [Falha("tempo_esgotado")] * rotular.TENTATIVAS
    professor = _Professor(
        [
            {"pede": ["Python", "Docker"]},
            {"pede": "Python"},  # fora do esquema
            {"pede": ["Haskell"]},  # inventado: a anti-invenção esvazia
            *falhas,  # do servidor, sempre na mesma vaga: ela fica pulada e a rodada segue
            {"pede": ["Docker"]},
        ]
    )
    rotulos = tmp_path / "treino.rotulos.jsonl"
    assert rotular.rotular_lado(professor, "prof", _registros(5), rotulos, ()) == (2, 3)
    assert _linhas(rotulos) == [
        {"id": "v0", "pede": ["Python", "Docker"]},
        {"id": "v1", "pede": []},
        {"id": "v2", "pede": []},
        {"id": "v3", "pede": [], "pulada": "tempo_esgotado"},
        {"id": "v4", "pede": ["Docker"]},
    ]
    assert {p.prazo_s for p in professor.pedidos} == {rotular.PRAZO_S}
    professor.respostas = [{"pede": ["PostgreSQL"]}]
    assert rotular.rotular_lado(professor, "prof", _registros(6), rotulos, (), 42.0) == (1, 0)
    assert len(professor.pedidos) == 5 + rotular.TENTATIVAS  # nada foi pedido de novo
    assert professor.pedidos[-1].prazo_s == 42.0
    exemplos = rotular.exemplos_do_lado(
        _registros(6), {r["id"]: r["pede"] for r in _linhas(rotulos)}
    )
    assert {e["id"] for e in exemplos if e["tarefa"] == "habilidades"} == {"v0", "v4", "v5"}


class _ProfessorFora:
    def __init__(self) -> None:
        self.pedidos = 0

    def pedir(self, pedido: Pedido) -> Resposta:
        self.pedidos += 1
        raise Falha("servico_fora")


def test_rotular_para_quando_o_servidor_cai_sem_marcar_as_puladas(tmp_path: Path) -> None:
    rotulos = tmp_path / "treino.rotulos.jsonl"
    fora = _ProfessorFora()
    with pytest.raises(Falha):
        rotular.rotular_lado(fora, "prof", _registros(9), rotulos, ())
    assert fora.pedidos == rotular.MAX_PULADAS_SEGUIDAS * rotular.TENTATIVAS
    assert rotulos.read_text() == ""  # nenhuma vaga ficou marcada: a próxima rodada pede todas
    professor = _Professor([{"pede": ["Python"]}] * 9)
    assert rotular.rotular_lado(professor, "prof", _registros(9), rotulos, ()) == (9, 0)


def test_rotular_para_se_as_primeiras_vagas_vem_vazias(tmp_path: Path) -> None:
    n = rotular.PRIMEIRAS_VAZIAS + 5
    rotulos = tmp_path / "treino.rotulos.jsonl"
    vazio = _Professor([{"pede": ["Haskell"]}] * n)
    with pytest.raises(rotular.ProfessorMalConfigurado):
        rotular.rotular_lado(vazio, "prof", _registros(n), rotulos, ())
    assert len(vazio.pedidos) == rotular.PRIMEIRAS_VAZIAS
    # controle: uma vaga boa entre as primeiras e a rodada vai até o fim
    rotulos.unlink()
    respostas: list[object] = [{"pede": ["Haskell"]}] * n
    respostas[3] = {"pede": ["Python"]}
    assert rotular.rotular_lado(_Professor(respostas), "p", _registros(n), rotulos, ()) == (
        1,
        n - 1,
    )


def test_rotular_refaz_a_ultima_linha_cortada(tmp_path: Path) -> None:
    rotulos = tmp_path / "treino.rotulos.jsonl"
    rotulos.write_text('{"id": "v0", "pede": ["Python"]}\n{"id": "v1", "pe')
    professor = _Professor([{"pede": ["Docker"]}])
    assert rotular.rotular_lado(professor, "prof", _registros(2), rotulos, ()) == (1, 0)
    assert [r["id"] for r in _linhas(rotulos)] == ["v0", "v1"]
    # a última linha inteira mas sem o fim de linha não é pedida de novo nem cola na próxima
    rotulos.write_text('{"id": "v0", "pede": ["Python"]}')
    professor = _Professor([{"pede": ["Docker"]}])
    assert rotular.rotular_lado(professor, "prof", _registros(2), rotulos, ()) == (1, 0)
    assert [r["id"] for r in _linhas(rotulos)] == ["v0", "v1"]
    assert len(professor.pedidos) == 1


def _rotular_main(tmp_path: Path, registro: dict[str, Any], saida: Path) -> int:
    conjunto = tmp_path / "conjunto"
    conjunto.mkdir(exist_ok=True)
    (conjunto / "treino.jsonl").write_text(json.dumps(registro) + "\n")
    (conjunto / "validacao.jsonl").write_text("")
    args = ["--conjunto", str(conjunto), "--saida", str(saida), "--modelo", "p"]
    return int(rotular.main(args, env={}, montar=lambda a, e: _Professor([])))


def test_rotular_main_confere_ouro_na_retomada_e_a_saida(tmp_path: Path) -> None:
    ouro = json.loads(OURO.read_text(encoding="utf-8"))["vagas"][4]
    do_ouro = {"id": "o", "titulo": ouro["titulo"], "descricao": ouro["descricao"]}
    saida = tmp_path / "rotulado"
    saida.mkdir()
    # a vaga do ouro já estava rotulada (rodada antiga): a retomada não a pede, mas o exemplo para
    (saida / "treino.rotulos.jsonl").write_text('{"id": "o", "pede": ["HTML"]}\n')
    assert _rotular_main(tmp_path, do_ouro, saida) == 2
    assert not (saida / "treino.jsonl").exists()
    # saída proibida ou dentro do repositório: recusa sem criar a pasta
    for proibida in (tmp_path / "dados_locais" / "r", RAIZ / "rotulado_teste"):
        assert _rotular_main(tmp_path, do_ouro, proibida) == 2
        assert not proibida.exists()
    # controle: vaga comum já rotulada vira exemplo
    comum = {"id": "c", "titulo": "Dev", "descricao": LONGA}
    (saida / "treino.rotulos.jsonl").write_text('{"id": "c", "pede": ["Python"]}\n')
    assert _rotular_main(tmp_path, comum, saida) == 0
    assert (saida / "treino.jsonl").read_text().count('"tarefa": "habilidades"') == 1


def test_exemplos_custam_o_mesmo_por_vaga(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[int] = []
    original = montar.pede_da_vaga

    def contar(pede: list[str], texto: str) -> list[str]:
        chamadas.append(len(pede))
        return list(original(pede, texto))

    monkeypatch.setattr(montar, "pede_da_vaga", contar)
    n = 300
    registros = _registros(n)
    rotulos = {f"v{i}": ["Python", "Docker", "PostgreSQL", f"Item{i}"] for i in range(n)}
    exemplos = rotular.exemplos_do_lado(registros, rotulos)
    assert len(chamadas) <= n  # uma chamada por vaga, não uma por item do lado
    assert max(chamadas) <= montar.SORTEIO_VF
    for i in range(n):
        vf = [e for e in exemplos if e["id"] == f"v{i}" and e["tarefa"] == "vf"]
        sim = [e for e in vf if '"resposta": true' in e["completion"][0]["content"]]
        nao = [e["prompt"][1]["content"].rsplit("Item: ", 1)[1] for e in vf if e not in sim]
        assert 1 <= len(sim) <= montar.VERDADEIRAS_POR_VAGA
        assert 1 <= len(nao) <= montar.FALSAS_POR_VAGA
        assert all(x.startswith("Item") and x != f"Item{i}" for x in nao)


def test_rotular_recusa_vaga_do_ouro(tmp_path: Path) -> None:
    ouro = json.loads(OURO.read_text(encoding="utf-8"))["vagas"][2]
    registros = [{"id": "o", "titulo": ouro["titulo"], "descricao": ouro["descricao"]}]
    with pytest.raises(montar.Recusa):
        rotular.rotular_lado(
            _Professor([]), "p", registros, tmp_path / "r.jsonl", montar.descricoes_do_ouro()
        )


# --- custo.py ---------------------------------------------------------------------------------


def _gpu(id: str, preco: float | None, memoria: int = 24) -> Any:
    return custo.Gpu(id, id, memoria, preco)


def test_escolhe_o_menor_custo_total_mesmo_mais_lenta() -> None:
    gpus = [
        _gpu("barata_lenta", 0.10),  # 10000 passos a 0,5/s: 5,6 h, US$ 0,56
        _gpu("cara_rapida", 0.40),  # 10000 a 4/s: 0,7 h, US$ 0,28
        _gpu("mais_barata_por_hora", 0.06),  # 10000 a 0,25/s: 11,1 h, US$ 0,67
        _gpu("secure", None),  # só Secure: nunca entra, mesmo rapidíssima
        _gpu("pouca_memoria", 0.01, memoria=8),
        _gpu("sem_medida", 0.02),
    ]
    vazoes = {
        "barata_lenta": 0.5,
        "cara_rapida": 4.0,
        "mais_barata_por_hora": 0.25,
        "secure": 100.0,
        "pouca_memoria": 100.0,
    }
    linhas, escolha = custo.escolher(gpus, vazoes, 10000)
    assert escolha.gpu.id == "cara_rapida"
    assert [x.gpu.id for x in linhas] == [
        "cara_rapida",
        "barata_lenta",
        "mais_barata_por_hora",
        "sem_medida",
    ]
    # a mais lenta ganha quando é a mais barata no total
    _, escolha = custo.escolher(gpus, {**vazoes, "barata_lenta": 2.0}, 10000)
    assert escolha.gpu.id == "barata_lenta"


def test_teto_de_dias_tira_a_gpu_lenta_demais() -> None:
    gpus = [_gpu("lenta", 0.00005), _gpu("rapida", 1.0)]
    # lenta: 10000 passos = 2778 h, US$ 0,14; rápida: 0,28 h, US$ 0,28
    vazoes = {"lenta": 0.001, "rapida": 10.0}
    _, escolha = custo.escolher(gpus, vazoes, 10000)
    assert escolha.gpu.id == "rapida"
    _, escolha = custo.escolher(gpus, vazoes, 10000, max_horas=10**6)
    assert escolha.gpu.id == "lenta"


def test_horas_e_total_pela_vazao_e_passos_pelas_epocas() -> None:
    linhas, escolha = custo.escolher([_gpu("A", 0.10)], {"A": 0.5}, 10000)
    assert escolha is not None
    assert escolha.horas == pytest.approx(10000 / 0.5 / 3600)
    assert escolha.total == pytest.approx(10000 / 0.5 / 3600 * 0.10)
    assert custo.passos_do_treino(1000, 16, 2) == 126  # 63 passos por época
    assert custo.passos_do_treino(1000, 16, 1.5) == 95


@pytest.mark.parametrize("vazao", [{"A": -1.0}, {"A": 0.0}, {"NVIDIA A ": 1.0}])
def test_vazao_ruim_ou_fora_do_catalogo_e_recusada(vazao: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        custo.escolher([_gpu("A", 0.10), _gpu("B", 0.20)], {"B": 1.0, **vazao}, 100)


def _catalogo_falso(pedidos: list[httpx.Request]) -> httpx.Client:
    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        dados = [
            {
                "id": i,
                "displayName": i,
                "memoryInGb": 24,
                "communityCloud": True,
                "communityPrice": p,
            }
            for i, p in (("A", 0.2), ("B", 0.1))
        ]
        return httpx.Response(200, json={"data": {"gpuTypes": dados}})

    return httpx.Client(transport=httpx.MockTransport(responder))


def test_custo_main_escolhe_pelo_total_com_a_acumulacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "segredo")
    (tmp_path / "a.json").write_text('{"gpu": "A", "por_s": 0.5}')
    (tmp_path / "b.json").write_text('{"gpu": "B", "por_s": 0.2}')
    pedidos: list[httpx.Request] = []
    args = ["--vazao", str(tmp_path / "a.json"), str(tmp_path / "b.json"), "--exemplos", "1600"]
    args += ["--epocas", "2", "--lote", "8", "--acumular", "2"]
    assert custo.main(args, cliente=_catalogo_falso(pedidos)) == 0
    # 1600 / (8 × 2) × 2 = 200 passos: A 0,11 h × 0,20 = 0,02; B 0,28 h × 0,10 = 0,03
    assert "Escolha: A (Community), 0.1 h × US$ 0.20/h = US$ 0.02" in capsys.readouterr().out
    assert "authorization" not in pedidos[0].headers
    (tmp_path / "b.json").write_text('{"gpu": "B ", "por_s": 0.9}')  # id fora do catálogo
    assert custo.main(args, cliente=_catalogo_falso(pedidos)) == 2


def test_medir_usa_os_exemplos_mais_longos_e_recusa_saida_no_repo(tmp_path: Path) -> None:
    exemplos = [{"id": str(i), "texto": "x" * i} for i in (5, 50, 1, 20)]
    assert [e["id"] for e in custo.longos(exemplos, 2)] == ["50", "20"]
    args = ["--medir", "--dados", str(tmp_path), "--escrever", str(RAIZ / "vazao.json")]
    assert custo.main(args) == 2


def test_catalogo_so_le_e_guarda_o_preco_community() -> None:
    pedidos: list[httpx.Request] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        dados = [
            {
                "id": "A",
                "displayName": "A",
                "memoryInGb": 24,
                "communityCloud": True,
                "communityPrice": 0.2,
            },
            {
                "id": "S",
                "displayName": "S",
                "memoryInGb": 80,
                "communityCloud": False,
                "communityPrice": 0.5,
            },
            {
                "id": "Z",
                "displayName": "Z",
                "memoryInGb": 80,
                "communityCloud": True,
                "communityPrice": 0,
            },
        ]
        return httpx.Response(200, json={"data": {"gpuTypes": dados}})

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        gpus = custo.catalogo(cliente)
    assert [(g.id, g.preco_h) for g in gpus] == [("A", 0.2), ("S", None), ("Z", None)]
    corpo = json.loads(pedidos[0].content)["query"]
    assert corpo.startswith("query") and "mutation" not in corpo


# --- treinar.py -------------------------------------------------------------------------------


class _TreinoFalso:
    """Grava um checkpoint a cada 10 passos e cai no passo `cai_em` (o pod que some)."""

    def __init__(self, saida: Path, total: int, cai_em: int | None) -> None:
        self.saida, self.total, self.cai_em = saida, total, cai_em
        self.retomou_de: str | None = None
        self.passos_feitos: list[int] = []

    def train(self, resume_from_checkpoint: str | None = None) -> None:
        self.retomou_de = resume_from_checkpoint
        inicio = int(resume_from_checkpoint.rsplit("-", 1)[1]) if resume_from_checkpoint else 0
        for passo in range(inicio + 1, self.total + 1):
            self.passos_feitos.append(passo)
            if passo % 10 == 0:
                pasta = self.saida / f"checkpoint-{passo}"
                pasta.mkdir(exist_ok=True)
                if passo == self.cai_em:
                    raise RuntimeError("pod caiu gravando o checkpoint")
                (pasta / "trainer_state.json").write_text("{}")

    def save_model(self, output_dir: str | None = None) -> None:
        assert output_dir is not None
        Path(output_dir).mkdir()


def test_treino_retoma_do_ultimo_checkpoint_inteiro(tmp_path: Path) -> None:
    dados = tmp_path / "rotulado"
    dados.mkdir()
    exemplo = montar.exemplo_habilidades({"id": "y", "titulo": "Dev", "descricao": LONGA}, ["Go"])
    for nome in ("treino", "validacao"):
        (dados / f"{nome}.jsonl").write_text(json.dumps(exemplo) + "\n")
    args = argparse.Namespace(dados=dados, saida=tmp_path / "laya", recorte=0)
    falsos: list[_TreinoFalso] = []

    def montar_falso(cai_em: int | None) -> Any:
        def montar_(a: argparse.Namespace, treino: list[Any], val: list[Any]) -> _TreinoFalso:
            falsos.append(_TreinoFalso(a.saida, 50, cai_em))
            return falsos[-1]

        return montar_

    with pytest.raises(RuntimeError):
        treinar.treinar(args, montar_falso(cai_em=30))  # 30 ficou cortado
    assert falsos[0].retomou_de is None
    final = treinar.treinar(args, montar_falso(cai_em=None))
    assert falsos[1].retomou_de == str(tmp_path / "laya" / "checkpoint-20")
    assert falsos[1].passos_feitos[0] == 21
    assert final == tmp_path / "laya" / "lora" and final.is_dir()


def test_ultimo_checkpoint_ignora_o_cortado_e_ordena_por_numero(tmp_path: Path) -> None:
    assert treinar.ultimo_checkpoint(tmp_path / "nada") is None
    for n, estado in ((9, "{}"), (100, "{}"), (200, None), (300, '{"global_st')):
        (tmp_path / f"checkpoint-{n}").mkdir()
        if estado is not None:
            (tmp_path / f"checkpoint-{n}" / "trainer_state.json").write_text(estado)
    assert treinar.ultimo_checkpoint(tmp_path) == tmp_path / "checkpoint-100"


def test_base_e_o_original_do_2b_do_manifesto() -> None:
    assert treinar.base_do_manifesto() == "Qwen/Qwen3.5-2B"


def test_entrada_do_manifesto_tem_sha256_e_tamanho(tmp_path: Path) -> None:
    gguf = tmp_path / "Laya-2B-Q4_K_M.gguf"
    gguf.write_bytes(b"GGUF" + bytes(10))
    entrada = treinar.entrada_manifesto(gguf, "https://exemplo.invalid/v1/x.gguf", "Qwen/X")
    assert entrada["tamanho"] == 14
    assert entrada["sha256"] == hashlib.sha256(b"GGUF" + bytes(10)).hexdigest()
    assert set(entrada) == {"nome", "arquivo", "url", "tamanho", "sha256", "licenca", "origem"}


def test_treino_recusa_saida_proibida(tmp_path: Path) -> None:
    for saida in (tmp_path / "dados_locais" / "laya", RAIZ / "laya_teste"):
        args = argparse.Namespace(dados=tmp_path, saida=saida, recorte=0)
        with pytest.raises(montar.Recusa):
            treinar.treinar(args, lambda *a: pytest.fail("não devia montar"))
        assert not saida.exists()


def test_exportar_converte_em_outro_ambiente_e_assina_o_q4(tmp_path: Path) -> None:
    saida, llama = tmp_path / "laya", tmp_path / "llama.cpp"
    saida.mkdir()
    ordem: list[str] = []

    def juntar(pasta: Path, base: str) -> Path:
        ordem.append(f"juntar {base}")
        return pasta / "junto"

    def rodar(comando: list[str], check: bool) -> None:
        assert check
        ordem.append(comando[0])
        if comando[0] == "uv":  # o conversor escreve o f16
            Path(comando[comando.index("--outfile") + 1]).write_bytes(b"f16" * 100)
        else:  # o llama-quantize escreve o Q4_K_M
            Path(comando[2]).write_bytes(b"q4km!")
        ordem.append(" ".join(comando))

    args = argparse.Namespace(
        saida=saida,
        llama_cpp=llama,
        base="Qwen/X",
        url="https://exemplo.invalid/v1/Laya-2B-Q4_K_M.gguf",
        python_conversor="uv run --no-project --with-requirements req.txt python",
    )
    gguf = treinar.exportar(args, juntar, rodar)
    assert ordem[0] == "juntar Qwen/X"
    assert ordem[2].startswith(
        f"uv run --no-project --with-requirements req.txt python {llama}/convert_hf_to_gguf.py "
        f"{saida}/junto --outfile"
    )
    assert ordem[4].startswith(f"{llama}/build/bin/llama-quantize {saida}/laya-2b-f16.gguf")
    manifesto = json.loads((saida / "manifesto_laya.json").read_text())["laya"]
    assert manifesto["sha256"] == hashlib.sha256(b"q4km!").hexdigest()
    assert manifesto["tamanho"] == 5
    assert gguf == saida / "Laya-2B-Q4_K_M.gguf"


def test_config_do_treino_sem_warmup_ratio_e_avaliacao_num_recorte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def registrar(**kw: Any) -> dict[str, Any]:
        return kw

    monkeypatch.setitem(
        sys.modules, "trl", SimpleNamespace(SFTConfig=registrar, SFTTrainer=registrar)
    )
    monkeypatch.setitem(sys.modules, "peft", SimpleNamespace(LoraConfig=registrar))
    monkeypatch.setitem(
        sys.modules, "datasets", SimpleNamespace(Dataset=SimpleNamespace(from_list=list))
    )
    exemplo: dict[str, list[Any]] = {"prompt": [], "completion": []}
    args = argparse.Namespace(
        saida=Path("/x"),
        epocas=2.0,
        max_passos=-1,
        lote=8,
        acumular=2,
        taxa=2e-4,
        salvar_a_cada=100,
        max_tokens=3072,
        rank=16,
        base="Qwen/X",
        avaliar=3,
    )
    montado: Any = treinar.montar_hf(args, [exemplo] * 5, [exemplo] * 10)
    config = montado["args"]
    # transformers 5 tirou `warmup_ratio`; `warmup_steps` < 1 vale como proporção
    assert "warmup_ratio" not in config and config["warmup_steps"] == 0.03
    assert config["eval_strategy"] == "epoch" and "eval_steps" not in config
    assert len(montado["eval_dataset"]) == 3
    args.avaliar = 0
    montado = treinar.montar_hf(args, [exemplo] * 5, [exemplo] * 10)
    assert montado["args"]["eval_strategy"] == "no" and montado["eval_dataset"] is None


def test_treino_nem_comeca_com_exemplo_do_ouro(tmp_path: Path) -> None:
    ouro = json.loads(OURO.read_text(encoding="utf-8"))["vagas"][3]
    dados = tmp_path / "rotulado"
    dados.mkdir()
    do_ouro = montar.exemplo_habilidades(
        {"id": "o", "titulo": ouro["titulo"], "descricao": ouro["descricao"]}, ["SQL"]
    )
    (dados / "treino.jsonl").write_text(json.dumps(do_ouro) + "\n")
    (dados / "validacao.jsonl").write_text("")
    montados: list[object] = []

    def montar_(a: argparse.Namespace, treino: list[Any], val: list[Any]) -> _TreinoFalso:
        montados.append(a)
        return _TreinoFalso(a.saida, 10, None)

    args = argparse.Namespace(dados=dados, saida=tmp_path / "laya", recorte=0)
    with pytest.raises(montar.Recusa, match="ouro"):
        treinar.treinar(args, montar_)
    assert montados == []
    # controle: sem a vaga do ouro, o mesmo treino roda
    comum = montar.exemplo_habilidades({"id": "y", "titulo": "Dev", "descricao": LONGA}, ["Go"])
    (dados / "treino.jsonl").write_text(json.dumps(comum) + "\n")
    treinar.treinar(args, montar_)
    assert len(montados) == 1


# --- juntar_lora: o merge e o tokenizador (D219.18) ---------------------------------------------
# Falsos do torch, do peft, do transformers e do huggingface_hub: o Qwen3.5 é multimodal e o
# LoRA do SFTTrainer tem as chaves da classe de imagem e texto (`model.language_model.layers`).


class _Modelo:
    def __init__(self, base: str, chaves: str, juntou: bool = False) -> None:
        self.base, self.chaves, self.juntou = base, chaves, juntou

    def save_pretrained(self, pasta: str) -> None:
        Path(pasta).mkdir(parents=True, exist_ok=True)
        conteudo = {"base": self.base, "juntou": self.juntou}
        (Path(pasta) / "config.json").write_text(json.dumps(conteudo))


class _ComLora:
    def __init__(self, modelo: _Modelo, lora: str) -> None:
        self.modelo, self.lora = modelo, lora

    def merge_and_unload(self) -> _Modelo:
        # as chaves do LoRA só casam com a classe multimodal; senão o merge não muda nada
        casou = self.modelo.chaves == "model.language_model.layers"
        return _Modelo(self.modelo.base, self.modelo.chaves, juntou=casou)


def _falsos_do_merge(monkeypatch: pytest.MonkeyPatch, origem: Path) -> None:
    def multimodal(base: str, **_kw: Any) -> _Modelo:
        return _Modelo(base, "model.language_model.layers")

    def so_texto(lora: str, **_kw: Any) -> _ComLora:
        return _ComLora(_Modelo("Qwen/Qwen3.5-2B", "model.layers"), lora)

    class _Tokenizador:
        def save_pretrained(self, pasta: str) -> None:
            # o transformers 5 grava a classe nova, que o conversor do llama.cpp não conhece
            (Path(pasta) / "tokenizer_config.json").write_text(
                json.dumps({"tokenizer_class": "Qwen3_5Tokenizer"})
            )

    transformers = SimpleNamespace(
        AutoModelForImageTextToText=SimpleNamespace(from_pretrained=multimodal),
        AutoModelForCausalLM=SimpleNamespace(
            from_pretrained=lambda b, **kw: _Modelo(b, "model.layers")
        ),
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda b, **kw: _Tokenizador()),
    )
    peft = SimpleNamespace(
        PeftModel=SimpleNamespace(from_pretrained=lambda m, lora, **kw: _ComLora(m, lora)),
        AutoPeftModelForCausalLM=SimpleNamespace(from_pretrained=so_texto),
    )
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "peft", peft)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(bfloat16="bf16"))
    # a cópia local do repositório original traz também os pesos e o config.json dele
    hub = SimpleNamespace(snapshot_download=lambda repo, **kw: str(origem))
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)


def _snapshot(pasta: Path) -> Path:
    pasta.mkdir()
    (pasta / "tokenizer_config.json").write_text(json.dumps({"tokenizer_class": "Qwen2Tokenizer"}))
    (pasta / "tokenizer.json").write_text('{"model": {}}')
    (pasta / "chat_template.jinja").write_text("{{ messages }}")
    (pasta / "config.json").write_text(json.dumps({"base": "original", "juntou": False}))
    (pasta / "model.safetensors").write_bytes(b"pesos do original")
    return pasta


def test_juntar_lora_pela_classe_multimodal_muda_o_modelo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _falsos_do_merge(monkeypatch, _snapshot(tmp_path / "snapshot"))
    junto = treinar.juntar_lora(tmp_path / "laya", "Qwen/Qwen3.5-2B")
    config = json.loads((junto / "config.json").read_text())
    # pela classe só de texto as chaves não casam e o "junto" sai igual ao base
    assert config == {"base": "Qwen/Qwen3.5-2B", "juntou": True}


def test_juntar_lora_copia_so_o_tokenizador_do_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origem = _snapshot(tmp_path / "snapshot")
    _falsos_do_merge(monkeypatch, origem)
    junto = treinar.juntar_lora(tmp_path / "laya", "Qwen/Qwen3.5-2B")
    # a classe que o conversor do llama.cpp conhece, do repositório original
    tokenizador = json.loads((junto / "tokenizer_config.json").read_text())
    assert tokenizador == {"tokenizer_class": "Qwen2Tokenizer"}
    for nome in ("tokenizer.json", "chat_template.jinja"):
        assert (junto / nome).read_bytes() == (origem / nome).read_bytes()
    # só os do tokenizador: o config.json e os pesos do original não pisam no junto
    assert json.loads((junto / "config.json").read_text())["base"] == "Qwen/Qwen3.5-2B"
    assert not (junto / "model.safetensors").exists()


def test_lora_fora_da_torre_de_visao(monkeypatch: pytest.MonkeyPatch) -> None:
    def registrar(**kw: Any) -> dict[str, Any]:
        return kw

    monkeypatch.setitem(
        sys.modules, "trl", SimpleNamespace(SFTConfig=registrar, SFTTrainer=registrar)
    )
    monkeypatch.setitem(sys.modules, "peft", SimpleNamespace(LoraConfig=registrar))
    monkeypatch.setitem(
        sys.modules, "datasets", SimpleNamespace(Dataset=SimpleNamespace(from_list=list))
    )
    args = argparse.Namespace(
        saida=Path("/x"), epocas=2.0, max_passos=-1, lote=8, acumular=2, taxa=2e-4,
        salvar_a_cada=100, max_tokens=3072, rank=16, base="Qwen/X", avaliar=0,
    )  # fmt: skip
    lora: Any = treinar.montar_hf(args, [], [])["peft_config"]
    fora = lora.get("exclude_modules")
    assert fora is not None and re.fullmatch(fora, "model.visual.blocks.0.attn.qkv")
    # controle: as camadas de texto continuam no LoRA
    assert not re.fullmatch(fora, "model.language_model.layers.0.self_attn.q_proj")


def test_requisitos_do_treino_trazem_os_da_classe_multimodal() -> None:
    linhas = (PASTA / "requirements.txt").read_text(encoding="utf-8").splitlines()
    fixados = {linha.split("==")[0]: linha for linha in linhas if "==" in linha}
    assert fixados.get("torchvision") == "torchvision==0.29.2"
    assert fixados.get("pillow") == "pillow==13.0.0"
    assert fixados.get("flash-linear-attention") == "flash-linear-attention==0.6.0"
    assert fixados["torch"] == "torch==2.15.0"  # controle: leu o arquivo
