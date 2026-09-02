let oneWayDistance = 0;
let currentStep = 1;
const totalSteps = 3;
let searchTimer;
let activeSearch;
let routeMap;
let directionsService;
let directionsRenderer;
const placeAutocompletes = [];
let oneWayRouteMinutes = 0;

let destinationOptionsCache = null;
const selectedTouristPlaces = new Set();
const selectedFoodMeals = new Set();
let selectedHotelTier = null;

const fareHints = {
    bus_type: { "0.835": "Rate used: ₹0.84/km per person", "1.90": "Rate used: ₹1.90/km per person", "2.00": "Rate used: ₹2.00/km per person", "3.25": "Rate used: ₹3.25/km per person" },
    train_type: { "0.40": "Rate used: ₹0.40/km per person", "0.65": "Rate used: ₹0.65/km per person", "1.80": "Rate used: ₹1.80/km per person", "2.50": "Rate used: ₹2.50/km per person", "3.10": "Rate used: ₹3.10/km per person", "4.00": "Rate used: ₹4.00/km per person" },
    flight_type: { "4.75": "Rate used: ₹4.75/km per person", "7.00": "Rate used: ₹7.00/km per person", "14.00": "Rate used: ₹14.00/km per person", "27.50": "Rate used: ₹27.50/km per person" }
};
const speed = { walk: 5, bike: 80, car: 100, bus: 90, train: 110, flight: 800 };

function getSelectedTripMode() {
    return "before";
}

function updateModeDescription() {
    const description = document.getElementById("mode_description");
    if (!description) return;
    description.textContent = "This will estimate your budget before the trip using planned expenses and destination estimates.";
}

function clearPlannerForm() {
    try {
        localStorage.removeItem("travelBudgetPlannerState");
    } catch (_) {}

    const form = document.getElementById("planner_form");
    if (form) form.reset();

    oneWayDistance = 0;
    oneWayRouteMinutes = 0;
    selectedTouristPlaces.clear();
    selectedFoodMeals.clear();
    selectedHotelTier = null;
    destinationOptionsCache = null;

    const distInput = document.getElementById("distance");
    if (distInput) distInput.value = "";
    const travelTimeInput = document.getElementById("travel_time");
    if (travelTimeInput) travelTimeInput.value = "";

    const distCard = document.getElementById("distance_card");
    if (distCard) distCard.textContent = "—";
    const durCard = document.getElementById("duration_card");
    if (durCard) durCard.textContent = "—";

    const tollHint = document.getElementById("toll_auto_hint");
    if (tollHint) tollHint.style.display = "none";

    ["places_suggestions_section", "food_suggestions_section", "hotels_suggestions_section"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });

    currentStep = 1;
    document.querySelectorAll(".form-step").forEach((step, idx) => {
        step.classList.toggle("active", idx === 0);
    });

    onTransportChange();
    toggleRentalCost();
    updateStepUI();
}

function savePlannerState() {
    const fields = [
        "travelers", "transport_mode", "round_trip", "from_location", "destination",
        "distance", "travel_time", "places_to_visit", "per_places_entry_fee",
        "food_cost_per_person", "room_cost", "trip_days", "vehicle_type",
        "vehicle_rental_cost", "parking_fee", "mileage", "fuel_type",
        "bus_type", "train_type", "flight_type", "toll_charges"
    ];
    const state = {};
    fields.forEach(name => {
        const field = document.querySelector(`[name="${name}"]`);
        if (field) state[name] = field.value;
    });
    state.oneWayDistance = Number(oneWayDistance) || 0;
    state.oneWayRouteMinutes = Number(oneWayRouteMinutes) || 0;
    try {
        localStorage.setItem("travelBudgetPlannerState", JSON.stringify(state));
    } catch (_) {}
}

