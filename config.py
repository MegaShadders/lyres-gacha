import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable must be set")
    DATABASE_URI = os.environ.get('DATABASE_URI')
    MIGRATIONS_URI = os.environ.get('MIGRATIONS_URI')
    DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
    CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
    REDIRECT_URI = os.environ.get('REDIRECT_URI')
    OAUTH_URL = os.environ.get('OAUTH_URL')
    PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID') 
    PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')
    PULL_COST = 160

    @staticmethod
    def admin_discord_ids():
        raw = os.environ.get("ADMIN_DISCORD_IDS") or os.environ.get("ADMIN_DISCORD_ID") or ""
        ids = set()
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
        return ids