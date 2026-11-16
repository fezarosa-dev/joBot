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

  // barra lateral (T251; desenho 5.2). O estado fica no <html data-lateral>, que a troca do body pelo
  // histórico não apaga: "aberta" (padrão), "recolhida" (janela larga, a pessoa escondeu) e
  // "sobreposta" (janela média, aberta por cima do conteúdo). Abaixo de 640px a lateral vira uma
  // faixa no topo e o CSS a mostra sempre, sem JS. Tudo por delegação: o histórico recria os nós.
  const raiz = document.documentElement;
  raiz.dataset.js = ""; // com JavaScript, a janela média recolhe a lateral (casca.css)
  const MIN = 180;
  const MAX = 320;
  const PADRAO = 240;
  const larga = matchMedia("(min-width: 900px)");
  const estreita = matchMedia("(max-width: 639.98px)");
  const lerGuardado = (chave) => {
    try {
      return localStorage.getItem(chave);
    } catch {
      return null; // janela privada ou armazenamento bloqueado: fica o padrão
    }
  };
  const guardar = (chave, valor) => {
    try {
      localStorage.setItem(chave, valor);
    } catch {
      // sem armazenamento a escolha vale só nesta página
    }
  };
  const lateralVisivel = () =>
    estreita.matches ||
    (larga.matches ? raiz.dataset.lateral !== "recolhida" : raiz.dataset.lateral === "sobreposta");
  const sincronizar = () => {
    if (!raiz.dataset.lateral) return; // página sem lateral (assistente, Sair)
    const botao = document.querySelector("[data-recolher]");
    if (botao) {
      const visivel = lateralVisivel();
      botao.setAttribute("aria-expanded", String(visivel));
      botao.setAttribute("aria-label", visivel ? botao.dataset.recolherRotulo : botao.dataset.mostrar);
    }
    const largura = Number.parseInt(getComputedStyle(raiz).getPropertyValue("--lateral-largura"), 10);
    document.querySelector("[data-divisor]")?.setAttribute("aria-valuenow", String(largura || PADRAO));
  };
  const mudarLargura = (px) => {
    const largura = Math.min(MAX, Math.max(MIN, Math.round(px)));
    raiz.style.setProperty("--lateral-largura", `${largura}px`); // CSSOM: o CSP não barra
    guardar("jobot.lateral.largura", String(largura));
    sincronizar();
  };
  const larguraAtual = () =>
    Number.parseInt(getComputedStyle(raiz).getPropertyValue("--lateral-largura"), 10) || PADRAO;
  const mudarEstado = (estado) => {
    raiz.dataset.lateral = estado;
    if (larga.matches) guardar("jobot.lateral.recolhida", estado === "recolhida" ? "1" : "0");
    sincronizar();
  };
  const fecharSobreposta = (devolverFoco) => {
    if (raiz.dataset.lateral !== "sobreposta") return;
    mudarEstado("aberta");
    if (devolverFoco) document.querySelector("[data-recolher]")?.focus();
  };
  if (raiz.dataset.lateral) {
    const guardada = Number.parseInt(lerGuardado("jobot.lateral.largura") ?? "", 10);
    if (guardada) raiz.style.setProperty("--lateral-largura", `${Math.min(MAX, Math.max(MIN, guardada))}px`);
    if (larga.matches && lerGuardado("jobot.lateral.recolhida") === "1") raiz.dataset.lateral = "recolhida";
    sincronizar();
  }
  // a janela mudou de faixa: a sobreposta não sobra aberta numa janela larga
  const aoMudarJanela = () => {
    if (larga.matches && raiz.dataset.lateral === "sobreposta") raiz.dataset.lateral = "aberta";
    sincronizar();
  };
  larga.addEventListener("change", aoMudarJanela);
  estreita.addEventListener("change", aoMudarJanela);
  document.addEventListener("htmx:historyRestore", sincronizar);
  // as abas da tela de Vagas trocam só o miolo: a lateral passa a marcar a aba do novo endereço
  // (sem ?aba, a primeira, como faz o servidor)
  document.addEventListener("htmx:pushedIntoHistory", () => {
    const lateral = document.getElementById("lateral");
    if (!lateral || !/^\/(vagas)?$/.test(location.pathname)) return;
    const pedida = new URLSearchParams(location.search).get("aba");
    const abas = [...lateral.querySelectorAll('a[href^="/vagas?aba="]')];
    const atual = abas.find((a) => new URL(a.href).searchParams.get("aba") === pedida) ?? abas[0];
    if (!atual) return;
    for (const marcado of lateral.querySelectorAll("[aria-current]")) marcado.removeAttribute("aria-current");
    atual.setAttribute("aria-current", "page");
  });

  document.addEventListener("click", (evento) => {
    if (evento.target.closest("[data-recolher]")) {
      if (larga.matches) {
        mudarEstado(lateralVisivel() ? "recolhida" : "aberta");
      } else if (lateralVisivel()) {
        fecharSobreposta(false);
      } else {
        mudarEstado("sobreposta");
        const lateral = document.getElementById("lateral");
        (lateral?.querySelector("[aria-current]") ?? lateral?.querySelector("a[href]"))?.focus();
      }
      return;
    }
    // sobreposta: escolher um item ou clicar fora fecha
    if (raiz.dataset.lateral !== "sobreposta") return;
    const naLateral = evento.target.closest("#lateral");
    if (!naLateral || evento.target.closest("a[href]")) fecharSobreposta(false);
  });
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape" && raiz.dataset.lateral === "sobreposta") {
      fecharSobreposta(true);
      return;
    }
    if (!evento.target.matches?.("[data-divisor]")) return;
    // na escrita da direita para a esquerda, a seta para a esquerda alarga
    const sinal = getComputedStyle(raiz).direction === "rtl" ? -1 : 1;
    const passos = { ArrowLeft: -10 * sinal, ArrowRight: 10 * sinal, ArrowDown: -10, ArrowUp: 10 };
    if (evento.key in passos) {
      mudarLargura(larguraAtual() + passos[evento.key]);
    } else if (evento.key === "Home") {
      mudarLargura(MIN);
    } else if (evento.key === "End") {
      mudarLargura(MAX);
    } else if (evento.key === "Enter") {
      mudarEstado(larga.matches ? "recolhida" : "aberta");
      document.querySelector("[data-recolher]")?.focus(); // o divisor sumiu com a lateral
    } else {
      return;
    }
    evento.preventDefault();
  });
  document.addEventListener("dblclick", (evento) => {
    if (evento.target.closest?.("[data-divisor]")) mudarLargura(PADRAO);
  });
  // arrastar: o divisor segue o ponteiro 1:1 a partir de onde foi pego
  document.addEventListener("pointerdown", (evento) => {
    const divisor = evento.target.closest?.("[data-divisor]");
    if (!divisor || evento.button !== 0) return;
    const inicio = evento.clientX;
    const largura = larguraAtual();
    const sinal = getComputedStyle(raiz).direction === "rtl" ? -1 : 1;
    divisor.setPointerCapture(evento.pointerId);
    const mover = (e) => mudarLargura(largura + (e.clientX - inicio) * sinal);
    const soltar = () => {
      divisor.removeEventListener("pointermove", mover);
      divisor.removeEventListener("pointerup", soltar);
      divisor.removeEventListener("pointercancel", soltar);
    };
    divisor.addEventListener("pointermove", mover);
    divisor.addEventListener("pointerup", soltar);
    divisor.addEventListener("pointercancel", soltar);
    evento.preventDefault();
  });

  // janela sem foco: a lateral e a barra perdem a cor de destaque, como num app do Mac
  window.addEventListener("blur", () => {
    raiz.dataset.janela = "inativa";
  });
  window.addEventListener("focus", () => {
    delete raiz.dataset.janela;
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
