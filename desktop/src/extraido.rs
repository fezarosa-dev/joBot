//! AppImage extraído (T354, D211). Sem FUSE, ou com `--appimage-extract-and-run`, o runtime do
//! AppImage se extrai em `$TMPDIR/appimage_extracted_<md5>` (o `/tmp`, que em muitos Linux fica
//! na RAM: uns 400 MB) e só apaga a pasta se ele mesmo sobreviver até a casca sair. Ctrl+C,
//! fechar o terminal ou matar o processo deixam a pasta. A casca lança então um vigia, num
//! grupo de processos próprio e sem o ambiente do AppImage, que espera a casca e o runtime
//! saírem e apaga a pasta. Com FUSE, o próprio runtime desmonta e apaga o `.mount_*`.

use std::path::{Path, PathBuf};
use std::process::Command;

/// A pasta extraída que a casca deve limpar: o `APPDIR` absoluto chamado
/// `appimage_extracted_<32 hex>`, com o `APPIMAGE` definido e o executável da casca dentro
/// dele. Qualquer outra coisa (a montagem `.mount_*` do FUSE, o `.deb`, um `APPDIR` estranho)
/// fica como está.
pub fn pasta_a_limpar(
    appdir: Option<&Path>,
    appimage: Option<&Path>,
    exe: &Path,
) -> Option<PathBuf> {
    let _ = (appdir, appimage, exe);
    None
}

/// O vigia: espera todos os `pids` saírem e apaga a `pasta`.
pub fn vigia(pasta: &Path, pids: &[u32]) -> Command {
    let _ = (pasta, pids);
    Command::new("true")
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
        for nome in [
            "appimage_extracted_",
            "appimage_extracted_56fe70d7183c4a60aa470ea7cf3c62f",
            "appimage_extracted_56fe70d7183c4a60aa470ea7cf3c62f2x",
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
