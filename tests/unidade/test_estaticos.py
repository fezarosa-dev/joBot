"""Guarda dos arquivos de terceiros em `painel/static/`: o sha256 de cada `.meta.json` confere."""

import hashlib
import json
import shutil
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "jobot" / "painel" / "static"


def divergencias(pasta: Path) -> list[str]:
    """Arquivo descrito em `*.meta.json` que falta ou tem sha256 diferente do declarado."""
    metas = sorted(pasta.rglob("*.meta.json"))
    if not metas:
        return [f"{pasta}: nenhum .meta.json"]
    achados: list[str] = []
    for meta in metas:
        arquivos: dict[str, str | dict[str, str]] = json.loads(meta.read_text(encoding="utf-8"))[
            "arquivos"
        ]
        for nome, dados in arquivos.items():
            alvo = meta.parent / nome
            if not alvo.is_file():
                achados.append(f"{alvo.relative_to(pasta)}: falta")
            elif hashlib.sha256(alvo.read_bytes()).hexdigest() != (
                dados if isinstance(dados, str) else dados["sha256"]
            ):
                achados.append(f"{alvo.relative_to(pasta)}: sha256 diferente")
    return achados


def test_meta_json_confere_sha256() -> None:
    assert divergencias(STATIC) == []


def test_meta_json_hash_errado_e_detectado(tmp_path: Path) -> None:
    copia = tmp_path / "static"
    shutil.copytree(STATIC, copia)
    assert divergencias(copia) == []  # controle: a cópia fiel passa
    meta = copia / "vendor" / "htmx.meta.json"
    dados = json.loads(meta.read_text(encoding="utf-8"))
    dados["arquivos"]["htmx.min.js"]["sha256"] = "0" * 64
    meta.write_text(json.dumps(dados), encoding="utf-8")
    assert divergencias(copia) == ["vendor/htmx.min.js: sha256 diferente"]
    (copia / "fontes" / "OFL.txt").unlink()
    assert "fontes/OFL.txt: falta" in divergencias(copia)


def _bloco_forced_colors(css: str) -> str:
    """O texto do `@media (forced-colors: active) { ... }` (chaves contadas), ou vazio."""
    inicio = css.find("@media (forced-colors: active)")
    if inicio == -1:
        return ""
    abre = css.index("{", inicio)
    fundo = 0
    for i in range(abre, len(css)):
        fundo += {"{": 1, "}": -1}.get(css[i], 0)
        if fundo == 0:
            return css[abre : i + 1]
    return ""


def test_interruptor_tem_bloco_de_cores_forcadas() -> None:
    """Sem cores próprias (modo de alto contraste) o trilho e a bolinha precisam de borda e de
    cores do sistema, senão ligado e desligado ficam iguais."""
    css = (STATIC / "css" / "base.css").read_text(encoding="utf-8")
    bloco = _bloco_forced_colors(css)
    assert ".chave" in bloco
    for pedaco in ("ButtonText", "Highlight", "HighlightText", "GrayText", "forced-color-adjust"):
        assert pedaco in bloco, pedaco
    # o botão olho apertado (campo de senha do 2Captcha) segue no CSS de Configurações
    config = (STATIC / "css" / "configuracoes.css").read_text(encoding="utf-8")
    assert "[data-olho]" in _bloco_forced_colors(config)


def test_detector_do_bloco_forced_colors_acha_so_o_certo() -> None:
    assert _bloco_forced_colors("a { b: c }") == ""  # controle: sem bloco
    achado = _bloco_forced_colors("@media (forced-colors: active) { .x { a: b } } .y { c: d }")
    assert ".x" in achado
    assert ".y" not in achado


ICONES_DIR = STATIC / "icones"
ICONES = (
    # mapa do desenho 5.3
    "sparkles", "inbox", "circle-dot", "hourglass",
    "bookmark", "send", "graduation-cap", "eye-off",
    "search", "building-2", "lightbulb", "rss", "globe",
    "settings", "panel-left", "command",
    "undo-2", "redo-2", "x", "ellipsis", "triangle-alert", "link",
    # estados da 5.9
    "circle-dashed", "book-open", "circle-check", "circle-x", "clock",
    # grupos de Configurações, estado vazio e página Saiu
    "sliders-horizontal", "toggle-right", "timer", "shield", "plug", "key-round",
    "search-x", "log-out",
    # encaixe da linha, do cartão e do detalhe (T301)
    "circle", "contrast",
)  # fmt: skip


def _meta_icones() -> dict[str, str]:
    """`arquivos` do lucide.meta.json; sem o meta, falha por asserção (não FileNotFoundError)."""
    meta = ICONES_DIR / "lucide.meta.json"
    assert meta.exists(), "falta icones/lucide.meta.json"
    return dict(json.loads(meta.read_text(encoding="utf-8"))["arquivos"])


def test_icones_batem_com_o_meta() -> None:
    declarados = _meta_icones()
    em_disco = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ICONES_DIR.glob("*.svg")
    }
    assert em_disco == declarados


def test_icones_tem_licenca() -> None:
    licenca = ICONES_DIR / "LICENSE"
    assert licenca.exists(), "falta icones/LICENSE"
    assert "Lucide" in licenca.read_text(encoding="utf-8")


def test_icones_do_mapa_existem() -> None:
    assert len(ICONES) == 37
    faltam = [n for n in ICONES if not (ICONES_DIR / f"{n}.svg").is_file()]
    assert faltam == []


def test_icones_sem_recurso_externo() -> None:
    arquivos = sorted(ICONES_DIR.glob("*.svg"))
    assert arquivos, "nenhum SVG em icones/"
    ruins = [p.name for p in arquivos if "href" in (t := p.read_text("utf-8")) or "url(" in t]
    assert ruins == []
