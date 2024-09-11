from flask import Flask, render_template, request, redirect
import random
import sqlite3


app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/pull", methods=["GET", "POST"])
def pull():
    if request.method == "GET":
        return redirect("/")
    if not request.form.get("bannerID"):
        return redirect("/")
    if not request.form.get("pullNum"):
        return redirect("/")
    
    units = []
    
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        poolSSR = cur.execute("SELECT id, rarity FROM units WHERE id IN (SELECT unit_id FROM banner_units WHERE banner_id = ?) AND rarity = 'SSR'", request.form.get("bannerID")).fetchall()
        poolSR = cur.execute("SELECT id, rarity FROM units WHERE id IN (SELECT unit_id FROM banner_units WHERE banner_id = ?) AND rarity = 'SR'", request.form.get("bannerID")).fetchall()
        poolR = cur.execute("SELECT id, rarity FROM units WHERE id IN (SELECT unit_id FROM banner_units WHERE banner_id = ?) AND rarity = 'R'", request.form.get("bannerID")).fetchall()
        rarities = random.choices(["R", "SR", "SSR"], weights=[90, 5.1, 0.6], k= int(request.form.get("pullNum")))
        print(rarities)
        for rarity in rarities:
            if rarity == "R":
                units.append(random.choice(poolR))
            elif rarity == "SR":
                units.append(random.choice(poolSR))
            else:
                units.append(random.choice(poolSSR))        

    return render_template("pull.html", units=units, pullNum=request.form.get("pullNum"), bannerID=request.form.get("bannerID"))


@app.route("/collection", methods=["GET", "POST"])
def collection():

    units = []
    collectedUnits = []
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        units = cur.execute("SELECT id, rarity FROM units ORDER BY LENGTH(rarity) DESC").fetchall()
        collectedUnits = cur.execute("SELECT unit_id, copies FROM collections WHERE user_id = 3").fetchall()

        unitList = [x[0] for x in units]
        collectedList = [x[0] for x in collectedUnits]

        for i in range(len(units)):
            if unitList[i] in collectedList:
                units[i] = units[i] + (True, )
            else:
                units[i] = units[i] + (True, ) # Set to Flase when not testing
    
    return render_template("collection.html", units=units, collectedUnits=collectedUnits)