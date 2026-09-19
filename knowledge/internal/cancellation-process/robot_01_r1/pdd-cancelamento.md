# CANCELAMENTO DE VENDA — PDD GENÉRICO

> **Tipo:** PDD (Process Definition Document)
> **Área:** Backoffice
> **Versão:** 11
> **Classificação:** Uso interno

---

## Cabeçalho do documento

| Campo                | Valor                  |
| -------------------- | ---------------------- |
| Processo             | Cancelamento de Vendas |
| Data de elaboração   | 21/02/2024             |
| Área responsável     | Backoffice             |
| Responsável fictício | Mariana Oliveira       |
| Versão               | 11                     |

## Sumário

1. Objetivo
2. Termos e definições
3. Diretrizes

   * Macroprocesso
   * Entrada: leitura, validação e upload
   * Saída: consulta, download e retorno
   * Relatórios, exceções e preparação
4. Anexos
5. Referências
6. Histórico de revisões

---

# CANCELAMENTO DE VENDA

## 1. OBJETIVO

Definir o processo automatizado de cancelamento de vendas, desde o recebimento da solicitação por e-mail até o retorno ao estabelecimento comercial (EC), garantindo validação, rastreabilidade e atualização dos status.

## 2. TERMOS E DEFINIÇÕES

* **RPA:** automação de atividades repetitivas baseadas em regras.
* **EC:** estabelecimento comercial solicitante.
* **Retaguarda TI:** portal usado para enviar solicitações e obter resultados.
* **Lista permissiva:** relação de remetentes autorizados.
* **R1:** etapa de entrada, validação e upload.
* **R2:** etapa de consulta, download e retorno.
* **D+1:** dia seguinte ao processamento.
* **SLA:** prazo acordado para conclusão.

Datas e pastas devem usar os padrões `DD/MM/AAAA` e `AAAAMMDD`, conforme o contexto.

## 3. DIRETRIZES

### 3.1. Descrição do processo

O EC envia a solicitação por e-mail. O RPA valida remetente e anexo, gera um protocolo, prepara os arquivos e realiza o upload na Retaguarda TI. Depois, consulta o resultado, baixa o retorno, responde ao EC e atualiza a base de controle.

### 3.2. Macroprocesso

`Receber e-mail → validar remetente → gerar protocolo → validar anexo → preparar arquivo → fazer upload → consultar status → baixar retorno → responder ao EC → atualizar base`

**Decisões principais:**

* **Remetente não autorizado:** responder com erro e encerrar o caso.
* **Arquivo fora do template:** gerar relatório de erros, responder ao EC e não fazer upload.
* **Arquivo válido:** preparar por EC Matriz e fazer upload.
* **Protocolo não finalizado:** manter em andamento, atraso ou finalizado sem sucesso.
* **Protocolo finalizado:** baixar o resultado e responder ao EC.

#### 3.2.1. Descrição das etapas do macroprocesso

1. Ler a caixa de entrada e salvar os anexos.
2. Validar remetente, formato e conteúdo.
3. Gerar protocolo e arquivos ajustados.
4. Fazer upload dos arquivos válidos.
5. Consultar os protocolos pendentes.
6. Baixar e enviar o resultado ao EC.
7. Registrar todas as etapas na base.

### 3.3. PROCESSO RPA – Processo de Upload - Entrada

A entrada compreende criação dos diretórios, leitura dos e-mails, validação do remetente e dos anexos, geração de protocolo, upload e atualização da base.

### 3.4. DETALHAMENTO DO PROCESSO RPA – Processo de Upload - Entrada

#### 3.4.1. Criar pasta do dia

Criar a pasta `AAAAMMDD` em `\\servidor-exemplo\automacao\cancelamento-vendas\Arquivos`, com as subpastas:

* `Recebidos`
* `Ajustados`
* `Retornos`
* `Analise_RPA`

#### 3.4.2. Preencher banco de dados — informações a cada etapa

Registrar cada mudança de status na base localizada em `\\servidor-exemplo\automacao\cancelamento-vendas\Bases`.

A estrutura mínima está definida no item 3.7.

#### 3.4.3. Ler E-mail

