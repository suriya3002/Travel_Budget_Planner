import os
import sqlite3
from functools import wraps

import requests
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

ORS_API_KEY = os.environ.get("ORS_API_KEY")
GOOGLE_DIRECTIONS_API_KEY = os.environ.get("GOOGLE_DIRECTIONS_API_KEY")
GOOGLE_MAPS_JS_API_KEY = os.environ.get("GOOGLE_MAPS_JS_API_KEY")
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

INDIAN_CITY_SUGGESTIONS = (
    "Agra, Uttar Pradesh, India", "Ahmedabad, Gujarat, India",
    "Bengaluru, Karnataka, India", "Bhopal, Madhya Pradesh, India",
    "Chandigarh, India", "Chennai, Tamil Nadu, India",
    "Coimbatore, Tamil Nadu, India", "Delhi, India", "Goa, India",
    "Hyderabad, Telangana, India", "Jaipur, Rajasthan, India",
    "Kochi, Kerala, India", "Kolkata, West Bengal, India",
    "Lucknow, Uttar Pradesh, India", "Mumbai, Maharashtra, India",
    "Munnar, Kerala, India", "Mysuru, Karnataka, India",
    "Pune, Maharashtra, India", "Shimla, Himachal Pradesh, India",
    "Thiruvananthapuram, Kerala, India", "Varanasi, Uttar Pradesh, India",
)


ENTRY_FEE_BY_TIER = {"premium": 250, "mid": 150, "standard": 80}
HOTEL_PRICE_MULTIPLIERS = {0: 0.75, 1: 0.9, 2: 1.0, 3: 1.45, 4: 2.2}


def location_cost_estimate(destination):
    """Daily INR budget estimate by destination tier; users can edit it."""
    place = (destination or "").lower()
    premium = ("mumbai", "delhi", "bengaluru", "goa", "manali", "munnar", "shimla")
    mid_range = ("chennai", "hyderabad", "kolkata", "pune", "jaipur", "kochi", "agra", "mysuru")
    if any(city in place for city in premium):
        return {
            "food": 900,
            "room": 3500,
            "tier": "Popular / premium destination",
            "tier_key": "premium",
        }
    if any(city in place for city in mid_range):
        return {
            "food": 700,
            "room": 2500,
            "tier": "City / tourist destination",
            "tier_key": "mid",
        }
    return {"food": 550, "room": 1800, "tier": "Standard India estimate", "tier_key": "standard"}


def hotel_rate_from_price_level(base_room, price_level):
    multiplier = HOTEL_PRICE_MULTIPLIERS.get(price_level, 1.0)
    return round(base_room * multiplier)


def attach_photo_urls(places):
    for place in places:
        reference = place.pop("photo", "")
        place["image_url"] = url_for("place_photo", reference=reference) if reference else ""
    return places