function loadPlannerState() {
    if (window.location.search.includes("new=1")) {
        clearPlannerForm();
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
    }

    const raw = localStorage.getItem("travelBudgetPlannerState");
    if (!raw) return;
    try {
        const state = JSON.parse(raw);
        Object.entries(state).forEach(([key, value]) => {
            if (key === "oneWayRouteMinutes") {
                oneWayRouteMinutes = Number(value) || 0;
            } else if (key === "oneWayDistance") {
                oneWayDistance = Number(value) || 0;
            } else {
                const field = document.querySelector(`[name="${key}"]`);
                if (field) field.value = value;
            }
        });

        const distanceValue = Number(document.getElementById("distance")?.value) || oneWayDistance || 0;
        if (distanceValue > 0) {
            oneWayDistance = distanceValue;
            const roundTrip = document.getElementById("round_trip")?.value === "yes";
            const displayed = roundTrip ? distanceValue * 2 : distanceValue;
            const rounded = Math.round(displayed * 100) / 100;
            const distCard = document.getElementById("distance_card");
            if (distCard) distCard.textContent = `${rounded} km`;
            const durCard = document.getElementById("duration_card");
            const travelTimeEl = document.getElementById("travel_time");
            const dur = travelTimeEl?.value || formatDuration(oneWayRouteMinutes || (displayed / (speed[document.getElementById("transport_mode")?.value] || 60)) * 60);
            if (durCard) durCard.textContent = dur;
            if (travelTimeEl) travelTimeEl.value = dur;
            updateAutoTolls();
        }

        const destVal = document.getElementById("destination")?.value?.trim();
        if (destVal) {
            fetchDestinationOptions(destVal);
        }
    } catch (error) {
        console.warn("Could not restore saved planner state.", error);
    }
}

function changeStep(direction) {
    const next = currentStep + direction;
    if (next < 1 || next > totalSteps || (direction > 0 && !validateStep(currentStep))) return;
    document.querySelector(`.form-step[data-step="${currentStep}"]`).classList.remove("active");
    currentStep = next;
    document.querySelector(`.form-step[data-step="${currentStep}"]`).classList.add("active");
    updateStepUI();
    if (currentStep === 3) {
        const dest = document.getElementById("destination")?.value?.trim();
        if (dest) fetchDestinationOptions(dest);
        updateAutoTolls();
    }
}

function validateStep(step) {
    const ids = step === 1 ? ["travelers"] : step === 2 ? ["from_location", "destination"] : [];
    for (const id of ids) {
        const field = document.getElementById(id);
        if (!field || !field.value.trim() || (id === "travelers" && Number(field.value) < 1)) {
            field?.focus();
            if (field) shakeField(field);
            return false;
        }
    }
    if (step === 2 && Number(document.getElementById("distance")?.value) <= 0) {
        alert("Please enter valid locations and wait for the route to calculate.");
        return false;
    }
    return true;
}

function shakeField(element) {
    const group = element.closest(".field-group");
    group?.classList.add("shake");
    setTimeout(() => group?.classList.remove("shake"), 500);
}

function updateStepUI() {
    const pb = document.getElementById("progress_bar");
    if (pb) pb.style.width = `${(currentStep / totalSteps) * 100}%`;
    document.querySelectorAll(".step-dot").forEach(dot => {
        const step = Number(dot.dataset.step);
        dot.classList.toggle("active", step === currentStep);
        dot.classList.toggle("done", step < currentStep);
    });
    const prevBtn = document.getElementById("btn_prev");
    if (prevBtn) prevBtn.style.display = currentStep > 1 ? "block" : "none";
    const nextBtn = document.getElementById("btn_next");
    if (nextBtn) nextBtn.style.display = currentStep < totalSteps ? "block" : "none";
    const submitBtn = document.getElementById("btn_submit");
    if (submitBtn) submitBtn.style.display = currentStep === totalSteps ? "block" : "none";
}

function formatDuration(minutes) {
    if (!minutes || minutes <= 0) return "—";
    const hours = Math.floor(minutes / 60), remaining = Math.round(minutes % 60);
    return hours ? `${hours} hr${remaining ? ` ${remaining} min` : ""}` : `${remaining} min`;
}

function updateTravelTime() {
    const rawDistance = Number(document.getElementById("distance")?.value) || oneWayDistance;
    oneWayDistance = rawDistance;
    const roundTrip = document.getElementById("round_trip")?.value === "yes";
    const displayedDistance = roundTrip ? oneWayDistance * 2 : oneWayDistance;
    const distanceCard = document.getElementById("distance_card");
    const durationCard = document.getElementById("duration_card");
    if (displayedDistance <= 0) {
        if (distanceCard) distanceCard.textContent = "—";
        if (durationCard) durationCard.textContent = "—";
        return;
    }
    document.getElementById("distance").value = oneWayDistance;
    if (distanceCard) distanceCard.textContent = `${Math.round(displayedDistance * 100) / 100} km`;
    const durationMinutes = oneWayRouteMinutes
        ? oneWayRouteMinutes * (roundTrip ? 2 : 1)
        : (displayedDistance / (speed[document.getElementById("transport_mode")?.value] || 60)) * 60;
    const duration = formatDuration(durationMinutes);
    if (durationCard) durationCard.textContent = duration;
    const timeInput = document.getElementById("travel_time");
    if (timeInput) timeInput.value = duration;

    updateAutoTolls();
}

