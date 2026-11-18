//! AppImage extraído (T354, D211). Sem FUSE, ou com `--appimage-extract-and-run`, o runtime do
//! AppImage se extrai em `$TMPDIR/appimage_extracted_<md5>` (o `/tmp`, que em muitos Linux fica
//! na RAM: uns 400 MB) e só apaga a pasta se ele mesmo sobreviver até a casca sair. Ctrl+C,
//! fechar o terminal ou matar o processo deixam a pasta. A casca lança então um vigia, num
//! grupo de processos próprio e sem o ambiente do AppImage, que espera a casca e o runtime
//! saírem e apaga a pasta. Com FUSE, o próprio runtime desmonta e apaga o `.mount_*`.

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

/// `$1` é a pasta e o resto são os pids. Ignora o HUP de fechar o terminal e o INT do Ctrl+C.
const VIGIA: &str = r#"trap '' HUP INT
d=$1; shift
vivo() { for p in "$@"; do kill -0 "$p" 2>/dev/null && return 0; done; return 1; }
while vivo "$@"; do sleep 1; done
rm -rf -- "$d""#;

/// O vigia: espera todos os `pids` saírem e apaga a `pasta`. Grupo de processos próprio (o
/// Ctrl+C e o `kill` do grupo da casca não o alcançam), na raiz (não prende a pasta) e sem
/// o ambiente do AppImage, cujo `LD_LIBRARY_PATH` aponta para a pasta que ele apaga.
pub fn vigia(pasta: &Path, pids: &[u32]) -> Command {
    let mut c = Command::new("sh");
    c.arg("-c")
        .arg(VIGIA)
        .arg("jobot-vigia")
        .arg(pasta)
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
/// processo), que apaga a pasta numa saída normal; o vigia só age quando o runtime não pôde.
pub fn vigiar() {
    let appdir = std::env::var_os("APPDIR").and_then(|p| PathBuf::from(p).canonicalize().ok());
    let appimage = std::env::var_os("APPIMAGE").map(PathBuf::from);
    let Ok(exe) = std::env::current_exe() else {
        return;
    };
    let Some(pasta) = pasta_a_limpar(appdir.as_deref(), appimage.as_deref(), &exe) else {
        return;
    };
    let pids = [std::process::id(), std::os::unix::process::parent_id()];
    if let Err(erro) = vigia(&pasta, &pids).spawn() {
        eprintln!("jobot-app: não consegui vigiar {}: {erro}", pasta.display());
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use std::time::{Duration, Instant};

    const NOME: &str = "appimage_extracted_56fe70d7183c4a60aa470ea7cf3c62f2";

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
        let c = vigia(Path::new("/tmp/x"), &[10, 20]);
        assert_eq!(c.get_program(), "sh");
        let args: Vec<_> = c.get_args().map(|a| a.to_str().unwrap()).collect();
        assert_eq!(args[0], "-c");
        assert_eq!(&args[2..], ["jobot-vigia", "/tmp/x", "10", "20"]);
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

    /// Um vigia de verdade: a pasta fica enquanto um dos processos vive e sai depois.
    #[test]
    fn vigia_apaga_a_pasta_so_depois_que_todos_saem() {
        let pasta = std::env::temp_dir().join(format!("jobot-vigia-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&pasta);
        std::fs::create_dir_all(pasta.join("usr/bin")).unwrap();
        std::fs::write(pasta.join("usr/bin/jobot-app"), "x").unwrap();
        let mut curto = Command::new("sleep").arg("1").spawn().unwrap();
        let mut longo = Command::new("sleep").arg("4").spawn().unwrap();
        let mut v = vigia(&pasta, &[curto.id(), longo.id()]).spawn().unwrap();
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
    }
}
