"""Sistema falso do segundo plano: nenhum teste de tela chama systemctl nem distrobox de verdade.

`FalsoSistema` é o executor de comandos (`Rodar`) injetado no painel. Ele só anota o que foi
pedido e responde como um systemd e um distrobox-host-exec saudáveis,
salvo o que o teste muda. O estado de habilitado acompanha `enable` e `disable`.
"""

from collections.abc import Sequence
from pathlib import Path

from jobot.sistema.segundo_plano_linux import Resultado


class FalsoSistema:
    def __init__(self, home: str = "") -> None:
        self.home = home  # o $HOME que o host responde (só dentro da distrobox)
        self.tem_enter = True  # `command -v distrobox-enter` acha o programa
        self.habilitado = True  # o serviço está habilitado: enable liga, disable desliga
        self.systemd_ok = True  # `systemctl --user show-environment` responde
        self.falha_em: dict[str, Resultado] = {}  # primeiro argumento do systemctl -> resposta
        self.chamadas: list[tuple[str, ...]] = []

    def __call__(self, comando: Sequence[str]) -> Resultado:
        self.chamadas.append(tuple(comando))
        resto = list(comando)
        if resto[0] == "distrobox-host-exec":
            resto = resto[1:]
        if resto[:2] == ["sh", "-c"]:
            if "command -v" in resto[2]:
                return (
                    Resultado(0, "/usr/bin/distrobox-enter\n") if self.tem_enter else Resultado(1)
                )
            return Resultado(0, self.home)  # printf %s "$HOME"
        assert resto[:2] == ["systemctl", "--user"], f"comando inesperado: {comando!r}"
        acao = resto[2]
        if acao == "show-environment":
            return Resultado(0 if self.systemd_ok else 1)
        if acao in self.falha_em:
            return self.falha_em[acao]
        if acao == "enable":
            self.habilitado = True
        elif acao == "disable":
            self.habilitado = False
        elif acao == "is-enabled":
            return Resultado(0 if self.habilitado else 1)
        return Resultado(0)

    def systemctl(self) -> list[tuple[str, ...]]:
        """Os argumentos de cada `systemctl --user` pedido, sem o prefixo do host."""
        achados = []
        for comando in self.chamadas:
            resto = comando[1:] if comando[0] == "distrobox-host-exec" else comando
            if resto[:2] == ("systemctl", "--user"):
                achados.append(resto[2:])
        return achados


class FalsoAgendador:
    """Agendador de Tarefas falso (Windows): `schtasks` cria, apaga e consulta a tarefa."""

    def __init__(self, existe: bool = False) -> None:
        self.existe = existe  # a tarefa joBot está registrada
        self.falha_em: dict[str, Resultado] = {}  # "/Create", "/Delete" ou "/Query" -> resposta
        self.chamadas: list[tuple[str, ...]] = []
        self.xml = ""  # o XML do /Create, lido do arquivo na hora da chamada

    def __call__(self, comando: Sequence[str]) -> Resultado:
        self.chamadas.append(tuple(comando))
        if "/XML" in comando:
            self.xml = Path(comando[comando.index("/XML") + 1]).read_text(encoding="utf-16")
        assert comando[0] == "schtasks", f"comando inesperado: {comando!r}"
        acao = comando[1]
        if acao in self.falha_em:
            return self.falha_em[acao]
        if acao == "/Create":
            self.existe = True
        elif acao in ("/Delete", "/Query"):
            if not self.existe:
                return Resultado(1, erro="ERRO: o sistema não encontrou a tarefa.")
            self.existe = acao == "/Query"
        return Resultado(0)


class FalsoLaunchctl:
    """launchd falso (Mac): `launchctl` carrega, descarrega e mostra o LaunchAgent do joBot."""

    def __init__(self, carregado: bool = False, rodando: bool = True) -> None:
        self.carregado = carregado  # o LaunchAgent está no domínio gui/<uid>
        self.rodando = rodando  # o `print` diz `state = running` (senão `not running`)
        self.falha_em: dict[str, Resultado] = {}  # "bootstrap", "bootout" ou "print" -> resposta
        self.chamadas: list[tuple[str, ...]] = []
        self.plist = b""  # o plist do bootstrap, lido do arquivo na hora da chamada

    def __call__(self, comando: Sequence[str]) -> Resultado:
        self.chamadas.append(tuple(comando))
        assert comando[0] == "launchctl", f"comando inesperado: {comando!r}"
        acao = comando[1]
        if acao in self.falha_em:
            return self.falha_em[acao]
        if acao == "bootstrap":
            self.plist = Path(comando[3]).read_bytes()
            self.carregado = True
            return Resultado(0)
        if not self.carregado:
            return Resultado(113, erro="Could not find service in domain for user gui")
        if acao == "bootout":
            self.carregado = False
            return Resultado(0)
        estado = "running" if self.rodando else "not running"
        return Resultado(0, f"gui/501/io.github.fezarosa-dev.jobot = {{\n\tstate = {estado}\n}}\n")
