from flask import Flask
from flask_wtf.csrf import CSRFProtect
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
csrf = CSRFProtect(app)


@app.context_processor
def inject_globals():
    return {"oauth_url": Config.OAUTH_URL}


from app import routes
from app import admin_routes