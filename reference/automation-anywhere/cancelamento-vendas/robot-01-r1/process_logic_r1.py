from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re


HEADERS_ESPERADOS = (
    "NÂº EC Matriz", "NÂº EC onde foi efetuada a compra", "CÃ³digo da autorizaÃ§Ã£o",
    "CÃ³digo da Moeda (986)", "Data da venda", "Vlr venda (vlr original transaÃ§Ã£o)",
    "Valor Cancelamento", "NÂº Comprovante Venda (CV)", "NÂº do terminal",
)
PASTAS_EMAIL = {
    "processando": "Em processamento", "sucesso": "Atendidos Little Get",
    "parcial": "Atendidos Parcialmente", "template_invalido": "Template InvÃ¡lido",
    "remetente_invalido": "Remetentes NÃ£o Habilitados", "ja_processado": "JÃ¡ processados",
    "email_invalido": "E-mails InvÃ¡lidos",
}


@dataclass
class Anexo:
    nome: str
    headers: tuple[str, ...]
    linhas: list[dict[str, str]]


@dataclass
class Email:
    id: str
    remetente: str
    assunto: str
    anexos: list[Anexo] = field(default_factory=list)


@dataclass
class ResultadoAnexo:
    nome: str
    sucesso: bool
    detalhe: str


