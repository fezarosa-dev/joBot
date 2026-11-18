// A casca do joBot (D206, ADR 0027): instância única e uma janela pequena de controle, com o
// estado do painel, o endereço e os botões Ligar, Parar e Abrir joBot; o painel abre no
// navegador padrão da pessoa, nunca dentro da janela. Sem o joBot instalado, a janela mostra a
// tela de instalação (desenho 5.2) e, no fim, o controle. Com --verificar e
// --verificar-navegador, a fumaça sem janela da release (desenho 10).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod controle;
mod fechar;
mod instalar;
mod servidor;

use serde_json::{Value, json};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::ipc::Channel;
use tauri::utils::config::WindowConfig;
use tauri::{
    AppHandle, LogicalSize, Manager, RunEvent, Url, WebviewUrl, WebviewWindow,
    WebviewWindowBuilder, WindowEvent,
};

/// O sha256 do `manifesto.json` dos recursos, gravado no build (desenho 6.2; D174.7). Sem ele
/// (build local sem recursos), a tela diz que o instalador está incompleto.
const SHA_MANIFESTO: Option<&str> = option_env!("JOBOT_MANIFESTO_SHA256");
const VERSAO: &str = env!("CARGO_PKG_VERSION");

/// Se esta abertura da casca subiu o servidor (desenho 5.5): só esse ela pode parar ao fechar.
static SUBIU: AtomicBool = AtomicBool::new(false);

/// Ligar e Parar, um de cada vez: dois `jobot serve` ao mesmo tempo brigariam pela porta.
static ACAO: Mutex<()> = Mutex::new(());

/// A tela de instalação precisa de mais espaço que o controle do `tauri.conf.json` (D207).
const INSTALADOR: (f64, f64) = (760.0, 580.0);
const INSTALADOR_MINIMO: (f64, f64) = (640.0, 480.0);

fn ambiente(nome: &str) -> Option<String> {
    std::env::var(nome).ok()
}

fn dados() -> PathBuf {
    servidor::pasta_de_dados(ambiente, std::env::consts::OS)
}

