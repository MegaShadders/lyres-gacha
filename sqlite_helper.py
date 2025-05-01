import sqlite3

def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def claim_mission(user_id, mission):
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        cur.execute("UPDATE user_missions SET claimable = 0 WHERE user_id = ? AND missions_id = ?", [user_id, mission["id"]])
        cur.execute("UPDATE user_currency SET amount = amount + ? WHERE user_id = ? AND currency_id = ?", [mission["reward"], user_id, mission["currency_id"]])