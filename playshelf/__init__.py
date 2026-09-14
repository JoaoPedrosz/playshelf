import hashlib
import hmac
import os
import re
import secrets
import unicodedata
from datetime import timedelta
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .catalog import seed_products
from .db import Conflict, CouchDB, DatabaseError, NotFound
from .orders import ShopError, checkout, now, recover_order, total_shipping

ROOT = Path(__file__).resolve().parent.parent


def create_app(config=None, repository=None):
    load_dotenv(ROOT / ".env")
    app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
    app.config.update(SECRET_KEY=os.getenv("SECRET_KEY"),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=16384)
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"] or app.config["SECRET_KEY"] == "generate-a-long-random-secret":
        raise RuntimeError("Configure SECRET_KEY no .env antes de iniciar a PlayShelf.")
    db = repository or CouchDB(os.getenv("COUCHDB_URL") or ("http://" + os.getenv("COUCHDB_HOST", "127.0.0.1") + ":5984"),
                              os.getenv("COUCHDB_DATABASE", "playshelf"),
                              os.getenv("COUCHDB_USER", "admin"), os.getenv("COUCHDB_PASSWORD", ""))
    app.extensions["repository"] = db

    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    @app.before_request
    def protect():
        if request.method == "POST":
            given = request.form.get("csrf_token", "")
            if not hmac.compare_digest(session.get("csrf", "missing"), given):
                abort(400, description="O formulário expirou. Recarregue a página e tente novamente.")
        g.customer = None
        if session.get("cliente_id"):
            try:
                g.customer = db.get(session["cliente_id"])
            except NotFound:
                session.pop("cliente_id", None)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' https://upload.wikimedia.org; style-src 'self' 'unsafe-inline'; script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def context():
        return {"csrf_token": csrf, "cart_count": sum(session.get("carrinho", {}).values()),
                "customer": g.get("customer"), "shop_name": "PlayShelf"}

    @app.template_filter("money")
    def money(value):
        cents = int(value)
        whole = f"{cents // 100:,}".replace(",", ".")
        return f"R$ {whole},{cents % 100:02d}"

    def cart_data():
        items, subtotal = [], 0
        for pid, quantity in session.get("carrinho", {}).items():
            p = db.get(pid)
            items.append({"product": p, "quantity": quantity, "subtotal": p["preco_centavos"] * quantity})
            subtotal += p["preco_centavos"] * quantity
        return items, subtotal

    def require_login():
        if not g.customer:
            flash("Entre na sua conta para continuar.", "info")
            return redirect(url_for("login", next="checkout"))

    @app.get("/")
    def home():
        products = db.find({"tipo": "produto", "ativo": True}, "catalogo")
        products.sort(key=lambda p: p.get("ordem", 999))
        q = request.args.get("q", "").strip()[:100]
        console = request.args.get("console", "")
        genre = request.args.get("genero", "")
        sort = request.args.get("ordem", "destaques")
        def normalize(s):
            return "".join(c for c in unicodedata.normalize("NFD", s.casefold()) if not unicodedata.combining(c))
        selected = [p for p in products if (not console or p["console"] == console)
                    and (not genre or p["genero"] == genre)
                    and (not q or normalize(q) in normalize(p["nome"] + " " + p["genero"]))]
        if sort == "menor":
            selected.sort(key=lambda p: p["preco_centavos"])
        elif sort == "maior":
            selected.sort(key=lambda p: p["preco_centavos"], reverse=True)
        elif sort == "nome":
            selected.sort(key=lambda p: p["nome"])
        return render_template("home.html", products=selected, all_products=products, q=q, console=console,
                               genre=genre, sort=sort, genres=sorted({p["genero"] for p in products}),
                               filtered=bool(q or console or genre or sort != "destaques"))

    @app.get("/jogo/<slug>")
    def product(slug):
        p = db.get("produto:" + slug)
        if p.get("tipo") != "produto" or not p.get("ativo"):
            abort(404)
        related = [x for x in db.find({"tipo": "produto", "ativo": True}, "catalogo")
                   if x["console"] == p["console"] and x["_id"] != p["_id"]][:3]
        return render_template("product.html", product=p, related=related)

    @app.post("/carrinho/adicionar/<slug>")
    def add_cart(slug):
        p = db.get("produto:" + slug)
        if p.get("tipo") != "produto" or not p.get("ativo"):
            abort(404)
        cart = dict(session.get("carrinho", {}))
        quantity = cart.get(p["_id"], 0) + 1
        if quantity > min(p["estoque"], 20):
            flash("Quantidade indisponível no estoque.", "error")
        elif len(cart) >= 20 and p["_id"] not in cart:
            flash("Seu carrinho chegou ao limite de 20 jogos diferentes.", "error")
        else:
            cart[p["_id"]] = quantity
            session["carrinho"] = cart
            session.pop("checkout_token", None)
            flash(f"{p['titulo_curto']} entrou na sua sacola.", "success")
        return redirect(url_for("cart"))

    @app.get("/carrinho")
    def cart():
        items, subtotal = cart_data()
        return render_template("cart.html", items=items, subtotal=subtotal,
                               shipping=total_shipping(subtotal, "padrao") if items else 0)

    @app.post("/carrinho/alterar/<slug>")
    def change_cart(slug):
        pid = "produto:" + slug
        cart = dict(session.get("carrinho", {}))
        try:
            quantity = int(request.form.get("quantidade", ""))
        except ValueError:
            abort(400)
        if quantity == 0:
            cart.pop(pid, None)
        elif quantity < 0 or quantity > 20 or pid not in cart:
            abort(400)
        else:
            p = db.get(pid)
            if not p.get("ativo") or quantity > p["estoque"]:
                flash("Quantidade indisponível no estoque.", "error")
                return redirect(url_for("cart"))
            cart[pid] = quantity
        session["carrinho"] = cart
        session.pop("checkout_token", None)
        return redirect(url_for("cart"))

    @app.route("/cadastro", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("senha", "")
            if not 2 <= len(name) <= 80 or len(email) > 150 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                flash("Confira seu nome e e-mail.", "error")
                return render_template("auth.html", mode="register"), 400
            if not 8 <= len(password) <= 128:
                flash("A senha precisa ter entre 8 e 128 caracteres.", "error")
                return render_template("auth.html", mode="register"), 400
            cid = "cliente:" + hashlib.sha256(email.encode()).hexdigest()
            try:
                db.put({"_id": cid, "tipo": "cliente", "schema_version": 1, "nome": name, "email": email,
                        "senha_hash": generate_password_hash(password), "criado_em": now()})
            except Conflict:
                flash("Este e-mail já tem uma conta. Entre para continuar.", "error")
                return render_template("auth.html", mode="register"), 409
            cart = session.get("carrinho", {})
            session.clear()
            session.update(cliente_id=cid, carrinho=cart)
            session.permanent = True
            flash("Sua conta está pronta. Bem-vindo à PlayShelf!", "success")
            return redirect(url_for("cart" if cart else "home"))
        return render_template("auth.html", mode="register")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()[:150]
            password = request.form.get("senha", "")
            cid = "cliente:" + hashlib.sha256(email.encode()).hexdigest()
            try:
                person = db.get(cid)
            except NotFound:
                person = None
            if not person or len(password) > 128 or not check_password_hash(person["senha_hash"], password):
                flash("E-mail ou senha incorretos.", "error")
                return render_template("auth.html", mode="login"), 401
            cart = session.get("carrinho", {})
            session.clear()
            session.update(cliente_id=cid, carrinho=cart)
            session.permanent = True
            return redirect(url_for("cart" if cart else "orders"))
        return render_template("auth.html", mode="login")

    @app.post("/sair")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    @app.route("/checkout", methods=["GET", "POST"])
    def checkout_page():
        if response := require_login():
            return response
        if request.method == "POST":
            token = request.form.get("checkout_token", "")
            if not token or not hmac.compare_digest(token, session.get("checkout_token", "")):
                abort(400, description="Atualize a página para revisar seu pedido.")
            try:
                order = checkout(db, g.customer["_id"], session.get("carrinho", {}), token,
                                 request.form.get("entrega", "padrao"))
            except ShopError as exc:
                flash(str(exc), "error")
                return redirect(url_for("cart"))
            if order["status"] == "CONFIRMADO":
                session["carrinho"] = {}
                flash("Pedido confirmado! Sua coleção vai ganhar novos capítulos.", "success")
            elif order["status"] == "CANCELADO":
                session.pop("checkout_token", None)
                flash("Não foi possível concluir. O estoque reservado foi devolvido; revise a sacola.", "error")
            else:
                flash("Seu pedido está em conferência. Consulte o histórico antes de tentar outra compra.", "info")
            return redirect(url_for("order_detail", order_id=order["_id"].split(":", 1)[1]))
        items, subtotal = cart_data()
        if not items:
            return redirect(url_for("cart"))
        if "checkout_token" not in session:
            session["checkout_token"] = secrets.token_urlsafe(24)
        return render_template("checkout.html", items=items, subtotal=subtotal,
                               shipping=total_shipping(subtotal, "padrao"))

    @app.get("/pedidos")
    def orders():
        if response := require_login():
            return response
        data = db.find({"tipo": "pedido", "cliente_id": g.customer["_id"]}, "pedidos_cliente")
        data.sort(key=lambda x: x["criado_em"], reverse=True)
        return render_template("orders.html", orders=data, detail=False)

    @app.get("/pedidos/<order_id>")
    def order_detail(order_id):
        if response := require_login():
            return response
        order = db.get("pedido:" + order_id)
        if order.get("cliente_id") != g.customer["_id"] or order.get("tipo") != "pedido":
            abort(404)
        return render_template("orders.html", orders=[order], detail=True)

    @app.get("/sobre")
    def about():
        return render_template("about.html")

    @app.get("/healthz")
    def health():
        db.request("GET")
        return {"status": "ok", "database": "couchdb"}

    @app.errorhandler(NotFound)
    def not_found(exc):
        return render_template("error.html", code=404, message="Esse jogo ou pedido não foi encontrado."), 404

    @app.errorhandler(DatabaseError)
    def unavailable(exc):
        app.logger.warning("Database failure: %s", type(exc).__name__)
        return render_template("error.html", code=503, message="Estamos reorganizando a estante. Tente novamente em instantes. Se estava comprando, confira seus pedidos antes de repetir."), 503

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def http_error(exc):
        return render_template("error.html", code=exc.code, message=exc.description if exc.code == 400 else "Não encontramos esta página ou o pedido não é válido."), exc.code

    @app.cli.command("init-db")
    def init_db():
        db.initialize(seed_products())
        click.echo("PlayShelf: banco, índices e catálogo inicializados sem sobrescrever dados existentes.")

    @app.cli.command("sync-covers")
    def sync_covers():
        for p in seed_products():
            fields = {k: v for k, v in p.items() if k.startswith("capa_")}
            db.update(p["_id"], lambda doc, fields=fields: dict(doc, **fields))
        click.echo("Links das capas atualizados no CouchDB.")

    @app.cli.command("recover-order")
    @click.argument("order_id")
    @click.option("--workers-stopped", is_flag=True, help="Confirmar que a aplicação foi parada antes da recuperação.")
    def recover(order_id, workers_stopped):
        if not workers_stopped:
            raise click.ClickException("Pare a aplicação e use --workers-stopped para evitar corrida com checkout em execução.")
        click.echo(recover_order(db, order_id)["status"])

    return app
