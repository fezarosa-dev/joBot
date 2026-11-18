// A casca do joBot (desenho 5.1 a 5.4): instância única, confere a janela, acha ou sobe o
// `jobot serve` e abre o painel em http://127.0.0.1:<porta>/; sem o joBot instalado, a tela de
// instalação (5.2). Com --verificar-janela <url>, a prova da ponte da T321 (a IPC do Tauri numa
// origem http://127.0.0.1 remota). Com --verificar e --verificar-navegador, a fumaça sem janela
// da release (desenho 10).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(target_os = "linux")]
mod extraido;
mod fechar;
mod instalar;
mod servidor;

use serde_json::{Value, json};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use tauri::ipc::Channel;
use tauri::webview::PageLoadEvent;
use tauri::{
    AppHandle, Manager, RunEvent, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder, WindowEvent,
};

/// O sha256 do `manifesto.json` dos recursos, gravado no build (desenho 6.2; D174.7). Sem ele
/// (build local sem recursos), a tela diz que o instalador está incompleto.
const SHA_MANIFESTO: Option<&str> = option_env!("JOBOT_MANIFESTO_SHA256");
const VERSAO: &str = env!("CARGO_PKG_VERSION");

/// Se esta abertura da casca subiu o servidor (desenho 5.5): só esse ela pode parar.
static SUBIU: AtomicBool = AtomicBool::new(false);

/// Tempo que a tela "o joBot abriu no navegador" fica antes de a janela fechar (desenho 5.4).
const AVISO_DA_JANELA: Duration = Duration::from_secs(10);

/// Caminho para onde o script da prova navega com o resultado. A navegação de
/// topo não passa pela CSP da página, então o aviso chega mesmo com a IPC barrada.
const CAMINHO_RESULTADO: &str = "/__jobot_resultado";
const PRAZO: Duration = Duration::from_secs(60);

const SCRIPT: &str = r#"
(() => {
  const violacoes = [];
  document.addEventListener("securitypolicyviolation", (e) => {
    violacoes.push(e.violatedDirective + " " + e.blockedURI);
  });
  const avisar = (chave, valor) => {
    const u = new URL("/__jobot_resultado", location.href);
    u.searchParams.set(chave, String(valor));
    if (violacoes.length) u.searchParams.set("csp", violacoes.join(" | "));
    location.href = u.href;
  };
  try {
    window.__TAURI__.core
      .invoke("plugin:window|is_maximized")
      .then((r) => avisar("ok", r), (e) => avisar("erro", e));
  } catch (e) {
    avisar("erro", e);
  }
})();
"#;

/// Código de saída pelo endereço que o script abriu: 0 se a IPC respondeu, 2 se foi barrada.
fn resultado(url: &Url) -> Option<i32> {
    if url.path() != CAMINHO_RESULTADO {
        return None;
    }
    let tem = |chave: &str| url.query_pairs().any(|(k, _)| k == chave);
    Some(if tem("ok") { 0 } else { 2 })
}

fn ambiente(nome: &str) -> Option<String> {
    std::env::var(nome).ok()
}

fn dados() -> PathBuf {
    servidor::pasta_de_dados(ambiente, std::env::consts::OS)
}

/// User agent da janela com a marca ` joBot-casca/<versão> (<so>)` que o painel lê
/// (`marca_da_casca`, desenho 5.3). A base é fixa por sistema (D179).
fn agente(so: &str) -> String {
    let (base, marca) = match so {
        "windows" => ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "windows"),
        "macos" => ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "macos"),
        _ => ("Mozilla/5.0 (X11; Linux x86_64)", "linux"),
    };
    let versao = env!("CARGO_PKG_VERSION");
    format!("{base} AppleWebKit/605.1.15 (KHTML, like Gecko) joBot-casca/{versao} ({marca})")
}

/// O que as páginas locais (`ui/`) pedem à casca, navegando para `/__jobot/...` da própria
/// origem do app. Vale só se a página que pede também é local (`tratar`): o painel não pede.
#[derive(Debug, PartialEq)]
enum Aviso {
    Janela { ok: bool },
    Tentar,
    Fechar,
}

