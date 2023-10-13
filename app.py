"""


Copyright 2023 Mohsen Bizhani

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.


"""



import json as js
import requests
import pandas as pd
from prophet import Prophet
from datetime import date
from datetime import datetime
from flask import Flask, request
from flask import render_template, redirect
from flask import session
import sqlite3 as sql
import secrets


app = Flask(__name__, static_url_path='/static')
app.secret_key = secrets.token_hex(16)



# Make an API request to the Metal Price API to get the latest gold price in USD
def make_metal_request():
    url = "https://api.metalpriceapi.com/v1/latest?api_key=b47e75249e15fe696378bec55ea78567&base=USD&currencies=XAU"
    try:
        response = requests.get(url)
        response.raise_for_status()
        result = js.loads(response.text)
        return result
    except requests.exceptions.RequestException as e:
        print("Error:", str(e))


# Update the database with the latest gold price if it's not already present.
def update_database(data):
    with sql.connect("gold.db") as conn:
        if not data["Date"].dt.date.eq(date.today()).any():
            today = make_metal_request()
            Date = date.today()
            Price = today["rates"]["XAU"]
            Price = float(Price)
            Price = 1 / Price
            new_row = {"Date": Date, "Price": Price}
            new_row = pd.DataFrame([new_row])
            data = pd.concat([data, new_row], ignore_index=True)
            data = data.reset_index(drop=True)
            data["Date"] = data["Date"].apply(lambda x: x.strftime("%Y-%m-%d"))
            new_row.to_sql("gold", conn, if_exists="append", index=False)

# Make a prediction using the Prophet model for the given date.
def make_prediction(model, predicted_date):
    if type(predicted_date) is type(datetime):
        prediction = model.predict(pd.DataFrame({"ds": [predicted_date]}))
    else:
        prediction = model.predict(pd.DataFrame({"ds": [pd.to_datetime(predicted_date)]}))
    predicted_price = prediction["yhat"][0]
    return predicted_price

with sql.connect("gold.db") as conn:
    data = pd.read_sql_query("SELECT * FROM gold", conn)




@app.route("/", methods=["GET", "POST"])
def index():
    data["Date"] = pd.to_datetime(data["Date"])
    if request.method == "POST":
        today_date = date.today()
        if today_date in data["Date"].dt.date.values:
            today_price = data.loc[data["Date"].dt.date == today_date, "Price"].iloc[0]
        else:
            update_database(data)
        model = Prophet()
        model.fit(data.rename(columns={"Date": "ds", "Price": "y"}))
        today_price = data.loc[data["Date"].dt.date == date.today(), "Price"].iloc[0]
        date_str = request.form.get("date")
        predicted_date = datetime.strptime(date_str, "%Y-%m-%d")
        prediction = make_prediction(model, predicted_date)
        session["today"] = today_price
        session["predicted"] = prediction
        session["date"] = date_str
        return redirect("/predict")
    return render_template("index.html")

@app.route("/predict")
def predict():
    today = session.get("today")
    predicted = session.get("predicted")
    predicted_date = session.get("date")
    today_date = date.today().strftime("%Y-%m-%d")
    today_formatted = "{:.2f}".format(today)
    predicted_formatted = "{:.2f}".format(predicted)


    return render_template(
        "predict.html",
        today=today_formatted,
        predicted=predicted_formatted,
        today_date=today_date,
        predicted_date=predicted_date
)



@app.route("/about")
def about():
    return render_template("about.html")
