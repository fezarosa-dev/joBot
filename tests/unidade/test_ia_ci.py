"""A prova do modelo de verdade (T410; desenho 12 da fase 4): o `ia.yml`, o conjunto de ouro e os
scripts `provar_ia.py` e `medir_modelo.py`, sem rede (backend falso e `httpx.MockTransport`)."""

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from jobot.nucleo.ia.contrato import Falha, limites
from jobot.nucleo.ia.falso import BackendFalso
from jobot.nucleo.ia.pedidos import pedido_encaixe, texto_encaixe
from jobot.nucleo.ia.tarefas import pede_da_vaga
from jobot.nucleo.texto import normalizar

RAIZ = Path(__file__).resolve().parents[2]
IA = RAIZ / ".github" / "workflows" / "ia.yml"
OURO = RAIZ / "tests" / "fixtures" / "ia" / "ouro_habilidades.json"
MANIFESTO = RAIZ / "src" / "jobot" / "nucleo" / "dados" / "ia_local.json"


def _script(nome: str) -> ModuleType:
    # o `medir_modelo` importa o `provar_ia` como na linha de comando (a pasta do script no path)
    if nome in sys.modules:
        return sys.modules[nome]
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / f"{nome}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


provar = _script("provar_ia")
medir = _script("medir_modelo")


def _codigo() -> str:
    bruto = IA.read_text(encoding="utf-8")
    return "\n".join(x for x in bruto.splitlines() if not x.lstrip().startswith("#"))


def _secao(texto: str, chave: str) -> list[str]:
    linhas = texto.splitlines()
    corpo = []
    for linha in linhas[linhas.index(f"{chave}:") + 1 :]:
        if linha and not linha.startswith(" "):
            break
        if linha.strip():
            corpo.append(linha.strip())
    return corpo


# --- ia.yml -----------------------------------------------------------------------------------


def test_ia_so_por_workflow_call_so_leitura_e_sem_segredo() -> None:
    texto = _codigo()
    assert _secao(texto, "on") == ["workflow_call:"]
    assert _secao(texto, "permissions") == ["contents: read"]
    assert texto.count("permissions:") == 1
    assert "secrets" not in texto
    assert "pull_request" not in texto


def test_actions_do_ia_fixadas_por_hash_com_versao() -> None:
    usos = re.findall(r"^\s*(?:- )?uses: (.+)$", IA.read_text(encoding="utf-8"), re.MULTILINE)
    assert usos
    for uso in usos:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+", uso), uso


def test_matriz_nos_tres_sistemas_com_prazo() -> None:
    texto = _codigo()
    assert "os: [ubuntu-22.04, windows-latest, macos-latest]" in texto
    assert "runs-on: ${{ matrix.os }}" in texto
    assert "fail-fast: false" in texto
    assert "timeout-minutes:" in texto
    assert "uv sync --locked" in texto


def test_passos_baixam_atestam_provam_e_medem_os_dois_modelos() -> None:
    texto = _codigo()
    passos = [
        "uv run jobot ferramentas baixar ia-local --modelo auto",
        "gh attestation verify",
        "uv run python scripts/provar_ia.py",
        "uv run python scripts/medir_modelo.py",
        "uv run jobot ferramentas baixar ia-local --modelo 2b",
    ]
    posicoes = [texto.index(p) for p in passos]
    assert posicoes == sorted(posicoes)
    # depois do 2B, a prova e a medida de novo
    depois = texto[texto.index(passos[-1]) :]
    assert "scripts/provar_ia.py" in depois
    assert "scripts/medir_modelo.py" in depois
    assert "JOBOT_DADOS=" in texto  # nada na pasta de dados do runner


def test_atestacao_com_o_dono_e_o_workflow_do_manifesto() -> None:
    atestacao = json.loads(MANIFESTO.read_text(encoding="utf-8"))["llama_server"]["atestacao"]
    texto = _codigo()
    comando = next(x for x in texto.splitlines() if "gh attestation verify" in x)
    assert f"--owner {atestacao['owner']}" in comando
    assert f"--signer-workflow {atestacao['workflow']}" in comando
    # o pacote conferido é o da URL do manifesto para este alvo, o mesmo que o joBot baixa
    assert "manifesto_local()" in texto and "ALVO" in texto
    assert "GH_TOKEN: ${{ github.token }}" in texto