/// A origem do app: `tauri://localhost` (Linux e Mac) ou `http(s)://tauri.localhost` (Windows).
fn e_local(url: &Url) -> bool {
    let host = url.host_str();
    url.port().is_none()
        && match url.scheme() {
            "tauri" => host == Some("localhost"),
            "http" | "https" => host == Some("tauri.localhost"),
            _ => false,
        }
}

fn aviso_local(url: &Url) -> Option<Aviso> {
    if !e_local(url) {
        return None;
    }
    match url.path() {
        "/__jobot/janela" => Some(Aviso::Janela {
            ok: url.query_pairs().any(|(k, _)| k == "ok"),
        }),
        "/__jobot/tentar" => Some(Aviso::Tentar),
        "/__jobot/fechar" => Some(Aviso::Fechar),
        _ => None,
    }
}

/// `ui/erro.html` com o motivo, o detalhe e o fim do log, na origem local de `base`.
fn pagina_de_erro(base: &Url, motivo: &str, detalhe: &str, log: &str) -> Url {
    let mut url = base.join("/erro.html").expect("caminho fixo");
    url.query_pairs_mut()
        .append_pair("motivo", motivo)
        .append_pair("detalhe", detalhe)
        .append_pair("log", log);
    url
}

fn ir(janela: &WebviewWindow, url: Url) {
    if let Err(erro) = janela.navigate(url) {
        eprintln!("jobot-app: não consegui navegar: {erro}");
    }
}

/// Para onde a janela vai depois da conferência: o painel, a tela de instalação (sem o joBot
/// instalado) ou a tela de erro com o fim do log.
fn destino_do_arranque(base: &Url, resultado: Result<u16, servidor::Falha>, dados: &Path) -> Url {
    match resultado {
        Ok(porta) => servidor::url_do_painel(porta).parse().expect("URL fixa"),
        Err(servidor::Falha::SemInstalacao) => base.join("/index.html").expect("caminho fixo"),
        Err(falha) => pagina_de_erro(
            base,
            falha.codigo(),
            &falha.detalhe(),
            &servidor::fim_do_log(dados),
        ),
    }
}

/// Janela conferida: acha ou sobe o servidor e navega ao painel (roda fora da linha da janela).
fn abrir_painel(janela: WebviewWindow, base: Url) {
    let dados = dados();
    let resultado = servidor::jobot_instalado(&dados, std::env::consts::OS)
        .ok_or(servidor::Falha::SemInstalacao)
        .and_then(|jobot| servidor::achar_ou_subir(&dados, &jobot, ambiente))
        .map(|achado| {
            if achado.subiu {
                SUBIU.store(true, Ordering::Relaxed);
            }
            achado.porta
        });
    ir(&janela, destino_do_arranque(&base, resultado, &dados));
}

/// A instalação em curso (desenho 5.2): fechar a janela no meio pede confirmação na página, e
/// o `cancelado` para o `uv` e desfaz o que a instalação criou.
#[derive(Default)]
struct Instalacao {
    em_curso: AtomicBool,
    cancelado: AtomicBool,
}

fn recursos(app: &AppHandle) -> PathBuf {
    app.path()
        .resource_dir()
        .unwrap_or_default()
        .join("recursos")
}

/// Para a tela de instalação: recursos completos, tamanhos e a pasta de dados.
#[tauri::command]
fn estado_instalador(app: AppHandle) -> Value {
    let mut estado = instalar::estado(&recursos(&app), SHA_MANIFESTO, VERSAO);
    estado["dados"] = dados().to_string_lossy().into_owned().into();
    estado
}

