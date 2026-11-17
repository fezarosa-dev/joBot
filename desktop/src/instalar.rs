//! Instalação pela casca, sem rede (desenho 5.2 e 6.2; D173, D174, D181). Confere o
//! `manifesto.json` pelo sha256 gravado no build e cada arquivo dos recursos pelo manifesto,
//! prepara o Python e o venv com o `uv` dos recursos, prova o `jobot --version`, baixa o
//! navegador se marcado (o único passo com rede, D183.24) e só então grava o `instalacao.json`. Falhou ou foi cancelada: o que a
//! instalação criou na pasta da casca sai e o `instalacao.json` não é gravado (o Chromium fica
//! na pasta do Playwright, D181.9).
//!
//! Recursos (`desktop/recursos/`, D181): `manifesto.json`, `bin/uv.tar` (o `uv` ou o `uv.exe`
//! num tar sem compressão, D183),
//! `python/<tag>/cpython-<versão>+<tag>-<alvo>-install_only_stripped.tar.gz` (o espelho que o
//! `uv python install --mirror` lê), `restricoes.txt`, `wheels/*.whl` e as `licencas/uv/`. O
//! navegador não vem nos recursos: o joBot não redistribui o Chrome for Testing que o Playwright
//! baixa (D183.24); o `jobot ferramentas baixar navegador` o baixa pelo `playwright install`.

