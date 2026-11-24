//! AppImage extraído (T354, D211, D217). Sem FUSE, ou com `--appimage-extract-and-run`, o
//! runtime do AppImage se extrai em `$TMPDIR/appimage_extracted_<md5>` (o `/tmp`, que em muitos
//! Linux fica na RAM: uns 400 MB). O runtime que vai no AppImage não apaga a pasta, nem numa
//! saída normal (visto com `strace`: depois do `wait4`, ele sai sem um `unlink`). A casca lança
//! então um vigia, num grupo de processos próprio e sem o ambiente do AppImage, que espera a
//! casca e o runtime saírem e apaga a pasta. Com FUSE, o próprio runtime desmonta e apaga o
//! `.mount_*`.
//!
//! A pasta tem o mesmo nome em toda abertura do mesmo arquivo: enquanto alguém a usa (o runtime
//! de outra abertura, que extrai nela, ou um programa de dentro dela, como a casca seguinte ou
//! um processo do WebKit que ainda sai), o vigia espera. Antes de apagar, ele troca o nome da
//! pasta, para que uma abertura que comece nesse instante extraia numa pasta nova.

use std::os::unix::process::CommandExt;
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};

/// A pasta extraída que a casca deve limpar: o `APPDIR` absoluto chamado
/// `appimage_extracted_<32 hex>`, com o `APPIMAGE` definido e o executável da casca dentro
/// dele. Qualquer outra coisa (a montagem `.mount_*` do FUSE, o `.deb`, um `APPDIR` estranho)
/// fica como está.
pub fn pasta_a_limpar(
    appdir: Option<&Path>,
    appimage: Option<&Path>,
    exe: &Path,
) -> Option<PathBuf> {
    appimage?;
    let pasta = appdir?;
    let hex = pasta
        .file_name()?
        .to_str()?
        .strip_prefix("appimage_extracted_")?;
    let nome = hex.len() == 32 && hex.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'));
    let limpo = pasta.is_absolute()
        && pasta
            .components()
            .all(|c| matches!(c, Component::RootDir | Component::Normal(_)));
    (nome && limpo && exe.starts_with(pasta)).then(|| pasta.to_path_buf())
}