/// Instala numa linha à parte; o progresso vai pelo canal e termina em `{"fim": ...}`.
#[tauri::command]
fn instalar(app: AppHandle, navegador: bool, progresso: Channel<Value>) -> Result<(), String> {
    let estado = app.state::<Arc<Instalacao>>().inner().clone();
    if estado.em_curso.swap(true, Ordering::SeqCst) {
        return Err("a instalação já está em curso".into());
    }
    estado.cancelado.store(false, Ordering::SeqCst);
    std::thread::spawn(move || {
        let (recursos, dados) = (recursos(&app), dados());
        let pasta = instalar::pasta_da_casca(ambiente, std::env::consts::OS);
        let instalador = instalar::Instalador {
            recursos: &recursos,
            pasta: &pasta,
            dados: &dados,
            so: std::env::consts::OS,
            versao: VERSAO,
        };
        let mut rodar = |comando: std::process::Command, linha: &mut dyn FnMut(&str)| {
            instalar::rodar(comando, &estado.cancelado, linha)
        };
        let resultado = instalador.instalar(
            SHA_MANIFESTO.unwrap_or_default(),
            navegador,
            &estado.cancelado,
            &mut rodar,
            &mut |aviso| {
                let _ = progresso.send(aviso);
            },
        );
        estado.em_curso.store(false, Ordering::SeqCst);
        let Some(janela) = app.get_webview_window("main") else {
            return;
        };
        // a pessoa pediu para fechar: fecha, mesmo que o cancelamento tenha chegado depois da
        // última conferência e a instalação tenha terminado
        if estado.cancelado.load(Ordering::SeqCst) {
            let _ = janela.close();
            return;
        }
        match resultado {
            Ok(()) => {
                let _ = progresso.send(json!({"etapa": "abrir"}));
                let _ = progresso.send(json!({"fim": "pronto"}));
                if let Ok(atual) = janela.url() {
                    ir(
                        &janela,
                        atual.join("/verificar.html").expect("caminho fixo"),
                    );
                }
            }
            Err(erro) => {
                let falha =
                    json!({"fim": "falhou", "motivo": erro.codigo(), "detalhe": erro.detalhe()});
                let _ = progresso.send(falha);
            }
        }
    });
    Ok(())
}

/// O "Fechar" da tela de instalação e o "Parar e fechar" do alerta: no meio da instalação,
/// cancela (a linha da instalação desfaz e fecha a janela); fora dela, fecha.
#[tauri::command]
fn fechar_instalador(app: AppHandle) {
    let estado = app.state::<Arc<Instalacao>>();
    if estado.em_curso.load(Ordering::SeqCst) {
        estado.cancelado.store(true, Ordering::SeqCst);
    } else if let Some(janela) = app.get_webview_window("main") {
        let _ = janela.close();
    }
}

fn em_curso(app: &AppHandle) -> bool {
    app.state::<Arc<Instalacao>>()
        .em_curso
        .load(Ordering::SeqCst)
}

/// Fechar no meio da instalação: a página pergunta antes (alerta, desenho 5.2).
fn pedir_fechar(app: &AppHandle) {
    if let Some(pagina) = app.get_webview_window("main") {
        let _ = pagina.eval("window.__jobotPedirFechar && window.__jobotPedirFechar()");
    }
}

/// Janela velha (5.4): abre o modo app de hoje (`jobot abrir`), avisa e fecha a janela.
fn cair_no_navegador(janela: WebviewWindow, base: Url) {
    let dados = dados();
    let Some(jobot) = servidor::jobot_instalado(&dados, std::env::consts::OS) else {
        ir(&janela, pagina_de_erro(&base, "instalar", "", ""));
        return;
    };
    if let Err(erro) = servidor::comando_destacado(&jobot, "abrir").spawn() {
        let log = servidor::fim_do_log(&dados);
        ir(
            &janela,
            pagina_de_erro(&base, "subir", &erro.to_string(), &log),
        );
        return;
    }
    ir(&janela, pagina_de_erro(&base, "janela", "", ""));
    std::thread::sleep(AVISO_DA_JANELA);
    let _ = janela.close();
}

fn tratar(app: &AppHandle, destino: &Url) -> bool {
    let Some(aviso) = aviso_local(destino) else {
        return true;
    };
    let Some(janela) = app.get_webview_window("main") else {
        return false;
    };
    // fora do tratador da navegação: navegar de dentro dele pode travar o WebKitGTK
    let base = destino.clone();
    std::thread::spawn(move || {
        // quem navega é a página aberta agora: se não for local (o painel), nada acontece
        if !janela.url().is_ok_and(|atual| e_local(&atual)) {
            return;
        }
        match aviso {
            Aviso::Janela { ok: true } => abrir_painel(janela, base),
            Aviso::Janela { ok: false } => cair_no_navegador(janela, base),
            Aviso::Tentar => ir(&janela, base.join("/verificar.html").expect("caminho fixo")),
            Aviso::Fechar => {
                let _ = janela.close();
            }
        }
    });
    false
}

