from flask import Flask, render_template, request, redirect, session, jsonify
import random
import sqlite3
import json
from config import Config
from zenora import APIClient
import user
import sqlite_helper
import collections

import logging
from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.logging.configuration.api_logging_configuration import (
    LoggingConfiguration,
    RequestLoggingConfiguration,
    ResponseLoggingConfiguration,
)
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient
from paypalserversdk.controllers.orders_controller import OrdersController
from paypalserversdk.controllers.payments_controller import PaymentsController
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.api_helper import ApiHelper

from app import app

client = APIClient(Config.DISCORD_TOKEN, client_secret=Config.CLIENT_SECRET)

STORE_PRODUCTS = {
    "160":   {"currency_amount": 160,   "price": "0.01", "currency_id": 2},
    "800":   {"currency_amount": 800,   "price": "0.04", "currency_id": 2},
    "1600":  {"currency_amount": 1600,  "price": "0.07", "currency_id": 2},
    "3200":  {"currency_amount": 3200,  "price": "0.13", "currency_id": 2},
    "6400":  {"currency_amount": 6400,  "price": "0.23", "currency_id": 2},
    "12800": {"currency_amount": 12800, "price": "0.40", "currency_id": 2},
    "25600": {"currency_amount": 25600, "price": "0.65", "currency_id": 2},
    "51200": {"currency_amount": 51200, "price": "1.00", "currency_id": 2},
}

paypal_client: PaypalServersdkClient = PaypalServersdkClient(
    client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
        o_auth_client_id=Config.PAYPAL_CLIENT_ID,
        o_auth_client_secret=Config.PAYPAL_CLIENT_SECRET,
    ),
    logging_configuration=LoggingConfiguration(
        log_level=logging.INFO,
        mask_sensitive_headers=True,
        request_logging_config=RequestLoggingConfiguration(
            log_headers=False, log_body=False
        ),
        response_logging_config=ResponseLoggingConfiguration(
            log_headers=False, log_body=False
        ),
    ),
)

orders_controller: OrdersController = paypal_client.orders
payments_controller: PaymentsController = paypal_client.payments


@app.route("/", methods=["GET", "POST"])
def index():
    if 'token' not in session: 
        return redirect(Config.OAUTH_URL)
    current_user, currencies = user.load_user()
    
    if request.method == "GET":
        with sqlite3.connect(Config.DATABASE_URI) as con:
            con.row_factory = sqlite_helper.dict_factory
            cur = con.cursor()
            banners = sqlite_helper.get_banners(cur)
            bannerUnits = []
            bannerPities = []
            sortedUnits = []
            # Get units and pities for each active banner
            for banner in banners:
                bannerUnits.append(sqlite_helper.get_banner_pool(cur, session["id"], banner["id"]))
                bannerPities.append(sorted(sqlite_helper.get_banner_pities(cur, banner["id"], session["id"]), key=lambda x: len(x["rarity"]), reverse=True))

            # Split units in each banner by rarity
            for units in bannerUnits:
                raritySorted = collections.defaultdict(list)
                for unit in units:
                    raritySorted[unit['rarity']].append(unit)
                sortedUnits.append(raritySorted)

        return render_template(
            "index.html",
            current_user=current_user,
            banners=banners,
            currencies=currencies,
            bannerUnits=sortedUnits,
            bannerPities=bannerPities,
        )

    elif request.method == "POST":
        user.sacrifice_request(request)

        return redirect("/")

    

