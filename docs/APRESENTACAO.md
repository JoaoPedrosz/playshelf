# Roteiro de apresentação — 8 a 10 minutos

## 1. Problema e proposta — 1 minuto

“A PlayShelf é uma loja demonstrativa de jogos em mídia física. O projeto usa Flask para a aplicação e CouchDB para guardar produtos, clientes e pedidos como documentos JSON. O foco é demonstrar modelagem e consistência de estoque, com uma interface agradável para computador e celular.”

Mostre o catálogo, as capas reais e a identificação dos consoles. Explique que preços e compras são simulados.

## 2. Jornada na loja — 2 minutos

1. Filtre Nintendo Switch e consulte um jogo.
2. Adicione à sacola e altere a quantidade.
3. Crie uma conta de demonstração sem dados pessoais reais.
4. Prossiga para o checkout. Alterne entrega padrão/expressa e observe o total.
5. Confirme o pedido simulado e abra o histórico.
6. Explique que o preço vem do servidor, que o estoque diminuiu e que um reenvio do mesmo pedido não faz nova baixa.

## 3. Documentos no Fauxton — 2 minutos

Abra `http://127.0.0.1:5984/_utils/` e entre usando o usuário e a senha do `.env` local. Não mostre a senha na gravação ou nos slides.

1. Abra o banco `playshelf` e um documento `produto:`. Destaque `_id`, `_rev`, `tipo`, preço em centavos e estoque.
2. Abra um `pedido:`. Mostre `cliente_id` como referência e `itens` como conteúdo embutido.
3. Explique o snapshot: alterar o preço do produto não reescreve compras antigas.
4. No menu Mango Query, execute:

```json
{"selector":{"tipo":"produto","ativo":true},"use_index":"catalogo"}
```

5. Mostre os índices e a consulta de plataforma/preço em `PROJETO.md`.

## 4. Conflito e recuperação — 2 minutos

Execute `python scripts/demo_couchdb.py` no ambiente configurado. Abra `docs/evidencias/couchdb.json`:

- `conflito.http = 409`: uma revisão antiga foi rejeitada.
- `consulta_mango.indice_escolhido = plataforma_preco`: a consulta usou o índice pretendido.
- `checkout.mesmo_pedido_ao_repetir = true`: repetição idempotente.
- `replicacao.pedido_preservado = true`: cópia local do documento validada.

O script usa bancos temporários e preserva o banco da loja. Para explicar a falha parcial, desenhe a sequência `PROCESSANDO → COMPENSANDO → CANCELADO`: cada reserva tem seu marcador e só é devolvida uma vez. Os testes também cobrem perda da resposta depois de uma gravação bem-sucedida.

## 5. Testes, segurança e conclusão — 1 a 3 minutos

Mostre `pytest -q`: 17 testes quando a integração está configurada. Destaque a disputa pela última unidade, a privacidade dos pedidos e o bloqueio de POST sem CSRF.

“O checkout tem atomicidade por documento e compensação entre documentos. Não é uma transação ACID de vários produtos. A aplicação está validada localmente; o GitHub será privado e o Render está preparado para a próxima etapa.”

## Evidências para a entrega final

- Tela inicial em computador e celular.
- Sacola, checkout e pedido confirmado com dados fictícios.
- Documento de produto e pedido no Fauxton, sem mostrar credenciais.
- Índices/consulta Mango, conflito 409 e saída dos testes.
- Após o deploy: URL pública e `/healthz`; esse registro ainda está pendente.

Inclua o nome dos integrantes e a turma conforme a orientação do professor. Use `QUESTOES.md` para revisar os conceitos antes da apresentação.
