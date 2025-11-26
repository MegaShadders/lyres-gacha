import sqlite3

def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}
    

def change_currency(amount, user_id, currency_id):
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        cur.execute("UPDATE user_currency SET amount = amount + ? WHERE user_id = ? AND currency_id = ?", [amount, user_id, currency_id])


def claim_mission(user_id, mission):
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        cur.execute("UPDATE user_missions SET claimable = 0 WHERE user_id = ? AND missions_id = ?", [user_id, mission["id"]])
    change_currency(mission["reward"], user_id, mission["currency_id"])


def sacrifice_copies(sacriUnit, user_id, sacriAmt):
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        cur.execute("""UPDATE collections 
                    SET copies = copies - ? 
                    WHERE user_id = ? AND unit_id = ?;"""
                    , [sacriAmt, user_id, sacriUnit["id"]])
        

def get_banners():
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        return cur.execute("SELECT id FROM banners WHERE active == 1").fetchall()

