//! Fechar a janela e desinstalar (desenho 5.5 e 7.2). Os comandos entram por parâmetro: os
//! testes contam as chamadas sem subir nenhum processo.

use crate::servidor;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

/// O servidor que a casca subiu nesta abertura: só esse ela pode parar ao fechar.
#[derive(Debug, Clone, PartialEq)]
pub struct Subido {
    pub jobot: PathBuf,
    pub porta: u16,
}

/// Ao fechar a janela (desenho 5.5): `jobot sair` só se a casca subiu o servidor e o
/// `/saude-local` diz `segundo_plano: false`. Servidor que a casca achou no ar (o do segundo
/// plano, o de um `jobot abrir`), resposta que não vem ou sem o campo: nada é parado.
pub fn ao_fechar(
    _subido: Option<&Subido>,
    _segundo_plano: impl FnOnce(u16) -> Option<bool>,
    _sair: impl FnOnce(&Path),
) {
}

/// A pasta da casca do `<dados>/instalacao.json` (desenho 6.2), só se apagá-la não leva a
/// pasta de dados junto: caminho absoluto que não é a pasta de dados nem a contém.
fn pasta_da_casca(_dados: &Path) -> Option<PathBuf> {
    None
}

/// Desinstalar (desenho 7.2; o NSIS chama `--desinstalar`): com o `jobot` do venv, desliga o
/// segundo plano e para o servidor; depois apaga a pasta da casca e o `instalacao.json`.
/// Nunca a pasta de dados; o Chromium da pasta padrão do Playwright fica (D174).
pub fn desinstalar(_dados: &Path, _so: &str, _rodar: impl FnMut(&Path, &[&str])) {
    let _ = (pasta_da_casca, apagar_pasta, servidor::jobot_instalado);
}

/// `jobot <args>` esperando o fim, sem entrada, saída nem janela de console.
pub fn rodar_esperando(jobot: &Path, args: &[&str]) {
    let mut comando = Command::new(jobot);
    comando
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    std::os::windows::process::CommandExt::creation_flags(&mut comando, 0x0800_0000);
    if let Err(erro) = comando.status() {
        eprintln!("jobot-app: não consegui rodar {}: {erro}", jobot.display());
    }
}

/// `remove_dir_all` com algumas tentativas: no Windows o processo que acabou de sair ainda
/// prende os arquivos do venv por um instante.
fn apagar_pasta(pasta: &Path) {
    for _ in 0..10 {
        match std::fs::remove_dir_all(pasta) {
            Ok(()) => return,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return,
            Err(_) => std::thread::sleep(Duration::from_millis(500)),
        }
    }
    eprintln!("jobot-app: não consegui apagar {}", pasta.display());
}

#[cfg(test)]
mod testes {
    use super::*;
    use std::cell::RefCell;

