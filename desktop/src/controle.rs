//! O controle da casca (D206, ADR 0027; T350): o estado do painel, o endereço, Ligar, Parar e
//! Abrir joBot. A casca nunca mostra o painel: o endereço abre no navegador padrão da pessoa.
//! Os comandos, a saúde e o abridor entram por parâmetro: os testes não sobem processo nenhum.

use crate::servidor;
use serde_json::{Value, json};
use std::path::Path;
use std::process::{Command, Stdio};

/// A porta do painel: a da trava (servidor no ar) ou a que o `jobot serve` usaria.
pub fn porta(dados: &Path, env: impl Fn(&str) -> Option<String>) -> u16 {
    servidor::ler_trava(dados)
        .1
        .unwrap_or_else(|| servidor::porta(env))
}

/// O que a página do controle desenha. `no_ar` é a pergunta à `/saude-local` daquela porta.
pub fn estado(porta: u16, no_ar: impl FnOnce(u16) -> bool) -> Value {
    json!({"ligado": no_ar(porta), "endereco": servidor::url_do_painel(porta)})
}

/// O estado com o motivo da falha (o `codigo` de `servidor::Falha`, ou `abrir`), o detalhe e
/// o fim do log, que a página mostra.
pub fn com_falha(mut estado: Value, codigo: &str, detalhe: &str, log: &str) -> Value {
    estado["falha"] = codigo.into();
    estado["detalhe"] = detalhe.into();
    estado["log"] = log.into();
    estado
}

/// Ligar: acha ou sobe o servidor do joBot instalado (`achar` é o `servidor::achar_ou_subir`).
pub fn ligar(
    dados: &Path,
    so: &str,
    achar: impl FnOnce(&Path) -> Result<servidor::Servidor, servidor::Falha>,
) -> Result<servidor::Servidor, servidor::Falha> {
    servidor::jobot_instalado(dados, so)
        .ok_or(servidor::Falha::SemInstalacao)
        .and_then(|jobot| achar(&jobot))
}

/// Se fechar a janela pode parar este servidor (`SUBIU`): a casca o subiu agora, ou a trava
/// estava solta e o `jobot serve` lançado não respondeu a tempo (ele pode terminar de subir
/// depois; o `fechar::ao_fechar` reconfere a trava e o segundo plano). A `Porta` de antes de
/// lançar também entra: com outro programa na porta, ninguém prende a trava e nada é parado.
pub fn subiu(trava_solta: bool, ligar: &Result<servidor::Servidor, servidor::Falha>) -> bool {
    match ligar {
        Ok(achado) => achado.subiu,
        Err(servidor::Falha::SemResposta(_) | servidor::Falha::Porta(_)) => trava_solta,
        Err(_) => false,
    }
}

/// Parar: `jobot sair` pelo joBot instalado (`sair` espera o fim) e o estado depois (`agora`).
/// Painel ainda no ar é a falha `parar`: o `sair` não encerrou (prazo de 10 s ou permissão).
pub fn parar(
    dados: &Path,
    so: &str,
    sair: impl FnOnce(&Path),
    agora: impl FnOnce() -> Value,
) -> Value {
    if let Some(jobot) = servidor::jobot_instalado(dados, so) {
        sair(&jobot);
    }
    let estado = agora();
    if estado["ligado"] == true {
        return com_falha(estado, "parar", "", &servidor::fim_do_log(dados));
    }
    estado
}

/// Dentro de uma distrobox, a mesma regra do `sistema/caso.py`: há `CONTAINER_ID`.
pub fn em_distrobox(env: impl Fn(&str) -> Option<String>) -> bool {
    env("CONTAINER_ID").is_some_and(|nome| !nome.is_empty())
}

