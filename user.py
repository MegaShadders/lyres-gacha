import sqlite3
from zenora import APIClient
from flask import session
import datetime
import sqlite_helper


def load_user_currency(user_id):
    with sqlite3.connect("lyres.db") as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        currencies = cur.execute("SELECT currency_id, amount FROM user_currency WHERE user_id = ?", [user_id]).fetchall()
    return currencies

def load_user():
    bearer_client = APIClient(session.get('token'), bearer=True)
    current_user = bearer_client.users.get_current_user()
    currencies = load_user_currency(current_user.id)

    return current_user, currencies

def load_user_missions(user_id):
    load_user_daily(user_id)
    with sqlite3.connect("lyres.db") as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()

        missions = cur.execute("""SELECT id, description, reward, currency_id, claimable 
                               FROM user_missions
                               INNER JOIN missions
                               ON missions.id = user_missions.missions_id
                               WHERE user_id = ?""", [user_id]).fetchall()                  
        
    return missions

def load_user_daily(user_id):
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        last_daily_claimed = cur.execute("SELECT last_daily_claimed FROM users WHERE id = ?", [user_id]).fetchone()[0]
        if datetime.date.today() > datetime.date.fromisoformat(last_daily_claimed):
            cur.execute("UPDATE users SET last_daily_claimed = date('now') WHERE id = ?", [user_id])
            cur.execute("UPDATE user_missions SET claimable = 1 WHERE user_id = ?", [user_id])
