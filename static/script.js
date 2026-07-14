let oneWayDistance = 0;
let currentStep = 1;
const totalSteps = 3;
let searchTimer;
let activeSearch;
let routeMap;
let directionsService;
let directionsRenderer;
const placeAutocompletes = [];

const fareHints = {
    bus_type: { "0.835": "Rate used: ₹0.84/km per person", "1.90": "Rate used: ₹1.90/km per person", "2.00": "Rate used: ₹2.00/km per person", "3.25": "Rate used: ₹3.25/km per person" },
    train_type: { "0.40": "Rate used: ₹0.40/km per person", "0.65": "Rate used: ₹0.65/km per person", "1.80": "Rate used: ₹1.80/km per person", "2.50": "Rate used: ₹2.50/km per person", "3.10": "Rate used: ₹3.10/km per person", "4.00": "Rate used: ₹4.00/km per person" },
    flight_type: { "4.75": "Rate used: ₹4.75/km per person", "7.00": "Rate used: ₹7.00/km per person", "14.00": "Rate used: ₹14.00/km per person", "27.50": "Rate used: ₹27.50/km per person" }
};
const speed = { walk: 5, bike: 80, car: 100, bus: 90, train: 110, flight: 800 };

function changeStep(direction) {
    const next = currentStep + direction;
    if (next < 1 || next > totalSteps || (direction > 0 && !validateStep(currentStep))) return;
    document.querySelector(`.form-step[data-step="${currentStep}"]`).classList.remove("active");
    currentStep = next;
    document.querySelector(`.form-step[data-step="${currentStep}"]`).classList.add("active");
    updateStepUI();
}

function validateStep(step) {
    const ids = step === 1 ? ["travelers"] : step === 2 ? ["from_location", "destination"] : [];
    for (const id of ids) {
        const field = document.getElementById(id);
        if (!field.value.trim() || (id === "travelers" && Number(field.value) < 1)) {
            field.focus(); shakeField(field); return false;
        }
    }
    if (step === 2 && Number(document.getElementById("distance").value) <= 0) {
        alert("Select valid locations and wait for the route to calculate."); return false;
    }
    return true;
}

function shakeField(element) {
    const group = element.closest(".field-group");
    group?.classList.add("shake");
    setTimeout(() => group?.classList.remove("shake"), 500);
}

function updateStepUI() {
    document.getElementById("progress_bar").style.width = `${(currentStep / totalSteps) * 100}%`;
    document.querySelectorAll(".step-dot").forEach(dot => {
        const step = Number(dot.dataset.step);
        dot.classList.toggle("active", step === currentStep);
        dot.classList.toggle("done", step < currentStep);
    });
    document.getElementById("btn_prev").style.display = currentStep > 1 ? "block" : "none";
    document.getElementById("btn_next").style.display = currentStep < totalSteps ? "block" : "none";
    document.getElementById("btn_submit").style.display = currentStep === totalSteps ? "block" : "none";
}

function formatDuration(minutes) {
    if (!minutes || minutes <= 0) return "—";
    const hours = Math.floor(minutes / 60), remaining = Math.round(minutes % 60);
    return hours ? `${hours} hr${remaining ? ` ${remaining} min` : ""}` : `${remaining} min`;
}

function updateTravelTime() {
    const distance = document.getElementById("round_trip").value === "yes" ? oneWayDistance * 2 : oneWayDistance;
    const distanceCard = document.getElementById("distance_card");
    const durationCard = document.getElementById("duration_card");
    if (distance <= 0) { distanceCard.textContent = "—"; durationCard.textContent = "—"; return; }
    document.getElementById("distance").value = oneWayDistance;
    distanceCard.textContent = `${Math.round(distance * 100) / 100} km`;
    const duration = formatDuration((distance / (speed[document.getElementById("transport_mode").value] || 60)) * 60);
    durationCard.textContent = duration;
    document.getElementById("travel_time").value = duration;
}

function setLoadingState(loading) {
    ["distance_card", "duration_card"].forEach(id => {
        const card = document.getElementById(id);
        card.classList.toggle("loading", loading);
        if (loading) card.textContent = "Calculating…";
    });
}

function updateFareHint(selectId, hintId) {
    document.getElementById(hintId).textContent = fareHints[selectId][document.getElementById(selectId).value];
}
function updateBusFareHint() { updateFareHint("bus_type", "bus_hint"); }
function updateTrainFareHint() { updateFareHint("train_type", "train_hint"); }
function updateFlightFareHint() { updateFareHint("flight_type", "flight_hint"); }

function onTransportChange() {
    const mode = document.getElementById("transport_mode").value;
    ["vehicle_section", "toll_section", "fuel_section", "fuel_type_group", "bus_options", "train_options", "flight_options"].forEach(id => document.getElementById(id).style.display = "none");
    if (["bike", "car"].includes(mode)) {
        ["vehicle_section", "toll_section", "fuel_section", "fuel_type_group"].forEach(id => document.getElementById(id).style.display = "block");
        document.getElementById("mileage").value ||= 20;
    }
    if (["bus", "train", "flight"].includes(mode)) {
        document.getElementById(`${mode}_options`).style.display = "block";
        ({ bus: updateBusFareHint, train: updateTrainFareHint, flight: updateFlightFareHint })[mode]();
    }
    updateTravelTime();
}