# --- conjunto de ouro -------------------------------------------------------------------------


def _ouro() -> list[dict[str, Any]]:
    vagas: list[dict[str, Any]] = json.loads(OURO.read_text(encoding="utf-8"))["vagas"]
    return vagas


def test_ouro_tem_umas_20_vagas_com_o_esperado_escrito_nelas() -> None:
    vagas = _ouro()
    assert 18 <= len(vagas) <= 25
    for vaga in vagas:
        assert set(vaga) == {"titulo", "descricao", "esperado"}, vaga["titulo"]
        esperado = vaga["esperado"]
        assert esperado, vaga["titulo"]
        assert len({normalizar(x) for x in esperado}) == len(esperado), vaga["titulo"]
        # a anti-invenção deixa passar cada item: o modelo consegue achar todos
        texto = texto_encaixe(vaga["titulo"], vaga["descricao"])
        assert texto.cortados == 0
        assert pede_da_vaga(esperado, texto.texto) == esperado, vaga["titulo"]


# --- provar_ia.py -----------------------------------------------------------------------------


def _vaga(titulo: str, descricao: str, esperado: list[str]) -> dict[str, Any]:
    return {"titulo": titulo, "descricao": descricao, "esperado": esperado}


DUAS = [
    _vaga(
        "Dev Python",
        "Requisitos: Python, Django, Docker e Redis.",
        ["Python", "Django", "Docker", "Redis"],
    ),
    _vaga("Analista", "Pedimos Excel e Power BI.", ["Excel", "Power BI"]),
]


def test_acerto_conta_o_esperado_achado_com_caixa_e_acento_diferentes() -> None:
    # "docker" casa "Docker"; "Kubernetes" não está na vaga e sai (anti-invenção); "Redis" falta
    falso = BackendFalso(
        [{"pede": ["python", "Django.", "docker", "Kubernetes"]}, {"pede": ["Excel", "power bi"]}]
    )
    resultado = provar.avaliar(
        falso, "local", "m", DUAS, relogio=iter([0.0, 2.0, 2.0, 5.0]).__next__
    )
    assert (resultado.esperados, resultado.achados, resultado.vazias) == (6, 5, 0)
    assert resultado.acerto == pytest.approx(5 / 6)
    assert resultado.tempos == [2.0, 3.0]
    assert resultado.faltas == [("Dev Python", ["Redis"])]
    assert resultado.passou


def test_pede_o_mesmo_pedido_do_encaixe() -> None:
    falso = BackendFalso([{"pede": []}, {"pede": []}])
    provar.avaliar(falso, "local", "Qwen", DUAS)
    esperado = pedido_encaixe(
        texto_encaixe(DUAS[0]["titulo"], DUAS[0]["descricao"]), "local", "Qwen"
    )
    assert falso.pedidos[0] == esperado


@pytest.mark.parametrize(
    ("achados", "vazias", "passou"),
    [(8, 0, True), (7, 0, False), (10, 1, False), (10, 0, True)],
)
def test_meta_de_80_por_cento_e_nenhum_pede_vazio(achados: int, vazias: int, passou: bool) -> None:
    resultado = provar.Resultado(esperados=10, achados=achados, vazias=vazias)
    assert resultado.passou is passou


def test_falha_da_vaga_conta_como_pede_vazio_e_segue() -> None:
    falso = BackendFalso([Falha("formato"), {"pede": ["Excel", "Power BI"]}])
    resultado = provar.avaliar(falso, "local", "m", DUAS)
    assert (resultado.achados, resultado.vazias, len(falso.pedidos)) == (2, 1, 2)
    assert not resultado.passou


def test_pede_vazio_depois_da_anti_invencao_conta_como_vazio() -> None:
    falso = BackendFalso([{"pede": ["Kubernetes"]}, {"pede": ["Excel", "Power BI"]}])
    assert provar.avaliar(falso, "local", "m", DUAS).vazias == 1


def _montar(falso: BackendFalso, fechou: list[bool]) -> Any:
    def montar(args: Any, env: Any) -> tuple[BackendFalso, str, Any]:
        return falso, "Qwen", lambda: fechou.append(True)

    return montar


