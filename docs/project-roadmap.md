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

   ✅ Política de segurança interna
      └─ knowledge/internal/security/security-policy.md

   ✅ Dataset de avaliação
      └─ evaluation/rag/dataset-v1.yaml
         ├─ 25 casos
         ├─ rag-019 segurança/credencial
         ├─ rag-025 acesso sensível
         └─ thresholds globais

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


4.1 ARQUITETURA DOS SCHEMAS                         ← EM ANDAMENTO

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


   4.1.2 DEFINIR RESPONSABILIDADE DO SCHEMA OPS       ← AGORA

      Finalidade:
      representar o comportamento operacional observado do RPA.

      Deve contemplar conceitualmente:
      - cadastro da automação
      - execuções
      - processamentos
      - logs
      - alertas
      - e-mails
      - anexos
      - ECs
      - protocolos
      - upload/download
      - status do processo

      Referência:
      modelo Oracle reconstruído do processo de cancelamento.


   4.1.3 DEFINIR RESPONSABILIDADE DO SCHEMA AUDIT     ⏳

      Finalidade:
      registrar eventos de segurança e governança do agente.

      Deve contemplar conceitualmente:
      - solicitações de credenciais
      - solicitações de secrets
      - tentativa de acesso ao banco
      - acesso a infraestrutura protegida
      - prompt injection
      - tentativa de bypass
      - ação tomada
      - conteúdo sanitizado
      - revisão/auditoria


   4.1.4 DEFINIR LIMITES E FLUXO ENTRE OS SCHEMAS     ⏳

      Definir claramente:

      rag
      → responde "o que deveria acontecer?"

      ops
      → responde "o que realmente aconteceu?"

      audit
      → responde "houve algum evento de segurança ou governança?"

      Regras:
      - não misturar conhecimento RAG com dados operacionais
      - não armazenar logs de segurança dentro do RAG
      - não transformar respostas geradas pelo agente em conhecimento
      - manter responsabilidades e ciclos de vida separados


   4.1.5 APROVAR ARQUITETURA CONCEITUAL DOS SCHEMAS   ⏳

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


   4.2 ARQUITETURA DO SCHEMA RAG                       ⏳

      Proposta atual:

      rag.sources
      rag.documents
      rag.chunks
      rag.ingestion_runs

      Aqui ainda vamos:
      - aprovar cada tabela
      - definir responsabilidades
      - definir relacionamentos

      Estado atual:
      - nenhuma tabela física rag, ops ou audit foi criada


   4.3 ARQUITETURA DO SCHEMA OPS                       ⏳

      Usar como referência o Oracle reconstruído:

      TBA_RPA
      TBS_RPA_EXECUCAO
      TBS_RPA_LOG
      TBS_RPA_ALERTA
      TBS_PROCESSAMENTO
      TBF_6_EMAIL
      TBA_6_ANEXO
      TBA_6_EC
      SERVCLI_PREP_RPA_CANC_VENDA
      TBL_6_VALIDA_EXCEL_TEMP

      Depois adaptar apenas o necessário para PostgreSQL/POC.


   4.4 ARQUITETURA DO SCHEMA AUDIT                     ⏳

      Primeira tabela prevista:

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


   4.5 MODELO FÍSICO DO BANCO                          ⏳

      Definir:
      - campos
      - tipos
      - PK
      - FK
      - UNIQUE
      - NOT NULL
      - CHECK
      - indexes
      - JSONB
      - TSVECTOR
      - VECTOR(N)

      ⚠️ Antes de VECTOR(N):
         definir definitivamente o modelo FastEmbed
         para sabermos a dimensão do vetor.


   4.6 CRIAR TABELAS / DDL / MIGRATIONS                ⏳

      Criar fisicamente:
      - schema rag
      - schema ops
      - schema audit
      - tabelas
      - índices
      - constraints


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

   escolher modelo definitivo
   ↓
   definir dimensão
   ↓
   gerar embeddings
   ↓
   persistir em rag.chunks


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


9. KNOWLEDGE AGENT + TOOLS + TAVILY                    ⏳

   Knowledge Agent
   ├─ RAG
   ├─ operational tools
   ├─ security guardrails
   └─ Tavily controlado


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

    executar dataset-v1.yaml
    ↓
    25 casos
    ↓
    medir:
    - Top-5 source rate
    - provenance
    - unsupported facts
    - insufficient evidence
    - security blocking
    - audit logging
    - redaction


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
