import sqlite3
from config import Config
import user

def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}
    

def change_currency(cur, amount, user_id, currency_id):
    cur.execute("UPDATE user_currency SET amount = amount + (?) WHERE user_id = ? AND currency_id = ?", [amount, user_id, currency_id])

def claim_mission(cur, user_id, mission):
    cur.execute("UPDATE user_missions SET claimed = 1 WHERE user_id = ? AND mission_id = ?", [user_id, mission["mission_id"]])
    change_currency(cur, mission["reward"], user_id, mission["currency_id"])


def sacrifice_copies(cur, sacriUnit, user_id, sacriAmt):
    cur.execute("""UPDATE collections 
                SET copies = copies - ? 
                WHERE user_id = ? AND unit_id = ?;"""
                , [sacriAmt, user_id, sacriUnit["id"]])
    
    #Check mission
    missions = user.get_user_missions(user_id)
    for mission in missions:
        if "Offering" in mission["description"]:
            user.complete_mission(cur, mission["mission_id"], user_id, sacriAmt)


def get_banners(cur):
    return cur.execute(
        """SELECT id, name, currency_id, starts_at, ends_at, sort_order, active
           FROM banners
           WHERE active = 1
             AND (starts_at IS NULL OR starts_at <= datetime('now'))
             AND (ends_at IS NULL OR ends_at > datetime('now'))
           ORDER BY sort_order ASC, id ASC"""
    ).fetchall()


def get_playable_banner_by_id(cur, banner_id):
    return cur.execute(
        """SELECT id, name, currency_id, starts_at, ends_at, sort_order, active
           FROM banners
           WHERE id = ?
             AND active = 1
             AND (starts_at IS NULL OR starts_at <= datetime('now'))
             AND (ends_at IS NULL OR ends_at > datetime('now'))""",
        (banner_id,),
    ).fetchone()


def get_all_banners_admin(cur):
    return cur.execute(
        """SELECT id, name, currency_id, starts_at, ends_at, sort_order, active,
                  (SELECT COUNT(*) FROM banner_units WHERE banner_id = banners.id) AS unit_count
           FROM banners
           ORDER BY sort_order ASC, id ASC"""
    ).fetchall()


def get_currency_rows(cur):
    return cur.execute("SELECT id, name FROM currency ORDER BY id").fetchall()


def get_units_for_admin(cur):
    return cur.execute("SELECT id, rarity FROM units ORDER BY LENGTH(rarity) DESC, id").fetchall()


def get_pity_rows(cur):
    return cur.execute(
        "SELECT id, maximum, note, rarity, rateup_exists FROM pity ORDER BY id"
    ).fetchall()


def get_banner_admin_detail(cur, banner_id):
    row = cur.execute(
        """SELECT id, name, currency_id, starts_at, ends_at, sort_order, active
           FROM banners WHERE id = ?""",
        (banner_id,),
    ).fetchone()
    if not row:
        return None
    units = cur.execute(
        "SELECT unit_id, rateup FROM banner_units WHERE banner_id = ? ORDER BY unit_id",
        (banner_id,),
    ).fetchall()
    pities = cur.execute(
        "SELECT pity_id FROM banner_pity WHERE banner_id = ? ORDER BY pity_id",
        (banner_id,),
    ).fetchall()
    return {"banner": row, "units": units, "pity_ids": [p["pity_id"] for p in pities]}


def insert_banner(cur, name, active, starts_at, ends_at, sort_order, currency_id):
    cur.execute(
        """INSERT INTO banners (name, active, starts_at, ends_at, sort_order, currency_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, 1 if active else 0, starts_at, ends_at, sort_order, currency_id),
    )
    return cur.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_banner(cur, banner_id, name, active, starts_at, ends_at, sort_order, currency_id):
    cur.execute(
        """UPDATE banners
           SET name = ?, active = ?, starts_at = ?, ends_at = ?, sort_order = ?, currency_id = ?
           WHERE id = ?""",
        (name, 1 if active else 0, starts_at, ends_at, sort_order, currency_id, banner_id),
    )


def replace_banner_units(cur, banner_id, unit_rateup_pairs):
    cur.execute("DELETE FROM banner_units WHERE banner_id = ?", (banner_id,))
    for unit_id, rateup in unit_rateup_pairs:
        cur.execute(
            "INSERT INTO banner_units (banner_id, unit_id, rateup) VALUES (?, ?, ?)",
            (banner_id, unit_id, 1 if rateup else 0),
        )


def replace_banner_pity(cur, banner_id, pity_ids):
    cur.execute("DELETE FROM banner_pity WHERE banner_id = ?", (banner_id,))
    for pity_id in pity_ids:
        cur.execute(
            "INSERT INTO banner_pity (banner_id, pity_id) VALUES (?, ?)",
            (banner_id, pity_id),
        )


def copy_banner_pity_from_banner(cur, target_banner_id, source_banner_id):
    cur.execute("DELETE FROM banner_pity WHERE banner_id = ?", (target_banner_id,))
    cur.execute(
        """INSERT INTO banner_pity (banner_id, pity_id)
           SELECT ?, pity_id FROM banner_pity WHERE banner_id = ?""",
        (target_banner_id, source_banner_id),
    )


def get_banner_pool(cur, user_id, banner_id):
    return cur.execute("""SELECT id, rarity, copies, rateup
                            FROM units
                            INNER JOIN banner_units ON units.id = banner_units.unit_id
                            LEFT JOIN collections ON banner_units.unit_id = collections.unit_id AND collections.user_id = ?
                            WHERE banner_id = ?""", (user_id, banner_id)).fetchall()

def get_banner_pities(cur, banner_id, user_id):
    return cur.execute("""SELECT id, rarity, count, maximum, rateup_exists, note
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


def get_collection(cur, user_id):
    return cur.execute("""SELECT id, rarity, copies 
                                FROM (SELECT id, rarity FROM units) 
                                LEFT JOIN (
                                    SELECT unit_id, copies 
                                    FROM collections 
                                    WHERE user_id = ?
                                ) ON unit_id = id 
                                ORDER BY LENGTH(rarity) DESC;""", [user_id]).fetchall()

def get_sacrifice_unit(cur, user_id, unit_id):
    return cur.execute("""SELECT id, rarity, copies 
                                FROM (SELECT id, rarity FROM units) 
                                LEFT JOIN (
                                    SELECT unit_id, copies 
                                    FROM collections 
                                    WHERE user_id = ?
                                ) ON unit_id = id 
                                WHERE id = ?
                                ORDER BY LENGTH(rarity) DESC;""", [user_id, unit_id]).fetchone()



    


    