import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-default'
    DATABASE_URI = os.environ.get('DATABASE_URI')
    MIGRATIONS_URI = os.environ.get('MIGRATIONS_URI')
    DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
    CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
    REDIRECT_URI = os.environ.get('REDIRECT_URI')
    OAUTH_URL = os.environ.get('OAUTH_URL')
    SECRET_KEY = os.environ.get('SECRET_KEY')
    PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID') 
    PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')