@app.route("/oauth/callback")
def callback():
    try:
        code = request.args['code']
        access_token = client.oauth.get_access_token(code, Config.REDIRECT_URI).access_token
        session['token'] = access_token
    except:
        return redirect("/")
    
    bearer_client = APIClient(session.get('token'), bearer=True)
    current_user = bearer_client.users.get_current_user()
    with sqlite3.connect(Config.DATABASE_URI) as con:
        cur = con.cursor()
        #If discord id does not exist insert new user in db
        if user.identify_user(cur, current_user.id) == 0:
            user.create_new_user(cur, current_user)
    session['id'] = current_user.id
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/pull", methods=["POST"])
def pull():
    #check user logged in
    if 'token' not in session: 
        return redirect("/")
    current_user, currencies = user.load_user()
    
    if not request.form.get("bannerID") or not request.form.get("pullNum"):
        return redirect("/")

    
    pulledUnits = []
    try: 
        bannerID = int(request.form.get("bannerID"))
        pullNum = int(request.form.get("pullNum"))
    except (TypeError, ValueError):
        return redirect("/")

    if pullNum not in (1, 10):
        return redirect("/")


    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()

        banner_row = sqlite_helper.get_playable_banner_by_id(cur, bannerID)
        if not banner_row:
            return redirect("/")

        currency_id = banner_row["currency_id"]
        total_cost = Config.PULL_COST * pullNum
        if not sqlite_helper.deduct_currency(cur, total_cost, current_user.id, currency_id):
            return redirect("/")

        pool = sqlite_helper.get_banner_pool(cur, current_user.id, bannerID)
        pities = sqlite_helper.get_banner_pities(cur, request.form.get("bannerID"), session['id'])
        
        for i in range(pullNum): #For every pull
            rates=[95.0, 4.5, 0.5] #Set Base Rates
            rateup = 0 #reset rateup flag
            #Pity Check
            pities =  sorted(pities, key=lambda x: len(x["rarity"]))#Sort pity by rarity so the highest priority pities will be processed last
            for pity in pities:
                #If pity wont be hit this pull, continue to next pity
                if pity["count"] + 1 < pity["maximum"]:
                    pity["count"] = pity["count"] + 1
                    continue
                #If pity is hit, change rate according to rarity
                if pity["rarity"] == "SSR":
                    rates = [0, 0, 100]
                elif pity["rarity"] == "SR":
                    rates = [0, 99.5, 0.5]

                if pity["rateup_exists"] != None:
                    rateup = 1
                pity["count"] = 0

            

            #Roll Rarity
            pullRarity = random.choices(["R", "SR", "SSR"], weights=rates)[0]  
            for pity in pities:
                if pity["rateup_exists"] != None and pity["rarity"] == pullRarity and random.choice([0, 1]) == 1: 
                    #50% to set rateup flag to 1 if a rateup exists and the rarity is for this pity
                    rateup = 1

            #Roll Unit
            eligible = [
                unit
                for unit in pool
                if unit["rarity"] == pullRarity and unit["rateup"] == rateup
            ]
            if not eligible:
                return redirect("/")
            pulledUnits.append(random.choice(eligible))
          
        #Update database with pulled units
        for unit in pulledUnits:
            if unit["copies"] == None: #First time pulling this unit
                    sqlite_helper.create_collection_entry(cur, session['id'], unit["id"])
                    #TODO This doesn't work 
                    unit["copies"] = 0 #manually change copies so this isn't triggered again in the same pull
            else:
                sqlite_helper.update_collection_entry(cur, session['id'], unit["id"])
        
        # Update database with new pity counts
        for pity in pities:
            sqlite_helper.update_pity(cur, pity["count"], pity["id"], session['id'])

    current_user, currencies = user.load_user()
    return render_template("pull.html", current_user=current_user, units=pulledUnits, pullNum=pullNum, bannerID=bannerID, currencies=currencies)


@app.route("/collection", methods=["GET", "POST"])
def collection():
    if 'token' not in session: 
        return redirect("/")
    current_user, currencies = user.load_user()

    if request.method == "GET":
        units = []
        with sqlite3.connect(Config.DATABASE_URI) as con:
            con.row_factory = sqlite_helper.dict_factory
            cur = con.cursor()
            units = sqlite_helper.get_collection(cur, session['id'])
            
        return render_template("collection.html", current_user=current_user, units=units, currencies=currencies)
    elif request.method == "POST":
        user.sacrifice_request(request)
        
        return redirect("/collection")

@app.route("/store", methods=["GET"])
def store():
    if 'token' not in session:
        return redirect("/")
    current_user, currencies = user.load_user()

    return render_template(
        "store.html",
        current_user=current_user,
        currencies=currencies,
        store_products=STORE_PRODUCTS,
        paypal_client_id=Config.PAYPAL_CLIENT_ID,
    )


