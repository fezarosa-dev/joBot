//! Achar, subir e conferir o joBot (desenho 5.1 e 7.1). A casca só fala HTTP com o painel e
//! chama o executável `jobot` do venv; o ambiente, o relógio e a porta entram por parâmetro.

use std::fs::{File, TryLockError};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::Duration;

/// A de `sistema/instancia.py` (`PORTA_PADRAO`).
pub const PORTA_PADRAO: u16 = 47615;
/// Mesmo prazo e passo do `abrir.py` (`esperar_s` e `_ESPERA_PASSO_S`).
pub const PRAZO: Duration = Duration::from_secs(15);
pub const PASSO: Duration = Duration::from_millis(200);
const LINHAS_DO_LOG: usize = 20;

/// Por que o painel não abriu; o `codigo` vira o `motivo` da `ui/erro.html`.
#[derive(Debug, PartialEq)]
pub enum Falha {
    SemInstalacao,
    Captura,
    Porta(u16),
    SemResposta(u16),
    Saiu(Option<i32>),
    NaoSubiu(String),
}

impl Falha {
    pub fn codigo(&self) -> &'static str {
        match self {
            Falha::SemInstalacao => "instalar",
            Falha::Captura => "captura",
            Falha::Porta(_) => "porta",
            Falha::SemResposta(_) => "sem_resposta",
            Falha::Saiu(_) => "saiu",
            Falha::NaoSubiu(_) => "subir",
        }
    }

    /// O que a `ui/erro.html` põe no lugar de `{detalhe}`: a porta, o código de saída ou o erro.
    pub fn detalhe(&self) -> String {
        match self {
            Falha::Porta(p) | Falha::SemResposta(p) => p.to_string(),
            Falha::Saiu(Some(codigo)) => codigo.to_string(),
            Falha::NaoSubiu(erro) => erro.clone(),
            _ => String::new(),
        }
    }
}

fn juntar(base: PathBuf, partes: &[&str]) -> PathBuf {
    partes.iter().fold(base, |p, parte| p.join(parte))
}

#[allow(deprecated)] // home_dir voltou a ser recomendado; o atributo cala as duas versões
fn casa_do_sistema() -> PathBuf {
    std::env::home_dir().unwrap_or_default()
}

/// A mesma regra de `pasta_de_dados` em `src/jobot/sistema/pastas.py` (desenho 7.1): o
/// `tests/unidade/test_casca_regras.py` confere por texto os caminhos e as variáveis daqui.
pub fn pasta_de_dados(env: impl Fn(&str) -> Option<String>, so: &str) -> PathBuf {
    let var = |nome: &str| env(nome).filter(|v| !v.is_empty());
    let casa = |nome: &str| var(nome).map_or_else(casa_do_sistema, PathBuf::from);
    if let Some(dados) = var("JOBOT_DADOS") {
        return PathBuf::from(dados);
    }
    match so {
        "windows" => match var("LOCALAPPDATA") {
            Some(local) => juntar(PathBuf::from(local), &["joBot"]),
            None => juntar(casa("USERPROFILE"), &["AppData", "Local", "joBot"]),
        },
        "macos" => juntar(casa("HOME"), &["Library", "Application Support", "joBot"]),
        _ => match var("XDG_DATA_HOME") {
            Some(xdg) => juntar(PathBuf::from(xdg), &["jobot"]),
            None => juntar(casa("HOME"), &[".local", "share", "jobot"]),
        },
    }
}

/// `JOBOT_PORTA` quando é um número de 1 a 65535; senão a porta padrão (como `instancia.porta`).
pub fn porta(env: impl Fn(&str) -> Option<String>) -> u16 {
    env("JOBOT_PORTA")
        .and_then(|v| v.trim().parse::<u16>().ok())
        .filter(|p| *p >= 1)
        .unwrap_or(PORTA_PADRAO)
}

fn inteiro_positivo(texto: &str) -> u64 {
    if !texto.is_empty() && texto.bytes().all(|b| b.is_ascii_digit()) {
        texto.parse().unwrap_or(0)
    } else {
        0
    }
}

