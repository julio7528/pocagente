# Cancelamento de Vendas — Robot 02 / R2 — Technical Overview

## 1. Identificação

* **Processo:** Cancelamento de Vendas
* **Componente:** Robot 02 / R2
* **Responsabilidade:** Consulta, acompanhamento, download e retorno dos lotes enviados pelo Robot 01
* **Plataforma de referência:** Automation Anywhere A360
* **Classificação:** Uso interno
* **Status deste documento:** Conhecimento técnico curado para POC e RAG

## 2. Objetivo

O Robot 02 é responsável por acompanhar solicitações de cancelamento que já foram validadas e enviadas à Retaguarda pelo Robot 01.

O R2 consulta a base operacional, identifica protocolos ainda pendentes, consulta a Retaguarda por requisição HTTP, interpreta o resultado, baixa o arquivo de retorno quando disponível, atualiza a base e realiza as comunicações correspondentes.

O Robot 02 não recebe novas solicitações de cancelamento.

## 3. Relação com o Robot 01

O Robot 01 executa a entrada do processo:

```text
E-mail
→ validação
→ protocolo
→ preparação
→ upload
→ registro no banco
```

O Robot 02 executa a saída:

```text
Banco
→ protocolos pendentes
→ consulta Retaguarda
→ resultado
→ download
→ atualização do banco
→ e-mail
```

O protocolo e o nome do arquivo são os principais identificadores usados para relacionar R1 e R2.

## 4. Fluxo principal

```text
Consultar banco
    ↓
Buscar protocolos pendentes
    ↓
Consultar Retaguarda por request
    ↓
Protocolo encontrado?
    ├─ não → registrar e encaminhar para análise
    └─ sim
         ↓
Processamento finalizado?
    ├─ não → atualizar Em andamento / Atrasado
    └─ sim
         ↓
Resultado com sucesso?
    ├─ não → registrar rejeição ou falha
    └─ sim
         ↓
Arquivo disponível?
    ├─ não → registrar erro de download
    └─ sim
         ↓
Baixar retorno
    ↓
Atualizar banco
    ↓
Enviar e-mail
```

## 5. Fonte de entrada

A entrada do R2 é a base operacional preenchida pelo R1.

São relevantes, no mínimo:

* protocolo;
* nome do arquivo;
* EC Matriz, quando aplicável;
* data/hora do upload;
* status atual;
* indicador de download;
* remetente da solicitação original;
* identificador da transação ou execução;
* descrição do último resultado.

## 6. Seleção de pendências

O R2 deve consultar apenas registros ainda elegíveis.

Exemplos:

* `Sucesso upload`;
* `Em andamento`;
* `Atrasado`.

Registros já finalizados ou com retorno já baixado não devem entrar no processamento normal.

Regra lógica simplificada:

```text
status elegível
AND
baixado = false
```

## 7. Consulta à Retaguarda

Para cada protocolo pendente, o R2 consulta a Retaguarda utilizando requisição HTTP autenticada.

A consulta é baseada principalmente em:

* protocolo;
* nome do arquivo.

A integração deve ser isolada em um cliente técnico para que o restante do processo não dependa diretamente do formato original da Retaguarda.

## 8. Resultado normalizado

A resposta da Retaguarda deve ser convertida para uma estrutura comum.

Exemplo conceitual:

```text
encontrado
finalizado
sucesso
arquivo_disponivel
mensagem
codigo_resultado
```

Isso permite tratar os diferentes cenários sem acoplar a lógica do processo à resposta HTTP original.

## 9. Cenário: protocolo não encontrado

Quando o protocolo ou arquivo não for localizado:

* registrar a ocorrência;
* não assumir sucesso;
* não assumir rejeição;
* preservar a evidência da consulta;
* encaminhar para análise interna;
* não enviar uma conclusão definitiva ao solicitante sem evidência.

## 10. Cenário: processamento ainda pendente

Quando o protocolo for encontrado, mas ainda não estiver finalizado, o R2 mantém o caso aberto.

O status depende do tempo transcorrido desde o upload.