/// `$1` é a pasta, `$2` o AppImage e o resto são os pids. Ignora o HUP de fechar o terminal e
/// o INT do Ctrl+C. Zumbi conta como morto: um pai que não o recolhe (no contêiner, o `sleep`
/// como pid 1) prenderia o vigia para sempre. `em_uso`: um processo da pessoa roda o mesmo
/// AppImage (o runtime de outra abertura, que extrai na mesma pasta) ou um programa de dentro
/// da pasta; o vigia espera também por eles. O `mv` antes do `rm` tira o nome da pasta do
/// caminho de quem abrir depois.
const VIGIA: &str = r#"trap '' HUP INT
d=$1; a=$2; shift 2
vivo() {
  for p in "$@"; do
    s=$(cat "/proc/$p/stat" 2>/dev/null) || continue
    e=${s##*) }
    case $e in Z*) ;; *) return 0 ;; esac
  done
  return 1
}
em_uso() {
  for x in /proc/[0-9]*/exe; do
    x=$(readlink "$x" 2>/dev/null) || continue
    case $x in "$a" | "$d"/*) return 0 ;; esac
  done
  return 1
}
while vivo "$@" || em_uso; do sleep 1; done
lixo="$d.apagando.$$"
if mv -- "$d" "$lixo" 2>/dev/null; then rm -rf -- "$lixo"; fi"#;

/// O vigia: espera todos os `pids` saírem, e ninguém mais usar a `pasta` nem rodar o
/// `appimage`, e apaga a pasta. Grupo de processos próprio (o Ctrl+C e o `kill` do grupo da casca não o
/// alcançam), na raiz (não prende a pasta) e sem o ambiente do AppImage, cujo
/// `LD_LIBRARY_PATH` aponta para a pasta que ele apaga.
pub fn vigia(pasta: &Path, appimage: &Path, pids: &[u32]) -> Command {
    let mut c = Command::new("sh");
    c.arg("-c")
        .arg(VIGIA)
        .arg("jobot-vigia")
        .arg(pasta)
        .arg(appimage)
        .args(pids.iter().map(u32::to_string))
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .current_dir("/")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .process_group(0);
    c
}

/// No começo da casca: se ela roda de uma extração do AppImage, lança o vigia da pasta. Espera
/// a casca e o pai dela, o runtime (o AppRun do AppImage troca de programa sem criar outro
/// processo). O AppImage vai com o caminho real, que é o que o `/proc/<pid>/exe` do runtime
/// mostra.
pub fn vigiar() {
    let appdir = std::env::var_os("APPDIR").and_then(|p| PathBuf::from(p).canonicalize().ok());
    let appimage = std::env::var_os("APPIMAGE").map(PathBuf::from);
    let Ok(exe) = std::env::current_exe() else {
        return;
    };
    let Some(pasta) = pasta_a_limpar(appdir.as_deref(), appimage.as_deref(), &exe) else {
        return;
    };
    let Some(appimage) = appimage.map(|a| a.canonicalize().unwrap_or(a)) else {
        return;
    };
    let pids = [std::process::id(), std::os::unix::process::parent_id()];
    if let Err(erro) = vigia(&pasta, &appimage, &pids).spawn() {
        eprintln!("jobot-app: não consegui vigiar {}: {erro}", pasta.display());
    }
}

unsafe extern "C" {
    fn fcntl(fd: i32, cmd: i32, ...) -> i32;
}
const F_GETFD: i32 = 1;
const F_SETFD: i32 = 2;
const FD_CLOEXEC: i32 = 1;

/// No começo da casca: os descritores herdados além de 0-2 não passam aos filhos (D217). O
/// runtime do AppImage com FUSE deixa aberto o cano que mantém a montagem `/tmp/.mount_*`
/// viva; o `jobot serve` que fica ligado depois da casca a prenderia por dias. A casca segue
/// com eles abertos (o Rust já abre os dele assim).
pub fn nao_herdar_descritores() {
    let Ok(lista) = std::fs::read_dir("/proc/self/fd") else {
        return;
    };
    let fds: Vec<i32> = lista
        .filter_map(|e| e.ok()?.file_name().to_str()?.parse().ok())
        .filter(|&fd| fd > 2)
        .collect();
    for fd in fds {
        // SAFETY: só lê e troca as flags do descritor; um que já fechou (o da própria lista)
        // devolve -1 e fica como está
        unsafe {
            let flags = fcntl(fd, F_GETFD);
            if flags >= 0 && flags & FD_CLOEXEC == 0 {
                fcntl(fd, F_SETFD, flags | FD_CLOEXEC);
            }
        }
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use std::time::{Duration, Instant};

    const NOME: &str = "appimage_extracted_56fe70d7183c4a60aa470ea7cf3c62f2";
    /// Um AppImage que nenhum processo roda.
    const NAO_HA: &str = "/nao/existe/joBot.AppImage";

    fn limpar(appdir: &str, appimage: Option<&str>, exe: &str) -> Option<PathBuf> {
        pasta_a_limpar(
            Some(Path::new(appdir)),
            appimage.map(Path::new),
            Path::new(exe),
        )
    }

    #[test]
    fn so_a_pasta_extraida_que_tem_a_casca_dentro() {
        let pasta = format!("/tmp/{NOME}");
        let exe = format!("{pasta}/usr/bin/jobot-app");
        let img = Some("/home/p/joBot.AppImage");
        assert_eq!(limpar(&pasta, img, &exe), Some(PathBuf::from(&pasta)));
        // o TMPDIR da pessoa vale tanto quanto o /tmp
        let cache = format!("/home/p/.cache/{NOME}");
        let exe_cache = format!("{cache}/usr/bin/jobot-app");
        assert_eq!(limpar(&cache, img, &exe_cache), Some(PathBuf::from(&cache)));
    }

    #[test]
    fn fora_da_extracao_nada_e_apagado() {
        let img = Some("/home/p/joBot.AppImage");
        // FUSE: o runtime desmonta e apaga a montagem sozinho
        assert_eq!(
            limpar(
                "/tmp/.mount_joBotX1",
                img,
                "/tmp/.mount_joBotX1/usr/bin/jobot-app"
            ),
            None
        );
        // sem APPIMAGE: não foi o runtime do AppImage que montou o APPDIR
        let pasta = format!("/tmp/{NOME}");
        assert_eq!(
            limpar(&pasta, None, &format!("{pasta}/usr/bin/jobot-app")),
            None
        );
        // a casca não roda de dentro da pasta (APPDIR herdado de outro programa)
        assert_eq!(limpar(&pasta, img, "/usr/bin/jobot-app"), None);
        // caminho relativo, com `..`, nome sem os 32 hex ou com outra coisa no fim
        let rel = format!("tmp/{NOME}");
        assert_eq!(limpar(&rel, img, &format!("{rel}/usr/bin/jobot-app")), None);
        let volta = format!("/tmp/{NOME}/..");
        assert_eq!(limpar(&volta, img, &format!("{volta}/x/jobot-app")), None);
        let meio = format!("/tmp/../tmp/{NOME}");
        assert_eq!(
            limpar(&meio, img, &format!("{meio}/usr/bin/jobot-app")),
            None
        );
        for nome in [
            "appimage_extracted_",
            "appimage_extracted_56fe70d7183c4a60aa470ea7cf3c62f",
            "appimage_extracted_56fe70d7183c4a60aa470ea7cf3c62f2x",
            "appimage_extracted_56fe70d7183c4a60aa470ea7cf3c62f2a",
            "appimage_extracted_56FE70D7183C4A60AA470EA7CF3C62F2",
            "appimage_extracted_zzfe70d7183c4a60aa470ea7cf3c62f2",
        ] {
            let p = format!("/tmp/{nome}");
            assert_eq!(
                limpar(&p, img, &format!("{p}/usr/bin/jobot-app")),
                None,
                "{nome}"
            );
        }
        // sem APPDIR
        assert_eq!(
            pasta_a_limpar(
                None,
                img.map(Path::new),
                Path::new("/tmp/x/usr/bin/jobot-app")
            ),
            None
        );
    }

    #[test]
    fn vigia_roda_sh_mudo_e_sem_o_ambiente_do_appimage() {
        let c = vigia(
            Path::new("/tmp/x"),
            Path::new("/home/p/joBot.AppImage"),
            &[10, 20],
        );
        assert_eq!(c.get_program(), "sh");
        let args: Vec<_> = c.get_args().map(|a| a.to_str().unwrap()).collect();
        assert_eq!(args[0], "-c");
        assert_eq!(
            &args[2..],
            [
                "jobot-vigia",
                "/tmp/x",
                "/home/p/joBot.AppImage",
                "10",
                "20"
            ]
        );
        assert_eq!(c.get_current_dir(), Some(Path::new("/")));
        let envs: Vec<_> = c.get_envs().collect();
        assert_eq!(
            envs,
            [(
                std::ffi::OsStr::new("PATH"),
                Some(std::ffi::OsStr::new("/usr/bin:/bin"))
            )]
        );
    }

    /// Um processo que saiu e ninguém recolheu (zumbi) não prende o vigia.
    #[test]
    fn vigia_nao_espera_zumbi() {
        let pasta = std::env::temp_dir().join(format!("jobot-zumbi-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&pasta);
        std::fs::create_dir_all(&pasta).unwrap();
        let mut zumbi = Command::new("true").spawn().unwrap();
        // sem wait: o `true` sai e fica zumbi, filho deste teste
        let fim = Instant::now() + Duration::from_secs(5);
        let zumbi_ja = || {
            std::fs::read_to_string(format!("/proc/{}/stat", zumbi.id()))
                .is_ok_and(|s| s.rsplit_once(") ").unwrap().1.starts_with('Z'))
        };
        while !zumbi_ja() && Instant::now() < fim {
            std::thread::sleep(Duration::from_millis(20));
        }
        assert!(zumbi_ja(), "o processo não virou zumbi");
        let mut v = vigia(&pasta, Path::new(NAO_HA), &[zumbi.id()])
            .spawn()
            .unwrap();
        let fim = Instant::now() + Duration::from_secs(10);
        while pasta.exists() && Instant::now() < fim {
            std::thread::sleep(Duration::from_millis(100));
        }
        assert!(!pasta.exists(), "o vigia esperou o zumbi");
        assert!(v.wait().unwrap().success());
        zumbi.wait().unwrap();
    }

    /// Um vigia de verdade: a pasta fica enquanto um dos processos vive e sai depois.
    #[test]
    fn vigia_apaga_a_pasta_so_depois_que_todos_saem() {
        let pasta = std::env::temp_dir().join(format!("jobot-vigia-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&pasta);
        std::fs::create_dir_all(pasta.join("usr/bin")).unwrap();
        std::fs::write(pasta.join("usr/bin/jobot-app"), "x").unwrap();
        let mut curto = Command::new("sleep").arg("1").spawn().unwrap();
        let mut longo = Command::new("sleep").arg("4").spawn().unwrap();
        let mut v = vigia(&pasta, Path::new(NAO_HA), &[curto.id(), longo.id()])
            .spawn()
            .unwrap();
        // grupo próprio (o kill do grupo da casca não o alcança) e só o PATH no ambiente
        let stat = std::fs::read_to_string(format!("/proc/{}/stat", v.id())).unwrap();
        let campos: Vec<_> = stat
            .rsplit_once(')')
            .unwrap()
            .1
            .split_whitespace()
            .collect();
        assert_eq!(
            campos[2],
            v.id().to_string(),
            "o vigia não tem grupo próprio"
        );
        let ambiente = std::fs::read(format!("/proc/{}/environ", v.id())).unwrap();
        assert_eq!(ambiente, b"PATH=/usr/bin:/bin\0");
        // fechar o terminal (HUP) e o Ctrl+C (INT) não o derrubam, depois do `trap`
        std::thread::sleep(Duration::from_millis(300));
        for sinal in ["-HUP", "-INT"] {
            let pid = v.id().to_string();
            assert!(
                Command::new("kill")
                    .args([sinal, &pid])
                    .status()
                    .unwrap()
                    .success()
            );
        }
        std::thread::sleep(Duration::from_millis(300));
        assert!(v.try_wait().unwrap().is_none(), "um sinal derrubou o vigia");
        curto.wait().unwrap();
        std::thread::sleep(Duration::from_millis(1500));
        assert!(pasta.exists(), "apagou com um processo ainda vivo");
        longo.wait().unwrap();
        let fim = Instant::now() + Duration::from_secs(10);
        while pasta.exists() && Instant::now() < fim {
            std::thread::sleep(Duration::from_millis(100));
        }
        assert!(!pasta.exists(), "o vigia não apagou a pasta");
        assert!(v.wait().unwrap().success());
        // nem a pasta com o nome trocado sobra
        let nome = pasta.file_name().unwrap().to_str().unwrap().to_owned();
        let sobra = std::fs::read_dir(pasta.parent().unwrap())
            .unwrap()
            .filter_map(Result::ok)
            .any(|e| e.file_name().to_string_lossy().starts_with(&nome));
        assert!(!sobra, "sobrou a pasta renomeada");
    }

    /// Outra abertura do mesmo AppImage no ar (o runtime dela extraindo na mesma pasta): o
    /// vigia espera ela sair antes de apagar (D217). Uma cópia do `sleep` faz o papel do
    /// AppImage (um nome só deste teste: o sistema pode ter outros `sleep` rodando).
    #[test]
    fn vigia_espera_outra_abertura_do_mesmo_appimage() {
        let pasta = std::env::temp_dir().join(format!("jobot-outra-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&pasta);
        std::fs::create_dir_all(&pasta).unwrap();
        let sleep = std::env::temp_dir().join(format!("jobot-img-{}.AppImage", std::process::id()));
        std::fs::copy("/bin/sleep", &sleep).unwrap();
        // ETXTBSY: outro teste pode ter feito fork com a cópia recém-escrita aberta
        let mut outra = std::iter::repeat_with(|| Command::new(&sleep).arg("30").spawn())
            .take(50)
            .find_map(|r| match r {
                Err(e) if e.raw_os_error() == Some(26) => {
                    std::thread::sleep(Duration::from_millis(100));
                    None
                }
                r => Some(r.unwrap()),
            })
            .unwrap();
        let mut runtime = Command::new("true").spawn().unwrap();
        runtime.wait().unwrap();
        let real = sleep.canonicalize().unwrap(); // o que o /proc/<pid>/exe mostra
        let mut v = vigia(&pasta, &real, &[runtime.id()]).spawn().unwrap();
        std::thread::sleep(Duration::from_millis(1500));
        assert!(pasta.exists(), "o vigia apagou a pasta de outra abertura");
        assert!(
            v.try_wait().unwrap().is_none(),
            "o vigia desistiu de esperar"
        );
        outra.kill().unwrap();
        outra.wait().unwrap();
        let fim = Instant::now() + Duration::from_secs(10);
        while pasta.exists() && Instant::now() < fim {
            std::thread::sleep(Duration::from_millis(100));
        }
        assert!(
            !pasta.exists(),
            "o vigia não apagou depois que a outra abertura saiu"
        );
        assert!(v.wait().unwrap().success());
        std::fs::remove_file(&sleep).unwrap();
    }

    /// Um descritor herdado sem CLOEXEC (o cano do runtime do AppImage) não chega aos filhos.
    #[test]
    fn descritor_herdado_nao_passa_aos_filhos() {
        use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
        const F_DUPFD: i32 = 0;
        let arquivo = std::fs::File::open("/proc/self/stat").unwrap();
        // como o runtime o deixa: herdável (o F_DUPFD não copia o CLOEXEC), num número que o
        // `sh` do teste não usa
        let fd = unsafe { fcntl(arquivo.as_raw_fd(), F_DUPFD, 100) };
        assert!(fd >= 100);
        let _dono = unsafe { OwnedFd::from_raw_fd(fd) };
        let flags = |fd| unsafe { fcntl(fd, F_GETFD) };
        assert_eq!(flags(fd) & FD_CLOEXEC, 0);
        let entrada = flags(0);
        let herda = |fd: i32| {
            Command::new("sh")
                .arg("-c")
                .arg(format!("test -e /proc/self/fd/{fd}"))
                .status()
                .unwrap()
                .success()
        };
        assert!(
            herda(fd),
            "controle: o filho deveria ver o descritor herdável"
        );
        nao_herdar_descritores();
        assert_eq!(flags(fd) & FD_CLOEXEC, FD_CLOEXEC);
        assert!(!herda(fd), "o filho herdou o descritor");
        assert_eq!(flags(0), entrada, "mexeu no 0-2");
    }
}
