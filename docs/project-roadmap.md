MAPA ATUAL — GETNET SUPPORT POC
================================


1. STACK / ARQUITETURA TÉCNICA                         ✅ CONCLUÍDO


   ✅ Django definido para:
      - frontend/web
      - autenticação/sessão
      - admin


   ✅ FastAPI definido para:
      - APIs internas
      - agentes
      - RAG
      - tools
      - providers


   ✅ LangGraph definido para orquestração futura
   ✅ PostgreSQL definido como banco da POC
   ✅ pgvector definido para vetores
   ✅ Docker definido para infraestrutura local




2. RAG — CONHECIMENTO, FONTES E AVALIAÇÃO


   ✅ Corpus interno R1
      ├─ PDD
      ├─ SDD
      └─ Technical Overview


   ✅ Corpus interno R2
      ├─ PDD
      ├─ SDD
      └─ Technical Overview


   ✅ Códigos Python de referência R1/R2


   ✅ Fontes públicas controladas
      └─ knowledge/internal/cancellation-process/public/sources.yaml
         ├─ cancelamento/corporativo
         └─ produtos, serviços e suporte oficial Getnet


   ✅ Política de segurança interna
      └─ knowledge/internal/security/security-policy.md


   ✅ Dataset de avaliação
      └─ evaluation/rag/dataset-v1.yaml
         ├─ 25 casos
         ├─ rag-019 segurança/credencial
         ├─ rag-025 acesso sensível
         └─ thresholds globais


   ✅ Suíte de cenários do desafio
      └─ evaluation/challenge/scenarios-v1.yaml
         ├─ 14 cenários end-to-end
         ├─ routing e seleção de capacidades
         ├─ RAG vs Web Search
         ├─ tools de Customer Support
         └─ cooperação multiagente e segurança


   ✅ Regras já aprovadas
      ├─ provenance/citation
      ├─ anti-alucinação
      ├─ insufficient evidence
      ├─ source priority
      ├─ allowlist pública
      ├─ prompt injection protection
      └─ segurança/auditoria




3. IMPLEMENTAÇÃO EXECUTÁVEL DO RAG




   3.0 DECISÕES DE ARQUITETURA                         ✅ CONCLUÍDO


      ✅ PostgreSQL + pgvector
      ✅ FastEmbed
      ✅ busca híbrida
      ✅ PostgreSQL Full Text Search
      ✅ busca vetorial
      ✅ RRF
      ✅ lexical candidates = 10
      ✅ semantic candidates = 10
      ✅ final Top-K = 5
      ✅ chunking estrutural
      ✅ provenance
      ✅ checksum para detectar mudanças
      ✅ substituição controlada do documento atual
      ✅ Tavily como web-search provider




   3.1 ESTRUTURA DE CÓDIGO RAG                         ✅ CONCLUÍDO


      ✅ FastAPI main.py
      ✅ /health
      ✅ /ready
      ✅ /chat autenticado sobre o runtime de orquestração
      ✅ autenticação interna Bearer fail-closed


      ✅ RAGService
      ✅ config
      ✅ models


      ✅ ingestion skeleton
      ✅ FastEmbed adapter
      ✅ lexical retrieval skeleton
      ✅ semantic retrieval skeleton
      ✅ hybrid retrieval skeleton
      ✅ RRF skeleton
      ✅ grounding skeleton




   3.2 AMBIENTE PYTHON / DEPENDÊNCIAS                  ✅ CONCLUÍDO


      ✅ .venv
      ✅ política do Harness para uso da .venv
      ✅ FastAPI
      ✅ Pydantic
      ✅ Uvicorn
      ✅ FastEmbed
      ✅ PyYAML
      ✅ HTTPX
      ✅ pytest
      ✅ pyproject.toml
      ✅ editable install
      ✅ pip check
      ✅ imports validados
      ✅ compileall validado




4. POSTGRESQL + PGVECTOR                               ✅ CONCLUÍDO




   4.0 INFRAESTRUTURA DO BANCO                         ✅ CONCLUÍDO


      ✅ Docker Desktop
      ✅ Docker Engine
      ✅ Docker Compose
      ✅ docker-compose.yml
      ✅ .env local protegido
      ✅ .env.example no Git
      ✅ PostgreSQL 17
      ✅ container healthy
      ✅ volume persistente
      ✅ conexão DBeaver
      ✅ extensão pgvector 0.8.6




