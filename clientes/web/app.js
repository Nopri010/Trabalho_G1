import { conectar, enviarMensagem } from "./websocket.js";
import {
  atualizarConexao,
  bloquearLobby,
  corDaPeca,
  elementos,
  mostrarMensagemLobby,
  mostrarMensagemTabuleiro,
  mostrarPromocao,
  ocultarPromocao,
  abrirPartida,
  abrirLobby,
  renderizarPartida,
} from "./ui.js";

const CHAVE_SESSAO = "chesssocket.sessao";

const aplicacao = {
  sessao: null,
  partida: null,
  casaSelecionada: null,
  promocaoPendente: null,
  reconectando: false,
};


function salvarSessao(sessao) {
  sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao));
}


function carregarSessao() {
  try {
    const sessao = JSON.parse(sessionStorage.getItem(CHAVE_SESSAO));
    if (
      typeof sessao?.codigoSala === "string" &&
      typeof sessao?.cor === "string" &&
      typeof sessao?.nome === "string" &&
      typeof sessao?.token === "string"
    ) {
      return sessao;
    }
  } catch {
    // Uma sessão inválida não deve impedir a abertura da página inicial.
  }
  sessionStorage.removeItem(CHAVE_SESSAO);
  return null;
}


function esquecerSessao(mensagem = "") {
  sessionStorage.removeItem(CHAVE_SESSAO);
  aplicacao.sessao = null;
  aplicacao.partida = null;
  aplicacao.reconectando = false;
  abrirLobby();
  bloquearLobby(false);
  mostrarMensagemLobby(mensagem);
}


function iniciarConexao(acao) {
  const nome = elementos.playerName.value.trim();
  const codigoSala = elementos.roomCode.value.trim().toUpperCase();
  if (nome.length < 2) {
    mostrarMensagemLobby("Informe um nome com pelo menos 2 caracteres.");
    return;
  }
  if (acao === "entrar" && codigoSala.length !== 5) {
    mostrarMensagemLobby("Informe o código de 5 caracteres da sala.");
    return;
  }

  bloquearLobby(true);
  mostrarMensagemLobby("");
  atualizarConexao("connecting", "Abrindo WebSocket...");
  const parametros = { acao, nome };
  if (acao === "entrar") parametros.sala = codigoSala;

  conectar(parametros, {
    aoAbrir: () => atualizarConexao("online", "WebSocket conectado"),
    aoReceber: tratarMensagem,
    aoFechar: tratarDesconexao,
    aoFalhar: () => mostrarMensagemLobby("Não foi possível conectar ao servidor Python."),
  });
}


function reconectar(sessao) {
  aplicacao.sessao = sessao;
  aplicacao.reconectando = true;
  elementos.playerName.value = sessao.nome;
  abrirPartida(sessao);
  atualizarConexao("connecting", "Recuperando partida...");
  elementos.gameStatus.textContent = "Reconectando...";

  conectar(
    { acao: "reconectar", sala: sessao.codigoSala },
    {
      aoAbrir: () => {
        atualizarConexao("online", "WebSocket conectado");
        enviarMensagem("reconectar", { token: sessao.token });
      },
      aoReceber: tratarMensagem,
      aoFechar: tratarDesconexao,
      aoFalhar: () => mostrarMensagemTabuleiro("Não foi possível reconectar ao servidor."),
    },
  );
}


function tratarMensagem(mensagem) {
  if (mensagem.tipo === "sessao_iniciada") {
    aplicacao.sessao = {
      codigoSala: mensagem.codigo_sala,
      cor: mensagem.cor,
      nome: mensagem.nome || elementos.playerName.value.trim(),
      token: mensagem.token,
    };
    aplicacao.reconectando = false;
    salvarSessao(aplicacao.sessao);
    abrirPartida(aplicacao.sessao);
    return;
  }

  if (mensagem.tipo === "estado_partida") {
    aplicacao.partida = mensagem;
    aplicacao.casaSelecionada = null;
    mostrarMensagemTabuleiro("");
    atualizarTela();
    return;
  }

  if (mensagem.tipo === "erro") {
    if (aplicacao.reconectando) {
      esquecerSessao(mensagem.mensagem);
      return;
    }
    if (aplicacao.sessao) {
      mostrarMensagemTabuleiro(mensagem.mensagem);
    } else {
      mostrarMensagemLobby(mensagem.mensagem);
    }
  }
}