fn ir(janela: &WebviewWindow, url: Url) {
    if let Err(erro) = janela.navigate(url) {
        eprintln!("jobot-app: não consegui navegar: {erro}");
    }
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
                ir_ao_controle(&app, &janela);
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

/// O estado do painel agora, pela `/saude-local` (no máximo uns 2 s, fora da linha da janela).
fn estado_agora(dados: &Path) -> Value {
    controle::estado(controle::porta(dados, ambiente), servidor::perguntar_saude)
}

/// O controle pergunta o estado ao abrir e de tempos em tempos: só lê, nunca liga nem abre.
/// `async`: a pergunta roda fora da linha da janela, que não trava.
#[tauri::command(async)]
fn estado_controle() -> Value {
    estado_agora(&dados())
}

/// Ligar: o `servidor::achar_ou_subir` do joBot instalado (até 15 s, fora da linha da janela).
#[tauri::command(async)]
fn ligar() -> Value {
    let _vez = ACAO.lock().unwrap_or_else(|e| e.into_inner());
    let dados = dados();
    let trava_solta = servidor::ler_trava(&dados).0.is_none();
    let resultado = controle::ligar(&dados, std::env::consts::OS, |jobot| {
        servidor::achar_ou_subir(&dados, jobot, ambiente)
    });
    if controle::subiu(trava_solta, &resultado) {
        SUBIU.store(true, Ordering::Relaxed);
    }
    match resultado {
        Ok(achado) => controle::estado(achado.porta, |_| true),
        Err(falha) => controle::com_falha(
            estado_agora(&dados),
            falha.codigo(),
            &falha.detalhe(),
            &servidor::fim_do_log(&dados),
        ),
    }
}

/// Parar: `jobot sair`, esperando o servidor sair (o `sair` espera até 10 s).
#[tauri::command(async)]
fn parar() -> Value {
    let _vez = ACAO.lock().unwrap_or_else(|e| e.into_inner());
    let dados = dados();
    let estado = controle::parar(
        &dados,
        std::env::consts::OS,
        |jobot| fechar::rodar_esperando(jobot, &["sair"]),
        || estado_agora(&dados),
    );
    if estado["ligado"] != true {
        SUBIU.store(false, Ordering::Relaxed); // só quando parou: no ar, fechar ainda o para
    }
    estado
}

/// Abrir joBot: o endereço do painel no navegador padrão da pessoa, só com o painel no ar.
#[tauri::command(async)]
fn abrir_jobot() -> Value {
    let dados = dados();
    controle::abrir(
        controle::porta(&dados, ambiente),
        servidor::perguntar_saude,
        |endereco| {
            let vars: Vec<_> = std::env::vars().collect();
            controle::comando_abridor(std::env::consts::OS, &vars, endereco)
        },
        |mut comando| {
            let mut filho = comando.spawn()?;
            std::thread::spawn(move || filho.wait()); // colhe o abridor quando ele sair
            Ok(())
        },
    )
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

/// A janela `main` do `tauri.conf.json`: o controle, pequeno e com as decorações do sistema.
fn janela_do_controle(app: &AppHandle) -> WindowConfig {
    app.config()
        .app
        .windows
        .iter()
        .find(|j| j.label == "main")
        .expect("janela main no tauri.conf.json")
        .clone()
}

/// Sem o joBot instalado, a mesma janela abre na tela de instalação, maior.
fn para_o_instalador(mut config: WindowConfig) -> WindowConfig {
    config.url = WebviewUrl::App("index.html".into());
    (config.width, config.height) = INSTALADOR;
    (config.min_width, config.min_height) = (Some(INSTALADOR_MINIMO.0), Some(INSTALADOR_MINIMO.1));
    config
}

/// Instalação pronta: a janela volta ao tamanho do controle e mostra o controle.
fn ir_ao_controle(app: &AppHandle, janela: &WebviewWindow) {
    let config = janela_do_controle(app);
    let minimo = config
        .min_width
        .zip(config.min_height)
        .map(|(l, a)| LogicalSize::new(l, a));
    let _ = janela.set_min_size(minimo);
    let _ = janela.set_size(LogicalSize::new(config.width, config.height));
    let _ = janela.center();
    if let Ok(atual) = janela.url() {
        ir(janela, atual.join("/controle.html").expect("caminho fixo"));
    }
}

/// Abre a janela no controle (joBot instalado) ou na tela de instalação (sem ele).
fn abrir_janela(app: &AppHandle) -> tauri::Result<()> {
    let config = janela_do_controle(app);
    let instalado = servidor::jobot_instalado(&dados(), std::env::consts::OS).is_some();
    let config = if instalado {
        config
    } else {
        para_o_instalador(config)
    };
    WebviewWindowBuilder::from_config(app, &config)?.build()?;
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
    let contexto = tauri::generate_context!();
    let args: Vec<String> = std::env::args().skip(1).collect();
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
            fechar_instalador,
            estado_controle,
            ligar,
            parar,
            abrir_jobot
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

    fn conf(texto: &str) -> Value {
        serde_json::from_str(texto).unwrap()
    }

    fn main_do_conf() -> WindowConfig {
        let c = conf(include_str!("../tauri.conf.json"));
        let main = c["app"]["windows"]
            .as_array()
            .unwrap()
            .iter()
            .find(|j| j["label"] == "main")
            .unwrap()
            .clone();
        serde_json::from_value(main).unwrap()
    }

    #[test]
    fn janela_main_e_o_controle_pequeno_com_as_decoracoes_do_sistema() {
        let main = main_do_conf();
        assert!(!main.create, "a casca cria a janela (abrir_janela)");
        assert_eq!(main.url, WebviewUrl::App("controle.html".into()));
        assert!((380.0..=480.0).contains(&main.width), "{}", main.width);
        assert!((260.0..=360.0).contains(&main.height), "{}", main.height);
        assert!(main.decorations);
        // no Mac também: sem a barra própria (Overlay) que o painel desenhava
        let mac = conf(include_str!("../tauri.macos.conf.json"));
        assert!(mac["app"]["windows"].is_null(), "{mac}");
    }

    #[test]
    fn sem_instalacao_a_mesma_janela_abre_a_tela_de_instalacao_maior() {
        let main = main_do_conf();
        let instalador = para_o_instalador(main.clone());
        assert_eq!(instalador.url, WebviewUrl::App("index.html".into()));
        assert_eq!((instalador.width, instalador.height), INSTALADOR);
        assert_eq!(
            (instalador.min_width, instalador.min_height),
            (Some(INSTALADOR_MINIMO.0), Some(INSTALADOR_MINIMO.1))
        );
        assert!(instalador.width > main.width && instalador.height > main.height);
        assert_eq!(
            (instalador.label, instalador.decorations),
            (main.label, main.decorations)
        );
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
}
