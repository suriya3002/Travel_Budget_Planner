import os
import sqlite3

import requests
from flask import Flask, jsonify, redirect, render_template, request

ORS_API_KEY = os.environ.get("ORS_API_KEY")

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect("travel_budget.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            destination TEXT,
            travelers INTEGER,
            total_distance REAL,
            transport_mode TEXT,
            transport_cost REAL,
            fuel_type TEXT,
            fuel_price REAL,
            fuel_cost REAL,
            food_cost REAL,
            room_cost REAL,
            toll_charges REAL,
            parking_fee REAL,
            vehicle_type TEXT,
            vehicle_rental_cost REAL,
            places_fee_total REAL,
            total_budget REAL,
            cost_per_person REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_db()


def geocode(place):
    if not place or not place.strip():
        return None
    headers = {"User-Agent": "TravelBudgetPlanner"}
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "json", "limit": 1},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        return None
    return (float(data[0]["lon"]), float(data[0]["lat"]))


def get_int(field):
    try:
        return int(request.form.get(field, 0))
    except (TypeError, ValueError):
        return 0


def get_float(field):
    try:
        return float(request.form.get(field, 0))
    except (TypeError, ValueError):
        return 0.0


def calculate_travel_time(distance, transport_mode):
    speed = {
        "walk": 5,
        "bike": 45,
        "car": 60,
        "bus": 45,
        "train": 80,
        "flight": 700,
    }
    avg_speed = speed.get(transport_mode, 60)
    if distance <= 0:
        return "0 mins"
    total_minutes = int((distance / avg_speed) * 60)
    h, m = divmod(total_minutes, 60)
    if h == 0:
        return f"{m} mins"
    return f"{h} hr {m} mins"


def trip_from_form():
    travelers = get_int("travelers")
    destination = request.form.get("destination", "")
    distance = get_float("distance")
    round_trip = request.form.get("round_trip", "no")
    total_distance = distance * 2 if round_trip == "yes" else distance

    places_to_visit = get_int("places_to_visit")
    per_places_entry_fee = get_float("per_places_entry_fee")
    vehicle_type = request.form.get("vehicle_type", "own")
    vehicle_rental_cost = get_float("vehicle_rental_cost")
    vehicle_cost = vehicle_rental_cost if vehicle_type == "rental" else 0
    parking_fee = get_float("parking_fee")
    mileage = get_float("mileage")
    fuel_type = request.form.get("fuel_type", "petrol")
    fuel_price = 108.85 if fuel_type == "petrol" else 101.60
    transport_mode = request.form.get("transport_mode", "car")
    transport_cost = 0.0
    fuel_cost = 0.0

    if transport_mode == "walk":
        transport_cost = 0
    elif transport_mode in ("bike", "car") and mileage > 0:
        fuel_cost = (total_distance / mileage) * fuel_price
        transport_cost = fuel_cost
    elif transport_mode == "bus":
        rate = get_float("bus_type") or 0.835
        transport_cost = total_distance * rate * travelers
    elif transport_mode == "train":
        rate = get_float("train_type") or 0.40
        transport_cost = total_distance * rate * travelers
    elif transport_mode == "flight":
        rate = get_float("flight_type") or 4.75
        transport_cost = total_distance * rate * travelers

    bus_cost = total_distance * 0.835 * travelers
    train_cost = total_distance * 0.40 * travelers
    flight_cost = total_distance * 4.75 * travelers

    food_cost_per_person = get_float("food_cost_per_person")
    room_cost = get_float("room_cost")

    if transport_mode == "car":
        if distance <= 100:
            toll_charges = 0
        elif distance <= 300:
            toll_charges = 150
        elif distance <= 600:
            toll_charges = 400
        else:
            toll_charges = 700
    else:
        toll_charges = 0

    food_cost = food_cost_per_person * travelers
    places_fee_total = places_to_visit * per_places_entry_fee
    total_budget = (
        transport_cost
        + food_cost
        + room_cost
        + toll_charges
        + parking_fee
        + vehicle_cost
        + places_fee_total
    )
    cost_per_person = total_budget / travelers if travelers > 0 else 0
    travel_time = calculate_travel_time(total_distance, transport_mode)

    return {
        "destination": destination,
        "travelers": travelers,
        "total_distance": round(total_distance, 2),
        "transport_mode": transport_mode,
        "transport_cost": round(transport_cost, 2),
        "fuel_type": fuel_type,
        "fuel_price": fuel_price,
        "fuel_cost": round(fuel_cost, 2),
        "food_cost": round(food_cost, 2),
        "room_cost": round(room_cost, 2),
        "toll_charges": round(toll_charges, 2),
        "parking_fee": round(parking_fee, 2),
        "vehicle_type": vehicle_type,
        "vehicle_rental_cost": round(vehicle_rental_cost, 2),
        "places_fee_total": round(places_fee_total, 2),
        "total_budget": round(total_budget, 2),
        "cost_per_person": round(cost_per_person, 2),
        "travel_time": travel_time,
        "bus_cost": round(bus_cost, 2),
        "train_cost": round(train_cost, 2),
        "flight_cost": round(flight_cost, 2),
        "image_url": (
            "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"
            "?auto=format&fit=crop&w=1200&q=80"
        ),
    }