### Até 12 horas

```text
Em andamento
```

### Acima de 12 horas e abaixo de 96 horas

```text
Atrasado
```

### A partir de 96 horas

```text
Finalizado sem sucesso
```

Casos acima do limite devem ser disponibilizados para tratamento interno.

## 11. Cenário: sucesso

Quando a Retaguarda indicar conclusão com sucesso:

1. validar a disponibilidade do arquivo de retorno;
2. realizar o download;
3. armazenar a referência do arquivo;
4. marcar o retorno como baixado;
5. atualizar o banco para `Sucesso`;
6. registrar data/hora;
7. responder ao solicitante;
8. anexar a planilha ou arquivo de comprovação.

O sucesso só deve ser considerado completo quando houver evidência suficiente do resultado.

## 12. Cenário: rejeição de negócio

O lote pode ser finalizado sem que o cancelamento seja efetivado.

Nesse caso:

* registrar a rejeição;
* armazenar código e motivo quando disponíveis;
* atualizar o status;
* responder ao solicitante;
* informar que o cancelamento não foi efetivado;
* anexar o retorno quando aplicável.

A mensagem externa não deve expor detalhes técnicos internos desnecessários.

## 13. Cenário: erro no download

Pode ocorrer de o lote estar finalizado, mas o arquivo não ser baixado.

Nesse caso:

* registrar `Erro download`;
* manter `baixado = false`;
* não comunicar sucesso ao solicitante;
* gerar alerta interno;
* preservar o protocolo;
* permitir nova tentativa.

## 14. Cenário: falha de acesso à Retaguarda

Possíveis falhas:

* timeout;
* portal indisponível;
* falha de autenticação;
* erro HTTP;
* indisponibilidade de rede;
* sessão inválida;
* resposta inesperada.

O R2 deve:

* registrar erro técnico;
* preservar o estado funcional anterior;
* não inferir resultado;
* não informar sucesso ou rejeição ao solicitante;
* permitir nova consulta posterior;
* comunicar internamente quando necessário.

## 15. Download

O download deve ocorrer somente quando:

* o protocolo foi encontrado;
* o processamento está finalizado;
* o resultado é elegível;
* existe arquivo disponível;
* o retorno ainda não foi baixado.

Após sucesso:

```text
baixado = true
status = Sucesso
```

Downloads duplicados devem ser evitados.

## 16. Atualização do banco

O R2 deve registrar, conforme aplicável:

* protocolo;
* arquivo;
* timestamp da consulta;
* status anterior;
* novo status;
* descrição;
* resultado retornado pelo portal;
* indicador de download;
* data/hora do download;
* referência do arquivo baixado;
* resultado do e-mail;
* código de rejeição;
* erro técnico sanitizado.

O histórico deve permitir reconstruir o comportamento do processo.

## 17. Status principais

### Operacionais

* Em andamento;
* Atrasado;
* Sucesso;
* Finalizado sem sucesso.

### Negócio

* Rejeitado;
* Protocolo não encontrado.

### Técnicos

* Erro download;
* Erro sistema;
* Erro outros.

A nomenclatura física poderá ser normalizada na implementação da POC.

## 18. Comunicação por e-mail

O R2 reutiliza o remetente registrado pelo R1.

### Sucesso

Enviar:

* protocolo;
* confirmação de conclusão;
* informação de sucesso;
* arquivo ou planilha de comprovação.

### Rejeição

Enviar:

* protocolo;
* informação de que o cancelamento não foi efetivado;
* motivo funcional permitido;
* evidência ou arquivo aplicável.

### Erro técnico

Não enviar automaticamente uma conclusão ao solicitante.

Gerar comunicação interna para tratamento.

## 19. Retry

Falhas transitórias podem ser tratadas em uma execução futura.

Exemplos:

* timeout;
* indisponibilidade temporária da Retaguarda;
* falha de rede;
* erro temporário de download.

O retry deve:

* reutilizar o mesmo protocolo;
* preservar o histórico;
* não criar nova solicitação;
* não duplicar e-mail ou download.

