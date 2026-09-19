# CANCELAMENTO DE VENDA — SDD ROBOT 02 / R2

| Campo                        | Valor                          |
| ---------------------------- | ------------------------------ |
| **Tipo**                     | SDD — Solution Design Document |
| **Processo**                 | Cancelamento de Vendas         |
| **Componente**               | Robot 02 / R2                  |
| **Plataforma de referência** | Automation Anywhere A360       |
| **Versão**                   | 1.0 — POC                      |
| **Classificação**            | Uso interno                    |

## 1. OBJETIVO

Descrever o desenho técnico do Robot 02 / R2 do processo de Cancelamento de Vendas.

O R2 é responsável por consultar solicitações previamente enviadas pelo Robot 01 / R1, verificar o processamento do lote na Retaguarda TI, baixar o arquivo de resultado quando disponível, atualizar a base operacional e realizar as comunicações correspondentes.

Este documento foi elaborado para a POC e representa o comportamento técnico esperado do R2.

## 2. ESCOPO

O Robot 02 implementa:

* leitura de protocolos pendentes no banco de dados;
* identificação de registros ainda elegíveis para acompanhamento;
* consulta à Retaguarda TI por requisição HTTP;
* pesquisa baseada principalmente em protocolo e nome do arquivo;
* interpretação do status do processamento;
* controle de tempo do protocolo;
* download do arquivo de retorno;
* persistência dos resultados;
* envio de e-mail de sucesso ou rejeição;
* geração de alertas internos em falhas técnicas;
* manutenção da rastreabilidade entre R1 e R2.

O R2 não recebe novas solicitações de cancelamento.

## 3. VISÃO DA ARQUITETURA

Fluxo lógico:

```text
Banco de Dados
      ↓
Carregador de Pendências
      ↓
Cliente HTTP Retaguarda
      ↓
Analisador de Resultado
      ↓
┌─────────────┬───────────────┬──────────────┐
│ Pendente    │ Sucesso       │ Rejeição     │
│             │               │              │
│ Atualiza DB │ Download      │ Atualiza DB  │
│             │ Atualiza DB   │ E-mail       │
└─────────────┴───────────────┴──────────────┘
                      │
                      ▼
              Comunicação / Logs
```

Componentes lógicos:

* Orquestrador R2;
* Repositório de Protocolos;
* Cliente HTTP da Retaguarda;
* Analisador de Status;
* Controlador de SLA;
* Serviço de Download;
* Persistência;
* Serviço de E-mail;
* Serviço de Logs;
* Tratamento de Exceções.

## 4. INICIALIZAÇÃO

Ao iniciar, o Robot 02 deve:

1. carregar configurações do ambiente;
2. iniciar o contexto da execução;
3. gerar um identificador da execução;
4. inicializar logs;
5. validar disponibilidade do banco;
6. carregar registros elegíveis para consulta;
7. iniciar o processamento individual dos protocolos.

Uma falha estrutural durante a inicialização deve interromper a execução de forma controlada.

## 5. CONSULTA DE REGISTROS PENDENTES

O Robot 02 consulta a base operacional produzida pelo Robot 01.

São elegíveis registros:

* cujo upload foi realizado;
* que ainda não possuem resultado final;
* cujo retorno ainda não foi baixado;
* que permanecem dentro do fluxo de acompanhamento.

Estados de exemplo:

* `SUCESSO UPLOAD`;
* `EM ANDAMENTO`;
* `ATRASADO`.

O Robot 02 não deve reprocessar normalmente registros já concluídos.

Exemplo lógico:

```text
status IN (
    "SUCESSO UPLOAD",
    "EM ANDAMENTO",
    "ATRASADO"
)
AND baixado = false
```

Consultas ao banco devem ser parametrizadas.

## 6. ESTRUTURA LÓGICA DO REGISTRO

Um registro acompanhado pelo R2 pode conter:

* `id_transacao`;
* `id_protocolo`;
* `nome_arquivo`;
* `ec_matriz`;
* `data_upload`;
* `status`;
* `descricao`;
* `baixado`;
* `remetente_email`;
* `hora_ultima_consulta`;
* `hora_download`;
* `caminho_retorno`;
* `resultado_email`.

