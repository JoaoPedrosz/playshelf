"""Small HTTP repository. All application data is persisted in Apache CouchDB."""
import copy
import re
from urllib.parse import quote

import requests


class DatabaseError(Exception):
    pass


class Conflict(DatabaseError):
    pass


class NotFound(DatabaseError):
    pass


class CouchDB:
    def __init__(self, url, database, user, password):
        if not re.fullmatch(r"[a-z][a-z0-9_$()+/-]*", database):
            raise ValueError("Nome de banco inválido")
        self.base = url.rstrip("/")
        self.url = f"{self.base}/{quote(database, safe='')}"
        self.auth = (user, password)

    def request(self, method, path="", *, root=False, **kwargs):
        try:
            response = requests.request(method, (self.base if root else self.url) + path,
                                        auth=self.auth, timeout=(4, 15), **kwargs)
        except requests.RequestException as exc:
            raise DatabaseError("O banco está temporariamente indisponível.") from exc
        if response.status_code == 409:
            raise Conflict("O documento foi alterado por outra operação.")
        if response.status_code == 404:
            raise NotFound("Documento não encontrado.")
        if response.status_code >= 400:
            raise DatabaseError(f"O banco respondeu com HTTP {response.status_code}.")
        return response.json() if response.content else {}

    def get(self, doc_id):
        return self.request("GET", "/" + quote(doc_id, safe=""))

    def put(self, doc):
        result = self.request("PUT", "/" + quote(doc["_id"], safe=""), json=doc)
        return dict(doc, _rev=result["rev"])

    def update(self, doc_id, change, attempts=6):
        for _ in range(attempts):
            doc = self.get(doc_id)
            changed = change(copy.deepcopy(doc))
            if changed == doc:
                return doc
            try:
                return self.put(changed)
            except Conflict:
                continue
        raise Conflict("Muitas alterações simultâneas. Tente novamente.")

    def find(self, selector, index=None):
        result, bookmark = [], None
        while True:
            payload = {"selector": selector, "limit": 200}
            if index:
                payload["use_index"] = index
            if bookmark:
                payload["bookmark"] = bookmark
            page = self.request("POST", "/_find", json=payload)
            result.extend(page["docs"])
            next_bookmark = page.get("bookmark")
            if len(page["docs"]) < 200 or not next_bookmark or next_bookmark == bookmark:
                return result
            bookmark = next_bookmark

    def initialize(self, products):
        # An existing database must never be cleared or reseeded over user edits.
        try:
            self.request("GET")
        except NotFound:
            self.request("PUT")
        indexes = [(["tipo", "ativo"], "catalogo"),
                   (["tipo", "plataforma", "preco_centavos"], "plataforma_preco"),
                   (["tipo", "cliente_id"], "pedidos_cliente"),
                   (["tipo", "email"], "cliente_email"),
                   (["tipo", "status"], "pedidos_status")]
        for fields, name in indexes:
            self.request("POST", "/_index", json={"index": {"fields": fields},
                         "ddoc": name, "name": name, "type": "json"})
        for product in products:
            try:
                self.put(product)
            except Conflict:
                pass
