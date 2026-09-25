from pathlib import Path

from tornado.ioloop import IOLoop
from tornado.web import Application, StaticFileHandler

from logger import configurar_logger, obter_logger
from servidor import XadrezHandler

log_servidor = obter_logger("Servidor")


class ArquivosWebHandler(StaticFileHandler):
    """Serve a interface sem reutilizar arquivos antigos do cache do navegador."""

    def set_extra_headers(self, path: str) -> None:
        self.set_header("Cache-Control", "no-store")


def criar_aplicacao() -> Application:
    diretorio_web = Path(__file__).resolve().parent / "clientes" / "web"
    return Application(
        [
            (r"/ws", XadrezHandler),
            (
                r"/(.*)",
                ArquivosWebHandler,
                {"path": str(diretorio_web), "default_filename": "index.html"},
            ),
        ],
        websocket_ping_interval=20,
        websocket_ping_timeout=20,
    )


def iniciar_servidor(porta: int = 8080) -> None:
    aplicacao = criar_aplicacao()
    aplicacao.listen(porta, address="127.0.0.1")
    log_servidor.info("Interface: http://localhost:%s", porta)
    log_servidor.info("WebSocket: ws://localhost:%s/ws", porta)
    IOLoop.current().start()


if __name__ == "__main__":
    configurar_logger()
    iniciar_servidor()