4.1 ARQUITETURA DOS SCHEMAS                         ✅ CONCLUÍD


   Objetivo:
   Definir conceitualmente a responsabilidade de cada schema,
   os limites entre eles e como os dados se relacionam.


   4.1.1 DEFINIR RESPONSABILIDADE DO SCHEMA RAG      ✅ CONCLUÍDO


      Finalidade:
      armazenar e organizar o conhecimento utilizado pelo RAG.


      Deve contemplar conceitualmente:
      - fontes de conhecimento
      - documentos
      - chunks
      - embeddings
      - provenance
      - busca lexical
      - busca semântica
      - metadados de execução de ingestão


      Não definir ainda:
      - campos
      - tipos
      - PK/FK
      - índices
      - VECTOR(N)
      - DDL




   4.1.2 DEFINIR RESPONSABILIDADE DO SCHEMA OPS       ✅ CONCLUÍDO


      Finalidade:
      representar o comportamento operacional observado do RPA.


      Estruturas conceituais aprovadas:
      - ops.automation_runs
      - ops.incoming_emails
      - ops.email_attachments
      - ops.service_requests
      - ops.establishments
      - ops.execution_log


      Regras aprovadas:
      - R1 recebe a solicitação e cria o protocolo
      - R2 monitora e continua um protocolo existente
      - um protocolo pode ser acompanhado por múltiplas execuções R2
      - execution_log mantém a linha do tempo operacional detalhada
      - e-mail existe independentemente da geração de protocolo
      - modelo Oracle reconstruído é somente referência funcional
      - nenhuma tabela física ops foi criada




   4.1.3 DEFINIR RESPONSABILIDADE DO SCHEMA AUDIT     ✅ CONCLUÍDO


      Finalidade:
      registrar eventos de segurança e governança detectados pelos
      controles do agente ou da aplicação.


      Estrutura conceitual aprovada:
      - audit.security_events


      Deve registrar conceitualmente:
      - categoria do evento de segurança/governança
      - componente de origem e referência da solicitação
      - conteúdo sanitizado
      - ação tomada
      - resultado
      - metadados opcionais de revisão


      Regras aprovadas:
      - nenhum secret ou credencial real pode ser persistido
      - logs operacionais R1/R2 permanecem em ops
      - conhecimento e retrieval permanecem em rag
      - nenhuma tabela física audit foi criada




   4.1.4 DEFINIR LIMITES E FLUXO ENTRE OS SCHEMAS     ✅ CONCLUÍDO


      Responsabilidades aprovadas:


      rag
      → conhecimento e comportamento esperado


      ops
      → fatos e estado operacional observados


      audit
      → eventos de segurança e governança


      Fluxo aprovado:
      - application/agents consultam um ou mais schemas conforme necessário
      - LLM interpreta as evidências e produz conclusão grounded
      - LangGraph permanece como camada planejada de orquestração
      - não há cópia ou sincronização automática entre domínios
      - AUDIT não é log geral de interações ou operações RPA
      - respostas geradas pelo LLM não viram conhecimento RAG automaticamente
      - nenhuma FK ou implementação física entre schemas foi definida




   4.1.5 APROVAR ARQUITETURA CONCEITUAL DOS SCHEMAS   ✅ CONCLUÍDO


      Critérios para concluir 4.1:


      - responsabilidade de rag aprovada
      - responsabilidade de ops aprovada
      - responsabilidade de audit aprovada
      - limites entre schemas aprovados
      - nenhuma sobreposição relevante de responsabilidade
      - fluxo de consulta entre schemas compreendido


      Resultado esperado:


      PostgreSQL
      ├── rag
      │   └── conhecimento e retrieval
      │
      ├── ops
      │   └── estado operacional do RPA
      │
      └── audit
          └── segurança e governança


      Após aprovação:
      avançar para 4.2 — Arquitetura do Schema RAG.




   4.2 ARQUITETURA DO SCHEMA RAG                       ✅ CONCLUÍDO


      Estruturas conceituais aprovadas:
      - rag.sources
      - rag.documents
      - rag.chunks
      - rag.ingestion_runs


      Relacionamentos conceituais aprovados:
      - source 1:N documents
      - document 1:N chunks
      - document 1:N ingestion_runs


      Regras aprovadas:
      - rag.chunks como unidade principal de busca (retrieval unit)
      - cadeia de proveniência: chunk -> document -> source
      - controle de alteração/reprocessamento por checksum
      - sem versionamento histórico de documentos ou chunks
      - rastreamento de execução de ingestão (ingestion tracking)
      - ingestão desacoplada da busca em query-time
      - nenhuma tabela física rag criada; sem DDL, tipos ou VECTOR(N)


   4.3 ARQUITETURA DO SCHEMA OPS                       ✅ CONCLUÍDO


      Detalhar as seis estruturas conceituais OPS aprovadas,
      seus relacionamentos e regras:
      - ops.automation_runs
      - ops.incoming_emails
      - ops.email_attachments
      - ops.service_requests
      - ops.establishments
      - ops.execution_log


      Resumo aprovado da arquitetura conceitual OPS:
      - seis estruturas: ops.automation_runs, ops.incoming_emails,
        ops.email_attachments, ops.service_requests, ops.establishments e
        ops.execution_log
      - uma execução processa N itens;
      - uma execução R1 processa N incoming_emails;
      - um incoming_email possui N email_attachments;
      - um incoming_email possui 0..1 service_request;
      - um e-mail corresponde a um protocolo único, reutilizado pelo R2;
      - service_requests não possui attachment_id;
      - establishments possui generated_file_name;
      - o handoff R1 -> R2 ocorre por establishments;
      - o estado atual fica em establishments;
      - o histórico cronológico fica em execution_log;
      - um item pode ser observado por múltiplas execuções R2;
      - timestamps representam data e hora completas;
      - nenhuma estrutura física foi criada.

      O Oracle reconstruído permanece somente como referência funcional;
      seus nomes físicos e separação de tabelas não serão reproduzidos.




   4.4 ARQUITETURA DO SCHEMA AUDIT                     ✅ CONCLUÍDO


      Estrutura conceitual aprovada a detalhar:


      audit.security_events


      Para registrar:
      - credential request
      - secret request
      - database access request
      - prompt injection
      - bypass attempt
      - sensitive infrastructure request
      - texto sanitizado
      - ação tomada

      Arquitetura conceitual aprovada:
      - campos: event_id, occurred_at, event_type, source_component,
        user_identifier, request_reference, resource_category,
        sanitized_content, action_taken, result, review_status, reviewed_at,
        review_note e created_at;
      - um request produz 0..N eventos; normal=0, protected simples=1,
        multi-threat=N;
      - cada evento possui um único event_type; eventos multi-threat compartilham
        request_reference, sem arrays, coleções JSON ou tabelas de junção;
      - sanitização/redação ocorre antes da persistência;
      - fluxo: input -> detection -> sanitization/redaction -> action ->
        persistência -> safe response;
      - AUDIT contém somente evidência de segurança/governança sanitizada;
      - nenhuma estrutura física, tipo SQL, enum, constraint, índice, migration
        ou DDL foi criada.




