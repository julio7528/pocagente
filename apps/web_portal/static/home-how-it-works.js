(() => {
  const section = document.querySelector(".home-how-it-works");
  if (!section) return;

  const diagram = section.querySelector("[data-flow-surface]");
  const tooltip = section.querySelector("[data-flow-tooltip]");
  const tooltipTitle = section.querySelector("[data-flow-tooltip-title]");
  const tooltipDescription = section.querySelector("[data-flow-tooltip-description]");
  const detailsTitle = section.querySelector("[data-flow-details-title]");
  const detailsDescription = section.querySelector("[data-flow-details-description]");
  const detailsUses = section.querySelector("[data-flow-details-uses]");
  const nodes = Array.from(section.querySelectorAll(".home-flow-node[data-flow-term]"));
  const edges = Array.from(section.querySelectorAll(".home-flow-edge[data-flow-groups]"));

  if (!diagram || !tooltip || !tooltipTitle || !tooltipDescription || !detailsTitle || !detailsDescription || !detailsUses || nodes.length === 0) return;

  const explanations = {
    user: {
      title: "Cliente",
      short: "Envia a mensagem pelo navegador e recebe a resposta pelo portal.",
      detail: "O navegador conversa com o portal Django. Ele não chama a Agent API nem os agentes diretamente.",
      uses: "Fluxo: navegador → Django → Agent API."
    },
    portal: {
      title: "Portal Django",
      short: "Autentica a sessão, autoriza a conversa e controla o histórico.",
      detail: "O Django salva a mensagem do cliente, monta o contexto limitado da mesma conversa e faz a chamada interna. Depois, persiste a resposta permitida no histórico.",
      uses: "Sessão, autorização, contexto e persistência do portal."
    },
    fastapi: {
      title: "FastAPI · /chat",
      short: "É a fronteira autenticada entre o portal e o runtime dos agentes.",
      detail: "A rota recebe uma requisição tipada pela conexão interna autenticada, confere a identidade confiável e delega o turno ao serviço de chat.",
      uses: "O browser não acessa a Agent API diretamente."
    },
    langgraph: {
      title: "LangGraph",
      short: "Organiza as etapas e rotas do runtime em um grafo acíclico.",
      detail: "A execução do grafo começa pelo Router, passa pela capacidade selecionada e termina no Assembly. Algumas rotas combinam capacidades antes da montagem.",
      uses: "Router → capacidades → Assembly."
    },
    "input-security": {
      title: "Segurança de entrada",
      short: "O preflight do Router avalia a solicitação antes da rota de negócio.",
      detail: "O Router executa o preflight de segurança e pode aplicar a classificação semântica configurada. Uma solicitação bloqueada segue um resultado controlado e pode gerar evento de auditoria sanitizado.",
      uses: "Segurança de entrada ocorre dentro do início da execução do grafo."
    },
    router: {
      title: "Router Agent",
      short: "Decide quais capacidades devem atuar; o Router não executa essas capacidades.",
      detail: "A decisão tipada seleciona conversa, conhecimento, dados operacionais, busca web, handoff ou um caminho combinado. O grafo executa a decisão e as condições de cada rota.",
      uses: "Pode selecionar fallback web e a rota cooperativa Knowledge + Customer Support."
    },
    audit: {
      title: "Audit",
      short: "Registra eventos de segurança sem expor conteúdo interno bruto na interface.",
      detail: "Bloqueios de segurança e ações de proteção podem gerar registros sanitizados pela fronteira de auditoria. A home não mostra prompts, payloads de ferramentas ou dados sensíveis.",
      uses: "Auditoria tipada e sanitizada; não é uma fonte de resposta."
    },
    conversational: {
      title: "Conversational Agent",
      short: "Atende a rota conversacional e entrega o resultado ao Assembly.",
      detail: "O Router pode encaminhar interações conversacionais simples para essa capacidade. A resposta segue ao ponto de montagem do grafo.",
      uses: "LangGraph → Conversational Agent → Assembly."
    },
    knowledge: {
      title: "Knowledge Agent",
      short: "Responde com conhecimento recuperado e fundamentado em evidências.",
      detail: "A capacidade usa retrieval aprovado, constrói um contexto grounded e gera a resposta com referências. Se as evidências forem insuficientes, pode encerrar esse caminho de forma controlada ou acionar o fallback web configurado.",
      uses: "RAG híbrida · grounding · citações."
    },
    rag: {
      title: "RAG híbrida",
      short: "Combina resultados de busca lexical e busca vetorial.",
      detail: "A camada de retrieval recupera trechos da base de conhecimento autorizada. O Knowledge Agent avalia se o contexto recuperado sustenta uma resposta antes de gerar.",
      uses: "PostgreSQL FTS + pgvector + FastEmbed; resultados passam por grounding."
    },
    fts: {
      title: "PostgreSQL Full Text Search",
      short: "Localiza trechos por correspondência lexical.",
      detail: "O retrieval híbrido usa a busca textual do PostgreSQL como uma das fontes de candidatos para a pergunta.",
      uses: "Busca lexical dentro da fronteira de retrieval."
    },
    pgvector: {
      title: "pgvector",
      short: "Permite recuperar trechos por similaridade vetorial.",
      detail: "A busca vetorial participa do retrieval híbrido para encontrar trechos semanticamente próximos da consulta.",
      uses: "Busca vetorial no PostgreSQL."
    },
    fastembed: {
      title: "FastEmbed",
      short: "Gera os embeddings usados pelo caminho de busca vetorial.",
      detail: "FastEmbed integra o pipeline de embeddings do retrieval vetorial; ele não decide a resposta nem substitui o grounding.",
      uses: "Embeddings para pesquisa com pgvector."
    },
    grounding: {
      title: "Grounding",
      short: "Relaciona a resposta candidata às evidências recuperadas.",
      detail: "O contexto grounded registra as evidências e suas citações. Sem evidência suficiente, o Knowledge Agent retorna um estado controlado em vez de inventar sustentação.",
      uses: "Evidências recuperadas → contexto grounded → geração com citações."
    },
    "customer-support": {
      title: "Customer Support Agent",
      short: "Consulta fatos operacionais por ferramentas controladas e autorizadas.",
      detail: "O agente planeja consultas OPS limitadas, recebe fatos estruturados e pode distinguir observações diretas de inferências identificadas. O LLM não recebe acesso SQL livre ao banco.",
      uses: "OPS Tools somente leitura → repositórios autorizados → PostgreSQL OPS."
    },
    "ops-tools": {
      title: "OPS Tools",
      short: "Oferecem consultas operacionais tipadas, limitadas e somente leitura.",
      detail: "As ferramentas validam a autorização e os seletores permitidos antes de consultar dados. Não aceitam SQL arbitrário nem deixam o modelo escolher operações irrestritas.",
      uses: "Status de protocolo, execução, investigação e consultas aprovadas."
    },
    "ops-postgres": {
      title: "PostgreSQL OPS",
      short: "Guarda as fontes operacionais acessadas pela camada de repositórios.",
      detail: "O agente não abre conexão direta: ferramentas e repositórios executam somente as operações aprovadas pela aplicação.",
      uses: "Acesso mediado por OPS Tools e repositórios."
    },
    "ops-facts": {
      title: "Fatos operacionais",
      short: "Mantêm fatos observados separados de interpretações do agente.",
      detail: "O resultado tipado diferencia fatos apoiados nos registros consultados de inferências explicitamente identificadas.",
      uses: "Evidência OPS pode cooperar com conhecimento grounded."
    },
    "web-knowledge": {
      title: "Web Knowledge",
      short: "Busca evidência pública atual quando a política de rota permite.",
      detail: "A capacidade consulta informação pública por uma requisição limitada e usa o resultado como evidência atual. Esse conteúdo não vira dado OPS nem é gravado na base RAG por essa execução.",
      uses: "Busca web controlada → evidência pública → resposta grounded."
    },
    tavily: {
      title: "Tavily",
      short: "Fornece busca pública ao vivo por uma fronteira de consulta limitada.",
      detail: "A solicitação da busca usa os limites e domínios aprovados pela aplicação. A resposta do provedor é tratada como evidência externa, não como instrução de sistema.",
      uses: "Web Knowledge Agent."
    },
    "public-evidence": {
      title: "Evidência pública atual",
      short: "Pode apoiar respostas sobre informações públicas e atuais.",
      detail: "A evidência vem da busca web da execução corrente e pode ser atribuída na resposta. Ela não substitui os registros privados operacionais nem a base persistente de conhecimento.",
      uses: "Evidência externa, limitada e não persistida como OPS/RAG."
    },
    "human-agent": {
      title: "Human Escalation",
      short: "Coordena as transições tipadas para oferecer, aceitar ou resolver um handoff.",
      detail: "O agente valida transições de estado sem manter a fila persistente. No portal, a confirmação explícita segue uma fronteira interna, e o Django é dono do estado durável da conversa e do handoff.",
      uses: "A automação só é suspensa depois do aceite de um atendente autorizado."
    },
    "human-transition": {
      title: "Transição humana tipada",
      short: "Representa uma transição válida do fluxo humano, sem persistir a fila.",
      detail: "A Agent API valida a transição por um contrato interno e devolve um resultado tipado. O Django valida esse resultado e persiste a fila, a atribuição e o estado no portal.",
      uses: "A fila e a propriedade da conversa pertencem ao Django."
    },
    "cooperative-synthesis": {
      title: "Síntese cooperativa",
      short: "Combina fatos operacionais e conhecimento fundamentado quando a rota pede os dois.",
      detail: "Na rota cooperativa do grafo, Customer Support consulta primeiro os dados OPS; Knowledge recupera evidências e a síntese combina os dois resultados antes do Assembly.",
      uses: "Customer Support → Knowledge → síntese → Assembly."
    },
    assembly: {
      title: "Assembly",
      short: "Reúne a saída da rota executada no LangGraph.",
      detail: "Conversação, agentes especializados e resultados terminais convergem para a montagem do resultado da orquestração. O Assembly ainda não é a resposta liberada ao cliente.",
      uses: "Depois dele, ChatApplicationService aplica a verificação da saída configurada."
    },
    "output-security": {
      title: "Output Security",
      short: "Analisa a resposta candidata depois do Assembly e antes da entrega.",
      detail: "O serviço de chat aplica o gate de saída à resposta candidata e pode permitir, redigir ou bloquear o conteúdo. Quando necessário, registra a ação pela fronteira de auditoria.",
      uses: "Fica no ChatApplicationService, fora do grafo LangGraph."
    },
    "api-response": {
      title: "Resposta tipada da API",
      short: "Entrega ao Django apenas os campos permitidos pelo contrato de chat.",
      detail: "A Agent API retorna um modelo de resposta allowlisted. Prompts, estado interno do grafo, SQL, payloads de ferramentas e credenciais não fazem parte desse contrato.",
      uses: "FastAPI → cliente interno do Django."
    },
    "django-persist": {
      title: "Persistência no Django",
      short: "Grava a resposta do agente no histórico da conversa autorizada.",
      detail: "Após a chamada interna, o portal mapeia o retorno seguro para a mensagem do agente e a persiste no mesmo histórico, respeitando a situação atual da conversa.",
      uses: "O portal continua dono do transcript e do estado web."
    },
    "user-response": {
      title: "Resposta no portal",
      short: "Mostra ao cliente o retorno que passou pelo contrato e pelos controles da aplicação.",
      detail: "A interface lê a conversa persistida no Django. O navegador não recebe diretamente o estado de orquestração nem os payloads internos dos agentes.",
      uses: "Histórico do portal Django."
    },
    "explicit-confirmation": {
      title: "Confirmação explícita",
      short: "O pedido de atendimento humano precisa de confirmação explícita do cliente.",
      detail: "A rota do portal verifica a confirmação explícita e a propriedade da conversa antes de iniciar a transição. Um pedido direto de suporte pode usar essa rota sem passar pelo turno padrão de agentes.",
      uses: "Django autoriza a conversa e chama a transição interna confiável."
    },
    "transition-api": {
      title: "Transição interna FastAPI",
      short: "Delega o evento de handoff ao Human Escalation Agent existente.",
      detail: "A fronteira interna aceita somente ações tipadas e deriva a identidade do ator de credenciais confiáveis. O resultado sem estado durável não atribui propriedade por si só.",
      uses: "Endpoint interno de transição humana; não é uma rota do browser."
    },
    "waiting-queue": {
      title: "Fila WAITING_HUMAN",
      short: "O Django grava a conversa e a solicitação de atendimento na fila persistente.",
      detail: "Após validar o resultado da transição, o portal atualiza o estado da conversa e cria o registro de handoff. A fila pode ser consultada pelos atendentes autorizados.",
      uses: "Estado e fila duráveis no banco do portal."
    },
    "operator-accept": {
      title: "Aceite do atendente",
      short: "Um atendente autorizado assume a conversa por uma atribuição única.",
      detail: "O Django serializa a tomada da fila e persiste o atendente atribuído somente depois da transição autorizada retornar o estado HUMAN para aquele operador.",
      uses: "O aceite define o dono do atendimento humano."
    },
    "automation-suspended": {
      title: "Automação suspensa",
      short: "A automação é suspensa somente depois que o atendente autorizado assume.",
      detail: "A solicitação em espera não suspende automaticamente o turno de chat. A suspensão acontece após o aceite do atendente e o estado HUMAN persistido pelo portal.",
      uses: "Handoff ativo → operador atribuído → automação suspensa."
    }
  };

  const defaultTitle = "Explore a arquitetura";
  const defaultDescription = "Passe o mouse ou toque em um componente; também é possível navegar pelo diagrama com o teclado.";
  let selectedTerm = null;
  let hoveredNode = null;
  let focusedNode = null;
  let tooltipNode = null;

  function nodeTerm(node) {
    return node && node.dataset.flowTerm;
  }

  function visibleNodeForTerm(term) {
    if (!term) return null;
    return nodes.find((node) => nodeTerm(node) === term && node.getBoundingClientRect().width > 0) || null;
  }

  function updateDetails(term) {
    const entry = explanations[term];
    if (!entry) {
      detailsTitle.textContent = defaultTitle;
      detailsDescription.textContent = defaultDescription;
      detailsUses.textContent = "";
      detailsUses.hidden = true;
      return;
    }

    detailsTitle.textContent = entry.title;
    detailsDescription.textContent = entry.detail;
    detailsUses.textContent = entry.uses ? "Utiliza: " + entry.uses : "";
    detailsUses.hidden = !entry.uses;
  }

  function updatePressedState() {
    nodes.forEach((node) => {
      const pressed = selectedTerm !== null && nodeTerm(node) === selectedTerm;
      node.setAttribute("aria-pressed", String(pressed));
    });
  }

  function activeNodeForHighlight() {
    return hoveredNode || focusedNode || visibleNodeForTerm(selectedTerm);
  }

  function updateRelatedHighlights() {
    const activeNode = activeNodeForHighlight();
    const activeGroups = new Set((activeNode?.dataset.flowGroups || "").split(/\s+/).filter(Boolean));

    nodes.forEach((node) => {
      const groups = (node.dataset.flowGroups || "").split(/\s+/).filter(Boolean);
      node.classList.toggle("is-related", activeNode !== null && node !== activeNode && groups.some((group) => activeGroups.has(group)));
    });

    edges.forEach((edge) => {
      const groups = (edge.dataset.flowGroups || "").split(/\s+/).filter(Boolean);
      edge.classList.toggle("is-related", activeNode !== null && groups.some((group) => activeGroups.has(group)));
    });
  }

  function positionTooltip(node) {
    const nodeRect = node.getBoundingClientRect();
    const diagramRect = diagram.getBoundingClientRect();
    if (nodeRect.width === 0 || diagramRect.width === 0) return;

    const tooltipRect = tooltip.getBoundingClientRect();
    const margin = 8;
    const gap = 10;
    const maxLeft = Math.max(margin, diagramRect.width - tooltipRect.width - margin);
    const preferredLeft = nodeRect.left - diagramRect.left + (nodeRect.width - tooltipRect.width) / 2;
    const left = Math.min(maxLeft, Math.max(margin, preferredLeft));
    const above = nodeRect.top - diagramRect.top - tooltipRect.height - gap;
    const below = nodeRect.bottom - diagramRect.top + gap;
    const top = above >= margin ? above : Math.min(Math.max(margin, below), diagramRect.height - tooltipRect.height - margin);

    tooltip.style.left = left + "px";
    tooltip.style.top = Math.max(margin, top) + "px";
  }

  function hideTooltip() {
    if (tooltipNode) tooltipNode.removeAttribute("aria-describedby");
    tooltipNode = null;
    tooltip.hidden = true;
  }

  function syncTooltip() {
    let candidate = hoveredNode || focusedNode;
    if (!candidate && selectedTerm) candidate = visibleNodeForTerm(selectedTerm);
    const entry = candidate ? explanations[nodeTerm(candidate)] : null;

    if (!candidate || !entry) {
      hideTooltip();
      updateRelatedHighlights();
      return;
    }

    if (tooltipNode && tooltipNode !== candidate) tooltipNode.removeAttribute("aria-describedby");
    tooltipNode = candidate;
    tooltipTitle.textContent = entry.title;
    tooltipDescription.textContent = entry.short;
    tooltip.hidden = false;
    candidate.setAttribute("aria-describedby", "home-flow-tooltip");
    positionTooltip(candidate);
    updateRelatedHighlights();
  }

  function selectNode(node) {
    const term = nodeTerm(node);
    selectedTerm = selectedTerm === term ? null : term;
    updatePressedState();
    updateDetails(selectedTerm);
    syncTooltip();
  }

  function clearSelection() {
    selectedTerm = null;
    updatePressedState();
    updateDetails(null);
    syncTooltip();
  }

  nodes.forEach((node) => {
    const entry = explanations[nodeTerm(node)];
    if (entry) node.setAttribute("aria-label", entry.title + ". Selecione para ver detalhes.");

    node.addEventListener("pointerenter", (event) => {
      if (event.pointerType === "touch") return;
      hoveredNode = node;
      syncTooltip();
    });

    node.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "touch") return;
      if (hoveredNode === node) hoveredNode = null;
      syncTooltip();
    });

    node.addEventListener("focus", () => {
      focusedNode = node;
      syncTooltip();
    });

    node.addEventListener("blur", () => {
      if (focusedNode === node) focusedNode = null;
      syncTooltip();
    });

    node.addEventListener("click", () => selectNode(node));

    node.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " " && event.key !== "Spacebar") return;
      event.preventDefault();
      selectNode(node);
    });
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest(".home-flow-node") || section.querySelector("[data-flow-details]").contains(target)) return;
    clearSelection();
  });

  let positionFrame = null;
  const repositionTooltip = () => {
    if (!tooltipNode || positionFrame !== null) return;
    positionFrame = window.requestAnimationFrame(() => {
      positionFrame = null;
      if (!tooltip.hidden && tooltipNode) positionTooltip(tooltipNode);
    });
  };

  window.addEventListener("resize", repositionTooltip, { passive: true });
  window.addEventListener("scroll", repositionTooltip, { passive: true, capture: true });

  updatePressedState();
  updateRelatedHighlights();
})();
