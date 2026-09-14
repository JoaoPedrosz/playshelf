import concurrent.futures
import hashlib

import pytest

from conftest import form
from playshelf.db import Conflict, DatabaseError
from playshelf.orders import ShopError, checkout, move_stock, recover_order, total_shipping

PID = 'produto:zelda-tears-switch'


def register(client, email='player@example.test'):
    return client.post('/cadastro', data=form(client, {'nome':'Player Teste','email':email,'senha':'test-password-123'}))


def test_catalog_filters_and_detail(client):
    home = client.get('/').get_data(as_text=True)
    assert home.count('class="product-card"') == 12
    filtered = client.get('/?console=ps5&q=elden').get_data(as_text=True)
    assert filtered.count('class="product-card"') == 1
    assert 'Elden Ring' in filtered
    assert client.get('/jogo/zelda-tears-switch').status_code == 200
    assert client.get('/jogo/inexistente').status_code == 404


def test_empty_states_and_csrf(client):
    assert client.get('/carrinho').status_code == 200
    assert client.get('/?q=zzzzzz').status_code == 200
    assert client.get('/login').status_code == 200
    assert client.post('/carrinho/adicionar/zelda-tears-switch').status_code == 400
    assert client.get('/checkout').status_code == 302


def test_account_hash_uniqueness_and_login(client, db):
    assert register(client).status_code == 302
    cid = 'cliente:' + hashlib.sha256(b'player@example.test').hexdigest()
    doc = db.get(cid)
    assert doc['senha_hash'] != 'test-password-123'
    assert 'senha' not in doc
    assert register(client, 'PLAYER@example.test').status_code == 409
    client.post('/sair', data=form(client))
    client.get('/login')
    assert client.post('/login', data=form(client, {'email':'player@example.test','senha':'wrong'})).status_code == 401
    assert client.post('/login', data=form(client, {'email':'player@example.test','senha':'test-password-123'})).status_code == 302


def test_cart_quantity_and_removal(client, db):
    assert client.post('/carrinho/adicionar/zelda-tears-switch', data=form(client)).status_code == 302
    assert client.post('/carrinho/alterar/zelda-tears-switch', data=form(client, {'quantidade':-1})).status_code == 400
    client.post('/carrinho/alterar/zelda-tears-switch', data=form(client, {'quantidade':99}))
    with client.session_transaction() as session:
        assert session['carrinho'][PID] == 1
    client.post('/carrinho/alterar/zelda-tears-switch', data=form(client, {'quantidade':0}))
    with client.session_transaction() as session:
        assert session['carrinho'] == {}


def test_checkout_route_and_order_access(client, db, app):
    register(client)
    client.get('/')
    client.post('/carrinho/adicionar/zelda-tears-switch', data=form(client))
    assert client.get('/checkout').status_code == 200
    with client.session_transaction() as s:
        token = s['checkout_token']
    data = form(client, {'checkout_token':token,'entrega':'expresso','total':'1'})
    response = client.post('/checkout', data=data)
    assert response.status_code == 302
    assert client.get(response.location).status_code == 200
    assert client.post('/checkout', data=data).location == response.location
    orders = db.find({'tipo':'pedido'})
    assert len(orders) == 1
    assert orders[0]['total_centavos'] == 32980
    assert db.get(PID)['estoque'] == 11
    other = app.test_client()
    other.get('/')
    register(other, 'other@example.test')
    assert other.get(response.location).status_code == 404


def test_snapshot_and_idempotency(db):
    order = checkout(db, 'cliente:test', {PID:2}, 'token', 'padrao')
    db.update(PID, lambda p: dict(p, preco_centavos=1, nome='Alterado'))
    replay = checkout(db, 'cliente:test', {}, 'token', 'padrao')
    assert replay['_id'] == order['_id']
    assert replay['total_centavos'] == 59980
    assert replay['itens'][0]['nome'] != 'Alterado'
    assert db.get(PID)['estoque'] == 10


def test_conflict_and_concurrent_last_unit(db):
    old = db.get(PID)
    db.update(PID, lambda d: dict(d, estoque=1))
    with pytest.raises(Conflict):
        db.put(old)
    def buy(i):
        try:
            return checkout(db, 'cliente:test', {PID:1}, f'concurrent-{i}', 'padrao')['status']
        except ShopError:
            return 'SEM_ESTOQUE'
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(buy, range(2)))
    assert outcomes.count('CONFIRMADO') == 1
    assert db.get(PID)['estoque'] == 0


