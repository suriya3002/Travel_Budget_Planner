// ===============================
// Travel Budget Planner Script
// ===============================

let userLat = 0;
let userLon = 0;
let oneWayDistance = 0;
let currentStep = 1;
const totalSteps = 3;

const busHints = {
    "0.835": "Rate used: ₹0.84/km per person",
    "1.90":  "Rate used: ₹1.90/km per person",
    "2.00":  "Rate used: ₹2.00/km per person",
    "3.25":  "Rate used: ₹3.25/km per person"
};

const trainHints = {
    "0.40": "Rate used: ₹0.40/km per person",
    "0.65": "Rate used: ₹0.65/km per person",
    "1.80": "Rate used: ₹1.80/km per person",
    "2.50": "Rate used: ₹2.50/km per person",
    "3.10": "Rate used: ₹3.10/km per person",
    "4.00": "Rate used: ₹4.00/km per person"
};

const flightHints = {
    "4.75":  "Rate used: ₹4.75/km per person",
    "7.00":  "Rate used: ₹7.00/km per person",
    "14.00": "Rate used: ₹14.00/km per person",
    "27.50": "Rate used: ₹27.50/km per person"
};

const speed = {
    walk: 5,
    bike: 45,
    car: 70,
    bus: 50,
    train: 80,
    flight: 700
};

// --------------------
// Multi-step form
// --------------------

function changeStep(direction) {
    const next = currentStep + direction;
    if (next < 1 || next > totalSteps) return;

    if (direction > 0 && !validateStep(currentStep)) return;

    const currentEl = document.querySelector(`.form-step[data-step="${currentStep}"]`);
    currentEl.classList.remove("active");
    if (direction > 0) currentEl.classList.add("exit-left");

    currentStep = next;

    setTimeout(() => {
        document.querySelectorAll(".form-step").forEach(s => s.classList.remove("exit-left"));
        const nextEl = document.querySelector(`.form-step[data-step="${currentStep}"]`);
        nextEl.classList.add("active");

        nextEl.querySelectorAll(".animate-in").forEach(el => {
            el.style.animation = "none";
            el.offsetHeight;
            el.style.animation = "";
        });
    }, direction > 0 ? 280 : 0);

    updateStepUI();
}

function validateStep(step) {
    if (step === 1) {
        const travelers = document.getElementById("travelers");
        if (!travelers.value || travelers.value < 1) {
            travelers.focus();
            shakeField(travelers);
            return false;
        }
    }
    if (step === 2) {
        const from = document.getElementById("from_location");
        const dest = document.getElementById("destination");
        const dist = document.getElementById("distance");
        if (!from.value.trim()) { shakeField(from); from.focus(); return false; }
        if (!dest.value.trim()) { shakeField(dest); dest.focus(); return false; }
        if (!dist.value || parseFloat(dist.value) <= 0) {
            alert("Please wait for distance to calculate, or check your locations.");
            return false;
        }
    }
    return true;
}

function shakeField(el) {
    el.closest(".field-group")?.classList.add("shake");
    setTimeout(() => el.closest(".field-group")?.classList.remove("shake"), 500);
}

function updateStepUI() {
    const progress = (currentStep / totalSteps) * 100;
    document.getElementById("progress_bar").style.width = progress + "%";

    document.querySelectorAll(".step-dot").forEach(dot => {
        const s = parseInt(dot.dataset.step);
        dot.classList.toggle("active", s === currentStep);
        dot.classList.toggle("done", s < currentStep);
    });

    document.getElementById("btn_prev").style.display = currentStep > 1 ? "block" : "none";
    document.getElementById("btn_next").style.display = currentStep < totalSteps ? "block" : "none";
    document.getElementById("btn_submit").style.display = currentStep === totalSteps ? "block" : "none";
}

// --------------------
// Duration formatting
// --------------------

function formatDuration(totalMinutes) {
    if (!totalMinutes || totalMinutes <= 0) return "—";
    const h = Math.floor(totalMinutes / 60);
    const m = Math.round(totalMinutes % 60);
    if (h === 0) return `${m} min`;
    if (m === 0) return `${h} hr`;
    return `${h} hr ${m} min`;
}

function getEffectiveDistance() {
    const roundTrip = document.getElementById("round_trip").value;
    return roundTrip === "yes" ? oneWayDistance * 2 : oneWayDistance;
}

function updateTravelTime() {
    const mode = document.getElementById("transport_mode").value;
    const distance = getEffectiveDistance();

    const distCard = document.getElementById("distance_card");
    const durCard = document.getElementById("duration_card");
    const distInput = document.getElementById("distance");

    if (!distance || distance <= 0) {
        distCard.textContent = "—";
        durCard.textContent = "—";
        return;
    }

    const displayDist = Math.round(distance * 100) / 100;
    distInput.value = oneWayDistance;
    distCard.textContent = displayDist + " km";
    pulseCard(distCard);

    const avgSpeed = speed[mode] || 60;
    const totalMinutes = (distance / avgSpeed) * 60;
    const formatted = formatDuration(totalMinutes);

    durCard.textContent = formatted;
    document.getElementById("travel_time").value = formatted;
    pulseCard(durCard);
}