1. Ler a caixa fictícia `cancelamento.vendas@empresa-exemplo.invalid`.
2. Processar os e-mails pendentes.
3. Salvar os anexos originais em `Recebidos`.
4. Manter os e-mails concluídos na pasta `Tratados`.

##### 3.4.3.1. Arquivar e-mails tratados (lidos) (AÇÃO EM FREEZING)

A rotina permanece em freezing até aprovação técnica.

Quando habilitada, deve arquivar mensagens tratadas até D-7, usando a nomenclatura `deAAAAMMDD_ateAAAAMMDD`.

Se a caixa estiver cheia, notificar a área responsável.

##### 3.4.3.2. Lógica para criação do protocolo por e-mail

Gerar protocolo único com data, chave aleatória de dez dígitos e sequência do anexo:

`OK_SC-AAAAMMDD#########hashtag#_N_ARQUIVO_ret_EC-MATRIZ`

Exemplo fictício:

`OK_SC-203001159876543210_1_CANCELAMENTO-VENDA_ret_7654321.xlsx`.

Se houver vários anexos ou números de EC Matriz, manter o protocolo principal e diferenciar sequência e sufixo.

##### 3.4.3.3. Verificar se o remetente está habilitado

Consultar `Lista_Permissiva_Cancelamento.xlsx`, cuja primeira planilha, coluna A, contém os e-mails autorizados.

###### 3.4.3.3.1. Se estiver na lista

Prosseguir para a classificação do anexo.

###### 3.4.3.3.2. Se não estiver na lista

1. Não processar o anexo.
2. Registrar `Exceção de negócio — Remetente não habilitado`.
3. Responder com o template específico e orientar o cadastro pelo endereço fictício `cadastro.cancelamento@empresa-exemplo.invalid`.
4. Mover a mensagem para `Tratados`.

#### 3.4.4. Classificar e-mail

O anexo deve estar em formato `xlsx` e conter somente uma aba preenchida com o layout esperado.

| Campo obrigatório     | Validação principal                   |
| --------------------- | ------------------------------------- |
| Nº EC Matriz          | Somente dígitos                       |
| Nº EC da compra       | Somente dígitos                       |
| Código da autorização | Somente dígitos                       |
| Código da moeda       | Valor previsto pela regra vigente     |
| Data da venda         | Data válida, não futura e normalizada |
| Valor da venda        | Número positivo                       |
| Valor do cancelamento | Número positivo                       |
| Nº do comprovante     | Somente dígitos                       |
| Nº do terminal        | Formato previsto pela regra vigente   |

Campos vazios, cabeçalhos incorretos, abas duplicadas, arquivo corrompido ou extensão diferente de `xlsx` tornam o arquivo inválido.

##### 3.4.4.1. SE E-mail Dentro template

Preparar o arquivo, responder ao EC, armazenar e realizar o upload.

###### 3.4.4.1.1. Criação de novo Excel com as informações e criação de protocolo

* Normalizar os dados válidos.
* Separar os registros por EC Matriz.
* Criar um arquivo `xlsx` por EC Matriz.
* Renomear conforme o protocolo e registrar `Arquivo Validado`.

###### 3.4.4.1.2. Informar via e-mail o protocolo do arquivo criado

Responder ao EC com o protocolo, por exemplo `SC-203001159876543210`, e anexar todos os arquivos ajustados gerados para a solicitação.

###### 3.4.4.1.3. Armazenar na pasta arquivo ajustado

Salvar em `Arquivos\AAAAMMDD\Ajustados`.

###### 3.4.4.1.4. Realizar o Upload dos arquivos portal Retaguarda TI

Selecionar na base os registros com `Arquivo Validado` e localizar em `Ajustados` os arquivos com prefixo `OK`.

Protocolos marcados como erro não devem ser reenviados automaticamente.

###### 3.4.4.1.5. Upload Retaguarda TI

1. Acessar o portal pelo endereço configurado fora deste documento.
2. Autenticar com `[USUARIO_AUTOMACAO]` e credencial do cofre corporativo.
3. Enviar os arquivos elegíveis.
4. Registrar `Sucesso upload` ou `Insucesso upload`, com data, protocolo e descrição.

##### 3.4.4.2. SE Fora do template E-mail

Não realizar upload. Gerar relatório de erros e responder ao EC.

