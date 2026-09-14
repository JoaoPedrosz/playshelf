# GitHub Desktop privado e Render

## Publicar manualmente no GitHub Desktop

1. Abra o GitHub Desktop. Se a PlayShelf ainda não estiver selecionada, use **File → Add local repository** e selecione a pasta `outputs/playshelf` desta entrega.
2. Confira que o repositório atual é **playshelf**. As alterações iniciais já devem estar reunidas em um commit.
3. Clique em **Publish repository**.
4. Use o nome `playshelf`, mantenha **Keep this code private** marcado e selecione sua conta.
5. Clique em **Publish repository** e depois **Repository → View on GitHub** para conferir o selo **Private**.

O `.env`, o banco local e senhas ficam fora do repositório. O projeto não deve ser adicionado por engano ao repositório de outro trabalho. Se o professor precisar acessar, compartilhe o acesso privado com a conta que ele informar.

## Deploy futuro no Render

O arquivo `render.yaml` descreve dois serviços:

- **playshelf:** Flask servido por Waitress, com HTTPS oferecido pelo Render e health check em `/healthz`.
- **playshelf-db:** CouchDB em serviço privado, com disco persistente em `/opt/couchdb/data`.

Os serviços estão configurados no plano `starter`. **Revise os custos atuais antes de criar o Blueprint:** o serviço privado e o disco persistente não constituem um deploy totalmente gratuito. Um sistema de arquivos efêmero perderia os pedidos em reinícios/redeploys. [Discos persistentes do Render](https://render.com/docs/disks).

### Passo a passo

1. Publique o repositório privado e confira se o workflow de testes terminou com sucesso.
2. Entre no Render e conecte o GitHub, autorizando o acesso ao repositório `playshelf`.
3. Crie um **Blueprint** a partir desse repositório e da branch `main`.
4. Revise os dois serviços, a mesma região, o disco e os custos apresentados antes de confirmar a criação.
5. O Blueprint gera `SECRET_KEY` e `COUCHDB_PASSWORD`, compartilha a senha entre os serviços por referência e injeta o host privado do banco. Não publique esses valores.
6. Aguarde o banco ficar pronto e a web inicializar o catálogo. Se a primeira inicialização da web ocorrer antes do banco, reinicie o deploy da web depois que o banco estiver saudável.
7. Abra a URL pública da web. Confira `/healthz`, catálogo, cadastro e um pedido simulado.
8. Reinicie a web e confirme que o pedido continua no histórico. Registre a URL e o resultado como evidência de deploy.

O comando de início executa `flask --app app init-db` e depois o Waitress na porta `$PORT`. A inicialização preserva documentos existentes. `COOKIE_SECURE=true` exige HTTPS na URL usada pelo cliente. O banco é privado; não publique a porta 5984 nem o Fauxton na internet.

O endereço privado vem da propriedade `host` do serviço de banco. Caso um nome/região seja alterado, mantenha as referências de serviço consistentes. [Especificação de Blueprints](https://render.com/docs/blueprint-spec), [serviços privados](https://render.com/docs/private-services) e [Flask no Render](https://render.com/docs/deploy-flask).

## Antes de uma operação comercial

Separar usuário administrativo e usuário de aplicação, configurar backup com restauração testada, supervisão dos pedidos pendentes e proteção contra tentativas repetidas de login. O MVP não processa pagamentos nem despacha produtos.

## Estado atual

Configuração entregue e testada localmente. A publicação manual e a criação dos serviços no Render ainda não foram executadas nesta entrega.
