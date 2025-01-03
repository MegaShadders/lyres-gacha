from flask import Flask, render_template, request, redirect, session
import random
import sqlite3
from config import CLIENT_SECRET, TOKEN, REDIRECT_URI, OAUTH_URL, SESSION_KEY, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET
from zenora import APIClient
import user

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


app = Flask(__name__)
app.config["SECRET_KEY"] = SESSION_KEY
client = APIClient(TOKEN, client_secret=CLIENT_SECRET)

paypal_client: PaypalServersdkClient = PaypalServersdkClient(
    client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
        o_auth_client_id=PAYPAL_CLIENT_ID,
        o_auth_client_secret=PAYPAL_CLIENT_SECRET,
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



@app.route("/")
def index():
    if 'token' not in session: 
        return redirect(OAUTH_URL)
    current_user, session['currencies'] = user.load_user()

    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        banners = cur.execute("SELECT id FROM banners WHERE active == 1").fetchall()
        
    return render_template("index.html", current_user=current_user, banners=banners, currencies=session['currencies'])


@app.route("/oauth/callback")
def callback():
    try:
        code = request.args['code']
        access_token = client.oauth.get_access_token(code, REDIRECT_URI).access_token
        session['token'] = access_token
    except:
        return redirect("/")
    
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        bearer_client = APIClient(session.get('token'), bearer=True)
        current_user = bearer_client.users.get_current_user()
        #If discord id does not exist insert new user in db
        if cur.execute("SELECT EXISTS(SELECT id FROM users WHERE id = ?)", (current_user.id,)).fetchone()[0] == 0:
            cur.execute("INSERT INTO users (id, username) VALUES(?, ?)", [current_user.id, current_user.username])
            #Create Pity Entries
            cur.execute("INSERT INTO user_pity (user_id, pity_id, count, rateup_pity) SELECT ?, id, 0, rateup_exists FROM pity", (current_user.id,))
            #Create Currency Entries
            cur.execute("INSERT INTO user_currency (user_id, currency_id, amount) SELECT ?, id, 0 FROM currency", (current_user.id,))
        session['id'] = current_user.id
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/pull", methods=["GET", "POST"])
def pull():
    if 'token' not in session: 
        return redirect("/")
    current_user, session['currencies'] = user.load_user()
    
    if request.method == "GET":
        return redirect("/")
    if not request.form.get("bannerID"):
        return redirect("/")
    if not request.form.get("pullNum"):
        return redirect("/")
    
    units = []
    bannerID = int(request.form.get("bannerID"))
    pullNum = int(request.form.get("pullNum"))

    if session['currencies'][bannerID - 1][0] < (160 * pullNum):
        return redirect("/") 
    
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        pool = cur.execute("""SELECT id, rarity, copies, rateup
                            FROM units
                            INNER JOIN banner_units ON units.id = banner_units.unit_id
                            LEFT JOIN collections ON banner_units.unit_id = collections.unit_id AND collections.user_id = ?
                            WHERE banner_id = ?""", (current_user.id, bannerID)).fetchall()
        #pool = cur.execute("SELECT id, rarity, copies, rateup FROM (SELECT id, rarity, rateup FROM units LEFT JOIN (SELECT unit_id, rateup FROM banner_units WHERE banner_id = ?) ON unit_id = id WHERE id IN (SELECT unit_id FROM banner_units WHERE banner_id = ?)) LEFT JOIN (SELECT unit_id, copies FROM collections WHERE user_id = ?) ON unit_id = id", [request.form.get("bannerID"), request.form.get("bannerID"), session['id']]).fetchall()
        pity = cur.execute("SELECT id, rarity, count, maximum, rateup_pity FROM pity INNER JOIN user_pity ON pity.id = user_pity.pity_id WHERE id IN (SELECT pity_id FROM banner_pity WHERE banner_id = ?) AND user_id = ?", [request.form.get("bannerID"), session['id']]).fetchall()
        
        counts = [x[2] for x in pity] #Puts the counts for every pity in a list
        for i in range(int(request.form.get("pullNum"))): #For every pull
            rates=[94.3, 5.1, 0.6] #Set Base Rates
            rateup = 0 #reset rateup
            #Pity Check
            pityRarity = ""
            for j in range(len(pity)): #Check each pity
                if counts[j] + 1 >= pity[j][3]: #If count + 1 = maximum
                    if pity[j][1] == "SSR":
                        pityRarity = "SSR"
                    elif pity[j][1] == "SR":
                        pityRarity = "SR"
                counts[j] = counts[j] + 1

                match pityRarity: #Change rate according to pity met
                    case "SSR":
                        rates = [0, 0, 100]
                    case "SR":
                        rates = [0, 99.4, 0.6]
                        
            # Roll
            pullRarity = random.choices(["R", "SR", "SSR"], weights=rates)[0]
            for j in range(len(pity)): #For every pity    
                if pity[j][1] == pullRarity: #If this pull was for the rarity of the pity
                    counts[j] = 0 #reset pity                   
                    if pity[j][4] != None: #if a rateup exists
                        rateup = pity[j][4] #Assign the rateup
                        if rateup == 0: #If this is not guaranteed 50/50 win
                            rateup = random.choice([0, 1]) #50% chance to win rateup
                        #Fix rateup for next pull
                        if rateup == 1:
                            pity[j] = (pity[j][0], pity[j][1], pity[j][2], pity[j][3], 0) #if rateup won reset to 0
                        elif rateup == 0:
                            pity[j] = (pity[j][0], pity[j][1], pity[j][2], pity[j][3], 1) #if rateup lost (and exists) set to 1 to win the next
                    else:
                        rateup = 0 #If a rateup doesn't exist assign 0, the default rateup value in database
            units.append(random.choice([x for x in pool if x[1] == pullRarity and x[3] == rateup])) #Random choice between applicable units.
            

                
                    
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
            cur.execute("UPDATE user_pity SET count = ?, rateup_pity = ? WHERE pity_id = ? AND user_id = ?", [counts[k], pity[k][4], pity[k][0], session['id']])  
        
        #Update database and session with new currency amounts
        cur.execute("UPDATE user_currency SET amount = ? WHERE user_id = ? AND currency_id = ?", (session['currencies'][bannerID - 1][0] - (160 * pullNum), current_user.id, int(request.form.get("bannerID"))))
        session['currencies'] = cur.execute("SELECT amount FROM user_currency WHERE user_id = ?", (current_user.id,)).fetchall()
    return render_template("pull.html", current_user=current_user, units=units, pullNum=request.form.get("pullNum"), bannerID=request.form.get("bannerID"), currencies=session['currencies'])


@app.route("/collection", methods=["GET", "POST"])
def collection():
    if 'token' not in session: 
        return redirect("/")
    current_user, session['currencies'] = user.load_user()

    units = []
    with sqlite3.connect("lyres.db") as con:
        cur = con.cursor()
        units = cur.execute("SELECT id, rarity, copies FROM (SELECT id, rarity FROM units) LEFT JOIN (SELECT unit_id, copies FROM collections WHERE user_id = ?) ON unit_id = id ORDER BY LENGTH(rarity) DESC;", [session['id']]).fetchall()
    return render_template("collection.html", current_user=current_user, units=units, currencies=session['currencies'])


@app.route("/store", methods=["GET", "POST"])
def store():
    if 'token' not in session:
        return redirect("/")
    current_user, session['currencies'] = user.load_user()

    return render_template("store.html", current_user=current_user, currencies=session['currencies'])


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
