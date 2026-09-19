# Cancelamento de Vendas — Robot 01 / R1 — Technical Overview

## 1. Identificação

* **Processo:** Cancelamento de Vendas
* **Componente:** Robot 01 / R1
* **Responsabilidade:** Entrada, validação, preparação e upload das solicitações de cancelamento
* **Plataforma original:** Automation Anywhere A360
* **Classificação:** Uso interno
* **Status deste documento:** Conhecimento técnico curado para POC e RAG

## 2. Objetivo

O Robot 01 é responsável por receber solicitações de cancelamento de vendas enviadas por e-mail, validar o remetente e os arquivos recebidos, gerar protocolo, preparar os dados por EC Matriz, realizar o upload para a Retaguarda TI e registrar o resultado de cada etapa na base de controle.

O Robot 01 não confirma a efetivação final do cancelamento. A consulta posterior do protocolo e do resultado do processamento pertence ao Robot 02 / R2.

## 3. Fluxo principal

```text
Receber e-mail
    ↓
Verificar duplicidade
    ↓
Gerar protocolo
    ↓
Validar remetente
    ↓
Validar anexos
    ↓
Validar template e conteúdo
    ↓
Separar registros por EC Matriz
    ↓
Gerar arquivos ajustados
    ↓
Realizar upload na Retaguarda TI
    ↓
Persistir resultado no banco
    ↓
Responder ao remetente
    ↓
Mover e-mail para pasta correspondente
    ↓
Gerar relatório operacional
```

## 4. Entrada do processo

A entrada principal é uma mensagem recebida na caixa corporativa do processo.

O e-mail pode conter um ou mais anexos.

Para cada mensagem são relevantes, no mínimo:

* identificador da mensagem;
* remetente;
* assunto;
* data/hora de recebimento;
* anexos;
* quantidade de anexos.

Somente arquivos `xlsx` são elegíveis para o processamento de cancelamento.

## 5. Controle de duplicidade

Antes do processamento, o Robot 01 verifica se a solicitação já foi tratada.

A implementação técnica original utiliza informações do e-mail para identificar duplicidade.

Quando a solicitação já foi processada:

* não deve ocorrer novo upload;
* o e-mail deve ser finalizado conforme regra do processo;
* a ocorrência deve permanecer rastreável.

## 6. Geração de protocolo

Cada nova solicitação válida recebe um protocolo.

O protocolo é utilizado para relacionar:

* e-mail recebido;
* arquivo original;
* arquivos ajustados;
* EC Matriz;
* upload;
* status;
* futura consulta pelo Robot 02.

O protocolo é uma das principais chaves de rastreabilidade entre R1 e R2.

## 7. Validação do remetente

O remetente é comparado com uma lista permissiva de endereços autorizados.

### Remetente autorizado

O processamento continua normalmente.

### Remetente não autorizado

O Robot 01 deve:

1. interromper o processamento dos anexos;
2. registrar exceção de negócio;
3. atualizar a base;
4. responder ao remetente;
5. finalizar o e-mail sem realizar upload.

## 8. Validação dos anexos

O processo espera planilhas `xlsx`.

O layout contém, entre outros:

* Nº EC Matriz;
* Nº EC onde ocorreu a compra;
* código da autorização;
* código da moeda;
* data da venda;
* valor da venda;
* valor do cancelamento;
* Nº do comprovante de venda;
* Nº do terminal.

São consideradas situações inválidas:

* ausência de anexo;
* extensão diferente de `xlsx`;
* cabeçalho ausente;
* cabeçalho divergente;
* cabeçalho duplicado;
* arquivo sem dados;
* campos obrigatórios inválidos;
* data inválida;
* data futura;
* arquivo corrompido;
* estrutura fora do template esperado.

## 9. Validações de conteúdo

O Robot 01 executa validações de formato e conteúdo.

Entre elas:

* ECs devem respeitar formato numérico;
* código de autorização deve respeitar o formato vigente;
* código da moeda deve corresponder à configuração esperada;
* data deve ser válida e não futura;
* valores devem possuir formato numérico válido;
* comprovante deve respeitar limite e formato estabelecidos;
* terminal deve respeitar o formato configurado.

As regras documentais e a implementação técnica podem apresentar divergências pontuais. Essas divergências devem ser preservadas como evidência e não corrigidas silenciosamente pelo agente.

## 10. Tratamento de arquivo inválido

Quando o arquivo não passa nas validações:

* nenhum upload deve ser realizado;
* o erro deve ser registrado;
* deve ser produzido relatório com os problemas encontrados;
* o solicitante deve receber retorno com orientação;
* o caso deve permanecer registrado na base de controle.

## 11. Separação por EC Matriz

Após a validação, os registros são agrupados pelo campo `Nº EC Matriz`.

Para cada EC Matriz identificado:

1. são selecionadas as linhas correspondentes;
2. é criado um arquivo ajustado;
3. o arquivo recebe identificação relacionada ao protocolo;
4. o arquivo fica disponível para upload.

Uma única solicitação pode, portanto, gerar múltiplos arquivos de saída.

## 12. Upload para Retaguarda TI

Os arquivos válidos são enviados para a Retaguarda TI.

O fluxo técnico envolve:

