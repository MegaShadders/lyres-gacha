from flask import Flask
from flask_wtf.csrf import CSRFProtect
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
csrf = CSRFProtect(app)

STATIC_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".css", ".js",
})

IMMUTABLE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


@app.after_request
def set_cache_headers(response):
    if response.status_code >= 400:
        return response

    import os
    path = response.headers.get("X-Sendfile") or ""
    _, ext = os.path.splitext(path)

    if not ext:
        from flask import request
        _, ext = os.path.splitext(request.path)

    if ext.lower() in STATIC_EXTENSIONS:
        response.headers["Cache-Control"] = f"public, max-age={IMMUTABLE_MAX_AGE}"
        response.headers["CDN-Cache-Control"] = f"max-age={IMMUTABLE_MAX_AGE}"

    return response


@app.context_processor
def inject_globals():
    return {"oauth_url": Config.OAUTH_URL}


from app import routes
from app import admin_routes