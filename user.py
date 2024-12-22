import sqlite3
import datetime
from zenora import APIClient
from flask import session


def load_user_currency(user_id):
    con = sqlite3.connect("lyres.db")
    cur = con.cursor()
    currencies = cur.execute("SELECT amount FROM user_currency WHERE user_id = ?", [user_id]).fetchall()
    last_claimed = cur.execute("SELECT last_daily_claimed FROM users WHERE id = ?", [user_id]).fetchone()[0]

    #Daily Reset
    if datetime.date.today() > datetime.date.fromisoformat(last_claimed):
        #Daily 1600 Silver Fox Coins
        cur.execute("UPDATE users SET last_daily_claimed = date('now') WHERE id = ?", [user_id])
        currencies[0] = (currencies[0][0] + 1600,)
        cur.execute("UPDATE user_currency SET amount = ? WHERE user_id = ? AND currency_id = 1", [currencies[0][0], user_id])
        #Other Dailies Below
    con.commit()
    return currencies

def load_user(session_currencies):
    bearer_client = APIClient(session.get('token'), bearer=True)
    current_user = bearer_client.users.get_current_user()
    session_currencies = load_user_currency(current_user.id)

    return current_user, session_currencies