def test_main_sai_com_erro_abaixo_da_meta_e_escreve_o_resumo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ouro = tmp_path / "ouro.json"
    ouro.write_text(json.dumps({"vagas": DUAS}), encoding="utf-8")
    resumo = tmp_path / "resumo.md"
    fechou: list[bool] = []
    falso = BackendFalso([{"pede": ["Python"]}, {"pede": ["Excel"]}])
    env = {"GITHUB_STEP_SUMMARY": str(resumo)}
    codigo = provar.main(
        ["--ouro", str(ouro), "--rotulo", "ubuntu-22.04"], env=env, montar=_montar(falso, fechou)
    )
    assert codigo == 1
    assert fechou == [True]
    texto = resumo.read_text(encoding="utf-8")
    assert "ubuntu-22.04" in texto and "Qwen" in texto and "33%" in texto
    linha = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (linha["acerto"], linha["passou"], linha["modelo"]) == (
        pytest.approx(2 / 6),
        False,
        "Qwen",
    )


def test_main_sai_com_zero_na_meta(tmp_path: Path) -> None:
    ouro = tmp_path / "ouro.json"
    ouro.write_text(json.dumps({"vagas": DUAS}), encoding="utf-8")
    falso = BackendFalso([{"pede": ["Python", "Django", "Docker", "Redis"]}, {"pede": ["Excel"]}])
    assert provar.main(["--ouro", str(ouro)], env={}, montar=_montar(falso, [])) == 0


def test_falha_do_backend_para_a_prova(tmp_path: Path) -> None:
    ouro = tmp_path / "ouro.json"
    ouro.write_text(json.dumps({"vagas": DUAS}), encoding="utf-8")
    fechou: list[bool] = []
    falso = BackendFalso([Falha("sem_rede"), {"pede": ["Excel"]}])
    assert provar.main(["--ouro", str(ouro)], env={}, montar=_montar(falso, fechou)) == 1
    assert len(falso.pedidos) == 1
    assert fechou == [True]


def _resposta_openai(pede: list[str], timings: dict[str, float] | None = None) -> dict[str, Any]:
    corpo: dict[str, Any] = {"choices": [{"message": {"content": json.dumps({"pede": pede})}}]}
    if timings is not None:
        corpo["timings"] = timings
    return corpo


def test_backend_de_fora_leva_a_chave_da_variavel_de_ambiente() -> None:
    vistos: list[httpx.Request] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        vistos.append(pedido)
        return httpx.Response(200, json=_resposta_openai(["Excel"]))

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    args = provar.argumentos(["--backend", "openai", "--modelo", "gpt-x", "--chave-env", "MINHA"])
    backend, modelo, fechar = provar.montar_backend(args, {"MINHA": "sk-teste"}, cliente=cliente)
    provar.avaliar(backend, "openai", modelo, DUAS[1:])
    fechar()
    assert modelo == "gpt-x"
    assert str(vistos[0].url) == "https://api.openai.com/v1/chat/completions"
    assert vistos[0].headers["Authorization"] == "Bearer sk-teste"


@pytest.mark.parametrize("backend", ["openai", "anthropic"])
def test_backend_de_fora_sem_a_chave_nao_manda_nada(tmp_path: Path, backend: str) -> None:
    # guarda; o controle é o teste acima, com a mesma montagem e a chave no ambiente
    ouro = tmp_path / "ouro.json"
    ouro.write_text(json.dumps({"vagas": DUAS}), encoding="utf-8")
    vistos: list[httpx.Request] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        vistos.append(pedido)
        return httpx.Response(500)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))

    def montar(args: Any, env: Any) -> Any:
        return provar.montar_backend(args, env, cliente=cliente)

    argv = ["--ouro", str(ouro), "--backend", backend, "--modelo", "claude-haiku-5-5"]
    assert provar.main(argv, env={"OUTRA": "k"}, montar=montar) == 2
    assert vistos == []


def test_anthropic_usa_o_cliente_proprio() -> None:
    args = provar.argumentos(["--backend", "anthropic", "--modelo", "claude-haiku-5-5"])
    backend, _, fechar = provar.montar_backend(args, {"JOBOT_IA_CHAVE": "k"})
    fechar()
    assert type(backend).__name__ == "ClienteAnthropic"