/// A janela `main` do `tauri.conf.json` (`tauri.macos.conf.json` no Mac: `Overlay`), que abre
/// em `ui/verificar.html`.
fn abrir_janela(app: &AppHandle) -> tauri::Result<()> {
    let config = app
        .config()
        .app
        .windows
        .iter()
        .find(|j| j.label == "main")
        .expect("janela main no tauri.conf.json")
        .clone();
    let dono = app.clone();
    WebviewWindowBuilder::from_config(app, &config)?
        .user_agent(&agente(std::env::consts::OS))
        .on_navigation(move |destino| tratar(&dono, destino))
        .build()?;
    Ok(())
}

fn trazer_para_frente(app: &AppHandle) {
    if let Some(janela) = app.get_webview_window("main") {
        let _ = janela.unminimize();
        let _ = janela.show();
        let _ = janela.set_focus();
    }
}

/// A janela fechou e a casca vai sair: para o servidor que ela subiu, se não for de ficar.
fn ao_sair() {
    fechar::ao_fechar(
        SUBIU.swap(false, Ordering::Relaxed),
        &dados(),
        std::env::consts::OS,
        servidor::perguntar_segundo_plano,
        |jobot| {
            // destacado: o `jobot sair` termina o trabalho mesmo com a casca já fechada
            if let Err(erro) = servidor::comando_destacado(jobot, "sair").spawn() {
                eprintln!("jobot-app: não consegui rodar jobot sair: {erro}");
            }
        },
    );
}

fn main() {
    // antes de tudo, até das fumaças: o AppImage sem FUSE não deixa a extração no /tmp (T354)
    #[cfg(target_os = "linux")]
    extraido::vigiar();
    let contexto = tauri::generate_context!();
    let args: Vec<String> = std::env::args().skip(1).collect();
    if let [flag, url] = args.as_slice()
        && flag == "--verificar-janela"
    {
        verificar_janela(url, contexto);
        return;
    }
    if args.first().is_some_and(|a| a == "--verificar") {
        std::process::exit(verificar(contexto.package_info()));
    }
    if args.first().is_some_and(|a| a == "--verificar-navegador") {
        std::process::exit(verificar_navegador(contexto.package_info()));
    }
    if args.first().is_some_and(|a| a == "--desinstalar") {
        // o desinstalador do NSIS (desktop/windows/ganchos.nsh, desenho 7.2)
        fechar::desinstalar(&dados(), std::env::consts::OS, fechar::rodar_esperando);
        return;
    }
    tauri::Builder::default()
        // primeiro plugin: a segunda abertura só traz a janela que já existe (desenho 5.1)
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            trazer_para_frente(app)
        }))
        .manage(Arc::new(Instalacao::default()))
        .invoke_handler(tauri::generate_handler![
            estado_instalador,
            instalar,
            fechar_instalador
        ])
        .on_window_event(|janela, evento| {
            if let WindowEvent::CloseRequested { api, .. } = evento
                && em_curso(janela.app_handle())
            {
                api.prevent_close();
                pedir_fechar(janela.app_handle());
            }
        })
        .setup(|app| {
            abrir_janela(app.handle())?;
            Ok(())
        })
        .build(contexto)
        .expect("erro ao montar a janela")
        .run(|app, evento| match evento {
            // o Cmd+Q do Mac sai sem passar pelo CloseRequested: no meio da instalação, pergunta
            RunEvent::ExitRequested { api, .. } if em_curso(app) => {
                api.prevent_exit();
                pedir_fechar(app);
            }
            RunEvent::Exit => ao_sair(),
            _ => {}
        });
}

