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
    // a marca vale uma vez: no "carregar mais" seguinte, o alvo (a lista) ainda tem esta linha
    foco.removeAttribute("data-foco");
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

  // Esc no campo da busca limpa o texto (desenho 5.5); o campo vazio deixa o Esc seguir
  document.addEventListener("keydown", (evento) => {
    const campo = evento.target;
    if (evento.key !== "Escape" || !campo.matches?.("[data-busca]") || !campo.value) return;
    evento.preventDefault();
    campo.value = "";
  });

  // lista de vagas (T254; desenho 5.5): listbox de seleção única com tabindex móvel. O HTML chega
  // sem tabindex nas linhas (sem JS, cada <a> é um link no Tab); aqui só uma fica no Tab, a
  // escolhida. Setas, Home, End, J e K movem; Return segue o link (o <a> já faz).
  const opcoesDe = (lista) => [...lista.querySelectorAll(':scope > [role="option"]')];
  const escolher = (lista, opcao, focar) => {
    for (const outra of opcoesDe(lista)) {
      outra.tabIndex = outra === opcao ? 0 : -1;
      outra.setAttribute("aria-selected", outra === opcao ? "true" : "false");
    }
    if (focar) opcao.focus();
  };
  const prepararListas = () => {
    for (const lista of document.querySelectorAll('[role="listbox"]')) {
      const opcoes = opcoesDe(lista);
      const atual = opcoes.find((o) => o.ariaSelected === "true") ?? opcoes[0];
      if (atual) escolher(lista, atual, false);
    }
  };
  prepararListas();
  document.addEventListener("htmx:afterSettle", prepararListas);
  document.addEventListener("htmx:historyRestore", prepararListas);
  document.addEventListener("focusin", (evento) => {
    const no = evento.target;
    const lista = no.closest?.('[role="listbox"]');
    if (!lista) return;
    if (no === lista) {
      // o "pular para a lista" foca o listbox: o foco desce para a linha escolhida
      const atual = opcoesDe(lista).find((o) => o.ariaSelected === "true");
      if (atual) atual.focus();
    } else if (no.matches('[role="option"]')) {
      escolher(lista, no, false);
    }
  });
  const MOVER = { ArrowDown: 1, j: 1, J: 1, ArrowUp: -1, k: -1, K: -1 }; // J e K também com Caps Lock
  document.addEventListener("keydown", (evento) => {
    if (evento.ctrlKey || evento.metaKey || evento.altKey || evento.shiftKey) return;
    const opcao = evento.target.closest?.('[role="option"]');
    const lista = opcao?.parentElement;
    if (!opcao || lista?.getAttribute("role") !== "listbox") return;
    const opcoes = opcoesDe(lista);
    const i = opcoes.indexOf(opcao);
    let destino = null;
    if (evento.key in MOVER) destino = opcoes[i + MOVER[evento.key]];
    else if (evento.key === "Home") destino = opcoes[0];
    else if (evento.key === "End") destino = opcoes[opcoes.length - 1];
    else return;
    evento.preventDefault(); // a seta não rola a página; na ponta, fica onde está
    if (destino) escolher(lista, destino, true);
  });

  // detalhe ao lado da lista (T255): a linha pede o detalhe por htmx (hx-get no <a>) e o
  // <dialog id="detalhe-vaga"> recebe. O CSS diz o modo em --detalhe-modo, pela largura do miolo:
  // "coluna", "sobreposto" ou "pagina" (abaixo de 640px a linha segue o href, como sem JS).
  const lado = () => document.getElementById("detalhe-vaga");
  const modo = () => {
    const no = lado();
    return no ? getComputedStyle(no).getPropertyValue("--detalhe-modo").trim() : "pagina";
  };
  // clique com tecla (nova aba, nova janela) e o modo página ficam com o navegador: a captura no
  // document para o clique antes do ouvinte do htmx no <a>, sem impedir o link
  document.addEventListener(
    "click",
    (evento) => {
      const opcao = evento.target.closest?.('[role="option"][hx-get]');
      if (!opcao) return;
      const comTecla = evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey;
      if (comTecla || evento.button !== 0 || modo() === "pagina") evento.stopPropagation();
    },
    true,
  );
  // a linha aberta fica marcada pela resposta, não pelo foco: Safari e Firefox do Mac não focam o
  // <a> clicado, e o focusin não chega
  document.addEventListener("htmx:afterSettle", (evento) => {
    if (!evento.target.matches?.("#detalhe-vaga")) return;
    const linha = document.getElementById(`vaga-${lado()?.dataset.vaga}`);
    const lista = linha?.parentElement;
    if (lista?.getAttribute("role") === "listbox") escolher(lista, linha, false);
  });
  const fecharLado = (devolverFoco = true) => {
    const no = lado();
    if (!no?.open) return;
    const id = no.dataset.vaga;
    no.close();
    delete no.dataset.vaga;
    const url = new URL(location.href);
    url.searchParams.delete("vaga");
    history.replaceState(history.state, "", url);
    if (devolverFoco) document.getElementById(`vaga-${id}`)?.focus();
  };
  document.addEventListener("keydown", (evento) => {
    // a lateral sobreposta fecha primeiro (o ouvinte dela vem depois e não marca o evento)
    if (evento.key !== "Escape" || evento.defaultPrevented) return;
    if (document.querySelector("dialog.sheet[open]")) return; // o sheet modal fecha com o próprio Esc
    if (document.documentElement.dataset.lateral === "sobreposta") return;
    if (!lado()?.open || modo() !== "sobreposto") return;
    evento.preventDefault();
    fecharLado();
  });
  document.addEventListener("click", (evento) => {
    // clique na lista, fora de uma linha (a linha troca o detalhe), fecha o sobreposto
    if (!lado()?.open || modo() !== "sobreposto") return;
    if (evento.target.closest('.coluna-lista') && !evento.target.closest('[role="option"]')) {
      fecharLado();
    }
  });

  // sheet da correção (T264): o htmx põe o <dialog class="sheet"> no .correcao-slot e aqui ele abre
  // como modal (o resto da página fica inerte, o Esc fecha, o foco fica preso nele). Ao fechar, o
  // <dialog> sai do DOM e o foco volta ao link que o abriu. Sem JavaScript o link leva à página.
  let abriuSheet = null;
  document.addEventListener("htmx:beforeRequest", (evento) => {
    if (evento.target.matches?.("[data-correcao]")) abriuSheet = evento.target;
  });
  document.addEventListener("htmx:afterSwap", (evento) => {
    const alvo = evento.detail.target;
    if (!alvo?.matches?.(".correcao-slot")) return;
    alvo.querySelector("dialog.sheet")?.showModal();
  });
  // o evento `close` não borbulha: a captura no document o pega
  document.addEventListener(
    "close",
    (evento) => {
      if (!evento.target.matches?.("dialog.sheet")) return;
      evento.target.remove();
      if (abriuSheet?.isConnected) abriuSheet.focus();
      abriuSheet = null;
    },
    true,
  );
  // Ctrl/Cmd/Shift + clique no link da correção é "abrir em outra aba": o htmx não vê o clique
  // e o navegador segue o href
  document.addEventListener(
    "click",
    (evento) => {
      const modificado = evento.ctrlKey || evento.metaKey || evento.shiftKey;
      if (modificado && evento.target.closest?.("[data-correcao]")) evento.stopImmediatePropagation();
    },
    true,
  );
  // o fundo só fecha se o botão desceu e subiu nele: selecionar texto num campo e soltar fora
  // gera um clique no <dialog> e não pode fechar o sheet nem perder o que foi digitado
  let desceuNoFundo = false;
  document.addEventListener("mousedown", (evento) => {
    const sheet = evento.target.closest?.("dialog.sheet");
    desceuNoFundo = evento.target === sheet;
  });
  document.addEventListener("click", (evento) => {
    const sheet = evento.target.closest?.("dialog.sheet");
    // o botão Fechar do pé; ou o fundo (o clique cai no próprio <dialog>, que não tem margem)
    if (evento.target.closest("[data-fechar-sheet]")) sheet?.close();
    else if (evento.target === sheet && desceuNoFundo) sheet.close();
    desceuNoFundo = false;
  });

  // faixa de desfazer (T256; desenho 5.4). Ocultar e Desfazer/Refazer respondem com a faixa nova
  // (OOB, no mesmo nó da região viva) e um HX-Trigger-After-Settle: o aviso chega com a faixa já
  // processada (antes do settle, um ⌘Z faria POST nativo). Mostrar recarrega a lista no endereço de
  // agora (aba, busca e ordem ficam) em vez de achar a posição da linha à mão.
  const faixa = () => document.getElementById("faixa-desfazer");
  const botaoDaFaixa = () => faixa()?.querySelector('button[type="submit"]');
  const linhaEscolhida = () =>
    document.querySelector('[role="listbox"] > [role="option"][aria-selected="true"]');
  // onde estava o foco antes da ação: na faixa (o botão dela é trocado), na lista ou no detalhe
  // (a linha ou o detalhe somem) ou em nenhum lugar; em outro ponto ele fica onde está
  const ondeEstava = (no) => {
    if (no?.closest?.("#faixa-desfazer")) return "faixa";
    if (!no || no === document.body || no.closest?.('#detalhe-vaga, [role="listbox"]')) return "lista";
    return "";
  };
  // o aviso vem depois do settle, quando o botão da faixa que foi apertado já saiu da página (foco
  // no body): onde estava o foco é lido antes da troca
  let ondeAntes = "";
  document.addEventListener("htmx:beforeSwap", (evento) => {
    if (evento.detail.xhr?.getResponseHeader("HX-Trigger-After-Settle")) {
      ondeAntes = ondeEstava(document.activeElement);
    }
  });
  const devolverFoco = (onde, linha) => {
    if (onde === "faixa") botaoDaFaixa()?.focus();
    else if (onde === "lista") (linha ?? document.getElementById("conteudo"))?.focus();
  };
  // a faixa manda a página de agora como `voltar` (a lateral marca a aba certa) e a busca dela
  document.addEventListener("htmx:configRequest", (evento) => {
    if (!evento.detail.elt?.closest?.("#faixa-desfazer")) return;
    evento.detail.parameters.voltar = location.pathname + location.search;
    evento.detail.parameters.busca = new URLSearchParams(location.search).get("busca") ?? "";
  });
  // shortcut: recarrega só a página 1 do endereço de agora; o que veio por "Carregar mais" some e
  // uma linha de lá não volta à vista. Recarregar até a página já carregada se alguém reclamar.
  const recarregarLista = () =>
    document.getElementById("vagas-miolo")
      ? htmx.ajax("GET", location.pathname + location.search, { target: "#vagas-miolo", swap: "innerHTML" })
      : null;
  document.addEventListener("vaga-ocultada", (evento) => {
    const id = Number(evento.detail.vaga);
    const onde = ondeAntes;
    if (new URLSearchParams(location.search).get("aba") === "ocultas") {
      // Refazer na aba Ocultas: a linha entra na lista, não sai
      recarregarLista()?.then(() => devolverFoco(onde, null));
      return;
    }
    if (lado()?.dataset.vaga === String(id)) fecharLado(false);
    const linha = document.getElementById(`vaga-${id}`);
    const lista = linha?.parentElement;
    let vizinha = null;
    if (linha && lista?.getAttribute("role") === "listbox") {
      const opcoes = opcoesDe(lista);
      const i = opcoes.indexOf(linha);
      vizinha = opcoes[i + 1] ?? opcoes[i - 1] ?? null;
      // o Tab continua numa linha que existe: a seguinte ou, na ponta, a anterior
      if (linha.ariaSelected === "true" && vizinha) escolher(lista, vizinha, false);
    }
    linha?.remove();
    devolverFoco(onde, onde === "lista" ? (linhaEscolhida() ?? vizinha) : null);
  });
  document.addEventListener("vaga-mostrada", (evento) => {
    const id = Number(evento.detail.vaga);
    const onde = ondeAntes;
    recarregarLista()?.then(() => {
      const linha = document.getElementById(`vaga-${id}`);
      const lista = linha?.parentElement;
      if (linha && lista?.getAttribute("role") === "listbox") {
        escolher(lista, linha, false);
        // o realce de 1 s mostra onde a linha voltou; o CSS cuida do movimento reduzido
        linha.classList.add("linha-volta");
        setTimeout(() => linha.classList.remove("linha-volta"), 1000);
      }
      devolverFoco(onde, linha);
    });
  });
  document.addEventListener("click", (evento) => {
    if (!evento.target.closest("[data-faixa-fechar]")) return;
    faixa()?.replaceChildren();
    devolverFoco("lista", linhaEscolhida());
  });
  // a faixa não entra na foto do histórico (voltaria velha), mas fica na tela: tiro antes da foto e
  // devolvo logo depois, no nó que estiver na página (o mesmo, ou o novo de uma volta no histórico)
  document.addEventListener("htmx:beforeHistorySave", () => {
    const nos = [...(faixa()?.childNodes ?? [])];
    if (!nos.length) return;
    faixa().replaceChildren();
    queueMicrotask(() => faixa()?.replaceChildren(...nos));
  });
  // ⌘Z desfaz e ⇧⌘Z refaz (Ctrl fora do Mac), só com a faixa na tela e fora de campo de texto
  // (select, caixa de marcar e botão não têm desfazer próprio: neles o atalho vai para a faixa)
  const campoDeTexto =
    'textarea, input:not([type="checkbox"], [type="radio"], [type="button"], [type="submit"], [type="reset"], [type="range"], [type="color"], [type="file"])';
  const plataforma = navigator.userAgentData?.platform ?? navigator.platform ?? "";
  const noMac = /mac|iphone|ipad/i.test(plataforma);
  document.addEventListener("keydown", (evento) => {
    if (evento.key?.toLowerCase() !== "z" || evento.altKey) return;
    if (noMac ? !evento.metaKey || evento.ctrlKey : !evento.ctrlKey || evento.metaKey) return;
    const ativo = document.activeElement;
    if (ativo && (ativo.isContentEditable || ativo.matches(campoDeTexto))) return;
    const acao = evento.shiftKey ? "refazer" : "desfazer";
    const botao = faixa()?.querySelector(`[data-faixa="${acao}"] button[type="submit"]`);
    if (!botao) return;
    evento.preventDefault();
    // a faixa recém-chegada só ganha os hx-* no settle; processar antes (o htmx ignora o que já
    // processou) evita que o ⌘Z dessa janela vire POST nativo
    htmx.process(botao.form);
    // com o menu aberto, ele fecha antes: Refazer pode tirar a linha dele sem `htmx:beforeSwap`
    fecharMenu(false);
    botao.click();
  });

  // menu de contexto (T257; desenho 5.4): um <div popover role="menu"> por página
  // (_menu_contexto.html), preenchido com os data-* do alvo ao abrir. Botão direito abre no
  // ponteiro; a tecla de menu e Shift+F10, no alvo focado. Setas movem, Esc e Tab fecham e o foco
  // volta ao alvo; clique fora (o popover fecha sozinho), rolagem, janela nova ou troca do htmx
  // fecham também. O que cada item faz é o link ou o form dele: o menu não tem ação própria.
  let menuAberto = null;
  let alvoMenu = null;
  let abertoPeloTeclado = null;
  let ondeEstavaOAlvo = "";
  const posicaoDe = (no) => {
    const caixa = no.getBoundingClientRect();
    return `${caixa.left},${caixa.top}`;
  };
  const itensDoMenu = (no) =>
    [...no.querySelectorAll('[role="menuitem"]')].filter((item) => !item.closest("[hidden]"));
  const preencher = (modelo, alvo) => modelo.replace(/\{(\w+)\}/g, (_, campo) => alvo.dataset[campo] ?? "");
  const esquecerMenu = () => {
    menuAberto = null;
    alvoMenu = null;
    abertoPeloTeclado = null;
  };
  const fecharMenu = (devolverFoco) => {
    const menu = menuAberto;
    const alvo = alvoMenu;
    if (!menu) return;
    esquecerMenu();
    if (menu.matches(":popover-open")) menu.hidePopover();
    if (devolverFoco && alvo?.isConnected) alvo.focus({ preventScroll: true });
  };
  // o ponteiro dá a posição em coordenadas físicas; sem espaço à direita ou embaixo, o menu
  // encosta na borda da janela ou abre para cima (acima de `yAcima`), como no Mac
  const posicionar = (menu, x, y, yAcima) => {
    menu.style.setProperty("--menu-x", `${x}px`); // CSSOM: o CSP não barra
    menu.style.setProperty("--menu-y", `${y}px`);
    const caixa = menu.getBoundingClientRect();
    const { clientWidth: largura, clientHeight: altura } = document.documentElement;
    if (caixa.right > largura) menu.style.setProperty("--menu-x", `${Math.max(0, largura - caixa.width)}px`);
    if (caixa.bottom > altura) menu.style.setProperty("--menu-y", `${Math.max(0, yAcima - caixa.height)}px`);
  };
  const abrirMenu = (alvo, x, y, yAcima, peloTeclado) => {
    const menu = document.getElementById(alvo.dataset.menu);
    if (!menu?.matches("[data-menu-contexto]")) return false;
    // a HIG esconde o item que não vale para este alvo (não o apaga); grupo vazio some junto
    for (const no of menu.querySelectorAll("[data-requer]")) no.hidden = !(no.dataset.requer in alvo.dataset);
    for (const grupo of menu.querySelectorAll('[role="group"]')) {
      grupo.hidden = false;
      grupo.hidden = itensDoMenu(grupo).length === 0;
    }
    for (const link of menu.querySelectorAll("[data-modelo-href]")) link.href = preencher(link.dataset.modeloHref, alvo);
    for (const form of menu.querySelectorAll("form[data-modelo-acao]")) {
      const acao = preencher(form.dataset.modeloAcao, alvo);
      form.setAttribute("action", acao);
      if (form.hasAttribute("hx-post")) form.setAttribute("hx-post", acao);
      // como a faixa: a página de agora como `voltar` e a busca dela
      const { voltar, busca } = form.elements;
      if (voltar) voltar.value = location.pathname + location.search;
      if (busca) busca.value = new URLSearchParams(location.search).get("busca") ?? "";
    }
    htmx.process(menu); // o htmx refaz o form cujo hx-post mudou
    menuAberto = menu;
    alvoMenu = alvo;
    abertoPeloTeclado = peloTeclado ? alvo : null;
    ondeEstavaOAlvo = posicaoDe(alvo);
    if (!menu.matches(":popover-open")) menu.showPopover();
    posicionar(menu, x, y, yAcima);
    // pelo teclado, o primeiro item já vem realçado; pelo ponteiro, nenhum (como no Mac)
    const primeiro = itensDoMenu(menu)[0];
    (peloTeclado && primeiro ? primeiro : menu).focus({ preventScroll: true });
    return true;
  };
  document.addEventListener(
    "toggle",
    (evento) => {
      if (evento.target === menuAberto && evento.newState === "closed") esquecerMenu();
    },
    true,
  );
  // o botão direito do Mac escolhe a palavra no mousedown: o que estava escolhido é lido antes
  let haviaSelecao = false;
  document.addEventListener(
    "pointerdown",
    (evento) => {
      const selecao = getSelection();
      haviaSelecao = evento.button === 2 && !!selecao && !selecao.isCollapsed && selecao.toString().trim() !== "";
    },
    true,
  );
  document.addEventListener("contextmenu", (evento) => {
    if (evento.target.closest?.("[data-menu-contexto]")) {
      evento.preventDefault();
      return;
    }
    const alvo = evento.target.closest?.("[data-menu]");
    if (!alvo) return;
    // a tecla de menu de alguns navegadores ainda manda um contextmenu: o menu já está aberto
    if (abertoPeloTeclado === alvo && menuAberto) {
      evento.preventDefault();
      return;
    }
    // texto escolhido ou um link de dentro do alvo são outro objeto: o menu do navegador cuida
    // (Copiar, Abrir link), como a HIG pede para o menu falar do que está sob o ponteiro
    const selecao = getSelection();
    if (haviaSelecao && selecao && !selecao.isCollapsed && selecao.containsNode(alvo, true)) return;
    const link = evento.target.closest("a[href]");
    if (link && link !== alvo) return;
    if (abrirMenu(alvo, evento.clientX, evento.clientY, evento.clientY, false)) evento.preventDefault();
  });
  document.addEventListener("keydown", (evento) => {
    const pediu = evento.key === "ContextMenu" || (evento.key === "F10" && evento.shiftKey);
    if (!pediu || evento.ctrlKey || evento.metaKey || evento.altKey) return;
    const alvo = evento.target;
    if (!alvo.matches?.("[data-menu]")) return;
    const caixa = alvo.getBoundingClientRect();
    if (abrirMenu(alvo, caixa.left, caixa.bottom, caixa.top, true)) evento.preventDefault();
  });
  // dentro do menu, na captura: o Esc não chega ao detalhe nem à lateral, as setas não rolam a página
  document.addEventListener(
    "keydown",
    (evento) => {
      const menu = menuAberto;
      const ativo = document.activeElement;
      if (!menu || !menu.contains(ativo) || evento.ctrlKey || evento.metaKey || evento.altKey) return;
      const itens = itensDoMenu(menu);
      const i = itens.indexOf(ativo);
      let destino = null;
      if (evento.key === "ArrowDown") destino = itens[(i + 1) % itens.length];
      else if (evento.key === "ArrowUp") destino = itens[(i <= 0 ? itens.length : i) - 1];
      else if (evento.key === "Home") destino = itens[0];
      else if (evento.key === "End") destino = itens[itens.length - 1];
      // o Tab fecha o menu e volta à linha que o abriu (o desenho diz "o Tab sai"); o próximo Tab
      // segue a ordem normal a partir dela
      else if (evento.key === "Escape" || evento.key === "Tab") fecharMenu(true);
      else if (evento.key === " " && ativo.matches("a[role='menuitem']")) ativo.click();
      else return;
      evento.preventDefault();
      evento.stopPropagation();
      destino?.focus({ preventScroll: true });
    },
    true,
  );
  // o ponteiro realça o item sob ele (o foco é o realce) e, ao sair, nenhum
  document.addEventListener("pointerover", (evento) => {
    const item = evento.target.closest?.('[data-menu-contexto] [role="menuitem"]');
    if (item && item.closest("[data-menu-contexto]") === menuAberto) item.focus({ preventScroll: true });
  });
  document.addEventListener("pointerout", (evento) => {
    const item = evento.target.closest?.('[data-menu-contexto] [role="menuitem"]');
    if (item && document.activeElement === item && !item.contains(evento.relatedTarget)) {
      menuAberto?.focus({ preventScroll: true });
    }
  });
  const copiarLink = async (menu, item, endereco) => {
    let copiou = false;
    try {
      await navigator.clipboard.writeText(endereco); // sem clipboard (navegador antigo) cai no catch
      copiou = endereco !== "";
    } catch {
      copiou = false;
    }
    const aviso = document.getElementById(`${menu.id}-aviso`);
    if (!aviso) return;
    const texto = document.createElement("p");
    texto.dataset.someSozinho = "";
    texto.textContent = copiou ? item.dataset.copiado : item.dataset.naoCopiou;
    aviso.replaceChildren(texto);
    agendarSumico();
  };
  document.addEventListener("click", (evento) => {
    const item = evento.target.closest?.('[data-menu-contexto] [role="menuitem"]');
    if (!item || item.closest("[data-menu-contexto]") !== menuAberto) return;
    const menu = menuAberto;
    const alvo = alvoMenu;
    // o alvo saiu da página por um caminho que o menu não viu: fecha sem agir (nem o form nem o link)
    if (!alvo?.isConnected) {
      evento.preventDefault();
      fecharMenu(false);
      return;
    }
    // o form e o link seguem sozinhos (o form ainda está na página depois de o menu fechar)
    fecharMenu(true);
    if (item.matches("[data-abrir]")) {
      // Abrir é o clique na própria linha: detalhe ao lado ou página, quem decide é a linha
      evento.preventDefault();
      alvo?.click();
    } else if (item.matches("[data-modelo-copiar]") && alvo) {
      copiarLink(menu, item, preencher(item.dataset.modeloCopiar, alvo));
    }
  });
  // rolar fecha o menu; o aviso de rolagem chega no quadro seguinte, então a rolagem que veio antes
  // de abrir (o foco do mousedown traz a linha para a vista) não conta: só fecha se o alvo andou
  document.addEventListener(
    "scroll",
    (evento) => {
      if (!menuAberto || menuAberto.contains(evento.target)) return;
      if (posicaoDe(alvoMenu) !== ondeEstavaOAlvo) fecharMenu(true);
    },
    true,
  );
  window.addEventListener("resize", () => fecharMenu(true));
  document.addEventListener("htmx:beforeSwap", (evento) => {
    if (alvoMenu && evento.detail.target?.contains(alvoMenu)) fecharMenu(false);
  });
  document.addEventListener("htmx:beforeHistorySave", () => fecharMenu(false));

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

  // componente de progresso (T252; desenho 5.9). O CSP barra o atributo style, então a largura vem
  // de data-valor e anda numa animação linear de 2 s a partir da largura que estava na tela antes
  // da troca (a animação não escreve no style). A pergunta de 2 s recria o "Ver detalhes": aberto
  // antes da troca, reabre depois. O texto de "Ver detalhes"/"Ocultar detalhes" segue o popover.
  const movimentoReduzido = window.matchMedia("(prefers-reduced-motion: reduce)");
  const larguras = new Map();
  const animados = new WeakSet();
  let detalhesAbertos = null;
  document.addEventListener("htmx:beforeSwap", () => {
    larguras.clear();
    for (const p of document.querySelectorAll(".progresso-preenchimento[id]")) {
      const trilho = p.parentElement.getBoundingClientRect().width;
      const largura = p.classList.contains("indeterminado") ? 0 : p.getBoundingClientRect().width;
      if (trilho > 0) larguras.set(p.id, (largura / trilho) * 100);
    }
    detalhesAbertos = document.querySelector(".progresso-detalhes:popover-open")?.id ?? null;
  });
  const aplicarLarguras = () => {
    for (const p of document.querySelectorAll(".progresso-preenchimento[data-valor]")) {
      if (animados.has(p)) continue;
      animados.add(p);
      const ate = `${p.dataset.valor}%`;
      const de = larguras.has(p.id) ? `${larguras.get(p.id)}%` : ate;
      const duration = movimentoReduzido.matches || de === ate ? 0 : 2000;
      p.animate([{ width: de }, { width: ate }], { duration, easing: "linear", fill: "forwards" });
    }
  };
  // a página que volta do histórico traz o data-valor sem a animação que punha a largura
  document.addEventListener("htmx:historyRestore", () => {
    larguras.clear();
    aplicarLarguras();
  });
  document.addEventListener("htmx:afterSwap", () => {
    aplicarLarguras();
    const detalhes = detalhesAbertos && document.getElementById(detalhesAbertos);
    detalhesAbertos = null;
    if (detalhes && !detalhes.matches(":popover-open")) {
      detalhes.showPopover({ source: document.querySelector(`[popovertarget="${detalhes.id}"]`) });
    }
  });
  document.addEventListener(
    "toggle",
    (evento) => {
      const detalhes = evento.target;
      if (!detalhes.matches?.(".progresso-detalhes")) return;
      const botao = document.querySelector(`[popovertarget="${detalhes.id}"][data-ver]`);
      if (!botao) return;
      botao.textContent = evento.newState === "open" ? botao.dataset.ocultar : botao.dataset.ver;
    },
    true, // toggle não sobe: só a captura o vê no document
  );
})();