function updateAutoTolls() {
    const mode = document.getElementById("transport_mode")?.value;
    const tollInput = document.getElementById("toll_charges");
    const hintEl = document.getElementById("toll_auto_hint");
    if (!tollInput || !hintEl) return;

    if (mode === "car") {
        const dist = Number(document.getElementById("distance")?.value) || oneWayDistance || 0;
        const isRound = document.getElementById("round_trip")?.value === "yes";
        if (dist > 0) {
            let baseToll = 0;
            if (dist <= 100) baseToll = 0;
            else if (dist <= 300) baseToll = 180;
            else if (dist <= 600) baseToll = 420;
            else baseToll = 750;

            const totalToll = isRound ? baseToll * 2 : baseToll;
            tollInput.value = totalToll;
            hintEl.textContent = `⚡ Auto-calculated for Car: ₹${totalToll} (${isRound ? 'Round Trip' : 'One Way'}, ${Math.round(isRound ? dist * 2 : dist)} km)`;
            hintEl.style.display = "block";
        } else {
            hintEl.style.display = "none";
        }
    } else {
        hintEl.style.display = "none";
    }
}

function swapLocations() {
    const fromInput = document.getElementById("from_location");
    const destInput = document.getElementById("destination");
    if (!fromInput || !destInput) return;
    const temp = fromInput.value;
    fromInput.value = destInput.value;
    destInput.value = temp;

    if (fromInput.value.trim() && destInput.value.trim()) {
        calculateDistance();
        fetchDestinationOptions(destInput.value.trim());
        savePlannerState();
    }
}

function setLoadingState(loading) {
    ["distance_card", "duration_card"].forEach(id => {
        const card = document.getElementById(id);
        if (!card) return;
        card.classList.toggle("loading", loading);
        if (loading) card.textContent = "Calculating…";
    });
}

function updateFareHint(selectId, hintId) {
    const selectEl = document.getElementById(selectId);
    const hintEl = document.getElementById(hintId);
    if (selectEl && hintEl && fareHints[selectId]) {
        hintEl.textContent = fareHints[selectId][selectEl.value];
    }
}
function updateBusFareHint() { updateFareHint("bus_type", "bus_hint"); }
function updateTrainFareHint() { updateFareHint("train_type", "train_hint"); }
function updateFlightFareHint() { updateFareHint("flight_type", "flight_hint"); }

function onTransportChange() {
    const mode = document.getElementById("transport_mode")?.value || "car";
    ["vehicle_section", "toll_section", "fuel_section", "fuel_type_group", "bus_options", "train_options", "flight_options"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });
    if (["bike", "car"].includes(mode)) {
        ["vehicle_section", "toll_section", "fuel_section", "fuel_type_group"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = "block";
        });
        const mileageEl = document.getElementById("mileage");
        if (mileageEl && !mileageEl.value) mileageEl.value = 20;
    }
    if (["bus", "train", "flight"].includes(mode)) {
        const optEl = document.getElementById(`${mode}_options`);
        if (optEl) optEl.style.display = "block";
        ({ bus: updateBusFareHint, train: updateTrainFareHint, flight: updateFlightFareHint })[mode]?.();
    }
    updateTravelTime();
    updateAutoTolls();
}

function toggleRentalCost() {
    const rental = document.getElementById("vehicle_type")?.value === "rental";
    const rentalCostDiv = document.getElementById("rental_cost_div");
    if (rentalCostDiv) rentalCostDiv.style.display = rental ? "block" : "none";
    const rentalCostInput = document.getElementById("vehicle_rental_cost");
    if (rentalCostInput && !rental) rentalCostInput.value = 0;
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
    const from = document.getElementById("from_location")?.value?.trim();
    const destination = document.getElementById("destination")?.value?.trim();
    if (!from || !destination) return;
    setLoadingState(true);
    try {
        const response = await fetch(`/get_distance?from=${encodeURIComponent(from)}&destination=${encodeURIComponent(destination)}`);
        const data = await response.json();
        if (!response.ok || data.error) throw new Error(data.error || "Unable to calculate this route.");
        oneWayDistance = Number(data.distance);
        oneWayRouteMinutes = Number(data.duration) * 60;
        updateTravelTime();
        updateAutoTolls();
        savePlannerState();
        drawRoutePreview(from, destination, data);
    } catch (error) {
        oneWayDistance = 0;
        oneWayRouteMinutes = 0;
        document.getElementById("distance").value = "";
        document.getElementById("distance_card").textContent = "—";
        document.getElementById("duration_card").textContent = "—";
        const gmapsRow = document.getElementById("gmaps_external_row");
        if (gmapsRow) gmapsRow.style.display = "none";
        alert(error.message || "Could not calculate distance. Check your connection.");
    } finally { setLoadingState(false); }
}

