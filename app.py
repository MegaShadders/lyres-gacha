from flask import Flask, render_template, request, redirect, session
import random
import sqlite3
from config import CLIENT_SECRET, TOKEN, REDIRECT_URI, OAUTH_URL
from zenora import APIClient


app = Flask(__name__)
app.config["SECRET_KEY"] = "verysecret"
client = APIClient(TOKEN, client_secret=CLIENT_SECRET)

@app.route("/")
def index():
    if 'token' in session:
        bearer_client = APIClient(session.get('token'), bearer=True)
        current_user = bearer_client.users.get_current_user()
        return render_template("index.html", current_user=current_user)

    return render_template("index.html", oauth_url=OAUTH_URL)


@app.route("/oauth/callback")
def callback():
    code = request.args['code']
    access_token = client.oauth.get_access_token(code, REDIRECT_URI).access_token
    session['token'] = access_token

    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        bearer_client = APIClient(session.get('token'), bearer=True)
        current_user = bearer_client.users.get_current_user()
        #If discord id does not exist insert new user in db
        if cur.execute("SELECT EXISTS(SELECT id FROM users WHERE id = ?)", (current_user.id,)).fetchone()[0] == 0:
            cur.execute("INSERT INTO users (id, username) VALUES(?, ?)", [current_user.id, current_user.username])
            #Create Pity entries
            cur.execute("INSERT INTO user_pity (user_id, pity_id, count) SELECT ?, id, 0 FROM pity", (current_user.id,))
        session['id'] = current_user.id
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/pull", methods=["GET", "POST"])
def pull():
    if 'token' in session:
        bearer_client = APIClient(session.get('token'), bearer=True)
        current_user = bearer_client.users.get_current_user()
    if request.method == "GET":
        return redirect("/")
    if not request.form.get("bannerID"):
        return redirect("/")
    if not request.form.get("pullNum"):
        return redirect("/")
    
    units = []
    
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        pool = cur.execute("SELECT id, rarity, copies FROM (SELECT id, rarity FROM units WHERE id IN (SELECT unit_id FROM banner_units WHERE banner_id = ?)) LEFT JOIN (SELECT unit_id, copies FROM collections WHERE user_id = ?) ON unit_id = id", [request.form.get("bannerID"), session['id']]).fetchall()
        pity = cur.execute("SELECT id, rarity, count, maximum FROM pity INNER JOIN user_pity ON pity.id = user_pity.pity_id WHERE id IN (SELECT pity_id FROM banner_pity WHERE banner_id = ?) AND user_id = ?", [request.form.get("bannerID"), session['id']]).fetchall()
        
        counts = [x[2] for x in pity] #Puts the counts for every pity in a list
        for i in range(int(request.form.get("pullNum"))): #For every pull
            rates=[94.3, 5.1, 0.6] #Set Base Rates
            #Pity Check
            pityRarity = ""
            for j in range(len(pity)): #Check each pity
                if counts[j] + 1 == pity[j][3]: #If count + 1 = maximum
                    if pity[j][1] == "SSR":
                        pityRarity = "SSR"
                    elif pity[j][1] == "SR":
                        if pityRarity != "SSR": #Ensure you are not overwriting a higher rarity pity
                            pityRarity = "SR"
                counts[j] = counts[j] + 1

                match pityRarity: #Change rate according to pity met
                    case "SSR":
                        rates = [0, 0, 100]
                    case "SR":
                        rates = [0, 99.4, 0.6]
                        
            # Roll
            pullRarity = random.choices(["R", "SR", "SSR"], weights=rates)
            if pullRarity[0] == "R":
                units.append(random.choice([x for x in pool if x[1] == "R"]))                               
            elif pullRarity[0] == "SR":
                units.append(random.choice([x for x in pool if x[1] == "SR"]))
                for j in range(len(pity)):
                    if pity[j][1] == "SR":
                        counts[j] = 0
            else:
                units.append(random.choice([x for x in pool if x[1] == "SSR"]))    
                if pity[j][1] == "SSR":
                        counts[j] = 0
        #Update database with pulled units
        newIDs = []
        for unit in units:
            if unit[2] == None and unit[0] not in newIDs: #First time pulling this unit
                    cur.execute("INSERT INTO collections (user_id, unit_id, copies) VALUES(?, ?, 0)", [session['id'], unit[0]])
                    newIDs.append(unit[0])
            else:
                cur.execute("UPDATE collections SET copies = copies + 1 WHERE user_id = ? AND unit_id = ?", [session['id'], unit[0]])
        # Update database with new pity counts
        for k in range(len(pity)):
            cur.execute("UPDATE user_pity SET count = ? WHERE pity_id = ? AND user_id = ?", [counts[k], pity[k][0], session['id']])  
    return render_template("pull.html", current_user=current_user, units=units, pullNum=request.form.get("pullNum"), bannerID=request.form.get("bannerID"))


@app.route("/collection", methods=["GET", "POST"])
def collection():
    if 'token' in session:
        bearer_client = APIClient(session.get('token'), bearer=True)
        current_user = bearer_client.users.get_current_user()
        
    units = []
    collectedUnits = []
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        units = cur.execute("SELECT id, rarity, copies FROM (SELECT id, rarity FROM units ORDER BY LENGTH(rarity) DESC) LEFT JOIN (SELECT unit_id, copies FROM collections WHERE user_id = ?) ON unit_id = id;", [session['id']]).fetchall()
    print(units)
    return render_template("collection.html", current_user=current_user, units=units)