1. autenticação utilizando credencial protegida;
2. obtenção de contexto de sessão;
3. envio do arquivo por requisição HTTP;
4. avaliação do resultado;
5. persistência do resultado na base.

Possíveis resultados incluem:

* `Sucesso upload`;
* `Insucesso upload`.

Credenciais, tokens e cookies não devem ser persistidos em logs ou na base operacional.

## 13. Persistência operacional

O Robot 01 registra informações necessárias para permitir rastreabilidade e posterior processamento pelo Robot 02.

Entre os dados relevantes:

* identificador da execução;
* identificador da mensagem;
* protocolo;
* remetente;
* assunto;
* nome do anexo;
* EC Matriz;
* data/hora;
* status;
* descrição;
* resultado da validação;
* resultado do upload;
* referência ao arquivo.

O registro do protocolo após o upload é essencial porque o Robot 02 utilizará esses dados para consultar posteriormente o resultado na Retaguarda TI.

## 14. Status relevantes do R1

Principais estados relacionados ao Robot 01:

* Exceção de negócio;
* Arquivo Validado;
* Sucesso upload;
* Insucesso upload;
* Remetente não habilitado;
* Arquivo/template inválido;
* E-mail já processado;
* Falha de sistema.

A nomenclatura exata pode variar entre documentação funcional, implementação e representação da POC.

## 15. Pastas e organização lógica

O processo original utiliza áreas lógicas semelhantes a:

```text
Recebidos
Ajustados
Retornos
Analise_RPA
Arquivamento_Outlook
```

Para o R1, as áreas mais relevantes são:

* `Recebidos`: arquivos originais;
* `Ajustados`: arquivos validados e preparados;
* `Analise_RPA`: relatórios e evidências de erro.

`Retornos` está principalmente associado ao processamento posterior do R2.

## 16. Resposta ao solicitante

Após o processamento, o Robot 01 envia retorno ao solicitante.

Dependendo do resultado, a resposta pode informar:

* protocolo criado;
* sucesso no tratamento;
* arquivo inválido;
* remetente não habilitado;
* falha de processamento;
* resultado parcial quando há múltiplos anexos.

## 17. Tratamento de exceções

### Exceções de negócio

Exemplos:

* solicitação duplicada;
* remetente não habilitado;
* ausência de anexo;
* extensão inválida;
* cabeçalho incorreto;
* dados inválidos;
* falha de upload.

### Exceções de sistema

Exemplos:

* falha no Microsoft 365;
* indisponibilidade de rede;
* falha de banco;
* falha de autenticação;
* falha da API;
* erro de leitura/escrita de arquivo;
* indisponibilidade da Retaguarda TI.

As exceções devem ser registradas sem exposição de credenciais ou outros segredos.

## 18. Segurança

O Robot 01 deve respeitar as seguintes regras:

* credenciais não ficam no código;
* tokens e cookies não são persistidos;
* secrets devem vir de mecanismo seguro;
* consultas ao banco devem ser parametrizadas;
* logs não devem conter credenciais;
* informações sensíveis devem ter acesso restrito;
* falhas não devem expor configuração interna desnecessária.

## 19. Relação com o Robot 02 / R2

O Robot 01 termina após o envio da solicitação para a Retaguarda TI e o registro do estado correspondente.

O Robot 02 utilizará posteriormente informações persistidas pelo Robot 01, principalmente:

* protocolo;
* nome do arquivo;
* data/hora do upload;
* status;
* indicador de retorno/download;
* dados necessários para relacionar o resultado à solicitação original.

A responsabilidade do Robot 02 é consultar os casos ainda abertos e determinar o resultado final do processamento.

## 20. Limites do Robot 01

O Robot 01 não deve ser considerado responsável por:

* confirmar o cancelamento final da venda;
* consultar periodicamente o status final do protocolo;
* baixar o arquivo de retorno final;
* classificar SLA de protocolo pendente;
* concluir casos não processados pela Retaguarda.

Essas responsabilidades pertencem ao Robot 02 / R2.

## 21. Fontes deste conhecimento

Este overview foi derivado das seguintes fontes da POC:

* PDD genérico de Cancelamento de Vendas;
* SDD genérico da automação R1;
* representação Python não executável da lógica do Robot 01.

Quando houver divergência entre essas fontes:

1. o PDD representa a regra funcional esperada;
2. o SDD representa o desenho/implementação técnica observada;
3. o código lógico da POC representa uma aproximação técnica para entendimento;
4. divergências devem permanecer identificáveis para análise pelo agente.

## 22. Uso no RAG

Este documento é uma fonte técnica curada.

Metadados recomendados para ingestão:

```yaml
document_id: cancellation-robot-01-r1-technical-overview
document_type: technical_overview
process: sales_cancellation
robot: robot-01
stage: r1
knowledge_type: technical
status: active
language: pt-BR
authority_level: technical
```

A fonte autoritativa para regras de negócio continua sendo o PDD aprovado.

Este documento deve ser utilizado principalmente para:

* explicar o funcionamento técnico do Robot 01;
* relacionar etapas técnicas com registros operacionais;
* identificar onde uma falha pode ter ocorrido;
* comparar comportamento esperado e observado;
* fornecer contexto ao agente durante investigação de protocolos.