async function fetchDestinationOptions(destination) {
    if (!destination) return;
    try {
        const response = await fetch(`/destination_options?destination=${encodeURIComponent(destination)}`);
        if (!response.ok) return;
        const data = await response.json();
        destinationOptionsCache = data;

        // 1. Update stay estimate label
        const estimateEl = document.getElementById("stay_estimate");
        if (estimateEl) {
            estimateEl.textContent = `${data.tier}: suggested ₹${data.base_food}/person/day for food and ₹${data.base_room}/day for room. You can choose from suggestions below or edit anytime.`;
        }

        // 2. Render Tourist Places Suggestions
        renderPlacesSuggestions(data.places || [], data.links || {});

        // 3. Render Food Meal Timings Suggestions
        renderFoodMealsSuggestions(data.food_meals || [], data.links || {});

        // 4. Render Hotels Tiers and OYO / MMT Booking Links
        renderHotelTiers(data.hotels || [], data.links || {});

        // Pre-fill initial defaults if fields are empty
        const foodInput = document.getElementById("food_cost_per_person");
        if (foodInput && !foodInput.value) foodInput.value = data.base_food;
        const roomInput = document.getElementById("room_cost");
        if (roomInput && !roomInput.value) roomInput.value = data.base_room;

    } catch (err) {
        console.warn("Could not load destination options:", err);
    }
}

function renderPlacesSuggestions(places, links = {}) {
    const section = document.getElementById("places_suggestions_section");
    const container = document.getElementById("places_chips_container");
    const allMapLink = document.getElementById("all_places_map_link");
    if (!section || !container) return;

    if (!places.length) {
        section.style.display = "none";
        return;
    }

    if (allMapLink && links.all_places_maps) {
        allMapLink.href = links.all_places_maps;
        allMapLink.style.display = "inline-flex";
    }

    container.replaceChildren();
    places.forEach((place, index) => {
        const chip = document.createElement("div");
        chip.className = `place-chip ${selectedTouristPlaces.has(index) ? "selected" : ""}`;
        chip.innerHTML = `
            <div class="place-chip-title">${place.name}</div>
            <div class="place-chip-footer">
                <span class="place-chip-fee">₹${place.entry_fee} entry</span>
                <div style="display:flex; align-items:center; gap:6px;">
                    ${place.rating ? `<span class="place-chip-rating">★ ${place.rating}</span>` : ""}
                    <a href="${place.maps_url}" target="_blank" rel="noopener" class="chip-map-btn" onclick="event.stopPropagation()" title="View on Google Maps">📍 Map</a>
                </div>
            </div>
        `;
        chip.addEventListener("click", () => togglePlaceSelection(index, place, chip));
        container.appendChild(chip);
    });

    section.style.display = "block";
    updatePlacesSummary();
}

function togglePlaceSelection(index, place, chip) {
    if (selectedTouristPlaces.has(index)) {
        selectedTouristPlaces.delete(index);
        chip.classList.remove("selected");
    } else {
        selectedTouristPlaces.add(index);
        chip.classList.add("selected");
    }

    const places = destinationOptionsCache?.places || [];
    const count = selectedTouristPlaces.size;
    let totalFee = 0;
    const selectedList = [];
    selectedTouristPlaces.forEach(idx => {
        if (places[idx]) {
            totalFee += Number(places[idx].entry_fee) || 0;
            selectedList.push(places[idx]);
        }
    });

    const placesInput = document.getElementById("places_to_visit");
    const feeInput = document.getElementById("per_places_entry_fee");
    const hiddenJsonInput = document.getElementById("selected_places_json");

    if (placesInput) placesInput.value = count;
    if (feeInput) feeInput.value = count > 0 ? Math.round((totalFee / count) * 100) / 100 : 0;
    if (hiddenJsonInput) hiddenJsonInput.value = JSON.stringify(selectedList);

    updatePlacesSummary();
    savePlannerState();
}

