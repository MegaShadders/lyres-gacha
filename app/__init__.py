from flask import Flask
from flask_wtf.csrf import CSRFProtect
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
csrf = CSRFProtect(app)

from app import routes
from app import admin_routes