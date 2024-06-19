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
        pool = cur.execute("SELECT id, rarity FROM lyres WHERE id IN (SELECT lyres_id FROM banner_units WHERE banner_id = ?)", request.form.get("bannerID")).fetchall()
    for i in range(int(request.form.get("pullNum"))):
        units.append(random.choice(pool))



    return render_template("pull.html", units=units)