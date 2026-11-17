// Esqueleto da prova da ponte (T321): abre o painel numa janela sem moldura e,
// com --verificar-janela, confere se a IPC do Tauri responde numa origem
// http://127.0.0.1 remota. Não é a casca final.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::time::Duration;
use tauri::webview::PageLoadEvent;
use tauri::{Url, WebviewUrl, WebviewWindowBuilder};

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

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (verificar, alvo) = match args.as_slice() {
        [flag, url] if flag == "--verificar-janela" => (true, url),
        [url] => (false, url),
        _ => {
            eprintln!("uso: jobot-app [--verificar-janela] http://127.0.0.1:<porta>/");
            std::process::exit(1);
        }
    };
    let url: Url = alvo.parse().expect("URL inválida");

    tauri::Builder::default()
        .setup(move |app| {
            let mut janela = WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("joBot")
                .decorations(false);
            if verificar {
                janela = janela
                    .on_page_load(|webview, carga| {
                        if carga.event() == PageLoadEvent::Finished
                            && resultado(carga.url()).is_none()
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
                    });
                std::thread::spawn(|| {
                    std::thread::sleep(PRAZO);
                    eprintln!("verificar-janela: sem resposta em {PRAZO:?}");
                    std::process::exit(2);
                });
            }
            janela.build()?;
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
}