function updatePlacesSummary() {
    const pill = document.getElementById("places_summary_pill");
    if (!pill) return;
    const count = selectedTouristPlaces.size;
    if (count > 0) {
        const places = destinationOptionsCache?.places || [];
        let totalFee = 0;
        selectedTouristPlaces.forEach(idx => {
            if (places[idx]) totalFee += Number(places[idx].entry_fee) || 0;
        });
        pill.textContent = `✓ Selected ${count} tourist sight${count === 1 ? '' : 's'} · Total Entry: ₹${totalFee} (auto-filled)`;
        pill.style.display = "inline-block";
    } else {
        pill.style.display = "none";
    }
}

function renderFoodMealsSuggestions(meals, links = {}) {
    const section = document.getElementById("food_suggestions_section");
    const container = document.getElementById("food_meals_container");
    const allFoodLink = document.getElementById("all_food_google_link");
    if (!section || !container) return;

    if (!meals.length) {
        section.style.display = "none";
        return;
    }

    if (allFoodLink && links.all_food_google) {
        allFoodLink.href = links.all_food_google;
        allFoodLink.style.display = "inline-flex";
    }

    container.replaceChildren();
    meals.forEach((meal, idx) => {
        const card = document.createElement("div");
        card.className = `meal-card ${selectedFoodMeals.has(idx) ? "selected" : ""}`;
        card.innerHTML = `
            <div class="meal-card-head">
                <span class="meal-card-name">${meal.icon} ${meal.name}</span>
                <span class="meal-card-cost">₹${meal.cost}</span>
            </div>
            <div class="meal-card-time">${meal.time}</div>
            <div class="meal-card-desc">${meal.desc}</div>
            <div class="chip-links-row">
                <a href="${meal.maps_url}" target="_blank" rel="noopener" class="chip-map-btn" onclick="event.stopPropagation()">📍 Restaurants on Map</a>
                <a href="${meal.google_url}" target="_blank" rel="noopener" class="chip-map-btn" onclick="event.stopPropagation()">🔍 Google Search</a>
            </div>
        `;
        card.addEventListener("click", () => toggleMealSelection(idx, meal, card));
        container.appendChild(card);
    });

    section.style.display = "block";
    updateFoodSummary();
}

function toggleMealSelection(idx, meal, card) {
    if (selectedFoodMeals.has(idx)) {
        selectedFoodMeals.delete(idx);
        card.classList.remove("selected");
    } else {
        selectedFoodMeals.add(idx);
        card.classList.add("selected");
    }

    const meals = destinationOptionsCache?.food_meals || [];
    let totalMealCost = 0;
    const selectedList = [];
    selectedFoodMeals.forEach(i => {
        if (meals[i]) {
            totalMealCost += Number(meals[i].cost) || 0;
            selectedList.push(meals[i]);
        }
    });

    const foodInput = document.getElementById("food_cost_per_person");
    const hiddenMealsInput = document.getElementById("selected_meals_json");

    if (foodInput) {
        foodInput.value = totalMealCost > 0 ? totalMealCost : (destinationOptionsCache?.base_food || 600);
    }
    if (hiddenMealsInput) hiddenMealsInput.value = JSON.stringify(selectedList);

    updateFoodSummary();
    savePlannerState();
}

function updateFoodSummary() {
    const pill = document.getElementById("food_summary_pill");
    if (!pill) return;
    const count = selectedFoodMeals.size;
    if (count > 0) {
        const meals = destinationOptionsCache?.food_meals || [];
        let totalMealCost = 0;
        selectedFoodMeals.forEach(i => {
            if (meals[i]) totalMealCost += Number(meals[i].cost) || 0;
        });
        pill.textContent = `✓ Selected ${count} meal${count === 1 ? '' : 's'} · ₹${totalMealCost} / day per person`;
        pill.style.display = "inline-block";
    } else {
        pill.style.display = "none";
    }
}

