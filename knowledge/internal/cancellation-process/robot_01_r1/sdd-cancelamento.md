# CANCELAMENTO DE VENDA — SDD GENÉRICO

| Campo             | Valor                    |
| ----------------- | ------------------------ |
| **Tipo**          | SDD resumido             |
| **Plataforma**    | Automation Anywhere A360 |
| **Versão**        | 1.1                      |
| **Classificação** | Uso interno              |

## 1. OBJETIVO

Descrever o desenho técnico da automação sem expor nomes, credenciais, URLs, servidores, caminhos ou identificadores corporativos reais.

## 2. ESCOPO

O código implementa o R1: inicialização, leitura de e-mails, prevenção de duplicidade, validação do remetente, geração de protocolo, validação de planilhas, separação por EC Matriz, criação de arquivos, upload na Retaguarda TI, resposta ao remetente, atualização do banco e relatório operacional.

Não foi encontrado fluxo R2 ativo para consultar protocolos, baixar o resultado final e responder sobre a efetivação do cancelamento.

A base reserva campos para R2, mas este pacote apenas os consulta ou exporta.

## 3. ARQUITETURA

A solução usa TaskBots A360.

Microsoft 365 Outlook trata mensagens; Excel e Python com pandas/openpyxl leem e transformam planilhas; Oracle mantém controles e validações; API HTTP autenticada recebe os arquivos; diretórios locais e de rede guardam temporários, recebidos, ajustados, erros, evidências e relatórios; Credential Manager fornece segredos.

Componentes lógicos: orquestrador, carregador de e-mails, processador, validadores, separador por EC, autenticador, upload, e-mail e relatório.

## 4. FLUXO TÉCNICO

### 4.1 Inicialização

O orquestrador identifica o ambiente, carrega configurações, cria a estrutura local, inicia logs, gera o ID de execução, mapeia a rede e cria `AAAAMMDD` com `Recebidos`, `Ajustados`, `Retornos`, `Analise_RPA` e `Arquivamento_Outlook`.

Raiz fictícia:

`\\servidor-exemplo\automacao\cancelamento-venda`.

### 4.2 Carga

O robô conecta ao Microsoft 365 por credenciais de aplicação, lê `cancelamento.venda@empresa-exemplo.invalid`, normaliza os metadados, ignora mensagens inválidas, salva uma cópia e baixa anexos em pasta exclusiva.

O item da fila contém remetente, destinatários, assunto, datas, ID da mensagem, quantidade e caminhos dos anexos.

O carregador reconhece `xlsx` e `csv`, mas a regra processa apenas `xlsx`.

### 4.3 Processamento

A duplicidade é verificada por `remetente + data de recebimento + assunto`.

E-mail já tratado é movido e encerrado.

Para item novo, o robô gera protocolo, grava o e-mail e valida o remetente.

Se não autorizado, atualiza o status, responde, move a mensagem e não processa anexos.

Se autorizado, classifica os arquivos.

Ao final, move o e-mail conforme o resultado e registra o encerramento.

### 4.4 Protocolo

Formato:

`SC- + AAAAMMDD + número aleatório entre 1 e 9.999.999.999`.

Exemplo fictício:

`SC-203001159876543210`.

Não há verificação explícita de unicidade nem garantia de dez posições.

### 4.5 Remetente

A lista permissiva é copiada da rede para a área temporária.

O robô lê a coluna configurada, converte valores para minúsculas, remove espaços e compara com o remetente normalizado, retornando `habilitado` ou `não habilitado`.

### 4.6 Anexos

E-mail sem anexo recebe resposta específica.

Havendo arquivos, a mensagem vai para `Em processamento` e o robô autentica na Retaguarda.

Para cada anexo:

* gera ID;
* exige `xlsx`;
* move o original para `Recebidos`;
* lê todas as abas em Python;
* valida cabeçalho e conteúdo;
* gera relatório se inválido;
* e, se válido, separa registros por EC Matriz, cria arquivos e faz os uploads.

Depois envia resposta consolidada.

Destino:

* todos válidos para `Atendidos`;
* resultado misto para `Atendidos parcialmente`;
* todos inválidos para `Template inválido`.

### 4.7 Upload

Usuário e senha vêm do gerenciador seguro.

O script Python autentica no serviço e devolve cookie temporário.

Cada arquivo é enviado por requisição multipart.

