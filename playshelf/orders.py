"""Recoverable checkout: atomic per-product stock moves and idempotent orders.

No claim of multi-document ACID: interrupted orders are recovered explicitly.
"""
import hashlib
from datetime import datetime, timezone

from .db import Conflict, DatabaseError, NotFound


class ShopError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def total_shipping(subtotal, shipping):
    if shipping not in ("padrao", "expresso"):
        raise ShopError("Escolha uma modalidade de entrega válida.")
    return 2990 if shipping == "expresso" else (0 if subtotal >= 39900 else 1490)


def move_stock(db, product_id, order_id, quantity, release=False):
    def change(p):
        state = p.setdefault("movimentos", {}).get(order_id)
        if release:
            if state != {"quantidade": quantity, "status": "reservado"}:
                return p
            p["estoque"] += quantity
            p["movimentos"][order_id] = {"quantidade": quantity, "status": "devolvido"}
        else:
            if state == {"quantidade": quantity, "status": "reservado"}:
                return p
            if state:
                raise ShopError("Operação de estoque já encerrada.")
            if not p.get("ativo") or p["estoque"] < quantity:
                raise ShopError(f"Estoque insuficiente para {p['nome']}.")
            p["estoque"] -= quantity
            p["movimentos"][order_id] = {"quantidade": quantity, "status": "reservado"}
        return p
    return db.update(product_id, change)


def compensate(db, order):
    # Read every item, including a PUT whose response might have timed out.
    for item in order["itens"]:
        move_stock(db, item["produto_id"], order["_id"], item["quantidade"], release=True)
    return db.update(order["_id"], lambda d: dict(d, status="CANCELADO", atualizado_em=now()))


def checkout(db, customer_id, cart, token, shipping):
    order_id = "pedido:" + hashlib.sha256(f"{customer_id}:{token}".encode()).hexdigest()[:32]
    try:
        return db.get(order_id)
    except NotFound:
        pass
    if not cart:
        raise ShopError("Seu carrinho está vazio.")
    items = []
    for pid, quantity in sorted(cart.items()):
        if not isinstance(quantity, int) or not 1 <= quantity <= 20:
            raise ShopError("Quantidade inválida.")
        p = db.get(pid)
        if p.get("tipo") != "produto" or not p.get("ativo") or p["estoque"] < quantity:
            raise ShopError("Um dos jogos não tem estoque suficiente.")
        items.append({"produto_id": pid, "nome": p["nome"], "plataforma": p["plataforma"],
                      "slug": p["slug"], "capa_url": p.get("capa_url", ""),
                      "quantidade": quantity, "preco_unitario_centavos": p["preco_centavos"]})
    subtotal = sum(i["quantidade"] * i["preco_unitario_centavos"] for i in items)
    freight = total_shipping(subtotal, shipping)
    order = {"_id": order_id, "tipo": "pedido", "schema_version": 1,
             "cliente_id": customer_id, "itens": items, "subtotal_centavos": subtotal,
             "frete_centavos": freight, "total_centavos": subtotal + freight,
             "entrega": shipping, "status": "PROCESSANDO", "simulado": True, "criado_em": now()}
    try:
        order = db.put(order)
    except Conflict:
        return db.get(order_id)  # Another request owns this order's execution.
    try:
        for item in items:
            move_stock(db, item["produto_id"], order_id, item["quantidade"])
        return db.update(order_id, lambda d: dict(d, status="CONFIRMADO", atualizado_em=now()))
    except (ShopError, DatabaseError):
        # A lost confirmation response may still represent a confirmed order.
        latest = db.get(order_id)
        if latest["status"] == "CONFIRMADO":
            return latest
        db.update(order_id, lambda d: dict(d, status="COMPENSANDO", atualizado_em=now()))
        return compensate(db, order)


def recover_order(db, order_id):
    """Run only after checkout workers have stopped, avoiding recovery races."""
    order = db.get(order_id)
    if order["status"] in ("CONFIRMADO", "CANCELADO"):
        return order
    return compensate(db, order)
