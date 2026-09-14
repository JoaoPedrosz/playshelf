# PlayShelf 🎮

**O próximo capítulo da sua coleção.** Loja acadêmica de jogos em mídia física, com identidade clara, detalhes vermelhos e capas reais consultadas pela API pública da Wikipedia. Interface em português para celular e computador.

Projeto da disciplina TAI/FACAMP: **Python + Flask + Apache CouchDB**, persistência documental via REST, consultas Mango, revisões e checkout recuperável. Compras, preços, estoque e frete são simulados; nenhum pagamento ou envio é realizado.

## O que funciona

- Catálogo com 12 jogos de Nintendo Switch, PlayStation 5 e Xbox, busca por nome/gênero, filtros e ordenação.
- Página de jogo com plataforma, condição, estoque e indicação de mídia física.
- Sacola com alteração de quantidade e remoção.
- Cadastro, login, logout e histórico individual de pedidos.
- Checkout com frete padrão/expresso, preços conferidos no servidor e baixa de estoque.
- Proteção contra pedido duplicado, conflito de estoque e compensação de reservas parciais.
- Capas obtidas por API, links de origem e alternativa visual quando uma imagem falha.
- Testes automatizados, demonstração do banco, Docker e configuração futura do Render.

## Comece por aqui

| Material | Conteúdo |
|---|---|
| [Projeto e modelagem](docs/PROJETO.md) | Requisitos, documentos JSON, decisões, índices, segurança e limites |
| [Roteiro de apresentação](docs/APRESENTACAO.md) | Demonstração da loja e atividades no Fauxton |
| [Questões dissertativas](docs/QUESTOES.md) | Dez respostas para estudar e adaptar à apresentação |
| [GitHub Desktop e Render](docs/PUBLICACAO.md) | Publicação privada manual e próximo deploy |
| [Evidências](docs/evidencias/README.md) | Resultados realmente executados |

## Executar em outro computador

Pré-requisitos: Python 3.12, Docker com Compose e Git. O Docker é usado somente para o CouchDB. Se você já tem CouchDB 3.x, configure sua URL no `.env` e dispense a etapa Docker.

Na pasta do projeto, usando PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edite `.env`: escolha uma senha forte para `COUCHDB_PASSWORD` e uma chave aleatória para `SECRET_KEY`. Gere uma chave com:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

O `.env` nunca deve entrar no GitHub. Em seguida:

```powershell
docker compose up -d --wait
.\.venv\Scripts\python.exe -m flask --app app init-db
.\.venv\Scripts\python.exe app.py
```

Abra **http://127.0.0.1:5000**. Crie sua conta na própria loja. O Fauxton fica em **http://127.0.0.1:5984/_utils/**; entre com o usuário e a senha do `.env`. Essa conta administrativa é diferente da conta de cliente da loja.

O comando `init-db` cria banco, índices e produtos ausentes; **preserva produtos, estoque e pedidos já existentes**. Para encerrar a loja, pressione Ctrl+C. `docker compose stop` interrompe o banco preservando seu volume. Não use `down -v` se quiser guardar os dados.

### Ambiente preparado neste computador

A entrega inclui, um nível acima desta pasta, `Abrir PlayShelf.cmd`, que abre a prévia em **http://127.0.0.1:5001** e inicia os componentes locais quando necessário. Essa conveniência depende da pasta `work` desta sessão. O repositório e o ZIP são independentes dela e usam as instruções reproduzíveis acima. O CouchDB local foi extraído da distribuição oficial do Windows, sem instalação de serviço do sistema.

## Atualizar capas pela API

```powershell
.\.venv\Scripts\python.exe scripts/sync_covers.py
.\.venv\Scripts\python.exe -m flask --app app sync-covers
```

A primeira etapa consulta `https://en.wikipedia.org/api/rest_v1/page/summary/{titulo}` e salva URLs/origens em `data/covers.json`. A segunda atualiza esses campos nos documentos do banco. A página da loja usa os links em cache: uma falha da API não interrompe a venda simulada. As imagens ainda precisam de internet para carregar. Os textos descritivos são próprios; as capas e marcas pertencem aos respectivos titulares e não são distribuídas no repositório.

## Testar

Testes de regras e rotas (sem banco externo):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Para incluir os testes de integração, use o mesmo usuário/senha do banco de desenvolvimento:

```powershell
$env:COUCHDB_TEST_URL = 'http://127.0.0.1:5984'
$env:COUCHDB_TEST_USER = 'seu-usuario-local'
$env:COUCHDB_TEST_PASSWORD = 'sua-senha-local'
.\.venv\Scripts\python.exe -m pytest -q
```

Sem essas variáveis, os dois testes de integração aparecem como ignorados. Com elas, **17 testes** são executados. Os testes de integração criam bancos temporários exclusivos e apagam somente esses bancos ao terminar. Não aponte uma rotina de testes para uma instalação de produção.

Para gerar novamente a evidência de `_rev`, índice escolhido, checkout e replicação:

```powershell
.\.venv\Scripts\python.exe scripts/demo_couchdb.py
```

## Organização

```text
app.py                 entrada da aplicação
playshelf/             rotas, acesso REST, catálogo e checkout
data/                  produtos iniciais e metadados das capas
templates/ e static/   interface, estilos, ícones e interações
tests/                 regras, rotas e integração com CouchDB
scripts/               capas e demonstração documental
docs/                  material acadêmico e evidências
deploy/                configuração do CouchDB
render.yaml            Blueprint para o deploy futuro
```

## Estado da entrega

Aplicação e banco verificados localmente. Publicação no GitHub reservada ao usuário pelo GitHub Desktop, em repositório privado. Render preparado, **ainda não implantado**. O Blueprint utiliza serviço privado e disco persistente, que exigem revisar os planos e custos no Render antes de ativar.

Este é um MVP acadêmico. Os [limites e melhorias](docs/PROJETO.md#limites-do-mvp) descrevem o que falta para uma operação comercial.