### 4.5 MODELO FÍSICO DO BANCO DE DADOS — ✅ CONCLUÍDO

#### 4.5.1 CONVENÇÕES FÍSICAS GLOBAIS ✅ CONCLUÍDO
#### 4.5.2 MODELO FÍSICO DO SCHEMA RAG  ✅ CONCLUÍDO
#### 4.5.3 DECISÃO FINAL DO MODELO FASTEMBED  ✅ CONCLUÍDO
#### 4.5.4 FULL TEXT SEARCH — MODELO FÍSICO  ✅ CONCLUÍDO
#### 4.5.5 PGVECTOR — MODELO FÍSICO  ✅ CONCLUÍDO
#### 4.5.6 MODELO FÍSICO DO SCHEMA OPS  ✅ CONCLUÍDO
#### 4.5.7 MODELO FÍSICO DO SCHEMA AUDIT  ✅ CONCLUÍDO
#### 4.5.8 ESTRATÉGIA DE ÍNDICES  ✅ CONCLUÍDO
#### 4.5.9 CONSTRAINTS E INTEGRIDADE  ✅ CONCLUÍDO
#### 4.5.10 NULLABILITY E ESTADOS PARCIAIS  ✅ CONCLUÍDO
#### 4.5.11 DELETE / RETENTION / CASCADE BEHAVIOR  ✅ CONCLUÍDO
#### 4.5.12 PERFORMANCE E VOLUME DO POC  ✅ CONCLUÍDO
#### 4.5.13 SEGURANÇA DO MODELO FÍSICO  ✅ CONCLUÍDO
#### 4.5.14 ESPECIFICAÇÃO FÍSICA FINAL  ✅ CONCLUÍDO
#### 4.5.15 DOCUMENTAÇÃO E DECISION LOG  ✅ CONCLUÍDO
#### 4.5.16 CRITÉRIOS DE CONCLUSÃO DO 4.5  ✅ CONCLUÍDO



### 4.6 CRIAR TABELAS / DDL / MIGRATIONS ✅ CONCLUÍDO