Os nomes físicos de tabelas e campos não fazem parte deste documento.

## 7. CLIENTE HTTP DA RETAGUARDA

O acesso à Retaguarda TI deve ocorrer através de um componente isolado responsável pelas requisições HTTP.

O componente deve receber dados como:

* protocolo;
* nome do arquivo.

Dependendo do contrato técnico da Retaguarda, outros identificadores podem ser necessários.

As credenciais devem ser obtidas por mecanismo seguro.

O restante da aplicação não deve depender diretamente do formato original da resposta HTTP.

## 8. RESULTADO NORMALIZADO

A resposta da Retaguarda deve ser convertida para uma estrutura interna padronizada.

Exemplo lógico:

```text
ResultadoPortal

encontrado
finalizado
sucesso
arquivo_disponivel
mensagem
codigo_resultado
```

Essa normalização permite que a lógica de negócio permaneça independente do formato da API externa.

## 9. PROCESSAMENTO DO PROTOCOLO

Para cada protocolo pendente:

1. consultar a Retaguarda;
2. verificar se o protocolo/arquivo foi localizado;
3. verificar se o processamento foi finalizado;
4. classificar o resultado;
5. baixar o retorno quando aplicável;
6. atualizar a base;
7. realizar comunicação;
8. registrar o encerramento ou manter o caso pendente.

## 10. PROTOCOLO NÃO ENCONTRADO

Quando a Retaguarda não localizar protocolo ou arquivo correspondente:

* registrar a consulta;
* atualizar o status para `PROTOCOLO NÃO ENCONTRADO` ou equivalente;
* não concluir que houve rejeição;
* não concluir que houve sucesso;
* encaminhar para análise interna;
* preservar evidências da consulta.

Não deve ser enviada conclusão definitiva ao solicitante sem evidência suficiente.

## 11. PROCESSAMENTO AINDA NÃO FINALIZADO

Quando:

```text
encontrado = true
finalizado = false
```

o R2 deve manter o protocolo aberto.

O status depende do tempo transcorrido desde o upload.

### Até 12 horas

```text
EM ANDAMENTO
```

### Acima de 12 horas e abaixo de 96 horas

```text
ATRASADO
```

### A partir de 96 horas

```text
FINALIZADO SEM SUCESSO
```

Ao atingir o limite definido, o caso deve ser disponibilizado para tratamento interno.

## 12. PROCESSAMENTO FINALIZADO COM SUCESSO

Quando:

```text
encontrado = true
finalizado = true
sucesso = true
```

o Robot 02 deve verificar a disponibilidade do arquivo de resultado.

Se disponível:

1. solicitar download;
2. validar o retorno;
3. salvar a referência do arquivo;
4. atualizar `baixado = true`;
5. atualizar o status para `SUCESSO`;
6. registrar horário do download;
7. enviar e-mail ao solicitante;
8. anexar a planilha/arquivo de comprovação;
9. finalizar o acompanhamento.

## 13. REJEIÇÃO DE NEGÓCIO

O portal pode finalizar o lote sem efetivar o cancelamento devido a regra de negócio.

Nesse cenário:

```text
finalizado = true
sucesso = false
tipo = rejeicao_negocio
```

O R2 deve:

* registrar o resultado;
* salvar código e descrição quando disponíveis;
* atualizar o protocolo para `REJEITADO`;
* responder ao solicitante;
* informar que o cancelamento não foi efetivado;
* informar motivo funcional permitido;
* anexar resultado quando aplicável.

Informações técnicas internas não devem ser expostas ao solicitante.

## 14. ERRO DE DOWNLOAD

Pode ocorrer situação em que o lote esteja finalizado, mas o arquivo não seja baixado corretamente.

Exemplos:

* arquivo não disponível;
* timeout;
* resposta inválida;
* falha HTTP;
* erro na gravação do arquivo.

Nesse caso:

```text
status = ERRO DOWNLOAD
baixado = false
```