def destination_budget_details(destination, trip_days):
    """Fetch tourist places and hotels at the destination with estimated costs."""
    estimate = location_cost_estimate(destination)
    tier_key = estimate["tier_key"]
    entry_fee = ENTRY_FEE_BY_TIER[tier_key]
    base_room = estimate["room"]

    attractions = []
    hotels = []
    try:
        coordinates = geocode(destination)
        if coordinates:
            attractions = find_attractions(coordinates, radius=12000, limit=5)
            hotels = find_lodging(coordinates, radius=12000, limit=4)
    except requests.RequestException:
        pass

    for place in attractions:
        place["entry_fee"] = entry_fee

    for hotel in hotels:
        hotel["price_per_night"] = hotel_rate_from_price_level(
            base_room, hotel.get("price_level", 2)
        )

    attach_photo_urls(attractions)
    attach_photo_urls(hotels)

    if not attractions:
        place_name = short_location(destination) or "your destination"
        attractions = [
            {
                "name": f"{place_name} — suggested sight {index}",
                "address": destination,
                "rating": None,
                "entry_fee": entry_fee,
                "image_url": "",
            }
            for index in range(1, 4)
        ]

    places_fee_total = sum(place["entry_fee"] for place in attractions)
    places_count = len(attractions)
    per_place_fee = entry_fee

    if hotels:
        room_per_day = round(sum(hotel["price_per_night"] for hotel in hotels) / len(hotels))
    else:
        place_name = short_location(destination) or "your destination"
        hotels = [
            {
                "name": f"{place_name} — budget stay",
                "address": destination,
                "rating": None,
                "price_per_night": hotel_rate_from_price_level(base_room, 1),
                "image_url": "",
            },
            {
                "name": f"{place_name} — mid-range hotel",
                "address": destination,
                "rating": None,
                "price_per_night": base_room,
                "image_url": "",
            },
        ]
        room_per_day = round(sum(hotel["price_per_night"] for hotel in hotels) / len(hotels))

    return {
        "attractions": attractions,
        "hotels": hotels,
        "places_count": places_count,
        "places_fee_total": places_fee_total,
        "per_place_fee": per_place_fee,
        "room_per_day": room_per_day,
        "room_total": room_per_day * max(trip_days, 1),
        "tier_label": estimate["tier"],
    }

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "change-this-development-key")


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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add optional admin, active flags and last_seen to users table if not present
    user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "is_admin" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if "is_active" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
    if "last_seen" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")

    # Ensure trips reference users (user_id)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(trips)")}
    if "user_id" not in columns:
        conn.execute("ALTER TABLE trips ADD COLUMN user_id INTEGER")

    # Audit logs for admin actions (deletions, etc.)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            action TEXT,
            target_user_id INTEGER,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


@app.before_request
def update_last_seen():
    # Update a simple last_seen timestamp so admins can see active members.
    user_id = session.get('user_id')
    if user_id:
        try:
            conn = get_db()
            conn.execute('UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
        except Exception:
            # Non-fatal: best-effort update, do not block requests on this
            pass


@app.context_processor
def inject_user():
    """Inject small helpers into templates: whether current user is admin and logged_in flag."""
    is_admin = False
    logged_in = 'user_id' in session
    user_name = session.get('user_name')
    if logged_in:
        try:
            conn = get_db()
            row = conn.execute('SELECT is_admin FROM users WHERE id=?', (session['user_id'],)).fetchone()
            conn.close()
            is_admin = bool(row and row.get('is_admin'))
        except Exception:
            is_admin = False
    return dict(is_admin=is_admin, logged_in=logged_in, user_name=user_name)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


def require_admin(view):
    """Decorator to ensure the current session user is an admin.
    Uses the users table is_admin column (0/1)."""
    @wraps(view)
    def wrapped_admin(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        conn = get_db()
        user = conn.execute("SELECT is_admin FROM users WHERE id=?", (session["user_id"],)).fetchone()
        conn.close()
        if not user or not user.get("is_admin"):
            # Non-admins should see 403 Forbidden
            return Response("Forbidden", status=403)
        return view(*args, **kwargs)
    return wrapped_admin


def geocode(place):
    if not place or not place.strip():
        return None
    headers = {"User-Agent": "TravelBudgetPlanner"}
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "json", "limit": 1, "countrycodes": "in"},
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
        "bike": 80,
        "car": 100,
        "bus": 90,
        "train": 110,
        "flight": 800,
    }
    avg_speed = speed.get(transport_mode, 60)
    if distance <= 0:
        return "0 mins"
    total_minutes = int((distance / avg_speed) * 60)
    h, m = divmod(total_minutes, 60)
    if h == 0:
        return f"{m} mins"
    return f"{h} hr {m} mins"


def calculate_emissions(distance, transport_mode):
    """Estimate kg CO2e for this trip; values are per passenger-kilometre."""
    factors = {
        "walk": 0,
        "bike": 0.103,
        "car": 0.192,
        "bus": 0.105,
        "train": 0.041,
        "flight": 0.255,
    }
    return round(distance * factors.get(transport_mode, 0), 2)


def short_location(location):
    return (location or "").split(",")[0].strip()


