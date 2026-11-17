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

; WebView2 (D183.20): o instalador não baixa nada (`webviewInstallMode: skip`, D174.1). Sem o
; WebView2 Runtime (Evergreen; as mesmas chaves que o instalador do Tauri lê, por máquina e por
; usuário), mostra o link oficial da Microsoft e cancela antes de copiar qualquer arquivo (a
; pasta de instalação, vazia, pode ficar: o Tauri a cria antes do gancho). No /S não há caixa
; (o /SD IDOK é a resposta padrão): só cancela. O texto segue o idioma do instalador (1046 =
; português do Brasil).
!define JOBOT_WEBVIEW2 "Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
!define JOBOT_WEBVIEW2_URL "https://developer.microsoft.com/microsoft-edge/webview2/"

!macro NSIS_HOOK_PREINSTALL
  ReadRegStr $R9 HKLM "SOFTWARE\WOW6432Node\${JOBOT_WEBVIEW2}" "pv"
  ${If} $R9 == ""
  ${OrIf} $R9 == "0.0.0.0"
    ReadRegStr $R9 HKLM "SOFTWARE\${JOBOT_WEBVIEW2}" "pv"
  ${EndIf}
  ${If} $R9 == ""
  ${OrIf} $R9 == "0.0.0.0"
    ReadRegStr $R9 HKCU "SOFTWARE\${JOBOT_WEBVIEW2}" "pv"
  ${EndIf}
  ${If} $R9 == ""
  ${OrIf} $R9 == "0.0.0.0"
    ${If} $LANGUAGE == 1046
      StrCpy $R8 "O joBot precisa do Microsoft Edge WebView2 Runtime, que não está instalado neste computador. Instale-o pela página oficial da Microsoft e rode este instalador de novo: ${JOBOT_WEBVIEW2_URL}"
    ${Else}
      StrCpy $R8 "joBot needs the Microsoft Edge WebView2 Runtime, which is not installed on this computer. Install it from Microsoft's official page and run this installer again: ${JOBOT_WEBVIEW2_URL}"
    ${EndIf}
    MessageBox MB_ICONSTOP|MB_OK "$R8" /SD IDOK
    Abort "$R8"
  ${EndIf}
!macroend
