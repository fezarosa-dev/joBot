// Tela de instalação da casca (desenho 5.2; T336). Fala com a casca pelos comandos
// `estado_instalador`, `instalar` e `fechar_instalador` (window.__TAURI__.core), que só as
// páginas locais alcançam. O progresso chega por um canal: {"etapa", "feito", "total"} e, no fim,
// {"fim": "pronto"} ou {"fim": "falhou", "motivo"}. Só o navegador (D183.24) e o Modelo local
// (desenho 10.1), opcionais, vêm da internet; o resto não usa a rede (D174.1). O modelo baixa
// depois de o joBot instalado: {"fim": "pronto", "ia_local": motivo} diz que ele não baixou.
(() => {
  "use strict";
  // fatia fixa de cada etapa (proposta, D181 e D205); sem o navegador ou o modelo, as outras
  // dividem o todo
  const PESOS = { conferir: 10, python: 20, jobot: 30, navegador: 35, ia_local: 60, abrir: 5 };
  const ORDEM = ["conferir", "python", "jobot", "navegador", "ia_local", "abrir"];
  const TETO = 99; // a barra só chega a 100 no fim
  const FATOR_DISCO = 3; // arquivos compactados -> espaço instalado (aproximado, D181)
  const MOTIVOS = ["arquivo", "espaco", "prova", "navegador", "outro"];
  // os motivos do `jobot ferramentas baixar ia-local` (sistema/baixar.py e cli/ferramentas.py)
  const MOTIVOS_IA = [
    "sem_rede", "espaco", "arquivo", "ocupado", "programa_ausente", "modelo_ausente",
  ];
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
  let iaFalhou = null; // o motivo, quando o Modelo local não baixou

  const t = (chave, params = {}) =>
    Object.entries(params).reduce(
      (texto, [nome, v]) => texto.split(`{${nome}}`).join(String(v)),
      textos[chave] ?? chave,
    );

  const navegador = () => $("ferramenta-navegador").checked;
  const modeloLocal = () => !$("grupo-ia").hidden && $("ferramenta-ia-local").checked;

  // bytes já no tamanho em disco
  const formatar = (bytes) => {
    const mb = bytes / 1e6;
    const formato = new Intl.NumberFormat(document.documentElement.lang, {
      maximumFractionDigits: mb >= 1000 ? 1 : 0,
    });
    return mb >= 1000 ? `${formato.format(mb / 1000)} GB` : `${formato.format(Math.ceil(mb))} MB`;
  };
  // os compactados viram o espaço instalado pelo fator; o modelo (GGUF) ocupa o que baixa
  const tamanho = (bytes) => t("ferramentas.tamanho", { tamanho: formatar(bytes * FATOR_DISCO) });

  // os tamanhos do Modelo local no manifesto (o llama-server e cada modelo); sem eles, null
  function iaLocal() {
    const ia = estado.ia_local;
    const modelos = Object.values((ia && ia.modelos) || {}).filter((n) => n > 0);
    if (!ia || !(ia.servidor > 0) || !modelos.length) return null;
    // o modelo sai da memória do computador, que esta tela não lê: conta o maior
    const ate = Math.max(...modelos);
    return { de: Math.min(...modelos), ate, disco: ia.servidor * FATOR_DISCO + ate };
  }

  function desenharRodape() {
    const base = estado.base || 0;
    const nav = estado.navegador || 0;
    const ia = iaLocal();
    $("grupo-ia").hidden = !ia;
    $("tamanho-jobot").textContent = tamanho(base);
    $("tamanho-navegador").textContent = tamanho(nav);
    if (ia) {
      const disco = formatar(ia.disco);
      $("tamanho-ia-local").textContent = t("ferramentas.tamanho_ate", { tamanho: disco });
      $("frase-ia-local").textContent = t("ferramentas.ia_local_frase", {
        de: formatar(ia.de),
        ate: formatar(ia.ate),
      });
    }
    $("onde-fica").textContent = estado.dados || "";
    const total = (base + (navegador() ? nav : 0)) * FATOR_DISCO + (modeloLocal() ? ia.disco : 0);
    $("espaco").textContent = t("ferramentas.tamanho", { tamanho: formatar(total) });
  }

  function desenharPronto() {
    const motivo = MOTIVOS_IA.includes(iaFalhou) ? iaFalhou : "outro";
    const texto = t("pronto.ia_local", { motivo: t(`ia_local.motivo.${motivo}`) });
    $("pronto-ia").textContent = iaFalhou ? texto : "";
    $("pronto-ia").hidden = !iaFalhou;
    $("pronto-abrindo").hidden = Boolean(iaFalhou);
  }

  // no download do modelo o joBot já está instalado: parar não desfaz nada (D185.17)
  function desenharAlerta() {
    const sufixo = etapa === "ia_local" ? "_ia" : "";
    $("alerta-titulo").textContent = t(`alerta.titulo${sufixo}`);
    $("alerta-texto").textContent = t(`alerta.texto${sufixo}`);
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
    desenharPronto();
    desenharAlerta();
  }

  function mostrarPasso(nome) {
    for (const secao of document.querySelectorAll("[data-passo]")) {
      secao.hidden = secao.dataset.passo !== nome;
    }
    const visiveis = [...(BOTOES[nome] || [])];
    if (nome === "pronto" && iaFalhou) visiveis.push("abrir");
    // sem rede, tentar de novo com o navegador falha sempre: a saída fica na própria tela (D183.24)
    if (nome === "falha" && motivo === "navegador") visiveis.push("sem-navegador");
    for (const id of ["continuar", "instalar", "tentar", "voltar", "sem-navegador", "abrir"]) {
      $(id).hidden = !visiveis.includes(id);
    }
    document.querySelector(`[data-passo="${nome}"] [tabindex="-1"]`)?.focus();
  }

  // a barra nunca volta e fica no teto até o fim; nas etapas do uv a fatia se completa quando
  // a etapa seguinte começa
  function calcular(nome, feito, total) {
    const etapas = ORDEM.filter(
      (e) => (e !== "navegador" || navegador()) && (e !== "ia_local" || modeloLocal()),
    );
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
      iaFalhou = typeof aviso.ia_local === "string" ? aviso.ia_local : null;
      desenharPronto();
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
    iaFalhou = null;
    valor = 0;
    etapa = null;
    aplicar();
    mostrarPasso("instalando");
    aoAviso({ etapa: "conferir" });
    const canal = new core.Channel();
    canal.onmessage = aoAviso;
    try {
      await core.invoke("instalar", {
        navegador: navegador(),
        modelo_local: modeloLocal(),
        progresso: canal,
      });
    } catch {
      aoAviso({ fim: "falhou", motivo: "outro" });
    }
  }

  const fechar = () => core?.invoke("fechar_instalador");
  // a casca chama esta função quando a pessoa fecha a janela no meio (main.rs, on_window_event)
  window.__jobotPedirFechar = () => {
    if (instalando) {
      desenharAlerta();
      $("alerta-fechar").showModal();
    } else fechar();
  };

  $("continuar").addEventListener("click", () => mostrarPasso("ferramentas"));
  $("voltar").addEventListener("click", () => mostrarPasso("boas-vindas"));
  $("instalar").addEventListener("click", instalar);
  $("tentar").addEventListener("click", instalar);
  $("sem-navegador").addEventListener("click", () => {
    $("ferramenta-navegador").checked = false;
    desenharRodape();
    instalar();
  });
  $("ferramenta-navegador").addEventListener("change", desenharRodape);
  $("ferramenta-ia-local").addEventListener("change", desenharRodape);
  // o mesmo caminho da casca quando tudo deu (main.rs): confere a janela e abre o painel
  $("abrir").addEventListener("click", () => {
    location.href = "verificar.html";
  });
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