#### 4.6.1 DEFINIR ESTRATÉGIA DE MIGRATIONS  ✅ CONCLUÍDO
#### 4.6.2 DEFINIR ESTRUTURA E ORDEM DAS MIGRATIONS  ✅ CONCLUÍDO
#### 4.6.3 CRIAR PRÉ-REQUISITOS POSTGRESQL E SCHEMAS  ✅ CONCLUÍDO
#### 4.6.4 CRIAR TABELAS DO SCHEMA RAG  ✅ CONCLUÍDO
#### 4.6.5 CRIAR TABELAS DO SCHEMA OPS  ✅ CONCLUÍDO
#### 4.6.6 CRIAR TABELA DO SCHEMA AUDIT  ✅ CONCLUÍDO
#### 4.6.7 IMPLEMENTAR CONSTRAINTS E INTEGRIDADE  ✅ CONCLUÍDO
#### 4.6.8 CRIAR ÍNDICES E ACCESS PATHS  ✅ CONCLUÍDO
#### 4.6.9 DEFINIR COMPORTAMENTO DE EXECUÇÃO, TRANSAÇÃO E ROLLBACK  ✅ CONCLUÍDO
#### 4.6.10 APLICAR MIGRATIONS NO POSTGRESQL LOCAL  ✅ CONCLUÍDO
#### 4.6.11 VALIDAR ESTRUTURA FÍSICA CRIADA  ✅ CONCLUÍDO
#### 4.6.12 ATUALIZAR DOCUMENTAÇÃO E DECISION LOG  ✅ CONCLUÍDO
#### 4.6.13 CRITÉRIOS DE CONCLUSÃO DO 4.6  ✅ CONCLUÍDO


### 4.7 DEPENDÊNCIAS PYTHON DO BANCO ✅ CONCLUÍDO

#### 4.7.1 LEVANTAR REQUISITOS DA CAMADA PYTHON DE BANCO  ✅ CONCLUÍDO
#### 4.7.2 DEFINIR ESTRATÉGIA DE ACESSO PYTHON AO POSTGRESQL  ✅ CONCLUÍDO
#### 4.7.3 DEFINIR DRIVER POSTGRESQL E MODO DE INSTALAÇÃO  ✅ CONCLUÍDO
#### 4.7.4 AVALIAR NECESSIDADE DO SQLALCHEMY  ✅ CONCLUÍDO
#### 4.7.5 DEFINIR INTEGRAÇÃO PYTHON COM PGVECTOR  ✅ CONCLUÍDO
#### 4.7.6 DEFINIR DEPENDÊNCIAS E VERSÕES APROVADAS  ✅ CONCLUÍDO
#### 4.7.7 ATUALIZAR PYPROJECT.TOML  ✅ CONCLUÍDO
#### 4.7.8 INSTALAR DEPENDÊNCIAS NO AMBIENTE PYTHON  ✅ CONCLUÍDO
#### 4.7.9 VALIDAR INSTALAÇÃO, IMPORTS E COMPATIBILIDADE  ✅ CONCLUÍDO
#### 4.7.10 ATUALIZAR DOCUMENTAÇÃO E DECISION LOG  ✅ CONCLUÍDO
#### 4.7.11 CRITÉRIOS DE CONCLUSÃO DO 4.7  ✅ CONCLUÍDO




### 4.8 CAMADA DE ACESSO AO BANCO  ✅ CONCLUÍDO / APROVADO

#### 4.8.1 DEFINIR ARQUITETURA DA CAMADA DE ACESSO AO BANCO  ✅ CONCLUÍDO
#### 4.8.2 DEFINIR CONFIGURAÇÃO E PARÂMETROS DE CONEXÃO  ✅ CONCLUÍDO
#### 4.8.3 DEFINIR LIFECYCLE DE CONEXÕES E CONNECTION POOL  ✅ CONCLUÍDO
#### 4.8.4 IMPLEMENTAR COMPONENTE CENTRAL DE CONEXÃO POSTGRESQL  ✅ CONCLUÍDO
#### 4.8.5 INTEGRAR PGVECTOR AO LIFECYCLE DAS CONEXÕES  ✅ CONCLUÍDO
#### 4.8.6 DEFINIR CONTRATOS E RESPONSABILIDADES DOS REPOSITORIES  ✅ CONCLUÍDO
#### 4.8.7 IMPLEMENTAR RAGREPOSITORY  ✅ CONCLUÍDO
#### 4.8.8 IMPLEMENTAR OPERATIONALREPOSITORY  ✅ CONCLUÍDO
#### 4.8.9 IMPLEMENTAR AUDITREPOSITORY  ✅ CONCLUÍDO
#### 4.8.10 IMPLEMENTAR CONTROLE TRANSACIONAL DA CAMADA DE ACESSO  ✅ CONCLUÍDO
#### 4.8.11 IMPLEMENTAR MAPEAMENTO DE RESULTADOS PARA MODELOS PYTHON  ✅ CONCLUÍDO
#### 4.8.12 IMPLEMENTAR TRATAMENTO DE ERROS DE BANCO  ✅ CONCLUÍDO
#### 4.8.13 VALIDAR CONEXÃO REAL COM POSTGRESQL  ✅ CONCLUÍDO
#### 4.8.14 VALIDAR REPOSITORIES E OPERAÇÕES BÁSICAS  ✅ CONCLUÍDO
#### 4.8.15 ATUALIZAR DOCUMENTAÇÃO E DECISION LOG  ✅ CONCLUÍDO
#### 4.8.16 CRITÉRIOS DE CONCLUSÃO DO 4.8  ✅ CONCLUÍDO




   4.9 DADOS FICTÍCIOS / SEED                          ✅ COMPLETED / APPROVED

      4.9.1 DEFINIR ESTRUTURA REUTILIZÁVEL DE SEED OPS  ✅ CONCLUÍDO
      4.9.2 INSERIR CASO 001 — SUCESSO R1/R2            ✅ CONCLUÍDO
      4.9.3 DEFINIR E INSERIR CENÁRIOS OPS ADICIONAIS    ✅ CONCLUÍDO


      - execuções RPA
      - protocolos
      - logs
      - alertas
      - status R1/R2
      - casos de sucesso/erro/atraso




   4.10 VALIDAÇÃO DO BANCO                             ✅ COMPLETED / APPROVED


      - conexão
      - inserts
      - FKs
      - constraints
      - pgvector
      - FTS
      - dados operacionais
      - auditoria




