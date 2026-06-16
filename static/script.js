let userLat = 0;
let userLon = 0;

/* ── Fare hint updaters ─────────────────── */

const busHints = {
  "0.835": "Rate used: ₹0.84/km per person (avg of ₹0.67–1.0)",
  "1.90":  "Rate used: ₹1.90/km per person (avg of ₹1.5–2.3)",
  "2.00":  "Rate used: ₹2.00/km per person (avg of ₹1.5–2.5)",
  "3.25":  "Rate used: ₹3.25/km per person (avg of ₹2.5–4.0)"
};
const trainHints = {
  "0.40":  "Rate used: ₹0.40/km per person (avg of ₹0.30–0.50)",
  "0.65":  "Rate used: ₹0.65/km per person (avg of ₹0.50–0.80)",
  "1.80":  "Rate used: ₹1.80/km per person (avg of ₹1.2–2.4)",
  "2.50":  "Rate used: ₹2.50/km per person (avg of ₹2.0–3.0)",
  "3.10":  "Rate used: ₹3.10/km per person (avg of ₹2.4–3.8)",
  "4.00":  "Rate used: ₹4.00/km per person (avg of ₹3.0–5.0)"
};
const flightHints = {
  "4.75":  "Rate used: ₹4.75/km per person (avg of ₹3.5–6.0)",
  "7.00":  "Rate used: ₹7.00/km per person (avg of ₹5.0–9.0)",
  "14.00": "Rate used: ₹14.00/km per person (avg of ₹8–20+)",
  "27.50": "Rate used: ₹27.50/km per person (avg of ₹15–40)"
};

function updateBusFareHint() {
  const v = document.getElementById("bus_type").value;
  document.getElementById("bus_hint").textContent = busHints[v] || "";
}
function updateTrainFareHint() {
  const v = document.getElementById("train_type").value;
  document.getElementById("train_hint").textContent = trainHints[v] || "";
}
function updateFlightFareHint() {
  const v = document.getElementById("flight_type").value;
  document.getElementById("flight_hint").textContent = flightHints[v] || "";
}

/* ── Toggle sections based on transport mode ── */

function onTransportChange() {

  const mode = document.getElementById("transport_mode").value;

  const vehicleSection  = document.getElementById("vehicle_section");
  const fuelSection     = document.getElementById("fuel_section");
  const tollSection     = document.getElementById("toll_section");
  const busOptions      = document.getElementById("bus_options");
  const trainOptions    = document.getElementById("train_options");
  const flightOptions   = document.getElementById("flight_options");

  // Hide all optional sections first
  vehicleSection.style.display  = "none";
  fuelSection.style.display     = "none";
  tollSection.style.display     = "none";
  busOptions.style.display      = "none";
  trainOptions.style.display    = "none";
  flightOptions.style.display   = "none";

  // Reset mileage so backend doesn't use it
  document.getElementById("mileage").value = 0;
  document.getElementById("toll_charges").value = 0;

  if (mode === "bike" || mode === "car") {
    vehicleSection.style.display = "block";
    fuelSection.style.display    = "block";
    tollSection.style.display    = "block";
    document.getElementById("mileage").value = 20;
  }

  if (mode === "bus") {
    busOptions.style.display = "block";
    updateBusFareHint();
  }

  if (mode === "train") {
    trainOptions.style.display = "block";
    updateTrainFareHint();
  }

  if (mode === "flight") {
    flightOptions.style.display = "block";
    updateFlightFareHint();
  }
}

function toggleRentalCost() {
  const vt = document.getElementById("vehicle_type").value;
  const rd = document.getElementById("rental_cost_div");
  const rc = document.getElementById("vehicle_rental_cost");
  if (vt === "own") {
    rd.style.display = "none";
    rc.value = 0;
  } else {
    rd.style.display = "block";
  }
}

/* ── Geolocation ── */

function getUserLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      function(pos) {
        userLat = pos.coords.latitude;
        userLon = pos.coords.longitude;
        document.getElementById("user_lat").value = userLat;
        document.getElementById("user_lon").value = userLon;
      },
      function() {
        alert("Please allow location access.");
      }
    );
  }
}

/* ── Distance auto-calc ── */

document.getElementById("destination").addEventListener("change", function() {
  const destination = this.value;
  if (!destination) return;

  fetch(`/get_distance?destination=${encodeURIComponent(destination)}&lat=${userLat}&lon=${userLon}`)
    .then(r => r.json())
    .then(data => {

      document.getElementById("distance").value    = data.distance;
      document.getElementById("travel_time").value = data.duration + " Hours";

      // Toll only relevant for car/bike
      const mode = document.getElementById("transport_mode").value;
      if (mode === "car" || mode === "bike") {
        let toll = 0;
        if      (data.distance <= 100) toll = 0;
        else if (data.distance <= 300) toll = 150;
        else if (data.distance <= 600) toll = 400;
        else                           toll = 700;
        document.getElementById("toll_charges").value = toll;
      }
    })
    .catch(err => {
      console.error(err);
      alert("Unable to calculate distance.");
    });
});

/* ── Init ── */

window.onload = function() {
  getUserLocation();
  onTransportChange();   // set correct UI on page load
};