## 20. Idempotência

O R2 deve verificar antes de executar ações:

* status atual;
* indicador de download;
* resultado já persistido;
* envio anterior de comunicação.

O objetivo é evitar:

* download duplicado;
* e-mail duplicado;
* processamento duplicado;
* alteração repetida do mesmo resultado.

## 21. Logs e evidências

Os logs devem permitir rastrear:

* execução;
* protocolo;
* etapa;
* resultado;
* erro.

Estrutura conceitual:

```text
Timestamp
ExecutionId
Protocol
Task
LogType
Description
```

Tipos:

* INFO;
* WARNING;
* ERROR.

Secrets nunca devem aparecer nos logs.

## 22. Segurança

O R2 deve:

* obter credenciais de mecanismo seguro;
* não persistir senhas;
* não persistir cookies;
* não expor tokens;
* utilizar SQL parametrizado;
* aplicar timeout em requisições;
* validar certificados;
* limitar retries;
* sanitizar logs;
* restringir acesso aos arquivos baixados;
* não expor detalhes técnicos internos ao solicitante.

## 23. Relação com o agente da POC

O agente não executa diretamente o R2.

O agente consulta informações produzidas pelo R2 através de tools controladas.

Exemplos:

```text
get_cancellation_protocol()

get_cancellation_execution()

get_execution_events()
```

Essa separação é essencial:

```text
Robot 02
→ executa o acompanhamento

Banco operacional
→ registra o que aconteceu

Agente
→ consulta, interpreta e explica
```

## 24. Uso conjunto com PDD e SDD

Durante uma investigação, o agente pode combinar:

```text
PDD
→ regra funcional esperada

SDD
→ comportamento técnico esperado

Banco operacional
→ comportamento realmente observado
```

Exemplo:

```text
PDD:
Após 96h deve finalizar sem sucesso.

Banco:
O protocolo permaneceu Em andamento por 110h.

Conclusão:
Há divergência entre a regra esperada e a execução observada.
```

O agente não deve corrigir essa divergência silenciosamente.

## 25. Limites do Robot 02

O R2 não é responsável por:

* receber nova solicitação;
* validar o template original;
* validar remetente inicial;
* criar arquivos de upload;
* criar novo protocolo;
* reenviar lote sem regra explícita;
* alterar regra funcional;
* concluir sucesso sem evidência da Retaguarda.

Essas responsabilidades pertencem ao R1 ou a processos externos.

## 26. Código de referência

A lógica técnica de referência da POC está representada em:

```text
reference/
└── automation-anywhere/
    └── cancelamento-vendas/
        └── robot-02-r2/
            └── process_logic_r2.py
```

Esse arquivo não faz parte do runtime do `getnet-support`.

Ele serve para:

* compreensão técnica;
* documentação;
* construção do RAG;
* elaboração de testes;
* investigação pelo agente.

## 27. Fontes deste conhecimento

Este overview foi derivado de:

* PDD Robot 02 / R2;
* SDD Robot 02 / R2;
* regras do R2 descritas no PDD original;
* código Python de referência do Robot 02;
* decisões funcionais da POC.

Quando houver conflito:

1. o PDD representa a regra funcional esperada;
2. o SDD representa o desenho técnico esperado;
3. o código Python representa uma referência lógica da POC;
4. o banco operacional representa a execução observada.

## 28. Uso no RAG

Este arquivo é uma fonte técnica curada.

Metadados recomendados:

```yaml
document_id: cancellation-robot-02-r2-technical-overview
document_type: technical_overview
process: sales_cancellation
robot: robot-02
stage: r2
knowledge_type: technical
status: active
language: pt-BR
authority_level: technical
```

Este documento deve ajudar o agente a:

* explicar o funcionamento do R2;
* identificar em qual etapa ocorreu uma falha;
* diferenciar erro técnico de rejeição de negócio;
* entender status e SLA;
* interpretar registros operacionais;
* comparar execução real com comportamento esperado;
* identificar divergências entre regra, desenho e execução.
