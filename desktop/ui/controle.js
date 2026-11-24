// O controle da casca (T350; D206, ADR 0027). Fala com a casca pelos comandos
// `estado_controle`, `ligar`, `parar`, `abrir_jobot` e `abrir_release` (window.__TAURI__.core), que
// só as páginas locais alcançam. Cada um devolve {"ligado", "endereco"} e, se deu errado,
// {"falha", "detalhe", "log"}; a consulta traz também os avisos `janela_velha` (o painel no ar é
// mais novo que esta casca, D207.12). Fechar a janela com o painel no ar pergunta antes (D215): a
// casca chama `window.__jobotPedirFechar` e a resposta volta por `fechar_controle`.
// Ao abrir, só pergunta o estado: não liga nem abre nada sozinho.
(() => {
  "use strict";
  // o mesmo `codigo` de servidor::Falha, o `abrir` do abridor do navegador, o `release` da
  // página da janela nova, o `parar` do Parar que não parou e o `outro`, para resposta que não
  // veio ou motivo que a página não conhece
  const MOTIVOS = [
    "instalar", "porta", "captura", "sem_resposta", "saiu", "subir", "abrir", "release", "parar",
    "outro",
  ];
  const INTERVALO = 3000; // de quanto em quanto tempo o controle confere se o painel caiu

  const core = window.__TAURI__ && window.__TAURI__.core;
  const $ = (id) => document.getElementById(id);
  let textos = {};
  let estado = { ligado: false, endereco: "", janelaVelha: false };
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
    $("janela-nova").hidden = !estado.ligado || !estado.janelaVelha;
    $("falha").hidden = !falha;
    if (falha) {
      const motivo = MOTIVOS.includes(falha.falha) ? falha.falha : "outro";
      escrever($("falha-texto"), t(`controle.falha.${motivo}`, { detalhe: falha.detalhe || "" }));
      $("falha-log").textContent = falha.log || "";
      $("falha-registro").hidden = !falha.log;
    }
  }

  // a resposta sem os avisos (a do Abrir joBot) mantém os da última consulta
  const ler = (r) => ({
    ligado: Boolean(r.ligado),
    endereco: r.endereco || estado.endereco,
    janelaVelha: Boolean(r.janela_velha ?? estado.janelaVelha),
  });

  async function chamar(comando, argumentos) {
    try {
      return core ? await core.invoke(comando, argumentos) : null;
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
      estado = ler(novo);
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
      estado = ler(resposta);
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
  $("baixar").addEventListener("click", () => agir("abrir_release", null, () => "baixar"));
  $("copiar").addEventListener("click", copiar);

  // D215: com o painel no ar, Deixar ligado ou Desligar; o Esc do diálogo cancela o fechar
  const pergunta = $("pergunta-fechar");
  const fechar = (desligar) => chamar("fechar_controle", { desligar });
  window.__jobotPedirFechar = () => {
    if (!estado.ligado) fechar(false);
    else if (!pergunta.open) {
      // sem `showModal` (WebView antigo) ou se ele lançar, fecha sem perguntar (D217)
      try {
        pergunta.showModal();
      } catch {
        fechar(false);
      }
    }
  };
  $("deixar-ligado").addEventListener("click", () => {
    pergunta.close();
    fechar(false);
  });
  $("desligar").addEventListener("click", () => {
    pergunta.close();
    fechar(true);
  });
  document.addEventListener("visibilitychange", consultar);

  (async () => {
    const doSistema = /^pt\b/i.test(navigator.language || "") ? "pt" : "en";
    await carregarTextos(idiomaGuardado() || doSistema);
    await consultar();
    setInterval(consultar, INTERVALO);
  })();
})();