use crate::servidor;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::fmt::Write as _;
use std::fs::{self, File, OpenOptions};
use std::io::{self, BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::time::Duration;

pub const MANIFESTO: &str = "manifesto.json";
pub const INSTALACAO: &str = "instalacao.json";
const UV: &str = "bin/uv.tar";
/// Quanto o navegador baixado ocupa compactado, para o rodapé da tela (o Chromium do Playwright
/// 1.65 baixa de 170 a 216 MB por sistema, D183.23); a tela multiplica pelo fator do disco.
pub const TAMANHO_DO_NAVEGADOR: u64 = 190_000_000;

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

impl Manifesto {
    fn achar(&self, aceita: impl Fn(&str) -> bool, o_que: &str) -> Result<&Entrada, Erro> {
        let mut achados = self.arquivos.iter().filter(|e| aceita(&e.nome));
        match (achados.next(), achados.next()) {
            (Some(entrada), None) => Ok(entrada),
            _ => Err(Erro::Arquivo(o_que.into())),
        }
    }
}

/// Por que a instalação parou; o `codigo` vira o motivo da tela de falha.
#[derive(Debug, PartialEq)]
pub enum Erro {
    Arquivo(String),
    Espaco,
    Prova(String),
    /// O download do navegador falhou (sem rede, por exemplo).
    Navegador(String),
    Cancelado,
    Outro(String),
}

impl Erro {
    pub fn codigo(&self) -> &'static str {
        match self {
            Erro::Arquivo(_) => "arquivo",
            Erro::Espaco => "espaco",
            Erro::Prova(_) => "prova",
            Erro::Navegador(_) => "navegador",
            Erro::Cancelado => "cancelado",
            Erro::Outro(_) => "outro",
        }
    }

    pub fn detalhe(&self) -> String {
        match self {
            Erro::Arquivo(texto)
            | Erro::Prova(texto)
            | Erro::Navegador(texto)
            | Erro::Outro(texto) => texto.clone(),
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

/// O `uv` dos recursos vem num tar ustar sem compressão, de um arquivo só: o linuxdeploy do
/// AppImage reescreve o rpath de todo ELF em `usr/lib`, e um `uv` solto deixaria de bater com o
/// manifesto (D183). O tar já foi conferido pelo sha256; aqui só se tira o conteúdo.
fn tirar_do_tar(tar: &Path, destino: &Path) -> Result<(), Erro> {
    let ruim = || Erro::Arquivo(UV.into());
    let bruto = fs::read(tar)?;
    let cabecalho = bruto.get(..512).ok_or_else(ruim)?;
    if &cabecalho[257..262] != b"ustar" || !matches!(cabecalho[156], b'0' | 0) {
        return Err(ruim());
    }
    let tamanho = std::str::from_utf8(&cabecalho[124..136])
        .ok()
        .map(|t| t.trim_matches(|c: char| c == '\0' || c == ' '))
        .and_then(|t| usize::from_str_radix(t, 8).ok())
        .ok_or_else(ruim)?;
    let dados = bruto.get(512..512 + tamanho).ok_or_else(ruim)?;
    fs::write(destino, dados)?;
    Ok(())
}

/// A versão do Python pelo nome do arquivo no espelho (`python/<tag>/cpython-<versão>+<tag>-...`).
fn versao_do_python(nome: &str) -> Option<&str> {
    let (tag, arquivo) = nome.strip_prefix("python/")?.split_once('/')?;
    let (versao, resto) = arquivo.strip_prefix("cpython-")?.split_once('+')?;
    let numeros = versao
        .split('.')
        .all(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit()));
    (numeros && resto.starts_with(tag) && arquivo.ends_with(".tar.gz")).then_some(versao)
}

pub fn ler_manifesto(bytes: &[u8]) -> Result<Manifesto, Erro> {
    let ruim = || Erro::Arquivo(MANIFESTO.into());
    let conteudo: Value = serde_json::from_slice(bytes).map_err(|_| ruim())?;
    let versao = conteudo
        .get("versao")
        .and_then(Value::as_str)
        .ok_or_else(ruim)?;
    let lista = conteudo
        .get("arquivos")
        .and_then(Value::as_array)
        .ok_or_else(ruim)?;
    let mut arquivos: Vec<Entrada> = Vec::new();
    for item in lista {
        let nome = item.get("nome").and_then(Value::as_str);
        let nome = nome
            .filter(|n| nome_valido(n) && *n != MANIFESTO)
            .ok_or_else(ruim)?;
        let tamanho = item
            .get("tamanho")
            .and_then(Value::as_u64)
            .ok_or_else(ruim)?;
        let sha256 = item.get("sha256").and_then(Value::as_str);
        let sha256 = sha256.filter(|s| e_hex(s)).ok_or_else(ruim)?;
        if arquivos.iter().any(|e| e.nome == nome) {
            return Err(ruim());
        }
        arquivos.push(Entrada {
            nome: nome.into(),
            tamanho,
            sha256: sha256.into(),
        });
    }
    Ok(Manifesto {
        versao: versao.into(),
        arquivos,
    })
}

/// Uma linha JSON do `jobot ferramentas baixar navegador` (T330).
#[derive(Debug, PartialEq)]
pub enum Linha {
    Progresso { feito: u64, total: Option<u64> },
    Fim(bool),
}

pub fn ler_linha(linha: &str) -> Option<Linha> {
    let conteudo: Value = serde_json::from_str(linha.trim()).ok()?;
    if let Some(fim) = conteudo.get("fim").and_then(Value::as_str) {
        return Some(Linha::Fim(fim == "pronto"));
    }
    if conteudo.get("etapa")?.as_str()? != "navegador" {
        return None;
    }
    Some(Linha::Progresso {
        feito: conteudo.get("feito")?.as_u64()?,
        total: conteudo.get("total").and_then(Value::as_u64),
    })
}

/// A pasta da casca (desenho 6.2): `<dados>/app` no Windows e no Mac (e com `JOBOT_DADOS`);
/// no Linux a vizinha `jobot-app` da pasta de dados (`~/.local/share/jobot-app`).
pub fn pasta_da_casca(env: impl Fn(&str) -> Option<String>, so: &str) -> PathBuf {
    let com_dados = env("JOBOT_DADOS").is_some_and(|v| !v.is_empty());
    let dados = servidor::pasta_de_dados(env, so);
    if com_dados || so == "windows" || so == "macos" {
        dados.join("app")
    } else {
        dados.with_file_name("jobot-app")
    }
}

/// O manifesto dos recursos, só se o sha256 bate com a constante do build e a versão é a da casca.
fn manifesto_da_versao(recursos: &Path, sha_manifesto: &str, versao: &str) -> Option<Manifesto> {
    let bruto = fs::read(recursos.join(MANIFESTO)).ok()?;
    if !e_hex(sha_manifesto) || hex(&Sha256::digest(&bruto)) != sha_manifesto {
        return None;
    }
    ler_manifesto(&bruto).ok().filter(|m| m.versao == versao)
}

/// Para a tela: se os recursos estão completos e quanto ocupam (o navegador, baixado à parte,
/// pela estimativa `TAMANHO_DO_NAVEGADOR`).
pub fn estado(recursos: &Path, sha_manifesto: Option<&str>, versao: &str) -> Value {
    let manifesto = sha_manifesto.and_then(|sha| manifesto_da_versao(recursos, sha, versao));
    let Some(manifesto) = manifesto else {
        return json!({"completo": false});
    };
    let base: u64 = manifesto.arquivos.iter().map(|e| e.tamanho).sum();
    json!({"completo": true, "base": base, "navegador": TAMANHO_DO_NAVEGADOR})
}

/// Escrita atômica (`.tmp` na mesma pasta, `fsync` e troca), 0600 no Linux e no Mac.
pub fn gravar_atomico(destino: &Path, conteudo: &[u8]) -> io::Result<()> {
    let pasta = destino.parent().expect("arquivo dentro de uma pasta");
    fs::create_dir_all(pasta)?;
    let nome = destino
        .file_name()
        .expect("nome do arquivo")
        .to_string_lossy();
    let tmp = pasta.join(format!(".{nome}.tmp"));
    let _ = fs::remove_file(&tmp);
    let mut opcoes = OpenOptions::new();
    opcoes.write(true).create_new(true);
    #[cfg(unix)]
    std::os::unix::fs::OpenOptionsExt::mode(&mut opcoes, 0o600);
    let gravado = opcoes.open(&tmp).and_then(|mut arquivo| {
        arquivo.write_all(conteudo)?;
        arquivo.sync_all()?;
        fs::rename(&tmp, destino)
    });
    if gravado.is_err() {
        let _ = fs::remove_file(&tmp);
    }
    gravado
}

/// Roda o comando sem janela nem entrada, avisa cada linha do stdout e o mata se `cancelado`.
pub fn rodar(
    mut comando: Command,
    cancelado: &AtomicBool,
    linha: &mut dyn FnMut(&str),
) -> Result<Saida, Erro> {
    comando
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    std::os::windows::process::CommandExt::creation_flags(&mut comando, 0x0800_0000); // sem console
    let mut filho = comando.spawn()?;
    let (envia, recebe) = mpsc::channel();
    let stdout = filho.stdout.take().expect("stdout com pipe");
    std::thread::spawn(move || {
        for texto in BufReader::new(stdout).lines().map_while(Result::ok) {
            if envia.send(texto).is_err() {
                break;
            }
        }
    });
    let mut stderr = filho.stderr.take().expect("stderr com pipe");
    let erro = std::thread::spawn(move || {
        let mut texto = String::new();
        let _ = stderr.read_to_string(&mut texto);
        texto
    });
    let mut saida = String::new();
    loop {
        if cancelado.load(Ordering::SeqCst) {
            let _ = filho.kill();
            let _ = filho.wait();
            return Err(Erro::Cancelado);
        }
        match recebe.recv_timeout(Duration::from_millis(100)) {
            Ok(texto) => {
                linha(&texto);
                saida.push_str(&texto);
                saida.push('\n');
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {}
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
    let status = filho.wait()?;
    Ok(Saida {
        codigo: status.code(),
        saida,
        erro: erro.join().unwrap_or_default(),
    })
}

/// O sha256 de um arquivo, avisando os bytes lidos; para se `cancelado`.
fn sha256_de(
    caminho: &Path,
    cancelado: &AtomicBool,
    andou: &mut dyn FnMut(u64),
) -> Result<(String, u64), Erro> {
    let mut arquivo = File::open(caminho)?;
    let mut soma = Sha256::new();
    let mut bloco = vec![0u8; 1 << 20];
    let mut lidos = 0u64;
    loop {
        if cancelado.load(Ordering::SeqCst) {
            return Err(Erro::Cancelado);
        }
        let n = arquivo.read(&mut bloco)?;
        if n == 0 {
            return Ok((hex(&soma.finalize()), lidos));
        }
        soma.update(&bloco[..n]);
        lidos += n as u64;
        andou(n as u64);
    }
}

/// Os arquivos de `pasta`, relativos a `raiz` e com `/`.
fn arquivos_em(raiz: &Path, pasta: &Path, achados: &mut Vec<String>) -> io::Result<()> {
    for item in fs::read_dir(pasta)? {
        let item = item?;
        let caminho = item.path();
        if item.file_type()?.is_dir() {
            arquivos_em(raiz, &caminho, achados)?;
        } else {
            let relativo = caminho.strip_prefix(raiz).expect("dentro da raiz");
            let partes: Vec<_> = relativo.iter().map(|p| p.to_string_lossy()).collect();
            achados.push(partes.join("/"));
        }
    }
    Ok(())
}

/// O manifesto conferido contra a constante do build e cada arquivo contra o manifesto: nome,
/// tamanho e sha256, sem faltar nem sobrar arquivo. Devolve também os bytes do manifesto.
pub fn conferir(
    recursos: &Path,
    sha_manifesto: &str,
    versao: &str,
    cancelado: &AtomicBool,
    progresso: &mut dyn FnMut(Value),
) -> Result<(Manifesto, Vec<u8>), Erro> {
    let ruim = || Erro::Arquivo(MANIFESTO.into());
    let bruto = fs::read(recursos.join(MANIFESTO)).map_err(|_| ruim())?;
    if !e_hex(sha_manifesto) || hex(&Sha256::digest(&bruto)) != sha_manifesto {
        return Err(ruim());
    }
    let manifesto = ler_manifesto(&bruto)?;
    if manifesto.versao != versao {
        return Err(ruim());
    }
    let mut achados = Vec::new();
    arquivos_em(recursos, recursos, &mut achados)?;
    let conhecido =
        |nome: &String| nome == MANIFESTO || manifesto.arquivos.iter().any(|e| &e.nome == nome);
    if let Some(sobra) = achados.into_iter().find(|n| !conhecido(n)) {
        return Err(Erro::Arquivo(sobra));
    }
    let total: u64 = manifesto.arquivos.iter().map(|e| e.tamanho).sum();
    let mut feito = 0u64;
    progresso(json!({"etapa": "conferir", "feito": 0, "total": total}));
    for entrada in &manifesto.arquivos {
        let mut andou = |n: u64| {
            feito += n;
            progresso(json!({"etapa": "conferir", "feito": feito, "total": total}));
        };
        let lido = sha256_de(&recursos.join(&entrada.nome), cancelado, &mut andou);
        match lido {
            Ok((sha, lidos)) if sha == entrada.sha256 && lidos == entrada.tamanho => {}
            Err(Erro::Cancelado) => return Err(Erro::Cancelado),
            _ => return Err(Erro::Arquivo(entrada.nome.clone())),
        }
    }
    Ok((manifesto, bruto))
}

/// Tira um caminho (pasta, arquivo ou atalho) sem seguir atalho.
fn apagar(caminho: &Path) {
    match caminho.symlink_metadata() {
        Ok(m) if m.is_dir() => {
            let _ = fs::remove_dir_all(caminho);
        }
        Ok(_) => {
            // atalho de pasta no Windows (junção) sai com remove_dir
            let _ = fs::remove_file(caminho).or_else(|_| fs::remove_dir(caminho));
        }
        Err(_) => {}
    }
}

fn itens(pasta: &Path) -> Vec<PathBuf> {
    fs::read_dir(pasta)
        .map(|lista| lista.flatten().map(|i| i.path()).collect())
        .unwrap_or_default()
}

/// O texto de um comando que falhou: o stderr (ou o stdout) e o código.
fn falhou(o_que: &str, saida: &Saida) -> Erro {
    let texto = if saida.erro.trim().is_empty() {
        saida.saida.trim()
    } else {
        saida.erro.trim()
    };
    if texto.contains("No space left on device") || texto.contains("os error 112") {
        return Erro::Espaco;
    }
    Erro::Outro(format!("{o_que} ({:?}): {texto}", saida.codigo))
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

    fn python_do_venv(&self) -> PathBuf {
        if self.so == "windows" {
            self.venv().join("Scripts").join("python.exe")
        } else {
            self.venv().join("bin").join("python")
        }
    }

    /// O `uv` da pasta da casca, offline, com as pastas da casca e sem índice nem espelho de fora.
    /// Toda `UV_*` do ambiente da pessoa sai (índice, espelho, `UV_CONSTRAINT`, `UV_NO_BINARY`,
    /// `UV_LINK_MODE`...): só valem as que a casca põe.
    fn comando_uv(&self, argumentos: &[&str]) -> Command {
        let mut comando = Command::new(self.uv());
        servidor::sem_python_de_fora(&mut comando);
        for (nome, _) in std::env::vars_os() {
            if nome.to_string_lossy().starts_with("UV_") {
                comando.env_remove(nome);
            }
        }
        comando
            .env("UV_OFFLINE", "1")
            .env("UV_NO_CONFIG", "1")
            .env("UV_CACHE_DIR", self.pasta.join("cache"))
            .env("UV_PYTHON_INSTALL_DIR", self.pasta.join("python"))
            .args(argumentos);
        comando
    }

    fn comando_jobot(&self, argumentos: &[&str]) -> Command {
        let mut comando = Command::new(servidor::jobot_do_venv(&self.venv(), self.so));
        servidor::sem_python_de_fora(&mut comando).args(argumentos);
        comando
    }

    /// O interpretador que o `uv python install` pôs em `<pasta>/python/cpython-<versão>-...`,
    /// depois de tirar os atalhos `cpython-<maior>.<menor>-...`: com eles o `uv venv` grava o
    /// atalho no `pyvenv.cfg`, e a limpeza do canal `casca` (`casca.limpar`) apagaria a pasta
    /// de verdade (D181).
    fn preparar_interpretador(&self, versao_python: &str) -> Result<PathBuf, Erro> {
        let pythons = self.pasta.join("python");
        let prefixo = format!("cpython-{versao_python}-");
        let mut achado = None;
        for caminho in itens(&pythons) {
            let nome = caminho
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .into_owned();
            let atalho = caminho
                .symlink_metadata()
                .is_ok_and(|m| m.file_type().is_symlink());
            if atalho && nome.starts_with("cpython-") {
                apagar(&caminho);
            } else if !atalho && nome.starts_with(&prefixo) && caminho.is_dir() {
                achado = Some(caminho);
            }
        }
        let pasta =
            achado.ok_or_else(|| Erro::Outro(format!("Python {versao_python} não apareceu")))?;
        Ok(if self.so == "windows" {
            pasta.join("python.exe")
        } else {
            pasta.join("bin").join("python3")
        })
    }

    fn passo(
        &self,
        rodar: &mut Rodar,
        comando: Command,
        o_que: &str,
        cancelado: &AtomicBool,
    ) -> Result<Saida, Erro> {
        if cancelado.load(Ordering::SeqCst) {
            return Err(Erro::Cancelado);
        }
        let saida = rodar(comando, &mut |_| {})?;
        if saida.codigo == Some(0) {
            Ok(saida)
        } else {
            Err(falhou(o_que, &saida))
        }
    }

    /// O passo opcional do navegador: o `jobot ferramentas baixar navegador` do venv, que baixa
    /// o Chromium pelo `playwright install` (com rede, D183.24); o progresso vem das linhas JSON.
    pub fn baixar_navegador(
        &self,
        cancelado: &AtomicBool,
        rodar: &mut Rodar,
        progresso: &mut dyn FnMut(Value),
    ) -> Result<(), Erro> {
        if cancelado.load(Ordering::SeqCst) {
            return Err(Erro::Cancelado);
        }
        progresso(json!({"etapa": "navegador"}));
        let comando = self.comando_jobot(&["ferramentas", "baixar", "navegador"]);
        let mut pronto = false;
        let saida = rodar(comando, &mut |texto| match ler_linha(texto) {
            Some(Linha::Progresso { feito, total }) => {
                progresso(json!({"etapa": "navegador", "feito": feito, "total": total}));
            }
            Some(Linha::Fim(ok)) => pronto = ok,
            None => {}
        })?;
        if saida.codigo != Some(0) || !pronto {
            return Err(match falhou("jobot ferramentas baixar navegador", &saida) {
                Erro::Outro(texto) => Erro::Navegador(texto),
                outro => outro,
            });
        }
        Ok(())
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
        let existia = self.pasta.exists();
        let pythons_antes = itens(&self.pasta.join("python"));
        let feito =
            self.instalar_sem_desfazer(sha_manifesto, navegador, cancelado, rodar, progresso);
        if feito.is_err() {
            if existia {
                apagar(&self.venv());
                for python in itens(&self.pasta.join("python")) {
                    if !pythons_antes.contains(&python) {
                        apagar(&python);
                    }
                }
            } else {
                apagar(self.pasta);
            }
        }
        feito
    }

    fn instalar_sem_desfazer(
        &self,
        sha_manifesto: &str,
        navegador: bool,
        cancelado: &AtomicBool,
        rodar: &mut Rodar,
        progresso: &mut dyn FnMut(Value),
    ) -> Result<(), Erro> {
        let (manifesto, bruto) = conferir(
            self.recursos,
            sha_manifesto,
            self.versao,
            cancelado,
            progresso,
        )?;
        let uv = manifesto.achar(|n| n == UV, "uv")?;
        let python = manifesto.achar(|n| versao_do_python(n).is_some(), "python")?;
        let versao_python = versao_do_python(&python.nome).unwrap_or_default();
        if cancelado.load(Ordering::SeqCst) {
            return Err(Erro::Cancelado);
        }

        progresso(json!({"etapa": "python"}));
        fs::create_dir_all(self.pasta.join("bin"))?;
        tirar_do_tar(&self.recursos.join(&uv.nome), &self.uv())?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(self.uv(), fs::Permissions::from_mode(0o755))?;
        }
        let espelho = tauri::Url::from_file_path(self.recursos.join("python"))
            .map_err(|_| Erro::Outro("caminho dos recursos".into()))?;
        let instalar_python = self.comando_uv(&[
            "python",
            "install",
            "--no-bin",
            "--no-registry", // no Windows, nada no registro (PEP 514) que o desfazer não tire
            "--mirror",
            espelho.as_str(),
            versao_python,
        ]);
        self.passo(rodar, instalar_python, "uv python install", cancelado)?;
        let interpretador = self.preparar_interpretador(versao_python)?;
        apagar(&self.venv());
        let interpretador = interpretador.to_string_lossy();
        let venv = self.venv();
        let criar_venv = self.comando_uv(&[
            "venv",
            "--offline",
            "--python",
            &interpretador,
            &venv.to_string_lossy(),
        ]);
        self.passo(rodar, criar_venv, "uv venv", cancelado)?;

        progresso(json!({"etapa": "jobot"}));
        let python_do_venv = self.python_do_venv();
        let rodas = self.recursos.join("wheels");
        let restricoes = self.recursos.join("restricoes.txt");
        let instalar_jobot = self.comando_uv(&[
            "pip",
            "install",
            "--offline",
            "--python",
            &python_do_venv.to_string_lossy(),
            "--no-index",
            "--find-links",
            &rodas.to_string_lossy(),
            "--require-hashes",
            "-r",
            &restricoes.to_string_lossy(),
        ]);
        self.passo(rodar, instalar_jobot, "uv pip install", cancelado)?;

        // a prova vem antes do navegador: o Chromium fica na pasta do Playwright, que o desfazer
        // não toca (D181.9)
        let prova = self.comando_jobot(&["--version"]);
        let saida = self
            .passo(rodar, prova, "jobot --version", cancelado)
            .map_err(|erro| match erro {
                Erro::Outro(texto) => Erro::Prova(texto),
                outro => outro,
            })?;
        if saida.saida.trim() != format!("jobot {}", self.versao) {
            return Err(Erro::Prova(saida.saida.trim().to_string()));
        }

        if navegador {
            self.baixar_navegador(cancelado, rodar, progresso)?;
        }

        if cancelado.load(Ordering::SeqCst) {
            return Err(Erro::Cancelado);
        }

        let copia = self.pasta.join(format!("manifesto-{}.json", self.versao));
        gravar_atomico(&copia, &bruto)?;
        let texto = |p: &Path| p.to_string_lossy().into_owned();
        let instalacao = json!({
            "canal": "casca",
            "pasta": texto(self.pasta),
            "uv": texto(&self.uv()),
            "venv": texto(&self.venv()),
            "anterior": null,
            "manifesto": texto(&copia),
        });
        let bytes = serde_json::to_vec_pretty(&instalacao).expect("JSON fixo");
        gravar_atomico(&self.dados.join(INSTALACAO), &bytes)?;
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

    fn temporaria(nome: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("jobot-instalar-{nome}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&p);
        fs::create_dir_all(&p).unwrap();
        p
    }

    fn sha(bytes: &[u8]) -> String {
        hex(&Sha256::digest(bytes))
    }

    /// Um tar ustar de um arquivo só, como o `scripts/montar_recursos.py` grava o `uv`.
    fn tar_de_um(nome: &str, dados: &[u8]) -> Vec<u8> {
        let mut tar = vec![0u8; 512];
        tar[..nome.len()].copy_from_slice(nome.as_bytes());
        tar[100..108].copy_from_slice(b"0000755\0");
        tar[124..136].copy_from_slice(format!("{:011o}\0", dados.len()).as_bytes());
        tar[156] = b'0';
        tar[257..263].copy_from_slice(b"ustar\0");
        tar.extend_from_slice(dados);
        tar.resize(tar.len().div_ceil(512) * 512 + 1024, 0);
        tar
    }

    fn arquivos() -> [(&'static str, Vec<u8>); 4] {
        [
            (UV, tar_de_um("uv", b"uv falso")),
            (PYTHON, b"python falso".to_vec()),
            (
                "restricoes.txt",
                b"jobot==0.3.0 --hash=sha256:00\n".to_vec(),
            ),
            (
                "wheels/jobot-0.3.0-py3-none-any.whl",
                b"roda falsa".to_vec(),
            ),
        ]
    }

    #[test]
    fn uv_sai_do_tar_e_tar_estragado_recusa() {
        let raiz = temporaria("tar-do-uv");
        let (tar, uv) = (raiz.join("uv.tar"), raiz.join("uv"));
        fs::write(&tar, tar_de_um("uv", b"uv falso")).unwrap();
        tirar_do_tar(&tar, &uv).unwrap();
        assert_eq!(fs::read(&uv).unwrap(), b"uv falso");
        fs::write(&tar, b"uv solto, sem tar").unwrap();
        assert!(matches!(tirar_do_tar(&tar, &uv), Err(Erro::Arquivo(_))));
        let mut curto = tar_de_um("uv", b"uv falso");
        curto.truncate(515);
        fs::write(&tar, curto).unwrap();
        assert!(matches!(tirar_do_tar(&tar, &uv), Err(Erro::Arquivo(_))));
    }

    #[test]
    fn tar_sem_a_marca_ustar_recusa() {
        let raiz = temporaria("tar-sem-marca");
        let (tar, uv) = (raiz.join("uv.tar"), raiz.join("uv"));
        // tamanho certo, mas sem a marca ustar
        let mut sem_marca = tar_de_um("uv", b"uv falso");
        sem_marca[257..263].fill(0);
        fs::write(&tar, sem_marca).unwrap();
        assert!(matches!(tirar_do_tar(&tar, &uv), Err(Erro::Arquivo(_))));
        assert!(!uv.exists());
    }

    #[test]
    fn tar_com_symlink_recusa() {
        let raiz = temporaria("tar-symlink");
        let (tar, uv) = (raiz.join("uv.tar"), raiz.join("uv"));
        // ustar, mas um symlink em vez de arquivo
        let mut atalho = tar_de_um("uv", b"uv falso");
        atalho[156] = b'2';
        fs::write(&tar, atalho).unwrap();
        assert!(matches!(tirar_do_tar(&tar, &uv), Err(Erro::Arquivo(_))));
        assert!(!uv.exists());
    }

    /// Recursos de mentira com o manifesto certo; devolve o sha256 do manifesto.
    fn montar_recursos(raiz: &Path, versao: &str) -> String {
        let mut lista = Vec::new();
        for (nome, conteudo) in arquivos() {
            let caminho = raiz.join(nome);
            fs::create_dir_all(caminho.parent().unwrap()).unwrap();
            fs::write(&caminho, &conteudo).unwrap();
            lista.push(json!({"nome": nome, "tamanho": conteudo.len(), "sha256": sha(&conteudo)}));
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
                    linha(r#"{"etapa":"navegador","feito":7}"#);
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
        // SAFETY: o std guarda o ambiente com trava própria e nenhum código C dos testes o lê
        unsafe {
            std::env::set_var("UV_NO_BINARY", "1"); // recusaria as wheels
            std::env::set_var("UV_CONSTRAINT", "/outra/restricao.txt");
        }
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
        // no Windows o endereço é `file:///C:/...`, com as barras de URL
        let espelho = tauri::Url::from_file_path(c.recursos.join("python"))
            .unwrap()
            .to_string();
        let esperado = vec![
            v(&[
                &uv,
                "python",
                "install",
                "--no-bin",
                "--no-registry",
                "--mirror",
                &espelho,
                "3.14.7",
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
            v(&[&jobot, "--version"]),
            // sem arquivo dos recursos: o navegador vem do `playwright install` (D183.24)
            v(&[&jobot, "ferramentas", "baixar", "navegador"]),
        ];
        assert_eq!(argvs(&feitos), esperado);
        // o uv roda offline, com as pastas da casca e sem nenhuma UV_* da pessoa
        for (argv, ambiente) in feitos.borrow().iter().take(3) {
            let valor = |k: &str| ambiente.get(k).cloned().flatten();
            assert_eq!(valor("UV_OFFLINE").as_deref(), Some("1"), "{argv:?}");
            assert_eq!(valor("UV_NO_CONFIG").as_deref(), Some("1"));
            assert_eq!(valor("UV_CACHE_DIR"), Some(texto(&c.pasta.join("cache"))));
            assert_eq!(
                valor("UV_PYTHON_INSTALL_DIR"),
                Some(texto(&c.pasta.join("python")))
            );
            for fora in ["UV_NO_BINARY", "UV_CONSTRAINT"] {
                assert_eq!(ambiente.get(fora), Some(&None), "{fora}");
            }
        }
        // o PYTHONHOME, o PYTHONPATH e o LD_LIBRARY_PATH do AppImage nunca chegam ao uv nem ao
        // jobot (D183.18)
        for (argv, ambiente) in feitos.borrow().iter() {
            for fora in ["LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"] {
                assert_eq!(ambiente.get(fora), Some(&None), "{fora} {argv:?}");
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
        assert!(avisos.contains(&json!({"etapa": "navegador", "feito": 7, "total": null})));
        let total: u64 = arquivos().iter().map(|(_, c)| c.len() as u64).sum();
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
        // motivo próprio: a tela diz que o navegador vem da internet (D183.24)
        assert!(
            matches!(&r, Err(Erro::Navegador(t)) if t.contains("deu errado")),
            "{r:?}"
        );
        assert_eq!(r.unwrap_err().codigo(), "navegador");
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
        let total: u64 = arquivos().iter().map(|(_, c)| c.len() as u64).sum();
        assert_eq!(
            estado(&c.recursos, Some(c.sha.as_str()), VERSAO),
            json!({"completo": true, "base": total, "navegador": TAMANHO_DO_NAVEGADOR})
        );
        assert_eq!(
            estado(&c.recursos, None, VERSAO),
            json!({"completo": false})
        );
        assert_eq!(
            estado(&c.recursos, Some(""), VERSAO),
            json!({"completo": false})
        );
        // manifesto adulterado (sha256 diferente da constante do build)
        assert_eq!(
            estado(&c.recursos, Some(sha(b"outro").as_str()), VERSAO),
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