5. INGESTION EXECUTÁVEL                                ✅ CONCLUÍDO

   5.1 Loader real                                      ✅ CONCLUÍDO
   5.2 Normalization                                    ✅ CONCLUÍDO
   5.3 Validator                                        ✅ CONCLUÍDO
   5.4 Checksum                                         ✅ CONCLUÍDO
   5.5 INGEST / REINGEST / SKIPPED_UNCHANGED           ✅ CONCLUÍDO
   5.6 Controlled reprocessing preparation              ✅ CONCLUÍDO
   5.7 Structural chunking                              ✅ CONCLUÍDO
   5.8 Metadata + provenance                            ✅ CONCLUÍDO
   5.9 Prepared ingestion contracts                     ✅ CONCLUÍDO
   5.10 Ingestion application service                   ✅ CONCLUÍDO
   5.11 Manual CLI entry points                         ✅ CONCLUÍDO
   5.12 Real corpus validation                          ✅ CONCLUÍDO
   5.13 Regression validation                           ✅ CONCLUÍDO
   5.14 Database safety validation                      ✅ CONCLUÍDO
   5.15 Documentation / completion gate                 ✅ CONCLUÍDO

   Phase 5 produces deterministic validated PreparedChunks only.
   Phase 6 owns FastEmbed 384, FTS payload preparation, and atomic PostgreSQL publication.




6. FASTEMBED EXECUTÁVEL                                ✅ CONCLUÍDO

   6.1 FastEmbed adapter                                ✅ CONCLUÍDO
   6.2 Validação de embeddings (384 dims, finite)       ✅ CONCLUÍDO
   6.3 Integração PreparedIngestion -> Embeddings       ✅ CONCLUÍDO
   6.4 Geração nativa PostgreSQL FTS (pesos A,B,C,D)    ✅ CONCLUÍDO
   6.5 Contratos de publicação (PublicationChunk/Result)✅ CONCLUÍDO
   6.6 RAGPublicationService centralizado               ✅ CONCLUÍDO
   6.7 Publicação atômica PostgresDatabase.transaction  ✅ CONCLUÍDO
   6.8 SKIPPED_UNCHANGED e REINGEST atômico             ✅ CONCLUÍDO
   6.9 Validação E2E com corpus curado real (99 chunks) ✅ CONCLUÍDO
   6.10 Regressão e documentação                        ✅ CONCLUÍDO

   Modelo aprovado: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
   Dimensão: 384 / VECTOR(384)
   Execução: Local CPU (ONNX Runtime), sem normalização manual de vetores.
   Corpus real publicado: PDD (52 chunks), SDD (20 chunks), Tech Overview (27 chunks).
   Smoke tests: Lexical search (FTS) e Semantic search (pgvector) validados no banco real.




7. HYBRID RETRIEVAL + RRF                              ✅ CONCLUÍDO


   PostgreSQL FTS → Top 10
   pgvector       → Top 10
           ↓
          RRF
           ↓
         Top 5

   REPEATABLE READ / READ ONLY snapshot; RRF k=60; chunk_id deduplication
   with best-channel-rank and stable chunk_id tie-breaking.




8. GROUNDING / ANTI-ALUCINAÇÃO                         ✅ CONCLUÍDO


   - evidência suficiente
   - evidência insuficiente
   - provenance
   - citation
   - source priority
   - resposta grounded

   GroundedContext imutável e provider-neutral, com provenance completo,
   citações determinísticas e suficiência estrutural. Sem geração por LLM.




