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
        pool = cur.execute("SELECT id, rarity FROM units WHERE id IN (SELECT unit_id FROM banner_units WHERE banner_id = ?)", request.form.get("bannerID")).fetchall()
    for i in range(int(request.form.get("pullNum"))):
        units.append(random.choice(pool))

    return render_template("pull.html", units=units, pullNum=request.form.get("pullNum"), bannerID=request.form.get("bannerID"))


@app.route("/collection", methods=["GET", "POST"])
def collection():

    units = []
    collectedUnits = []
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        units = cur.execute("SELECT id, rarity FROM units").fetchall()
        collectedUnits = cur.execute("SELECT unit_id, copies FROM collections WHERE user_id = 3").fetchall()

        unitList = [x[0] for x in units]
        collectedList = [x[0] for x in collectedUnits]

        for i in range(len(units)):
            if unitList[i] in collectedList:
                units[i] = units[i] + (True, )
            else:
                units[i] = units[i] + (False, )
    
    return render_template("collection.html", units=units, collectedUnits=collectedUnits)