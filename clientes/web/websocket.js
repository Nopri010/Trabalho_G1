let conexao = null;


export function conectar(parametros, eventos) {
  const esquema = window.location.protocol === "https:" ? "wss" : "ws";
  const busca = new URLSearchParams(parametros);
  conexao = new WebSocket(`${esquema}://${window.location.host}/ws?${busca}`);

  conexao.onopen = () => eventos.aoAbrir();
  conexao.onmessage = (evento) => {
    try {
      eventos.aoReceber(JSON.parse(evento.data));
    } catch (erro) {
      console.error("Mensagem inválida recebida do servidor", erro);
    }
  };
  conexao.onclose = (evento) => eventos.aoFechar(evento);
  conexao.onerror = () => eventos.aoFalhar();
}


export function enviarMensagem(tipo, dados = {}) {
  if (!conexao || conexao.readyState !== WebSocket.OPEN) {
    return false;
  }
  conexao.send(JSON.stringify({ tipo, ...dados }));
  return true;
}
