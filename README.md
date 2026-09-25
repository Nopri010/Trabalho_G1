# ChessSocket

Jogo de xadrez multiplayer em tempo real desenvolvido para a disciplina de
Computação Distribuída. O servidor usa Python e Tornado, mantém o estado global
das partidas e valida todas as jogadas. O cliente usa HTML, CSS e JavaScript e
troca mensagens com o servidor por WebSocket.

## Relação com o conteúdo da disciplina

O projeto segue a base apresentada em aula:

- `tornado.web.Application` publica a interface e o endpoint `/ws`;
- `WebSocketHandler` representa uma conexão persistente com cada jogador;
- parâmetros da URL identificam a ação, o jogador e a sala no handshake;
- dicionários em memória isolam as conexões e o estado de cada sala;
- `asyncio.Lock` protege o tabuleiro contra alterações concorrentes;
- mensagens em JSON formam um protocolo explícito entre Python e JavaScript;
- `dataclass`, type hints e logging organizam o código do servidor.

## Arquitetura

```text
Navegador A ─┐                 ┌─ Sala ABCDE (tabuleiro + jogadores)
             ├─ WebSocket ─────┤
Navegador B ─┘                 └─ Regras e estado no servidor Python
```

O cliente envia somente intenções, como `e2` → `e4`. O servidor confere a sala,
a identidade do jogador, o turno e a legalidade do movimento antes de alterar o
tabuleiro e publicar o novo estado aos dois participantes.

Ao entrar em uma sala, cada jogador recebe um token aleatório que fica no
`sessionStorage` da aba. Se a página for atualizada, o cliente usa esse token
para voltar à mesma cor e posição. O servidor espera oito segundos pela volta;
quando a aba é fechada e não retorna, a desconexão encerra a partida normalmente.

## Como executar com UV

Requer Python 3.11 ou superior e [UV](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python main.py
```

Depois, abra [http://localhost:8080](http://localhost:8080) em duas abas. Crie
uma sala na primeira, copie o código e entre nela pela segunda.

### Alternativa com `venv` e `pip`

```bash
python -m venv .venv
```

No Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

No Linux ou macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Protocolo WebSocket

O handshake transporta os dados necessários para criar ou entrar em uma sala:

```text
ws://localhost:8080/ws?acao=criar&nome=Ana
ws://localhost:8080/ws?acao=entrar&nome=Bruno&sala=ABCDE
ws://localhost:8080/ws?acao=reconectar&sala=ABCDE
```

Depois do handshake, todas as mensagens usam JSON.

### Cliente para servidor

```json
{ "tipo": "jogada", "origem": "e2", "destino": "e4" }
```

```json
{ "tipo": "jogada", "origem": "a7", "destino": "a8", "promocao": "q" }
```

```json
{ "tipo": "desistir" }
```

```json
{ "tipo": "reconectar", "token": "token-da-sessao" }
```

### Servidor para cliente

- `sessao_iniciada`: informa código da sala, cor e token do jogador;
- `estado_partida`: publica FEN, jogadores, turno, jogadas legais e resultado;
- `erro`: rejeita mensagens ou jogadas inválidas sem alterar o tabuleiro;
- `pong`: resposta opcional à mensagem `ping`.

## Estrutura

```text
ChessSocket/
├── clientes/web/
│   ├── app.js
│   ├── index.html
│   ├── style.css
│   ├── ui.js
│   └── websocket.js
├── jogo.py           # estado e regras de xadrez
├── servidor.py       # salas, concorrência e WebSockets
├── protocolo.py      # codificação e validação das mensagens
├── logger.py
└── main.py
```