def save_trip_data(data):
    conn = get_db()
    conn.execute(
        """
        INSERT INTO trips (
            destination, travelers, total_distance, transport_mode,
            transport_cost, fuel_type, fuel_price, fuel_cost, food_cost,
            room_cost, toll_charges, parking_fee, vehicle_type,
            vehicle_rental_cost, places_fee_total, total_budget, cost_per_person
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["destination"],
            data["travelers"],
            data["total_distance"],
            data["transport_mode"],
            data["transport_cost"],
            data["fuel_type"],
            data["fuel_price"],
            data["fuel_cost"],
            data["food_cost"],
            data["room_cost"],
            data["toll_charges"],
            data["parking_fee"],
            data["vehicle_type"],
            data["vehicle_rental_cost"],
            data["places_fee_total"],
            data["total_budget"],
            data["cost_per_person"],
        ),
    )
    conn.commit()
    conn.close()


def update_trip_data(trip_id, data):
    conn = get_db()
    conn.execute(
        """
        UPDATE trips SET
            destination=?, travelers=?, total_distance=?, transport_mode=?,
            transport_cost=?, fuel_type=?, fuel_price=?, fuel_cost=?,
            food_cost=?, room_cost=?, toll_charges=?, parking_fee=?,
            vehicle_type=?, vehicle_rental_cost=?, places_fee_total=?,
            total_budget=?, cost_per_person=?
        WHERE id=?
        """,
        (
            data["destination"],
            data["travelers"],
            data["total_distance"],
            data["transport_mode"],
            data["transport_cost"],
            data["fuel_type"],
            data["fuel_price"],
            data["fuel_cost"],
            data["food_cost"],
            data["room_cost"],
            data["toll_charges"],
            data["parking_fee"],
            data["vehicle_type"],
            data["vehicle_rental_cost"],
            data["places_fee_total"],
            data["total_budget"],
            data["cost_per_person"],
            trip_id,
        ),
    )
    conn.commit()
    conn.close()


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/planner")
def planner():
    return render_template("index.html", edit_mode=False)


@app.route("/trips")
def trips():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM trips ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("trips.html", trips=rows)


@app.route("/edit/<int:trip_id>")
def edit_trip(trip_id):
    conn = get_db()
    trip = conn.execute(
        "SELECT * FROM trips WHERE id=?", (trip_id,)
    ).fetchone()
    conn.close()
    if not trip:
        return redirect("/trips")
    return render_template("edit.html", trip=trip)


@app.route("/delete/<int:trip_id>")
def delete_trip(trip_id):
    conn = get_db()
    conn.execute("DELETE FROM trips WHERE id=?", (trip_id,))
    conn.commit()
    conn.close()
    return redirect("/trips")


def trip_from_result_form():
    return {
        "destination": request.form.get("destination", ""),
        "travelers": get_int("travelers"),
        "total_distance": get_float("total_distance"),
        "transport_mode": request.form.get("transport_mode", "car"),
        "transport_cost": get_float("transport_cost"),
        "fuel_type": request.form.get("fuel_type", "petrol"),
        "fuel_price": get_float("fuel_price"),
        "fuel_cost": get_float("fuel_cost"),
        "food_cost": get_float("food_cost"),
        "room_cost": get_float("room_cost"),
        "toll_charges": get_float("toll_charges"),
        "parking_fee": get_float("parking_fee"),
        "vehicle_type": request.form.get("vehicle_type", "own"),
        "vehicle_rental_cost": get_float("vehicle_rental_cost"),
        "places_fee_total": get_float("places_fee_total"),
        "total_budget": get_float("total_budget"),
        "cost_per_person": get_float("cost_per_person"),
    }


@app.route("/save_trips", methods=["POST"])
def save_trips():
    data = (
        trip_from_result_form()
        if request.form.get("from_result")
        else trip_from_form()
    )
    save_trip_data(data)
    return redirect("/trips")


@app.route("/update_trip", methods=["POST"])
def update_trip():
    trip_id = request.form.get("trip_id")
    if not trip_id:
        return redirect("/trips")
    data = (
        trip_from_result_form()
        if request.form.get("from_result")
        else trip_from_form()
    )
    update_trip_data(int(trip_id), data)
    return redirect("/trips")


@app.route("/get_distance")
def get_distance():
    from_place = request.args.get("from", "").strip()
    destination = request.args.get("destination", "").strip()
    try:
        start = geocode(from_place)
        end = geocode(destination)
    except requests.RequestException:
        return jsonify({"error": "Location search is temporarily unavailable. Please try again."}), 503

    if start is None:
        return jsonify({"error": "Invalid From Location"})
    if end is None:
        return jsonify({"error": "Invalid Destination"})

    # OSRM provides a dependable keyless route estimate.  ORS remains optional
    # for deployments that set ORS_API_KEY.
    try:
        if ORS_API_KEY:
            response = requests.post(
                "https://api.openrouteservice.org/v2/directions/driving-car",
                headers={"Authorization": ORS_API_KEY, "Content-Type": "application/json"},
                json={"coordinates": [list(start), list(end)]},
                timeout=15,
            )
            response.raise_for_status()
            summary = response.json()["routes"][0]["summary"]
        else:
            coordinates = f"{start[0]},{start[1]};{end[0]},{end[1]}"
            response = requests.get(
                f"https://router.project-osrm.org/route/v1/driving/{coordinates}",
                params={"overview": "false"},
                headers={"User-Agent": "TravelBudgetPlanner/1.0"},
                timeout=15,
            )
            response.raise_for_status()
            route = response.json().get("routes", [None])[0]
            if not route:
                raise ValueError("No route found")
            summary = route
        return jsonify({
            "distance": round(summary["distance"] / 1000, 2),
            "duration": round(summary["duration"] / 3600, 2),
        })
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return jsonify({"error": "We couldn't find a drivable route between those locations."}), 422


@app.route("/location_suggestions")
def location_suggestions():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 5, "addressdetails": 1},
            headers={"User-Agent": "TravelBudgetPlanner/1.0 (local planner)"},
            timeout=10,
        )
        response.raise_for_status()
        return jsonify([
            {"label": place["display_name"], "lat": place["lat"], "lon": place["lon"]}
            for place in response.json()
        ])
    except requests.RequestException:
        return jsonify([]), 503


@app.route("/reverse_geocode")
def reverse_geocode():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
    headers = {"User-Agent": "TravelBudgetPlanner"}
    try:
        result = requests.get(url, headers=headers, timeout=10)
        result.raise_for_status()
        return jsonify({"location": result.json().get("display_name", "")})
    except requests.RequestException:
        return jsonify({"error": "Could not identify your current location."}), 503


@app.route("/calculate", methods=["POST"])
def calculate():
    data = trip_from_form()
    trip_id = request.form.get("trip_id")
    return render_template(
        "result.html",
        **data,
        trip_id=trip_id,
        edit_mode=bool(trip_id),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
