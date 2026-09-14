# Dez questões — roteiro de estudo

Respostas aplicadas à PlayShelf para compreender e apresentar o trabalho. Os números correspondem às questões do enunciado.

## 1. Justifique CouchDB para o projeto

O acesso mais comum é ler produtos ou um pedido com todos os seus itens. O modelo documental permite representar esses agregados diretamente em JSON. A API HTTP integra o banco à aplicação Flask e o controle por revisões torna visível o tratamento de concorrência. Replicação é outro recurso relevante. Em contrapartida, joins, integridade entre documentos e checkout com vários produtos exigem lógica adicional; CouchDB não é automaticamente superior a SQL.

## 2. Compare documento e tabela

Em um modelo relacional, cliente, pedido e item geralmente estão em tabelas relacionadas por chaves, com consultas e restrições controladas pelo banco. Um documento pode reunir campos e listas aninhadas, como os itens de uma compra, reduzindo leituras para esse acesso. Documentos admitem formatos diferentes, mas a aplicação continua precisando validar tipos, campos obrigatórios e versões. Flexibilidade de estrutura não elimina modelagem.

## 3. Analise embed versus reference

Embed guarda dados dentro do documento principal: os itens do pedido incluem nome e preço daquela compra, permitindo leitura completa e preservação histórica. Reference armazena o ID de outra entidade: `cliente_id` identifica o titular e `produto_id` aponta ao produto. A PlayShelf combina as duas estratégias: referencia a entidade atual e copia os valores que não devem mudar no histórico. Evita copiar o cadastro e a senha do cliente nos pedidos.

## 4. Explique `_id`, `_rev` e `tipo`

`_id` é a identidade única do documento no banco. `_rev` é um token de revisão usado para detectar alterações concorrentes; não deve ser tratado como um sistema de histórico permanente. `tipo` é uma convenção criada na aplicação para distinguir produto, cliente e pedido em um mesmo banco. O CouchDB conhece os dois primeiros; o significado de `tipo` vem do nosso modelo.

## 5. Explique Mango e índices

Mango permite consultar documentos usando seletores JSON e operadores como `$lte`. Índices reduzem o trabalho de percorrer documentos quando correspondem aos campos e às condições da consulta. A PlayShelf indexa catálogo ativo, plataforma/preço e pedidos por cliente/status. `_explain` mostra o índice selecionado: o relatório demonstra uma consulta de jogos PS5 até R$ 250 com `plataforma_preco`.

## 6. Por que `_bulk_docs` não é ACID para um conjunto de documentos?

Uma chamada em lote pode gravar um documento e falhar em outro. Não existe confirmação ou rollback único que torne o lote inteiro uma transação. É necessário verificar cada resultado e planejar repetição/compensação. Por isso, o checkout não supõe que enviar pedido e produtos juntos garantiria consistência. [Referência oficial](https://docs.couchdb.org/en/stable/api/database/bulk-api.html).

## 7. Como tratar HTTP 409?

Ao tentar gravar uma revisão antiga, a aplicação deve reler o documento e reavaliar a operação sobre os valores atuais. No estoque, isso significa verificar novamente a quantidade disponível antes de tentar o PUT com o novo `_rev`. Não basta trocar a revisão e sobrescrever o documento antigo: isso perderia alterações. O repositório limita as tentativas a seis e propaga a falha caso a disputa continue.

## 8. Proponha compensação de checkout

Primeiro persistir um pedido pendente; depois reservar cada produto, gravando no próprio documento o movimento associado ao pedido. Se uma reserva falhar, identificar quais movimentos foram efetivados e devolvê-los uma única vez. A PlayShelf marca o processo como `COMPENSANDO` e então `CANCELADO`. O marcador de devolução evita crédito duplicado. Se a confirmação já foi gravada mas a resposta se perdeu, a leitura do pedido detecta isso e impede uma devolução indevida.

## 9. Explique replicação

É a transferência incremental de alterações entre bancos CouchDB, em uma direção por operação; pode ser pontual ou contínua. Sincronização nos dois sentidos envolve fluxos em ambas as direções e pode produzir conflitos se o mesmo documento for alterado independentemente. O projeto demonstrou replicação local entre dois bancos. Para tolerar perda de máquina, o destino teria de estar em outra instância e seria necessário testar recuperação. [Referência oficial](https://docs.couchdb.org/en/stable/replication/intro.html).

## 10. Liste controles de segurança em cloud

HTTPS na web; banco em rede privada; segredos em variáveis protegidas; autenticação e autorização; usuário de banco com privilégios mínimos; hash de senha; CSRF; cookies seguros; validação de entradas; dependências atualizadas; limitação de tentativas de login; logs sem segredos; backups e restauração ensaiada. A PlayShelf já implementa vários controles de aplicação, mas ainda precisa de limitação de login, usuário de banco restrito e operação de backup antes de uso comercial.