/// PID e porta das linhas do `jobot.lock` (formato de `instancia.py`); estragado: `None`.
pub fn interpretar_trava(texto: &str) -> (Option<u32>, Option<u16>) {
    let mut linhas = texto.split('\n');
    let pid = linhas.next().map_or(0, inteiro_positivo);
    let porta = linhas.next().map_or(0, inteiro_positivo);
    (
        u32::try_from(pid).ok().filter(|p| *p > 0),
        u16::try_from(porta).ok().filter(|p| *p > 0),
    )
}

/// PID e porta do servidor, só se alguém prende a trava agora: trava solta guarda dado velho.
pub fn ler_trava(dados: &Path) -> (Option<u32>, Option<u16>) {
    let caminho = dados.join("jobot.lock");
    // como o O_NOFOLLOW do Python: nunca seguir symlink para fora da pasta de dados
    match caminho.symlink_metadata() {
        Ok(m) if m.file_type().is_file() => {}
        _ => return (None, None),
    }
    let Ok(mut arquivo) = File::open(&caminho) else {
        return (None, None);
    };
    match arquivo.try_lock_shared() {
        Err(TryLockError::WouldBlock) => {}
        Ok(()) => {
            // ninguém prende. No Windows a trava cobre o arquivo todo (o byte da trava do
            // `instancia.py` também) e fechar só a solta "um dia": soltar já, como o `_fechar`,
            // senão o `jobot serve` que vem logo depois não pega a trava dele
            let _ = arquivo.unlock();
            return (None, None);
        }
        Err(_) => return (None, None),
    }
    let mut texto = [0u8; 64];
    let lidos = arquivo.read(&mut texto).unwrap_or(0);
    interpretar_trava(&String::from_utf8_lossy(&texto[..lidos]))
}

pub fn url_do_painel(porta: u16) -> String {
    format!("http://127.0.0.1:{porta}/")
}

/// True só para `200` com um JSON `{"app": "jobot", ...}` (como `abrir.e_o_jobot`).
pub fn e_o_jobot(resposta: &[u8]) -> bool {
    let Some(fim) = resposta.windows(4).position(|w| w == b"\r\n\r\n") else {
        return false;
    };
    let cabeca = String::from_utf8_lossy(&resposta[..fim]);
    let status = cabeca.lines().next().unwrap_or("");
    if status.split_whitespace().nth(1) != Some("200") {
        return false;
    }
    serde_json::from_slice::<serde_json::Value>(&resposta[fim + 4..])
        .is_ok_and(|v| v.get("app").and_then(|a| a.as_str()) == Some("jobot"))
}

fn conectar(porta: u16, prazo: Duration) -> Option<TcpStream> {
    TcpStream::connect_timeout(&SocketAddr::from(([127, 0, 0, 1], porta)), prazo).ok()
}

/// `GET /saude-local` direto no 127.0.0.1 (sem proxy, sem seguir redirecionamento).
pub fn perguntar_saude(porta: u16) -> bool {
    let Some(mut s) = conectar(porta, Duration::from_secs(1)) else {
        return false;
    };
    let _ = s.set_read_timeout(Some(Duration::from_secs(1)));
    let _ = s.set_write_timeout(Some(Duration::from_secs(1)));
    let pedido = format!("GET /saude-local HTTP/1.0\r\nHost: 127.0.0.1:{porta}\r\n\r\n");
    if s.write_all(pedido.as_bytes()).is_err() {
        return false;
    }
    let mut resposta = Vec::new();
    let _ = s.take(8192).read_to_end(&mut resposta);
    e_o_jobot(&resposta)
}

pub fn porta_ocupada(porta: u16) -> bool {
    conectar(porta, Duration::from_millis(500)).is_some()
}

pub enum Sonda {
    Pronto,
    Espera,
    Desiste,
}

