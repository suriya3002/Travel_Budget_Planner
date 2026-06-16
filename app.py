from flask import Flask, render_template, request, jsonify
from geopy.geocoders import Nominatim
import openrouteservice

app = Flask(__name__)

# -----------------------------
# OpenRouteService API Key
# -----------------------------
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjE4NTE1ZmM3ZTY0ODRkZjk4YWMzYzVkM2YwZDYxNzU5IiwiaCI6Im11cm11cjY0In0="


# -----------------------------
# Helper Functions
# -----------------------------
def get_int(field):
    try:
        return int(request.form.get(field, 0))
    except:
        return 0


def get_float(field):
    try:
        return float(request.form.get(field, 0))
    except:
        return 0.0


# -----------------------------
# Home Page
# -----------------------------
@app.route('/')
def home():
    return render_template('index.html')


# -----------------------------
# Distance API
# -----------------------------
@app.route('/get_distance')
def get_distance():

    destination = request.args.get('destination')
    user_lat = request.args.get('lat')
    user_lon = request.args.get('lon')

    if not destination:
        return jsonify({"distance": 0})

    try:

        geolocator = Nominatim(
            user_agent="travel_budget_planner"
        )

        location = geolocator.geocode(destination)

        if not location:
            return jsonify({"distance": 0})

        dest_lat = location.latitude
        dest_lon = location.longitude

        client = openrouteservice.Client(
            key=ORS_API_KEY
        )

        route = client.directions(
            coordinates=[
                (float(user_lon), float(user_lat)),
                (dest_lon, dest_lat)
            ],
            profile='driving-car',
            format='geojson'
        )

        summary = route['features'][0]['properties']['summary']

        distance = round(
            summary['distance'] / 1000,
            2
        )

        duration = round(
            summary['duration'] / 3600,
            2
        )

        return jsonify({
            "distance": distance,
            "duration": duration,
            "dest_lat": dest_lat,
            "dest_lon": dest_lon
        })

    except Exception as e:
        print("Route Error:", e)

        return jsonify({
            "distance": 0,
            "duration": 0
        })


# -----------------------------
# Budget Calculation
# -----------------------------
@app.route('/calculate', methods=['POST'])
def calculate():

    travelers = get_int('travelers')
    destination = request.form.get('destination', '')

    distance = get_float('distance')

    round_trip = request.form.get('round_trip', 'no')

    if round_trip == "yes":
        total_distance = distance * 2
    else:
        total_distance = distance

    # Places
    places_to_visit = get_int('places_to_visit')
    per_places_entry_fee = get_float('per_places_entry_fee')

    # Vehicle
    vehicle_type = request.form.get('vehicle_type', 'own')
    vehicle_rental_cost = get_float('vehicle_rental_cost')

    vehicle_cost = (
        vehicle_rental_cost
        if vehicle_type == "rental"
        else 0
    )

    parking_fee = get_float('parking_fee')

    # Fuel
    mileage = get_float('mileage')

    fuel_type = request.form.get(
        'fuel_type',
        'petrol'
    )

    fuel_price = (
        108.85
        if fuel_type == "petrol"
        else 101.60
    )

    # Transport Mode
    transport_mode = request.form.get(
        "transport_mode",
        "car"
    )

    transport_cost = 0
    fuel_cost = 0

    if transport_mode == "walk":

        transport_cost = 0

    elif transport_mode in ["bike", "car"]:

        if mileage > 0:

            fuel_cost = (
                total_distance / mileage
            ) * fuel_price

            transport_cost = fuel_cost

    elif transport_mode == "bus":

        rate = float(
            request.form.get(
                "bus_type",
                0.835   # Govt Ordinary default (avg ₹0.67–1.0/km)
            )
        )

        transport_cost = (
            total_distance *
            rate *
            travelers
        )

    elif transport_mode == "train":

        rate = float(
            request.form.get(
                "train_type",
                0.40    # General/2S default (avg ₹0.30–0.50/km)
            )
        )

        transport_cost = (
            total_distance *
            rate *
            travelers
        )

    elif transport_mode == "flight":

        rate = float(
            request.form.get(
                "flight_type",
                4.75    # Budget LCC default (avg ₹3.5–6.0/km)
            )
        )

        transport_cost = (
            total_distance *
            rate *
            travelers
        )

    # Other Costs
    food_cost_per_person = get_float(
        'food_cost_per_person'
    )

    room_cost = get_float('room_cost')

    # Toll
    if transport_mode in ["car", "bike"]:

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

    food_cost = (
        food_cost_per_person *
        travelers
    )

    places_fee_total = (
        places_to_visit *
        per_places_entry_fee
    )

    total_budget = (
        transport_cost +
        food_cost +
        room_cost +
        toll_charges +
        parking_fee +
        vehicle_cost +
        places_fee_total
    )

    cost_per_person = (
        total_budget / travelers
        if travelers > 0
        else 0
    )

    image_url = (
        "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"
        "?auto=format&fit=crop&w=1200&q=80"
    )

    return render_template(
        'result.html',
        destination=destination,
        travelers=travelers,
        total_distance=round(total_distance, 2),
        transport_mode=transport_mode,
        transport_cost=round(transport_cost, 2),
        fuel_type=fuel_type,
        fuel_price=fuel_price,
        fuel_cost=round(fuel_cost, 2),
        food_cost=round(food_cost, 2),
        room_cost=round(room_cost, 2),
        toll_charges=round(toll_charges, 2),
        parking_fee=round(parking_fee, 2),
        vehicle_type=vehicle_type,
        vehicle_rental_cost=round(vehicle_rental_cost, 2),
        places_fee_total=round(places_fee_total, 2),
        total_budget=round(total_budget, 2),
        cost_per_person=round(cost_per_person, 2),
        image_url=image_url
    )


if __name__ == '__main__':
    app.run(debug=True)