function tratarDesconexao(evento) {
  atualizarConexao("offline", "WebSocket desconectado");
  elementos.resign.disabled = true;
  if (aplicacao.sessao) {
    if (evento.code === 4000) return;
    elementos.gameStatus.textContent = "Conexão encerrada";
    mostrarMensagemTabuleiro("Atualize a página para recuperar a partida.");
  } else {
    bloquearLobby(false);
  }
}


function atualizarTela() {
  if (!aplicacao.partida || !aplicacao.sessao) return;
  renderizarPartida(
    aplicacao.partida,
    aplicacao.sessao,
    aplicacao.casaSelecionada,
    selecionarCasa,
  );
}


function selecionarCasa(nomeCasa, codigoPeca) {
  const partida = aplicacao.partida;
  const sessao = aplicacao.sessao;
  if (
    partida.estado !== "ativa" ||
    partida.turno !== sessao.cor ||
    partida.jogadas_legais.length === 0
  ) {
    return;
  }

  if (aplicacao.casaSelecionada) {
    if (aplicacao.casaSelecionada === nomeCasa) {
      aplicacao.casaSelecionada = null;
      atualizarTela();
      return;
    }

    const candidatas = partida.jogadas_legais.filter(
      (jogada) =>
        jogada.startsWith(aplicacao.casaSelecionada) && jogada.slice(2, 4) === nomeCasa,
    );
    if (candidatas.length > 0) {
      const origem = aplicacao.casaSelecionada;
      aplicacao.casaSelecionada = null;
      if (candidatas.some((jogada) => jogada.length === 5)) {
        aplicacao.promocaoPendente = { origem, destino: nomeCasa };
        mostrarPromocao(sessao.cor);
      } else {
        enviarJogada(origem, nomeCasa);
      }
      atualizarTela();
      return;
    }
  }

  const possuiJogada = partida.jogadas_legais.some((jogada) => jogada.startsWith(nomeCasa));
  if (corDaPeca(codigoPeca) === sessao.cor && possuiJogada) {
    aplicacao.casaSelecionada = nomeCasa;
  } else {
    aplicacao.casaSelecionada = null;
  }
  atualizarTela();
}


function enviarJogada(origem, destino, promocao = null) {
  const dados = { origem, destino };
  if (promocao) dados.promocao = promocao;
  if (!enviarMensagem("jogada", dados)) {
    mostrarMensagemTabuleiro("A conexão com o servidor não está disponível.");
  }
}


elementos.createRoom.addEventListener("click", () => iniciarConexao("criar"));
elementos.joinRoom.addEventListener("click", () => iniciarConexao("entrar"));
elementos.roomCode.addEventListener("input", () => {
  elementos.roomCode.value = elementos.roomCode.value
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "");
});
elementos.roomCode.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter") iniciarConexao("entrar");
});
elementos.playerName.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !elementos.roomCode.value) iniciarConexao("criar");
});
elementos.copyRoomCode.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(aplicacao.sessao.codigoSala);
    elementos.copyRoomCode.querySelector("small").textContent = "copiado!";
    window.setTimeout(() => {
      elementos.copyRoomCode.querySelector("small").textContent = "copiar";
    }, 1400);
  } catch {
    mostrarMensagemTabuleiro("Não foi possível copiar o código automaticamente.");
  }
});
elementos.resign.addEventListener("click", () => {
  if (window.confirm("Deseja realmente desistir da partida?")) {
    enviarMensagem("desistir");
  }
});
elementos.newGame.addEventListener("click", () => {
  sessionStorage.removeItem(CHAVE_SESSAO);
  window.location.assign("/");
});
elementos.promotionModal.querySelectorAll("button").forEach((botao) => {
  botao.addEventListener("click", () => {
    const pendente = aplicacao.promocaoPendente;
    if (!pendente) return;
    enviarJogada(pendente.origem, pendente.destino, botao.dataset.promotion);
    aplicacao.promocaoPendente = null;
    ocultarPromocao();
  });
});

const sessaoSalva = carregarSessao();
if (sessaoSalva) reconectar(sessaoSalva);