def trip_from_form():
    travelers = get_int("travelers")
    destination = request.form.get("destination", "")
    from_location = request.form.get("from_location", "")
    distance = get_float("distance")
    trip_days = max(get_int("trip_days"), 1)
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
    room_cost_per_day = get_float("room_cost")

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

    destination_details = destination_budget_details(destination, trip_days)

    if destination_details["places_count"] > 0:
        places_to_visit = destination_details["places_count"]
        per_places_entry_fee = destination_details["per_place_fee"]
        places_fee_total = destination_details["places_fee_total"]
        places_from_destination = True
    else:
        places_fee_total = places_to_visit * per_places_entry_fee
        places_from_destination = False

    if destination_details["hotels"]:
        room_cost_per_day = destination_details["room_per_day"]
        room_from_destination = True
    else:
        room_from_destination = False

    food_cost = food_cost_per_person * travelers * trip_days
    room_cost = room_cost_per_day * trip_days
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
    # Reuse the exact Travel Time shown in the planner. This prevents the
    # result page from showing a differently rounded/recalculated value.
    travel_time = request.form.get("travel_time", "").strip()
    if not travel_time:
        travel_time = calculate_travel_time(total_distance, transport_mode)
    emissions_kg = calculate_emissions(total_distance, transport_mode)
    # A simple, distance-sensitive impact indicator: 100 kg CO2e equals 100%.
    pollution_percent = min(round(emissions_kg, 1), 100)
    comparison_costs = {
        "walk": 0,
        "bike": round((total_distance / (mileage or 45)) * fuel_price, 2),
        "car": round((total_distance / (mileage or 15)) * fuel_price, 2),
        "bus": round(bus_cost, 2),
        "train": round(train_cost, 2),
        "flight": round(flight_cost, 2),
    }
    mode_impacts = [
        {
            "mode": mode,
            "label": mode.capitalize(),
            "cost": comparison_costs[mode],
            "emissions": calculate_emissions(total_distance, mode),
        }
        for mode in ("walk", "bike", "car", "bus", "train", "flight")
    ]
    eco_choice = min(mode_impacts, key=lambda item: item["emissions"])
    economy_choice = min(mode_impacts, key=lambda item: item["cost"])

    return {
        "from_location": from_location,
        "from_short": short_location(from_location),
        "destination": destination,
        "destination_short": short_location(destination),
        "travelers": travelers,
        "trip_days": trip_days,
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
        "emissions_kg": emissions_kg,
        "pollution_percent": pollution_percent,
        "mode_impacts": mode_impacts,
        "eco_choice": eco_choice,
        "economy_choice": economy_choice,
        "bus_cost": round(bus_cost, 2),
        "train_cost": round(train_cost, 2),
        "flight_cost": round(flight_cost, 2),
        "image_url": (
            "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"
            "?auto=format&fit=crop&w=1200&q=80"
        ),
        "destination_attractions": destination_details["attractions"],
        "destination_hotels": destination_details["hotels"],
        "destination_tier": destination_details["tier_label"],
        "places_from_destination": places_from_destination,
        "room_from_destination": room_from_destination,
        "places_to_visit": places_to_visit,
        "per_places_entry_fee": round(per_places_entry_fee, 2),
    }


def save_trip_data(data, user_id):
    conn = get_db()
    conn.execute(
        """
        INSERT INTO trips (
            destination, travelers, total_distance, transport_mode,
            transport_cost, fuel_type, fuel_price, fuel_cost, food_cost,
            room_cost, toll_charges, parking_fee, vehicle_type,
            vehicle_rental_cost, places_fee_total, total_budget, cost_per_person, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            user_id,
        ),
    )
    conn.commit()
    conn.close()


def update_trip_data(trip_id, data, user_id):
    conn = get_db()
    conn.execute(
        """
        UPDATE trips SET
            destination=?, travelers=?, total_distance=?, transport_mode=?,
            transport_cost=?, fuel_type=?, fuel_price=?, fuel_cost=?,
            food_cost=?, room_cost=?, toll_charges=?, parking_fee=?,
            vehicle_type=?, vehicle_rental_cost=?, places_fee_total=?,
            total_budget=?, cost_per_person=?
        WHERE id=? AND user_id=?
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
            user_id,
        ),
    )
    conn.commit()
    conn.close()


