import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-default'
    DATABASE_URI = "lyres.db"
    MIGRATIONS_URI = "migrations/"