def test_caminhos_do_local_vem_da_anotacao(tmp_path: Path) -> None:
    ferramentas = tmp_path / "ferramentas"
    ferramentas.mkdir()
    anotacao = {
        "modelo": "2b",
        "arquivo": "Qwen3.5-2B-Q4_K_M.gguf",
        "programa": "llama/b12359/llama-server",
    }
    (ferramentas / "ia_local.json").write_text(json.dumps(anotacao), encoding="utf-8")
    programa, gguf, nome = provar.caminhos_local(tmp_path)
    assert programa == ferramentas / "llama" / "b12359" / "llama-server"
    assert gguf == ferramentas / "modelos" / "Qwen3.5-2B-Q4_K_M.gguf"
    assert nome == "Qwen3.5-2B-Q4_K_M"


def test_sem_modelo_baixado_e_modelo_ausente(tmp_path: Path) -> None:
    with pytest.raises(Falha) as erro:
        provar.caminhos_local(tmp_path)
    assert erro.value.motivo == "modelo_ausente"


# --- medir_modelo.py --------------------------------------------------------------------------


def test_vagas_longas_tem_o_tamanho_do_corte_e_sao_diferentes() -> None:
    corte = limites()["tarefas"]["encaixe"]["corte"]
    longas = medir.vagas_longas(_ouro(), 3)
    assert len(longas) == 3
    assert len({d for _, d in longas}) == 3  # o cache do prompt não pula a leitura
    for titulo, descricao in longas:
        assert len(descricao) == corte["inicio"] + corte["fim"]
        assert texto_encaixe(titulo, descricao).cortados == 0


TIMINGS = {
    "prompt_n": 1500,
    "prompt_per_second": 50.0,
    "predicted_n": 40,
    "predicted_per_second": 8.0,
}


def _cliente_gravado(timings: dict[str, float] | None) -> tuple[Any, httpx.Client]:
    gravador = medir.Gravador(
        httpx.MockTransport(
            lambda _: httpx.Response(200, json=_resposta_openai(["Python"], timings))
        )
    )
    return gravador, httpx.Client(transport=gravador)


def test_gravador_le_os_timings_e_a_resposta_segue_legivel() -> None:
    from jobot.nucleo.ia.compativel_openai import ClienteCompativel

    gravador, cliente = _cliente_gravado(TIMINGS)
    backend = ClienteCompativel("local", "http://127.0.0.1:9/v1", "k", cliente=cliente)
    resposta = backend.pedir(pedido_encaixe(texto_encaixe("Dev", "Python"), "local", "m"))
    assert resposta.dados == {"pede": ["Python"]}
    assert gravador.timings == [TIMINGS]


def test_medir_junta_tempo_e_tokens_por_segundo() -> None:
    from jobot.nucleo.ia.compativel_openai import ClienteCompativel

    gravador, cliente = _cliente_gravado(TIMINGS)
    backend = ClienteCompativel("local", "http://127.0.0.1:9/v1", "k", cliente=cliente)
    vagas = [("Dev", "Python " * 10), ("Dev 2", "Python " * 11)]
    medidas = medir.medir(
        backend, gravador, "m", vagas, relogio=iter([0.0, 30.0, 30.0, 70.0]).__next__
    )
    assert [m.segundos for m in medidas] == [30.0, 40.0]
    assert [(m.leitura_n, m.leitura_tps, m.geracao_n, m.geracao_tps) for m in medidas] == [
        (1500, 50.0, 40, 8.0)
    ] * 2
    texto = medir.resumo(medidas, "windows-latest", "Qwen", carga_s=12.0)
    for parte in ("windows-latest", "Qwen", "50.0", "8.0", "35.0", "40.0", "12.0"):
        assert parte in texto, parte


def test_medir_sem_timings_nao_inventa_numero() -> None:
    from jobot.nucleo.ia.compativel_openai import ClienteCompativel

    gravador, cliente = _cliente_gravado(None)
    backend = ClienteCompativel("local", "http://127.0.0.1:9/v1", "k", cliente=cliente)
    medida = medir.medir(
        backend, gravador, "m", [("Dev", "Python")], relogio=iter([0.0, 1.0]).__next__
    )[0]
    assert (medida.leitura_tps, medida.geracao_tps) == (None, None)
    assert "?" in medir.resumo([medida], "x", "m", carga_s=0.0)