/// Prova da ponte (T321): abre a URL sem moldura e sai com 0 se a IPC respondeu, 2 se não.
fn verificar_janela(alvo: &str, contexto: tauri::Context) {
    let url: Url = alvo.parse().expect("URL inválida");
    tauri::Builder::default()
        .setup(move |app| {
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("joBot")
                .decorations(false)
                .on_page_load(|webview, carga| {
                    if carga.event() == PageLoadEvent::Finished && resultado(carga.url()).is_none()
                    {
                        webview.eval(SCRIPT).expect("eval do script da prova");
                    }
                })
                .on_navigation(|destino| match resultado(destino) {
                    Some(codigo) => {
                        println!("verificar-janela: {destino} -> {codigo}");
                        std::process::exit(codigo);
                    }
                    None => true,
                })
                .build()?;
            std::thread::spawn(|| {
                std::thread::sleep(PRAZO);
                eprintln!("verificar-janela: sem resposta em {PRAZO:?}");
                std::process::exit(2);
            });
            Ok(())
        })
        .run(contexto)
        .expect("erro ao rodar a janela");
}

/// Abre o Chromium de verdade pelo Python do venv e lê uma página (desenho 10): só conferir a
/// pasta não prova o bit de execução nem as bibliotecas. `channel="chromium"` é o binário
/// completo, o mesmo que o joBot abre com janela, em headless novo (sem tela); sem ele o
/// Playwright cairia no headless shell, que o `playwright install --no-shell` não baixa (D183).
const SCRIPT_CHROMIUM: &str = r#"
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    navegador = p.chromium.launch(channel="chromium")
    pagina = navegador.new_page()
    pagina.set_content("<p>joBot</p>")
    assert pagina.inner_text("p") == "joBot"
    navegador.close()
print("verificar: chromium ok")
"#;

/// O `python` ao lado do `jobot` do venv (`bin/` ou `Scripts\`).
fn python_ao_lado(jobot: &Path, so: &str) -> PathBuf {
    jobot.with_file_name(if so == "windows" {
        "python.exe"
    } else {
        "python"
    })
}

/// O Python do venv rodando o `SCRIPT_CHROMIUM`, sem o ambiente do Python do AppImage.
fn comando_chromium(jobot: &Path, so: &str) -> std::process::Command {
    let mut comando = std::process::Command::new(python_ao_lado(jobot, so));
    servidor::sem_python_de_fora(&mut comando).args(["-c", SCRIPT_CHROMIUM]);
    comando
}

/// A pasta dos recursos (a mesma do app), a de dados e a da casca, para a fumaça.
fn pastas_da_fumaca(info: &tauri::PackageInfo, so: &str) -> Option<(PathBuf, PathBuf, PathBuf)> {
    let recursos = match tauri::utils::platform::resource_dir(info, &tauri::Env::default()) {
        Ok(pasta) => pasta.join("recursos"),
        Err(erro) => {
            eprintln!("verificar: sem a pasta dos recursos: {erro}");
            return None;
        }
    };
    let (dados, pasta) = (dados(), instalar::pasta_da_casca(ambiente, so));
    println!("verificar: recursos {}", recursos.display());
    println!(
        "verificar: dados {}; casca {}",
        dados.display(),
        pasta.display()
    );
    Some((recursos, dados, pasta))
}

/// Fumaça sem janela e sem rede (desenho 10; D174.4): instala dos recursos sem o navegador,
/// sobe o servidor, confere `/saude-local` e para o servidor. 0 se tudo deu. O navegador, que
/// vem da internet (D183.24), é o `--verificar-navegador`, num passo à parte com rede.
fn verificar(info: &tauri::PackageInfo) -> i32 {
    let so = std::env::consts::OS;
    let Some((recursos, dados, pasta)) = pastas_da_fumaca(info, so) else {
        return 1;
    };
    let instalador = instalar::Instalador {
        recursos: &recursos,
        pasta: &pasta,
        dados: &dados,
        so,
        versao: VERSAO,
    };
    let cancelado = AtomicBool::new(false);
    let mut rodar = |comando: std::process::Command, linha: &mut dyn FnMut(&str)| {
        instalar::rodar(comando, &cancelado, linha)
    };
    let feito = instalador.instalar(
        SHA_MANIFESTO.unwrap_or_default(),
        false,
        &cancelado,
        &mut rodar,
        &mut |aviso| println!("verificar: {aviso}"),
    );
    if let Err(erro) = feito {
        eprintln!(
            "verificar: a instalação falhou ({}): {}",
            erro.codigo(),
            erro.detalhe()
        );
        return 1;
    }
    let Some(jobot) = servidor::jobot_instalado(&dados, so) else {
        eprintln!("verificar: o instalacao.json não aponta um jobot");
        return 1;
    };
    let porta = match servidor::achar_ou_subir(&dados, &jobot, ambiente) {
        Ok(achado) => achado.porta,
        Err(falha) => {
            eprintln!(
                "verificar: o servidor não subiu ({}): {}",
                falha.codigo(),
                falha.detalhe()
            );
            eprintln!("{}", servidor::fim_do_log(&dados));
            return 1;
        }
    };
    let saude = servidor::perguntar_saude(porta);
    println!("verificar: /saude-local na porta {porta}: {saude}");
    fechar::rodar_esperando(&jobot, &["sair"]);
    if saude { 0 } else { 1 }
}

