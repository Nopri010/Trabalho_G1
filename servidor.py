from __future__ import annotations

import asyncio
import secrets
from contextlib import suppress
from dataclasses import dataclass, field
from urllib.parse import urlparse

from tornado.ioloop import IOLoop
from tornado.websocket import WebSocketClosedError, WebSocketHandler

from jogo import Cor, ErroJogo, PartidaXadrez
from logger import obter_logger
from protocolo import ErroProtocolo, Mensagem, criar_mensagem

log_servidor = obter_logger("Servidor")
ALFABETO_SALA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PRAZO_RECONEXAO = 8.0


@dataclass
class Sala:
    codigo: str
    partida: PartidaXadrez = field(default_factory=PartidaXadrez)
    conexoes: dict[Cor, XadrezHandler] = field(default_factory=dict)
    tokens: dict[Cor, str] = field(default_factory=dict)
    tarefas_desconexao: dict[Cor, asyncio.Task[None]] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class GerenciadorSalas:
    """Mantém as salas em memória e serializa alterações concorrentes."""

    def __init__(self, prazo_reconexao: float = PRAZO_RECONEXAO) -> None:
        self.salas: dict[str, Sala] = {}
        self.lock = asyncio.Lock()
        self.prazo_reconexao = prazo_reconexao

    async def criar_sala(self, conexao: XadrezHandler, nome: str) -> tuple[Sala, Cor]:
        async with self.lock:
            codigo = self._novo_codigo()
            sala = Sala(codigo=codigo)
            cor = sala.partida.adicionar_jogador(nome)
            sala.conexoes[cor] = conexao
            sala.tokens[cor] = secrets.token_urlsafe(32)
            self.salas[codigo] = sala
        log_servidor.info("Sala %s criada por %s", codigo, nome)
        return sala, cor

    async def entrar_sala(
        self,
        conexao: XadrezHandler,
        codigo: str,
        nome: str,
    ) -> tuple[Sala, Cor]:
        codigo_normalizado = codigo.strip().upper()
        async with self.lock:
            sala = self.salas.get(codigo_normalizado)
        if sala is None:
            raise ErroJogo("sala_inexistente", "Sala não encontrada.")

        async with sala.lock:
            if sala.partida.estado == "encerrada":
                raise ErroJogo("partida_encerrada", "Essa partida já foi encerrada.")
            cor = sala.partida.adicionar_jogador(nome)
            sala.conexoes[cor] = conexao
            sala.tokens[cor] = secrets.token_urlsafe(32)
        log_servidor.info("%s entrou na sala %s", nome, codigo_normalizado)
        return sala, cor

    async def reconectar(
        self,
        conexao: XadrezHandler,
        codigo: str,
        token: str,
    ) -> tuple[Sala, Cor]:
        codigo_normalizado = codigo.strip().upper()
        async with self.lock:
            sala = self.salas.get(codigo_normalizado)
        if sala is None:
            raise ErroJogo("sala_inexistente", "A sala não está mais disponível.")

        async with sala.lock:
            cor_encontrada: Cor | None = None
            for cor_atual, token_atual in sala.tokens.items():
                if secrets.compare_digest(token_atual, token):
                    cor_encontrada = cor_atual
                    break
            if cor_encontrada is None:
                raise ErroJogo("sessao_invalida", "Não foi possível recuperar essa sessão.")
            cor = cor_encontrada

            tarefa = sala.tarefas_desconexao.pop(cor, None)
            if tarefa is not None:
                tarefa.cancel()

            conexao_anterior = sala.conexoes.get(cor)
            sala.conexoes[cor] = conexao

        if conexao_anterior is not None and conexao_anterior is not conexao:
            conexao_anterior.close(code=4001, reason="sessao_substituida")
        log_servidor.info("Sala %s: jogador %s reconectado", sala.codigo, cor)
        return sala, cor

    async def realizar_jogada(
        self,
        sala: Sala,
        cor: Cor,
        origem: object,
        destino: object,
        promocao: object = None,
    ) -> None:
        async with sala.lock:
            sala.partida.realizar_jogada(
                cor=cor,
                origem=str(origem),
                destino=str(destino),
                promocao=None if promocao is None else str(promocao),
            )
            envios = self._estados_da_sala(sala)
        log_servidor.info("Sala %s: %s jogou %s%s", sala.codigo, cor, origem, destino)
        await self._enviar_todos(envios)

    async def desistir(self, sala: Sala, cor: Cor) -> None:
        async with sala.lock:
            sala.partida.desistir(cor)
            envios = self._estados_da_sala(sala)
        log_servidor.info("Sala %s: %s desistiu", sala.codigo, cor)
        await self._enviar_todos(envios)

    async def anunciar_sessao(
        self,
        sala: Sala,
        cor: Cor,
        conexao: XadrezHandler,
    ) -> None:
        await conexao.enviar(
            "sessao_iniciada",
            codigo_sala=sala.codigo,
            cor=cor,
            nome=sala.partida.jogadores[cor],
            token=sala.tokens[cor],
        )
        await self.publicar_estado(sala)

    async def publicar_estado(self, sala: Sala) -> None:
        async with sala.lock:
            envios = self._estados_da_sala(sala)
        await self._enviar_todos(envios)

    async def desconectar(
        self,
        sala: Sala,
        cor: Cor,
        conexao: XadrezHandler,
    ) -> None:
        async with sala.lock:
            if sala.conexoes.get(cor) is not conexao:
                return
            sala.conexoes.pop(cor, None)
            tarefa_anterior = sala.tarefas_desconexao.pop(cor, None)
            if tarefa_anterior is not None:
                tarefa_anterior.cancel()
            sala.tarefas_desconexao[cor] = asyncio.create_task(self._encerrar_apos_prazo(sala, cor))

        log_servidor.info(
            "Sala %s: jogador %s desconectado; aguardando reconexão",
            sala.codigo,
            cor,
        )

    async def _encerrar_apos_prazo(self, sala: Sala, cor: Cor) -> None:
        try:
            await asyncio.sleep(self.prazo_reconexao)
        except asyncio.CancelledError:
            return

        async with sala.lock:
            if cor in sala.conexoes:
                return
            sala.tarefas_desconexao.pop(cor, None)
            sala.tokens.pop(cor, None)
            sala.partida.desconectar(cor)
            envios = self._estados_da_sala(sala)
            sala_vazia = not sala.conexoes

        log_servidor.info("Sala %s: prazo de reconexão encerrado para %s", sala.codigo, cor)
        await self._enviar_todos(envios)
        if sala_vazia:
            async with self.lock:
                if self.salas.get(sala.codigo) is sala:
                    self.salas.pop(sala.codigo, None)
                    log_servidor.info("Sala %s removida da memória", sala.codigo)

    def _estados_da_sala(self, sala: Sala) -> list[tuple[XadrezHandler, str]]:
        return [
            (
                conexao,
                criar_mensagem("estado_partida", **sala.partida.estado_para(cor)),
            )
            for cor, conexao in sala.conexoes.items()
        ]

    @staticmethod
    async def _enviar_todos(envios: list[tuple[XadrezHandler, str]]) -> None:
        if envios:
            await asyncio.gather(*(conexao.enviar_texto(mensagem) for conexao, mensagem in envios))

    def _novo_codigo(self) -> str:
        while True:
            codigo = "".join(secrets.choice(ALFABETO_SALA) for _ in range(5))
            if codigo not in self.salas:
                return codigo


