"""Manifesto do modelo local, `nucleo/dados/ia_local.json` (T407, desenho 7, D193).

Conferido em 2026-11-17 nas fontes oficiais:
- `llama-server` b12359: `digest` de cada anexo em
  https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b12359 e a atestação SLSA de cada
  digest em https://api.github.com/repos/ggml-org/llama.cpp/attestations/sha256:<digest>
  (workflow `.github/workflows/release-publish.yml` do `ggml-org/llama.cpp`); licença MIT pela
  https://api.github.com/repos/ggml-org/llama.cpp/license.
- Qwen3.5 2B e 4B Q4_K_M da Unsloth: commit e licença em
  https://huggingface.co/api/models/unsloth/Qwen3.5-<n>B-GGUF, oid LFS e tamanho em
  `.../tree/<commit>` e o `X-Linked-ETag` do `resolve/<commit>/...`.
- Laya 2B Q4_K_M (D219): a pre-release `modelo-laya-2b-1` do próprio joBot, com o sha256 e o
  tamanho do GGUF do treino, conferidos depois do download.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, get_args

from jobot.sistema.memoria import Modelo

MANIFESTO = Path(__file__).parents[2] / "src" / "jobot" / "nucleo" / "dados" / "ia_local.json"
ALVOS = {"ubuntu-x64", "win-cpu-x64", "macos-arm64", "macos-x64"}
GITHUB = re.compile(
    r"https://github\.com/ggml-org/llama\.cpp/releases/download/(b\d+)/(llama-\1-bin-[\w.-]+)"
)
HUGGING_FACE = re.compile(r"https://huggingface\.co/unsloth/[\w.-]+/resolve/[0-9a-f]{40}/([\w.-]+)")
# a pre-release do modelo, com tag própria e fixa (nunca `latest` nem `vX.Y.Z`, D219)
JOBOT = re.compile(
    r"https://github\.com/fezarosa-dev/joBot/releases/download/modelo-[\w.-]+-\d+/([\w.-]+)"
)
LAYA = {
    "arquivo": "Laya-2B-Q4_K_M.gguf",
    "tamanho": 1_285_207_680,
    "sha256": "606e488c0ecfc4ef0196b6ca5b8cf3294a886845c99be0b841fed6f9a080075a",
}


def _manifesto() -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    return dados


def _arquivos(manifesto: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield from manifesto["llama_server"]["alvos"].values()
    yield from manifesto["modelos"].values()


def test_tem_os_quatro_alvos_e_os_modelos() -> None:
    manifesto = _manifesto()
    assert set(manifesto["llama_server"]["alvos"]) == ALVOS
    assert set(manifesto["modelos"]) == set(get_args(Modelo))
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", manifesto["conferido_em"])


def test_laya_e_o_padrao_e_os_qwen_seguem_como_opcao() -> None:
    manifesto = _manifesto()
    assert manifesto.get("padrao") == "laya"
    laya = manifesto["modelos"]["laya"]
    assert {c: laya[c] for c in LAYA} == LAYA
    assert JOBOT.fullmatch(laya["url"]), laya["url"]
    assert laya["licenca"] == "Apache-2.0" and "Qwen/Qwen3.5-2B" in laya["origem"]
    assert {"2b", "4b"} < set(manifesto["modelos"])  # controle: os Qwen continuam


def test_toda_url_tem_versao_fixa() -> None:
    manifesto = _manifesto()
    build = manifesto["llama_server"]["build"]
    for alvo in manifesto["llama_server"]["alvos"].values():
        casou = GITHUB.fullmatch(alvo["url"])
        assert casou, alvo["url"]
        assert casou.groups() == (build, alvo["arquivo"])
    for modelo in manifesto["modelos"].values():
        casou = HUGGING_FACE.fullmatch(modelo["url"]) or JOBOT.fullmatch(modelo["url"])
        assert casou, modelo["url"]
        assert casou.group(1) == modelo["arquivo"]
    for arquivo in _arquivos(manifesto):
        assert "latest" not in arquivo["url"]
        assert "/main/" not in arquivo["url"]


def test_todo_arquivo_tem_sha256_tamanho_licenca_e_origem() -> None:
    arquivos = list(_arquivos(_manifesto()))
    assert len(arquivos) == len(ALVOS) + len(get_args(Modelo))
    for arquivo in arquivos:
        assert re.fullmatch(r"[0-9a-f]{64}", arquivo["sha256"]), arquivo["arquivo"]
        tamanho = arquivo["tamanho"]
        assert type(tamanho) is int and tamanho > 0, arquivo["arquivo"]
        for campo in ("licenca", "origem"):
            texto = arquivo.get(campo)
            assert isinstance(texto, str) and texto.strip(), (campo, arquivo)