def test_partial_failure_compensates_and_is_repeatable(db, monkeypatch):
    second = 'produto:mario-wonder-switch'
    original_put = db.put
    failed = False
    def put(doc):
        nonlocal failed
        if doc['_id'] == PID and doc.get('movimentos') and not failed:
            failed = True
            raise DatabaseError('Injected failure')
        return original_put(doc)
    monkeypatch.setattr(db, 'put', put)
    order = checkout(db, 'cliente:test', {PID:1, second:1}, 'failure', 'padrao')
    assert order['status'] == 'CANCELADO'
    assert db.get(second)['estoque'] == 18
    assert db.get(PID)['estoque'] == 12
    assert recover_order(db, order['_id'])['status'] == 'CANCELADO'
    assert db.get(second)['estoque'] == 18


def test_lost_reservation_response_is_compensated(db, monkeypatch):
    original_put = db.put
    failed = False
    def put(doc):
        nonlocal failed
        result = original_put(doc)
        if doc['_id'] == PID and doc.get('movimentos') and not failed:
            failed = True
            raise DatabaseError('Response lost after successful PUT')
        return result
    monkeypatch.setattr(db,'put',put)
    order = checkout(db, 'cliente:test', {PID:1}, 'lost-stock-response', 'padrao')
    assert order['status'] == 'CANCELADO'
    assert db.get(PID)['estoque'] == 12


def test_lost_confirmation_response_does_not_refund(db, monkeypatch):
    original_put = db.put
    failed = False
    def put(doc):
        nonlocal failed
        result = original_put(doc)
        if doc.get('status') == 'CONFIRMADO' and not failed:
            failed = True
            raise DatabaseError('Confirmation response lost')
        return result
    monkeypatch.setattr(db, 'put', put)
    order = checkout(db, 'cliente:test', {PID:1}, 'lost-confirm', 'padrao')
    assert order['status'] == 'CONFIRMADO'
    assert db.get(PID)['estoque'] == 11


def test_recovery_after_interruption_is_idempotent(db):
    order_id = 'pedido:interrupted'
    db.put({'_id':order_id,'tipo':'pedido','status':'PROCESSANDO','itens':[{'produto_id':PID,'quantidade':1}]})
    move_stock(db, PID, order_id, 1)
    assert db.get(PID)['estoque'] == 11
    assert recover_order(db, order_id)['status'] == 'CANCELADO'
    assert recover_order(db, order_id)['status'] == 'CANCELADO'
    assert db.get(PID)['estoque'] == 12


@pytest.mark.parametrize('subtotal,kind,expected',[(39899,'padrao',1490),(39900,'padrao',0),(39900,'expresso',2990)])
def test_shipping_boundary(subtotal, kind, expected):
    assert total_shipping(subtotal, kind) == expected


def test_invalid_inputs_and_headers(client):
    assert client.post('/cadastro', data=form(client, {'nome':'x','email':'invalid','senha':'short'})).status_code == 400
    with pytest.raises(ShopError):
        total_shipping(30000, 'free-hack')
    response = client.get('/')
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.integration
def test_real_couchdb_revision_indexes_checkout(real_db):
    p = real_db.get(PID)
    changed = real_db.put(dict(p, estoque=2))
    assert changed['_rev'] != p['_rev']
    with pytest.raises(Conflict):
        real_db.put(p)
    assert len(real_db.find({'tipo':'produto','ativo':True}, 'catalogo')) == 12
    indexes = real_db.request('GET', '/_index')['indexes']
    assert {'catalogo','plataforma_preco','pedidos_cliente'} <= {i['name'] for i in indexes}
    order = checkout(real_db, 'cliente:integration', {PID:1}, 'integration-token', 'padrao')
    assert order['status'] == 'CONFIRMADO'
    assert real_db.get(PID)['estoque'] == 1
    assert checkout(real_db, 'cliente:integration', {PID:1}, 'integration-token', 'padrao')['_id'] == order['_id']


@pytest.mark.integration
def test_real_couchdb_concurrent_checkouts(real_db):
    real_db.update(PID, lambda d: dict(d, estoque=1))
    def buy(i):
        try:
            return checkout(real_db, f'cliente:{i}', {PID:1}, f'last-{i}', 'padrao')['status']
        except ShopError:
            return 'SEM_ESTOQUE'
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(buy, range(2)))
    assert outcomes.count('CONFIRMADO') == 1
    assert real_db.get(PID)['estoque'] == 0
