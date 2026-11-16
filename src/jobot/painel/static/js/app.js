// O único JavaScript próprio do painel (desenho 13.1). Sem script inline: o CSP só aceita 'self'.
(() => {
  "use strict";

  const token = document.querySelector('meta[name="csrf-token"]')?.content ?? "";

  // token CSRF em todo pedido do HTMX (desenho 14.4)
  document.addEventListener("htmx:configRequest", (evento) => {
    evento.detail.headers["X-CSRF-Token"] = token;
  });

  // depois de uma troca, o foco vai para o [data-foco] do trecho novo, se ele tiver um;
  // trecho sem [data-foco] (ex.: andamento que atualiza sozinho) não rouba o foco.
  // Com hx-swap="outerHTML" o alvo é o nó antigo, já fora do DOM: aí vale o nó do evento
  document.addEventListener("htmx:afterSwap", (evento) => {
    const alvo = evento.detail.target;
    const raiz = alvo && alvo.isConnected ? alvo : evento.target;
    if (!raiz) return;
    const foco = raiz.matches("[data-foco]") ? raiz : raiz.querySelector("[data-foco]");
    if (!foco) return;
    if (!foco.matches("a[href], button, input, select, textarea, [tabindex]")) {
      foco.setAttribute("tabindex", "-1");
    }
    foco.focus();
  });

  // chips de filtro (T191): chegam num segundo pedido, depois da lista. O clique troca o miolo e o
  // chip focado some do DOM; o HTMX só devolve o foco a quem existe na troca. Guardo o id do chip
  // focado e, quando o fragmento dos chips chega (o de espera tem aria-busy), devolvo o foco a ele.
  let chipFocado = null;
  document.addEventListener("htmx:beforeRequest", (evento) => {
    const no = evento.detail.elt;
    if (no?.matches?.("button.chip[id]") && document.activeElement === no) chipFocado = no.id;
  });
  document.addEventListener("htmx:afterRequest", (evento) => {
    if (!evento.detail.successful && evento.detail.elt?.id === chipFocado) chipFocado = null;
  });
  document.addEventListener("htmx:afterSwap", (evento) => {
    const no = evento.target;
    if (!chipFocado || no?.id !== "filtros-chips" || no.getAttribute("aria-busy") === "true") return;
    const chip = document.getElementById(chipFocado);
    chipFocado = null;
    if (chip && document.activeElement === document.body) chip.focus();
  });

  // se o pedido dos chips falhar, o contêiner de espera não fica ocupado para sempre: o aviso global
  // de erro (mais abaixo) já fala do erro; aqui só sai o aria-busy e o texto de espera
  const chipsFalhou = (evento) => {
    const no = evento.detail.elt;
    if (no?.id !== "filtros-chips" || no.getAttribute("aria-busy") !== "true") return;
    no.removeAttribute("aria-busy");
    no.querySelector("[data-espera]")?.setAttribute("hidden", "");
  };
  document.addEventListener("htmx:responseError", chipsFalhou);
  document.addEventListener("htmx:sendError", chipsFalhou);

  // mensagem passageira ("Salvo."): o [data-some-sozinho] que está na página ao carregar, que chegou
  // numa troca ou numa troca fora de banda (OOB) some 5 s depois (tempo para o leitor de tela); o nó
  // em volta continua no lugar. Mostrada a mensagem, o ?salvo= sai da URL (os outros parâmetros e o
  // hash ficam), para recarregar ou voltar não repetir o "Salvo."
  const agendados = new WeakSet();
  const agendarSumico = () => {
    for (const no of document.querySelectorAll("[data-some-sozinho]:not([hidden])")) {
      if (agendados.has(no)) continue;
      agendados.add(no);
      setTimeout(() => {
        no.hidden = true;
      }, 5000);
    }
    const url = new URL(location.href);
    if (url.searchParams.has("salvo")) {
      url.searchParams.delete("salvo");
      history.replaceState(history.state, "", url);
    }
  };
  agendarSumico();
  document.addEventListener("htmx:afterSwap", agendarSumico);
  document.addEventListener("htmx:oobAfterSwap", agendarSumico);
  document.addEventListener("htmx:historyRestore", agendarSumico);
  // o snapshot do histórico não guarda a mensagem passageira (senão a volta a mostraria de novo)
  document.addEventListener("htmx:beforeHistorySave", () => {
    for (const no of document.querySelectorAll("[data-some-sozinho]")) no.hidden = true;
  });

  // botão olho: mostra ou oculta o que foi digitado no campo que ele controla (aria-controls);
  // o estado vive só no aria-pressed e o campo é buscado na hora (a troca do cartão o recria)
  document.addEventListener("click", (evento) => {
    const olho = evento.target.closest("[data-olho]");
    if (!olho) return;
    const campo = document.getElementById(olho.getAttribute("aria-controls"));
    if (!campo) return;
    const mostrar = campo.type === "password";
    campo.type = mostrar ? "text" : "password";
    olho.setAttribute("aria-pressed", String(mostrar));
  });

  // botão com texto de espera (.botao-espera): enquanto o pedido corre, o rótulo sai do nome acessível
  // e o leitor de tela só ouve a espera; no fim o rótulo volta e, se o foco estava no botão (que o
  // HTMX desativa), ele volta para lá. queueMicrotask: o HTMX reabilita o botão no mesmo ciclo
  const comEspera = (evento) => {
    const botao = evento.target;
    return botao instanceof HTMLElement && botao.querySelector(".botao-espera") ? botao : null;
  };
  const tinhaFoco = new WeakSet();
  document.addEventListener("htmx:beforeRequest", (evento) => {
    const botao = comEspera(evento);
    if (!botao) return;
    if (document.activeElement === botao) tinhaFoco.add(botao);
    botao.querySelector(".botao-rotulo")?.setAttribute("aria-hidden", "true");
  });
  document.addEventListener("htmx:afterRequest", (evento) => {
    const botao = comEspera(evento);
    if (!botao) return;
    botao.querySelector(".botao-rotulo")?.removeAttribute("aria-hidden");
    if (!tinhaFoco.delete(botao)) return;
    queueMicrotask(() => botao.focus());
  });

  // erro de um clique do HTMX (T151; D106): o aviso fixo da casca mostra o texto que o servidor
  // mandou em <p data-aviso-erro> ou, sem ele, o genérico da faixa do status. Só textContent.
  // Voltar/avançar troca o conteúdo do body (push-url sem hx-history-elt): o nó é buscado na hora,
  // o botão fechar usa delegação e o aviso é escondido antes de o histórico guardar a página.
  // Depois de fechado, o mesmo texto não reabre (polling e carga com o servidor fora do ar errariam a
  // cada 2 s): `fechado` guarda o texto que a pessoa fechou; um aviso novo (texto diferente) ou um
  // pedido que dá certo zera. Todo erro continua aparecendo; só não insiste depois de fechado.
  // shortcut: guarda só um texto; dois erros diferentes que se alternam reabrem a cada ciclo, trocar por um conjunto se aparecer
  let fechado = null;
  const textoDoAviso = (aviso) => aviso.querySelector("[data-aviso-texto]");
  const mostrarAviso = (chave, texto) => {
    const aviso = document.getElementById("aviso-erro");
    if (!aviso) return;
    const final = texto || aviso.getAttribute(chave);
    if (final === fechado) return;
    fechado = null;
    textoDoAviso(aviso).textContent = final;
    aviso.hidden = false;
  };
  document.addEventListener("htmx:responseError", (evento) => {
    const xhr = evento.detail.xhr;
    const doc = new DOMParser().parseFromString(xhr.responseText ?? "", "text/html");
    const texto = doc.querySelector("[data-aviso-erro]")?.textContent.trim();
    mostrarAviso(xhr.status < 500 ? "data-msg-4xx" : "data-msg-5xx", texto);
  });
  document.addEventListener("htmx:sendError", () => mostrarAviso("data-msg-rede"));
  document.addEventListener("htmx:beforeHistorySave", () => {
    const aviso = document.getElementById("aviso-erro");
    if (aviso) aviso.hidden = true;
  });
  document.addEventListener("htmx:afterRequest", (evento) => {
    if (evento.detail.successful) fechado = null;
  });
  document.addEventListener("click", (evento) => {
    if (!evento.target.closest("[data-aviso-fechar]")) return;
    const aviso = document.getElementById("aviso-erro");
    fechado = textoDoAviso(aviso).textContent;
    aviso.hidden = true;
  });

  // tecla "/" vai para a busca ([data-busca]), fora de campos de texto
  document.addEventListener("keydown", (evento) => {
    if (evento.key !== "/" || evento.ctrlKey || evento.metaKey || evento.altKey) return;
    const ativo = document.activeElement;
    if (ativo && (ativo.isContentEditable || ativo.matches("input, textarea, select"))) return;
    const busca = document.querySelector("[data-busca]");
    if (!busca) return;
    evento.preventDefault();
    busca.focus();
  });

  // chave de tema: troca na hora, sem esperar a volta do servidor
  document.addEventListener("submit", (evento) => {
    const botao = evento.submitter;
    if (botao && botao.name === "tema") document.documentElement.dataset.tema = botao.value;
  });

  // menus de Configurações > Geral: salvam ao mudar; o botão do <noscript> cobre quem não tem JS
  document.addEventListener("change", (evento) => {
    const menu = evento.target;
    const formulario = menu.closest && menu.closest("form[data-preferencia]");
    if (!formulario) return;
    if (menu.name === "tema") document.documentElement.dataset.tema = menu.value;
    if (menu.name === "tamanho") document.documentElement.dataset.texto = menu.value;
    formulario.requestSubmit();
  });
})();