###### 3.4.4.2.1. Classificar anexo SE e-mail fora do template

O relatório deve informar:

* nome do arquivo;
* linha, aba, cabeçalho ou campo afetado;
* erro identificado;
* recomendação de correção;
* diferenças entre o cabeçalho esperado e o recebido.

###### 3.4.4.2.2. Gravar Excel de Relatório de erros no diretório

Salvar o relatório em `Arquivos\AAAAMMDD\Analise_RPA`.

###### 3.4.4.2.3. E-mail template erro

Responder com o protocolo e anexar:

* relatório de erros;
* template padrão de cancelamento;
* instruções de correção, quando aplicável.

Registrar a exceção de negócio na base.

#### 3.4.4.3. Atualizar Banco de dados

Registrar protocolo, remetente, anexo, datas, caminhos, status da validação, resultado do upload e descrição de eventual erro.

### 3.5. PROCESSO RPA TO BE – Processo de Output – Saída

A saída consulta protocolos pendentes, verifica o status na Retaguarda TI, baixa arquivos finalizados, responde ao EC e atualiza a etapa R2.

### 3.6. Processo de Output

#### 3.6.1. Buscar Protocolos que ainda não possuem Status retorno

Selecionar na base os protocolos enviados e ainda sem conclusão.

**Regras de tempo:**

* até 12 horas: `Em andamento`;
* acima de 12 e abaixo de 96 horas: `Atrasado`;
* a partir de 96 horas: `Finalizado sem sucesso` e encaminhamento à área de negócio.

##### 3.6.1.1. Etapas de busca e análise – SE Arquivo Diferente de Finalizado

* `Arquivo Gerado` ou `Aguardando Validação`: manter em andamento ou atraso.
* `Arquivo com Erro` ou `Arquivo Rejeitado`: registrar e preparar retorno de insucesso.
* Sem conclusão após 96 horas: finalizar sem sucesso e notificar a área.

##### 3.6.1.2. Etapas de busca e análise – SE Arquivo Finalizado

1. Baixar o arquivo de resultado.
2. Salvar em `Arquivos\AAAAMMDD\Retornos`.
3. Registrar horário, caminho e status.
4. Encaminhar o caso para resposta ao EC.

##### 3.6.1.3. Status retorno - Enviar e-mail com template de retorno

Usar o assunto `Status Cancelamento_Venda - @PROTOCOLO`.

| Situação                      | Ação                                            |
| ----------------------------- | ----------------------------------------------- |
| Arquivo Finalizado            | Enviar template de sucesso e anexar o resultado |
| Arquivo com Erro ou Rejeitado | Enviar template de erro e anexos aplicáveis     |
| Finalizado sem sucesso        | Comunicar a falha e encaminhar para tratamento  |

##### 3.6.1.4. Atualizar status no banco de dados

Registrar status final, descrição, horário do download, caminho do anexo e resultado do envio de e-mail.

### 3.7. RELATÓRIOS – Banco de Dados

A base deve garantir rastreabilidade entre entrada e saída.

| Etapa | Campos mínimos                                                                                                               |
| ----- | ---------------------------------------------------------------------------------------------------------------------------- |
| R1    | TimeStamp, IDTransacao, IDProtocolo, Status, Descricao, HoraEmailRecebido, RemetenteEmail, AssuntoEmail, Anexo, CaminhoAnexo |
| R2    | TimeStamp, IDTransacao, IDProtocolo, Status, Descrição, HoraDownload, CaminhoAnexo                                           |

**Status principais:**

* R1: `Exceção de negócio`, `Arquivo Validado`, `Sucesso upload`, `Insucesso upload`.
* R2: `Em andamento`, `Atrasado`, `Sucesso`, `Finalizado sem sucesso`, `Erro outros`.

Senhas e credenciais nunca devem ser armazenadas na base ou nos logs.

### 3.1. EXCEÇÕES

#### 3.1.1. Exceção de Negócios

| Exceção                                     | Tratamento                                              |
| ------------------------------------------- | ------------------------------------------------------- |
| Remetente não habilitado                    | Responder, registrar e não processar                    |
| Anexo inválido ou fora do template          | Gerar relatório, responder e seguir para o próximo caso |
| E-mail, protocolo ou arquivo não encontrado | Registrar e encaminhar para análise                     |
| Erro na geração do Excel ou resposta        | Não reprocessar automaticamente; registrar e seguir     |
| Protocolo acima de 96 horas                 | Finalizar sem sucesso e acionar a área de negócio       |