@app.route("/")
def landing():
    return render_template("landing.html", logged_in="user_id" in session)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("planner"))
    error = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or "@" not in email or len(password) < 8:
            error = "Enter your name, a valid email, and a password with at least 8 characters."
        else:
            conn = get_db()
            try:
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
                conn.commit()
                new_id = cursor.lastrowid
                # If there are no other admins, make the first user an admin (convenience for initial setup)
                admin_exists = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin=1").fetchone()[0]
                if not admin_exists:
                    conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (new_id,))
                    conn.commit()
                session["user_id"] = new_id
                session["user_name"] = name
                return redirect(url_for("planner"))
            except sqlite3.IntegrityError:
                error = "An account with that email already exists. Please sign in."
            finally:
                conn.close()
    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("planner"))
    error = ""
    next_page = request.values.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            # Prevent login for soft-deleted/inactive users
            if user.get("is_active") == 0:
                error = "This account has been deactivated. Please contact an administrator."
            else:
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                return redirect(next_page if next_page.startswith("/") and not next_page.startswith("//") else url_for("planner"))
        else:
            error = "Email or password is incorrect."
    return render_template("login.html", error=error, next_page=next_page)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/planner")
@login_required
def planner():
    return render_template(
        "index.html",
        edit_mode=False,
        google_maps_js_api_key=GOOGLE_MAPS_JS_API_KEY,
    )