/// O programa e os argumentos que abrem `endereco` no navegador padrão do sistema. Nunca o
/// navegador do Playwright e nunca `--app`: quem escolhe o navegador é o sistema da pessoa.
pub fn abridor(so: &str, distrobox: bool, endereco: &str) -> (&'static str, Vec<String>) {
    let endereco = endereco.to_string();
    match so {
        "macos" => ("open", vec![endereco]),
        // o mesmo ShellExecute do navegador padrão, sem `cmd` (que leria `&` e `^` do endereço)
        "windows" => (
            "rundll32.exe",
            vec!["url.dll,FileProtocolHandler".into(), endereco],
        ),
        // a distrobox não tem navegador: quem abre é o `xdg-open` do sistema de fora
        _ if distrobox => ("distrobox-host-exec", vec!["xdg-open".into(), endereco]),
        _ => ("xdg-open", vec![endereco]),
    }
}

/// O ambiente que o abridor não leva para o navegador dentro de um AppImage (há `APPDIR`): o
/// AppRun aponta `GTK_PATH`, `GIO_EXTRA_MODULES`, `XDG_DATA_DIRS`, `PATH` e outras para dentro
/// dele, e um navegador que nasce do Abrir joBot seguiria vivo com a casca fechada (D207.1).
/// Lista de caminhos perde só os pedaços de dentro (`Some`); o resto que aponta para lá sai.
pub fn fora_do_appimage(vars: &[(String, String)]) -> Vec<(String, Option<String>)> {
    let Some((_, appdir)) = vars.iter().find(|(k, v)| k == "APPDIR" && !v.is_empty()) else {
        return Vec::new();
    };
    vars.iter()
        .filter_map(|(k, v)| {
            let partes: Vec<&str> = v.split(':').collect();
            let fora: Vec<&str> = partes
                .iter()
                .copied()
                .filter(|p| !Path::new(p).starts_with(appdir))
                .collect();
            if fora.len() == partes.len() {
                return None; // nada aponta para dentro
            }
            Some((k.clone(), (!fora.is_empty()).then(|| fora.join(":"))))
        })
        .collect()
}

/// O abridor pronto para rodar, com o ambiente da casca (`vars`): sem o ambiente do Python e
/// sem o do AppImage (o `LD_LIBRARY_PATH` e os módulos dele chegariam ao navegador), fora da
/// pasta do AppImage e sem entrada nem saída.
pub fn comando_abridor(so: &str, vars: &[(String, String)], endereco: &str) -> Command {
    let env = |nome: &str| vars.iter().find(|(k, _)| k == nome).map(|(_, v)| v.clone());
    let (programa, args) = abridor(so, em_distrobox(env), endereco);
    let mut comando = Command::new(programa);
    let fora = fora_do_appimage(vars);
    if !fora.is_empty() {
        // o AppRun deixa a casca em `$APPDIR/usr`: o navegador nasce na casa da pessoa (T355)
        comando.current_dir(env("HOME").filter(|c| !c.is_empty()).unwrap_or("/".into()));
    }
    for (nome, valor) in fora {
        match valor {
            Some(valor) => comando.env(nome, valor),
            None => comando.env_remove(nome),
        };
    }
    servidor::sem_python_de_fora(&mut comando)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    comando
}

