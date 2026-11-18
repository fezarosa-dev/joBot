// O controle da casca (T350; D206, ADR 0027). Fala com a casca pelos comandos
// `estado_controle`, `ligar`, `parar` e `abrir_jobot` (window.__TAURI__.core), que só as páginas
// locais alcançam. Cada um devolve {"ligado", "endereco"} e, se deu errado, {"falha", "detalhe",
// "log"}. Ao abrir, só pergunta o estado: não liga nem abre nada sozinho.
(() => {
  "use strict";
  // o mesmo `codigo` de servidor::Falha, o `abrir` do abridor do navegador, o `parar` do Parar
  // que não parou e o `outro`, para resposta que não veio ou motivo que a página não conhece
  const MOTIVOS = [
    "instalar", "porta", "captura", "sem_resposta", "saiu", "subir", "abrir", "parar", "outro",
  ];
  const INTERVALO = 3000; // de quanto em quanto tempo o controle confere se o painel caiu

  const core = window.__TAURI__ && window.__TAURI__.core;
  const $ = (id) => document.getElementById(id);
  let textos = {};
  let estado = { ligado: false, endereco: "" };
  let ocupado = null; // "ligando" ou "parando" enquanto a casca trabalha
  let falha = null;

  const t = (chave, params = {}) =>
    Object.entries(params).reduce(
      (texto, [nome, v]) => texto.split(`{${nome}}`).join(String(v)),
      textos[chave] ?? chave,
    );

  // só troca o texto quando ele muda: o leitor de tela não repete o estado a cada consulta
  const escrever = (el, texto) => {
    if (el.textContent !== texto) el.textContent = texto;
  };

  function desenhar() {
    const nome = ocupado || (estado.ligado ? "ligado" : "parado");
    escrever($("estado"), t(`controle.${nome}`));
    document.body.dataset.estado = nome;
    if ($("endereco").value !== estado.endereco) $("endereco").value = estado.endereco || "";
    $("ligar").disabled = Boolean(ocupado) || estado.ligado;
    $("parar").disabled = Boolean(ocupado) || !estado.ligado;
    $("abrir").hidden = Boolean(ocupado) || !estado.ligado;
    $("falha").hidden = !falha;
    if (falha) {
      const motivo = MOTIVOS.includes(falha.falha) ? falha.falha : "outro";
      escrever($("falha-texto"), t(`controle.falha.${motivo}`, { detalhe: falha.detalhe || "" }));
      $("falha-log").textContent = falha.log || "";
      $("falha-registro").hidden = !falha.log;
    }
  }

  async function chamar(comando) {
    try {
      return core ? await core.invoke(comando) : null;
    } catch {
      return null;
    }
  }

  async function consultar() {
    if (ocupado || document.hidden) return;
    const novo = await chamar("estado_controle");
    if (novo && !ocupado) {
      // o painel mudou sozinho (o Ligar que estourou o prazo terminou de subir): a falha velha sai
      if (Boolean(novo.ligado) !== estado.ligado) falha = null;
      estado = { ligado: Boolean(novo.ligado), endereco: novo.endereco || estado.endereco };
      desenhar();
    }
  }

  // o foco não se perde quando o botão apertado fica desativado: vai para o próximo passo
  async function agir(comando, nome, depois) {
    ocupado = nome;
    falha = null;
    desenhar();
    const resposta = await chamar(comando);
    ocupado = null;
    if (resposta) {
      estado = { ligado: Boolean(resposta.ligado), endereco: resposta.endereco || estado.endereco };
      falha = resposta.falha ? resposta : null;
    } else {
      falha = { falha: "outro" };
    }
    desenhar();
    const alvo = [depois(), "ligar", "parar"].map($).find((el) => !el.hidden && !el.disabled);
    alvo?.focus();
  }

  async function copiar() {
    const campo = $("endereco");
    try {
      await navigator.clipboard.writeText(campo.value);
    } catch {
      campo.select(); // sem a área de transferência da página: o jeito antigo
      document.execCommand("copy");
    }
    $("copiado").textContent = t("controle.copiado");
    setTimeout(() => ($("copiado").textContent = ""), INTERVALO);
  }

  // o idioma escolhido na tela de instalação, que abre na mesma origem (D207.9)
  function idiomaGuardado() {
    try {
      const idioma = localStorage.getItem("jobot.idioma");
      return ["pt", "en"].includes(idioma) ? idioma : null;
    } catch {
      return null;
    }
  }

  async function carregarTextos(idioma) {
    const resposta = await fetch(`i18n/${idioma}.json`);
    textos = await resposta.json();
    document.documentElement.lang = idioma;
    for (const el of document.querySelectorAll("[data-t]")) el.textContent = t(el.dataset.t);
    desenhar();
  }

  $("ligar").addEventListener("click", () => agir("ligar", "ligando", () => "abrir"));
  $("parar").addEventListener("click", () => agir("parar", "parando", () => "ligar"));
  $("abrir").addEventListener("click", () => agir("abrir_jobot", null, () => "abrir"));
  $("copiar").addEventListener("click", copiar);
  document.addEventListener("visibilitychange", consultar);

  (async () => {
    const doSistema = /^pt\b/i.test(navigator.language || "") ? "pt" : "en";
    await carregarTextos(idiomaGuardado() || doSistema);
    await consultar();
    setInterval(consultar, INTERVALO);
  })();
})();
