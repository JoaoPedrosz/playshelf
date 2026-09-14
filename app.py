from playshelf import create_app

app = create_app()

if __name__ == "__main__":
    from waitress import serve
    import os
    serve(app, host="127.0.0.1", port=int(os.getenv("PORT", "5000")))
