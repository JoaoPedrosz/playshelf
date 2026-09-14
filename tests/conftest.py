import copy
import os
import threading
import uuid

import pytest

from playshelf import create_app
from playshelf.catalog import seed_products
from playshelf.db import Conflict, CouchDB, NotFound


class MemoryRepository:
    """Test double only; production always uses CouchDB."""
    update = CouchDB.update

    def __init__(self):
        self.docs = {}
        self.lock = threading.Lock()
        for p in seed_products():
            self.put(p)

    def get(self, doc_id):
        with self.lock:
            if doc_id not in self.docs:
                raise NotFound()
            return copy.deepcopy(self.docs[doc_id])

    def put(self, doc):
        with self.lock:
            old = self.docs.get(doc['_id'])
            if old and old['_rev'] != doc.get('_rev'):
                raise Conflict()
            saved = dict(copy.deepcopy(doc), _rev=str(int(old['_rev'])+1 if old else 1))
            self.docs[doc['_id']] = saved
            return copy.deepcopy(saved)

    def find(self, selector, index=None):
        with self.lock:
            return [copy.deepcopy(d) for d in self.docs.values() if all(d.get(k) == v for k,v in selector.items())]


@pytest.fixture
def db():
    return MemoryRepository()


@pytest.fixture
def app(db):
    return create_app({'TESTING': True, 'SECRET_KEY': 'unit-test-only'}, repository=db)


@pytest.fixture
def client(app):
    client = app.test_client()
    client.get('/')
    return client


def form(client, data=None):
    with client.session_transaction() as s:
        needs_token = 'csrf' not in s
    if needs_token:
        client.get('/login')
    with client.session_transaction() as s:
        token = s['csrf']
    return dict(data or {}, csrf_token=token)


@pytest.fixture
def real_db():
    endpoint = os.getenv('COUCHDB_TEST_URL')
    if not endpoint:
        pytest.skip('Set COUCHDB_TEST_URL to run against a real CouchDB')
    name = 'playshelf_test_' + uuid.uuid4().hex
    db = CouchDB(endpoint, name, os.getenv('COUCHDB_TEST_USER','admin'), os.getenv('COUCHDB_TEST_PASSWORD',''))
    db.initialize(seed_products())
    try:
        yield db
    finally:
        # Delete only the temporary test database created by this fixture.
        assert name.startswith('playshelf_test_')
        db.request('DELETE')