O R2 deve:

* registrar a falha;
* preservar o protocolo;
* não comunicar sucesso ao solicitante;
* gerar alerta interno;
* permitir nova tentativa futura.

## 15. FALHA NA CONSULTA DA RETAGUARDA

Falhas técnicas na consulta podem incluir:

* timeout;
* indisponibilidade do portal;
* falha de rede;
* erro HTTP;
* falha de autenticação;
* sessão inválida;
* resposta inesperada.

O tratamento deve:

* registrar exceção de sistema;
* preservar o estado funcional anterior;
* não inferir resultado;
* não informar sucesso ou rejeição ao solicitante;
* permitir nova tentativa;
* comunicar internamente quando necessário.

## 16. DOWNLOAD

O download deve ocorrer somente quando:

* o protocolo estiver localizado;
* o processamento estiver finalizado;
* o resultado permitir download;
* o arquivo estiver disponível;
* a sessão estiver autorizada;
* `baixado = false`.

Após sucesso:

```text
baixado = true
```

O processo deve impedir downloads duplicados em condições normais.

## 17. PERSISTÊNCIA

Toda alteração importante deve ser persistida.

Informações recomendadas:

* protocolo;
* arquivo;
* EC Matriz;
* timestamp;
* status;
* descrição;
* resultado da consulta;
* quantidade de tentativas;
* indicador de download;
* data/hora do download;
* referência do retorno;
* resultado do e-mail;
* código de rejeição;
* mensagem sanitizada de erro.

O histórico não deve ser sobrescrito de forma que elimine rastreabilidade.

## 18. STATUS

Estados principais previstos:

### Operacionais

* `EM ANDAMENTO`;
* `ATRASADO`;
* `SUCESSO`;
* `FINALIZADO SEM SUCESSO`.

### Negócio

* `REJEITADO`;
* `PROTOCOLO NÃO ENCONTRADO`.

### Técnicos

* `ERRO DOWNLOAD`;
* `ERRO SISTEMA`;
* `ERRO OUTROS`.

A implementação poderá utilizar nomenclatura padronizada no modelo físico do banco.

## 19. COMUNICAÇÃO POR E-MAIL

O Robot 02 utiliza o remetente armazenado pelo R1.

### Sucesso

Enviar:

* protocolo;
* confirmação do processamento;
* confirmação do cancelamento quando comprovada;
* arquivo/planilha de comprovação baixada da Retaguarda.

### Rejeição de negócio

Enviar:

* protocolo;
* informação de não efetivação;
* motivo funcional permitido;
* arquivo de resultado quando existente.

### Erro técnico

Não enviar conclusão funcional automática ao solicitante.

Gerar comunicação interna para operação/suporte.

## 20. RETRY

Falhas transitórias podem ser processadas novamente.

Exemplos:

* timeout;
* portal indisponível;
* falha temporária de rede;
* erro temporário de download.

O retry deve reutilizar o mesmo protocolo.

Um retry nunca deve criar uma nova solicitação de cancelamento.

Cada tentativa deve permanecer rastreável.

## 21. IDEMPOTÊNCIA

Antes de executar ações, o R2 deve verificar:

* status atual;
* indicador de download;
* existência de resultado previamente tratado.

O objetivo é impedir:

* download duplicado;
* envio duplicado de e-mail;
* processamento duplicado;
* conclusão duplicada.

## 22. LOGS

Formato lógico recomendado:

```text
Timestamp;
ExecutionId;
Protocol;
Task;
TipoLog;
Descricao
```

Tipos:

* `INFO`;
* `ATENÇÃO`;
* `ERRO`.

Os logs podem conter identificadores técnicos necessários à investigação, mas não devem armazenar:

* senha;
* token;
* cookie;
* segredo de aplicação;
* credencial do banco;
* credencial da Retaguarda.

## 23. EXCEÇÕES DE NEGÓCIO

Exemplos:

* lote ainda em processamento;
* protocolo não encontrado;
* cancelamento rejeitado;
* processamento acima de 96 horas;
* resultado funcional não reconhecido.

