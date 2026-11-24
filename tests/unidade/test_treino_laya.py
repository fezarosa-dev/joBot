"""Regras duras do treino do Laya (T419; D219): `scripts/treino_laya/`, sem rede nem GPU."""

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from types import ModuleType
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
    assert montar.main(["montar", "--banco", str(banco), "--saida", str(saida)]) == 2
    assert not saida.exists()
    # controle: a mesma montagem com a fonte liberada escreve a vaga
    args = ["montar", "--banco", str(banco), "--saida", str(saida), "--fonte", "remotive"]
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
    assert montar.main(["montar", *args]) == 2
    banco = _banco(tmp_path, [{"fontes": ["remotive"]}])
    saida = ["--saida", str(tmp_path / pasta / "s"), "--fonte", "remotive"]
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


def test_rotular_descarta_o_que_nao_valida_e_retoma(tmp_path: Path) -> None:
    registros = [{"id": f"v{i}", "titulo": "Dev", "descricao": LONGA} for i in range(4)]
    professor = _Professor(
        [
            {"pede": ["Python", "Docker"]},
            {"pede": "Python"},  # fora do esquema
            {"pede": ["Haskell"]},  # inventado: a anti-invenção esvazia
            Falha("sem_rede"),  # do backend: para e a próxima rodada retoma
        ]
    )
    rotulos = tmp_path / "treino.rotulos.jsonl"
    with pytest.raises(Falha):
        rotular.rotular_lado(professor, "prof", registros, rotulos, ())
    feitos = [json.loads(x) for x in rotulos.read_text().splitlines()]
    assert feitos == [
        {"id": "v0", "pede": ["Python", "Docker"]},
        {"id": "v1", "pede": []},
        {"id": "v2", "pede": []},
    ]
    professor.respostas = [{"pede": ["PostgreSQL"]}]
    assert rotular.rotular_lado(professor, "prof", registros, rotulos, ()) == (1, 0)
    assert len(professor.pedidos) == 5  # v0 a v2 não foram pedidas de novo
    exemplos = rotular.exemplos_do_lado(
        registros, {r["id"]: r["pede"] for r in map(json.loads, rotulos.read_text().splitlines())}
    )
    assert {e["id"] for e in exemplos if e["tarefa"] == "habilidades"} == {"v0", "v3"}


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
    args = argparse.Namespace(dados=dados, saida=tmp_path / "laya")
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
    for n, inteiro in ((9, True), (100, True), (200, False)):
        (tmp_path / f"checkpoint-{n}").mkdir()
        if inteiro:
            (tmp_path / f"checkpoint-{n}" / "trainer_state.json").write_text("{}")
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

    args = argparse.Namespace(dados=dados, saida=tmp_path / "laya")
    with pytest.raises(montar.Recusa, match="ouro"):
        treinar.treinar(args, montar_)
    assert montados == []
    # controle: sem a vaga do ouro, o mesmo treino roda
    comum = montar.exemplo_habilidades({"id": "y", "titulo": "Dev", "descricao": LONGA}, ["Go"])
    (dados / "treino.jsonl").write_text(json.dumps(comum) + "\n")
    treinar.treinar(args, montar_)
    assert len(montados) == 1
