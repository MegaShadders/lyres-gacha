import sqlite3
from zenora import APIClient
from flask import session, request, redirect
import datetime
import sqlite_helper
from config import Config

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
    load_user_daily_login(user_id)
    with sqlite3.connect("lyres.db") as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()

        missions = cur.execute("""SELECT id, description, reward, currency_id, claimable 
                               FROM user_missions
                               INNER JOIN missions
                               ON missions.id = user_missions.mission_id
                               WHERE user_id = ?""", [user_id]).fetchall()                  
        
    return missions

def load_user_daily_login(user_id):
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        last_daily_claimed = cur.execute("SELECT last_daily_claimed FROM users WHERE id = ?", [user_id]).fetchone()[0]
        if datetime.date.today() > datetime.date.fromisoformat(last_daily_claimed):
            cur.execute("UPDATE users SET last_daily_claimed = date('now') WHERE id = ?", [user_id])
            cur.execute("UPDATE user_missions SET claimable = 1 WHERE user_id = ? AND description = 'Daily Login:'", [user_id])


def identify_user(cur, user_id):
    return cur.execute("SELECT EXISTS(SELECT id FROM users WHERE id = ?)", [user_id]).fetchone()[0]
     

def create_new_user(cur, current_user):
    #Create User Entry
    cur.execute("INSERT INTO users (id, username) VALUES(?, ?)", [current_user.id, current_user.username])
    #Create Pity Entries
    cur.execute("INSERT INTO user_pity (user_id, pity_id, count, rateup_pity) SELECT ?, id, 0, rateup_exists FROM pity", (current_user.id,))
    #Create Currency Entries
    cur.execute("INSERT INTO user_currency (user_id, currency_id, amount) SELECT ?, id, 0 FROM currency", (current_user.id,))
    #Create Mission Entries
    cur.execute("INSERT INTO user_missions (user_id, mission_id, claimable, last_claimed) SELECT ?, id, 0, date('now', '-1 day') FROM missions", (current_user.id,))


def sacrifice_request(request):
    if not request.form.get("id") or not request.form.get("sacrificeAmount"):
        return redirect("/")
        
    try: 
        sacriID = int(request.form.get("id"))
        sacriAmt = int(request.form.get("sacrificeAmount"))
    except (TypeError, ValueError):
        return redirect("/")
    

    with sqlite3.connect("lyres.db") as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        sacriUnit = sqlite_helper.get_sacrifice_unit(cur, session['id'], sacriID)
    
        if not sacriUnit["copies"] or sacriAmt > sacriUnit["copies"]:
            return redirect("/")
        
        rarity_map = {"SSR": 2, "SR": 1, "R": 0}
        rarityMod = rarity_map.get(sacriUnit["rarity"])

        exponentialAmt = min(sacriAmt, 5) #The amount of sacrifices subject to exponentially increasing rewards, up to 5
        linearAmt = max(sacriAmt-5, 0) #The overflow of sacrifices subject to linearly increasing rewards
        exponentialReward =  (Config.PULL_COST * 2**rarityMod) * 2**(exponentialAmt-1) #160*2^{0, 1, 2} * 2^{0-5}
        linearReward = linearAmt * exponentialReward # 0 if sacriAmt <= 5
        reward = exponentialReward + linearReward
        
        sqlite_helper.sacrifice_copies(cur, sacriUnit, session["id"], sacriAmt)
        sqlite_helper.change_currency(cur, reward, session["id"], min(1, rarityMod)+1) #if rarityMod = 0 (R) silver coins, if rarityMod is 1 or higher (SR/SSR), gold coins. +1 for 0 index array into sql table