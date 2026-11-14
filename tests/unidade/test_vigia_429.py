"""Um 429 que escapa do coletar não abre issue no vigia (T123, A36)."""

import importlib.util
import sys
from pathlib import Path

from jobot.nucleo.coletores.executor import motivo_do_escopo
from jobot.nucleo.http import Parou429

_spec = importlib.util.spec_from_file_location(
    "vigia_script_429", Path(__file__).resolve().parents[2] / "scripts/vigia.py"
)
assert _spec is not None and _spec.loader is not None
vigia = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = vigia  # o dataclass procura o módulo pelo nome
_spec.loader.exec_module(vigia)


def test_parou429_que_escapa_do_coletar_nao_abre_issue() -> None:
    # A36: o motivo agora é saude.parou_429 (antes saude.excecao:Parou429, que abria issue).
    motivo = motivo_do_escopo(Parou429("429"))
    assert motivo == "saude.parou_429"
    assert vigia.quebrou(vigia.Resultado(fonte="falsa", estado="falhou", motivo=motivo)) is False
