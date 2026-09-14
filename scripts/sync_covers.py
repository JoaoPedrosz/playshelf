"""Refresh cover URL metadata from Wikipedia's public REST summary API.

No secret key, image files or external descriptions are stored in this repository.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    products = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    target = ROOT / "data/covers.json"
    existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    for product in products:
        try:
            endpoint = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(product["wiki"].replace(" ", "_"), safe="")
            request = Request(endpoint, headers={"User-Agent": "PlayShelfAcademic/1.0 (educational game catalog)", "Accept": "application/json"})
            with urlopen(request, timeout=25) as response:
                payload = json.load(response)
            image = payload.get("originalimage", payload.get("thumbnail", {})).get("source")
            if not image or urlsplit(image).hostname != "upload.wikimedia.org":
                raise ValueError("Capa não encontrada no provedor permitido")
            existing[product["slug"]] = {"capa_url": image.split("?")[0],
                "capa_fonte": payload["content_urls"]["desktop"]["page"],
                "capa_api": endpoint, "capa_consultada_em": datetime.now(timezone.utc).isoformat()}
            print("OK", product["slug"], flush=True)
        except Exception as exc:
            print("FALHA", product["slug"], type(exc).__name__, flush=True)
        time.sleep(0.25)
    target.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(existing)}/{len(products)} capas disponíveis", flush=True)


if __name__ == "__main__":
    main()