function renderHotelTiers(hotels, links = {}) {
    const section = document.getElementById("hotels_suggestions_section");
    const container = document.getElementById("hotels_tiers_container");
    const linksBar = document.getElementById("hotels_booking_links");
    const allHotelsMap = document.getElementById("all_hotels_map_link");
    if (!section || !container) return;

    if (!hotels.length) {
        section.style.display = "none";
        return;
    }

    if (allHotelsMap && links.all_hotels_maps) {
        allHotelsMap.href = links.all_hotels_maps;
        allHotelsMap.style.display = "inline-flex";
    }

    container.replaceChildren();
    hotels.forEach((hotel, idx) => {
        const card = document.createElement("div");
        card.className = `hotel-tier-card ${selectedHotelTier === idx ? "selected" : ""}`;
        card.innerHTML = `
            <div class="hotel-tier-head">
                <span class="hotel-tier-name">${hotel.icon} ${hotel.name}</span>
                <span class="hotel-tier-price">₹${hotel.cost}/night</span>
            </div>
            <div class="hotel-tier-desc">${hotel.desc}</div>
            <div class="chip-links-row" style="margin-top:8px;">
                <a href="${hotel.maps_link || links.all_hotels_maps}" target="_blank" rel="noopener" class="chip-map-btn" onclick="event.stopPropagation()">📍 On Google Maps</a>
                <a href="${hotel.google_link || links.google}" target="_blank" rel="noopener" class="chip-map-btn" onclick="event.stopPropagation()">🔍 Google Hotels</a>
            </div>
        `;
        card.addEventListener("click", () => selectHotelTier(idx, hotel));
        container.appendChild(card);
    });

    if (linksBar) {
        linksBar.replaceChildren();
        if (links.oyo) {
            const oyoBtn = document.createElement("a");
            oyoBtn.className = "booking-link-btn oyo";
            oyoBtn.href = links.oyo;
            oyoBtn.target = "_blank";
            oyoBtn.rel = "noopener";
            oyoBtn.innerHTML = "🏨 Search OYO Rooms";
            linksBar.appendChild(oyoBtn);
        }
        if (links.makemytrip) {
            const mmtBtn = document.createElement("a");
            mmtBtn.className = "booking-link-btn mmt";
            mmtBtn.href = links.makemytrip;
            mmtBtn.target = "_blank";
            mmtBtn.rel = "noopener";
            mmtBtn.innerHTML = "✈️ MakeMyTrip Hotels";
            linksBar.appendChild(mmtBtn);
        }
        if (links.google) {
            const gBtn = document.createElement("a");
            gBtn.className = "booking-link-btn google";
            gBtn.href = links.google;
            gBtn.target = "_blank";
            gBtn.rel = "noopener";
            gBtn.innerHTML = "🔍 Google Hotels";
            linksBar.appendChild(gBtn);
        }
        if (links.all_hotels_maps) {
            const gMapsBtn = document.createElement("a");
            gMapsBtn.className = "booking-link-btn";
            gMapsBtn.style.background = "#2563eb";
            gMapsBtn.style.color = "#ffffff";
            gMapsBtn.href = links.all_hotels_maps;
            gMapsBtn.target = "_blank";
            gMapsBtn.rel = "noopener";
            gMapsBtn.innerHTML = "📍 Google Maps Hotels";
            linksBar.appendChild(gMapsBtn);
        }
    }

    section.style.display = "block";
}

function selectHotelTier(idx, hotel) {
    selectedHotelTier = idx;
    document.querySelectorAll(".hotel-tier-card").forEach((c, i) => {
        c.classList.toggle("selected", i === idx);
    });
    const roomInput = document.getElementById("room_cost");
    if (roomInput) {
        roomInput.value = hotel.cost;
    }
    const hiddenHotelInput = document.getElementById("selected_hotel_json");
    if (hiddenHotelInput) {
        hiddenHotelInput.value = JSON.stringify(hotel);
    }
    savePlannerState();
}

let leafletMap = null;
let leafletRouteLayer = null;

