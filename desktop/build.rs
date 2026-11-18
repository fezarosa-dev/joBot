//! Antes do `tauri_build`: copia o CSS, as fontes e o ícone do painel para `ui/painel/`
//! (gitignored; desenho 5.2), garante a pasta `recursos/` (gitignored, vazia no build local:
//! a casca diz que o instalador está incompleto) e declara os comandos da tela de instalação e
//! do controle, que só a capability `local` (as páginas de `ui/`) libera.

use std::fs;
use std::path::Path;

const DO_PAINEL: [(&str, &str); 6] = [
    ("../src/jobot/painel/static/css/base.css", "css/base.css"),
    (
        "../src/jobot/painel/static/css/execucao.css",
        "css/execucao.css",
    ),
    (
        "../src/jobot/painel/static/fontes/InterVariable.woff2",
        "fontes/InterVariable.woff2",
    ),
    (
        "../src/jobot/painel/static/fontes/InterVariable-Italic.woff2",
        "fontes/InterVariable-Italic.woff2",
    ),
    (
        "../src/jobot/painel/static/fontes/OFL.txt",
        "fontes/OFL.txt",
    ),
    ("icons/icon.png", "icone.png"),
];

fn main() {
    for (de, para) in DO_PAINEL {
        println!("cargo:rerun-if-changed={de}");
        let destino = Path::new("ui/painel").join(para);
        fs::create_dir_all(destino.parent().expect("pasta")).expect("criar ui/painel");
        fs::copy(de, &destino).unwrap_or_else(|e| panic!("copiar {de}: {e}"));
    }
    fs::create_dir_all("recursos").expect("criar recursos/");
    println!("cargo:rerun-if-env-changed=JOBOT_MANIFESTO_SHA256");
    let comandos = tauri_build::AppManifest::new().commands(&[
        "estado_instalador",
        "instalar",
        "fechar_instalador",
        "estado_controle",
        "ligar",
        "parar",
        "abrir_jobot",
        "abrir_release",
    ]);
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(comandos))
        .expect("tauri-build");
}
