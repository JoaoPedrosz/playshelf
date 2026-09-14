"""Generate public academic evidence in isolated, disposable CouchDB databases."""
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playshelf import create_app
from playshelf.catalog import seed_products
from playshelf.db import Conflict, CouchDB
from playshelf.orders import checkout


def main():
    live = create_app().extensions['repository']
    suffix = uuid.uuid4().hex
    source = CouchDB(live.base, 'playshelf_evidence_' + suffix, *live.auth)
    target_name = 'playshelf_replica_' + suffix
    target = CouchDB(live.base, target_name, *live.auth)
    report = {'executado_em': datetime.now(timezone.utc).isoformat(),
              'couchdb': live.request('GET', root=True)['version']}
    try:
        source.initialize(seed_products())
        pid = 'produto:zelda-tears-switch'
        before = source.get(pid)
        updated = source.put(dict(before, estoque=2))
        try:
            source.put(before)
            raise AssertionError('Expected stale revision conflict')
        except Conflict:
            report['conflito'] = {'http': 409, 'rev_anterior':before['_rev'], 'rev_atual':updated['_rev']}
        query = {'selector':{'tipo':'produto','plataforma':'PlayStation 5','preco_centavos':{'$lte':25000}},
                 'use_index':'plataforma_preco', 'fields':['_id','nome','preco_centavos']}
        found = source.request('POST', '/_find', json=query)
        explain = source.request('POST', '/_explain', json=query)
        report['consulta_mango'] = {'consulta':query, 'indice_escolhido':explain['index']['name'], 'resultados':found['docs']}
        order = checkout(source, 'cliente:demonstracao', {pid:1}, suffix, 'padrao')
        replay = checkout(source, 'cliente:demonstracao', {pid:1}, suffix, 'padrao')
        report['checkout'] = {'status':order['status'],'estoque_final':source.get(pid)['estoque'],
                              'mesmo_pedido_ao_repetir':order['_id']==replay['_id'], 'total_centavos':order['total_centavos']}
        source_name = 'playshelf_evidence_' + suffix
        replicated = source.request('POST', '/_replicate', root=True,
            json={'source':source_name,'target':target_name,'create_target':True})
        replica_order = target.get(order['_id'])
        report['replicacao'] = {'escopo':'Dois bancos na mesma instância local; demonstra o protocolo, não alta disponibilidade.',
                               'ok':replicated['ok'],'pedido_preservado':replica_order['total_centavos']==order['total_centavos']}
        assert report['replicacao']['pedido_preservado']
        destination = ROOT/'docs/evidencias/couchdb.json'
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
        print('Evidence saved: docs/evidencias/couchdb.json (no credentials or personal data)')
    finally:
        for disposable in (source, target):
            try:
                disposable.request('DELETE')
            except Exception:
                pass


if __name__ == '__main__':
    main()
