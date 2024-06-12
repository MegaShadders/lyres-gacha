from flask import Flask, render_template, request, redirect
import random
import sqlite3


app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/pull", methods=["POST"])
def pull():
    if not request.form.get("bannerID"):
        return redirect("/")
    if not request.form.get("pullNum"):
        return redirect("/")
    
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        units = cur.execute("SELECT id, rarity FROM lyres WHERE id IN (SELECT lyres_id FROM banner_units WHERE banner_id = ?)", request.form.get("bannerID"))
        unit = random.choice(units.fetchall())

    return render_template("pull.html", unit=unit)