function drawRoutePreview(origin, destination, routeData = null) {
    const mapElement = document.getElementById("route_map");
    if (!mapElement) return;

    // Show external Google Maps live route button
    const gmapsRow = document.getElementById("gmaps_external_row");
    const gmapsBtn = document.getElementById("open_in_gmaps_btn");
    if (gmapsRow && gmapsBtn) {
        const gUrl = routeData?.gmaps_url || `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}`;
        gmapsBtn.href = gUrl;
        gmapsRow.style.display = "block";
    }

    // 1. If Google Maps JS API is available, use Google Maps
    if (window.google?.maps?.DirectionsService) {
        if (!routeMap) {
            routeMap = new google.maps.Map(mapElement, {
                center: { lat: 20.5937, lng: 78.9629 },
                zoom: 5,
                mapTypeControl: false,
                streetViewControl: false
            });
            directionsService = new google.maps.DirectionsService();
            directionsRenderer = new google.maps.DirectionsRenderer({
                map: routeMap,
                suppressMarkers: false
            });
        }
        directionsService.route({ origin, destination, travelMode: google.maps.TravelMode.DRIVING }, (result, status) => {
            if (status === "OK") {
                directionsRenderer.setDirections(result);
                mapElement.style.display = "block";
            } else {
                mapElement.style.display = "none";
            }
        });
        return;
    }

    // 2. Otherwise use Leaflet (free OpenStreetMap, zero API key needed!)
    if (typeof L !== "undefined") {
        mapElement.style.display = "block";
        if (!leafletMap) {
            leafletMap = L.map(mapElement, {
                center: [20.5937, 78.9629],
                zoom: 5,
                zoomControl: true
            });
            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                attribution: "© OpenStreetMap contributors",
                maxZoom: 19
            }).addTo(leafletMap);
            leafletRouteLayer = L.featureGroup().addTo(leafletMap);
        }

        leafletRouteLayer.clearLayers();

        const coords = routeData?.route_geometry || [];
        const start = routeData?.start_coords;
        const end = routeData?.end_coords;

        if (coords.length > 0) {
            const polyline = L.polyline(coords, {
                color: "#0284c7",
                weight: 5,
                opacity: 0.85,
                lineJoin: "round"
            }).addTo(leafletRouteLayer);

            // Add start marker (Green)
            const startPoint = coords[0];
            const startMarker = L.circleMarker(startPoint, {
                radius: 8,
                fillColor: "#10b981",
                color: "#ffffff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.95
            }).bindPopup(`<b>Start:</b> ${origin}`);
            leafletRouteLayer.addLayer(startMarker);

            // Add destination marker (Red)
            const endPoint = coords[coords.length - 1];
            const endMarker = L.circleMarker(endPoint, {
                radius: 9,
                fillColor: "#ef4444",
                color: "#ffffff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.95
            }).bindPopup(`<b>Destination:</b> ${destination}`);
            leafletRouteLayer.addLayer(endMarker);

            leafletMap.fitBounds(polyline.getBounds(), { padding: [35, 35] });
            setTimeout(() => leafletMap.invalidateSize(), 200);
        } else if (start && end) {
            const polyline = L.polyline([start, end], {
                color: "#0284c7",
                weight: 4,
                dashArray: "6, 8",
                opacity: 0.8
            }).addTo(leafletRouteLayer);
            leafletMap.fitBounds(polyline.getBounds(), { padding: [35, 35] });
            setTimeout(() => leafletMap.invalidateSize(), 200);
        }
    }
}

async function searchLocation(inputId, boxId) {
    const query = document.getElementById(inputId)?.value?.trim();
    const box = document.getElementById(boxId);
    if (!box) return;
    if (!query || !query.length) {
        box.replaceChildren();
        box.style.display = "none";
        return;
    }
    activeSearch?.abort();
    activeSearch = new AbortController();
    try {
        const response = await fetch(`/location_suggestions?q=${encodeURIComponent(query)}`, { signal: activeSearch.signal });
        const places = await response.json();
        box.replaceChildren();
        places.forEach(place => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "gmap-sugg-row";
            item.innerHTML = `
                <span class="gmap-sugg-pin">📍</span>
                <div class="gmap-sugg-text">
                    <span class="gmap-sugg-main">${place.main_text || place.label}</span>
                    ${place.secondary_text ? `<span class="gmap-sugg-sec">${place.secondary_text}</span>` : ""}
                </div>
            `;
            item.addEventListener("click", () => selectLocation(inputId, boxId, place.label));
            box.appendChild(item);
        });
        box.style.display = places.length ? "block" : "none";
    } catch (error) {
        if (error.name !== "AbortError") box.style.display = "none";
    }
}

function selectLocation(inputId, boxId, value) {
    const input = document.getElementById(inputId);
    if (input) input.value = value;
    const box = document.getElementById(boxId);
    if (box) box.style.display = "none";
    updateClearButtonsVisibility();
    if (inputId === "destination") {
        fetchDestinationOptions(value);
    }
    calculateDistance();
    savePlannerState();
}

