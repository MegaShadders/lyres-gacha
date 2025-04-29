import sqlite3
from zenora import APIClient
from flask import session


def load_user_currency(user_id):
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        currencies = cur.execute("SELECT amount FROM user_currency WHERE user_id = ?", [user_id]).fetchall()
    return currencies

def load_user():
    bearer_client = APIClient(session.get('token'), bearer=True)
    current_user = bearer_client.users.get_current_user()
    session_currencies = load_user_currency(current_user.id)

    return current_user, session_currencies