    fn temporaria(nome: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("jobot-fechar-{nome}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&p);
        std::fs::create_dir_all(&p).unwrap();
        p
    }

    fn subido() -> Subido {
        Subido {
            jobot: PathBuf::from("/venv/bin/jobot"),
            porta: 47615,
        }
    }

    /// Fecha com a resposta `segundo_plano` e conta quem perguntou e quem chamou `jobot sair`.
    fn fechar(subido: Option<&Subido>, resposta: Option<bool>) -> (Vec<u16>, Vec<PathBuf>) {
        let perguntas = RefCell::new(Vec::new());
        let saidas = RefCell::new(Vec::new());
        ao_fechar(
            subido,
            |porta| {
                perguntas.borrow_mut().push(porta);
                resposta
            },
            |jobot| saidas.borrow_mut().push(jobot.to_path_buf()),
        );
        (perguntas.into_inner(), saidas.into_inner())
    }

    #[test]
    fn segundo_plano_desligado_chama_jobot_sair() {
        let (perguntas, saidas) = fechar(Some(&subido()), Some(false));
        assert_eq!(perguntas, [47615]);
        assert_eq!(saidas, [PathBuf::from("/venv/bin/jobot")]);
    }

    #[test]
    fn segundo_plano_ligado_nao_chama() {
        let (_, saidas) = fechar(Some(&subido()), Some(true));
        assert!(saidas.is_empty());
    }

    #[test]
    fn sem_resposta_nao_chama() {
        let (_, saidas) = fechar(Some(&subido()), None);
        assert!(saidas.is_empty());
    }

    #[test]
    fn nunca_para_servidor_que_a_casca_nao_subiu() {
        let (perguntas, saidas) = fechar(None, Some(false));
        assert!(perguntas.is_empty());
        assert!(saidas.is_empty());
    }

    /// `<dados>` com o banco, um venv com o `jobot` e o `instalacao.json` apontando `pasta`.
    fn instalado(dados: &Path, pasta: &Path) -> PathBuf {
        let venv = pasta.join("venvs").join("venv-0.4.0");
        let jobot = servidor::jobot_do_venv(&venv, "linux");
        std::fs::create_dir_all(jobot.parent().unwrap()).unwrap();
        std::fs::write(&jobot, "").unwrap();
        std::fs::create_dir_all(pasta.join("python")).unwrap();
        std::fs::write(pasta.join("manifesto-0.4.0.json"), "{}").unwrap();
        std::fs::write(dados.join("jobot.db"), "banco").unwrap();
        let instalacao = serde_json::json!({
            "canal": "casca",
            "pasta": pasta,
            "venv": venv,
        });
        std::fs::write(dados.join("instalacao.json"), instalacao.to_string()).unwrap();
        jobot
    }

    fn desinstalar_contando(dados: &Path) -> Vec<(PathBuf, Vec<String>)> {
        let mut chamadas = Vec::new();
        desinstalar(dados, "linux", |jobot, args| {
            let args = args.iter().map(|a| a.to_string()).collect();
            chamadas.push((jobot.to_path_buf(), args));
        });
        chamadas
    }

    fn args(lista: &[&str]) -> Vec<String> {
        lista.iter().map(|a| a.to_string()).collect()
    }

    #[test]
    fn desinstalar_desliga_para_e_apaga_a_pasta_da_casca() {
        // Windows e Mac: a pasta da casca fica dentro da pasta de dados (`<dados>/app`)
        let dados = temporaria("dentro");
        let pasta = dados.join("app");
        let jobot = instalado(&dados, &pasta);
        let chamadas = desinstalar_contando(&dados);
        assert_eq!(
            chamadas,
            [
                (jobot.clone(), args(&["segundo-plano", "desligar"])),
                (jobot, args(&["sair"])),
            ]
        );
        assert!(!pasta.exists());
        assert!(!dados.join("instalacao.json").exists());
        assert_eq!(std::fs::read(dados.join("jobot.db")).unwrap(), b"banco");
    }

    #[test]
    fn desinstalar_apaga_a_pasta_vizinha_no_linux() {
        // Linux: `~/.local/share/jobot-app/` ao lado de `~/.local/share/jobot/`
        let raiz = temporaria("vizinha");
        let dados = raiz.join("jobot");
        let pasta = raiz.join("jobot-app");
        std::fs::create_dir_all(&dados).unwrap();
        instalado(&dados, &pasta);
        assert_eq!(desinstalar_contando(&dados).len(), 2);
        assert!(!pasta.exists());
        assert!(dados.join("jobot.db").is_file());
    }

    #[test]
    fn desinstalar_nunca_apaga_a_pasta_de_dados() {
        for (nome, pasta) in [("igual", "."), ("acima", ".."), ("relativa", "rel")] {
            let raiz = temporaria(nome);
            let dados = raiz.join("dados");
            std::fs::create_dir_all(&dados).unwrap();
            let pasta = if pasta == "rel" {
                PathBuf::from("rel")
            } else {
                dados.join(pasta).canonicalize().unwrap()
            };
            let instalacao = serde_json::json!({"canal": "casca", "pasta": pasta, "venv": ""});
            std::fs::write(dados.join("instalacao.json"), instalacao.to_string()).unwrap();
            std::fs::write(dados.join("jobot.db"), "banco").unwrap();
            desinstalar_contando(&dados);
            assert!(dados.join("jobot.db").is_file(), "{nome}");
        }
    }

    #[test]
    fn desinstalar_sem_instalacao_nao_roda_nada() {
        let dados = temporaria("sem");
        std::fs::write(dados.join("jobot.db"), "banco").unwrap();
        assert!(desinstalar_contando(&dados).is_empty());
        assert!(dados.join("jobot.db").is_file());
    }
}
