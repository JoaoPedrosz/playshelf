# Evidências da execução

## Ambiente

- Windows, Python 3.12 e Apache CouchDB **3.5.2 real**.
- Banco local acessado por HTTP autenticado; não houve substituição por armazenamento em memória na aplicação.
- Interface verificada no navegador do Codex; o teste automatizado usa um repositório em memória somente nos casos unitários, além de dois casos no banco real.

## Resultados disponíveis

| Arquivo | O que comprova |
|---|---|
| `couchdb.json` | Conflito 409, mudança de `_rev`, consulta e índice Mango, checkout idempotente e replicação local |
| `testes.xml` | Resultado JUnit da suíte de testes executada |
| `revisao-interface.md` | Revisão visual e fluxo exercitado no navegador |

A replicação foi entre dois bancos da mesma instância, em ambiente temporário. O resultado não é prova de alta disponibilidade entre servidores. O script remove somente os bancos temporários da demonstração.

O deploy online no Render ainda não foi realizado; nenhuma captura ou resultado de produção foi inventado.