9. MULTI-AGENT + RAG + TOOLS + TAVILY                 ✅ CONCLUÍDO

   9.1 SDD Foundation, 9.2 LLM Provider / DeepSeek, 9.3 Knowledge Agent,
   9.4 OPS Tools, 9.5 Customer Support Agent, 9.6 Router Agent, and 9.7 LangGraph
   orchestration and 9.8 Tavily fallback are complete. Knowledge composes the approved Hybrid Retrieval/RRF and
   ContextBuilder boundaries with the provider-neutral LLM interface, returns
   controlled insufficient-evidence results without LLM invocation, and exposes
   only safe citations. Real PostgreSQL retrieval/grounding and opt-in DeepSeek
   validation passed; the API key remains local runtime configuration and is not
   committed. Phase 9.8 provides bounded, provider-neutral Tavily public live
   evidence only: current questions use it directly and Payment Link/WhatsApp
   uses RAG first with controlled fallback. Live evidence passes typed
   non-persistent grounding before generation; official Getnet priority is read
   from the approved source registry. It never persists web results or obtains
   private OPS facts. Phase 9.9 Human Escalation is complete: explicit
   confirmation reaches `WAITING_HUMAN`, authorized operator acceptance alone
   reaches human ownership, and only human ownership suspends automation. It
   is non-persistent and has no Django or ticket implementation. Phase 9.10
   `/chat` is complete: strict authenticated FastAPI transport maps through a
   narrow application adapter to orchestration and returns only allowlisted,
   provider-neutral responses. Phase 9.11 completed authenticated end-to-end
   validation of all fourteen approved challenge scenarios. The protected-route
   integration now records one sanitized security event through the approved
   `SecurityAuditService -> PostgresSecurityAuditSink -> AuditRepository`
   boundary; failure stays blocked and controlled. Phase 9 is complete. The
   next reviewed scope is Phase 10 SECURITY / AUDIT RUNTIME; that broader phase
   is not completed by the minimum Phase 9 audit integration.
   Phase 9.4 provides read-only, authorization-gated
   `lookup_protocol_status` and `inspect_execution_failure` application tools
   over the approved `OperationalRepository`; they return observed typed facts
   only and were validated against persisted synthetic OPS records. Phase 9.5
   consumes only these tools and the provider-neutral LLM boundary; it keeps
   deterministic observed facts separate from explicitly labeled LLM inferences.
   Phase 9.6 returns only immutable typed capability decisions and security blocks;
   it executes no specialized agent, tool, web search, or human handoff.
   Phase 9.7 coordinates those decisions through an acyclic LangGraph topology,
   preserves Knowledge citations and Customer Support FACT/INFERENCE results, and
   terminates security, ambiguity, web-pending, and human-pending routes safely.


   Router Agent
   ├─ Knowledge Agent
   │  ├─ RAG interno
   │  ├─ RAG público Getnet aprovado
   │  └─ Tavily/Web Search controlado
   ├─ Customer Support Agent
   │  ├─ tools controladas de cliente/OPS:
   │  │  ├─ lookup_protocol_status (fatos do estado operacional de protocolo)
   │  │  └─ inspect_execution_failure (evidências operacionais de falha de execução)
   │  ├─ interpretação de causa-raiz provável baseada em evidências (fato vs inferência)
   │  ├─ oferta explícita de escalonamento humano após diagnóstico quando apropriado
   │  ├─ handoff confirmado pelo usuário para o Human Escalation Agent
   │  └─ abertura/tratamento de ticket de suporte conduzido por humano após assunção
   ├─ Human Escalation Agent
   │  ├─ acionar quando o usuário solicitar atendimento humano
   │  ├─ acionar quando o sistema não conseguir resolver com evidência/confiança suficiente
   │  ├─ solicitar confirmação do usuário antes da transferência
   │  ├─ manter a conversa ativa na mesma experiência de chat
   │  ├─ encaminhar a conversa para uma fila de atendimento humano
   │  ├─ permitir que um segundo usuário autenticado, atuando como atendente, aceite e continue a conversa
   │  ├─ suspender respostas automáticas enquanto o atendimento estiver sob responsabilidade humana
   │  ├─ permitir devolução explícita do controle ao fluxo automatizado
   │  ├─ transferir somente o contexto necessário da conversa ativa
   │  ├─ não implementar memória persistente entre sessões/conversas
   │  ├─ tornar estado e responsável pelo handoff observáveis e testáveis
   │  └─ considerar WhatsApp apenas como possível canal futuro; a POC inicial usa o próprio chat da aplicação
   └─ coordenação multiagente quando necessária


10. SECURITY / AUDIT RUNTIME                           CONCLUÍDO


    detectar solicitação sensível
    ↓
    bloquear
    ↓
    sanitizar
    ↓
    audit.security_events
    ↓
    resposta de política




