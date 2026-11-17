//! Fechar a janela e desinstalar (desenho 5.5 e 7.2). Os comandos entram por parâmetro: os
//! testes contam as chamadas sem subir nenhum processo.

use crate::servidor;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

/// Ao fechar a janela (desenho 5.5): `jobot sair` só se a casca subiu o servidor nesta
/// abertura e o `/saude-local` diz `segundo_plano: false`. Servidor que a casca achou no ar
/// (o do segundo plano, o de um `jobot abrir`), resposta que não vem ou sem o campo: nada é
/// parado. A porta (da trava) e o `jobot` (do `instalacao.json`) são lidos agora, não os da
/// abertura: o "Atualizar agora" troca o venv e pode trocar a porta (D182).
pub fn ao_fechar(
    subiu: bool,
    dados: &Path,
    so: &str,
    segundo_plano: impl FnOnce(u16) -> Option<bool>,
    sair: impl FnOnce(&Path),
) {
    if !subiu {
        return;
    }
    let (_, Some(porta)) = servidor::ler_trava(dados) else {
        return; // ninguém prende a trava: não há servidor para parar
    };
    if segundo_plano(porta) == Some(false)
        && let Some(jobot) = servidor::jobot_instalado(dados, so)
    {
        sair(&jobot);
    }
}

/// A pasta da casca do `<dados>/instalacao.json` (desenho 6.2), só se apagá-la não leva a
/// pasta de dados junto (caminho absoluto que não é a pasta de dados nem a contém) e se ela
/// parece mesmo a da casca: canal `casca` e um `bin/` ou um `manifesto-*.json` dentro.
fn pasta_da_casca(dados: &Path) -> Option<PathBuf> {
    let texto = std::fs::read(dados.join("instalacao.json")).ok()?;
    let conteudo: serde_json::Value = serde_json::from_slice(&texto).ok()?;
    if conteudo.get("canal")?.as_str()? != "casca" {
        return None;
    }
    let pasta = PathBuf::from(conteudo.get("pasta")?.as_str()?);
    if !pasta.is_absolute() {
        return None;
    }
    // canônicos: `..`, symlink ou maiúsculas no Windows não escondem a pasta de dados
    let pasta = pasta.canonicalize().ok()?;
    let dados = dados.canonicalize().ok()?;
    if dados.starts_with(&pasta) {
        return None;
    }
    let manifesto = |nome: &str| nome.starts_with("manifesto-") && nome.ends_with(".json");
    let tem_sinal = pasta.join("bin").is_dir()
        || std::fs::read_dir(&pasta)
            .ok()?
            .flatten()
            .any(|e| e.file_name().to_str().is_some_and(manifesto) && e.path().is_file());
    tem_sinal.then_some(pasta)
}

/// Desinstalar (desenho 7.2; o NSIS chama `--desinstalar`): com o `jobot` do venv, desliga o
/// segundo plano e para o servidor; depois apaga a pasta da casca e o `instalacao.json`.
/// Nunca a pasta de dados; o Chromium da pasta padrão do Playwright fica (D174).
pub fn desinstalar(dados: &Path, so: &str, mut rodar: impl FnMut(&Path, &[&str])) {
    if let Some(jobot) = servidor::jobot_instalado(dados, so) {
        // desligar sem serviço também vale (`segundo_plano.desligar`): não precisa perguntar antes
        rodar(&jobot, &["segundo-plano", "desligar"]);
        rodar(&jobot, &["sair"]);
    }
    if let Some(pasta) = pasta_da_casca(dados) {
        apagar_pasta(&pasta);
    }
    let instalacao = dados.join("instalacao.json");
    if let Err(erro) = std::fs::remove_file(&instalacao)
        && erro.kind() != std::io::ErrorKind::NotFound
    {
        eprintln!(
            "jobot-app: não consegui apagar {}: {erro}",
            instalacao.display()
        );
    }
}