@app.route("/trips")
@login_required
def trips():
    search_query = request.args.get("q", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 8
    where_clause = ""
    params = []
    if search_query:
        where_clause = "WHERE user_id = ? AND (destination LIKE ? OR transport_mode LIKE ?)"
        term = f"%{search_query}%"
        params = [session["user_id"], term, term]
    else:
        where_clause = "WHERE user_id = ?"
        params = [session["user_id"]]
    conn = get_db()
    total = conn.execute(
        f"SELECT COUNT(*) FROM trips {where_clause}", params
    ).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    rows = conn.execute(
        f"SELECT * FROM trips {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    conn.close()
    return render_template(
        "trips.html", trips=rows, search_query=search_query, page=page,
        total_pages=total_pages, total=total,
        first_item=(page - 1) * per_page + 1 if total else 0,
    )


@app.route("/edit/<int:trip_id>")
@login_required
def edit_trip(trip_id):
    conn = get_db()
    trip = conn.execute(
        "SELECT * FROM trips WHERE id=? AND user_id=?", (trip_id, session["user_id"])
    ).fetchone()
    conn.close()
    if not trip:
        return redirect("/trips")
    return render_template("edit.html", trip=trip)


@app.route("/delete/<int:trip_id>", methods=["POST"])
@login_required
def delete_trip(trip_id):
    conn = get_db()
    conn.execute("DELETE FROM trips WHERE id=? AND user_id=?", (trip_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect("/trips")


# -----------------------------
# Admin dashboard routes
# -----------------------------
@app.route('/admin')
@login_required
@require_admin
def admin_index():
    return redirect(url_for('admin_members'))


@app.route('/admin/members')
@login_required
@require_admin
def admin_members():
    q = request.args.get('q', '').strip()
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 12
    params = []
    where = "WHERE is_active = 1"
    if q:
        where += " AND (name LIKE ? OR email LIKE ?)"
        term = f"%{q}%"
        params = [term, term]
    conn = get_db()
    total = conn.execute(f"SELECT COUNT(*) FROM users {where}", params).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    rows = conn.execute(
        f"SELECT id, name, email, created_at, is_admin, last_seen, CASE WHEN last_seen > datetime('now','-15 minutes') THEN 1 ELSE 0 END as is_online FROM users {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    conn.close()
    return render_template('admin_members.html', users=rows, q=q, page=page, total_pages=total_pages, total=total)


@app.route('/admin/member/<int:user_id>')
@login_required
@require_admin
def admin_member(user_id):
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 8
    conn = get_db()
    user = conn.execute("SELECT id, name, email, created_at, is_admin FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return redirect(url_for('admin_members'))
    total = conn.execute("SELECT COUNT(*) FROM trips WHERE user_id=?", (user_id,)).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    trips = conn.execute(
        "SELECT * FROM trips WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
        (user_id, per_page, (page - 1) * per_page),
    ).fetchall()
    conn.close()
    return render_template('admin_member.html', user=user, trips=trips, page=page, total_pages=total_pages, total=total)


@app.route('/admin/member/<int:user_id>/delete', methods=['POST'])
@login_required
@require_admin
def admin_delete_member(user_id):
    actor = session.get('user_id')
    conn = get_db()
    # Soft-delete the user by marking them inactive
    conn.execute('UPDATE users SET is_active=0 WHERE id=?', (user_id,))
    conn.execute(
        'INSERT INTO audit_logs (actor_user_id, action, target_user_id, details) VALUES (?, ?, ?, ?)',
        (actor, 'delete_user', user_id, f'Deleted by admin {actor}'),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_members'))


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


def trip_from_edit_form():
    """Validate edit form data and derive totals on the server."""
    travelers = max(get_int("travelers"), 1)
    costs = {
        "transport_cost": max(get_float("transport_cost"), 0),
        "food_cost": max(get_float("food_cost"), 0),
        "room_cost": max(get_float("room_cost"), 0),
        "toll_charges": max(get_float("toll_charges"), 0),
        "parking_fee": max(get_float("parking_fee"), 0),
        "vehicle_rental_cost": max(get_float("vehicle_rental_cost"), 0),
        "places_fee_total": max(get_float("places_fee_total"), 0),
    }
    total_budget = round(sum(costs.values()), 2)
    return {
        "destination": request.form.get("destination", "").strip(),
        "travelers": travelers,
        "total_distance": max(get_float("total_distance"), 0),
        "transport_mode": request.form.get("transport_mode", "car"),
        **{key: round(value, 2) for key, value in costs.items()},
        "fuel_type": request.form.get("fuel_type", "petrol"),
        "fuel_price": max(get_float("fuel_price"), 0),
        "fuel_cost": max(get_float("fuel_cost"), 0),
        "vehicle_type": request.form.get("vehicle_type", "own"),
        "total_budget": total_budget,
        "cost_per_person": round(total_budget / travelers, 2),
    }


@app.route("/save_trips", methods=["POST"])
@login_required
def save_trips():
    data = (
        trip_from_result_form()
        if request.form.get("from_result")
        else trip_from_form()
    )
    save_trip_data(data, session["user_id"])
    return redirect("/trips")


@app.route("/update_trip", methods=["POST"])
@login_required
def update_trip():
    trip_id = request.form.get("trip_id")
    if not trip_id:
        return redirect("/trips")
    data = (
        trip_from_edit_form()
        if request.form.get("edit_trip")
        else trip_from_result_form()
        if request.form.get("from_result")
        else trip_from_form()
    )
    update_trip_data(int(trip_id), data, session["user_id"])
    return redirect("/trips")


@app.route("/get_distance")
def get_distance():
    from_place = request.args.get("from", "").strip()
    destination = request.args.get("destination", "").strip()
    # The Google Directions API gives the most accurate road result when the
    # deployment has a restricted server key. Keep OSRM as a no-key fallback.
    if GOOGLE_DIRECTIONS_API_KEY:
        try:
            response = requests.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params={
                    "origin": from_place,
                    "destination": destination,
                    "mode": "driving",
                    "key": GOOGLE_DIRECTIONS_API_KEY,
                },
                timeout=15,
            )
            response.raise_for_status()
            route = response.json().get("routes", [None])[0]
            leg = route["legs"][0] if route else None
            if not leg:
                raise ValueError("No route found")
            return jsonify({
                "distance": round(leg["distance"]["value"] / 1000, 2),
                "duration": round(leg["duration"]["value"] / 3600, 2),
            })
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            # Continue to the public fallback if the Google key is restricted,
            # unavailable, or has no route for this journey.
            pass

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
    if not query:
        return jsonify([])
    local_matches = [
        {"label": city}
        for city in INDIAN_CITY_SUGGESTIONS
        if city.lower().startswith(query.lower())
    ][:5]
    if GOOGLE_PLACES_API_KEY:
        try:
            response = requests.get(
                "https://maps.googleapis.com/maps/api/place/autocomplete/json",
                params={"input": query, "key": GOOGLE_PLACES_API_KEY, "components": "country:in"},
                timeout=10,
            )
            response.raise_for_status()
            predictions = response.json().get("predictions", [])
            if predictions:
                return jsonify([
                    {"label": prediction["description"]}
                    for prediction in predictions[:5]
                ])
        except requests.RequestException:
            pass
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 5, "addressdetails": 1, "countrycodes": "in"},
            headers={"User-Agent": "TravelBudgetPlanner/1.0 (local planner)"},
            timeout=10,
        )
        response.raise_for_status()
        results = [
            {"label": place["display_name"], "lat": place["lat"], "lon": place["lon"]}
            for place in response.json()
        ]
        return jsonify((local_matches + results)[:5])
    except requests.RequestException:
        return jsonify(local_matches)


def find_attractions(coordinates, radius=15000, limit=6):
    if not GOOGLE_PLACES_API_KEY or not coordinates:
        return []
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{coordinates[1]},{coordinates[0]}",
                "radius": radius,
                "type": "tourist_attraction",
                "key": GOOGLE_PLACES_API_KEY,
            },
            timeout=12,
        )
        response.raise_for_status()
        return [
            {
                "name": place.get("name", "Nearby attraction"),
                "address": place.get("vicinity", "India"),
                "rating": place.get("rating"),
                "price_level": place.get("price_level", 1),
                "photo": place.get("photos", [{}])[0].get("photo_reference", ""),
            }
            for place in response.json().get("results", [])[:limit]
        ]
    except requests.RequestException:
        return []


def find_lodging(coordinates, radius=12000, limit=4):
    if not GOOGLE_PLACES_API_KEY or not coordinates:
        return []
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{coordinates[1]},{coordinates[0]}",
                "radius": radius,
                "type": "lodging",
                "key": GOOGLE_PLACES_API_KEY,
            },
            timeout=12,
        )
        response.raise_for_status()
        return [
            {
                "name": place.get("name", "Nearby hotel"),
                "address": place.get("vicinity", "India"),
                "rating": place.get("rating"),
                "price_level": place.get("price_level", 2),
                "photo": place.get("photos", [{}])[0].get("photo_reference", ""),
            }
            for place in response.json().get("results", [])[:limit]
        ]
    except requests.RequestException:
        return []