11. EVALUATION RUNNER                                  CONCLUÍDO


    11.1 SDD FOUNDATION                              CONCLUÍDO
        corrective contract review                   CONCLUÍDO
        mandatory local RAG and source manifest      CONCLUÍDO
    11.2 dataset contracts and versioned adapters    CONCLUÍDO (6/6 retrieval source mappings; security-only source excluded)
    11.3 RAG evaluation runner                       CONCLUÍDO (typed boundary; v1.1 27-case closure run)
    11.4 challenge evaluation runner                 CONCLUÍDO (14 deterministic authenticated observations; DEC-181 implementation reconciled)
    11.5 metrics and reporting                       CONCLUÍDO (v1.1 deterministic JSON; overall PASS)
    11.6 validation and closure                      CONCLUÍDO (REVALIDATED)
    Phase 11 closure                                  CLOSED / CONCLUÍDO
    next reviewed phase                               12. DJANGO / FRONTEND / INTEGRAÇÃO FINAL


    executar evaluation/rag/dataset-v1.1.yaml
    ├─ 27 casos de RAG/grounding/security/insufficient-evidence
    └─ medir:
       - Top-5 source rate
       - provenance
       - unsupported facts
       - insufficient evidence
       - security blocking
       - audit logging
       - redaction


    executar evaluation/challenge/scenarios-v1.yaml
    └─ 14 cenários de routing/capabilities/tools/cooperação




12. DJANGO / FRONTEND / INTEGRAÇÃO FINAL
   OWNER APPROVED / IMPLEMENTATION IN PROGRESS
    12.1 COMPLETED / OWNER APPROVED; 12.2 COMPLETED; 12.3 COMPLETED; 12.4 COMPLETED; 12.5 COMPLETED; 12.6 COMPLETED; 12.7 COMPLETED; 12.8 COMPLETED; 12.9 COMPLETED; 12.10 COMPLETED; 12.11 COMPLETED; 12.12 COMPLETED; 12.13 COMPLETED; 12.14 COMPLETE; 12.15 COMPLETE; 12.16 NEXT

   Authority: docs/specs/phase-12/00-phase-12-spec.md and linked specs.
   Architecture: apps/agent_api remains FastAPI; apps/web_portal is Django BFF.
   Schemas: portal owns web state; rag, ops and audit ownership is preserved.

12.1 SDD FOUNDATION E ARQUITETURA WEB
     CONCLUÍDO / OWNER APPROVED
     - owner review and approval gate before implementation
     - browser -> Django -> authenticated internal FastAPI boundary
     - Django/FastAPI ownership, module structure, scope and invariants

12.2 ESTRUTURA DO SERVIÇO DJANGO
     CONCLUÍDO
     - apps/web_portal modular config/accounts/conversations/support/admin_portal/integrations
     - settings, URL composition, templates, static assets and service health
     - no agent, Router, RAG or OPS logic duplicated

12.3 SCHEMA PORTAL E MODELO DE DADOS WEB
     CONCLUIDO
     - native migration 0007 creates only the portal schema
     - custom UUID User and five portal application models were migrated explicitly
     - Django framework tables resolve inside portal; RAG/OPS/AUDIT data is preserved
     - constraints, lifecycle, indexes and PostgreSQL validation passed

12.4 USUÁRIOS, AUTENTICAÇÃO E RBAC
     CONCLUÍDO / DEPENDE DE 12.3
     - ADMIN / CLIENT / SUPPORT_AGENT identity; is_active is the account access gate
     - ADMIN-only account service, normalized login, password hashing and session revocation
     - protected bootstrap_admin and concurrency-safe last-active-ADMIN guard
     - reusable route/object authorization and role-gated read-only technical Django Admin

12.5 LOGIN, SESSÃO E CONTROLE DE ACESSO
     CONCLUÍDO / DEPENDE DE 12.4
     - server-derived CLIENT / SUPPORT_AGENT / ADMIN landing routes and strict HTTP 403 role separation
     - CSRF-protected login/logout, generic credential failures and session fixation protection
     - 30-minute inactivity plus independent eight-hour absolute session lifetime
     - inactive/role/password revocation defense and environment-driven secure cookie policy
     - no registration, Remember Me or unfinished Forgot Password control

12.6 PERSISTÊNCIA DE CONVERSAS E MENSAGENS
     CONCLUÍDO / DEPENDE DE 12.3-12.5
     - atomic conversation/first-turn creation and immutable same-thread transcript services
     - conversation-scoped CLIENT idempotency and deterministic at-most-one AGENT persistence
     - provider-neutral same-conversation context: 12 prior messages and 6,000 characters
     - explicit oversized-current context truncation while preserving the complete persisted message
     - lifecycle write enforcement, owned queries and cross-conversation isolation

12.7 PORTAL DO CLIENTE / CHAT
     CONCLUÍDO / DEPENDE DE 12.6
     - login-protected client chat, new conversation and owned full history
     - ACTIVE, WAITING_HUMAN and HUMAN message entry; BLOCKED/CLOSED read-only; DELETED hidden
     - CSRF-protected idempotent forms, responsive accessible templates and safe pending/failure states
     - general agent transport was deferred to Phase 12.13 and is now implemented there

