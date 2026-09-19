# CANCELAMENTO DE VENDA — PDD ROBOT 02 / R2

> **Tipo:** PDD — Process Definition Document
> **Área:** Backoffice / Cancelamento de Vendas
> **Componente:** Robot 02 / R2
> **Classificação:** Uso interno
> **Versão:** 1.0 — POC

## 1. OBJETIVO

Definir o processo automatizado executado pelo Robot 02 / R2, responsável por acompanhar solicitações de cancelamento previamente enviadas pelo Robot 01 / R1, consultar seus resultados na Retaguarda TI, baixar arquivos de retorno quando disponíveis, atualizar a base de controle e comunicar o resultado ao solicitante ou à área interna responsável.

O Robot 02 não recebe novas solicitações de cancelamento. Sua entrada é formada pelos registros pendentes produzidos pelo Robot 01.

## 2. ESCOPO

O R2 compreende:

* consultar a base de controle;
* identificar protocolos enviados pela automação e ainda pendentes;
* consultar a Retaguarda TI por requisição HTTP;
* localizar o processamento com base no protocolo e/ou nome do arquivo;
* identificar o status do lote;
* baixar o arquivo de retorno quando disponível;
* atualizar o banco;
* enviar resposta de sucesso ou rejeição ao solicitante;
* registrar falhas técnicas apenas para tratamento interno;
* controlar situações de atraso e expiração do SLA.

## 3. RELAÇÃO ENTRE R1 E R2

O Robot 01 é responsável pela entrada do processo:

`E-mail → validação → protocolo → preparação → upload → banco`

O Robot 02 é responsável pela saída:

`Banco → protocolos pendentes → consulta Retaguarda → resultado → download → banco → e-mail`

O protocolo e o nome do arquivo constituem as principais chaves de relacionamento entre os dois fluxos.

## 4. ENTRADA DO R2

O Robot 02 consulta a base de dados e seleciona registros que:

* tiveram upload realizado;
* ainda não possuem conclusão definitiva;
* ainda não tiveram o arquivo final baixado;
* permanecem elegíveis para consulta.

Dados mínimos esperados:

* ID do protocolo;
* nome do arquivo enviado;
* EC Matriz, quando aplicável;
* data/hora do upload;
* remetente da solicitação original;
* status atual;
* indicador de download;
* identificador da solicitação/e-mail original.

## 5. MACROPROCESSO

`Buscar pendências → consultar Retaguarda → analisar status → baixar retorno quando disponível → atualizar banco → enviar comunicação → finalizar ou manter pendente`

## 6. BUSCA DOS PROTOCOLOS PENDENTES

O R2 deve selecionar apenas registros ainda abertos.

Exemplos de estados elegíveis:

* `Sucesso upload`;
* `Em andamento`;
* `Atrasado`.

Registros já finalizados ou marcados como baixados não devem ser reprocessados normalmente.

## 7. CONSULTA À RETAGUARDA

Para cada registro pendente, o Robot 02 deve consultar a Retaguarda TI por request autenticado.

A consulta deve considerar, conforme contrato técnico disponível:

* protocolo;
* nome do arquivo;
* identificadores auxiliares necessários.

A resposta deve ser interpretada sem alterar silenciosamente dados recebidos do portal.

## 8. RESULTADOS POSSÍVEIS

### 8.1. Lote ainda não finalizado

Quando o portal indicar que o processamento ainda não terminou:

* não realizar download;
* manter o protocolo aberto;
* atualizar o status conforme tempo decorrido;
* registrar data/hora da consulta.

### 8.2. Lote finalizado com sucesso

Quando o portal informar conclusão com sucesso:

1. baixar a planilha/arquivo de comprovação;
2. salvar o arquivo de retorno;
3. atualizar o banco;
4. marcar o download como realizado;
5. responder ao solicitante por e-mail;
6. anexar a comprovação obtida na Retaguarda;
7. finalizar o protocolo como `Sucesso`.

### 8.3. Lote finalizado com rejeição de negócio

Quando o processamento for concluído, mas o cancelamento não puder ser realizado devido a regra de negócio:

1. registrar a rejeição;
2. armazenar código/motivo quando disponível;
3. atualizar o banco;
4. responder ao solicitante;
5. informar que o cancelamento não foi efetivado;
6. anexar retorno ou evidência aplicável;
7. finalizar o protocolo como `Rejeitado` ou status equivalente.

A mensagem ao solicitante não deve expor informação técnica interna desnecessária.

### 8.4. Protocolo ou arquivo não encontrado

Quando a Retaguarda não localizar o item consultado:

* registrar a ocorrência;
* não assumir que o cancelamento falhou;
* manter evidência da consulta;
* encaminhar o caso para análise interna;
* não enviar ao solicitante uma conclusão não comprovada.

### 8.5. Erro no download

Quando o portal indicar que o lote está finalizado, mas o arquivo não puder ser baixado:

* registrar `Erro download`;
* preservar o protocolo como não concluído operacionalmente;
* não enviar resposta final ao solicitante;
* comunicar internamente para tratamento;
* permitir nova tentativa conforme política técnica.

### 8.6. Falha de acesso à Retaguarda

Quando a consulta via request não puder ser realizada por indisponibilidade, autenticação, timeout, rede ou erro HTTP:

* registrar exceção de sistema;
* não modificar o resultado funcional do protocolo;
* não responder ao solicitante como sucesso ou rejeição;
* comunicar internamente;
* permitir nova consulta em execução futura.