/// Pergunta à `sonda` de `PASSO` em `PASSO` até `PRAZO`; relógio e espera injetados.
pub fn esperar(
    agora: impl Fn() -> Duration,
    mut dormir: impl FnMut(Duration),
    mut sonda: impl FnMut() -> Sonda,
) -> bool {
    let fim = agora() + PRAZO;
    loop {
        match sonda() {
            Sonda::Pronto => return true,
            Sonda::Desiste => return false,
            Sonda::Espera => {}
        }
        if agora() >= fim {
            return false;
        }
        dormir(PASSO);
    }
}

/// O executável `jobot` de um venv (desenho 6.2).
pub fn jobot_do_venv(venv: &Path, so: &str) -> PathBuf {
    if so == "windows" {
        venv.join("Scripts").join("jobot.exe")
    } else {
        venv.join("bin").join("jobot")
    }
}

/// O `jobot` do venv apontado por `<dados>/instalacao.json`; sem arquivo ou executável: `None`.
pub fn jobot_instalado(dados: &Path, so: &str) -> Option<PathBuf> {
    let texto = std::fs::read(dados.join("instalacao.json")).ok()?;
    let conteudo: serde_json::Value = serde_json::from_slice(&texto).ok()?;
    if conteudo.get("canal")?.as_str()? != "casca" {
        return None;
    }
    let venv = conteudo.get("venv")?.as_str().filter(|v| !v.is_empty())?;
    Some(jobot_do_venv(Path::new(venv), so)).filter(|j| j.is_file())
}

/// `jobot <subcomando>` destacado (sessão própria no POSIX, grupo próprio sem console no
/// Windows, como `processo.destacar`): o servidor nunca é filho preso à casca.
pub fn comando_destacado(jobot: &Path, subcomando: &str) -> Command {
    let mut comando = Command::new(jobot);
    comando
        .arg(subcomando)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(unix)]
    std::os::unix::process::CommandExt::process_group(&mut comando, 0);
    #[cfg(windows)]
    std::os::windows::process::CommandExt::creation_flags(&mut comando, 0x200 | 0x8);
    comando
}

/// Acha o servidor pela trava ou sobe `jobot serve` e espera `/saude-local` (desenho 5.1).
pub fn achar_ou_subir(
    dados: &Path,
    jobot: &Path,
    env: impl Fn(&str) -> Option<String>,
) -> Result<u16, Falha> {
    let inicio = std::time::Instant::now();
    achar_ou_subir_com(
        dados,
        jobot,
        porta(env),
        || inicio.elapsed(),
        std::thread::sleep,
    )
}

/// O miolo de `achar_ou_subir`, com a porta padrão, o relógio e a espera injetados.
fn achar_ou_subir_com(
    dados: &Path,
    jobot: &Path,
    padrao: u16,
    agora: impl Fn() -> Duration,
    dormir: impl FnMut(Duration),
) -> Result<u16, Falha> {
    let (pid, gravada) = ler_trava(dados);
    if pid.is_some() && gravada.is_none() {
        return Err(Falha::Captura); // trava sem porta: captura com login no ar
    }
    let p = gravada.unwrap_or(padrao);
    let mut filho: Option<Child> = None;
    if pid.is_none() {
        if porta_ocupada(p) {
            return Err(Falha::Porta(p));
        }
        let c = comando_destacado(jobot, "serve")
            .spawn()
            .map_err(|e| Falha::NaoSubiu(e.to_string()))?;
        filho = Some(c);
    }
    let mut saiu = None;
    let pronto = esperar(agora, dormir, || {
        if perguntar_saude(p) {
            return Sonda::Pronto;
        }
        match filho.as_mut().and_then(|c| c.try_wait().ok().flatten()) {
            Some(status) => {
                saiu = Some(status.code());
                Sonda::Desiste
            }
            None => Sonda::Espera,
        }
    });
    if let Some(mut c) = filho.filter(|_| saiu.is_none()) {
        std::thread::spawn(move || c.wait()); // colhe o processo quando ele sair
    }
    match (pronto, saiu) {
        (true, _) => Ok(p),
        (false, Some(codigo)) => Err(Falha::Saiu(codigo)),
        (false, None) if porta_ocupada(p) && !perguntar_saude(p) => Err(Falha::Porta(p)),
        _ => Err(Falha::SemResposta(p)),
    }
}

