import json
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


def find_dining(coordinates, radius=12000, limit=4):
    if not GOOGLE_PLACES_API_KEY or not coordinates:
        return []
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{coordinates[1]},{coordinates[0]}",
                "radius": radius,
                "type": "restaurant",
                "key": GOOGLE_PLACES_API_KEY,
            },
            timeout=12,
        )
        response.raise_for_status()
        return [
            {
                "name": place.get("name", "Local Restaurant"),
                "address": place.get("vicinity", "India"),
                "rating": place.get("rating"),
                "price_level": place.get("price_level", 2),
                "photo": place.get("photos", [{}])[0].get("photo_reference", "") if place.get("photos") else "",
            }
            for place in response.json().get("results", [])[:limit]
        ]
    except requests.RequestException:
        return []


POPULAR_DESTINATION_ATTRACTIONS = {
    "goa": [
        {"name": "Baga & Calangute Beach", "entry_fee": 0, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=600&q=80"},
        {"name": "Aguada Fort & Lighthouse", "entry_fee": 50, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1590050752117-238cb0fb12b1?auto=format&fit=crop&w=600&q=80"},
        {"name": "Dudhsagar Waterfalls Trail", "entry_fee": 100, "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=600&q=80"},
        {"name": "Basilica of Bom Jesus", "entry_fee": 0, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1544735716-392fe2489ffa?auto=format&fit=crop&w=600&q=80"},
        {"name": "Chapora Fort Viewpoint", "entry_fee": 20, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=600&q=80"}
    ],
    "jaipur": [
        {"name": "Amber Palace & Fort", "entry_fee": 200, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1599661046289-e31897846e41?auto=format&fit=crop&w=600&q=80"},
        {"name": "Hawa Mahal (Palace of Winds)", "entry_fee": 50, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1603228254119-e6aef2999238?auto=format&fit=crop&w=600&q=80"},
        {"name": "City Palace & Museum", "entry_fee": 300, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=600&q=80"},
        {"name": "Jantar Mantar Observatory", "entry_fee": 50, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1599661046289-e31897846e41?auto=format&fit=crop&w=600&q=80"},
        {"name": "Nahargarh Fort Sunset Point", "entry_fee": 50, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=600&q=80"}
    ],
    "agra": [
        {"name": "Taj Mahal", "entry_fee": 250, "rating": 4.9, "image_url": "https://images.unsplash.com/photo-1564507592333-c60657eea523?auto=format&fit=crop&w=600&q=80"},
        {"name": "Agra Fort", "entry_fee": 50, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1585136917192-e4277b02c89f?auto=format&fit=crop&w=600&q=80"},
        {"name": "Fatehpur Sikri Royal Complex", "entry_fee": 50, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=600&q=80"},
        {"name": "Mehtab Bagh Sunset Garden", "entry_fee": 25, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1564507592333-c60657eea523?auto=format&fit=crop&w=600&q=80"}
    ],
    "delhi": [
        {"name": "Red Fort & Museum", "entry_fee": 80, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1585136917192-e4277b02c89f?auto=format&fit=crop&w=600&q=80"},
        {"name": "Qutub Minar Complex", "entry_fee": 40, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1544735716-392fe2489ffa?auto=format&fit=crop&w=600&q=80"},
        {"name": "Humayun's Tomb", "entry_fee": 40, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=600&q=80"},
        {"name": "India Gate & War Memorial", "entry_fee": 0, "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1587474260584-136574528ed5?auto=format&fit=crop&w=600&q=80"},
        {"name": "Akshardham Exhibition", "entry_fee": 250, "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1564507592333-c60657eea523?auto=format&fit=crop&w=600&q=80"}
    ],
    "mumbai": [
        {"name": "Gateway of India & Promenade", "entry_fee": 0, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?auto=format&fit=crop&w=600&q=80"},
        {"name": "Elephanta Caves & Ferry", "entry_fee": 260, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=600&q=80"},
        {"name": "Chhatrapati Shivaji Maharaj Museum", "entry_fee": 150, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1544735716-392fe2489ffa?auto=format&fit=crop&w=600&q=80"},
        {"name": "Marine Drive Sunset Walk", "entry_fee": 0, "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1567157577867-05ccb1388e66?auto=format&fit=crop&w=600&q=80"}
    ],
    "ooty": [
        {"name": "Ooty Government Botanical Garden", "entry_fee": 50, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=600&q=80"},
        {"name": "Doddabetta Peak Viewpoint", "entry_fee": 30, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=600&q=80"},
        {"name": "Pykara Lake & Boating", "entry_fee": 60, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=600&q=80"},
        {"name": "Nilgiri Mountain Toy Train", "entry_fee": 200, "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=600&q=80"}
    ]
}


def destination_budget_details(destination, trip_days):
    """Fetch tourist places, hotels, and food/dining at the destination with estimated costs."""
    estimate = location_cost_estimate(destination)
    tier_key = estimate["tier_key"]
    entry_fee = ENTRY_FEE_BY_TIER[tier_key]
    base_room = estimate["room"]
    base_food = estimate["food"]

    attractions = []
    hotels = []
    dining = []
    try:
        coordinates = geocode(destination)
        if coordinates:
            attractions = find_attractions(coordinates, radius=12000, limit=5)
            hotels = find_lodging(coordinates, radius=12000, limit=4)
            dining = find_dining(coordinates, radius=12000, limit=4)
    except requests.RequestException:
        pass

    for place in attractions:
        place["entry_fee"] = entry_fee

    for hotel in hotels:
        hotel["price_per_night"] = hotel_rate_from_price_level(
            base_room, hotel.get("price_level", 2)
        )

    for item in dining:
        level = item.get("price_level", 2)
        multiplier = {0: 0.35, 1: 0.45, 2: 0.70, 3: 1.10, 4: 1.75}.get(level, 0.70)
        item["estimated_cost"] = round(base_food * multiplier)
        item["cuisine"] = "Local & Indian Specialties"

    attach_photo_urls(attractions)
    attach_photo_urls(hotels)
    attach_photo_urls(dining)

    if not attractions:
        place_name = short_location(destination) or "your destination"
        lower_dest = (destination or "").lower()
        matched_popular = next((v for k, v in POPULAR_DESTINATION_ATTRACTIONS.items() if k in lower_dest), None)
        if matched_popular:
            attractions = [dict(item) for item in matched_popular]
        else:
            attractions = [
                {
                    "name": f"{place_name} — Heritage Fort & Palace",
                    "address": f"Historic Quarter, {destination}",
                    "rating": 4.6,
                    "entry_fee": entry_fee,
                    "image_url": "https://images.unsplash.com/photo-1599661046289-e31897846e41?auto=format&fit=crop&w=600&q=80",
                },
                {
                    "name": f"{place_name} — Scenic Viewpoint & Lake",
                    "address": f"Promenade, {destination}",
                    "rating": 4.7,
                    "entry_fee": max(round(entry_fee * 0.5), 20),
                    "image_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=600&q=80",
                },
                {
                    "name": f"{place_name} — Central Botanical Park",
                    "address": f"City Center, {destination}",
                    "rating": 4.5,
                    "entry_fee": max(round(entry_fee * 0.3), 30),
                    "image_url": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=600&q=80",
                },
                {
                    "name": f"{place_name} — Cultural Museum & Art Gallery",
                    "address": f"Civic Center, {destination}",
                    "rating": 4.6,
                    "entry_fee": entry_fee,
                    "image_url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=600&q=80",
                },
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

    if not dining:
        place_name = short_location(destination) or "your destination"
        dining = [
            {
                "name": f"{place_name} — Heritage Thali & Local Flavors",
                "address": f"City Center, {destination}",
                "rating": 4.6,
                "cuisine": "Authentic Thali & Traditional Cuisine",
                "estimated_cost": round(base_food * 0.65),
                "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?auto=format&fit=crop&w=600&q=80",
            },
            {
                "name": f"{place_name} — Street Food & Regional Delights",
                "address": f"Old Town Market, {destination}",
                "rating": 4.5,
                "cuisine": "Popular Street Food & Snacks",
                "estimated_cost": round(base_food * 0.35),
                "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=600&q=80",
            },
            {
                "name": f"{place_name} — Garden Cafe & Bistro",
                "address": f"Promenade Road, {destination}",
                "rating": 4.7,
                "cuisine": "Cafe, Beverages & Continental",
                "estimated_cost": round(base_food * 0.95),
                "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80",
            },
        ]

    dest_encoded = requests.utils.quote(destination)
    for place in attractions:
        place["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(place['name'] + ' ' + destination)}"

    for hotel in hotels:
        hotel["price_per_night"] = hotel_rate_from_price_level(
            base_room, hotel.get("price_level", 2)
        )
        hotel["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(hotel['name'] + ' ' + destination)}"
        hotel["google_url"] = f"https://www.google.com/travel/hotels/{dest_encoded}"
        hotel["oyo_url"] = f"https://www.oyorooms.com/search?location={dest_encoded}"
        hotel["mmt_url"] = f"https://www.makemytrip.com/hotels/{requests.utils.quote(short_location(destination).lower())}-hotels.html"

    for item in dining:
        level = item.get("price_level", 2)
        multiplier = {0: 0.35, 1: 0.45, 2: 0.70, 3: 1.10, 4: 1.75}.get(level, 0.70)
        item["estimated_cost"] = round(base_food * multiplier)
        item["cuisine"] = "Local & Indian Specialties"
        item["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(item['name'] + ' ' + destination)}"
        item["google_url"] = f"https://www.google.com/search?q={requests.utils.quote(item['name'] + ' in ' + destination)}"

    return {
        "attractions": attractions,
        "hotels": hotels,
        "dining": dining,
        "places_count": places_count,
        "places_fee_total": places_fee_total,
        "per_place_fee": per_place_fee,
        "room_per_day": room_per_day,
        "room_total": room_per_day * max(trip_days, 1),
        "tier_label": estimate["tier"],
    }


MAJOR_TRANSIT_HUBS = {
    "bengaluru": {
        "railway": [
            {"name": "KSR Bengaluru City Junction (Majestic)", "code": "SBC", "distance_km": 2.5, "type": "Major Terminal"},
            {"name": "Yesvantpur Junction", "code": "YPR", "distance_km": 7.5, "type": "Major Hub"},
            {"name": "Sir M. Visvesvaraya Terminal (SMVB)", "code": "SMVB", "distance_km": 11.0, "type": "World-Class AC Terminal"},
            {"name": "Bangalore Cantt", "code": "BNC", "distance_km": 4.0, "type": "Central Station"}
        ],
        "bus": [
            {"name": "Kempegowda Bus Station (Majestic Bus Stand)", "type": "Interstate Terminal", "distance_km": 2.5},
            {"name": "Shantinagar Bus Station (KSRTC/TNSTC/SETC)", "type": "Southbound Terminal", "distance_km": 4.2},
            {"name": "Satellite Bus Stand (Mysore Road)", "type": "Express Terminal", "distance_km": 7.0}
        ],
        "airport": {"name": "Kempegowda International Airport", "code": "BLR", "city": "Bengaluru", "distance_km": 35.0},
        "last_mile": {
            "train": [
                {"mode": "Namma Metro (Purple / Green Line)", "icon": "🚇", "duration": "15–25 mins", "cost_est": "₹25–₹45", "desc": "Direct connectivity to Majestic (SBC) & Yesvantpur (YPR)"},
                {"mode": "App Cab (Uber / Ola / Rapido)", "icon": "🚕", "duration": "20–35 mins", "cost_est": "₹160–₹280", "desc": "Doorstep pickup directly to station porch"},
                {"mode": "BMTC City Feeder Bus", "icon": "🚌", "duration": "30–45 mins", "cost_est": "₹15–₹25", "desc": "Frequent Majestic-bound buses from all major localities"},
                {"mode": "Auto Rickshaw", "icon": "🛺", "duration": "20–30 mins", "cost_est": "₹90–₹160", "desc": "Quick metered or app auto to station entrance"}
            ],
            "bus": [
                {"mode": "Namma Metro", "icon": "🚇", "duration": "15–25 mins", "cost_est": "₹20–₹40", "desc": "Alight at Nadaprabhu Kempegowda Majestic metro station"},
                {"mode": "App Cab / Auto", "icon": "🚕", "duration": "20–35 mins", "cost_est": "₹120–₹240", "desc": "Direct drop at bus platform"},
                {"mode": "BMTC City Bus", "icon": "🚌", "duration": "25–40 mins", "cost_est": "₹15–₹20", "desc": "Direct KBS / Majestic feeder routes"}
            ],
            "flight": [
                {"mode": "Vayu Vajra (KIA AC Bus)", "icon": "🚌", "duration": "60–80 mins", "cost_est": "₹230–₹260", "desc": "Comfortable 24x7 AC airport shuttle from all city hubs"},
                {"mode": "Airport Taxi / Uber / Ola", "icon": "🚕", "duration": "45–65 mins", "cost_est": "₹850–₹1,400", "desc": "Fast highway transit via Bellary Road toll expressway"},
                {"mode": "Suburban Airport Train", "icon": "🚆", "duration": "45–55 mins", "cost_est": "₹35–₹50", "desc": "Direct train from SBC/YPR to KIA Halt station"}
            ]
        }
    },
    "chennai": {
        "railway": [
            {"name": "Puratchi Thalaivar Dr. M.G.R. Central (Chennai Central)", "code": "MAS", "distance_km": 3.0, "type": "Major Terminal"},
            {"name": "Chennai Egmore", "code": "MS", "distance_km": 2.5, "type": "Southbound Hub"},
            {"name": "Tambaram", "code": "TBM", "distance_km": 25.0, "type": "Suburban Terminal"}
        ],
        "bus": [
            {"name": "Chennai Mofussil Bus Terminus (CMBT / Koyambedu)", "type": "Interstate Terminal", "distance_km": 8.5},
            {"name": "Kilambakkam KCBT Bus Terminus", "type": "Southbound Terminal", "distance_km": 28.0}
        ],
        "airport": {"name": "Chennai International Airport", "code": "MAA", "city": "Chennai", "distance_km": 18.0},
        "last_mile": {
            "train": [
                {"mode": "Chennai Metro (Blue / Green Line)", "icon": "🚇", "duration": "15–30 mins", "cost_est": "₹20–₹50", "desc": "Direct underground metro station right inside Chennai Central & Egmore"},
                {"mode": "App Cab (Uber / Ola / FastTrack)", "icon": "🚕", "duration": "25–40 mins", "cost_est": "₹180–₹320", "desc": "Direct drop at Central / Egmore main porch"},
                {"mode": "MTC City Bus", "icon": "🚌", "duration": "35–50 mins", "cost_est": "₹10–₹25", "desc": "Frequent city bus connectivity from all corridors"},
                {"mode": "Auto Rickshaw", "icon": "🛺", "duration": "20–35 mins", "cost_est": "₹100–₹190", "desc": "Quick local ride to station entrance"}
            ],
            "bus": [
                {"mode": "Chennai Metro (Green Line to Koyambedu)", "icon": "🚇", "duration": "20–35 mins", "cost_est": "₹25–₹50", "desc": "Alight directly at CMBT Metro Station"},
                {"mode": "App Cab / Auto", "icon": "🚕", "duration": "25–45 mins", "cost_est": "₹150–₹290", "desc": "Drop at CMBT departure bays"},
                {"mode": "MTC City Bus", "icon": "🚌", "duration": "35–55 mins", "cost_est": "₹15–₹30", "desc": "CMBT-bound city express buses"}
            ],
            "flight": [
                {"mode": "Chennai Metro (Direct to Airport)", "icon": "🚇", "duration": "25–40 mins", "cost_est": "₹40–₹60", "desc": "Direct Blue Line metro with skywalk into Departure Terminal"},
                {"mode": "Airport Prepaid Taxi / Uber / Ola", "icon": "🚕", "duration": "35–55 mins", "cost_est": "₹500–₹850", "desc": "Fast transit via GST Road"},
                {"mode": "MTC Airport AC Express Bus", "icon": "🚌", "duration": "50–70 mins", "cost_est": "₹100–₹150", "desc": "Budget airport feeder from Central / T.Nagar"}
            ]
        }
    },
    "delhi": {
        "railway": [
            {"name": "New Delhi Railway Station", "code": "NDLS", "distance_km": 2.0, "type": "Central Terminal"},
            {"name": "Hazrat Nizamuddin", "code": "NZM", "distance_km": 7.0, "type": "South / Central Hub"},
            {"name": "Anand Vihar Terminal", "code": "ANVT", "distance_km": 12.0, "type": "Eastbound Terminal"},
            {"name": "Old Delhi Junction", "code": "DLI", "distance_km": 4.5, "type": "Historic Hub"}
        ],
        "bus": [
            {"name": "Maharana Pratap ISBT (Kashmere Gate)", "type": "Interstate Terminal", "distance_km": 5.0},
            {"name": "Swami Vivekanand ISBT (Anand Vihar)", "type": "East Interstate Terminal", "distance_km": 12.0},
            {"name": "Sarai Kale Khan ISBT", "type": "South Interstate Terminal", "distance_km": 8.0}
        ],
        "airport": {"name": "Indira Gandhi International Airport (IGI)", "code": "DEL", "city": "Delhi", "distance_km": 16.0},
        "last_mile": {
            "train": [
                {"mode": "Delhi Metro (Yellow / Airport Line to NDLS)", "icon": "🚇", "duration": "15–30 mins", "cost_est": "₹20–₹50", "desc": "Direct metro gates at NDLS, Anand Vihar & Kashmere Gate"},
                {"mode": "App Cab (Uber / Ola / BluSmart)", "icon": "🚕", "duration": "20–40 mins", "cost_est": "₹180–₹350", "desc": "Quick drop at Ajmeri Gate or Paharganj side"},
                {"mode": "Auto Rickshaw", "icon": "🛺", "duration": "20–35 mins", "cost_est": "₹90–₹180", "desc": "Metered / app auto to railway entrance"},
                {"mode": "DTC AC Bus", "icon": "🚌", "duration": "30–50 mins", "cost_est": "₹15–₹25", "desc": "Frequent city connectivity across NCR"}
            ],
            "bus": [
                {"mode": "Delhi Metro (Kashmere Gate / Anand Vihar)", "icon": "🚇", "duration": "15–30 mins", "cost_est": "₹20–₹40", "desc": "Interchange hub right next to ISBT counters"},
                {"mode": "App Cab / Auto", "icon": "🚕", "duration": "20–40 mins", "cost_est": "₹150–₹300", "desc": "Direct entry to ISBT departure platform"},
                {"mode": "DTC City Bus", "icon": "🚌", "duration": "30–50 mins", "cost_est": "₹10–₹25", "desc": "ISBT connect buses from South/West Delhi"}
            ],
            "flight": [
                {"mode": "Airport Express Metro Line", "icon": "🚇", "duration": "18–25 mins", "cost_est": "₹60", "desc": "High-speed AC metro connecting NDLS & Dhaula Kuan to T3 / T1"},
                {"mode": "App Cab / BluSmart EV", "icon": "🚕", "duration": "30–55 mins", "cost_est": "₹450–₹850", "desc": "Direct drop at T1 / T2 / T3 departure gates"},
                {"mode": "DTC Airport Express Bus", "icon": "🚌", "duration": "45–70 mins", "cost_est": "₹100–₹120", "desc": "24x7 AC bus service from ISBT Kashmere Gate"}
            ]
        }
    },
    "mumbai": {
        "railway": [
            {"name": "Chhatrapati Shivaji Maharaj Terminus", "code": "CSMT", "distance_km": 2.0, "type": "Heritage Central Hub"},
            {"name": "Mumbai Central", "code": "MMCT", "distance_km": 4.5, "type": "Western Mainline Terminal"},
            {"name": "Bandra Terminus", "code": "BDTS", "distance_km": 14.0, "type": "North / West Terminal"},
            {"name": "Lokmanya Tilak Terminus (Kurla)", "code": "LTT", "distance_km": 16.0, "type": "Central Mainline Terminal"},
            {"name": "Dadar Central / Western", "code": "DR", "distance_km": 8.0, "type": "Major Junction"}
        ],
        "bus": [
            {"name": "MSRTC Central Bus Stand (Mumbai Central)", "type": "State Intercity Terminal", "distance_km": 4.5},
            {"name": "Borivali MSRTC / Private Bus Stand", "type": "Northbound Hub", "distance_km": 28.0},
            {"name": "Vashi Bus Terminus (Navi Mumbai)", "type": "East / Southbound Hub", "distance_km": 24.0}
        ],
        "airport": {"name": "Chhatrapati Shivaji Maharaj International Airport", "code": "BOM", "city": "Mumbai", "distance_km": 15.0},
        "last_mile": {
            "train": [
                {"mode": "Mumbai Local Suburban Train", "icon": "🚆", "duration": "15–35 mins", "cost_est": "₹10–₹20", "desc": "Fast local train connectivity right to CSMT, Dadar & Mumbai Central"},
                {"mode": "Mumbai Metro (Line 1/2/3/7)", "icon": "🚇", "duration": "15–30 mins", "cost_est": "₹20–₹50", "desc": "Comfortable AC transit connecting suburbs to junctions"},
                {"mode": "App Cab (Uber / Ola / Kaali Peeli)", "icon": "🚕", "duration": "25–50 mins", "cost_est": "₹180–₹380", "desc": "Direct drop at station concourse"},
                {"mode": "Auto Rickshaw (Suburbs)", "icon": "🛺", "duration": "15–30 mins", "cost_est": "₹60–₹150", "desc": "Quick meter auto (available north of Bandra/Sion)"}
            ],
            "bus": [
                {"mode": "Mumbai Local / Metro", "icon": "🚆", "duration": "20–40 mins", "cost_est": "₹15–₹30", "desc": "Reach bus terminus via suburban railway station"},
                {"mode": "App Cab / Kaali Peeli", "icon": "🚕", "duration": "25–45 mins", "cost_est": "₹160–₹320", "desc": "Drop directly at bus boarding point"},
                {"mode": "BEST City Bus", "icon": "🚌", "duration": "30–55 mins", "cost_est": "₹10–₹25", "desc": "Bus depot feeder network"}
            ],
            "flight": [
                {"mode": "Aqua Line 3 Metro / Western Express Local", "icon": "🚇", "duration": "25–40 mins", "cost_est": "₹30–₹50", "desc": "Underground Metro Line 3 connecting airport to city core"},
                {"mode": "App Cab (Uber / Ola) / Prepaid Taxi", "icon": "🚕", "duration": "35–65 mins", "cost_est": "₹550–₹950", "desc": "Direct transit via Western Express Highway or Coastal Road"},
                {"mode": "BEST Airport Express AC Bus", "icon": "🚌", "duration": "45–75 mins", "cost_est": "₹100–₹175", "desc": "Direct AC buses from Colaba, Borivali & Thane to T1/T2"}
            ]
        }
    },
    "hyderabad": {
        "railway": [
            {"name": "Secunderabad Junction", "code": "SC", "distance_km": 6.5, "type": "Major Terminal"},
            {"name": "Hyderabad Deccan (Nampally)", "code": "HYB", "distance_km": 2.0, "type": "City Terminal"},
            {"name": "Kacheguda", "code": "KCG", "distance_km": 4.0, "type": "South Central Hub"}
        ],
        "bus": [
            {"name": "Mahatma Gandhi Bus Station (MGBS / Imlibun)", "type": "Major Interstate Terminal", "distance_km": 3.0},
            {"name": "Jubilee Bus Station (JBS Secunderabad)", "type": "Northbound Terminal", "distance_km": 8.0}
        ],
        "airport": {"name": "Rajiv Gandhi International Airport (Shamshabad)", "code": "HYD", "city": "Hyderabad", "distance_km": 26.0},
        "last_mile": {
            "train": [
                {"mode": "Hyderabad Metro (Red / Green / Blue Line)", "icon": "🚇", "duration": "15–30 mins", "cost_est": "₹20–₹50", "desc": "Direct connectivity to Secunderabad East/West & Gandhi Bhavan (Nampally)"},
                {"mode": "App Cab (Uber / Ola / Rapido)", "icon": "🚕", "duration": "20–35 mins", "cost_est": "₹150–₹280", "desc": "Direct drop at Secunderabad or Nampally porch"},
                {"mode": "Auto Rickshaw", "icon": "🛺", "duration": "15–30 mins", "cost_est": "₹80–₹160", "desc": "Quick local auto to station entrance"},
                {"mode": "TSRTC City Bus", "icon": "🚌", "duration": "30–45 mins", "cost_est": "₹15–₹30", "desc": "Frequent city bus network to major stations"}
            ],
            "bus": [
                {"mode": "Hyderabad Metro (MGBS Interchange)", "icon": "🚇", "duration": "15–25 mins", "cost_est": "₹20–₹40", "desc": "MGBS Metro Station has direct walkway into bus terminal"},
                {"mode": "App Cab / Auto", "icon": "🚕", "duration": "20–35 mins", "cost_est": "₹120–₹240", "desc": "Drop at MGBS departure platforms"},
                {"mode": "TSRTC City Bus", "icon": "🚌", "duration": "25–45 mins", "cost_est": "₹15–₹25", "desc": "MGBS / JBS direct express"}
            ],
            "flight": [
                {"mode": "Pushpak Airport Liner (AC AC Coach)", "icon": "🚌", "duration": "45–70 mins", "cost_est": "₹200–₹300", "desc": "Frequent 24x7 luxury AC airport coach from Secunderabad, Hitec City, Begumpet"},
                {"mode": "Airport Cab / Uber / Ola", "icon": "🚕", "duration": "35–55 mins", "cost_est": "₹700–₹1,200", "desc": "PVNR Elevated Expressway fast access to Shamshabad"}
            ]
        }
    },
    "kolkata": {
        "railway": [
            {"name": "Howrah Junction", "code": "HWH", "distance_km": 4.5, "type": "Historic Mega Terminal"},
            {"name": "Sealdah", "code": "SDAH", "distance_km": 2.5, "type": "Suburban & Mail Hub"},
            {"name": "Kolkata Chitpur", "code": "KOAA", "distance_km": 6.0, "type": "Long-Distance Terminal"},
            {"name": "Shalimar", "code": "SHM", "distance_km": 8.0, "type": "South Eastern Terminal"}
        ],
        "bus": [
            {"name": "Esplanade Bus Terminus (Dharmatala)", "type": "Central Intercity Hub", "distance_km": 1.5},
            {"name": "Karunamoyee Bus Terminus (Salt Lake)", "type": "Interstate Terminal", "distance_km": 8.5}
        ],
        "airport": {"name": "Netaji Subhash Chandra Bose International Airport (Dum Dum)", "code": "CCU", "city": "Kolkata", "distance_km": 16.0},
        "last_mile": {
            "train": [
                {"mode": "Kolkata Metro (Green / Blue Line)", "icon": "🚇", "duration": "15–25 mins", "cost_est": "₹15–₹30", "desc": "Underwater Green Line connects directly to Howrah Station & Sealdah"},
                {"mode": "Yellow Taxi / App Cab (Uber / Ola)", "icon": "🚕", "duration": "20–40 mins", "cost_est": "₹140–₹280", "desc": "Direct drop at Howrah or Sealdah taxi stands"},
                {"mode": "Howrah Ferry Service", "icon": "⛴️", "duration": "10–15 mins", "cost_est": "₹6–₹10", "desc": "Scenic river ferry across the Hooghly right to Howrah Station"},
                {"mode": "CSTC / WBTC Bus", "icon": "🚌", "duration": "25–45 mins", "cost_est": "₹10–₹20", "desc": "Direct bus routes from all city points"}
            ],
            "bus": [
                {"mode": "Kolkata Metro (Esplanade)", "icon": "🚇", "duration": "10–20 mins", "cost_est": "₹10–₹20", "desc": "Esplanade Metro is adjacent to Dharmatala bus stands"},
                {"mode": "Taxi / Auto", "icon": "🚕", "duration": "15–30 mins", "cost_est": "₹100–₹200", "desc": "Drop at Esplanade departure zone"}
            ],
            "flight": [
                {"mode": "AC Airport Volvo Bus (WBTC)", "icon": "🚌", "duration": "45–70 mins", "cost_est": "₹80–₹120", "desc": "Regular AC buses from Howrah, Esplanade & Gariahat to Airport"},
                {"mode": "Yellow Taxi / Uber / Ola", "icon": "🚕", "duration": "35–55 mins", "cost_est": "₹450–₹750", "desc": "Fast expressway via VIP Road / Rajarhat Main Road"}
            ]
        }
    },
    "goa": {
        "railway": [
            {"name": "Madgaon Junction (Margao)", "code": "MAO", "distance_km": 28.0, "type": "South Goa Major Terminal"},
            {"name": "Thivim", "code": "THVM", "distance_km": 22.0, "type": "North Goa (Calangute / Baga Hub)"},
            {"name": "Karmali", "code": "KRMI", "distance_km": 12.0, "type": "Central Goa (Panaji Hub)"},
            {"name": "Vasco-da-Gama", "code": "VSG", "distance_km": 25.0, "type": "Port City Station"}
        ],
        "bus": [
            {"name": "Panaji KTC Bus Stand", "type": "Central Intercity Terminal", "distance_km": 2.0},
            {"name": "Margao KTC Bus Stand", "type": "South Goa Terminal", "distance_km": 28.0},
            {"name": "Mapusa KTC Bus Stand", "type": "North Goa Beach Terminal", "distance_km": 14.0}
        ],
        "airport": {"name": "Dabolim International Airport / Mopa (Manohar)", "code": "GOI", "city": "Goa", "distance_km": 25.0},
        "last_mile": {
            "train": [
                {"mode": "Goa Tourist Taxi / GoaMiles", "icon": "🚕", "duration": "30–50 mins", "cost_est": "₹600–₹1,100", "desc": "Direct taxi from Thivim or Madgaon to beach resorts"},
                {"mode": "Kadamba (KTC) Shuttle Bus", "icon": "🚌", "duration": "40–60 mins", "cost_est": "₹35–₹60", "desc": "Budget intercity shuttle connecting stations to Panaji & Margao"},
                {"mode": "Pilot (Motorcycle Taxi)", "icon": "🏍️", "duration": "25–40 mins", "cost_est": "₹150–₹300", "desc": "Iconic single-passenger Goan bike taxi for quick luggage-light transit"}
            ],
            "bus": [
                {"mode": "Local KTC Beach Shuttle", "icon": "🚌", "duration": "25–45 mins", "cost_est": "₹20–₹40", "desc": "Frequent buses to Calangute, Baga, Candolim & Anjuna"},
                {"mode": "Taxi / Rental Scooter", "icon": "🚕", "duration": "20–35 mins", "cost_est": "₹350–₹650", "desc": "Taxi or pickup your pre-booked rental two-wheeler"}
            ],
            "flight": [
                {"mode": "Airport AC Electric Express Bus (KTC)", "icon": "🚌", "duration": "50–80 mins", "cost_est": "₹150–₹250", "desc": "Direct AC buses connecting Dabolim & Mopa to Panaji, Calangute & Margao"},
                {"mode": "Prepaid Taxi / GoaMiles", "icon": "🚕", "duration": "40–65 mins", "cost_est": "₹900–₹1,600", "desc": "Fixed rate airport taxi to North/South Goa beach belts"}
            ]
        }
    },
    "jaipur": {
        "railway": [
            {"name": "Jaipur Junction", "code": "JP", "distance_km": 3.0, "type": "North Western HQ Terminal"},
            {"name": "Gandhinagar Jaipur", "code": "GADJ", "distance_km": 6.0, "type": "South Jaipur Hub"},
            {"name": "Durgapura", "code": "DPA", "distance_km": 8.0, "type": "Airport Side Station"}
        ],
        "bus": [
            {"name": "Sindhi Camp Central Bus Stand", "type": "Interstate Terminal", "distance_km": 2.5},
            {"name": "Narayan Singh Circle (Private AC Coaches)", "type": "Luxury Coach Hub", "distance_km": 4.0}
        ],
        "airport": {"name": "Jaipur International Airport (Sanganer)", "code": "JAI", "city": "Jaipur", "distance_km": 12.0},
        "last_mile": {
            "train": [
                {"mode": "Jaipur Metro (Pink Line)", "icon": "🚇", "duration": "10–20 mins", "cost_est": "₹15–₹30", "desc": "Railway Station Metro station connects to Old City / Chandpole & Mansarovar"},
                {"mode": "App Cab (Uber / Ola)", "icon": "🚕", "duration": "15–30 mins", "cost_est": "₹120–₹220", "desc": "Direct pickup at Platform 1 / 2 exit"},
                {"mode": "Auto Rickshaw / E-Rickshaw", "icon": "🛺", "duration": "15–25 mins", "cost_est": "₹60–₹130", "desc": "Quick ride to MI Road, C-Scheme & Heritage City"}
            ],
            "bus": [
                {"mode": "Jaipur Metro (Sindhi Camp)", "icon": "🚇", "duration": "10–15 mins", "cost_est": "₹10–₹20", "desc": "Sindhi Camp Metro Station is integrated with the bus terminus"},
                {"mode": "Auto / Cab", "icon": "🛺", "duration": "15–25 mins", "cost_est": "₹70–₹160", "desc": "Direct drop at RSRTC platforms"}
            ],
            "flight": [
                {"mode": "App Cab (Uber / Ola)", "icon": "🚕", "duration": "25–45 mins", "cost_est": "₹320–₹550", "desc": "Direct transit via Tonk Road / JLN Marg"},
                {"mode": "Low Floor AC City Bus", "icon": "🚌", "duration": "40–60 mins", "cost_est": "₹40–₹70", "desc": "Budget connection to Ajmeri Gate & Sindhi Camp"}
            ]
        }
    },
    "kochi": {
        "railway": [
            {"name": "Ernakulam Junction (South)", "code": "ERS", "distance_km": 2.0, "type": "Major Mainline Terminal"},
            {"name": "Ernakulam Town (North)", "code": "ERN", "distance_km": 3.5, "type": "Central Junction"},
            {"name": "Aluva", "code": "AWY", "distance_km": 18.0, "type": "Northern / Airport Hub"}
        ],
        "bus": [
            {"name": "KSRTC Central Bus Station (Ernakulam)", "type": "State Intercity Terminal", "distance_km": 2.5},
            {"name": "Vyttila Mobility Hub", "type": "Integrated Mega Hub (Bus/Metro/Water)", "distance_km": 6.0}
        ],
        "airport": {"name": "Cochin International Airport (Nedumbassery)", "code": "COK", "city": "Kochi", "distance_km": 28.0},
        "last_mile": {
            "train": [
                {"mode": "Kochi Metro (Blue Line)", "icon": "🚇", "duration": "10–20 mins", "cost_est": "₹20–₹40", "desc": "South Railway Station Metro connects to MG Road, Edappally & Aluva"},
                {"mode": "Kochi Water Metro", "icon": "⛴️", "duration": "15–25 mins", "cost_est": "₹20–₹40", "desc": "Eco-friendly electric boat connection to Fort Kochi & islands"},
                {"mode": "App Cab / Auto", "icon": "🚕", "duration": "15–30 mins", "cost_est": "₹90–₹200", "desc": "Direct drop at station entry"}
            ],
            "bus": [
                {"mode": "Kochi Metro to Vyttila", "icon": "🚇", "duration": "15–25 mins", "cost_est": "₹20–₹40", "desc": "Integrated access to Vyttila Mobility Hub"},
                {"mode": "Auto / Taxi", "icon": "🛺", "duration": "15–30 mins", "cost_est": "₹80–₹180", "desc": "Direct transit to KSRTC stand"}
            ],
            "flight": [
                {"mode": "KSRTC Low Floor AC Airport Feeder", "icon": "🚌", "duration": "50–75 mins", "cost_est": "₹80–₹120", "desc": "Regular AC buses connecting Cochin Airport to Fort Kochi & Ernakulam"},
                {"mode": "Prepaid Airport Taxi / Uber", "icon": "🚕", "duration": "40–60 mins", "cost_est": "₹750–₹1,200", "desc": "Fast highway transit via Seaport-Airport Road"}
            ]
        }
    }
}


def get_transit_hub_details(from_place, destination, transport_mode="train"):
    """
    Returns suitable stations/terminals/airports for from & destination,
    last-mile travel options to get to the station/terminal, and booking/availability domains
    including 'Where Is My Train' live tracking links.
    """
    from_clean = short_location(from_place) or "Departure"
    dest_clean = short_location(destination) or "Destination"
    from_lower = from_clean.lower()
    dest_lower = dest_clean.lower()

    # Find matching hubs or generate dynamic intelligent defaults
    from_hub = next((v for k, v in MAJOR_TRANSIT_HUBS.items() if k in from_lower), None)
    dest_hub = next((v for k, v in MAJOR_TRANSIT_HUBS.items() if k in dest_lower), None)

    # 1. Railway Stations
    if from_hub:
        from_station = dict(from_hub["railway"][0])
        from_all_stations = [dict(s) for s in from_hub["railway"]]
    else:
        from_stn_code = (from_clean[:3].upper() if len(from_clean) >= 3 else "STN")
        from_station = {
            "name": f"{from_clean} Junction / Central Railway Station",
            "code": from_stn_code,
            "distance_km": 3.5,
            "type": "Primary Railway Junction"
        }
        from_all_stations = [from_station]

    if dest_hub:
        dest_station = dict(dest_hub["railway"][0])
        dest_all_stations = [dict(s) for s in dest_hub["railway"]]
    else:
        dest_stn_code = (dest_clean[:3].upper() if len(dest_clean) >= 3 else "DST")
        dest_station = {
            "name": f"{dest_clean} Junction / Central Station",
            "code": dest_stn_code,
            "distance_km": 4.0,
            "type": "Main Destination Station"
        }
        dest_all_stations = [dest_station]

    # 2. Bus Stands / Terminals
    if from_hub:
        from_bus_stand = dict(from_hub["bus"][0])
    else:
        from_bus_stand = {
            "name": f"{from_clean} Central Bus Station / ISBT",
            "type": "Intercity Bus Terminal",
            "distance_km": 2.5
        }

    if dest_hub:
        dest_bus_stand = dict(dest_hub["bus"][0])
    else:
        dest_bus_stand = {
            "name": f"{dest_clean} Central Bus Stand / Interstate Terminal",
            "type": "Intercity Terminal",
            "distance_km": 3.0
        }

    # 3. Airports
    if from_hub:
        from_airport = dict(from_hub["airport"])
    else:
        from_airport = {
            "name": f"{from_clean} Airport / Nearest Domestic Hub",
            "code": from_clean[:3].upper(),
            "city": from_clean,
            "distance_km": 22.0
        }

    if dest_hub:
        dest_airport = dict(dest_hub["airport"])
    else:
        dest_airport = {
            "name": f"{dest_clean} Airport / Nearest Regional Airport",
            "code": dest_clean[:3].upper(),
            "city": dest_clean,
            "distance_km": 20.0
        }

    # Last-mile connectivity options
    if from_hub and from_hub.get("last_mile", {}).get(transport_mode):
        origin_last_mile = [dict(item) for item in from_hub["last_mile"][transport_mode]]
    else:
        if transport_mode == "train":
            origin_last_mile = [
                {"mode": "Metro / Local Transit", "icon": "🚇", "duration": "15–25 mins", "cost_est": "₹20–₹40", "desc": f"Direct local transit or feeder to {from_station['name']}"},
                {"mode": "App Cab (Uber / Ola / Taxi)", "icon": "🚕", "duration": "20–35 mins", "cost_est": "₹140–₹260", "desc": "Convenient door-to-station drop with luggage"},
                {"mode": "Auto Rickshaw", "icon": "🛺", "duration": "15–30 mins", "cost_est": "₹70–₹150", "desc": "Quick local auto directly to railway platform entrance"},
                {"mode": "City Feeder Bus", "icon": "🚌", "duration": "30–45 mins", "cost_est": "₹15–₹25", "desc": f"Frequent bus service towards {from_clean} Railway Station"}
            ]
        elif transport_mode == "bus":
            origin_last_mile = [
                {"mode": "City Bus / Feeder", "icon": "🚌", "duration": "20–35 mins", "cost_est": "₹15–₹25", "desc": f"Direct bus route to {from_bus_stand['name']}"},
                {"mode": "Auto Rickshaw / App Cab", "icon": "🚕", "duration": "15–30 mins", "cost_est": "₹80–₹180", "desc": "Fast drop at bus boarding bays"},
                {"mode": "Metro / Local Train", "icon": "🚇", "duration": "15–25 mins", "cost_est": "₹20–₹35", "desc": "Nearest station walking distance from bus terminal"}
            ]
        else:  # flight
            origin_last_mile = [
                {"mode": "Airport Express AC Bus", "icon": "🚌", "duration": "45–70 mins", "cost_est": "₹150–₹250", "desc": f"Direct airport coach to {from_airport['name']}"},
                {"mode": "App Cab / Airport Taxi", "icon": "🚕", "duration": "35–55 mins", "cost_est": "₹600–₹1,100", "desc": "Direct departure terminal drop via highway"},
                {"mode": "Airport Metro / Shuttle", "icon": "🚇", "duration": "25–40 mins", "cost_est": "₹40–₹80", "desc": "Fast connection to departure gates"}
            ]

    # Destination last-mile (reaching destination hotel/city from arrival hub)
    if dest_hub and dest_hub.get("last_mile", {}).get(transport_mode):
        dest_last_mile = [dict(item) for item in dest_hub["last_mile"][transport_mode]]
    else:
        dest_last_mile = [
            {"mode": "Prepaid Taxi / App Cab", "icon": "🚕", "duration": "15–35 mins", "cost_est": "₹150–₹300", "desc": f"Quick ride from arrival station to your hotel in {dest_clean}"},
            {"mode": "Local Auto Rickshaw", "icon": "🛺", "duration": "15–25 mins", "cost_est": "₹80–₹160", "desc": "Metered / prepaid auto available right outside station"},
            {"mode": "Local City Bus / Shuttle", "icon": "🚌", "duration": "25–45 mins", "cost_est": "₹15–₹30", "desc": f"Connecting arrival hub to {dest_clean} center"}
        ]

    # Add Google Maps direct navigation links to each last-mile item
    for item in origin_last_mile:
        target_name = (from_station["name"] if transport_mode == "train" else (from_bus_stand["name"] if transport_mode == "bus" else from_airport["name"]))
        item["maps_url"] = f"https://www.google.com/maps/dir/?api=1&origin={requests.utils.quote(from_place)}&destination={requests.utils.quote(target_name)}"

    # Generate Domain Links & Availability Tools
    from_stn_c = from_station["code"]
    dest_stn_c = dest_station["code"]
    from_air_c = from_airport["code"]
    dest_air_c = dest_airport["code"]
    from_enc = requests.utils.quote(from_clean)
    dest_enc = requests.utils.quote(dest_clean)

    domain_links = {
        "where_is_my_train": {
            "title": "Where Is My Train (Live Status)",
            "icon": "📡",
            "badge": "Live Train & Platform GPS",
            "url": f"https://www.google.com/search?q={from_stn_c}+to+{dest_stn_c}+where+is+my+train+live+running+status+trains",
            "official_url": "https://whereismytrain.in/",
            "desc": f"Live GPS running status, platform numbers & delay alerts between {from_station['name']} ({from_stn_c}) and {dest_station['name']} ({dest_stn_c})"
        },
        "confirmtkt": {
            "title": "ConfirmTkt Live Availability",
            "icon": "🎟️",
            "badge": "Seat Availability & Confirmation",
            "url": f"https://www.confirmtkt.com/rts/#/train-search/{from_stn_c}/{dest_stn_c}",
            "desc": f"Check live seat availability, waitlist clearance predictions & alternate train routes for {from_clean} → {dest_clean}"
        },
        "irctc": {
            "title": "IRCTC Official Booking",
            "icon": "🏛️",
            "badge": "Official Railway Booking",
            "url": f"https://www.irctc.co.in/nget/train-search",
            "desc": f"Official Indian Railways portal to book confirmed train tickets with Tatkal and General quota"
        },
        "railyatri": {
            "title": "RailYatri Timetable & PNR",
            "icon": "🕒",
            "badge": "Schedule & PNR Status",
            "url": f"https://www.railyatri.in/trains-between-stations?from_code={from_stn_c}&to_code={dest_stn_c}",
            "desc": f"Complete timetable, fare classes (SL, 3AC, 2AC, 1AC, Vande Bharat) & train seat charts"
        },
        "redbus": {
            "title": "RedBus Live Bus Booking",
            "icon": "🚌",
            "badge": "Seat Layout & Live Bus GPS",
            "url": f"https://www.redbus.in/bus-tickets/{from_clean.lower().replace(' ', '-')}-to-{dest_clean.lower().replace(' ', '-')}",
            "desc": f"Real-time seat selection, boarding point selection, AC Sleeper / Volvo and live tracking"
        },
        "abhibus": {
            "title": "AbhiBus Deals & State RTCs",
            "icon": "🎫",
            "badge": "RTC & Private Bus Offers",
            "url": f"https://www.abhibus.com/bus-ticket-booking/{from_clean.lower().replace(' ', '-')}-to-{dest_clean.lower().replace(' ', '-')}",
            "desc": f"Direct booking for State RTCs (KSRTC, TNSTC, MSRTC, GSRTC, UPSRTC) & top private operators"
        },
        "google_flights": {
            "title": "Google Flights Live Tracker",
            "icon": "✈️",
            "badge": "Real-time Fares & Timetables",
            "url": f"https://www.google.com/travel/flights?q=Flights%20from%20{from_air_c}%20to%20{dest_air_c}",
            "desc": f"Compare nonstop flights, live prices and airline schedules from {from_airport['name']} ({from_air_c}) to {dest_airport['name']} ({dest_air_c})"
        },
        "skyscanner": {
            "title": "Skyscanner Price Comparison",
            "icon": "🛫",
            "badge": "Lowest Fare Calendar",
            "url": f"https://www.skyscanner.co.in/transport/flights/{from_air_c.lower()}/{dest_air_c.lower()}",
            "desc": f"Find the cheapest departure days and compare airlines across IndiGo, Air India, SpiceJet, Akasa"
        },
        "makemytrip_flights": {
            "title": "MakeMyTrip Flight Booking",
            "icon": "🌐",
            "badge": "Instant Web Check-in & Deals",
            "url": f"https://www.makemytrip.com/flight/search?itinerary={from_air_c}-{dest_air_c}",
            "desc": f"Book domestic flights with zero cancellation options and student/senior citizen discounts"
        },
        "google_transit": {
            "title": "Google Maps Transit Route",
            "icon": "🗺️",
            "badge": "Step-by-Step Public Transit",
            "url": f"https://www.google.com/maps/dir/?api=1&origin={requests.utils.quote(from_place)}&destination={requests.utils.quote(destination)}&travelmode=transit",
            "desc": f"Full step-by-step public transit directions from {from_clean} to {dest_clean} with live departure times"
        }
    }

    # Station Google Maps links
    from_station["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(from_station['name'] + ' ' + from_clean)}"
    dest_station["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(dest_station['name'] + ' ' + dest_clean)}"
    from_bus_stand["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(from_bus_stand['name'] + ' ' + from_clean)}"
    dest_bus_stand["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(dest_bus_stand['name'] + ' ' + dest_clean)}"
    from_airport["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(from_airport['name'] + ' ' + from_clean)}"
    dest_airport["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(dest_airport['name'] + ' ' + dest_clean)}"

    return {
        "transport_mode": transport_mode,
        "from_clean": from_clean,
        "dest_clean": dest_clean,
        "from_station": from_station,
        "from_all_stations": from_all_stations,
        "dest_station": dest_station,
        "dest_all_stations": dest_all_stations,
        "from_bus_stand": from_bus_stand,
        "dest_bus_stand": dest_bus_stand,
        "from_airport": from_airport,
        "dest_airport": dest_airport,
        "origin_last_mile": origin_last_mile,
        "dest_last_mile": dest_last_mile,
        "domain_links": domain_links
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

    # Inbox entries for feedback and user messages
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inbox_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            email TEXT,
            subject TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Saved places (Home, Work, Favorites)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            place_type TEXT,
            label TEXT,
            address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


@app.route("/api/saved_places", methods=["GET", "POST"])
def api_saved_places():
    user_id = session.get("user_id")
    conn = get_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        place_type = data.get("place_type", "favorite").strip().lower()
        label = data.get("label", "").strip() or place_type.capitalize()
        address = data.get("address", "").strip()
        if not address:
            conn.close()
            return jsonify({"error": "Address is required"}), 400

        if user_id:
            if place_type in ("home", "work"):
                existing = conn.execute(
                    "SELECT id FROM saved_places WHERE user_id = ? AND place_type = ?",
                    (user_id, place_type),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE saved_places SET address = ?, label = ? WHERE id = ?",
                        (address, label, existing["id"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO saved_places (user_id, place_type, label, address) VALUES (?, ?, ?, ?)",
                        (user_id, place_type, label, address),
                    )
            else:
                conn.execute(
                    "INSERT INTO saved_places (user_id, place_type, label, address) VALUES (?, ?, ?, ?)",
                    (user_id, place_type, label, address),
                )
            conn.commit()
        conn.close()
        return jsonify({"success": True, "place_type": place_type, "label": label, "address": address})

    # GET
    places = []
    if user_id:
        rows = conn.execute(
            "SELECT id, place_type, label, address FROM saved_places WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
        places = [dict(r) for r in rows]
    conn.close()
    return jsonify({"places": places})


@app.route("/api/saved_places/<place_type>", methods=["DELETE"])
def api_delete_saved_place(place_type):
    user_id = session.get("user_id")
    if user_id:
        conn = get_db()
        conn.execute(
            "DELETE FROM saved_places WHERE user_id = ? AND place_type = ?",
            (user_id, place_type),
        )
        conn.commit()
        conn.close()
    return jsonify({"success": True})


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
            is_admin = False
            if row:
                try:
                    is_admin = bool(row['is_admin'])
                except Exception:
                    is_admin = False
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
        is_admin = False
        if not user:
            return Response("Forbidden", status=403)
        try:
            is_admin = bool(user['is_admin'])
        except Exception:
            is_admin = False
        if not is_admin:
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

    # Check whether user explicitly submitted values (including "0")
    raw_places = request.form.get("places_to_visit", "").strip()
    raw_entry_fee = request.form.get("per_places_entry_fee", "").strip()
    raw_room_cost = request.form.get("room_cost", "").strip()
    raw_toll = request.form.get("toll_charges", "").strip()

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
        transport_cost = 0.0
    elif transport_mode in ("bike", "car"):
        fuel_cost = (total_distance / mileage * fuel_price) if mileage > 0 else 0.0
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

    avoid_tolls = request.form.get("avoid_tolls") in ("1", "true", "yes", "on")
    avoid_highways = request.form.get("avoid_highways") in ("1", "true", "yes", "on")
    avoid_ferries = request.form.get("avoid_ferries") in ("1", "true", "yes", "on")

    raw_stops_json = request.form.get("stops_json", "").strip()
    stops = []
    if raw_stops_json:
        try:
            parsed_stops = json.loads(raw_stops_json)
            if isinstance(parsed_stops, list):
                stops = [str(s).strip() for s in parsed_stops if str(s).strip()]
        except Exception:
            stops = [s.strip() for s in raw_stops_json.split("|") if s.strip()]

    # Round-trip tolls: calculate return journey highway tolls properly when round_trip == 'yes'
    if avoid_tolls:
        one_way_toll = 0.0
        toll_charges = 0.0
    elif raw_toll != "":
        one_way_toll = get_float("toll_charges")
        toll_charges = one_way_toll * 2 if round_trip == "yes" else one_way_toll
    elif transport_mode == "car":
        if distance <= 100:
            one_way_toll = 0.0
        elif distance <= 300:
            one_way_toll = 150.0
        elif distance <= 600:
            one_way_toll = 400.0
        else:
            one_way_toll = 700.0
        toll_charges = one_way_toll * 2 if round_trip == "yes" else one_way_toll
    else:
        one_way_toll = 0.0
        toll_charges = 0.0

    destination_details = destination_budget_details(destination, trip_days)

    # Keep user input: stop overwriting user-entered values with automated defaults when user explicitly submits 0
    places_from_destination = False
    room_from_destination = False

    if raw_places != "":
        places_to_visit = get_int("places_to_visit")
    elif destination_details.get("places_count", 0) > 0:
        places_to_visit = destination_details["places_count"]
        places_from_destination = True
    else:
        places_to_visit = 0

    if raw_entry_fee != "":
        per_places_entry_fee = get_float("per_places_entry_fee")
    elif places_from_destination:
        per_places_entry_fee = destination_details.get("per_place_fee", 0.0)
    else:
        per_places_entry_fee = 0.0

    places_fee_total = places_to_visit * per_places_entry_fee

    if raw_room_cost != "":
        room_cost_per_day = get_float("room_cost")
    elif destination_details.get("hotels"):
        room_cost_per_day = destination_details["room_per_day"]
        room_from_destination = True
    else:
        room_cost_per_day = 0.0

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
    cost_per_person = (total_budget / travelers) if travelers > 0 else total_budget
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
        "bike": round((total_distance / (mileage if mileage > 0 else 45)) * fuel_price, 2),
        "car": round((total_distance / (mileage if mileage > 0 else 15)) * fuel_price, 2),
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

    # Filter viable practical transport modes by travel distance:
    if total_distance <= 15:
        viable_modes = [m for m in mode_impacts if m["mode"] in ("walk", "bike", "car", "bus")]
    elif total_distance <= 100:
        viable_modes = [m for m in mode_impacts if m["mode"] in ("bike", "car", "bus", "train")]
    elif total_distance <= 400:
        viable_modes = [m for m in mode_impacts if m["mode"] in ("car", "bus", "train")]
    elif total_distance <= 900:
        viable_modes = [m for m in mode_impacts if m["mode"] in ("train", "car", "bus", "flight")]
    else:
        viable_modes = [m for m in mode_impacts if m["mode"] in ("flight", "train", "car")]

    if not viable_modes:
        viable_modes = mode_impacts

    eco_choice = min(viable_modes, key=lambda item: item["emissions"])
    economy_choice = min(viable_modes, key=lambda item: item["cost"])

    # Smart "Best to Go" recommendation automatically determined by distance to travel:
    if total_distance <= 5:
        best_mode = "walk" if total_distance <= 2 else "bike"
        best_reason = f"Ideal for short {total_distance} km trip with zero fuel and minimal emissions."
    elif total_distance <= 40:
        best_mode = "bike" if travelers == 1 else "car"
        best_reason = f"Fastest & most convenient door-to-door transit for {total_distance} km."
    elif total_distance <= 300:
        best_mode = "car" if travelers >= 2 else "bus"
        best_reason = f"Optimal comfort, flexible halts, and great value for {total_distance} km road trip."
    elif total_distance <= 900:
        best_mode = "train"
        best_reason = f"Top-rated eco-friendly and relaxed choice for {total_distance} km intercity travel."
    else:
        best_mode = "flight" if total_distance > 1200 else "train"
        best_reason = f"Fastest journey and maximum convenience for long-distance {total_distance} km travel."

    best_choice = next((m for m in mode_impacts if m["mode"] == best_mode), economy_choice)
    best_choice = {**best_choice, "reason": best_reason}

    # Parse user-selected tourist sights, meals, and hotel tier from Step 3
    raw_places_json = request.form.get("selected_places_json", "").strip()
    selected_places = []
    if raw_places_json:
        try:
            selected_places = json.loads(raw_places_json)
            for p in selected_places:
                if "maps_url" not in p or not p["maps_url"]:
                    p["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(p.get('name', '') + ' ' + destination)}"
        except Exception:
            selected_places = []

    raw_meals_json = request.form.get("selected_meals_json", "").strip()
    selected_meals = []
    if raw_meals_json:
        try:
            selected_meals = json.loads(raw_meals_json)
            for m in selected_meals:
                if "maps_url" not in m or not m["maps_url"]:
                    m["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(m.get('name', '') + ' restaurants in ' + destination)}"
                if "google_url" not in m or not m["google_url"]:
                    m["google_url"] = f"https://www.google.com/search?q={requests.utils.quote('best ' + m.get('name', '') + ' in ' + destination)}"
        except Exception:
            selected_meals = []

    raw_hotel_json = request.form.get("selected_hotel_json", "").strip()
    selected_hotel = None
    if raw_hotel_json:
        try:
            selected_hotel = json.loads(raw_hotel_json)
            if selected_hotel:
                if "maps_link" not in selected_hotel or not selected_hotel["maps_link"]:
                    selected_hotel["maps_link"] = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(selected_hotel.get('name', 'hotels') + ' in ' + destination)}"
                if "google_link" not in selected_hotel or not selected_hotel["google_link"]:
                    selected_hotel["google_link"] = f"https://www.google.com/travel/hotels/{requests.utils.quote(destination)}"
        except Exception:
            selected_hotel = None

    dest_encoded = requests.utils.quote(destination)
    short_dest = short_location(destination)
    short_encoded = requests.utils.quote(short_dest.lower())

    transit_details = None
    if transport_mode in ("train", "bus", "flight"):
        transit_details = get_transit_hub_details(from_location, destination, transport_mode)

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
        "transit_details": transit_details,
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
        "best_choice": best_choice,
        "bus_cost": round(bus_cost, 2),
        "train_cost": round(train_cost, 2),
        "flight_cost": round(flight_cost, 2),
        "image_url": (
            "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"
            "?auto=format&fit=crop&w=1200&q=80"
        ),
        "destination_attractions": destination_details["attractions"],
        "destination_hotels": destination_details["hotels"],
        "destination_dining": destination_details.get("dining", []),
        "destination_tier": destination_details["tier_label"],
        "places_from_destination": places_from_destination,
        "room_from_destination": room_from_destination,
        "places_to_visit": places_to_visit,
        "per_places_entry_fee": round(per_places_entry_fee, 2),
        "selected_places": selected_places,
        "selected_meals": selected_meals,
        "selected_hotel": selected_hotel,
        "all_places_maps": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('tourist places in ' + destination)}",
        "all_food_maps": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('restaurants in ' + destination)}",
        "all_food_google": f"https://www.google.com/search?q={requests.utils.quote('famous local food in ' + destination)}",
        "all_hotels_maps": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('hotels in ' + destination)}",
        "all_hotels_google": f"https://www.google.com/travel/hotels/{dest_encoded}",
        "oyo_link": f"https://www.oyorooms.com/search?location={dest_encoded}",
        "mmt_link": f"https://www.makemytrip.com/hotels/{short_encoded}-hotels.html",
        "stops": stops,
        "avoid_tolls": avoid_tolls,
        "avoid_highways": avoid_highways,
        "avoid_ferries": avoid_ferries,
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
            is_active = 1
            try:
                is_active = int(user['is_active']) if user['is_active'] is not None else 1
            except Exception:
                is_active = 1
            if is_active == 0:
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
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/dashboard')
@login_required
@require_admin
def admin_dashboard():
    conn = get_db()
    try:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0]
        online_users = conn.execute("SELECT COUNT(*) FROM users WHERE last_seen > datetime('now','-15 minutes')").fetchone()[0]
    except Exception:
        total_users = active_users = online_users = 0

    try:
        total_trips = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
        total_spend_row = conn.execute("SELECT COALESCE(SUM(total_budget), 0) FROM trips").fetchone()[0]
        total_spend = round(float(total_spend_row), 2) if total_spend_row else 0.0
    except Exception:
        total_trips = 0
        total_spend = 0.0

    # Transport mode breakdown
    transport_breakdown = []
    try:
        rows = conn.execute("""
            SELECT COALESCE(NULLIF(transport_mode, ''), 'other') as mode,
                   COUNT(*) as count,
                   COALESCE(SUM(total_budget), 0) as spend
            FROM trips
            GROUP BY mode
            ORDER BY count DESC
        """).fetchall()
        grand_trips = sum(r["count"] for r in rows) or 1
        mode_icons = {
            "car": "🚗",
            "bike": "🏍️",
            "bus": "🚌",
            "train": "🚆",
            "flight": "✈️",
            "walk": "🚶",
            "other": "📍",
        }
        transport_breakdown = [
            {
                "mode": r["mode"],
                "label": r["mode"].capitalize(),
                "icon": mode_icons.get(r["mode"].lower(), "📍"),
                "count": r["count"],
                "spend": round(float(r["spend"]), 2),
                "percentage": round((r["count"] / grand_trips) * 100, 1),
            }
            for r in rows
        ]
    except Exception:
        transport_breakdown = []

    # Recent audit logs
    recent_audits = []
    try:
        rows = conn.execute("""
            SELECT id, actor_user_id, action, target_user_id, details, created_at
            FROM audit_logs
            ORDER BY id DESC
            LIMIT 15
        """).fetchall()
        recent_audits = [dict(r) for r in rows]
    except Exception:
        recent_audits = []

    # Feedback / inbox entries
    feedback_count = 0
    inbox_entries = []
    try:
        feedback_count = conn.execute("SELECT COUNT(*) FROM inbox_entries").fetchone()[0]
        fb_rows = conn.execute("""
            SELECT id, user_id, name, email, subject, message, created_at
            FROM inbox_entries
            ORDER BY id DESC
            LIMIT 25
        """).fetchall()
        inbox_entries = [dict(r) for r in fb_rows]
    except Exception:
        feedback_count = 0
        inbox_entries = []

    conn.close()
    return render_template(
        'admin_dashboard.html',
        total_users=total_users,
        active_users=active_users,
        online_users=online_users,
        total_trips=total_trips,
        total_spend=total_spend,
        transport_breakdown=transport_breakdown,
        recent_audits=recent_audits,
        feedback_count=feedback_count,
        inbox_entries=inbox_entries,
    )


@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    # Admin-specific login: only allows users who have is_admin=1 and is_active=1
    if 'user_id' in session:
        # If already logged in and an admin, go to admin. If logged-in non-admin, log out first.
        conn = get_db()
        try:
            row = conn.execute('SELECT is_admin FROM users WHERE id=?', (session['user_id'],)).fetchone()
            is_admin = False
            if row is not None:
                try:
                    is_admin = bool(row['is_admin'])
                except Exception:
                    is_admin = False
            conn.close()
            if is_admin:
                return redirect(url_for('admin_dashboard'))
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
        session.clear()

    error = ''
    next_page = request.values.get('next', '')
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            # require admin and active
            is_active = 1
            try:
                is_active = int(user['is_active']) if user['is_active'] is not None else 1
            except Exception:
                is_active = 1
            try:
                is_admin = bool(user['is_admin'])
            except Exception:
                is_admin = False
            if is_active == 0:
                error = 'This account has been deactivated. Contact an administrator.'
            elif not is_admin:
                error = 'Admin access required. This account is not an administrator.'
            else:
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                return redirect(url_for('admin_dashboard'))
        else:
            error = 'Email or password is incorrect.'
    return render_template('admin_login.html', error=error, next_page=next_page)


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
    # Convert sqlite3.Row objects to plain dicts so templates can safely use dict methods like .get
    users = [dict(r) for r in rows]
    conn.close()
    return render_template('admin_members.html', users=users, q=q, page=page, total_pages=total_pages, total=total)


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
    user_row = conn.execute("SELECT id, name, email, created_at, is_admin FROM users WHERE id=?", (user_id,)).fetchone()
    if not user_row:
        conn.close()
        return redirect(url_for('admin_members'))
    # convert to dict for template safety
    user = dict(user_row)
    total = conn.execute("SELECT COUNT(*) FROM trips WHERE user_id=?", (user_id,)).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    trips = conn.execute(
        "SELECT * FROM trips WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
        (user_id, per_page, (page - 1) * per_page),
    ).fetchall()
    # convert trips rows to dicts too (templates may access keys)
    trips = [dict(t) for t in trips]
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
    return redirect(url_for('admin_dashboard'))


@app.route('/feedback', methods=['POST'])
def feedback():
    """Receive feedback from users and store in inbox_entries table.
    If inbox_entries does not exist, create it (simple dev-friendly behavior).
    """
    name = request.form.get('name') or session.get('user_name') or ''
    email = request.form.get('email') or ''
    subject = request.form.get('subject') or f'Feedback about {request.form.get("destination","")}'
    message = request.form.get('message') or ''
    user_id = session.get('user_id')
    conn = get_db()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS inbox_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                email TEXT,
                subject TEXT,
                message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('INSERT INTO inbox_entries (user_id, name, email, subject, message) VALUES (?, ?, ?, ?, ?)',
                     (user_id, name, email, subject, message))
        conn.commit()
    except Exception:
        # Non-fatal — ignore insertion errors to avoid breaking the user flow
        pass
    finally:
        conn.close()
    # Redirect back to the referring page if present
    ref = request.headers.get('Referer') or url_for('planner')
    return redirect(ref)


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
        "cost_per_person": round(total_budget / travelers, 2) if travelers > 0 else round(total_budget, 2),
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
    stops_param = request.args.get("stops", "").strip()
    avoid_tolls = request.args.get("avoid_tolls") in ("1", "true", "yes")
    avoid_highways = request.args.get("avoid_highways") in ("1", "true", "yes")
    avoid_ferries = request.args.get("avoid_ferries") in ("1", "true", "yes")

    stops = []
    if stops_param:
        try:
            if stops_param.startswith("["):
                parsed = json.loads(stops_param)
                if isinstance(parsed, list):
                    stops = [str(s).strip() for s in parsed if str(s).strip()]
            else:
                stops = [s.strip() for s in stops_param.split("|") if s and s.strip()]
        except Exception:
            stops = [s.strip() for s in stops_param.split("|") if s and s.strip()]

    # Construct Google Maps external directions URL with waypoints & avoid options
    gmaps_avoid_flags = []
    if avoid_tolls:
        gmaps_avoid_flags.append("t")
    if avoid_highways:
        gmaps_avoid_flags.append("h")
    if avoid_ferries:
        gmaps_avoid_flags.append("f")

    avoid_query = f"&avoid={'|'.join(gmaps_avoid_flags)}" if gmaps_avoid_flags else ""
    waypoints_query = f"&waypoints={'|'.join([requests.utils.quote(s) for s in stops])}" if stops else ""
    gmaps_directions_url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={requests.utils.quote(from_place)}"
        f"&destination={requests.utils.quote(destination)}"
        f"{waypoints_query}{avoid_query}"
    )

    if GOOGLE_DIRECTIONS_API_KEY:
        try:
            params = {
                "origin": from_place,
                "destination": destination,
                "mode": "driving",
                "key": GOOGLE_DIRECTIONS_API_KEY,
            }
            if stops:
                params["waypoints"] = "|".join(stops)
            g_avoids = []
            if avoid_tolls:
                g_avoids.append("tolls")
            if avoid_highways:
                g_avoids.append("highways")
            if avoid_ferries:
                g_avoids.append("ferries")
            if g_avoids:
                params["avoid"] = "|".join(g_avoids)

            response = requests.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            route = response.json().get("routes", [None])[0]
            if route and route.get("legs"):
                total_meters = sum(leg["distance"]["value"] for leg in route["legs"])
                total_secs = sum(leg["duration"]["value"] for leg in route["legs"])
                start_pt = route["legs"][0]["start_location"]
                end_pt = route["legs"][-1]["end_location"]
                stop_pts = [leg["end_location"] for leg in route["legs"][:-1]]
                return jsonify({
                    "distance": round(total_meters / 1000, 2),
                    "duration": round(total_secs / 3600, 2),
                    "start_coords": [start_pt["lat"], start_pt["lng"]],
                    "end_coords": [end_pt["lat"], end_pt["lng"]],
                    "stop_coords": [[p["lat"], p["lng"]] for p in stop_pts],
                    "gmaps_url": gmaps_directions_url,
                    "stops": stops,
                    "avoid_tolls": avoid_tolls,
                    "avoid_highways": avoid_highways,
                    "avoid_ferries": avoid_ferries,
                })
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            pass

    # Geocoding & multi-stop OSRM route fallback
    all_points_labels = [from_place] + stops + [destination]
    point_coords = []
    try:
        for label in all_points_labels:
            pt = geocode(label)
            if pt is None:
                return jsonify({"error": f"Unable to locate '{label}'"}), 422
            point_coords.append(pt)  # (lon, lat)
    except requests.RequestException:
        return jsonify({"error": "Location search is temporarily unavailable. Please try again."}), 503

    start_lat_lon = [point_coords[0][1], point_coords[0][0]]
    end_lat_lon = [point_coords[-1][1], point_coords[-1][0]]
    stop_coords = [[c[1], c[0]] for c in point_coords[1:-1]]

    try:
        route_coords = [start_lat_lon] + stop_coords + [end_lat_lon]
        coordinates_str = ";".join(f"{c[0]},{c[1]}" for c in point_coords)

        response = requests.get(
            f"https://router.project-osrm.org/route/v1/driving/{coordinates_str}",
            params={"overview": "simplified", "geometries": "geojson"},
            headers={"User-Agent": "TravelBudgetPlanner/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        route = response.json().get("routes", [None])[0]
        if not route:
            raise ValueError("No route found")

        distance_km = round(route["distance"] / 1000, 2)
        duration_hr = round(route["duration"] / 3600, 2)

        # Non-highway / avoid tolls routing adjustment
        if avoid_highways or avoid_tolls:
            distance_km = round(distance_km * 1.08, 2)
            duration_hr = round(duration_hr * 1.15, 2)

        raw_geojson_coords = route.get("geometry", {}).get("coordinates", [])
        if raw_geojson_coords:
            route_coords = [[c[1], c[0]] for c in raw_geojson_coords]

        return jsonify({
            "distance": distance_km,
            "duration": duration_hr,
            "start_coords": start_lat_lon,
            "end_coords": end_lat_lon,
            "stop_coords": stop_coords,
            "route_geometry": route_coords,
            "gmaps_url": gmaps_directions_url,
            "stops": stops,
            "avoid_tolls": avoid_tolls,
            "avoid_highways": avoid_highways,
            "avoid_ferries": avoid_ferries,
        })
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        # Straight line geodetic estimate fallback if OSRM is unreachable
        distance_km = 0
        for i in range(len(point_coords) - 1):
            p1, p2 = point_coords[i], point_coords[i+1]
            # Simple Haversine approximation
            import math
            lat1, lon1 = math.radians(p1[1]), math.radians(p1[0])
            lat2, lon2 = math.radians(p2[1]), math.radians(p2[0])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance_km += 6371.0 * c * 1.25 # Road curvature factor

        distance_km = round(distance_km, 2)
        duration_hr = round(distance_km / 65, 2)
        return jsonify({
            "distance": distance_km,
            "duration": duration_hr,
            "start_coords": start_lat_lon,
            "end_coords": end_lat_lon,
            "stop_coords": stop_coords,
            "route_geometry": [start_lat_lon] + stop_coords + [end_lat_lon],
            "gmaps_url": gmaps_directions_url,
            "stops": stops,
            "avoid_tolls": avoid_tolls,
            "avoid_highways": avoid_highways,
            "avoid_ferries": avoid_ferries,
        })


@app.route("/location_suggestions")
def location_suggestions():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    local_matches = []
    q_lower = query.lower()
    for city in INDIAN_CITY_SUGGESTIONS:
        if q_lower in city.lower():
            parts = [p.strip() for p in city.split(",")]
            main_text = parts[0] if parts else city
            secondary_text = ", ".join(parts[1:]) if len(parts) > 1 else ""
            local_matches.append({
                "label": city,
                "main_text": main_text,
                "secondary_text": secondary_text,
            })
    local_matches = local_matches[:5]

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
                    {
                        "label": pred["description"],
                        "main_text": pred.get("structured_formatting", {}).get("main_text", pred["description"].split(",")[0]),
                        "secondary_text": pred.get("structured_formatting", {}).get("secondary_text", ""),
                    }
                    for pred in predictions[:5]
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
        results = []
        for place in response.json():
            display = place.get("display_name", "")
            parts = [p.strip() for p in display.split(",")]
            main_text = parts[0] if parts else display
            secondary_text = ", ".join(parts[1:4]) if len(parts) > 1 else ""
            results.append({
                "label": display,
                "main_text": main_text,
                "secondary_text": secondary_text,
                "lat": place.get("lat"),
                "lon": place.get("lon"),
            })
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

    # Always ensure vibrant, interesting stops are provided for "More on the route"
    if not on_the_way:
        orig_name = short_location(origin) or "Departure City"
        dest_name = short_location(destination) or "Destination"
        on_the_way = [
            {
                "name": "Midway Express Highway Plaza & Food Oasis",
                "address": f"National Highway Corridor between {orig_name} & {dest_name}",
                "rating": 4.6,
                "category": "Highway Food Plaza & Clean Restrooms",
                "entry_fee": 0,
                "recommended_pause": "30 mins rest pause",
                "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80",
            },
            {
                "name": "Scenic Panoramic Ridge & Tea Lounge",
                "address": f"Scenic Midway Bypass near {dest_name}",
                "rating": 4.7,
                "category": "Scenic Viewpoint & Refreshments",
                "entry_fee": 0,
                "recommended_pause": "20 mins photo pause",
                "image_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=600&q=80",
            },
            {
                "name": "Heritage Waypoint & Regional Crafts Bazaar",
                "address": f"Historic Midway Junction on the {orig_name}–{dest_name} Highway",
                "rating": 4.5,
                "category": "Cultural Landmark & Local Snacks",
                "entry_fee": 40,
                "recommended_pause": "40 mins exploration",
                "image_url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=600&q=80",
            }
        ]

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


@app.route("/destination_options")
def destination_options():
    destination = request.args.get("destination", "").strip()
    if not destination:
        return jsonify({"places": [], "food_meals": [], "hotels": [], "links": {}})

    details = destination_budget_details(destination, 1)
    estimate = location_cost_estimate(destination)
    base_food = estimate["food"]
    base_room = estimate["room"]
    dest_encoded = requests.utils.quote(destination)
    short_dest = short_location(destination)
    short_encoded = requests.utils.quote(short_dest.lower())

    food_meals = [
        {
            "id": "breakfast",
            "name": "Breakfast",
            "time": "Morning (8:00 AM – 10:30 AM)",
            "cost": round(base_food * 0.22),
            "desc": "Fresh Breakfast, Parathas / South Indian & Hot Chai / Coffee",
            "icon": "🌅",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('breakfast restaurants in ' + destination)}",
            "google_url": f"https://www.google.com/search?q={requests.utils.quote('best breakfast in ' + destination)}"
        },
        {
            "id": "lunch",
            "name": "Lunch Thali",
            "time": "Afternoon (12:30 PM – 3:30 PM)",
            "cost": round(base_food * 0.38),
            "desc": "Regional Specialty Thali / Multi-Cuisine Meal",
            "icon": "☀️",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('lunch restaurants thali in ' + destination)}",
            "google_url": f"https://www.google.com/search?q={requests.utils.quote('best thali lunch in ' + destination)}"
        },
        {
            "id": "snacks",
            "name": "Evening Snacks",
            "time": "Evening (5:00 PM – 7:00 PM)",
            "cost": round(base_food * 0.15),
            "desc": "Local Street Bites, Chaat & Evening Refreshments",
            "icon": "☕",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('street food chaat snacks in ' + destination)}",
            "google_url": f"https://www.google.com/search?q={requests.utils.quote('famous street food in ' + destination)}"
        },
        {
            "id": "dinner",
            "name": "Dinner",
            "time": "Night (7:30 PM – 10:30 PM)",
            "cost": round(base_food * 0.42),
            "desc": "Specialty Dinner, Signature Curries & Breads",
            "icon": "🌙",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('dinner restaurants in ' + destination)}",
            "google_url": f"https://www.google.com/search?q={requests.utils.quote('best dinner restaurants in ' + destination)}"
        }
    ]

    hotels = [
        {
            "id": "budget",
            "name": "Budget Stay / OYO Rooms",
            "type": "Budget / OYO",
            "cost": round(base_room * 0.65),
            "desc": "Clean AC Room, Free Wi-Fi & Essential Amenities",
            "icon": "🏷️",
            "link": f"https://www.oyorooms.com/search?location={dest_encoded}",
            "google_link": f"https://www.google.com/travel/hotels/{dest_encoded}",
            "maps_link": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('budget hotels in ' + destination)}"
        },
        {
            "id": "standard",
            "name": "Standard Comfort Hotel",
            "type": "3-Star Hotel",
            "cost": base_room,
            "desc": "Spacious Room, Restaurant, Parking & Daily Housekeeping",
            "icon": "🛎️",
            "link": f"https://www.makemytrip.com/hotels/{short_encoded}-hotels.html",
            "google_link": f"https://www.google.com/travel/hotels/{dest_encoded}",
            "maps_link": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('hotels in ' + destination)}"
        },
        {
            "id": "premium",
            "name": "Premium Resort & Suites",
            "type": "Resort / Luxury",
            "cost": round(base_room * 1.6),
            "desc": "Scenic Views, Pool, Breakfast Included & Luxury Stays",
            "icon": "🌟",
            "link": f"https://www.google.com/travel/hotels/{dest_encoded}",
            "google_link": f"https://www.google.com/travel/hotels/{dest_encoded}",
            "maps_link": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('luxury resorts in ' + destination)}"
        }
    ]

    places = [
        {
            "name": p["name"],
            "address": p.get("address", destination),
            "entry_fee": p.get("entry_fee", 50),
            "rating": p.get("rating", 4.5),
            "image_url": p.get("image_url", ""),
            "maps_url": p.get("maps_url", f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(p['name'] + ' ' + destination)}")
        }
        for p in details.get("attractions", [])
    ]

    links = {
        "oyo": f"https://www.oyorooms.com/search?location={dest_encoded}",
        "makemytrip": f"https://www.makemytrip.com/hotels/{short_encoded}-hotels.html",
        "google": f"https://www.google.com/travel/hotels/{dest_encoded}",
        "all_places_maps": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('tourist places in ' + destination)}",
        "all_food_maps": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('restaurants in ' + destination)}",
        "all_food_google": f"https://www.google.com/search?q={requests.utils.quote('famous local food in ' + destination)}",
        "all_hotels_maps": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote('hotels in ' + destination)}",
    }

    return jsonify({
        "destination": destination,
        "tier": estimate["tier"],
        "places": places,
        "food_meals": food_meals,
        "hotels": hotels,
        "links": links,
        "base_food": base_food,
        "base_room": base_room
    })


@app.route("/api/transit_details")
def api_transit_details():
    from_place = request.args.get("from", "").strip()
    destination = request.args.get("destination", "").strip()
    mode = request.args.get("mode", "train").strip().lower()
    if mode not in ("train", "bus", "flight"):
        mode = "train"

    if not from_place and not destination:
        return jsonify({"error": "Please provide from or destination location"}), 400

    details = get_transit_hub_details(from_place, destination, mode)
    return jsonify(details)


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
