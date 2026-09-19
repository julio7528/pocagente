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
      └─ knowledge/public/sources.yaml
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
         ├─ 13 cenários end-to-end
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
      ✅ /chat placeholder
      ✅ autenticação interna fail-closed


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




4. POSTGRESQL + PGVECTOR                               ← ESTAMOS AQUI




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



### 4.6 CRIAR TABELAS / DDL / MIGRATIONS ← AGORA

#### 4.6.1 DEFINIR ESTRATÉGIA DE MIGRATIONS  ✅ CONCLUÍDO
#### 4.6.2 DEFINIR ESTRUTURA E ORDEM DAS MIGRATIONS  ✅ CONCLUÍDO
#### 4.6.3 CRIAR PRÉ-REQUISITOS POSTGRESQL E SCHEMAS  ← AGORA
#### 4.6.4 CRIAR TABELAS DO SCHEMA RAG
#### 4.6.5 CRIAR TABELAS DO SCHEMA OPS
#### 4.6.6 CRIAR TABELA DO SCHEMA AUDIT
#### 4.6.7 IMPLEMENTAR CONSTRAINTS E INTEGRIDADE
#### 4.6.8 CRIAR ÍNDICES E ACCESS PATHS
#### 4.6.9 DEFINIR COMPORTAMENTO DE EXECUÇÃO, TRANSAÇÃO E ROLLBACK
#### 4.6.10 APLICAR MIGRATIONS NO POSTGRESQL LOCAL
#### 4.6.11 VALIDAR ESTRUTURA FÍSICA CRIADA
#### 4.6.12 ATUALIZAR DOCUMENTAÇÃO E DECISION LOG
#### 4.6.13 CRITÉRIOS DE CONCLUSÃO DO 4.6


   4.7 DEPENDÊNCIAS PYTHON DO BANCO                    ⏳


      Previstas:
      - SQLAlchemy
      - psycopg
      - pgvector




   4.8 CAMADA DE ACESSO AO BANCO                       ⏳


      RAGRepository
      OperationalRepository
      AuditRepository




   4.9 DADOS FICTÍCIOS / SEED                          ⏳


      - execuções RPA
      - protocolos
      - logs
      - alertas
      - status R1/R2
      - casos de sucesso/erro/atraso




   4.10 VALIDAÇÃO DO BANCO                             ⏳


      - conexão
      - inserts
      - FKs
      - constraints
      - pgvector
      - FTS
      - dados operacionais
      - auditoria




5. INGESTION EXECUTÁVEL                                ⏳


   loader real
   ↓
   validator
   ↓
   checksum
   ↓
   reprocessamento controlado
   ↓
   structural chunking
   ↓
   metadata
   ↓
   PostgreSQL




6. FASTEMBED EXECUTÁVEL                                ⏳


usar modelo aprovado:
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
↓
usar dimensão aprovada:
384 / VECTOR(384)
↓
gerar embeddings
↓
persistir em rag.chunks

Implementação de runtime permanece pendente; esta etapa não cria DDL,
migrações ou objetos de banco.




7. HYBRID RETRIEVAL + RRF                              ⏳


   PostgreSQL FTS → Top 10
   pgvector       → Top 10
           ↓
          RRF
           ↓
         Top 5




8. GROUNDING / ANTI-ALUCINAÇÃO                         ⏳


   - evidência suficiente
   - evidência insuficiente
   - provenance
   - citation
   - source priority
   - resposta grounded




9. MULTI-AGENT + RAG + TOOLS + TAVILY                 ⏳


   Router Agent
   ├─ Knowledge Agent
   │  ├─ RAG interno
   │  ├─ RAG público Getnet aprovado
   │  └─ Tavily/Web Search controlado
   ├─ Customer Support Agent
   │  └─ tools controladas de cliente/OPS
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


10. SECURITY / AUDIT RUNTIME                           ⏳


    detectar solicitação sensível
    ↓
    bloquear
    ↓
    sanitizar
    ↓
    audit.security_events
    ↓
    resposta de política




11. EVALUATION RUNNER                                  ⏳


    executar evaluation/rag/dataset-v1.yaml
    ├─ 25 casos de RAG/grounding/security
    └─ medir:
       - Top-5 source rate
       - provenance
       - unsupported facts
       - insufficient evidence
       - security blocking
       - audit logging
       - redaction


    executar evaluation/challenge/scenarios-v1.yaml
    └─ 13 cenários de routing/capabilities/tools/cooperação




12. DJANGO / FRONTEND / INTEGRAÇÃO FINAL               ⏳


    Django
       ↓
    FastAPI
       ↓
    LangGraph
       ↓
    RAG / OPS / Audit / Tavily




13. TESTES E ENTREGA DA POC                            ⏳


    - testes unitários
    - integração
    - segurança
    - RAG evaluation
    - Docker completo
    - documentação
    - validação final do Harness