/// `jobot <args>` esperando o fim, sem entrada, saída nem janela de console.
pub fn rodar_esperando(jobot: &Path, args: &[&str]) {
    let mut comando = Command::new(jobot);
    servidor::sem_python_de_fora(&mut comando)
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

    /// Prende o `jobot.lock` com `texto`, como o `jobot serve` no ar.
    fn trava_presa(dados: &Path, texto: &str) -> std::fs::File {
        std::fs::write(dados.join("jobot.lock"), texto).unwrap();
        let dono = std::fs::File::open(dados.join("jobot.lock")).unwrap();
        servidor::prender_como_o_python(&dono);
        dono
    }

    /// Fecha com a resposta `segundo_plano` e conta quem perguntou e quem chamou `jobot sair`.
    fn fechar(subiu: bool, dados: &Path, resposta: Option<bool>) -> (Vec<u16>, Vec<PathBuf>) {
        let perguntas = RefCell::new(Vec::new());
        let saidas = RefCell::new(Vec::new());
        ao_fechar(
            subiu,
            dados,
            "linux",
            |porta| {
                perguntas.borrow_mut().push(porta);
                resposta
            },
            |jobot| saidas.borrow_mut().push(jobot.to_path_buf()),
        );
        (perguntas.into_inner(), saidas.into_inner())
    }

    /// `<dados>` instalado com o servidor no ar na porta 47615.
    fn no_ar(nome: &str) -> (PathBuf, PathBuf, std::fs::File) {
        let dados = temporaria(nome);
        let jobot = instalado(&dados, &dados.join("app"));
        let dono = trava_presa(&dados, "42\n47615\n");
        (dados, jobot, dono)
    }

    #[test]
    fn segundo_plano_desligado_chama_jobot_sair() {
        let (dados, jobot, _dono) = no_ar("desligado");
        let (perguntas, saidas) = fechar(true, &dados, Some(false));
        assert_eq!(perguntas, [47615]);
        assert_eq!(saidas, [jobot]);
    }

    #[test]
    fn segundo_plano_ligado_nao_chama() {
        let (dados, _, _dono) = no_ar("ligado");
        let (_, saidas) = fechar(true, &dados, Some(true));
        assert!(saidas.is_empty());
    }

    #[test]
    fn sem_resposta_nao_chama() {
        let (dados, _, _dono) = no_ar("sem-resposta");
        let (_, saidas) = fechar(true, &dados, None);
        assert!(saidas.is_empty());
    }

    #[test]
    fn nunca_para_servidor_que_a_casca_nao_subiu() {
        let (dados, _, _dono) = no_ar("nao-subiu");
        let (perguntas, saidas) = fechar(false, &dados, Some(false));
        assert!(perguntas.is_empty());
        assert!(saidas.is_empty());
    }

    #[test]
    fn trava_solta_nao_pergunta() {
        // o servidor já saiu: a trava ficou com dado velho, ninguém a prende
        let dados = temporaria("trava-solta");
        instalado(&dados, &dados.join("app"));
        std::fs::write(dados.join("jobot.lock"), "42\n47615\n").unwrap();
        let (perguntas, saidas) = fechar(true, &dados, Some(false));
        assert!(perguntas.is_empty());
        assert!(saidas.is_empty());
    }

    #[test]
    fn depois_de_atualizar_usa_o_jobot_e_a_porta_de_agora() {
        // "Atualizar agora": venv novo no instalacao.json e o servidor novo noutra porta
        let (dados, _, dono) = no_ar("atualizou");
        drop(dono);
        let venv = dados.join("app").join("venvs").join("venv-0.4.1");
        let novo = servidor::jobot_do_venv(&venv, "linux");
        std::fs::create_dir_all(novo.parent().unwrap()).unwrap();
        std::fs::write(&novo, "").unwrap();
        let instalacao = serde_json::json!({
            "canal": "casca",
            "pasta": dados.join("app"),
            "venv": venv,
        });
        std::fs::write(dados.join("instalacao.json"), instalacao.to_string()).unwrap();
        let _dono = trava_presa(&dados, "43\n8123\n");
        let (perguntas, saidas) = fechar(true, &dados, Some(false));
        assert_eq!(perguntas, [8123]);
        assert_eq!(saidas, [novo]);
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
    fn desinstalar_so_apaga_pasta_com_cara_de_casca() {
        // canal de outro jeito de instalar, ou pasta sem `bin/` nem manifesto: fica
        for (nome, canal, sinal) in [("outro-canal", "pip", true), ("sem-sinal", "casca", false)] {
            let dados = temporaria(nome);
            let pasta = dados.join("app");
            instalado(&dados, &pasta);
            if !sinal {
                std::fs::remove_file(pasta.join("manifesto-0.4.0.json")).unwrap();
            }
            let mut instalacao: serde_json::Value =
                serde_json::from_slice(&std::fs::read(dados.join("instalacao.json")).unwrap())
                    .unwrap();
            instalacao["canal"] = canal.into();
            std::fs::write(dados.join("instalacao.json"), instalacao.to_string()).unwrap();
            desinstalar_contando(&dados);
            assert!(pasta.join("python").is_dir(), "{nome}");
        }
    }

    #[test]
    fn desinstalar_reconhece_a_pasta_pelo_bin() {
        let dados = temporaria("com-bin");
        let pasta = dados.join("app");
        instalado(&dados, &pasta);
        std::fs::remove_file(pasta.join("manifesto-0.4.0.json")).unwrap();
        std::fs::create_dir_all(pasta.join("bin")).unwrap();
        desinstalar_contando(&dados);
        assert!(!pasta.exists());
    }

    #[test]
    fn desinstalar_sem_instalacao_nao_roda_nada() {
        let dados = temporaria("sem");
        std::fs::write(dados.join("jobot.db"), "banco").unwrap();
        assert!(desinstalar_contando(&dados).is_empty());
        assert!(dados.join("jobot.db").is_file());
    }
}
