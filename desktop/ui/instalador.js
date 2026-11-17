// Tela de instalação da casca (desenho 5.2; T336). Fala com a casca pelos comandos
// `estado_instalador`, `instalar` e `fechar_instalador` (window.__TAURI__.core), que só as
// páginas locais alcançam. O progresso chega por um canal: {"etapa", "feito", "total"} e, no fim,
// {"fim": "pronto"} ou {"fim": "falhou", "motivo"}. Só o navegador, opcional, vem da internet
// (D183.24); o resto não usa a rede (D174.1).
(() => {
  "use strict";
  // fatia fixa de cada etapa (proposta, D181); sem o navegador, as outras dividem o todo
  const PESOS = { conferir: 10, python: 20, jobot: 30, navegador: 35, abrir: 5 };
  const ORDEM = ["conferir", "python", "jobot", "navegador", "abrir"];
  const TETO = 99; // a barra só chega a 100 no fim
  const FATOR_DISCO = 3; // arquivos compactados -> espaço instalado (aproximado, D181)
  const MOTIVOS = ["arquivo", "espaco", "prova", "navegador", "outro"];
  const BOTOES = {
    "boas-vindas": ["continuar"],
    ferramentas: ["instalar", "voltar"],
    falha: ["tentar"],
  };

  const core = window.__TAURI__ && window.__TAURI__.core;
  const $ = (id) => document.getElementById(id);
  let textos = {};
  let estado = { completo: false };
  let valor = 0;
  let etapa = null;
  let motivo = null;
  let instalando = false;
  let parando = false;
  let detalhe = "";

  const t = (chave, params = {}) =>
    Object.entries(params).reduce(
      (texto, [nome, v]) => texto.split(`{${nome}}`).join(String(v)),
      textos[chave] ?? chave,
    );

  const navegador = () => $("ferramenta-navegador").checked;

  const tamanho = (bytes) => {
    const mb = (bytes * FATOR_DISCO) / 1e6;
    const formato = new Intl.NumberFormat(document.documentElement.lang, {
      maximumFractionDigits: mb >= 1000 ? 1 : 0,
    });
    const texto = mb >= 1000 ? `${formato.format(mb / 1000)} GB` : `${formato.format(Math.ceil(mb))} MB`;
    return t("ferramentas.tamanho", { tamanho: texto });
  };

  function desenharRodape() {
    const base = estado.base || 0;
    const nav = estado.navegador || 0;
    $("tamanho-jobot").textContent = tamanho(base);
    $("tamanho-navegador").textContent = tamanho(nav);
    $("onde-fica").textContent = estado.dados || "";
    $("espaco").textContent = tamanho(base + (navegador() ? nav : 0));
  }

  function desenharFalha() {
    if (!motivo) return;
    $("falha-titulo").textContent = t(`falha.${motivo}`);
    $("falha-oque").textContent = t(`falha.${motivo}_oque`);
    $("falha-detalhe-texto").textContent = detalhe;
    $("falha-detalhe").hidden = !detalhe;
  }

  function desenharEtapa() {
    if (!etapa && !parando) return;
    const linha = $("instalador-linha");
    linha.textContent = parando ? t("parando") : t(`etapa.${etapa}`);
    linha.title = linha.textContent;
  }

  async function carregarTextos(idioma) {
    const resposta = await fetch(`i18n/${idioma}.json`);
    textos = await resposta.json();
    document.documentElement.lang = idioma;
    $("idioma").value = idioma;
    for (const el of document.querySelectorAll("[data-t]")) el.textContent = t(el.dataset.t);
    for (const el of document.querySelectorAll("[data-t-rotulo]")) {
      el.setAttribute("aria-label", t(el.dataset.tRotulo));
    }
    desenharRodape();
    desenharFalha();
    desenharEtapa();
  }

  function mostrarPasso(nome) {
    for (const secao of document.querySelectorAll("[data-passo]")) {
      secao.hidden = secao.dataset.passo !== nome;
    }
    const visiveis = BOTOES[nome] || [];
    for (const id of ["continuar", "instalar", "tentar", "voltar"]) $(id).hidden = !visiveis.includes(id);
    document.querySelector(`[data-passo="${nome}"] [tabindex="-1"]`)?.focus();
  }

  // a barra nunca volta e fica no teto até o fim; nas etapas do uv a fatia se completa quando
  // a etapa seguinte começa
  function calcular(nome, feito, total) {
    const etapas = ORDEM.filter((e) => e !== "navegador" || navegador());
    const i = etapas.indexOf(nome);
    if (i < 0) return valor;
    const soma = etapas.reduce((s, e) => s + PESOS[e], 0);
    const antes = etapas.slice(0, i).reduce((s, e) => s + PESOS[e], 0);
    const fracao = total > 0 ? Math.min(feito / total, 1) : 0;
    return ((antes + PESOS[nome] * fracao) / soma) * 100;
  }

  function aplicar() {
    $("trilho").setAttribute("aria-valuenow", String(valor));
    $("instalador-preenchimento").style.inlineSize = `${valor}%`;
  }

  function aoAviso(aviso) {
    if (aviso.fim === "pronto") {
      instalando = false;
      valor = 100;
      aplicar();
      mostrarPasso("pronto");
      return;
    }
    if (aviso.fim === "falhou") {
      instalando = false;
      motivo = MOTIVOS.includes(aviso.motivo) ? aviso.motivo : "outro";
      detalhe = typeof aviso.detalhe === "string" ? aviso.detalhe : "";
      desenharFalha();
      mostrarPasso("falha");
      return;
    }
    if (parando || !ORDEM.includes(aviso.etapa)) return;
    if (aviso.etapa !== etapa) {
      etapa = aviso.etapa;
      desenharEtapa();
      $("etapa-viva").textContent = t(`etapa.${etapa}`); // a região viva diz só o nome da etapa
    }
    valor = Math.min(TETO, Math.max(valor, Math.floor(calcular(etapa, aviso.feito || 0, aviso.total || 0))));
    aplicar();
  }

  async function instalar() {
    instalando = true;
    parando = false;
    valor = 0;
    etapa = null;
    aplicar();
    mostrarPasso("instalando");
    aoAviso({ etapa: "conferir" });
    const canal = new core.Channel();
    canal.onmessage = aoAviso;
    try {
      await core.invoke("instalar", { navegador: navegador(), progresso: canal });
    } catch {
      aoAviso({ fim: "falhou", motivo: "outro" });
    }
  }

  const fechar = () => core?.invoke("fechar_instalador");
  // a casca chama esta função quando a pessoa fecha a janela no meio (main.rs, on_window_event)
  window.__jobotPedirFechar = () => {
    if (instalando) $("alerta-fechar").showModal();
    else fechar();
  };

  $("continuar").addEventListener("click", () => mostrarPasso("ferramentas"));
  $("voltar").addEventListener("click", () => mostrarPasso("boas-vindas"));
  $("instalar").addEventListener("click", instalar);
  $("tentar").addEventListener("click", instalar);
  $("ferramenta-navegador").addEventListener("change", desenharRodape);
  $("idioma").addEventListener("change", (evento) => carregarTextos(evento.target.value));
  $("fechar-janela").addEventListener("click", () => window.__jobotPedirFechar());
  $("alerta-continuar").addEventListener("click", () => $("alerta-fechar").close());
  $("alerta-parar").addEventListener("click", () => {
    $("alerta-fechar").close();
    if (instalando) {
      // o desfazer apaga o venv antes de a janela fechar: a pessoa vê que pediu
      parando = true;
      desenharEtapa();
      $("etapa-viva").textContent = t("parando");
    }
    fechar();
  });
  // no Mac a janela tem os botões do sistema (Overlay): o "Fechar" da faixa sairia repetido
  $("fechar-janela").hidden = / \(macos\)$/.test(navigator.userAgent);

  (async () => {
    await carregarTextos(/^pt\b/i.test(navigator.language || "") ? "pt" : "en");
    try {
      estado = core ? await core.invoke("estado_instalador") : estado;
    } catch {
      estado = { completo: false };
    }
    desenharRodape();
    mostrarPasso(estado.completo ? "boas-vindas" : "incompleto");
  })();
})();
