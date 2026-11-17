//! Instalação pela casca, sem rede (desenho 5.2 e 6.2; D173, D174, D181). Confere o
//! `manifesto.json` pelo sha256 gravado no build e cada arquivo dos recursos pelo manifesto,
//! prepara o Python e o venv com o `uv` dos recursos, instala o navegador se marcado, prova o
//! `jobot --version` e só então grava o `instalacao.json`. Falhou ou foi cancelada: o que a
//! instalação criou sai e o `instalacao.json` não é gravado.
//!
//! Recursos (`desktop/recursos/`, D181): `manifesto.json`, `bin/uv` (`bin/uv.exe`),
//! `python/<tag>/cpython-<versão>+<tag>-<alvo>-install_only_stripped.tar.gz` (o espelho que o
//! `uv python install --mirror` lê), `restricoes.txt`, `wheels/*.whl` e
//! `chromium-<alvo>.tar.gz`.

#![allow(dead_code, unused_imports)] // esqueleto: a implementação vem no commit seguinte

use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::fmt::Write as _;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::AtomicBool;

pub const MANIFESTO: &str = "manifesto.json";
pub const INSTALACAO: &str = "instalacao.json";

#[derive(Debug, Clone, PartialEq)]
pub struct Entrada {
    pub nome: String,
    pub tamanho: u64,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Manifesto {
    pub versao: String,
    pub arquivos: Vec<Entrada>,
}

/// Por que a instalação parou; o `codigo` vira o motivo da tela de falha.
#[derive(Debug, PartialEq)]
pub enum Erro {
    Arquivo(String),
    Espaco,
    Prova(String),
    Cancelado,
    Outro(String),
}

impl Erro {
    pub fn codigo(&self) -> &'static str {
        match self {
            Erro::Arquivo(_) => "arquivo",
            Erro::Espaco => "espaco",
            Erro::Prova(_) => "prova",
            Erro::Cancelado => "cancelado",
            Erro::Outro(_) => "outro",
        }
    }

    pub fn detalhe(&self) -> String {
        match self {
            Erro::Arquivo(texto) | Erro::Prova(texto) | Erro::Outro(texto) => texto.clone(),
            _ => String::new(),
        }
    }
}

impl From<io::Error> for Erro {
    fn from(erro: io::Error) -> Self {
        if erro.kind() == io::ErrorKind::StorageFull {
            Erro::Espaco
        } else {
            Erro::Outro(erro.to_string())
        }
    }
}

/// O que um comando devolveu: o código, o stdout inteiro e o stderr.
#[derive(Debug, Default)]
pub struct Saida {
    pub codigo: Option<i32>,
    pub saida: String,
    pub erro: String,
}

/// Quem roda os comandos: recebe o comando e um aviso por linha do stdout.
pub type Rodar<'a> = dyn FnMut(Command, &mut dyn FnMut(&str)) -> Result<Saida, Erro> + 'a;

pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().fold(String::new(), |mut s, b| {
        let _ = write!(s, "{b:02x}");
        s
    })
}

