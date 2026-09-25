import json
from dataclasses import dataclass
from typing import Any


class ErroProtocolo(Exception):
    """Mensagem recebida não segue o protocolo JSON da aplicação."""


@dataclass(frozen=True)
class Mensagem:
    tipo: str
    dados: dict[str, Any]

    @staticmethod
    def decodificar(conteudo: str | bytes) -> "Mensagem":
        texto = conteudo.decode("utf-8") if isinstance(conteudo, bytes) else conteudo
        try:
            objeto = json.loads(texto)
        except json.JSONDecodeError as erro:
            raise ErroProtocolo("Mensagem JSON inválida.") from erro

        if not isinstance(objeto, dict):
            raise ErroProtocolo("A mensagem deve ser um objeto JSON.")

        tipo = objeto.pop("tipo", None)
        if not isinstance(tipo, str) or not tipo:
            raise ErroProtocolo("O campo 'tipo' é obrigatório.")

        return Mensagem(tipo=tipo, dados=objeto)

    def codificar(self) -> str:
        return json.dumps({"tipo": self.tipo, **self.dados}, ensure_ascii=False)


def criar_mensagem(tipo: str, **dados: Any) -> str:
    return Mensagem(tipo=tipo, dados=dados).codificar()
