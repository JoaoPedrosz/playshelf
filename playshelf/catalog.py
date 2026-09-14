import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def seed_products():
    products = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
    covers = json.loads((DATA / "covers.json").read_text(encoding="utf-8"))
    for i, p in enumerate(products):
        p.update(_id="produto:" + p["slug"], tipo="produto", ativo=True,
                 schema_version=1, midia="Física", condicao="Novo e lacrado", ordem=i,
                 movimentos={})
        p.update(covers.get(p["slug"], {}))
    return products
