// ===============================
// Travel Budget Planner Script
// ===============================

let userLat = 0;
let userLon = 0;

// --------------------
// Fare Hint Data
// --------------------

const busHints = {
    "0.835":"Rate used: ₹0.84/km per person",
    "1.90":"Rate used: ₹1.90/km per person",
    "2.00":"Rate used: ₹2.00/km per person",
    "3.25":"Rate used: ₹3.25/km per person"
};

const trainHints = {
    "0.40":"Rate used: ₹0.40/km per person",
    "0.65":"Rate used: ₹0.65/km per person",
    "1.80":"Rate used: ₹1.80/km per person",
    "2.50":"Rate used: ₹2.50/km per person",
    "3.10":"Rate used: ₹3.10/km per person",
    "4.00":"Rate used: ₹4.00/km per person"
};

const flightHints = {
    "4.75":"Rate used: ₹4.75/km per person",
    "7.00":"Rate used: ₹7.00/km per person",
    "14.00":"Rate used: ₹14.00/km per person",
    "27.50":"Rate used: ₹27.50/km per person"
};

// --------------------
// Fare Hint Functions
// --------------------

function updateBusFareHint(){
    document.getElementById("bus_hint").textContent =
        busHints[document.getElementById("bus_type").value];
}

function updateTrainFareHint(){
    document.getElementById("train_hint").textContent =
        trainHints[document.getElementById("train_type").value];
}

function updateFlightFareHint(){
    document.getElementById("flight_hint").textContent =
        flightHints[document.getElementById("flight_type").value];
}

// --------------------
// Transport Mode
// --------------------

function onTransportChange(){

    const mode=document.getElementById("transport_mode").value;

    document.getElementById("vehicle_section").style.display="none";
    document.getElementById("fuel_section").style.display="none";
    document.getElementById("toll_section").style.display="none";

    document.getElementById("bus_options").style.display="none";
    document.getElementById("train_options").style.display="none";
    document.getElementById("flight_options").style.display="none";

    if(mode==="bike" || mode==="car"){

        document.getElementById("vehicle_section").style.display="block";
        document.getElementById("fuel_section").style.display="block";
        document.getElementById("toll_section").style.display="block";

        document.getElementById("mileage").value=20;
    }

    if(mode==="bus"){

        document.getElementById("bus_options").style.display="block";
        updateBusFareHint();

    }

    if(mode==="train"){

        document.getElementById("train_options").style.display="block";
        updateTrainFareHint();

    }

    if(mode==="flight"){

        document.getElementById("flight_options").style.display="block";
        updateFlightFareHint();

    }

}

const speed = {

walk:5,
bike:45,
car:70,
bus:50,
train:80,
flight:700

};

function updateTravelTime(){

const mode=document.getElementById("transport_mode").value;

const distance=parseFloat(
document.getElementById("distance").value
);

if(isNaN(distance)) return;

const hours=distance/speed[mode];

const h=Math.floor(hours);

const m=Math.round((hours-h)*60);

document.getElementById("travel_time").value=

`${h} hr ${m} min`;

document.getElementById("duration_card").innerHTML=

`${h} hr ${m} min`;

}

// --------------------
// Rental Vehicle
// --------------------

function toggleRentalCost(){

    const vehicle=document.getElementById("vehicle_type").value;

    if(vehicle==="rental"){

        document.getElementById("rental_cost_div").style.display="block";

    }
    else{

        document.getElementById("rental_cost_div").style.display="none";
        document.getElementById("vehicle_rental_cost").value=0;

    }

}

// --------------------
// Current GPS
// --------------------

function getUserLocation(){

    if(!navigator.geolocation){

        alert("Geolocation not supported.");

        return;

    }

    navigator.geolocation.getCurrentPosition(

        function(position){

            userLat=position.coords.latitude;
            userLon=position.coords.longitude;

            document.getElementById("user_lat").value=userLat;
            document.getElementById("user_lon").value=userLon;

            console.log(userLat,userLon);

        },

        function(){

            alert("Please enable Location.");

        }

    );

}

// --------------------
// Use Current Location
// --------------------
function useCurrentLocation(){

navigator.geolocation.getCurrentPosition(async function(position){

const lat=position.coords.latitude;
const lon=position.coords.longitude;

const response=await fetch(
`/reverse_geocode?lat=${lat}&lon=${lon}`
);

const data=await response.json();

document.getElementById("from_location").value=data.location;

});

}


async function calculateDistance() {

    const from = document.getElementById("from_location").value;
    const destination = document.getElementById("destination").value;

    if (from === "" || destination === "")
        return;

    const response = await fetch(
        `/get_distance?from=${encodeURIComponent(from)}&destination=${encodeURIComponent(destination)}`
    );

    const data = await response.json();

    if (data.error) {
        alert(data.error);
        return;
    }

   document.getElementById("distance").value=data.distance;

document.getElementById("distance_card").innerHTML=

data.distance+" km";

updateTravelTime();
    document.getElementById("travel_time").value = data.duration + " Hours";
    document.getElementById("distance_card").textContent = data.distance + " km";
    document.getElementById("duration_card").textContent = data.duration + " hr";
}

document.getElementById("from_location").addEventListener("change", calculateDistance);
document.getElementById("destination").addEventListener("change", calculateDistance);

async function searchLocation(inputId, boxId){

const query=document.getElementById(inputId).value;

if(query.length<2) return;

const response=await fetch(

`https://nominatim.openstreetmap.org/search?format=json&q=${query}`

);

const data=await response.json();

let html="";

data.forEach(place=>{

html+=`

<div class="suggestion-item"

onclick="selectLocation('${inputId}','${boxId}','${place.display_name.replace(/'/g,"\\'")}')">

${place.display_name}

</div>

`;

});

const box=document.getElementById(boxId);

box.innerHTML=html;

box.style.display="block";

}

function selectLocation(inputId,boxId,value){

document.getElementById(inputId).value=value;

document.getElementById(boxId).style.display="none";

calculateDistance();

}

document.getElementById("from_location")
.addEventListener("input",()=>{

searchLocation("from_location","from_suggestions");

});

document.getElementById("destination")
.addEventListener("input",()=>{

searchLocation("destination","destination_suggestions");

});
// --------------------
// Page Load
// --------------------

window.onload=function(){

    getUserLocation();

    onTransportChange();

    toggleRentalCost();

};