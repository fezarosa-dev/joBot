"""Prova das três tarefas novas no modelo local (T445): o `provar_tarefas.py` sem rede (backend
falso que anota os `timings`, como o `llama-server` os põe na resposta)."""

import importlib.util
import json
import sys
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from jobot.nucleo.ia.contrato import Falha, Motivo, Pedido, Resposta, limites
from jobot.nucleo.ia.falso import BackendFalso
from jobot.nucleo.ia.pedidos import limpar_contato
from jobot.sistema.llama import CONTEXTO

RAIZ = Path(__file__).resolve().parents[2]


def _script(nome: str) -> ModuleType:
    # como na linha de comando: o script importa os vizinhos pelo nome
    if nome in sys.modules:
        return sys.modules[nome]
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / f"{nome}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


_script("provar_ia")
_script("medir_modelo")
provar = _script("provar_tarefas")

NOMES = [
    "curriculo",
    "curriculo_longo",
    "perguntas",
    "perguntas_longo",
    "candidatura",
    "candidatura_longa",
]
VALIDAS: dict[str, dict[str, object]] = {
    "curriculo": {"cargo_atual": "Desenvolvedora Python Pleno", "habilidades": ["Python"]},
    "perguntas": {"perguntas": [{"pergunta": "Já usou Kubernetes?", "por_que": "a vaga pede"}]},
    "candidatura": {"idioma": "pt", "carta": "Olá.", "resumo": "Dev Python.", "usou": ["resumo"]},
}
TIMINGS = {"prompt_n": 3000, "predicted_n": 400}


class _Gravado(BackendFalso):
    """Anota os `timings` de cada resposta na lista, como o `Gravador` do `medir_modelo`."""

    def __init__(
        self,
        prontas: list[dict[str, object] | Falha],
        timings: list[dict[str, Any] | None],
        por_pedido: Callable[[Pedido], dict[str, Any] | None] = lambda _: dict(TIMINGS),
    ) -> None:
        super().__init__(prontas)
        self.timings = timings
        self.por_pedido = por_pedido

    def pedir(self, pedido: Pedido) -> Resposta:
        if not isinstance(self.prontas[0], Falha):
            self.timings.append(self.por_pedido(pedido))
        return super().pedir(pedido)


def _casos() -> list[Any]:
    casos: list[Any] = provar.casos("laya")
    assert len(casos) == len(NOMES)
    return casos


def _relogio(passo: float) -> Callable[[], float]:
    contas: Iterator[float] = (passo * n for n in range(1000))
    return lambda: next(contas)


def _validas(casos: list[Any]) -> list[dict[str, object] | Falha]:
    return [VALIDAS[c.pedido.tarefa] for c in casos]


def test_casos_cobrem_as_tres_tarefas_no_local_com_o_pior_caso() -> None:
    casos = _casos()
    assert [c.nome for c in casos] == NOMES
    lim = limites()
    for caso in casos:
        tarefa = caso.pedido.tarefa
        assert tarefa == caso.nome.split("_")[0]
        assert caso.pedido.max_tokens == lim["tarefas"][tarefa]["max_tokens"]["local"], caso.nome
        assert caso.pedido.prazo_s == lim["prazo_s"]["local"]
        assert caso.pedido.modelo == "laya"


def test_curriculo_vem_do_pdf_montado_e_os_longos_passam_do_corte() -> None:
    casos = {c.nome: c.pedido.mensagens[1].texto for c in _casos()}
    # o texto lido do PDF pelo leitor de produção, com os acentos
    assert "FastAPI" in casos["curriculo"] and "Análise e Desenvolvimento" in casos["curriculo"]
    assert "was cut" not in casos["curriculo"]
    assert "The resume was cut" in casos["curriculo_longo"]
    assert "was cut" not in casos["candidatura"]
    assert "The posting was cut" in casos["candidatura_longa"]
    corte = limites()["tarefas"]["perguntas"]["corte"]["caracteres"]
    assert len(casos["perguntas"]) < corte < len(casos["perguntas_longo"])


def test_dados_sinteticos_sem_contato_de_pessoa() -> None:
    perfis = (provar.PERFIL, provar.PERFIL_LONGO)
    textos = [*provar.CURRICULO, *provar.VAGA, *(json.dumps(p, ensure_ascii=False) for p in perfis)]
    assert [t for t in textos if limpar_contato(t) != t] == []
    assert all({"nome", "email", "telefone", "cidade_moradia"}.isdisjoint(p) for p in perfis)


def test_provar_mede_tempo_tokens_e_valida_no_esquema() -> None:
    casos = _casos()
    timings: list[dict[str, Any] | None] = []
    backend = _Gravado(_validas(casos), timings)
    medidas = provar.provar(backend, casos, timings, relogio=_relogio(10))
    assert [m.caso for m in medidas] == NOMES
    assert [(m.segundos, m.leitura_n, m.geracao_n) for m in medidas] == [(10, 3000, 400)] * 6
    assert all(m.valida and m.cabe and m.no_prazo and m.passou for m in medidas)
    # o que veio preenchido (o esquema aceita a resposta vazia: o número diz se leu algo)
    curriculo, perguntas, candidatura = (
        ("cargo_atual", "habilidades"),
        ("perguntas",),
        (
            "idioma",
            "carta",
            "resumo",
            "usou",
        ),
    )
    assert [m.campos for m in medidas] == [curriculo] * 2 + [perguntas] * 2 + [candidatura] * 2