@app.route("/nearby_attractions")
def nearby_attractions():
    destination = request.args.get("destination", "")
    origin = request.args.get("from", "")
    try:
        destination_coordinates = geocode(destination)
        origin_coordinates = geocode(origin) if origin else None
    except requests.RequestException:
        return jsonify({"destination": [], "on_the_way": []}), 503

    destination_places = find_attractions(destination_coordinates)
    on_the_way = []
    if origin_coordinates and destination_coordinates:
        midpoint = (
            (origin_coordinates[0] + destination_coordinates[0]) / 2,
            (origin_coordinates[1] + destination_coordinates[1]) / 2,
        )
        on_the_way = find_attractions(midpoint, radius=25000)

    estimate = location_cost_estimate(destination)
    entry_fee = ENTRY_FEE_BY_TIER[estimate["tier_key"]]
    for place in destination_places:
        place["entry_fee"] = entry_fee
    attach_photo_urls(destination_places)
    attach_photo_urls(on_the_way)
    return jsonify({"destination": destination_places, "on_the_way": on_the_way})


@app.route("/place_photo")
def place_photo():
    reference = request.args.get("reference", "")
    if not GOOGLE_PLACES_API_KEY or not reference or len(reference) > 500:
        return "", 404
    try:
        photo = requests.get(
            "https://maps.googleapis.com/maps/api/place/photo",
            params={"maxwidth": 520, "photoreference": reference, "key": GOOGLE_PLACES_API_KEY},
            timeout=15,
        )
        photo.raise_for_status()
        return Response(
            photo.content,
            content_type=photo.headers.get("Content-Type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except requests.RequestException:
        return "", 404


@app.route("/estimate_stay_costs")
def estimate_stay_costs():
    return jsonify(location_cost_estimate(request.args.get("destination", "")))


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
