// A casca do joBot (desenho 5.1 a 5.4): instância única, confere a janela, acha ou sobe o
// `jobot serve` e abre o painel em http://127.0.0.1:<porta>/. Com --verificar-janela <url>,
// a prova da ponte da T321 (a IPC do Tauri numa origem http://127.0.0.1 remota).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod servidor;

use std::path::PathBuf;
use std::time::Duration;
use tauri::webview::PageLoadEvent;
use tauri::{AppHandle, Manager, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

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

/// Janela conferida: acha ou sobe o servidor e navega ao painel (roda fora da linha da janela).
fn abrir_painel(janela: WebviewWindow, base: Url) {
    let dados = dados();
    let resultado = servidor::jobot_instalado(&dados, std::env::consts::OS)
        .ok_or(servidor::Falha::SemInstalacao)
        .and_then(|jobot| servidor::achar_ou_subir(&dados, &jobot, ambiente));
    let destino = match resultado {
        Ok(porta) => servidor::url_do_painel(porta).parse().expect("URL fixa"),
        Err(falha) => pagina_de_erro(
            &base,
            falha.codigo(),
            &falha.detalhe(),
            &servidor::fim_do_log(&dados),
        ),
    };
    ir(&janela, destino);
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

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if let [flag, url] = args.as_slice()
        && flag == "--verificar-janela"
    {
        verificar_janela(url);
        return;
    }
    tauri::Builder::default()
        // primeiro plugin: a segunda abertura só traz a janela que já existe (desenho 5.1)
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            trazer_para_frente(app)
        }))
        .setup(|app| {
            abrir_janela(app.handle())?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("erro ao rodar a janela");
}

/// Prova da ponte (T321): abre a URL sem moldura e sai com 0 se a IPC respondeu, 2 se não.
fn verificar_janela(alvo: &str) {
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
        .run(tauri::generate_context!())
        .expect("erro ao rodar a janela");
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
