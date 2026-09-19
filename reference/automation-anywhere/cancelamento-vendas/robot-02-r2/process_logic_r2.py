from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


# ============================================================
# REFERÊNCIA NÃO EXECUTÁVEL
# ============================================================
#
# Este arquivo representa a lógica esperada do Robô 2 (R2)
# do processo de cancelamento de vendas.
#
# Foi criado para fins de POC, documentação e análise pelo
# agente de IA.
#
# Não representa código real de produção.
# ============================================================


STATUS_ABERTOS = {
    "SUCESSO UPLOAD",
    "EM ANDAMENTO",
    "ATRASADO",
}


@dataclass
class RegistroProtocolo:
    protocolo: str
    nome_arquivo: str
    data_upload: datetime
    status: str
    baixado: bool = False
    caminho_retorno: Optional[str] = None
    descricao: str = ""


@dataclass
class ResultadoPortal:
    encontrado: bool
    finalizado: bool
    sucesso: bool
    arquivo_disponivel: bool
    mensagem: str


class BancoSimulado:
    def __init__(self):
        agora = datetime.now()

        self.registros = [
            RegistroProtocolo(
                protocolo="SC-000001",
                nome_arquivo="cancelamento_123456.xlsx",
                data_upload=agora - timedelta(hours=5),
                status="SUCESSO UPLOAD",
            ),
            RegistroProtocolo(
                protocolo="SC-000002",
                nome_arquivo="cancelamento_654321.xlsx",
                data_upload=agora - timedelta(hours=20),
                status="EM ANDAMENTO",
            ),
            RegistroProtocolo(
                protocolo="SC-000003",
                nome_arquivo="cancelamento_999999.xlsx",
                data_upload=agora - timedelta(hours=100),
                status="ATRASADO",
            ),
        ]

    def buscar_protocolos_pendentes(self) -> list[RegistroProtocolo]:
        return [
            registro
            for registro in self.registros
            if registro.status.upper() in STATUS_ABERTOS
            and not registro.baixado
        ]

    def atualizar(
        self,
        registro: RegistroProtocolo,
        status: str,
        descricao: str,
        baixado: Optional[bool] = None,
        caminho_retorno: Optional[str] = None,
    ) -> None:
        registro.status = status
        registro.descricao = descricao

        if baixado is not None:
            registro.baixado = baixado

        if caminho_retorno is not None:
            registro.caminho_retorno = caminho_retorno

        print(
            f"[BANCO] {registro.protocolo} | "
            f"{registro.nome_arquivo} | "
            f"{registro.status} | "
            f"{registro.descricao}"
        )


class PortalRetaguardaSimulado:
    """
    Simula a consulta que, no processo real,
    seria feita via HTTP request.
    """

    def consultar(
        self,
        protocolo: str,
        nome_arquivo: str,
    ) -> ResultadoPortal:

        cenarios = {
            "SC-000001": ResultadoPortal(
                encontrado=True,
                finalizado=True,
                sucesso=True,
                arquivo_disponivel=True,
                mensagem="Arquivo Finalizado",
            ),

            "SC-000002": ResultadoPortal(
                encontrado=True,
                finalizado=False,
                sucesso=False,
                arquivo_disponivel=False,
                mensagem="Aguardando processamento",
            ),

            "SC-000003": ResultadoPortal(
                encontrado=False,
                finalizado=False,
                sucesso=False,
                arquivo_disponivel=False,
                mensagem="Protocolo não encontrado",
            ),
        }

        return cenarios.get(
            protocolo,
            ResultadoPortal(
                encontrado=False,
                finalizado=False,
                sucesso=False,
                arquivo_disponivel=False,
                mensagem="Protocolo não localizado",
            ),
        )

    def baixar_arquivo(
        self,
        protocolo: str,
        nome_arquivo: str,
    ) -> Optional[str]:

        print(
            f"[PORTAL] Baixando resultado de "
            f"{protocolo} / {nome_arquivo}"
        )

        # Simulação de sucesso no download.
        return (
            f"Retornos/"
            f"{protocolo}_{nome_arquivo}"
        )