fn e_hex(texto: &str) -> bool {
    texto.len() == 64
        && texto
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

/// Caminho relativo com `/`, sem `..`, `.`, partes vazias, `\` nem `:`.
fn nome_valido(nome: &str) -> bool {
    !nome.contains(['\\', ':'])
        && nome
            .split('/')
            .all(|parte| !parte.is_empty() && parte != "." && parte != "..")
}

fn e_chromium(nome: &str) -> bool {
    nome.starts_with("chromium-") && nome.ends_with(".tar.gz") && !nome.contains('/')
}

pub fn ler_manifesto(bytes: &[u8]) -> Result<Manifesto, Erro> {
    let _ = bytes;
    Err(Erro::Arquivo(MANIFESTO.into()))
}

/// Uma linha JSON do `jobot ferramentas baixar navegador` (T330).
#[derive(Debug, PartialEq)]
pub enum Linha {
    Progresso { feito: u64, total: Option<u64> },
    Fim(bool),
}

pub fn ler_linha(linha: &str) -> Option<Linha> {
    let _ = linha;
    None
}

/// A pasta da casca (desenho 6.2): `<dados>/app` no Windows e no Mac (e com `JOBOT_DADOS`);
/// no Linux a vizinha `jobot-app` da pasta de dados (`~/.local/share/jobot-app`).
pub fn pasta_da_casca(env: impl Fn(&str) -> Option<String>, so: &str) -> PathBuf {
    let _ = (env, so);
    PathBuf::new()
}

/// Para a tela: se os recursos estão completos e quanto ocupam (o navegador à parte).
pub fn estado(recursos: &Path, sha_manifesto: Option<&str>, versao: &str) -> Value {
    let _ = (recursos, sha_manifesto, versao);
    json!({})
}

/// Escrita atômica (`.tmp` na mesma pasta, `fsync` e troca), 0600 no Linux e no Mac.
pub fn gravar_atomico(destino: &Path, conteudo: &[u8]) -> io::Result<()> {
    fs::write(destino, conteudo)
}

/// Roda o comando sem janela nem entrada, avisa cada linha do stdout e o mata se `cancelado`.
pub fn rodar(
    comando: Command,
    cancelado: &AtomicBool,
    linha: &mut dyn FnMut(&str),
) -> Result<Saida, Erro> {
    let _ = (comando, cancelado, linha);
    Ok(Saida::default())
}

/// As pastas e a versão de uma instalação.
pub struct Instalador<'a> {
    pub recursos: &'a Path,
    pub pasta: &'a Path,
    pub dados: &'a Path,
    pub so: &'a str,
    pub versao: &'a str,
}