gerenciador = GerenciadorSalas()


class XadrezHandler(WebSocketHandler):
    sala: Sala | None = None
    cor: Cor | None = None
    codigo_reconexao: str | None = None

    def check_origin(self, origin: str) -> bool:
        """Aceita somente a interface servida pelo mesmo host do WebSocket."""
        return not origin or urlparse(origin).netloc == self.request.host

    async def open(self) -> None:
        self.set_nodelay(True)
        acao = self.get_query_argument("acao", "")
        nome = self.get_query_argument("nome", "")
        try:
            if acao == "criar":
                self.sala, self.cor = await gerenciador.criar_sala(self, nome)
            elif acao == "entrar":
                codigo = self.get_query_argument("sala", "")
                self.sala, self.cor = await gerenciador.entrar_sala(self, codigo, nome)
            elif acao == "reconectar":
                self.codigo_reconexao = self.get_query_argument("sala", "")
                return
            else:
                raise ErroJogo("acao_invalida", "Informe se deseja criar ou entrar na sala.")

            await gerenciador.anunciar_sessao(self.sala, self.cor, self)
        except ErroJogo as erro:
            await self.enviar_erro(erro.codigo, erro.mensagem)
            self.close(code=4000, reason=erro.codigo)

    async def on_message(self, conteudo: str | bytes) -> None:
        try:
            mensagem = Mensagem.decodificar(conteudo)
            if self.sala is None or self.cor is None:
                if mensagem.tipo != "reconectar" or self.codigo_reconexao is None:
                    raise ErroJogo("sessao_invalida", "A conexão não pertence a uma sala.")
                token = mensagem.dados.get("token")
                if not isinstance(token, str) or not token:
                    raise ErroProtocolo("Token de reconexão ausente.")
                self.sala, self.cor = await gerenciador.reconectar(
                    self,
                    self.codigo_reconexao,
                    token,
                )
                await gerenciador.anunciar_sessao(self.sala, self.cor, self)
                return

            if mensagem.tipo == "jogada":
                await gerenciador.realizar_jogada(
                    self.sala,
                    self.cor,
                    mensagem.dados.get("origem", ""),
                    mensagem.dados.get("destino", ""),
                    mensagem.dados.get("promocao"),
                )
            elif mensagem.tipo == "desistir":
                await gerenciador.desistir(self.sala, self.cor)
            elif mensagem.tipo == "ping":
                await self.enviar("pong")
            else:
                raise ErroProtocolo("Tipo de mensagem desconhecido.")
        except ErroJogo as erro:
            await self.enviar_erro(erro.codigo, erro.mensagem)
            if self.sala is None:
                self.close(code=4000, reason=erro.codigo)
        except ErroProtocolo as erro:
            await self.enviar_erro("protocolo_invalido", str(erro))
            if self.sala is None:
                self.close(code=4000, reason="protocolo_invalido")

    def on_close(self) -> None:
        if self.sala is not None and self.cor is not None:
            IOLoop.current().spawn_callback(
                gerenciador.desconectar,
                self.sala,
                self.cor,
                self,
            )

    async def enviar(self, tipo: str, **dados: object) -> None:
        await self.enviar_texto(criar_mensagem(tipo, **dados))

    async def enviar_erro(self, codigo: str, mensagem: str) -> None:
        await self.enviar("erro", codigo=codigo, mensagem=mensagem)

    async def enviar_texto(self, mensagem: str) -> None:
        with suppress(WebSocketClosedError):
            await self.write_message(mensagem)