12.8 HUMAN ESCALATION E PORTAL DO SUPPORT_AGENT
     CONCLUÍDO / DEPENDE DE 12.6-12.7
     - reuse FastAPI Human Escalation transitions
     - narrow trusted FastAPI transition transport for confirmation, claim and resolution
     - WAITING queue, atomic single-agent claim and assigned conversations
     - same-thread human messages, automation suspension and finalization
     - HTTP polling initially; no WebSocket requirement

12.9 ADMINISTRAÇÃO DE USUÁRIOS
     CONCLUÍDO / DEPENDE DE 12.4-12.5
     - user list/search/create/activate/block/role/password workflows
     - protect last active ADMIN; prefer deactivation to physical deletion

12.10 DASHBOARD DE SEGURANÇA
      CONCLUÍDO / API INTERNA AUDIT READ-ONLY AUTORIZADA NESTA ETAPA
      - ADMIN-only dashboard from audit.security_events
      - internal FastAPI/AuditRepository typed read API
      - date, event type, source and supported user filters; charts and events
      - Django does not query audit directly

12.11 ADMINISTRAÇÃO DE CONVERSAS
      CONCLUÍDO / DEPENDE DE 12.6 E 12.9
      - bounded search, filters, pagination, safe metadata and full transcript inspection
      - transactional block/unblock preserves valid prior state and HUMAN assignment
      - soft-delete records ADMIN actor/time and retains conversation, messages and handoff
      - active WAITING_HUMAN/HUMAN handoffs cannot be soft-deleted

12.12 FLUXO DE RECUPERAÇÃO DE SENHA
      CONCLUÍDO / DEPENDE DE 12.9
      - generic non-enumerating public request confirmation
      - ADMIN OPEN queue with bounded filters/pagination and terminal RESOLVED/REJECTED actions
      - Phase 12.4 password service hashes new credentials and revokes target sessions
      - PostgreSQL concurrency proves one terminal winner; no email, token, or plaintext persistence

12.13 INTEGRAÇÃO DJANGO  FASTAPI
      COMPLETED / VALIDATED / DEPENDE DE 12.2, 12.4, 12.6 E 12.8
      - authenticated /chat with typed same-conversation context and turn correlation
      - trusted identity/role and policy-derived OPS authorization
      - general agent execution; narrow AUDIT and Human Escalation boundaries remain owned by 12.10 and 12.8
      - bounded timeout/retry behavior, idempotency, stale-state checks and safe result persistence
      - full regression, isolated PostgreSQL, Django checks, Docker readiness and security scans passed

12.14 TESTES DE SEGURANÇA / AUTORIZAÇÃO / E2E
      COMPLETE / VALIDATION PASSED
      - route/object/CSRF/session and trusted-claim forgery matrix
      - concurrent handoff claim and HUMAN automation suspension
      - complete client -> AI -> support -> finalized client history journey
      - AUDIT/dashboard sanitization and no-secret checks
      - 36 protected routes and 21 browser mutation routes covered by security matrices
      - isolated PostgreSQL Django suite: 189 tests passed; full pytest: 922 passed, 37 skipped, 1 known warning
      - no migration drift; Docker configuration valid; agent-api healthy and /ready returned HTTP 200
      - Phase 12.15 had not started when the Phase 12.14 validation closed

12.15 DOCKER COM DJANGO
      COMPLETE / VALIDATION PASSED
      - separately built web-portal added; existing postgres/agent-api names and loopback mappings preserved
      - portal exposed only at 127.0.0.1:8001; private API/database DNS and browser boundary validated
      - safe liveness/readiness, static assets, health ordering, and controlled agent outage/recovery validated
      - clean image build; runtime-only secrets; startup runs no migration, seed, or admin bootstrap
      - docker compose down/up without -v preserved exact PostgreSQL volume, all domain counts, and pgvector
      - evidence and explicit operator procedures recorded in phase-12/11-docker-and-deployment-spec.md

12.16 VALIDAÇÃO FINAL DA PHASE 12
      NEXT / NÃO INICIADO / DEPENDE DA REVISÃO DE 12.15
      - full project and Phase 9-11 regressions
      - PostgreSQL, security, dependency, container and performance checks
      - complete 100-requirement traceability with passing evidence
      - resolve all acceptance failures before closure

12.17 DOCUMENTAÇÃO / DECISION LOG / CLOSURE
      NÃO INICIADO / OWNER REVIEW REQUIRED
      - update project-context and append approved Decision Log record
      - reconcile roadmap and Phase 12 SDD with actual implementation
      - owner reviews evidence and explicitly approves Phase 12 closure


13. TESTES E ENTREGA DA POC                            ⏳


    - testes unitários
    - integração
    - segurança
    - RAG evaluation
    - Docker completo
    - documentação
    - validação final do Harness