def test_resposta_fora_do_esquema_nao_passa() -> None:
    casos = _casos()
    timings: list[dict[str, Any] | None] = []
    prontas = _validas(casos)
    prontas[2] = {"perguntas": "Já usou Kubernetes?"}  # tipo errado
    medidas = provar.provar(_Gravado(prontas, timings), casos, timings, relogio=_relogio(10))
    assert [m.motivo for m in medidas] == [None, None, "formato", None, None, None]
    assert [m.passou for m in medidas] == [True, True, False, True, True, True]


def test_passar_do_prazo_nao_passa() -> None:
    casos = _casos()[:1]
    prazo = limites()["prazo_s"]["local"]
    for passo, passou in ((prazo, True), (prazo + 1, False)):
        timings: list[dict[str, Any] | None] = []
        backend = _Gravado(_validas(casos), timings)
        [medida] = provar.provar(backend, casos, timings, relogio=_relogio(passo))
        assert (medida.valida, medida.no_prazo, medida.passou) == (True, passou, passou)


def _lidos(n: int) -> Callable[[Pedido], dict[str, Any] | None]:
    return lambda _: {"prompt_n": n}


def test_passar_do_contexto_nao_passa() -> None:
    casos = _casos()[:1]
    teto = CONTEXTO - casos[0].pedido.max_tokens
    for lidos, cabe in ((teto, True), (teto + 1, False)):
        timings: list[dict[str, Any] | None] = []
        backend = _Gravado(_validas(casos), timings, _lidos(lidos))
        [medida] = provar.provar(backend, casos, timings, relogio=_relogio(1))
        assert (medida.valida, medida.cabe, medida.passou) == (True, cabe, cabe)


def test_sem_timings_nao_inventa_numero_e_nao_passa() -> None:
    casos = _casos()[:1]
    timings: list[dict[str, Any] | None] = [dict(TIMINGS)]  # sobra de antes: não conta
    backend = _Gravado(_validas(casos), timings, lambda _: None)
    [medida] = provar.provar(backend, casos, timings, relogio=_relogio(1))
    assert (medida.leitura_n, medida.geracao_n, medida.cabe, medida.passou) == (
        None,
        None,
        False,
        False,
    )


def test_falha_de_um_caso_e_anotada_e_os_outros_seguem() -> None:
    casos = _casos()
    timings: list[dict[str, Any] | None] = [dict(TIMINGS)]
    prontas = _validas(casos)
    prontas[0] = Falha("tempo_esgotado")
    medidas = provar.provar(_Gravado(prontas, timings), casos, timings, relogio=_relogio(1))
    assert [m.motivo for m in medidas] == ["tempo_esgotado", None, None, None, None, None]
    assert medidas[0].campos == ()
    assert (medidas[0].leitura_n, medidas[0].passou) == (None, False)
    assert all(m.passou for m in medidas[1:])


def test_espera_maior_so_para_medir_e_o_prazo_do_produto_julga() -> None:
    casos = _casos()[:2]
    timings: list[dict[str, Any] | None] = []
    backend = _Gravado(_validas(casos), timings)
    medidas = provar.provar(backend, casos, timings, relogio=_relogio(400), espera_s=900)
    assert [p.prazo_s for p in backend.pedidos] == [900, 900]
    assert [m.prazo_s for m in medidas] == [limites()["prazo_s"]["local"]] * 2
    assert [m.passou for m in medidas] == [False, False]


def _montar(backend: BackendFalso, timings: list[Any], fechou: list[bool]) -> Any:
    def montar(env: Mapping[str, str]) -> Any:
        return backend, "laya", lambda: fechou.append(True), timings

    return montar


def test_main_escreve_o_resumo_e_sai_com_zero_quando_tudo_passa(tmp_path: Path) -> None:
    resumo = tmp_path / "resumo.md"
    timings: list[Any] = []
    fechou: list[bool] = []
    backend = _Gravado(_validas(_casos()), timings)
    env = {"GITHUB_STEP_SUMMARY": str(resumo)}
    codigo = provar.main(["--rotulo", "ubuntu"], env=env, montar=_montar(backend, timings, fechou))
    assert (codigo, fechou) == (0, [True])
    texto = resumo.read_text(encoding="utf-8")
    for nome in NOMES:
        assert f"| ubuntu | {nome} |" in texto
    assert "| 3000 | 400 |" in texto
    assert "| 3000 | 400 | 1536 | sim | 2 | valida | passou |" in texto


def test_main_sai_com_um_quando_um_caso_nao_passa(tmp_path: Path) -> None:
    timings: list[Any] = []
    fechou: list[bool] = []
    prontas = _validas(_casos())
    prontas[-1] = {"idioma": "fr", "carta": "x", "resumo": "y"}
    backend = _Gravado(prontas, timings)
    assert provar.main([], env={}, montar=_montar(backend, timings, fechou)) == 1
    assert fechou == [True]


def test_main_sai_com_dois_sem_o_modelo() -> None:
    def montar(env: Mapping[str, str]) -> Any:
        raise Falha("modelo_ausente")

    assert provar.main([], env={}, montar=montar) == 2


@pytest.mark.parametrize("motivo", ["programa_ausente", "servico_fora"])
def test_main_sai_com_dois_sem_subir_o_servidor(motivo: str) -> None:
    def montar(env: Mapping[str, str]) -> Any:
        raise Falha(cast(Motivo, motivo))

    assert provar.main([], env={}, montar=montar) == 2