impl Instalador<'_> {
    fn exe(&self, nome: &str) -> String {
        if self.so == "windows" {
            format!("{nome}.exe")
        } else {
            nome.to_string()
        }
    }

    pub fn uv(&self) -> PathBuf {
        self.pasta.join("bin").join(self.exe("uv"))
    }

    pub fn venv(&self) -> PathBuf {
        self.pasta
            .join("venvs")
            .join(format!("venv-{}", self.versao))
    }

    /// Confere, instala e grava; com erro, desfaz o que criou.
    pub fn instalar(
        &self,
        sha_manifesto: &str,
        navegador: bool,
        cancelado: &AtomicBool,
        rodar: &mut Rodar,
        progresso: &mut dyn FnMut(Value),
    ) -> Result<(), Erro> {
        let _ = (sha_manifesto, navegador, cancelado, rodar, progresso);
        Ok(())
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use std::cell::RefCell;
    use std::collections::HashMap;
    use std::rc::Rc;
    use std::sync::atomic::Ordering;

    const VERSAO: &str = "0.3.0";
    const PYTHON: &str = "python/20260807/cpython-3.14.7+20260807-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz";
    const CHROMIUM: &str = "chromium-x86_64-unknown-linux-gnu.tar.gz";

    fn temporaria(nome: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("jobot-instalar-{nome}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&p);
        fs::create_dir_all(&p).unwrap();
        p
    }

    fn sha(bytes: &[u8]) -> String {
        hex(&Sha256::digest(bytes))
    }

    const ARQUIVOS: [(&str, &str); 5] = [
        ("bin/uv", "uv falso"),
        (PYTHON, "python falso"),
        ("restricoes.txt", "jobot==0.3.0 --hash=sha256:00\n"),
        ("wheels/jobot-0.3.0-py3-none-any.whl", "roda falsa"),
        (CHROMIUM, "chromium falso"),
    ];

    /// Recursos de mentira com o manifesto certo; devolve o sha256 do manifesto.
    fn montar_recursos(raiz: &Path, versao: &str) -> String {
        let mut lista = Vec::new();
        for (nome, conteudo) in ARQUIVOS {
            let caminho = raiz.join(nome);
            fs::create_dir_all(caminho.parent().unwrap()).unwrap();
            fs::write(&caminho, conteudo).unwrap();
            lista.push(json!({"nome": nome, "tamanho": conteudo.len(), "sha256": sha(conteudo.as_bytes())}));
        }
        let bruto = serde_json::to_vec(&json!({"versao": versao, "arquivos": lista})).unwrap();
        fs::write(raiz.join(MANIFESTO), &bruto).unwrap();
        sha(&bruto)
    }

    struct Cenario {
        recursos: PathBuf,
        pasta: PathBuf,
        dados: PathBuf,
        sha: String,
    }

    fn cenario(nome: &str) -> Cenario {
        let raiz = temporaria(nome);
        let recursos = raiz.join("recursos");
        let sha = montar_recursos(&recursos, VERSAO);
        Cenario {
            recursos,
            pasta: raiz.join("casca"),
            dados: raiz.join("dados"),
            sha,
        }
    }

    impl Cenario {
        fn instalador(&self) -> Instalador<'_> {
            Instalador {
                recursos: &self.recursos,
                pasta: &self.pasta,
                dados: &self.dados,
                so: "linux",
                versao: VERSAO,
            }
        }
    }

    type Feitos = Rc<RefCell<Vec<(Vec<String>, HashMap<String, Option<String>>)>>>;

    /// Executor falso: grava cada comando e imita o `uv` e o `jobot` (`falhar_em` faz o comando
    /// com esse argumento sair com 1; `versao` é o que o `jobot --version` responde).
    #[allow(clippy::type_complexity)] // o executor é um impl FnMut: não cabe num type
    fn falso(
        pasta: PathBuf,
        versao: &'static str,
        falhar_em: Option<&'static str>,
    ) -> (
        Feitos,
        impl FnMut(Command, &mut dyn FnMut(&str)) -> Result<Saida, Erro>,
    ) {
        let feitos: Feitos = Rc::default();
        let gravados = feitos.clone();
        let executor = move |comando: Command, linha: &mut dyn FnMut(&str)| {
            let mut argv = vec![comando.get_program().to_string_lossy().into_owned()];
            argv.extend(comando.get_args().map(|a| a.to_string_lossy().into_owned()));
            let ambiente = comando
                .get_envs()
                .map(|(k, v)| {
                    let valor = v.map(|v| v.to_string_lossy().into_owned());
                    (k.to_string_lossy().into_owned(), valor)
                })
                .collect();
            gravados.borrow_mut().push((argv.clone(), ambiente));
            if falhar_em.is_some_and(|f| argv.iter().any(|a| a == f)) {
                return Ok(Saida {
                    codigo: Some(1),
                    erro: "deu errado".into(),
                    ..Saida::default()
                });
            }
            let mut saida = String::new();
            match argv.get(1).map(String::as_str) {
                Some("python") => {
                    let python = pasta.join("python");
                    let real = python.join("cpython-3.14.7-linux-x86_64-gnu");
                    fs::create_dir_all(real.join("bin")).unwrap();
                    fs::write(real.join("bin").join("python3"), "").unwrap();
                    #[cfg(unix)]
                    std::os::unix::fs::symlink(&real, python.join("cpython-3.14-linux-x86_64-gnu"))
                        .unwrap();
                }
                Some("venv") => fs::create_dir_all(argv.last().unwrap()).unwrap(),
                Some("ferramentas") => {
                    linha(r#"{"etapa":"navegador","feito":5,"total":14}"#);
                    linha(r#"{"fim":"pronto"}"#);
                }
                Some("--version") => saida = format!("{versao}\n"),
                _ => {}
            }
            Ok(Saida {
                codigo: Some(0),
                saida,
                erro: String::new(),
            })
        };
        (feitos, executor)
    }

    fn v(partes: &[&str]) -> Vec<String> {
        partes.iter().map(|s| s.to_string()).collect()
    }

    fn texto(p: &Path) -> String {
        p.to_string_lossy().into_owned()
    }

    fn argvs(feitos: &Feitos) -> Vec<Vec<String>> {
        feitos.borrow().iter().map(|(a, _)| a.clone()).collect()
    }

    #[test]
    fn manifesto_com_sha_diferente_recusa_antes_de_copiar_ou_chamar_o_uv() {
        let c = cenario("sha-manifesto");
        let (feitos, mut executor) = falso(c.pasta.clone(), "jobot 0.3.0", None);
        let errado = sha(b"outro");
        let r = c.instalador().instalar(
            &errado,
            true,
            &AtomicBool::new(false),
            &mut executor,
            &mut |_| {},
        );
        assert_eq!(r, Err(Erro::Arquivo(MANIFESTO.into())));
        assert!(feitos.borrow().is_empty());
        assert!(!c.pasta.exists());
        assert!(!c.dados.join(INSTALACAO).exists());
    }

    #[test]
    fn arquivo_diferente_do_manifesto_recusa_antes_de_copiar_ou_chamar_o_uv() {
        let c = cenario("arquivo-diferente");
        fs::write(
            c.recursos.join("wheels/jobot-0.3.0-py3-none-any.whl"),
            "roda trocada",
        )
        .unwrap();
        let (feitos, mut executor) = falso(c.pasta.clone(), "jobot 0.3.0", None);
        let r = c.instalador().instalar(
            &c.sha,
            true,
            &AtomicBool::new(false),
            &mut executor,
            &mut |_| {},
        );
        assert_eq!(
            r,
            Err(Erro::Arquivo("wheels/jobot-0.3.0-py3-none-any.whl".into()))
        );
        assert!(feitos.borrow().is_empty());
        assert!(!c.pasta.exists());
    }

    #[test]
    fn arquivo_que_falta_ou_que_sobra_recusa() {
        let c = cenario("falta");
        fs::remove_file(c.recursos.join("restricoes.txt")).unwrap();
        let (feitos, mut executor) = falso(c.pasta.clone(), "jobot 0.3.0", None);
        let parar = AtomicBool::new(false);
        let r = c
            .instalador()
            .instalar(&c.sha, true, &parar, &mut executor, &mut |_| {});
        assert_eq!(r, Err(Erro::Arquivo("restricoes.txt".into())));
        let c = cenario("sobra");
        fs::write(c.recursos.join("wheels/intrusa-1.0-py3-none-any.whl"), "x").unwrap();
        let r = c
            .instalador()
            .instalar(&c.sha, true, &parar, &mut executor, &mut |_| {});
        assert_eq!(
            r,
            Err(Erro::Arquivo("wheels/intrusa-1.0-py3-none-any.whl".into()))
        );
        assert!(feitos.borrow().is_empty());
    }

    #[test]
    fn manifesto_de_outra_versao_recusa() {
        let c = cenario("outra-versao");
        let sha_outro = montar_recursos(&c.recursos, "0.2.0");
        let (feitos, mut executor) = falso(c.pasta.clone(), "jobot 0.3.0", None);
        let parar = AtomicBool::new(false);
        let r = c
            .instalador()
            .instalar(&sha_outro, true, &parar, &mut executor, &mut |_| {});
        assert_eq!(r, Err(Erro::Arquivo(MANIFESTO.into())));
        assert!(feitos.borrow().is_empty());
    }

    #[test]
    fn manifesto_recusa_nome_fora_da_pasta_e_sha_torto() {
        let entrada = |nome: &str, sha: &str| {
            let m = json!({"versao": VERSAO, "arquivos": [{"nome": nome, "tamanho": 1, "sha256": sha}]});
            ler_manifesto(&serde_json::to_vec(&m).unwrap())
        };
        let bom = "a".repeat(64);
        assert!(entrada("wheels/a.whl", &bom).is_ok());
        for nome in ["../fora", "/abs", "a//b", "c:/x", "a\\b", "./a", MANIFESTO] {
            assert!(entrada(nome, &bom).is_err(), "{nome}");
        }
        for torto in ["A".repeat(64), "a".repeat(63), "g".repeat(64)] {
            assert!(entrada("x", &torto).is_err(), "{torto}");
        }
        assert!(ler_manifesto(b"{").is_err());
    }

    #[test]
    fn instala_com_os_comandos_montados_e_grava_depois_da_prova() {
        let c = cenario("certo");
        let (feitos, mut executor) = falso(c.pasta.clone(), "jobot 0.3.0", None);
        let mut avisos = Vec::new();
        let r = c.instalador().instalar(
            &c.sha,
            true,
            &AtomicBool::new(false),
            &mut executor,
            &mut |v| avisos.push(v),
        );
        assert_eq!(r, Ok(()));
        let uv = texto(&c.pasta.join("bin").join("uv"));
        let venv = c.pasta.join("venvs").join("venv-0.3.0");
        let jobot = texto(&venv.join("bin").join("jobot"));
        let interpretador = c
            .pasta
            .join("python")
            .join("cpython-3.14.7-linux-x86_64-gnu")
            .join("bin")
            .join("python3");
        let espelho = format!("file://{}", texto(&c.recursos.join("python")));
        let chromium = c.recursos.join(CHROMIUM);
        let esperado = vec![
            v(&[
                &uv, "python", "install", "--no-bin", "--mirror", &espelho, "3.14.7",
            ]),
            v(&[
                &uv,
                "venv",
                "--offline",
                "--python",
                &texto(&interpretador),
                &texto(&venv),
            ]),
            v(&[
                &uv,
                "pip",
                "install",
                "--offline",
                "--python",
                &texto(&venv.join("bin").join("python")),
                "--no-index",
                "--find-links",
                &texto(&c.recursos.join("wheels")),
                "--require-hashes",
                "-r",
                &texto(&c.recursos.join("restricoes.txt")),
            ]),
            v(&[
                &jobot,
                "ferramentas",
                "baixar",
                "navegador",
                "--arquivo",
                &texto(&chromium),
                "--sha256",
                &sha(b"chromium falso"),
            ]),
            v(&[&jobot, "--version"]),
        ];
        assert_eq!(argvs(&feitos), esperado);
        // o uv roda offline, com as pastas da casca, sem índice nem espelho de fora
        for (argv, ambiente) in feitos.borrow().iter().take(3) {
            let valor = |k: &str| ambiente.get(k).cloned().flatten();
            assert_eq!(valor("UV_OFFLINE").as_deref(), Some("1"), "{argv:?}");
            assert_eq!(valor("UV_NO_CONFIG").as_deref(), Some("1"));
            assert_eq!(valor("UV_CACHE_DIR"), Some(texto(&c.pasta.join("cache"))));
            assert_eq!(
                valor("UV_PYTHON_INSTALL_DIR"),
                Some(texto(&c.pasta.join("python")))
            );
            for fora in [
                "UV_INDEX_URL",
                "UV_DEFAULT_INDEX",
                "UV_PYTHON_INSTALL_MIRROR",
            ] {
                assert_eq!(ambiente.get(fora), Some(&None), "{fora}");
            }
        }
        assert!(argvs(&feitos).concat().iter().all(|a| !a.contains("http")));
        // o uv copiado para a pasta da casca; o atalho cpython-3.14 tirado antes do venv
        assert_eq!(
            fs::read(c.pasta.join("bin").join("uv")).unwrap(),
            b"uv falso"
        );
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let modo = fs::metadata(c.pasta.join("bin").join("uv"))
                .unwrap()
                .permissions()
                .mode();
            assert_eq!(modo & 0o755, 0o755);
            let atalho = c.pasta.join("python").join("cpython-3.14-linux-x86_64-gnu");
            assert!(atalho.symlink_metadata().is_err());
        }
        // gravados depois da prova
        let manifesto = c.pasta.join("manifesto-0.3.0.json");
        assert_eq!(
            fs::read(&manifesto).unwrap(),
            fs::read(c.recursos.join(MANIFESTO)).unwrap()
        );
        let instalacao: Value =
            serde_json::from_slice(&fs::read(c.dados.join(INSTALACAO)).unwrap()).unwrap();
        assert_eq!(
            instalacao,
            json!({
                "canal": "casca",
                "pasta": texto(&c.pasta),
                "uv": uv,
                "venv": texto(&venv),
                "anterior": null,
                "manifesto": texto(&manifesto),
            })
        );
        // as etapas, em ordem, e o progresso do navegador lido das linhas JSON
        let mut etapas: Vec<&str> = avisos.iter().filter_map(|v| v["etapa"].as_str()).collect();
        etapas.dedup();
        assert_eq!(etapas, ["conferir", "python", "jobot", "navegador"]);
        assert!(avisos.contains(&json!({"etapa": "navegador", "feito": 5, "total": 14})));
        let total: u64 = ARQUIVOS.iter().map(|(_, c)| c.len() as u64).sum();
        assert!(avisos.contains(&json!({"etapa": "conferir", "feito": total, "total": total})));
    }

    #[test]
    fn navegador_desmarcado_nao_roda_nem_usa_o_arquivo() {
        let c = cenario("sem-navegador");
        let (feitos, mut executor) = falso(c.pasta.clone(), "jobot 0.3.0", None);
        let r = c.instalador().instalar(
            &c.sha,
            false,
            &AtomicBool::new(false),
            &mut executor,
            &mut |_| {},
        );
        assert_eq!(r, Ok(()));
        let todos = argvs(&feitos);
        assert_eq!(todos.len(), 4, "{todos:?}");
        assert!(
            todos
                .concat()
                .iter()
                .all(|a| !a.contains("chromium") && a != "ferramentas")
        );
        assert!(c.dados.join(INSTALACAO).exists());
    }

    #[test]
    fn prova_que_falha_desfaz_e_nao_grava() {
        let c = cenario("prova");
        let (_, mut executor) = falso(c.pasta.clone(), "jobot 0.2.0", None);
        let r = c.instalador().instalar(
            &c.sha,
            true,
            &AtomicBool::new(false),
            &mut executor,
            &mut |_| {},
        );
        assert_eq!(r, Err(Erro::Prova("jobot 0.2.0".into())));
        assert!(!c.pasta.exists());
        assert!(!c.dados.join(INSTALACAO).exists());
    }

    #[test]
    fn falha_no_meio_apaga_o_venv_e_o_python_novos_e_deixa_o_resto() {
        let c = cenario("falha-pip");
        let guardado = c.pasta.join("guardado.txt");
        fs::create_dir_all(&c.pasta).unwrap();
        fs::write(&guardado, "fica").unwrap();
        let (feitos, mut executor) =
            falso(c.pasta.clone(), "jobot 0.3.0", Some("--require-hashes"));
        let r = c.instalador().instalar(
            &c.sha,
            true,
            &AtomicBool::new(false),
            &mut executor,
            &mut |_| {},
        );
        assert!(
            matches!(&r, Err(Erro::Outro(t)) if t.contains("deu errado")),
            "{r:?}"
        );
        assert_eq!(argvs(&feitos).len(), 3); // parou no pip
        assert!(guardado.exists());
        assert!(!c.instalador().venv().exists());
        assert!(
            !c.pasta
                .join("python")
                .join("cpython-3.14.7-linux-x86_64-gnu")
                .exists()
        );
        assert!(!c.dados.join(INSTALACAO).exists());
        assert!(!c.pasta.join("manifesto-0.3.0.json").exists());
    }

    #[test]
    fn navegador_que_falha_desfaz() {
        let c = cenario("falha-navegador");
        let (_, mut executor) = falso(c.pasta.clone(), "jobot 0.3.0", Some("ferramentas"));
        let r = c.instalador().instalar(
            &c.sha,
            true,
            &AtomicBool::new(false),
            &mut executor,
            &mut |_| {},
        );
        assert!(matches!(r, Err(Erro::Outro(_))), "{r:?}");
        assert!(!c.pasta.exists());
        assert!(!c.dados.join(INSTALACAO).exists());
    }

    #[test]
    fn cancelada_no_meio_apaga_e_nao_grava() {
        let c = cenario("cancelada");
        let parar = AtomicBool::new(false);
        let (feitos, mut base) = falso(c.pasta.clone(), "jobot 0.3.0", None);
        let mut executor = |comando: Command, linha: &mut dyn FnMut(&str)| {
            let pip = comando.get_args().any(|a| a == "pip");
            let r = base(comando, linha);
            if pip {
                parar.store(true, Ordering::SeqCst); // fechou a janela durante o pip
                return Err(Erro::Cancelado);
            }
            r
        };
        let r = c
            .instalador()
            .instalar(&c.sha, true, &parar, &mut executor, &mut |_| {});
        assert_eq!(r, Err(Erro::Cancelado));
        assert_eq!(argvs(&feitos).len(), 3);
        assert!(!c.pasta.exists());
        assert!(!c.dados.join(INSTALACAO).exists());
    }

    #[test]
    fn cancelada_antes_nao_roda_nada() {
        let c = cenario("cancelada-antes");
        let (feitos, mut executor) = falso(c.pasta.clone(), "jobot 0.3.0", None);
        let r = c.instalador().instalar(
            &c.sha,
            true,
            &AtomicBool::new(true),
            &mut executor,
            &mut |_| {},
        );
        assert_eq!(r, Err(Erro::Cancelado));
        assert!(feitos.borrow().is_empty());
        assert!(!c.pasta.exists());
    }

    #[test]
    fn linhas_do_navegador() {
        assert_eq!(
            ler_linha(r#"{"etapa":"navegador","feito":3,"total":9}"#),
            Some(Linha::Progresso {
                feito: 3,
                total: Some(9)
            })
        );
        assert_eq!(
            ler_linha(r#"{"etapa":"navegador","feito":3}"#),
            Some(Linha::Progresso {
                feito: 3,
                total: None
            })
        );
        assert_eq!(ler_linha(r#"{"fim":"pronto"}"#), Some(Linha::Fim(true)));
        assert_eq!(ler_linha(r#"{"fim":"falhou"}"#), Some(Linha::Fim(false)));
        assert_eq!(ler_linha(r#"{"etapa":"outra","feito":1}"#), None);
        assert_eq!(ler_linha("aviso solto"), None);
    }

    #[test]
    fn pasta_da_casca_por_sistema() {
        let env = |pares: &'static [(&'static str, &'static str)]| {
            move |nome: &str| {
                pares
                    .iter()
                    .find(|(k, _)| *k == nome)
                    .map(|(_, v)| v.to_string())
            }
        };
        assert_eq!(
            pasta_da_casca(env(&[("HOME", "/h")]), "linux"),
            PathBuf::from("/h/.local/share/jobot-app")
        );
        assert_eq!(
            pasta_da_casca(env(&[("XDG_DATA_HOME", "/x"), ("HOME", "/h")]), "linux"),
            PathBuf::from("/x/jobot-app")
        );
        assert_eq!(
            pasta_da_casca(env(&[("HOME", "/Users/a")]), "macos"),
            PathBuf::from("/Users/a/Library/Application Support/joBot/app")
        );
        assert_eq!(
            pasta_da_casca(env(&[("LOCALAPPDATA", "C:/L")]), "windows"),
            PathBuf::from("C:/L").join("joBot").join("app")
        );
        assert_eq!(
            pasta_da_casca(env(&[("JOBOT_DADOS", "/d"), ("HOME", "/h")]), "linux"),
            PathBuf::from("/d/app")
        );
    }

    #[test]
    fn estado_diz_se_esta_completo_e_quanto_ocupa() {
        let c = cenario("estado");
        let navegador = "chromium falso".len() as u64;
        let total: u64 = ARQUIVOS.iter().map(|(_, c)| c.len() as u64).sum();
        assert_eq!(
            estado(&c.recursos, Some(c.sha.as_str()), VERSAO),
            json!({"completo": true, "base": total - navegador, "navegador": navegador})
        );
        assert_eq!(
            estado(&c.recursos, None, VERSAO),
            json!({"completo": false})
        );
        assert_eq!(
            estado(&c.recursos, Some(""), VERSAO),
            json!({"completo": false})
        );
        assert_eq!(
            estado(&c.recursos, Some(c.sha.as_str()), "9.9.9"),
            json!({"completo": false})
        );
        let vazia = temporaria("estado-vazio");
        assert_eq!(
            estado(&vazia, Some(c.sha.as_str()), VERSAO),
            json!({"completo": false})
        );
    }

    #[test]
    fn gravar_atomico_troca_o_arquivo_inteiro() {
        let pasta = temporaria("atomico");
        let destino = pasta.join("sub").join("instalacao.json");
        gravar_atomico(&destino, b"um").unwrap();
        gravar_atomico(&destino, b"dois").unwrap();
        assert_eq!(fs::read(&destino).unwrap(), b"dois");
        let sobras: Vec<_> = fs::read_dir(destino.parent().unwrap()).unwrap().collect();
        assert_eq!(sobras.len(), 1); // sem .tmp
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let modo = fs::metadata(&destino).unwrap().permissions().mode();
            assert_eq!(modo & 0o777, 0o600);
        }
    }

    #[cfg(unix)]
    #[test]
    fn rodar_de_verdade_le_linhas_e_codigo() {
        let mut comando = Command::new("/bin/sh");
        comando.args(["-c", "echo um; echo dois; echo ruim >&2; exit 3"]);
        let mut linhas = Vec::new();
        let saida = rodar(comando, &AtomicBool::new(false), &mut |l| {
            linhas.push(l.to_string())
        })
        .unwrap();
        assert_eq!(linhas, ["um", "dois"]);
        assert_eq!(saida.codigo, Some(3));
        assert_eq!(saida.saida, "um\ndois\n");
        assert_eq!(saida.erro, "ruim\n");
    }

    #[cfg(unix)]
    #[test]
    fn rodar_cancelado_mata_o_comando() {
        let mut comando = Command::new("/bin/sh");
        comando.args(["-c", "sleep 30"]);
        let inicio = std::time::Instant::now();
        let r = rodar(comando, &AtomicBool::new(true), &mut |_| {});
        assert!(matches!(r, Err(Erro::Cancelado)), "{r:?}");
        assert!(inicio.elapsed() < std::time::Duration::from_secs(10));
    }
}