class ProcessoConsultaCancelamento:
    def __init__(self):
        self.banco = BancoSimulado()
        self.portal = PortalRetaguardaSimulado()

    def executar(self) -> None:
        print("[R2] Iniciando consulta de cancelamentos")

        registros = self.banco.buscar_protocolos_pendentes()

        print(
            f"[R2] {len(registros)} protocolo(s) "
            f"pendente(s) encontrado(s)"
        )

        for registro in registros:
            try:
                self.processar(registro)

            except ConnectionError as erro:
                self.banco.atualizar(
                    registro,
                    status="ERRO SISTEMA",
                    descricao=(
                        "Não foi possível acessar "
                        f"a Retaguarda: {erro}"
                    ),
                )

            except Exception as erro:
                self.banco.atualizar(
                    registro,
                    status="ERRO OUTROS",
                    descricao=str(erro),
                )

    def processar(
        self,
        registro: RegistroProtocolo,
    ) -> None:

        print(
            f"\n[R2] Consultando protocolo "
            f"{registro.protocolo}"
        )

        resultado = self.portal.consultar(
            registro.protocolo,
            registro.nome_arquivo,
        )

        # ----------------------------------------
        # CENÁRIO 1
        # Protocolo não encontrado
        # ----------------------------------------

        if not resultado.encontrado:
            self.banco.atualizar(
                registro,
                status="PROTOCOLO NÃO ENCONTRADO",
                descricao=resultado.mensagem,
            )
            return

        # ----------------------------------------
        # CENÁRIO 2
        # Ainda não terminou
        # ----------------------------------------

        if not resultado.finalizado:
            self.atualizar_status_por_tempo(
                registro,
                resultado.mensagem,
            )
            return

        # ----------------------------------------
        # CENÁRIO 3
        # Finalizado, mas sem sucesso
        # ----------------------------------------

        if not resultado.sucesso:
            self.banco.atualizar(
                registro,
                status="FINALIZADO SEM SUCESSO",
                descricao=resultado.mensagem,
            )
            return

        # ----------------------------------------
        # CENÁRIO 4
        # Finalizado com sucesso,
        # mas arquivo ainda indisponível
        # ----------------------------------------

        if not resultado.arquivo_disponivel:
            self.banco.atualizar(
                registro,
                status="ERRO DOWNLOAD",
                descricao=(
                    "Processamento finalizado, "
                    "mas arquivo não disponível"
                ),
            )
            return

        # ----------------------------------------
        # CENÁRIO 5
        # Download
        # ----------------------------------------

        caminho = self.portal.baixar_arquivo(
            registro.protocolo,
            registro.nome_arquivo,
        )

        if not caminho:
            self.banco.atualizar(
                registro,
                status="ERRO DOWNLOAD",
                descricao=(
                    "Arquivo localizado, mas "
                    "não foi possível baixar"
                ),
            )
            return

        # ----------------------------------------
        # SUCESSO
        # ----------------------------------------

        self.banco.atualizar(
            registro,
            status="SUCESSO",
            descricao="Resultado baixado com sucesso",
            baixado=True,
            caminho_retorno=caminho,
        )

    def atualizar_status_por_tempo(
        self,
        registro: RegistroProtocolo,
        mensagem_portal: str,
    ) -> None:

        idade = (
            datetime.now() - registro.data_upload
        )

        horas = idade.total_seconds() / 3600

        if horas <= 12:
            status = "EM ANDAMENTO"

        elif horas < 96:
            status = "ATRASADO"

        else:
            status = "FINALIZADO SEM SUCESSO"

        self.banco.atualizar(
            registro,
            status=status,
            descricao=mensagem_portal,
        )


if __name__ == "__main__":
    ProcessoConsultaCancelamento().executar()