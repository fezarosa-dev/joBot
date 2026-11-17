; Ganchos do instalador NSIS da casca (desenho 7.2, T337).
;
; Desinstalar: a casca desliga o segundo plano, para o servidor e apaga a pasta dela (bin/,
; python/, venvs/, manifestos) e o instalacao.json; nunca a pasta de dados nem o Chromium.
; Quem faz é o Rust (`--desinstalar`, desktop/src/fechar.rs); aqui só a chamada.
;
; Na troca de versão nada disso roda (D182). Pelo updater do Tauri, o desinstalador velho vem
; com /UPDATE. Pela tela normal (o .exe novo, com "Desinstalar antes de instalar"), o
; instalador novo roda o desinstalador velho no lugar (`_?=`), de dentro de $INSTDIR; a
; desinstalação de verdade (Painel de Controle, winget) se copia antes para o temporário.
;
; Limite (D182): este gancho roda antes do aviso "feche o app" do Tauri; com a janela aberta,
; quem cancela nesse aviso fica com a casca sem venv (reinstalar resolve).

!macro NSIS_HOOK_PREUNINSTALL
  ${If} $UpdateMode <> 1
  ${AndIf} $EXEDIR != $INSTDIR
    ExecWait '"$INSTDIR\${MAINBINARYNAME}.exe" --desinstalar'
  ${EndIf}
!macroend