/// Abrir joBot: só com o painel no ar; `rodar` lança o abridor (sem esperar o navegador).
pub fn abrir(
    porta: u16,
    no_ar: impl FnOnce(u16) -> bool,
    abridor: impl FnOnce(&str) -> Command,
    rodar: impl FnOnce(Command) -> std::io::Result<()>,
) -> Value {
    let estado = estado(porta, no_ar);
    if estado["ligado"] != true {
        return estado;
    }
    match rodar(abridor(&servidor::url_do_painel(porta))) {
        Ok(()) => estado,
        Err(erro) => com_falha(estado, "abrir", &erro.to_string(), ""),
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use std::cell::RefCell;
    use std::ffi::OsStr;
    use std::path::PathBuf;

    fn temporaria(nome: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("jobot-controle-{nome}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&p);
        std::fs::create_dir_all(&p).unwrap();
        p
    }

    fn sem_env(_: &str) -> Option<String> {
        None
    }

    /// `<dados>/instalacao.json` apontando um venv com o `jobot` de verdade (arquivo).
    fn instalado(dados: &Path) -> PathBuf {
        let venv = dados.join("venv");
        let jobot = servidor::jobot_do_venv(&venv, "linux");
        std::fs::create_dir_all(jobot.parent().unwrap()).unwrap();
        std::fs::write(&jobot, "").unwrap();
        let instalacao = json!({"canal": "casca", "venv": venv.to_string_lossy()});
        std::fs::write(dados.join("instalacao.json"), instalacao.to_string()).unwrap();
        jobot
    }

    #[test]
    fn estado_ligado_e_parado_com_o_endereco() {
        let perguntas = RefCell::new(Vec::new());
        let ligado = estado(47615, |p| {
            perguntas.borrow_mut().push(p);
            true
        });
        assert_eq!(
            ligado,
            json!({"ligado": true, "endereco": "http://127.0.0.1:47615/"})
        );
        assert_eq!(perguntas.into_inner(), [47615]);
        let parado = estado(8000, |_| false);
        assert_eq!(
            parado,
            json!({"ligado": false, "endereco": "http://127.0.0.1:8000/"})
        );
    }

    #[test]
    fn porta_da_trava_ou_a_do_jobot_serve() {
        let dados = temporaria("porta");
        assert_eq!(porta(&dados, sem_env), servidor::PORTA_PADRAO);
        let env = |nome: &str| (nome == "JOBOT_PORTA").then(|| "8123".to_string());
        assert_eq!(porta(&dados, env), 8123);
        std::fs::write(dados.join("jobot.lock"), "42\n47999\n").unwrap();
        let dono = std::fs::File::open(dados.join("jobot.lock")).unwrap();
        servidor::prender_como_o_python(&dono);
        assert_eq!(porta(&dados, env), 47999);
        drop(dono);
        let _ = std::fs::remove_dir_all(&dados);
    }

    #[test]
    fn falha_leva_motivo_detalhe_e_log() {
        let e = com_falha(estado(8000, |_| false), "porta", "8000", "linha");
        assert_eq!(e["ligado"], false);
        assert_eq!(e["falha"], "porta");
        assert_eq!(e["detalhe"], "8000");
        assert_eq!(e["log"], "linha");
    }

    #[test]
    fn ligar_sem_instalacao_nao_sobe_nada() {
        let dados = temporaria("ligar-sem");
        let chamou = RefCell::new(false);
        let r = ligar(&dados, "linux", |_| {
            *chamou.borrow_mut() = true;
            Ok(servidor::Servidor {
                porta: 1,
                subiu: true,
            })
        });
        assert_eq!(r, Err(servidor::Falha::SemInstalacao));
        assert!(!chamou.into_inner());
        let _ = std::fs::remove_dir_all(&dados);
    }

    #[test]
    fn ligar_acha_ou_sobe_pelo_jobot_instalado() {
        let dados = temporaria("ligar");
        let jobot = instalado(&dados);
        let visto = RefCell::new(None);
        let r = ligar(&dados, "linux", |j| {
            *visto.borrow_mut() = Some(j.to_path_buf());
            Err(servidor::Falha::Porta(47615))
        });
        assert_eq!(r, Err(servidor::Falha::Porta(47615)));
        assert_eq!(visto.into_inner(), Some(jobot));
        let _ = std::fs::remove_dir_all(&dados);
    }

    #[test]
    fn parar_roda_jobot_sair_so_com_instalacao() {
        let dados = temporaria("parar");
        let chamadas = RefCell::new(Vec::new());
        let parado = || estado(8000, |_| false);
        let e = parar(
            &dados,
            "linux",
            |j| chamadas.borrow_mut().push(j.to_path_buf()),
            parado,
        );
        assert!(chamadas.borrow().is_empty());
        assert!(e.get("falha").is_none());
        let jobot = instalado(&dados);
        let e = parar(
            &dados,
            "linux",
            |j| chamadas.borrow_mut().push(j.to_path_buf()),
            parado,
        );
        assert_eq!(chamadas.into_inner(), [jobot]);
        assert_eq!(e["ligado"], false);
        assert!(e.get("falha").is_none());
        let _ = std::fs::remove_dir_all(&dados);
    }

    #[test]
    fn parar_que_nao_parou_diz_por_que() {
        let dados = temporaria("parar-falha");
        instalado(&dados);
        let e = parar(&dados, "linux", |_| {}, || estado(8000, |_| true));
        assert_eq!(e["ligado"], true);
        assert_eq!(e["falha"], "parar");
        let _ = std::fs::remove_dir_all(&dados);
    }

    #[test]
    fn subiu_tambem_quando_o_serve_lancado_nao_respondeu_a_tempo() {
        use servidor::{Falha, Servidor};
        let achado = |subiu| Ok(Servidor { porta: 1, subiu });
        assert!(subiu(true, &achado(true)));
        assert!(!subiu(true, &achado(false)));
        for falha in [Falha::SemResposta(1), Falha::Porta(1)] {
            assert!(subiu(true, &Err(falha)));
        }
        // a trava já estava presa: o servidor é de outro (segundo plano, `jobot abrir`)
        assert!(!subiu(false, &Err(Falha::SemResposta(1))));
        for falha in [
            Falha::SemInstalacao,
            Falha::Captura,
            Falha::Saiu(Some(1)),
            Falha::NaoSubiu("x".into()),
        ] {
            assert!(!subiu(true, &Err(falha)));
        }
    }

    #[test]
    fn abridor_do_navegador_padrao_por_sistema() {
        let e = "http://127.0.0.1:47615/";
        let casos = [
            ("linux", false, "xdg-open", vec![e]),
            ("linux", true, "distrobox-host-exec", vec!["xdg-open", e]),
            ("macos", false, "open", vec![e]),
            ("macos", true, "open", vec![e]),
            (
                "windows",
                false,
                "rundll32.exe",
                vec!["url.dll,FileProtocolHandler", e],
            ),
        ];
        for (so, distrobox, programa, args) in casos {
            let (p, a) = abridor(so, distrobox, e);
            assert_eq!(
                (p, a),
                (programa, args.iter().map(|s| s.to_string()).collect())
            );
        }
    }

    #[test]
    fn abridor_nunca_e_o_navegador_do_playwright_nem_modo_app() {
        for so in ["linux", "macos", "windows"] {
            for distrobox in [false, true] {
                let (p, a) = abridor(so, distrobox, "http://127.0.0.1:1/");
                let tudo = format!("{p} {}", a.join(" ")).to_lowercase();
                for proibido in ["--app", "chrom", "playwright", "firefox", "msedge"] {
                    assert!(!tudo.contains(proibido), "{so} {distrobox}: {tudo}");
                }
            }
        }
    }

    #[test]
    fn distrobox_pelo_container_id() {
        assert!(em_distrobox(
            |n| (n == "CONTAINER_ID").then(|| "fedora".into())
        ));
        assert!(!em_distrobox(|n| (n == "CONTAINER_ID").then(String::new)));
        assert!(!em_distrobox(sem_env));
    }

    fn vars(pares: &[(&str, &str)]) -> Vec<(String, String)> {
        pares
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect()
    }

    #[test]
    fn fora_do_appimage_tira_o_que_aponta_para_dentro() {
        let d = "/tmp/.mount_jobotX";
        let ambiente = vars(&[
            ("APPDIR", d),
            ("GTK_PATH", "/tmp/.mount_jobotX/usr/lib/gtk-3.0"),
            ("PATH", "/tmp/.mount_jobotX/usr/bin:/usr/local/bin:/usr/bin"),
            ("XDG_DATA_DIRS", "/tmp/.mount_jobotX/usr/share"),
            // o AppRun monta "$APPDIR/...:$ORIGINAL"; sem original, sobra "" (desliga o sistema)
            (
                "GST_PLUGIN_SYSTEM_PATH",
                "/tmp/.mount_jobotX/usr/lib/gstreamer-1.0:",
            ),
            ("QT_PLUGIN_PATH", "/tmp/.mount_jobotX/usr/qt::/usr/lib/qt"),
            ("HOME", "/home/p"),
            ("VIZINHO", "/tmp/.mount_jobotXY/x"), // outra pasta, só o começo igual
        ]);
        let mut fora = fora_do_appimage(&ambiente);
        fora.sort();
        assert_eq!(
            fora,
            [
                ("APPDIR".to_string(), None),
                ("GST_PLUGIN_SYSTEM_PATH".into(), None),
                ("GTK_PATH".into(), None),
                ("PATH".into(), Some("/usr/local/bin:/usr/bin".into())),
                ("QT_PLUGIN_PATH".into(), Some("/usr/lib/qt".into())),
                ("XDG_DATA_DIRS".into(), None),
            ]
        );
        assert!(fora_do_appimage(&vars(&[("GTK_PATH", "/x"), ("APPDIR", "")])).is_empty());
    }

    #[test]
    fn comando_abridor_sem_o_ambiente_do_appimage() {
        let ambiente = vars(&[
            ("CONTAINER_ID", "fedora"),
            ("APPDIR", "/tmp/.mount_j"),
            ("GIO_EXTRA_MODULES", "/tmp/.mount_j/usr/lib/gio"),
            ("HOME", "/home/p"),
        ]);
        let c = comando_abridor("linux", &ambiente, "http://127.0.0.1:47615/");
        // o AppRun deixa a casca em `$APPDIR/usr`: o navegador nasce na casa da pessoa (T355)
        assert_eq!(c.get_current_dir(), Some(Path::new("/home/p")));
        // e o `PWD` herdado diz a mesma pasta, para um abridor que não seja shell
        assert!(
            c.get_envs()
                .any(|(k, v)| k == "PWD" && v == Some(OsStr::new("/home/p")))
        );
        assert_eq!(c.get_program(), "distrobox-host-exec");
        assert_eq!(
            c.get_args().collect::<Vec<_>>(),
            ["xdg-open", "http://127.0.0.1:47615/"]
        );
        let fora: Vec<_> = c
            .get_envs()
            .filter(|(_, v)| v.is_none())
            .map(|(k, _)| k)
            .collect();
        assert_eq!(
            fora,
            [
                "APPDIR",
                "GIO_EXTRA_MODULES",
                "LD_LIBRARY_PATH",
                "PYTHONHOME",
                "PYTHONPATH"
            ]
        );
    }

    #[test]
    fn abridor_fora_do_appimage_nao_muda_a_pasta() {
        let c = comando_abridor("linux", &vars(&[("HOME", "/home/p")]), "u");
        assert_eq!(c.get_current_dir(), None);
        // sem a casa: a raiz, que nunca está dentro do AppImage
        let c = comando_abridor("linux", &vars(&[("APPDIR", "/tmp/.mount_j")]), "u");
        assert_eq!(c.get_current_dir(), Some(Path::new("/")));
        assert!(
            c.get_envs()
                .any(|(k, v)| k == "PWD" && v == Some(OsStr::new("/")))
        );
    }

    #[test]
    fn abrir_so_com_o_painel_no_ar() {
        let rodou = RefCell::new(Vec::new());
        let abridor_falso = |e: &str| Command::new(e);
        let parado = abrir(
            8000,
            |_| false,
            abridor_falso,
            |c| {
                rodou.borrow_mut().push(c.get_program().to_owned());
                Ok(())
            },
        );
        assert_eq!(parado["ligado"], false);
        assert!(rodou.borrow().is_empty());
        let ligado = abrir(
            8000,
            |_| true,
            abridor_falso,
            |c| {
                rodou.borrow_mut().push(c.get_program().to_owned());
                Ok(())
            },
        );
        assert_eq!(ligado["ligado"], true);
        assert!(ligado.get("falha").is_none());
        assert_eq!(rodou.into_inner(), ["http://127.0.0.1:8000/"]);
    }

    #[test]
    fn abrir_que_falha_diz_por_que() {
        let e = abrir(
            8000,
            |_| true,
            |e| Command::new(e),
            |_| Err(std::io::Error::other("sem xdg-open")),
        );
        assert_eq!(e["falha"], "abrir");
        assert_eq!(e["detalhe"], "sem xdg-open");
        assert_eq!(e["ligado"], true);
    }
}
