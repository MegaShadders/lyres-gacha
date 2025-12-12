import sqlite3
from zenora import APIClient
from flask import session, request, redirect
import datetime
import sqlite_helper
from config import Config

def load_user_currency(user_id):
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        currencies = cur.execute("SELECT currency_id, amount FROM user_currency WHERE user_id = ?", [user_id]).fetchall()
    return currencies

def load_user():
    bearer_client = APIClient(session.get('token'), bearer=True)
    current_user = bearer_client.users.get_current_user()
    currencies = load_user_currency(current_user.id)

    return current_user, currencies

def get_user_missions(user_id):
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()

        missions = cur.execute("""SELECT mission_id, description, reward, currency_id, claimable, reset, last_reset
                               FROM user_missions
                               INNER JOIN missions
                               ON missions.id = user_missions.mission_id
                               WHERE user_id = ?""", [user_id]).fetchall()
        
    return missions

def check_login_missions(cur, missions, user_id):
    for mission in missions:
        if mission["description"] == "Daily Login:" or mission["description"] == "Weekly Login:":
            if check_mission_reset(cur, mission, user_id):
                reset_mission(cur, mission["mission_id"], user_id)
                set_mission_claimable(cur, mission["mission_id"], user_id)
                mission["claimable"] = 1

def check_mission_reset(cur, mission, user_id):
    today = datetime.date.today()
    if mission["reset"] == "Daily":
        last_reset = datetime.date.fromisoformat(mission["last_reset"])
        if today > last_reset:
            return True
    elif mission["reset"] == "Weekly":
        last_reset = datetime.date.fromisoformat(mission["last_reset"])
        this_monday = today - datetime.timedelta(days=today.weekday())
        if last_reset < this_monday:
            return True
    return False
            

def reset_mission(cur, mission_id, user_id):
    cur.execute("UPDATE user_missions SET last_reset = date('now') WHERE user_id = ? AND mission_id = ?", [user_id, mission_id])


def set_mission_claimable(cur, mission_id, user_id):
    cur.execute("UPDATE user_missions SET claimable = 1 WHERE user_id = ? AND mission_id = ?", [user_id, mission_id])


def identify_user(cur, user_id):
    return cur.execute("SELECT EXISTS(SELECT id FROM users WHERE id = ?)", [user_id]).fetchone()[0]
     

def create_new_user(cur, current_user):
    #Create User Entry
    cur.execute("INSERT INTO users (id, username) VALUES(?, ?)", [current_user.id, current_user.username])
    #Create Pity Entries
    cur.execute("INSERT INTO user_pity (user_id, pity_id, count, rateup_pity) SELECT ?, id, 0, rateup_exists FROM pity", (current_user.id,))
    #Create Currency Entries
    cur.execute("INSERT INTO user_currency (user_id, currency_id, amount) SELECT ?, id, 0 FROM currency", (current_user.id,))
    #Create Mission Entries, set last_reset to 10 days ago so all missions get reset upon load (date(0) or null doesn't work)
    cur.execute("INSERT INTO user_missions (user_id, mission_id, claimable, last_reset) SELECT ?, id, 0, date('now', '-10 day') FROM missions", (current_user.id,))


def sacrifice_request(request):
    if not request.form.get("id") or not request.form.get("sacrificeAmount"):
        return redirect("/")
        
    try: 
        sacriID = int(request.form.get("id"))
        sacriAmt = int(request.form.get("sacrificeAmount"))
    except (TypeError, ValueError):
        return redirect("/")
    

    with sqlite3.connect(Config.DATABASE_URI) as con:
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