function scheduleLocationSearch(inputId, boxId) {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => searchLocation(inputId, boxId), 350);
}

function onLocationInputChange(inputId) {
    updateClearButtonsVisibility();
    if (inputId === "from_location") {
        if (!window.google?.maps?.places) scheduleLocationSearch("from_location", "from_suggestions");
    } else if (inputId === "destination") {
        if (!window.google?.maps?.places) scheduleLocationSearch("destination", "destination_suggestions");
    }
}

function updateClearButtonsVisibility() {
    const fromVal = document.getElementById("from_location")?.value?.trim();
    const destVal = document.getElementById("destination")?.value?.trim();
    const fromClear = document.getElementById("from_clear_btn");
    const destClear = document.getElementById("dest_clear_btn");

    if (fromClear) fromClear.style.display = fromVal ? "inline-flex" : "none";
    if (destClear) destClear.style.display = destVal ? "inline-flex" : "none";
}

function clearLocationInput(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.value = "";
    updateClearButtonsVisibility();

    if (inputId === "from_location") {
        const box = document.getElementById("from_suggestions");
        if (box) box.style.display = "none";
    } else if (inputId === "destination") {
        const box = document.getElementById("destination_suggestions");
        if (box) box.style.display = "none";
    }

    // Reset distance card & travel time if either is cleared
    document.getElementById("distance_card").textContent = "—";
    document.getElementById("duration_card").textContent = "—";
    const distInput = document.getElementById("distance");
    if (distInput) distInput.value = "";
    const durInput = document.getElementById("travel_time");
    if (durInput) durInput.value = "";
    const gmapsRow = document.getElementById("gmaps_external_row");
    if (gmapsRow) gmapsRow.style.display = "none";

    savePlannerState();
}

function selectQuickDestination(destName) {
    const destInput = document.getElementById("destination");
    if (!destInput) return;
    destInput.value = destName;
    updateClearButtonsVisibility();
    const box = document.getElementById("destination_suggestions");
    if (box) box.style.display = "none";
    fetchDestinationOptions(destName);
    calculateDistance();
    savePlannerState();
}

function selectGmapMode(mode) {
    const select = document.getElementById("transport_mode");
    if (select) {
        select.value = mode;
    }
    syncGmapModeTabs();
    onTransportChange();
    savePlannerState();
}

function syncGmapModeTabs() {
    const currentMode = document.getElementById("transport_mode")?.value || "car";
    document.querySelectorAll(".gmap-mode-tab").forEach(tab => {
        tab.classList.toggle("active", tab.getAttribute("data-mode") === currentMode);
    });
}

function swapLocations() {
    const fromInput = document.getElementById("from_location");
    const destInput = document.getElementById("destination");
    const swapBtn = document.getElementById("gmap_swap_btn");

    if (!fromInput || !destInput) return;

    if (swapBtn) {
        swapBtn.classList.add("rotating");
        setTimeout(() => swapBtn.classList.remove("rotating"), 350);
    }

    const temp = fromInput.value;
    fromInput.value = destInput.value;
    destInput.value = temp;

    updateClearButtonsVisibility();

    const newDest = destInput.value.trim();
    if (newDest) {
        fetchDestinationOptions(newDest);
    }

    if (fromInput.value.trim() && newDest) {
        calculateDistance();
    }
    savePlannerState();
}

document.getElementById("from_location")?.addEventListener("change", () => {
    updateClearButtonsVisibility();
    calculateDistance();
    savePlannerState();
});

document.getElementById("destination")?.addEventListener("change", () => {
    updateClearButtonsVisibility();
    const dest = document.getElementById("destination")?.value?.trim();
    if (dest) fetchDestinationOptions(dest);
    calculateDistance();
    savePlannerState();
});

document.getElementById("round_trip")?.addEventListener("change", () => {
    updateTravelTime();
    updateAutoTolls();
    savePlannerState();
});

document.getElementById("transport_mode")?.addEventListener("change", () => {
    syncGmapModeTabs();
    onTransportChange();
    savePlannerState();
});

document.querySelectorAll("#planner_form input, #planner_form select").forEach(input => {
    input.addEventListener("change", savePlannerState);
});

window.onload = () => {
    loadPlannerState();
    updateClearButtonsVisibility();
    syncGmapModeTabs();
    onTransportChange();
    toggleRentalCost();
    updateModeDescription();
    updateStepUI();
};