@app.route("/api/orders", methods=["POST"])
def create_order():
    if 'token' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    request_body = request.get_json()
    if not request_body:
        return jsonify({"error": "Invalid request"}), 400

    product_id = str(request_body.get("product_id", ""))
    product = STORE_PRODUCTS.get(product_id)
    if not product:
        return jsonify({"error": "Unknown product"}), 400

    custom_id = json.dumps({"user_id": session["id"], "product_id": product_id})

    order = orders_controller.orders_create(
        {
            "body": OrderRequest(
                intent=CheckoutPaymentIntent.CAPTURE,
                purchase_units=[
                    PurchaseUnitRequest(
                        amount=AmountWithBreakdown(
                            currency_code="GBP",
                            value=product["price"],
                        ),
                        custom_id=custom_id,
                    )
                ],
            )
        }
    )
    return ApiHelper.json_serialize(order.body)


@app.route("/api/orders/<order_id>/capture", methods=["POST"])
def capture_order(order_id):
    if 'token' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    order = orders_controller.orders_capture(
        {"id": order_id, "prefer": "return=representation"}
    )
    order_data = json.loads(ApiHelper.json_serialize(order.body))

    capture = (
        order_data.get("purchase_units", [{}])[0]
        .get("payments", {})
        .get("captures", [{}])[0]
    )
    if capture.get("status") != "COMPLETED":
        return jsonify(order_data)

    capture_id = capture.get("id", "")
    custom_id_raw = order_data.get("purchase_units", [{}])[0].get("custom_id", "")
    try:
        meta = json.loads(custom_id_raw)
        pay_user_id = meta["user_id"]
        product_id = meta["product_id"]
    except (json.JSONDecodeError, KeyError, TypeError):
        logging.error("Bad custom_id on captured order %s: %s", order_id, custom_id_raw)
        return jsonify(order_data)

    product = STORE_PRODUCTS.get(product_id)
    if not product:
        logging.error("Unknown product_id %s in captured order %s", product_id, order_id)
        return jsonify(order_data)

    with sqlite3.connect(Config.DATABASE_URI) as con:
        cur = con.cursor()
        already = cur.execute(
            "SELECT 1 FROM paypal_captures WHERE capture_id = ?", (capture_id,)
        ).fetchone()
        if not already:
            cur.execute(
                "INSERT INTO paypal_captures (capture_id, order_id, user_id, product_id) VALUES (?, ?, ?, ?)",
                (capture_id, order_id, pay_user_id, product_id),
            )
            sqlite_helper.change_currency(
                cur, product["currency_amount"], pay_user_id, product["currency_id"]
            )

    return jsonify(order_data)


@app.route("/missions", methods=["GET", "POST"])
def missions():
    if 'token' not in session:
        return redirect("/")
    current_user, currencies = user.load_user()

    missions = user.get_user_missions(session["id"]) #Load user missions

    if request.method == "GET": #If GET, load page and check daily login
        with sqlite3.connect(Config.DATABASE_URI) as con:
            cur = con.cursor()
            for mission in missions:
                if user.check_mission_reset(mission):
                    user.reset_mission(cur, mission["mission_id"], session["id"])
                    #If it's a login mission, immediately complete it
                    if mission["description"] == "Daily Login:" or mission["description"] == "Weekly Login:":
                        user.complete_mission(cur, mission["mission_id"], session["id"], 1)

        #Get missions again for changes
        updated_missions = user.get_user_missions(session["id"])
        return render_template("missions.html", current_user=current_user, currencies=currencies, missions=updated_missions)

    #If POST, mission has been claimed
    if not request.form.get("mission_id"): #If doesn't exist, exit
        return redirect("/missions")
    
    try:
        #Get the claimed mission id from form
        claimed_mission = next((mission for mission in missions if mission["mission_id"] == int(request.form.get("mission_id"))), None)
        if claimed_mission["claimed"] == 1  or claimed_mission["count"] < claimed_mission["requirement"]: #If not claimable, exit
            return redirect("/missions")
    except Exception as e: #If None, or int conversion fails, exit
        print(e)
        return redirect("/missions")
    
    #Claim Mission
    with sqlite3.connect(Config.DATABASE_URI) as con:
        cur = con.cursor()
        sqlite_helper.claim_mission(cur, session["id"], claimed_mission)
    return redirect("/missions")