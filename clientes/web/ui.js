const pecas = {
  K: "♔",
  Q: "♕",
  R: "♖",
  B: "♗",
  N: "♘",
  P: "♙",
  k: "♚",
  q: "♛",
  r: "♜",
  b: "♝",
  n: "♞",
  p: "♟",
};

const rotulosMotivo = {
  xeque_mate: "Xeque-mate",
  afogamento: "Empate por afogamento",
  material_insuficiente: "Empate por material insuficiente",
  regra_75_lances: "Empate pela regra dos 75 lances",
  repeticao_cinco_vezes: "Empate por repetição",
  regra_50_lances: "Empate pela regra dos 50 lances",
  repeticao_tripla: "Empate por repetição tripla",
  desistencia: "Partida encerrada por desistência",
  adversario_desconectado: "Adversário desconectado",
  criador_desconectado: "Criador da sala desconectado",
  fim_de_jogo: "Partida encerrada",
};

export const elementos = {
  homeView: document.querySelector("#home-view"),
  gameView: document.querySelector("#game-view"),
  connection: document.querySelector("#connection-status"),
  playerName: document.querySelector("#player-name"),
  roomCode: document.querySelector("#room-code"),
  createRoom: document.querySelector("#create-room"),
  joinRoom: document.querySelector("#join-room"),
  lobbyMessage: document.querySelector("#lobby-message"),
  currentRoomCode: document.querySelector("#current-room-code"),
  copyRoomCode: document.querySelector("#copy-room-code"),
  gameStatus: document.querySelector("#game-status"),
  board: document.querySelector("#chessboard"),
  boardMessage: document.querySelector("#board-message"),
  selfName: document.querySelector("#self-name"),
  opponentName: document.querySelector("#opponent-name"),
  playerColor: document.querySelector("#player-color"),
  selfTurn: document.querySelector("#self-turn"),
  opponentTurn: document.querySelector("#opponent-turn"),
  lastMove: document.querySelector("#last-move"),
  resign: document.querySelector("#resign"),
  newGame: document.querySelector("#new-game"),
  promotionModal: document.querySelector("#promotion-modal"),
};


export function atualizarConexao(estado, texto) {
  elementos.connection.className = `connection ${estado}`;
  elementos.connection.querySelector("span:last-child").textContent = texto;
}


export function bloquearLobby(bloqueado) {
  elementos.createRoom.disabled = bloqueado;
  elementos.joinRoom.disabled = bloqueado;
}


export function mostrarMensagemLobby(mensagem) {
  elementos.lobbyMessage.textContent = mensagem;
}


export function mostrarMensagemTabuleiro(mensagem) {
  elementos.boardMessage.textContent = mensagem;
}


export function abrirPartida(sessao) {
  elementos.currentRoomCode.textContent = sessao.codigoSala;
  elementos.selfName.textContent = sessao.nome;
  elementos.playerColor.textContent = sessao.cor.toUpperCase();
  elementos.homeView.classList.add("hidden");
  elementos.gameView.classList.remove("hidden");
  mostrarMensagemLobby("");
}


export function abrirLobby() {
  elementos.gameView.classList.add("hidden");
  elementos.homeView.classList.remove("hidden");
}


export function renderizarPartida(partida, sessao, selecionada, aoSelecionar) {
  const corAdversario = sessao.cor === "brancas" ? "pretas" : "brancas";
  elementos.selfName.textContent = partida.jogadores[sessao.cor] || sessao.nome;
  elementos.opponentName.textContent = partida.jogadores[corAdversario] || "Aguardando...";
  elementos.selfTurn.classList.toggle(
    "active",
    partida.estado === "ativa" && partida.turno === sessao.cor,
  );
  elementos.opponentTurn.classList.toggle(
    "active",
    partida.estado === "ativa" && partida.turno === corAdversario,
  );
  elementos.resign.disabled = partida.estado !== "ativa";
  elementos.lastMove.textContent = partida.ultima_jogada
    ? `Última jogada: ${partida.ultima_jogada.san} (${partida.ultima_jogada.uci})`
    : "Nenhuma jogada realizada.";

  if (partida.estado === "aguardando") {
    elementos.gameStatus.textContent = "Aguardando adversário...";
  } else if (partida.estado === "ativa") {
    const meuTurno = partida.turno === sessao.cor;
    elementos.gameStatus.textContent = partida.em_xeque
      ? meuTurno
        ? "Xeque — sua vez"
        : "Xeque no adversário"
      : meuTurno
        ? "Sua vez"
        : "Vez do adversário";
  } else {
    elementos.gameStatus.textContent = mensagemFinal(partida, sessao);
  }

  renderizarTabuleiro(partida, sessao, selecionada, aoSelecionar);
}