## 9. REGRAS DE TEMPO

Enquanto o lote não estiver finalizado:

* até 12 horas após o upload: `Em andamento`;
* acima de 12 horas e abaixo de 96 horas: `Atrasado`;
* a partir de 96 horas sem conclusão: `Finalizado sem sucesso`.

Ao atingir 96 horas:

* registrar a situação;
* interromper o acompanhamento automático normal;
* encaminhar o caso para tratamento interno;
* comunicar o solicitante somente conforme regra de negócio aprovada.

## 10. DOWNLOAD DO RESULTADO

O download ocorre somente quando:

* o protocolo foi localizado;
* o processamento está finalizado;
* existe arquivo de retorno disponível;
* a sessão/autorização permite o download.

O arquivo deve ser associado ao protocolo e armazenado na área de retorno correspondente.

O indicador de download deve ser atualizado para impedir downloads duplicados.

## 11. COMUNICAÇÃO POR E-MAIL

O R2 deve reutilizar os dados do solicitante registrados pelo R1.

### 11.1. Sucesso

Enviar ao solicitante:

* protocolo;
* informação de conclusão;
* indicação de sucesso;
* planilha/arquivo de comprovação baixado da Retaguarda.

### 11.2. Rejeição de negócio

Enviar ao solicitante:

* protocolo;
* informação de que o cancelamento não foi efetivado;
* motivo funcional, quando permitido;
* arquivo de retorno, quando aplicável.

### 11.3. Erro técnico

Erros técnicos do R2 não devem gerar automaticamente uma resposta final ao solicitante.

Devem gerar comunicação interna para:

* operação;
* suporte;
* equipe responsável pela automação.

Exemplos:

* Retaguarda indisponível;
* timeout;
* falha de autenticação;
* erro de download;
* erro de banco;
* falha de rede.

## 12. ATUALIZAÇÃO DO BANCO

A cada consulta devem ser registrados, conforme aplicável:

* protocolo;
* nome do arquivo;
* timestamp da consulta;
* status anterior;
* status encontrado;
* descrição;
* resultado da consulta;
* indicador de download;
* horário do download;
* caminho lógico do retorno;
* resultado do envio de e-mail;
* código/motivo de rejeição;
* erro técnico, quando houver.

## 13. STATUS PRINCIPAIS

Possíveis estados do R2:

* `Em andamento`;
* `Atrasado`;
* `Sucesso`;
* `Rejeitado`;
* `Protocolo não encontrado`;
* `Erro download`;
* `Finalizado sem sucesso`;
* `Erro sistema`;
* `Erro outros`.

A nomenclatura final deverá permanecer alinhada ao modelo de dados da POC.

## 14. EXCEÇÕES DE NEGÓCIO

| Situação                 | Tratamento                           |
| ------------------------ | ------------------------------------ |
| Cancelamento rejeitado   | Registrar e responder ao solicitante |
| Lote não finalizado      | Manter aberto                        |
| Protocolo não localizado | Registrar e encaminhar para análise  |
| Protocolo acima de 96h   | Finalizar sem sucesso e escalar      |

## 15. EXCEÇÕES DE SISTEMA

| Situação                         | Tratamento                                   |
| -------------------------------- | -------------------------------------------- |
| Retaguarda indisponível          | Registrar e tentar novamente posteriormente  |
| Timeout HTTP                     | Registrar e manter protocolo elegível        |
| Falha de autenticação            | Registrar internamente sem expor credenciais |
| Erro de download                 | Registrar e não enviar retorno final         |
| Banco indisponível               | Interromper com segurança                    |
| Rede indisponível                | Registrar e manter rastreabilidade           |
| Falha no envio interno de alerta | Registrar para contingência                  |

## 16. SEGURANÇA

O Robot 02 deve:

* usar credenciais protegidas;
* não persistir tokens, cookies ou senhas;
* não registrar secrets em log;
* utilizar consultas parametrizadas;
* restringir acesso aos arquivos baixados;
* evitar envio de informações técnicas internas ao solicitante;
* preservar rastreabilidade das consultas.

## 17. PLANEJAMENTO DE EXECUÇÃO

O R2 pode ser executado em janelas periódicas independentes do R1.

A frequência deve ser suficiente para acompanhar protocolos ainda abertos sem gerar carga excessiva na Retaguarda.

Para a POC, o agendamento exato permanece configuração operacional.

## 18. CRITÉRIOS DE ACEITE

O R2 será considerado funcional quando:

* identificar somente protocolos elegíveis;
* não reprocessar protocolos já concluídos;
* consultar a Retaguarda;
* diferenciar pendente, sucesso, rejeição, não encontrado e erro técnico;
* aplicar as regras de 12h e 96h;
* baixar o arquivo final quando disponível;
* impedir download duplicado;
* atualizar a base;
* enviar sucesso/rejeição ao solicitante;
* direcionar erros técnicos somente para comunicação interna;
* preservar rastreabilidade;
* não expor credenciais ou secrets.

## 19. RELAÇÃO COM O AGENTE DA POC

O agente de suporte poderá consultar os registros gerados pelo R2 para responder perguntas como:

* qual o status do protocolo;
* se o lote já foi processado;
* se houve sucesso ou rejeição;
* qual erro ocorreu;
* quando ocorreu a última consulta;
* se o arquivo de retorno foi baixado;
* por que o caso permanece pendente;
* qual regra deveria ter sido aplicada.

O RAG representa o comportamento esperado.

A base operacional representa o que efetivamente ocorreu.