function toggleRentalCost() {
    const rental = document.getElementById("vehicle_type").value === "rental";
    document.getElementById("rental_cost_div").style.display = rental ? "block" : "none";
    if (!rental) document.getElementById("vehicle_rental_cost").value = 0;
}

async function useCurrentLocation() {
    if (!navigator.geolocation) return alert("Your browser does not support location access.");
    navigator.geolocation.getCurrentPosition(async position => {
        try {
            const response = await fetch(`/reverse_geocode?lat=${position.coords.latitude}&lon=${position.coords.longitude}`);
            const data = await response.json();
            if (!response.ok || !data.location) throw new Error(data.error);
            document.getElementById("from_location").value = data.location;
            calculateDistance();
        } catch (error) { alert(error.message || "Could not identify your current location."); }
    }, () => alert("Please enable location access to use GPS."));
}

async function calculateDistance() {
    const from = document.getElementById("from_location").value.trim();
    const destination = document.getElementById("destination").value.trim();
    if (!from || !destination) return;
    setLoadingState(true);
    try {
        const response = await fetch(`/get_distance?from=${encodeURIComponent(from)}&destination=${encodeURIComponent(destination)}`);
        const data = await response.json();
        if (!response.ok || data.error) throw new Error(data.error || "Unable to calculate this route.");
        oneWayDistance = Number(data.distance);
        updateTravelTime();
        drawRoutePreview(from, destination);
    } catch (error) {
        oneWayDistance = 0;
        document.getElementById("distance").value = "";
        document.getElementById("distance_card").textContent = "—";
        document.getElementById("duration_card").textContent = "—";
        alert(error.message || "Could not calculate distance. Check your connection.");
    } finally { setLoadingState(false); }
}

// Called by the optional Maps JavaScript API. The custom suggestion list still
// works when the browser key is not configured.
function initGooglePlaces() {
    if (!window.google?.maps?.places) return;
    ["from_location", "destination"].forEach(id => {
        const input = document.getElementById(id);
        const autocomplete = new google.maps.places.Autocomplete(input, {
            componentRestrictions: { country: "in" },
            fields: ["formatted_address", "name", "geometry"]
        });
        placeAutocompletes.push(autocomplete);
        autocomplete.addListener("place_changed", () => {
            const place = autocomplete.getPlace();
            input.value = place.formatted_address || place.name || input.value;
            document.getElementById(id === "from_location" ? "from_suggestions" : "destination_suggestions").style.display = "none";
            calculateDistance();
        });
    });
    navigator.geolocation?.getCurrentPosition(position => {
        const point = new google.maps.LatLng(position.coords.latitude, position.coords.longitude);
        const bounds = new google.maps.Circle({ center: point, radius: 50000 }).getBounds();
        placeAutocompletes.forEach(autocomplete => autocomplete.setBounds(bounds));
    }, () => {}, { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 });
}

function drawRoutePreview(origin, destination) {
    if (!window.google?.maps?.DirectionsService) return;
    const mapElement = document.getElementById("route_map");
    if (!mapElement) return;
    if (!routeMap) {
        routeMap = new google.maps.Map(mapElement, { center: { lat: 20.5937, lng: 78.9629 }, zoom: 5, mapTypeControl: false, streetViewControl: false });
        directionsService = new google.maps.DirectionsService();
        directionsRenderer = new google.maps.DirectionsRenderer({ map: routeMap, suppressMarkers: false });
    }
    directionsService.route({ origin, destination, travelMode: google.maps.TravelMode.DRIVING }, (result, status) => {
        if (status === "OK") { directionsRenderer.setDirections(result); mapElement.style.display = "block"; }
        else { mapElement.style.display = "none"; }
    });
}

async function searchLocation(inputId, boxId) {
    const query = document.getElementById(inputId).value.trim();
    const box = document.getElementById(boxId);
    if (query.length < 2) { box.replaceChildren(); box.style.display = "none"; return; }
    activeSearch?.abort(); activeSearch = new AbortController();
    try {
        const response = await fetch(`/location_suggestions?q=${encodeURIComponent(query)}`, { signal: activeSearch.signal });
        const places = await response.json();
        box.replaceChildren();
        places.forEach(place => {
            const item = document.createElement("button");
            item.type = "button"; item.className = "suggestion-item"; item.textContent = place.label;
            item.addEventListener("click", () => selectLocation(inputId, boxId, place.label));
            box.appendChild(item);
        });
        box.style.display = places.length ? "block" : "none";
    } catch (error) { if (error.name !== "AbortError") box.style.display = "none"; }
}

function selectLocation(inputId, boxId, value) {
    document.getElementById(inputId).value = value;
    document.getElementById(boxId).style.display = "none";
    calculateDistance();
}
function scheduleLocationSearch(inputId, boxId) { clearTimeout(searchTimer); searchTimer = setTimeout(() => searchLocation(inputId, boxId), 350); }

document.getElementById("from_location").addEventListener("change", calculateDistance);
document.getElementById("destination").addEventListener("change", calculateDistance);
document.getElementById("from_location").addEventListener("input", () => { if (!window.google?.maps?.places) scheduleLocationSearch("from_location", "from_suggestions"); });
document.getElementById("destination").addEventListener("input", () => { if (!window.google?.maps?.places) scheduleLocationSearch("destination", "destination_suggestions"); });
window.onload = () => { onTransportChange(); toggleRentalCost(); updateStepUI(); };