#### 3.1.2. Exceção de Sistema

| Exceção                     | Tratamento                                                |
| --------------------------- | --------------------------------------------------------- |
| Portal indisponível         | Registrar insucesso e encaminhar para contingência manual |
| E-mail ou rede indisponível | Registrar, notificar e interromper com segurança          |
| Caixa postal cheia          | Notificar e executar ou solicitar arquivamento            |
| Falha de autenticação       | Não expor credenciais; solicitar regularização do acesso  |

Na contingência manual, a área deve atualizar a mesma estrutura de controle definida neste PDD.

#### 3.1.3. Sistemas e/ou Softwares utilizados

| Sistema                       | Finalidade                       |
| ----------------------------- | -------------------------------- |
| Cliente de e-mail corporativo | Receber e responder solicitações |
| Planilha eletrônica           | Validar e preparar arquivos      |
| Retaguarda TI                 | Upload, consulta e download      |
| Diretório de rede fictício    | Armazenar arquivos e bases       |

### 3.2. PREPARAÇÃO PARA AUTOMAÇÃO

#### 3.2.1. E-mails

* **Caixa do processo:** `cancelamento.vendas@empresa-exemplo.invalid`.
* **Alertas internos:** `operacoes@empresa-exemplo.invalid` e `suporte.rpa@empresa-exemplo.invalid`.
* **Retorno ao EC:** usar o remetente registrado na base e o template correspondente ao status.

#### 3.2.2. Diretórios

| Diretório fictício                                                      | Uso                               |
| ----------------------------------------------------------------------- | --------------------------------- |
| `\\servidor-exemplo\automacao\cancelamento-vendas\Arquivos`             | Arquivos diários                  |
| `\\servidor-exemplo\automacao\cancelamento-vendas\Bases`                | Base de status e lista permissiva |
| `\\servidor-exemplo\automacao\cancelamento-vendas\Arquivamento_Outlook` | Arquivamento de mensagens         |

#### 3.2.3. Gestão de Acessos

Solicitar pelos canais corporativos os perfis genéricos:

* `[PERFIL_REDE_CANCELAMENTO]`;
* `[PERFIL_RETAGUARDA_USUARIO]`;
* `[PERFIL_CAIXA_COMPARTILHADA]`;
* `[PERFIL_COFRE_RPA]`.

Endereços dos sistemas e credenciais devem permanecer em configuração segura, fora deste documento.

#### 3.2.4. Planejamento da Execução

* **Dias:** segunda-feira a domingo.
* **Janelas de processamento:** 09h, 15h e 18h.
* **Janelas de consulta:** 12h, 17h e 21h.
* **SLA de retorno:** até dois dias úteis, observadas as regras de atraso.

O tempo de retorno varia conforme a quantidade de transações no arquivo.

## 4. ANEXOS

Templates mantidos em repositório corporativo controlado:

* `Template_Cancelamento_Venda.xlsx`;
* resposta de protocolo;
* resposta para remetente não cadastrado;
* retorno de sucesso;
* retorno de erro.

Não há imagens ou binários incorporados neste arquivo.

## 5. REFERÊNCIAS

* PDD genérico do processo de Cancelamento de Venda, versão 11.
* Template corporativo de cancelamento.
* Procedimentos internos de acesso, credenciais e contingência.

Não são mantidos links ou caminhos corporativos reais nesta versão.

## 6. HISTÓRICO DE REVISÕES

| Versão | Data                    | Alteração                                                                            | Responsável fictício |
| ------ | ----------------------- | ------------------------------------------------------------------------------------ | -------------------- |
| 1 a 10 | 02/01/2022 a 15/01/2024 | Criação e evoluções de validação, templates, banco, status e arquivamento            | Mariana Oliveira     |
| 11     | 21/02/2024              | Novos status de saída, retorno de erro, validação de data e freezing do arquivamento | Mariana Oliveira     |

---

> **Nota:** Versão resumida e anonimizada, sem imagens, links, credenciais, caminhos ou identificadores corporativos reais.