class ProcessoLittleGet:
    def __init__(self) -> None:
        self.remetentes_habilitados = {
            "cliente.habilitado@empresa.com", "operacao@empresa.com"
        }
        self.emails_processados = {"MSG-000"}
        self.proximo_protocolo = 1
        self.registros_banco: list[dict[str, str]] = []

    def executar(self) -> None:
        print("[SIMULAÃ‡ÃƒO] Inicializando configuraÃ§Ãµes, logs e estrutura de pastas")
        for email in self.carregar_fila_office365():
            try:
                self.processar_email(email)
            except Exception as erro:
                self.registrar("ERRO DE SISTEMA", email.id, str(erro))
        self.gerar_relatorio()
        print("[SIMULAÃ‡ÃƒO] Enviando relatÃ³rio consolidado por e-mail")

    def carregar_fila_office365(self) -> list[Email]:
        print("[SIMULAÃ‡ÃƒO] Lendo a Inbox do Microsoft 365 e baixando anexos")
        linha_valida = {
            "NÂº EC Matriz": "123456789",
            "NÂº EC onde foi efetuada a compra": "987654321",
            "CÃ³digo da autorizaÃ§Ã£o": "A1B2C3",
            "CÃ³digo da Moeda (986)": "986",
            "Data da venda": "01092026",
            "Vlr venda (vlr original transaÃ§Ã£o)": "150,00",
            "Valor Cancelamento": "50,00",
            "NÂº Comprovante Venda (CV)": "123456789",
            "NÂº do terminal": "POS123",
        }
        return [
            Email("MSG-001", "cliente.habilitado@empresa.com", "SolicitaÃ§Ã£o de cancelamento", [Anexo("cancelamentos.xlsx", HEADERS_ESPERADOS, [linha_valida])]),
            Email("MSG-002", "nao.cadastrado@empresa.com", "SolicitaÃ§Ã£o de cancelamento"),
        ]

    def processar_email(self, email: Email) -> None:
        if email.id in self.emails_processados:
            self.finalizar_email(email, PASTAS_EMAIL["ja_processado"], "E-mail jÃ¡ processado")
            return
        protocolo = self.gerar_protocolo()
        self.emails_processados.add(email.id)
        self.registrar("INÍCIO", email.id, protocolo)
        if email.remetente.lower().strip() not in self.remetentes_habilitados:
            self.atualizar_banco(email, protocolo, "REMETENTE NÃƒO HABILITADO")
            self.enviar_retorno(email, protocolo, "Remetente nÃ£o habilitado")
            self.finalizar_email(email, PASTAS_EMAIL["remetente_invalido"], protocolo)
            return
        anexos_xlsx = [a for a in email.anexos if Path(a.nome).suffix.lower() == ".xlsx"]
        if not anexos_xlsx:
            self.atualizar_banco(email, protocolo, "E-MAIL SEM ANEXO XLSX")
            self.enviar_retorno(email, protocolo, "O e-mail nÃ£o contÃ©m anexos XLSX vÃ¡lidos")
            self.finalizar_email(email, PASTAS_EMAIL["email_invalido"], protocolo)
            return
        self.mover_email(email, PASTAS_EMAIL["processando"])
        resultados = [self.processar_anexo(email, protocolo, a) for a in anexos_xlsx]
        sucessos = sum(resultado.sucesso for resultado in resultados)
        if sucessos == len(resultados):
            pasta_final = PASTAS_EMAIL["sucesso"]
        elif sucessos:
            pasta_final = PASTAS_EMAIL["parcial"]
        else:
            pasta_final = PASTAS_EMAIL["template_invalido"]
        resumo = "; ".join(f"{item.nome}: {item.detalhe}" for item in resultados)
        self.enviar_retorno(email, protocolo, resumo)
        self.finalizar_email(email, pasta_final, protocolo)

    def processar_anexo(self, email: Email, protocolo: str, anexo: Anexo) -> ResultadoAnexo:
        if anexo.headers != HEADERS_ESPERADOS:
            detalhe = "Headers duplicados, ausentes ou fora do padrÃ£o"
            self.atualizar_banco(email, protocolo, detalhe, anexo.nome)
            return ResultadoAnexo(anexo.nome, False, detalhe)
        erros = self.validar_conteudo(anexo.linhas)
        if erros:
            detalhe = "ConteÃºdo invÃ¡lido: " + " | ".join(erros)
            self.atualizar_banco(email, protocolo, detalhe, anexo.nome)
            return ResultadoAnexo(anexo.nome, False, detalhe)
        arquivos_por_ec = self.separar_por_ec(anexo)
        uploads_ok = all(self.upload_retaguarda(nome, linhas) for nome, linhas in arquivos_por_ec.items())
        detalhe = "UPLOAD REALIZADO COM SUCESSO" if uploads_ok else "FALHA NO UPLOAD"
        self.atualizar_banco(email, protocolo, detalhe, anexo.nome)
        return ResultadoAnexo(anexo.nome, uploads_ok, detalhe)

    def validar_conteudo(self, linhas: list[dict[str, str]]) -> list[str]:
        validadores = {
            "NÂº EC Matriz": r"^[0-9]+$", "NÂº EC onde foi efetuada a compra": r"^[0-9]+$",
            "CÃ³digo da autorizaÃ§Ã£o": r"^[A-Z0-9]{1,6}$", "CÃ³digo da Moeda (986)": r"^986$",
            "Vlr venda (vlr original transaÃ§Ã£o)": r"^\d+(,\d+)?$", "Valor Cancelamento": r"^\d+(,\d+)?$",
            "NÂº Comprovante Venda (CV)": r"^\d{1,9}$", "NÂº do terminal": r"^[A-Z0-9]{1,8}$",
        }
        erros: list[str] = []
        if not linhas:
            return ["Planilha sem dados"]
        for numero_linha, linha in enumerate(linhas, start=2):
            for coluna, expressao in validadores.items():
                valor = str(linha.get(coluna, "")).strip().upper()
                if not re.fullmatch(expressao, valor):
                    erros.append(f"linha {numero_linha}, coluna {coluna}")
            data_texto = str(linha.get("Data da venda", "")).strip()
            try:
                data_venda = datetime.strptime(data_texto, "%d%m%Y").date()
                if data_venda > datetime.now().date():
                    erros.append(f"linha {numero_linha}, Data da venda futura")
            except ValueError:
                erros.append(f"linha {numero_linha}, Data da venda invÃ¡lida")
        return erros

    def separar_por_ec(self, anexo: Anexo) -> dict[str, list[dict[str, str]]]:
        grupos: dict[str, list[dict[str, str]]] = {}
        for linha in anexo.linhas:
            ec = linha["NÂº EC Matriz"]
            grupos.setdefault(f"{Path(anexo.nome).stem}_{ec}.xlsx", []).append(linha)
        print(f"[SIMULAÃ‡ÃƒO] {anexo.nome} separado em {len(grupos)} arquivo(s) por EC")
        return grupos

    def upload_retaguarda(self, nome_arquivo: str, linhas: list[dict[str, str]]) -> bool:
        print(f"[SIMULAÃ‡ÃƒO] Upload de {nome_arquivo} na retaguarda ({len(linhas)} linha(s))")
        return bool(linhas)

    def gerar_protocolo(self) -> str:
        protocolo = f"SC-{self.proximo_protocolo:06d}"
        self.proximo_protocolo += 1
        return protocolo

    def atualizar_banco(self, email: Email, protocolo: str, status: str, anexo: str = "") -> None:
        self.registros_banco.append({
            "email_id": email.id, "protocolo": protocolo, "remetente": email.remetente,
            "anexo": anexo, "status": status,
        })
        print(f"[SIMULAÃ‡ÃƒO] Banco atualizado: {email.id} - {status}")

    def enviar_retorno(self, email: Email, protocolo: str, mensagem: str) -> None:
        print(f"[SIMULAÃ‡ÃƒO] Retorno para {email.remetente} | {protocolo} | {mensagem}")

    def mover_email(self, email: Email, pasta: str) -> None:
        print(f"[SIMULAÃ‡ÃƒO] Movendo {email.id} para '{pasta}'")

    def finalizar_email(self, email: Email, pasta: str, detalhe: str) -> None:
        self.mover_email(email, pasta)
        self.registrar("FIM", email.id, detalhe)

    def registrar(self, tipo: str, item: str, detalhe: str) -> None:
        print(f"[SIMULAÃ‡ÃƒO][{tipo}] {item}: {detalhe}")

    def gerar_relatorio(self) -> None:
        print("\n[SIMULAÃ‡ÃƒO] RelatÃ³rio consolidado")
        for registro in self.registros_banco:
            print(f"{registro['protocolo']};{registro['email_id']};{registro['anexo']};{registro['status']}")


if __name__ == "__main__":
    ProcessoLittleGet().executar()
