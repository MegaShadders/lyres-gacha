from flask import Flask, render_template, request, redirect, session
import random
import sqlite3
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

paypal_client: PaypalServersdkClient = PaypalServersdkClient(
    client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
        o_auth_client_id=Config.PAYPAL_CLIENT_ID,
        o_auth_client_secret=Config.PAYPAL_CLIENT_SECRET,
    ),
    logging_configuration=LoggingConfiguration(
        log_level=logging.INFO,
        # Disable masking of sensitive headers for Sandbox testing.
        # This should be set to True (the default if unset)in production.
        mask_sensitive_headers=False,
        request_logging_config=RequestLoggingConfiguration(
            log_headers=True, log_body=True
        ),
        response_logging_config=ResponseLoggingConfiguration(
            log_headers=True, log_body=True
        ),
    ),
)

orders_controller: OrdersController = paypal_client.orders
payments_controller: PaymentsController = paypal_client.payments


PULL_COST = 160



@app.route("/")
def index():
    if 'token' not in session: 
        return redirect(Config.OAUTH_URL)
    current_user, currencies = user.load_user()

    with sqlite3.connect("lyres.db") as con:
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

    return render_template("index.html", current_user=current_user, banners=banners, currencies=currencies, bannerUnits=sortedUnits, bannerPities=bannerPities)


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
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        #If discord id does not exist insert new user in db
        if user.identify_user(current_user.id) == 0:
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
    
    #if not request.form.get("bannerID") or not request.form.get("pullNum"):
     #   return redirect("/")

    
    pulledUnits = []
    try: 
        bannerID = int(request.form.get("bannerID"))
        pullNum = int(request.form.get("pullNum"))
    except (TypeError, ValueError):
        return redirect("/")


    #This will break if a 3rd currency is created
    currencyIndex = min(1, bannerID-1)
    if currencies[currencyIndex]["amount"] < (PULL_COST * pullNum):
        return redirect("/") 
    
    with sqlite3.connect("lyres.db") as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()

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
            pulledUnits.append(random.choice([unit for unit in pool if unit["rarity"] == pullRarity and unit["rateup"] == rateup])) #Random choice between applicable units.
          
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
        
        #Update database with new currency amounts
        sqlite_helper.change_currency(cur, -(PULL_COST * pullNum), current_user.id, currencyIndex+1) 

    current_user, currencies = user.load_user()
    return render_template("pull.html", current_user=current_user, units=pulledUnits, pullNum=pullNum, bannerID=bannerID, currencies=currencies)


@app.route("/collection", methods=["GET", "POST"])
def collection():
    if 'token' not in session: 
        return redirect("/")
    current_user, currencies = user.load_user()

    if request.method == "GET":
        units = []
        with sqlite3.connect("lyres.db") as con:
            con.row_factory = sqlite_helper.dict_factory
            cur = con.cursor()
            units = sqlite_helper.get_collection(cur, session['id'])
            
        return render_template("collection.html", current_user=current_user, units=units, currencies=currencies)
    elif request.method == "POST":
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
            exponentialReward =  (PULL_COST * 2**rarityMod) * 2**(exponentialAmt-1) #160*2^{0, 1, 2} * 2^{0-5}
            linearReward = linearAmt * exponentialReward # 0 if sacriAmt <= 5
            reward = exponentialReward + linearReward
            
            sqlite_helper.sacrifice_copies(cur, sacriUnit, session["id"], sacriAmt)
            sqlite_helper.change_currency(cur, reward, session["id"], min(1, rarityMod)+1) #if rarityMod = 0 (R) silver coins, if rarityMod is 1 or higher (SR/SSR), gold coins. +1 for 0 index array into sql table


        return redirect("/collection")

@app.route("/store", methods=["GET"])
def store():
    if 'token' not in session:
        return redirect("/")
    current_user, currencies = user.load_user()

    return render_template("store.html", current_user=current_user, currencies=currencies)


"""
Create an order to start the transaction.

@see https://developer.paypal.com/docs/api/orders/v2/#orders_create
"""
@app.route("/api/orders", methods=["POST"])
def create_order():
    request_body = request.get_json()
    # use the cart information passed from the front-end to calculate the order amount detals
    cart = request_body["cart"]
    order = orders_controller.orders_create(
        {
            "body": OrderRequest(
                intent=CheckoutPaymentIntent.CAPTURE,
                purchase_units=[
                    PurchaseUnitRequest(
                        amount=AmountWithBreakdown(
                            currency_code="GBP",
                            value=cart[0]['price'],
                        ),

                    )
                ],

            )
        }
    )
    return ApiHelper.json_serialize(order.body)



"""

Capture payment for the created order to complete the transaction.

@see https://developer.paypal.com/docs/api/orders/v2/#orders_capture
"""
@app.route("/api/orders/<order_id>/capture", methods=["POST"])
def capture_order(order_id):
    order = orders_controller.orders_capture(
        {"id": order_id, "prefer": "return=representation"}
    )
    return ApiHelper.json_serialize(order.body)


@app.route("/missions", methods=["GET", "POST"])
def missions():
    if 'token' not in session:
        return redirect("/")
    current_user, currencies = user.load_user()

    missions = user.load_user_missions(session["id"]) #Load user missions

    if request.method == "GET": #If GET, load page
        return render_template("missions.html", current_user=current_user, currencies=currencies, missions=missions)

    #If POST, mission has been claimed
    if not request.form.get("mission_id"): #If doesn't exist, exit
        return redirect("/missions")
    
    try:
        #Get the claimed mission id from form
        claimed_mission = next((mission for mission in missions if mission["id"] == int(request.form.get("mission_id"))), None)
        if claimed_mission["claimable"] == 0: #If not claimable, exit
            return redirect("/missions")
    except: #If None, or int conversion fails, exit
        return redirect("/missions")
    
    #Claim Mission
    sqlite_helper.claim_mission(session["id"], claimed_mission)
    return redirect("/missions")