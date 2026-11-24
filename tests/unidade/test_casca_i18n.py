"""Textos e arquivos da tela de instalação da casca (T336; desenho 5.2).

Os catálogos `desktop/ui/i18n/{pt,en}.json` têm as mesmas chaves, e `desktop/ui/` não guarda
cópia do CSS, das fontes nem do ícone do painel: o `build.rs` copia tudo para `ui/painel/`, que
o git ignora.
"""

import hashlib
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
UI = RAIZ / "desktop" / "ui"
ESTATICOS = RAIZ / "src" / "jobot" / "painel" / "static"


def _ler(caminho: Path) -> str:
    assert caminho.exists(), caminho
    return caminho.read_text(encoding="utf-8")


def _catalogo(idioma: str) -> dict[str, str]:
    caminho = UI / "i18n" / f"{idioma}.json"
    assert caminho.exists(), caminho
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    assert isinstance(conteudo, dict)
    return conteudo


def test_mesmas_chaves_em_pt_e_en() -> None:
    pt, en = _catalogo("pt"), _catalogo("en")
    assert pt.keys() == en.keys()
    assert all(isinstance(v, str) and v.strip() for v in [*pt.values(), *en.values()])


def test_parametros_iguais_nas_duas_linguas() -> None:
    pt, en = _catalogo("pt"), _catalogo("en")
    for chave, texto in pt.items():
        assert set(re.findall(r"\{\w+\}", texto)) == set(re.findall(r"\{\w+\}", en[chave])), chave


def test_toda_chave_usada_pela_tela_existe() -> None:
    html = _ler(UI / "index.html")
    js = _ler(UI / "instalador.js")
    usadas = set(re.findall(r'data-t(?:-rotulo)?="([^"]+)"', html))
    etapas = ("conferir", "python", "jobot", "navegador", "ia_local", "abrir")
    usadas |= {f"etapa.{e}" for e in etapas}
    motivos = ("arquivo", "espaco", "prova", "navegador", "outro")
    usadas |= {f"falha.{m}{s}" for m in motivos for s in ("", "_oque")}
    # os motivos do `jobot ferramentas baixar ia-local` que a página Pronto diz (T418)
    do_modelo = (
        "sem_rede",
        "espaco",
        "arquivo",
        "ocupado",
        "programa_ausente",
        "modelo_ausente",
        "outro",
    )
    usadas |= {f"ia_local.motivo.{m}" for m in do_modelo}
    usadas |= set(re.findall(r't\("([\w.]+)"', js))
    assert "ferramentas.tamanho" in js
    usadas.add("ferramentas.tamanho")
    assert usadas <= _catalogo("pt").keys()


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_ui_sem_copia_versionada_do_painel() -> None:
    assert "desktop/ui/painel/" in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    do_painel = {_sha(p) for p in ESTATICOS.rglob("*") if p.is_file()}
    do_painel.add(_sha(RAIZ / "desktop" / "icons" / "icon.png"))
    proprios = [p for p in UI.rglob("*") if p.is_file() and (UI / "painel") not in p.parents]
    assert proprios, "desktop/ui vazia"
    assert [p for p in proprios if _sha(p) in do_painel] == []


def test_o_que_a_tela_pede_de_painel_o_build_copia() -> None:
    html = _ler(UI / "index.html")
    pedidos = set(re.findall(r'(?:href|src)="painel/([^"]+)"', html))
    assert pedidos
    build = (RAIZ / "desktop" / "build.rs").read_text(encoding="utf-8")
    copiados = set(re.findall(r'"([^"]+)",?\s*\)', build))
    assert pedidos <= copiados, pedidos - copiados


def test_toda_chave_usada_pelo_controle_existe() -> None:
    # o controle da casca (T350; D206): os textos também vêm de desktop/ui/i18n
    html = _ler(UI / "controle.html")
    js = _ler(UI / "controle.js")
    usadas = set(re.findall(r'data-t(?:-rotulo)?="([^"]+)"', html))
    usadas |= set(re.findall(r't\("([\w.]+)"', js))
    motivos = set(re.findall(r'"(\w+)"', js.split("const MOTIVOS = [", 1)[1].split("]", 1)[0]))
    esperados = {"instalar", "porta", "captura", "sem_resposta", "saiu", "subir", "abrir", "parar"}
    assert esperados <= motivos
    usadas |= {f"controle.falha.{m}" for m in motivos}
    assert "t(`controle.${nome}`)" in js
    usadas |= {f"controle.{e}" for e in ("ligado", "parado", "ligando", "parando")}
    assert {"controle.ligado", "controle.parado", "controle.ligar", "controle.abrir"} <= usadas
    assert usadas <= _catalogo("pt").keys(), usadas - _catalogo("pt").keys()