function mensagemFinal(partida, sessao) {
  const motivo = rotulosMotivo[partida.motivo] || "Partida encerrada";
  if (!partida.vencedor) return motivo;
  return partida.vencedor === sessao.cor
    ? `${motivo} — você venceu!`
    : `${motivo} — vitória do adversário`;
}


function lerFen(fen) {
  const posicao = {};
  const linhas = fen.split(" ")[0].split("/");
  linhas.forEach((linha, indiceLinha) => {
    let indiceColuna = 0;
    for (const item of linha) {
      if (/\d/.test(item)) {
        indiceColuna += Number(item);
      } else {
        const casa = `${"abcdefgh"[indiceColuna]}${8 - indiceLinha}`;
        posicao[casa] = item;
        indiceColuna += 1;
      }
    }
  });
  return posicao;
}


function renderizarTabuleiro(partida, sessao, selecionada, aoSelecionar) {
  const posicao = lerFen(partida.fen);
  const orientacaoBrancas = sessao.cor === "brancas";
  const colunas = orientacaoBrancas ? [..."abcdefgh"] : [..."hgfedcba"];
  const linhas = orientacaoBrancas ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
  const ultimaJogada = partida.ultima_jogada?.uci?.slice(0, 4) || "";
  const destinos = destinosLegais(partida, selecionada);
  elementos.board.replaceChildren();

  linhas.forEach((linha, indiceLinha) => {
    colunas.forEach((coluna, indiceColuna) => {
      const nomeCasa = `${coluna}${linha}`;
      const codigoPeca = posicao[nomeCasa];
      const casa = document.createElement("button");
      const clara = ("abcdefgh".indexOf(coluna) + linha) % 2 === 1;
      casa.type = "button";
      casa.className = `square ${clara ? "light" : "dark"}`;
      casa.dataset.square = nomeCasa;
      casa.setAttribute("aria-label", nomeCasa);

      if (ultimaJogada.includes(nomeCasa)) casa.classList.add("last-move");
      if (selecionada === nomeCasa) casa.classList.add("selected");
      if (destinos.has(nomeCasa)) casa.classList.add("legal-target");
      if (codigoPeca) {
        casa.classList.add("has-piece");
        const peca = document.createElement("span");
        peca.className = "piece";
        peca.textContent = pecas[codigoPeca];
        casa.append(peca);
      }

      if (indiceLinha === 7) {
        const coordenadaColuna = document.createElement("span");
        coordenadaColuna.className = "coordinate file";
        coordenadaColuna.textContent = coluna;
        casa.append(coordenadaColuna);
      }
      if (indiceColuna === 0) {
        const coordenadaLinha = document.createElement("span");
        coordenadaLinha.className = "coordinate rank";
        coordenadaLinha.textContent = linha;
        casa.append(coordenadaLinha);
      }

      casa.addEventListener("click", () => aoSelecionar(nomeCasa, codigoPeca));
      elementos.board.append(casa);
    });
  });
}


function destinosLegais(partida, origem) {
  if (!origem) return new Set();
  return new Set(
    partida.jogadas_legais
      .filter((jogada) => jogada.startsWith(origem))
      .map((jogada) => jogada.slice(2, 4)),
  );
}


export function corDaPeca(codigoPeca) {
  if (!codigoPeca) return null;
  return codigoPeca === codigoPeca.toUpperCase() ? "brancas" : "pretas";
}


export function mostrarPromocao(cor) {
  const simbolos = cor === "brancas" ? ["♕", "♖", "♗", "♘"] : ["♛", "♜", "♝", "♞"];
  elementos.promotionModal.querySelectorAll("button").forEach((botao, indice) => {
    botao.textContent = simbolos[indice];
  });
  elementos.promotionModal.classList.remove("hidden");
}


export function ocultarPromocao() {
  elementos.promotionModal.classList.add("hidden");
}
