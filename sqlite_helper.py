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


def get_banner_pool(cur, user_id, banner_id):
    return cur.execute("""SELECT id, rarity, copies, rateup
                            FROM units
                            INNER JOIN banner_units ON units.id = banner_units.unit_id
                            LEFT JOIN collections ON banner_units.unit_id = collections.unit_id AND collections.user_id = ?
                            WHERE banner_id = ?""", (user_id, banner_id)).fetchall()

def get_banner_pities(cur, banner_id, user_id):
    return cur.execute("""SELECT id, rarity, count, maximum, rateup_exists
                             FROM pity 
                             INNER JOIN user_pity ON pity.id = user_pity.pity_id 
                             WHERE id IN (
                                SELECT pity_id 
                                FROM banner_pity 
                                WHERE banner_id = ?
                             ) 
                             AND user_id = ?""", [banner_id, user_id]).fetchall()

def create_collection_entry(cur, user_id, unit_id):
    cur.execute("INSERT INTO collections (user_id, unit_id, copies) VALUES(?, ?, 0)", [user_id, unit_id])


def update_collection_entry(cur, user_id, unit_id):
    cur.execute("UPDATE collections SET copies = copies + 1 WHERE user_id = ? AND unit_id = ?", [user_id, unit_id])


def update_pity(cur, pity_count, pity_id, user_id):
            cur.execute("UPDATE user_pity SET count = ? WHERE pity_id = ? AND user_id = ?", [pity_count, pity_id, user_id]) 


def update_currencies(cur, new_amount, user_id, banner_id):
    cur.execute("UPDATE user_currency SET amount = ? WHERE user_id = ? AND currency_id = ?", (new_amount, user_id, banner_id))


    


    