import sqlite3
from zenora import APIClient
from flask import session
import datetime
import sqlite_helper
from config import Config

SACRIFICE_THRESHOLD = 80
SACRIFICE_MULTIPLIERS = [1, 5, 10]  # Maps to [R, SR, SSR]

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

        missions = cur.execute("""SELECT mission_id, description, reward, currency_id, count, requirement, reset, claimed, last_reset
                               FROM user_missions
                               INNER JOIN missions
                               ON missions.id = user_missions.mission_id
                               WHERE user_id = ?""", [user_id]).fetchall()

    return missions    


def check_mission_reset(mission):
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
    cur.execute("UPDATE user_missions SET claimed = 0, count = 0, last_reset = date('now') WHERE user_id = ? AND mission_id = ?", [user_id, mission_id])


def complete_mission(cur, mission_id, user_id, amount):
    cur.execute("UPDATE user_missions SET count = count + ? WHERE user_id = ? AND mission_id = ?", [amount, user_id, mission_id])


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
    cur.execute("INSERT INTO user_missions (user_id, mission_id, count, claimed, last_reset) SELECT ?, id, 0, 0, date('now', '-10 day') FROM missions", (current_user.id,))


def sacrifice_request(request):
    """Returns True if sacrifice was performed, False on validation failure."""
    if not request.form.get("id") or not request.form.get("sacrificeAmount"):
        return False

    try: 
        sacriID = int(request.form.get("id"))
        sacriAmt = int(request.form.get("sacrificeAmount"))
    except (TypeError, ValueError):
        return False

    if sacriAmt < 1:
        return False

    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        sacriUnit = sqlite_helper.get_sacrifice_unit(cur, session['id'], sacriID)
    
        if not sacriUnit or not sacriUnit["copies"] or sacriAmt > sacriUnit["copies"]:
            return False
        
        rarity_map = {"SSR": 2, "SR": 1, "R": 0}
        rarityMod = rarity_map.get(sacriUnit["rarity"])

        multiplier = SACRIFICE_MULTIPLIERS[rarityMod]
        
        # Piecewise formula: triangular formula up to threshold, then linear        
        if sacriAmt <= SACRIFICE_THRESHOLD:
            reward = int(multiplier * ((sacriAmt * (sacriAmt + 1)) / 2))
        else:
            threshold_reward = int(multiplier * ((SACRIFICE_THRESHOLD * (SACRIFICE_THRESHOLD + 1)) / 2))
            # THRESHOLD * MULTIPLIER is the linear rate so that the marginal increase is equal to the [threshold - 1]-th sacrifice
            reward = threshold_reward + (SACRIFICE_THRESHOLD * SACRIFICE_MULTIPLIERS[rarityMod]) * (sacriAmt - SACRIFICE_THRESHOLD)
        
        sqlite_helper.sacrifice_copies(cur, sacriUnit, session["id"], sacriAmt)
        #if rarityMod = 0 (R) silver coins, if rarityMod is 1 or higher (SR/SSR), gold coins. +1 for 0 index array into sql table
        sqlite_helper.change_currency(cur, reward, session["id"], min(1, rarityMod)+1)

    return True