/// Fumaça do navegador, com rede, depois do `--verificar`: o mesmo passo da tela de instalação
/// (`Instalador::baixar_navegador`, o `playwright install` pelo joBot do venv) e o Chromium
/// aberto de verdade pelo Python do venv. 0 se os dois deram.
fn verificar_navegador(info: &tauri::PackageInfo) -> i32 {
    let so = std::env::consts::OS;
    let Some((recursos, dados, pasta)) = pastas_da_fumaca(info, so) else {
        return 1;
    };
    let Some(jobot) = servidor::jobot_instalado(&dados, so) else {
        eprintln!("verificar: sem instalação; rode o --verificar antes");
        return 1;
    };
    let instalador = instalar::Instalador {
        recursos: &recursos,
        pasta: &pasta,
        dados: &dados,
        so,
        versao: VERSAO,
    };
    let cancelado = AtomicBool::new(false);
    let mut rodar = |comando: std::process::Command, linha: &mut dyn FnMut(&str)| {
        instalar::rodar(comando, &cancelado, linha)
    };
    let baixado = instalador.baixar_navegador(&cancelado, &mut rodar, &mut |aviso| {
        println!("verificar: {aviso}")
    });
    if let Err(erro) = baixado {
        eprintln!(
            "verificar: o navegador não baixou ({}): {}",
            erro.codigo(),
            erro.detalhe()
        );
        return 1;
    }
    match comando_chromium(&jobot, so).status() {
        Ok(status) if status.success() => 0,
        Ok(_) => 1,
        Err(erro) => {
            eprintln!("verificar: não consegui rodar o Python do venv: {erro}");
            1
        }
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    fn url(texto: &str) -> Url {
        texto.parse().unwrap()
    }

    #[test]
    fn ok_da_zero() {
        assert_eq!(
            resultado(&url("http://127.0.0.1:8765/__jobot_resultado?ok=false")),
            Some(0)
        );
    }

    #[test]
    fn erro_da_dois() {
        let u = url("http://127.0.0.1:8765/__jobot_resultado?erro=x&csp=connect-src");
        assert_eq!(resultado(&u), Some(2));
    }

    #[test]
    fn outra_pagina_nao_e_resultado() {
        assert_eq!(resultado(&url("http://127.0.0.1:8765/?ok=1")), None);
    }

    #[test]
    fn python_ao_lado_do_jobot_do_venv() {
        let venv = Path::new("venvs").join("venv-1");
        let jobot = servidor::jobot_do_venv(&venv, "linux");
        assert_eq!(
            python_ao_lado(&jobot, "linux"),
            venv.join("bin").join("python")
        );
        let jobot = servidor::jobot_do_venv(&venv, "windows");
        assert_eq!(
            python_ao_lado(&jobot, "windows"),
            venv.join("Scripts").join("python.exe")
        );
    }

    #[test]
    fn chromium_completo_pelo_python_do_venv_sem_o_ambiente_do_appimage() {
        let venv = Path::new("venvs").join("venv-1");
        let jobot = servidor::jobot_do_venv(&venv, "linux");
        let c = comando_chromium(&jobot, "linux");
        assert_eq!(c.get_program(), venv.join("bin").join("python").as_os_str());
        assert_eq!(c.get_args().collect::<Vec<_>>(), ["-c", SCRIPT_CHROMIUM]);
        let fora: Vec<_> = c
            .get_envs()
            .filter(|(_, v)| v.is_none())
            .map(|(k, _)| k)
            .collect();
        assert_eq!(fora, ["LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"]);
    }

    #[test]
    fn script_abre_o_chromium_completo_e_nao_o_headless_shell() {
        assert!(SCRIPT_CHROMIUM.contains("p.chromium.launch(channel=\"chromium\")"));
    }

    #[test]
    fn script_usa_o_mesmo_caminho() {
        assert!(SCRIPT.contains(CAMINHO_RESULTADO));
    }

    #[test]
    fn agente_leva_a_marca_da_casca() {
        let versao = env!("CARGO_PKG_VERSION");
        for (so, marca) in [
            ("linux", "linux"),
            ("windows", "windows"),
            ("macos", "macos"),
        ] {
            let ua = agente(so);
            assert!(ua.starts_with("Mozilla/5.0 ("), "{ua}");
            assert!(
                ua.ends_with(&format!(" joBot-casca/{versao} ({marca})")),
                "{ua}"
            );
        }
    }

    #[test]
    fn so_a_origem_local_fala_com_a_casca() {
        let ok = Some(Aviso::Janela { ok: true });
        assert_eq!(
            aviso_local(&url("tauri://localhost/__jobot/janela?ok=1")),
            ok
        );
        assert_eq!(
            aviso_local(&url("http://tauri.localhost/__jobot/janela?ok=1")),
            ok
        );
        assert_eq!(
            aviso_local(&url("tauri://localhost/__jobot/janela?falta=popover")),
            Some(Aviso::Janela { ok: false })
        );
        assert_eq!(
            aviso_local(&url("tauri://localhost/__jobot/tentar")),
            Some(Aviso::Tentar)
        );
        assert_eq!(
            aviso_local(&url("http://127.0.0.1:47615/__jobot/tentar")),
            None
        );
        assert_eq!(aviso_local(&url("tauri://localhost/verificar.html")), None);
        assert_eq!(
            aviso_local(&url("tauri://localhost/__jobot/fechar")),
            Some(Aviso::Fechar)
        );
        for de_fora in [
            "tauri://outro/__jobot/tentar",
            "http://tauri.localhost:8080/__jobot/tentar",
            "http://tauri.localhost.exemplo/__jobot/tentar",
            "file://localhost/__jobot/tentar",
        ] {
            assert_eq!(aviso_local(&url(de_fora)), None, "{de_fora}");
        }
    }

    #[test]
    fn so_a_pagina_local_pede() {
        assert!(e_local(&url("tauri://localhost/erro.html?motivo=porta")));
        assert!(e_local(&url("http://tauri.localhost/verificar.html")));
        assert!(e_local(&url("https://tauri.localhost/erro.html")));
        assert!(!e_local(&url("http://127.0.0.1:47615/")));
        assert!(!e_local(&url("http://localhost/")));
        assert!(!e_local(&url("tauri://outro/")));
    }

    #[test]
    fn sem_instalacao_vai_para_a_tela_de_instalacao() {
        let base = url("tauri://localhost/__jobot/janela?ok=1");
        let dados = Path::new("/nao/existe");
        let destino = destino_do_arranque(&base, Err(servidor::Falha::SemInstalacao), dados);
        assert_eq!(destino.as_str(), "tauri://localhost/index.html");
        let painel = destino_do_arranque(&base, Ok(47615), dados);
        assert_eq!(painel.as_str(), "http://127.0.0.1:47615/");
        let erro = destino_do_arranque(&base, Err(servidor::Falha::Porta(8000)), dados);
        assert_eq!(erro.path(), "/erro.html");
    }

    #[test]
    fn erro_leva_motivo_detalhe_e_log_na_origem_local() {
        let u = pagina_de_erro(
            &url("tauri://localhost/__jobot/janela?ok=1"),
            "porta",
            "47615",
            "a&b\nc",
        );
        assert_eq!(u.path(), "/erro.html");
        assert_eq!(u.scheme(), "tauri");
        let pares: Vec<(String, String)> =
            u.query_pairs().map(|(k, v)| (k.into(), v.into())).collect();
        assert_eq!(
            pares,
            [
                ("motivo".into(), "porta".into()),
                ("detalhe".into(), "47615".into()),
                ("log".into(), "a&b\nc".into())
            ]
        );
    }
}