function pulseCard(el) {
    el.classList.remove("pulse");
    el.offsetHeight;
    el.classList.add("pulse");
}

function setLoadingState(loading) {
    const durCard = document.getElementById("duration_card");
    const distCard = document.getElementById("distance_card");
    if (loading) {
        durCard.textContent = "Calculating…";
        distCard.textContent = "Calculating…";
        durCard.classList.add("loading");
        distCard.classList.add("loading");
    } else {
        durCard.classList.remove("loading");
        distCard.classList.remove("loading");
    }
}

// --------------------
// Fare hints
// --------------------

function updateBusFareHint() {
    document.getElementById("bus_hint").textContent =
        busHints[document.getElementById("bus_type").value];
}

function updateTrainFareHint() {
    document.getElementById("train_hint").textContent =
        trainHints[document.getElementById("train_type").value];
}

function updateFlightFareHint() {
    document.getElementById("flight_hint").textContent =
        flightHints[document.getElementById("flight_type").value];
}

// --------------------
// Transport mode
// --------------------

function onTransportChange() {
    const mode = document.getElementById("transport_mode").value;

    document.getElementById("vehicle_section").style.display = "none";
    document.getElementById("toll_section").style.display = "none";
    document.getElementById("bus_options").style.display = "none";
    document.getElementById("train_options").style.display = "none";
    document.getElementById("flight_options").style.display = "none";

    if (mode === "bike" || mode === "car") {
        document.getElementById("vehicle_section").style.display = "block";
        document.getElementById("toll_section").style.display = "block";
        document.getElementById("fuel_section").style.display = "block";
        document.getElementById("fuel_type_group").style.display = "block";
        document.getElementById("mileage").value = 20;
    }

    if (mode === "bus") {
        document.getElementById("bus_options").style.display = "block";
        updateBusFareHint();
    }
    if (mode === "train") {
        document.getElementById("train_options").style.display = "block";
        updateTrainFareHint();
    }
    if (mode === "flight") {
        document.getElementById("flight_options").style.display = "block";
        updateFlightFareHint();
    }

    updateTravelTime();
}

function toggleRentalCost() {
    const vehicle = document.getElementById("vehicle_type").value;
    const div = document.getElementById("rental_cost_div");
    if (vehicle === "rental") {
        div.style.display = "block";
    } else {
        div.style.display = "none";
        document.getElementById("vehicle_rental_cost").value = 0;
    }
}

// --------------------
// GPS
// --------------------

function getUserLocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
        function (position) {
            userLat = position.coords.latitude;
            userLon = position.coords.longitude;
            document.getElementById("user_lat").value = userLat;
            document.getElementById("user_lon").value = userLon;
        },
        function () { /* location denied — silent */ }
    );
}

function useCurrentLocation() {
    navigator.geolocation.getCurrentPosition(async function (position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        const response = await fetch(`/reverse_geocode?lat=${lat}&lon=${lon}`);
        const data = await response.json();
        const input = document.getElementById("from_location");
        input.value = data.location;
        input.dispatchEvent(new Event("change"));
        calculateDistance();
    }, function () {
        alert("Please enable location access to use GPS.");
    });
}

// --------------------
// Distance API
// --------------------

async function calculateDistance() {
    const from = document.getElementById("from_location").value;
    const destination = document.getElementById("destination").value;

    if (from === "" || destination === "") return;

    setLoadingState(true);

    try {
        const response = await fetch(
            `/get_distance?from=${encodeURIComponent(from)}&destination=${encodeURIComponent(destination)}`
        );
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            setLoadingState(false);
            document.getElementById("duration_card").textContent = "—";
            document.getElementById("distance_card").textContent = "—";
            return;
        }

        oneWayDistance = data.distance;
        updateTravelTime();
    } catch (err) {
        alert("Could not calculate distance. Check your connection.");
        document.getElementById("duration_card").textContent = "—";
        document.getElementById("distance_card").textContent = "—";
    }
}

document.getElementById("from_location").addEventListener("change", calculateDistance);
document.getElementById("destination").addEventListener("change", calculateDistance);

// --------------------
// Location search
// --------------------

async function searchLocation(inputId, boxId) {
    const query = document.getElementById(inputId).value;
    if (query.length < 2) return;

    const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`
    );
    const data = await response.json();

    let html = "";
    data.forEach(place => {
        const safe = place.display_name.replace(/'/g, "\\'");
        html += `<div class="suggestion-item"
            onclick="selectLocation('${inputId}','${boxId}','${safe}')">
            ${place.display_name}</div>`;
    });

    const box = document.getElementById(boxId);
    box.innerHTML = html;
    box.style.display = html ? "block" : "none";
}

function selectLocation(inputId, boxId, value) {
    document.getElementById(inputId).value = value;
    document.getElementById(boxId).style.display = "none";
    calculateDistance();
}

document.getElementById("from_location").addEventListener("input", () => {
    searchLocation("from_location", "from_suggestions");
});
document.getElementById("destination").addEventListener("input", () => {
    searchLocation("destination", "destination_suggestions");
});

// --------------------
// Page load
// --------------------

window.onload = function () {
    getUserLocation();
    onTransportChange();
    toggleRentalCost();
    updateStepUI();
};
