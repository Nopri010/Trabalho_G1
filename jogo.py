from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import chess

Cor = Literal["brancas", "pretas"]


class ErroJogo(Exception):
    """Erro de regra que pode ser exibido com segurança ao cliente."""

    def __init__(self, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem


PROMOCOES = {
    "q": chess.QUEEN,
    "r": chess.ROOK,
    "b": chess.BISHOP,
    "n": chess.KNIGHT,
}

MOTIVOS_TERMINO = {
    chess.Termination.CHECKMATE: "xeque_mate",
    chess.Termination.STALEMATE: "afogamento",
    chess.Termination.INSUFFICIENT_MATERIAL: "material_insuficiente",
    chess.Termination.SEVENTYFIVE_MOVES: "regra_75_lances",
    chess.Termination.FIVEFOLD_REPETITION: "repeticao_cinco_vezes",
    chess.Termination.FIFTY_MOVES: "regra_50_lances",
    chess.Termination.THREEFOLD_REPETITION: "repeticao_tripla",
    chess.Termination.VARIANT_WIN: "vitoria",
    chess.Termination.VARIANT_LOSS: "derrota",
    chess.Termination.VARIANT_DRAW: "empate",
}


@dataclass
class PartidaXadrez:
    """Estado global e regras de uma partida, sem detalhes de rede."""

    tabuleiro: chess.Board = field(default_factory=chess.Board)
    jogadores: dict[Cor, str | None] = field(
        default_factory=lambda: {"brancas": None, "pretas": None}
    )
    estado: Literal["aguardando", "ativa", "encerrada"] = "aguardando"
    resultado: str | None = None
    motivo: str | None = None
    ultima_jogada: dict[str, str] | None = None

    def adicionar_jogador(self, nome: str) -> Cor:
        nome_limpo = " ".join(nome.strip().split())
        if not 2 <= len(nome_limpo) <= 24:
            raise ErroJogo("nome_invalido", "Use um nome com 2 a 24 caracteres.")

        nomes_atuais = {nome.casefold() for nome in self.jogadores.values() if nome}
        if nome_limpo.casefold() in nomes_atuais:
            raise ErroJogo("nome_repetido", "Esse nome já está em uso na sala.")

        if self.jogadores["brancas"] is None:
            cor: Cor = "brancas"
        elif self.jogadores["pretas"] is None:
            cor = "pretas"
        else:
            raise ErroJogo("sala_cheia", "A sala já possui dois jogadores.")

        self.jogadores[cor] = nome_limpo
        if all(self.jogadores.values()):
            self.estado = "ativa"
        return cor

    def realizar_jogada(
        self,
        cor: Cor,
        origem: str,
        destino: str,
        promocao: str | None = None,
    ) -> None:
        if self.estado != "ativa":
            raise ErroJogo("partida_inativa", "A partida ainda não está ativa.")

        turno_esperado: Cor = "brancas" if self.tabuleiro.turn == chess.WHITE else "pretas"
        if cor != turno_esperado:
            raise ErroJogo("fora_do_turno", "Aguarde o turno do adversário.")

        try:
            casa_origem = chess.parse_square(origem.lower())
            casa_destino = chess.parse_square(destino.lower())
        except (AttributeError, ValueError) as erro:
            raise ErroJogo("casa_invalida", "Casa de origem ou destino inválida.") from erro

        peca_promocao = None
        if promocao is not None:
            peca_promocao = PROMOCOES.get(str(promocao).lower())
            if peca_promocao is None:
                raise ErroJogo(
                    "promocao_invalida",
                    "Escolha dama, torre, bispo ou cavalo.",
                )

        jogada = chess.Move(casa_origem, casa_destino, promotion=peca_promocao)
        if jogada not in self.tabuleiro.legal_moves:
            promocoes_possiveis = [
                candidata
                for candidata in self.tabuleiro.legal_moves
                if candidata.from_square == casa_origem
                and candidata.to_square == casa_destino
                and candidata.promotion is not None
            ]
            if promocoes_possiveis and promocao is None:
                raise ErroJogo(
                    "promocao_obrigatoria",
                    "Escolha a peça para promover o peão.",
                )
            raise ErroJogo("jogada_ilegal", "Essa jogada não é permitida.")

        notacao = self.tabuleiro.san(jogada)
        self.tabuleiro.push(jogada)
        self.ultima_jogada = {"uci": jogada.uci(), "san": notacao}
        self.atualizar_resultado()

    def atualizar_resultado(self) -> None:
        resultado = self.tabuleiro.outcome(claim_draw=True)
        if resultado is None:
            return

        self.estado = "encerrada"
        self.resultado = resultado.result()
        self.motivo = MOTIVOS_TERMINO.get(resultado.termination, "fim_de_jogo")

    def desistir(self, cor: Cor) -> None:
        if self.estado != "ativa":
            raise ErroJogo("partida_inativa", "Não há uma partida ativa para desistir.")
        self.estado = "encerrada"
        self.resultado = "0-1" if cor == "brancas" else "1-0"
        self.motivo = "desistencia"

    def desconectar(self, cor: Cor) -> None:
        if self.estado == "ativa":
            self.estado = "encerrada"
            self.resultado = "0-1" if cor == "brancas" else "1-0"
            self.motivo = "adversario_desconectado"
        elif self.estado == "aguardando":
            self.estado = "encerrada"
            self.motivo = "criador_desconectado"

    def estado_para(self, observador: Cor) -> dict[str, object]:
        turno: Cor = "brancas" if self.tabuleiro.turn == chess.WHITE else "pretas"
        jogadas_legais = (
            [jogada.uci() for jogada in self.tabuleiro.legal_moves]
            if self.estado == "ativa" and observador == turno
            else []
        )

        vencedor: Cor | None = None
        if self.resultado == "1-0":
            vencedor = "brancas"
        elif self.resultado == "0-1":
            vencedor = "pretas"

        return {
            "fen": self.tabuleiro.fen(),
            "jogadores": self.jogadores.copy(),
            "estado": self.estado,
            "turno": turno,
            "em_xeque": self.tabuleiro.is_check(),
            "resultado": self.resultado,
            "vencedor": vencedor,
            "motivo": self.motivo,
            "ultima_jogada": self.ultima_jogada,
            "jogadas_legais": jogadas_legais,
        }
