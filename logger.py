import logging


def configurar_logger() -> None:
    """Configura o nível e o formato dos logs do servidor."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def obter_logger(nome: str) -> logging.Logger:
    """Retorna um logger identificado pelo componente da aplicação."""
    return logging.getLogger(nome)