O robô grava EC, arquivo, data e `Upload realizado com sucesso` ou `Falha no upload`.

Credenciais e cookies não são persistidos.

### 4.8 Encerramento

O robô consulta os registros da execução, gera CSV, envia relatório, atualiza o status final e registra exceções ou evidências.

## 5. VALIDAÇÃO DO EXCEL

A planilha deve ter uma única aba válida com:

* Nº EC Matriz;
* Nº EC da compra;
* autorização;
* moeda;
* data;
* valor da venda;
* valor do cancelamento;
* comprovante;
* terminal.

Cabeçalho ausente, divergente ou duplicado é exceção de negócio.

O código remove espaços, normaliza a data e converte valores em texto.

Regras:

* ECs numéricos;
* autorização alfanumérica com até seis caracteres;
* moeda definida na configuração;
* data `DDMMAAAA`, válida, não futura e a partir de 2023;
* valores numéricos obrigatórios;
* comprovante numérico com até nove posições;
* terminal alfanumérico com até oito.

Os dados passam por tabela temporária e expressões regulares; erros por linha e campo alimentam o relatório.

## 6. DADOS

O modelo lógico contém controles de e-mail, anexo, EC, validação temporária e processo consolidado.

Registra execução, remetente, assunto, protocolo, arquivos, caminhos lógicos, validações, ECs, datas e status.

Usa:

* `SELECT` para duplicidade e relatórios;
* `INSERT` para novos itens;
* `UPDATE` para estados;
* `DELETE` para limpar a validação temporária.

Nomes físicos foram omitidos.

## 7. CONFIGURAÇÃO E SEGURANÇA

O JSON possui perfis por ambiente com tentativas, status, cabeçalho, templates, pastas e aliases.

Segredos permanecem no Credential Manager ou em variáveis protegidas:

* `[CREDENCIAL_EMAIL]`;
* `[CREDENCIAL_RETAGUARDA]`;
* `[CREDENCIAL_BANCO]`;
* `[SEGREDO_APLICACAO]`.

Não registrar senhas, cookies, e-mails reais ou caminhos corporativos em código, configuração, banco, log ou relatório.

Credencial literal, mesmo em comando desativado, deve ser removida e rotacionada.

## 8. LOGS E EXCEÇÕES

Formato:

`Timestamp;Task;TipoLog;LinhaErro;Descricao`

com:

* `INFO`;
* `ATENÇÃO`;
* `ERRO`.

Subtarefas retornam `TipoExcecao`, `MensagemExcecao` e dados da operação; falhas podem gerar evidência.

Negócio:

* duplicidade;
* remetente não habilitado;
* ausência de anexo;
* extensão inválida;
* cabeçalho incorreto;
* dados inválidos;
* falha de upload.

Sistema:

* falha no Microsoft 365;
* rede;
* banco;
* Excel;
* autenticação;
* API;
* arquivos.

Assunto e remetente podem aparecer no log; o acesso deve ser restrito.

## 9. DEPENDÊNCIAS

A360, Bot Agent, pacotes de Outlook, Excel, Python, REST, arquivos, pastas e banco; Python 3 com `requests`, `pandas` e `openpyxl`; acessos à caixa compartilhada, rede, Oracle, Retaguarda e templates.

O agendamento é externo ao código.

## 10. PONTOS DE ATENÇÃO

* O R2 não está implementado;
* a tabela temporária é limpa integralmente e exige execução serial ou isolamento;
* consultas concatenam dados externos e devem ser parametrizadas;
* o carregador aceita `csv`, mas o classificador exige `xlsx`;
* um perfil de ambiente aparenta estar incompleto;
* segredos não devem permanecer no JSON ou em comandos desativados.

## 11. ACEITE

* E-mails novos são processados uma vez;
* remetentes não autorizados não chegam aos anexos;
* somente `xlsx` válido é enviado;
* cada EC Matriz gera arquivo próprio;
* sucesso e falha são persistidos;
* o remetente recebe resposta consolidada;
* o e-mail é movido conforme o resultado;
* a execução gera logs e CSV;
* falhas retornam tipo e mensagem;
* nenhuma credencial é gravada.

---

| Histórico                                                                               |
| --------------------------------------------------------------------------------------- |
| **versão 1.1, 18/09/2026, resumo anonimizado, responsável fictício: Mariana Oliveira.** |

> **Nota:** dados físicos e sensíveis foram substituídos por descrições lógicas ou fictícias.