/// As últimas `LINHAS_DO_LOG` linhas de `<dados>/logs/jobot.log`; sem log, vazio.
pub fn fim_do_log(dados: &Path) -> String {
    let bruto = std::fs::read(dados.join("logs").join("jobot.log")).unwrap_or_default();
    let texto = String::from_utf8_lossy(&bruto);
    let linhas: Vec<&str> = texto.lines().collect();
    linhas[linhas.len().saturating_sub(LINHAS_DO_LOG)..].join("\n")
}

#[cfg(test)]
mod testes {
    use super::*;
    use std::cell::Cell;
    use std::collections::HashMap;
    use std::net::TcpListener;

    fn ambiente(pares: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
        let mapa: HashMap<String, String> = pares
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        move |nome| mapa.get(nome).cloned()
    }

    fn pasta(pares: &[(&str, &str)], so: &str) -> PathBuf {
        pasta_de_dados(ambiente(pares), so)
    }

    fn temporaria(nome: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("jobot-casca-{nome}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&p);
        std::fs::create_dir_all(&p).unwrap();
        p
    }

    #[test]
    fn jobot_dados_vence_em_todo_sistema() {
        for so in ["linux", "windows", "macos"] {
            let env = [
                ("JOBOT_DADOS", "/x/d"),
                ("HOME", "/h"),
                ("LOCALAPPDATA", "/l"),
            ];
            assert_eq!(pasta(&env, so), PathBuf::from("/x/d"));
        }
    }

    #[test]
    fn linux_usa_xdg_e_depois_a_casa() {
        assert_eq!(
            pasta(&[("XDG_DATA_HOME", "/x"), ("HOME", "/h")], "linux"),
            PathBuf::from("/x/jobot")
        );
        let casa = pasta(&[("XDG_DATA_HOME", ""), ("HOME", "/h")], "linux");
        assert_eq!(casa, PathBuf::from("/h/.local/share/jobot"));
    }

    #[test]
    fn mac_usa_application_support() {
        assert_eq!(
            pasta(&[("HOME", "/Users/a")], "macos"),
            PathBuf::from("/Users/a/Library/Application Support/joBot")
        );
    }

    #[test]
    fn windows_usa_localappdata_e_depois_o_perfil() {
        let local = pasta(&[("LOCALAPPDATA", "C:/L")], "windows");
        assert_eq!(local, juntar(PathBuf::from("C:/L"), &["joBot"]));
        let perfil = pasta(&[("USERPROFILE", "C:/U")], "windows");
        assert_eq!(
            perfil,
            juntar(PathBuf::from("C:/U"), &["AppData", "Local", "joBot"])
        );
    }

    #[test]
    fn porta_do_ambiente_ou_a_padrao() {
        assert_eq!(porta(ambiente(&[("JOBOT_PORTA", " 8000 ")])), 8000);
        for ruim in ["0", "70000", "abc", ""] {
            assert_eq!(porta(ambiente(&[("JOBOT_PORTA", ruim)])), PORTA_PADRAO);
        }
        assert_eq!(porta(ambiente(&[])), PORTA_PADRAO);
    }

    #[test]
    fn trava_le_pid_e_porta() {
        assert_eq!(interpretar_trava("123\n47615\n"), (Some(123), Some(47615)));
        assert_eq!(interpretar_trava("123\n0\n"), (Some(123), None));
        assert_eq!(interpretar_trava("123\n"), (Some(123), None));
        assert_eq!(interpretar_trava("-1\n99999\n"), (None, None));
        assert_eq!(interpretar_trava("x\n+80\n"), (None, None));
        assert_eq!(interpretar_trava(""), (None, None));
    }

    #[test]
    fn trava_solta_e_dado_velho() {
        let dados = temporaria("solta");
        std::fs::write(dados.join("jobot.lock"), "42\n8000\n").unwrap();
        assert_eq!(ler_trava(&dados), (None, None));
        let dono = File::open(dados.join("jobot.lock")).unwrap();
        dono.lock().unwrap();
        assert_eq!(ler_trava(&dados), (Some(42), Some(8000)));
        drop(dono);
        assert_eq!(ler_trava(&temporaria("sem-trava")), (None, None));
    }

    #[test]
    fn url_do_painel_no_loopback() {
        assert_eq!(url_do_painel(47615), "http://127.0.0.1:47615/");
    }

    #[test]
    fn so_o_jobot_vale_na_saude() {
        let ok = b"HTTP/1.1 200 OK\r\ncontent-type: application/json\r\n\r\n{\"app\":\"jobot\",\"versao\":\"0.4.0\"}";
        assert!(e_o_jobot(ok));
        assert!(!e_o_jobot(b"HTTP/1.1 200 OK\r\n\r\n{\"app\":\"outro\"}"));
        assert!(!e_o_jobot(
            b"HTTP/1.1 404 Not Found\r\n\r\n{\"app\":\"jobot\"}"
        ));
        assert!(!e_o_jobot(b"HTTP/1.1 200 OK\r\n\r\n[\"jobot\"]"));
        assert!(!e_o_jobot(b"HTTP/1.1 200 OK\r\n\r\nnao e json"));
        assert!(!e_o_jobot(b"lixo"));
    }

    #[test]
    fn pergunta_a_saude_pela_rede_local() {
        let ouvinte = TcpListener::bind("127.0.0.1:0").unwrap();
        let p = ouvinte.local_addr().unwrap().port();
        let servidor = std::thread::spawn(move || {
            let (mut s, _) = ouvinte.accept().unwrap();
            let mut pedido = [0u8; 512];
            let n = s.read(&mut pedido).unwrap();
            assert!(String::from_utf8_lossy(&pedido[..n]).starts_with("GET /saude-local "));
            s.write_all(b"HTTP/1.1 200 OK\r\n\r\n{\"app\":\"jobot\"}")
                .unwrap();
        });
        assert!(perguntar_saude(p));
        servidor.join().unwrap();
    }

    #[test]
    fn espera_ate_quinze_segundos_de_duzentos_em_duzentos() {
        let relogio = Cell::new(Duration::ZERO);
        let mut perguntas = 0;
        let pronto = esperar(
            || relogio.get(),
            |d| relogio.set(relogio.get() + d),
            || {
                perguntas += 1;
                Sonda::Espera
            },
        );
        assert!(!pronto);
        assert_eq!(relogio.get(), PRAZO);
        assert_eq!(perguntas, 76); // em 0 s e a cada 200 ms até 15 s
    }

    #[test]
    fn espera_para_quando_fica_pronto_ou_desiste() {
        let relogio = Cell::new(Duration::ZERO);
        let pronto = esperar(
            || relogio.get(),
            |d| relogio.set(relogio.get() + d),
            || {
                if relogio.get() >= Duration::from_secs(3) {
                    Sonda::Pronto
                } else {
                    Sonda::Espera
                }
            },
        );
        assert!(pronto);
        assert_eq!(relogio.get(), Duration::from_secs(3));
        let desistiu = esperar(
            || Duration::ZERO,
            |_| panic!("não dorme"),
            || Sonda::Desiste,
        );
        assert!(!desistiu);
    }

    #[test]
    fn jobot_do_venv_por_sistema() {
        let venv = Path::new("/c/venvs/venv-0.4.0");
        assert_eq!(jobot_do_venv(venv, "linux"), venv.join("bin").join("jobot"));
        assert_eq!(jobot_do_venv(venv, "macos"), venv.join("bin").join("jobot"));
        assert_eq!(
            jobot_do_venv(venv, "windows"),
            venv.join("Scripts").join("jobot.exe")
        );
    }

    #[test]
    fn instalacao_aponta_o_jobot_do_venv() {
        let dados = temporaria("instalacao");
        assert_eq!(jobot_instalado(&dados, "linux"), None);
        let venv = dados.join("venv");
        let gravar = |canal: &str| {
            let json = serde_json::json!({"canal": canal, "venv": venv});
            std::fs::write(dados.join("instalacao.json"), json.to_string()).unwrap();
        };
        gravar("casca");
        assert_eq!(jobot_instalado(&dados, "linux"), None); // sem o executável
        std::fs::create_dir_all(venv.join("bin")).unwrap();
        std::fs::write(venv.join("bin").join("jobot"), "").unwrap();
        assert_eq!(
            jobot_instalado(&dados, "linux"),
            Some(venv.join("bin").join("jobot"))
        );
        gravar("uv_tool");
        assert_eq!(jobot_instalado(&dados, "linux"), None);
        std::fs::write(dados.join("instalacao.json"), "{").unwrap();
        assert_eq!(jobot_instalado(&dados, "linux"), None);
    }

    #[test]
    fn comando_destacado_sem_entrada_nem_saida() {
        let c = comando_destacado(Path::new("/v/bin/jobot"), "serve");
        assert_eq!(c.get_program(), "/v/bin/jobot");
        assert_eq!(c.get_args().collect::<Vec<_>>(), ["serve"]);
    }

    /// Um filho de verdade conta onde ficaram a entrada, as saídas e o grupo de processos.
    #[cfg(target_os = "linux")]
    #[test]
    fn comando_destacado_roda_em_grupo_proprio_e_mudo() {
        let pasta = temporaria("destacado");
        let script = pasta.join("conta.sh");
        // `$(...)` lê os descritores do próprio sh ($$) antes de qualquer redirecionamento
        let conta = "x=$(for n in 0 1 2; do readlink /proc/$$/fd/$n; done; \
                     cut -d' ' -f5 /proc/$$/stat)\necho \"$x\" > \"$0.out\"\n";
        std::fs::write(&script, conta).unwrap();
        // `sh <script>` em vez de rodar o script: sem o "text file busy" de teste em paralelo
        let mut filho = comando_destacado(Path::new("/bin/sh"), script.to_str().unwrap())
            .spawn()
            .unwrap();
        assert!(filho.wait().unwrap().success());
        let saida = std::fs::read_to_string(pasta.join("conta.sh.out")).unwrap();
        let linhas: Vec<&str> = saida.lines().collect();
        assert_eq!(linhas[..3], ["/dev/null"; 3]);
        assert_eq!(linhas[3], filho.id().to_string()); // líder do próprio grupo
    }

    fn trava_presa(dados: &Path, texto: &str) -> File {
        std::fs::write(dados.join("jobot.lock"), texto).unwrap();
        let dono = File::open(dados.join("jobot.lock")).unwrap();
        dono.lock().unwrap();
        dono
    }

    fn porta_livre() -> u16 {
        TcpListener::bind("127.0.0.1:0")
            .unwrap()
            .local_addr()
            .unwrap()
            .port()
    }

    /// Responde `resposta` a todo pedido, numa linha à parte que vive até o fim dos testes.
    fn servidor_falso(resposta: &'static [u8]) -> u16 {
        let ouvinte = TcpListener::bind("127.0.0.1:0").unwrap();
        let p = ouvinte.local_addr().unwrap().port();
        std::thread::spawn(move || {
            for mut s in ouvinte.incoming().flatten() {
                let mut pedido = [0u8; 512];
                let _ = s.read(&mut pedido);
                let _ = s.write_all(resposta);
            }
        });
        p
    }

    fn subir_com_relogio_falso(dados: &Path, jobot: &Path, padrao: u16) -> Result<u16, Falha> {
        let relogio = Cell::new(Duration::ZERO);
        achar_ou_subir_com(
            dados,
            jobot,
            padrao,
            || relogio.get(),
            |d| relogio.set(relogio.get() + d),
        )
    }

    const NAO_EXISTE: &str = "/nao/existe/jobot";

    #[test]
    fn trava_sem_porta_e_captura() {
        let dados = temporaria("captura");
        let _dono = trava_presa(&dados, "42\n");
        let r = subir_com_relogio_falso(&dados, Path::new(NAO_EXISTE), porta_livre());
        assert_eq!(r, Err(Falha::Captura));
    }

    #[test]
    fn porta_ocupada_sem_trava_nem_tenta_subir() {
        let dados = temporaria("ocupada");
        let ouvinte = TcpListener::bind("127.0.0.1:0").unwrap();
        let p = ouvinte.local_addr().unwrap().port();
        // com `jobot` que não existe, subir daria NaoSubiu
        let r = subir_com_relogio_falso(&dados, Path::new(NAO_EXISTE), p);
        assert_eq!(r, Err(Falha::Porta(p)));
    }

    #[test]
    fn trava_com_porta_acha_o_servidor_sem_subir() {
        let dados = temporaria("acha");
        let p = servidor_falso(b"HTTP/1.1 200 OK\r\n\r\n{\"app\":\"jobot\"}");
        let _dono = trava_presa(&dados, &format!("42\n{p}\n"));
        let r = subir_com_relogio_falso(&dados, Path::new(NAO_EXISTE), porta_livre());
        assert_eq!(r, Ok(p));
    }

    #[test]
    fn jobot_que_nao_roda_nao_subiu() {
        let dados = temporaria("nao-roda");
        let r = subir_com_relogio_falso(&dados, Path::new(NAO_EXISTE), porta_livre());
        assert!(matches!(r, Err(Falha::NaoSubiu(_))), "{r:?}");
    }

    #[cfg(unix)]
    #[test]
    fn filho_que_sai_vira_saiu() {
        let dados = temporaria("saiu");
        // `sh serve` sai logo com erro: não há arquivo `serve` para ler
        let inicio = std::time::Instant::now();
        let r = achar_ou_subir_com(
            &dados,
            Path::new("/bin/sh"),
            porta_livre(),
            || inicio.elapsed(),
            std::thread::sleep,
        );
        assert!(matches!(r, Err(Falha::Saiu(Some(c))) if c != 0), "{r:?}");
    }

    #[test]
    fn sem_saude_no_prazo_com_a_porta_de_outro_e_porta() {
        let dados = temporaria("outro");
        let p = servidor_falso(b"HTTP/1.1 404 Not Found\r\n\r\n");
        let _dono = trava_presa(&dados, &format!("42\n{p}\n"));
        let r = subir_com_relogio_falso(&dados, Path::new(NAO_EXISTE), porta_livre());
        assert_eq!(r, Err(Falha::Porta(p)));
    }

    #[test]
    fn sem_saude_no_prazo_e_porta_vazia_e_sem_resposta() {
        let dados = temporaria("vazia");
        let p = porta_livre();
        let _dono = trava_presa(&dados, &format!("42\n{p}\n"));
        let r = subir_com_relogio_falso(&dados, Path::new(NAO_EXISTE), porta_livre());
        assert_eq!(r, Err(Falha::SemResposta(p)));
    }

    #[test]
    fn fim_do_log_tem_as_ultimas_vinte_linhas() {
        let dados = temporaria("log");
        assert_eq!(fim_do_log(&dados), "");
        std::fs::create_dir_all(dados.join("logs")).unwrap();
        let linhas: Vec<String> = (1..=30).map(|n| format!("linha {n}")).collect();
        std::fs::write(dados.join("logs").join("jobot.log"), linhas.join("\n")).unwrap();
        let fim = fim_do_log(&dados);
        assert!(fim.starts_with("linha 11\n"));
        assert!(fim.ends_with("linha 30"));
    }

    #[test]
    fn codigos_das_falhas() {
        assert_eq!(Falha::SemInstalacao.codigo(), "instalar");
        assert_eq!(Falha::Porta(1).codigo(), "porta");
        assert_eq!(Falha::Saiu(None).codigo(), "saiu");
        assert_eq!(Falha::SemResposta(8000).detalhe(), "8000");
        assert_eq!(Falha::Saiu(Some(3)).detalhe(), "3");
    }
}