Essas situações não devem ser confundidas com falha técnica da automação.

## 24. EXCEÇÕES DE SISTEMA

Exemplos:

* banco indisponível;
* Retaguarda indisponível;
* timeout HTTP;
* falha de autenticação;
* falha de rede;
* falha no download;
* falha no envio de e-mail;
* falha de acesso ao arquivo.

A exceção deve ser registrada sem exposição de secrets.

## 25. SEGURANÇA

A implementação deve:

* obter credenciais por mecanismo seguro;
* não persistir senhas;
* não persistir cookies;
* não expor tokens;
* utilizar SQL parametrizado;
* aplicar timeout nas chamadas HTTP;
* validar certificados;
* controlar quantidade de retries;
* sanitizar logs;
* restringir acesso aos arquivos de retorno;
* não expor detalhes técnicos desnecessários ao solicitante.

## 26. CÓDIGO DE REFERÊNCIA DA POC

O comportamento técnico do R2 também é representado por um código Python de referência em:

```text
reference/
└── automation-anywhere/
    └── cancelamento-vendas/
        └── robot-02-r2/
            └── process_logic_r2.py
```

Esse arquivo existe para:

* demonstrar a lógica;
* apoiar documentação;
* servir de fonte técnica para análise;
* apoiar construção do corpus do RAG.

Ele não representa necessariamente código de produção.

## 27. RELAÇÃO COM O ROBOT 01

O R1 produz os dados que o R2 consome.

```text
ROBOT 01
E-mail
 ↓
Validação
 ↓
Protocolo
 ↓
Upload
 ↓
Banco
      ↓
      ↓
ROBOT 02
Pendências
 ↓
Consulta
 ↓
Resultado
 ↓
Download
 ↓
Banco
 ↓
E-mail
```

A rastreabilidade entre R1 e R2 deve ser preservada por protocolo e demais identificadores do processo.

## 28. RELAÇÃO COM O AGENTE GETNET-SUPPORT

O agente da POC não executa o R2 diretamente.

O agente consulta os dados produzidos pelo processo através de ferramentas controladas.

Exemplos:

```text
get_cancellation_protocol(protocol_id)

get_cancellation_execution(protocol_id)

get_execution_events(protocol_id)
```

O agente utiliza:

```text
Banco operacional
→ o que realmente ocorreu

PDD
→ o que deveria ocorrer funcionalmente

SDD / documentação técnica
→ como deveria funcionar tecnicamente
```

Essa separação permite comparar execução, regra e implementação.

## 29. PONTOS DE ATENÇÃO

* não confundir rejeição de negócio com erro técnico;
* não marcar sucesso sem comprovação;
* não responder ao solicitante com sucesso sem resultado do portal;
* não repetir download já concluído;
* não criar novo protocolo no retry;
* preservar histórico;
* manter relacionamento com R1;
* tratar retorno desconhecido como inconclusivo;
* permitir investigação posterior pelo agente;
* não inferir resultado quando a Retaguarda estiver indisponível.

## 30. CRITÉRIOS DE ACEITE

O R2 deve:

* consultar somente protocolos elegíveis;
* consultar a Retaguarda;
* reconhecer protocolo não encontrado;
* reconhecer protocolo pendente;
* aplicar as regras de 12 e 96 horas;
* reconhecer sucesso;
* reconhecer rejeição;
* baixar retorno;
* impedir download duplicado;
* persistir alterações;
* enviar e-mail de sucesso;
* enviar e-mail de rejeição;
* não enviar conclusão em erro técnico;
* gerar alerta interno;
* preservar rastreabilidade;
* proteger credenciais;
* gerar logs sanitizados.

## 31. FONTES DO DOCUMENTO

Este SDD foi elaborado a partir de:

* PDD Robot 02 / R2 da POC;
* regras R2 descritas no PDD original;
* desenho técnico do Robot 01;
* código Python de referência criado para o Robot 02;
* decisões funcionais definidas para a POC.

Quando existir contrato técnico definitivo da Retaguarda ou modelo físico definitivo do banco, este documento deverá ser revisado e versionado.
