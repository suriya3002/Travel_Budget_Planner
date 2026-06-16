let userLat = 0;
let userLon = 0;

function getUserLocation() {

    navigator.geolocation.getCurrentPosition(
        function(position){

            userLat = position.coords.latitude;
            userLon = position.coords.longitude;
        }
    );
}

function toggleTransportFields(){

    let mode =
        document.getElementById(
            "transport_mode"
        ).value;

    document.getElementById(
        "vehicle_section"
    ).style.display =
        (mode === "car" || mode === "bike")
        ? "block"
        : "none";

    document.getElementById(
        "bus_options"
    ).style.display =
        mode === "bus"
        ? "block"
        : "none";

    document.getElementById(
        "train_options"
    ).style.display =
        mode === "train"
        ? "block"
        : "none";

    document.getElementById(
        "flight_options"
    ).style.display =
        mode === "flight"
        ? "block"
        : "none";
}

function calculateDistance(){

    let destination =
        document.getElementById(
            "destination"
        ).value;

    let mode =
        document.getElementById(
            "transport_mode"
        ).value;

    fetch(
        `/get_distance?destination=${destination}&lat=${userLat}&lon=${userLon}&mode=${mode}`
    )

    .then(res => res.json())

    .then(data => {

        document.getElementById(
            "distance"
        ).value = data.distance;

        document.getElementById(
            "travel_time"
        ).value =
            data.duration + " Hours";
    });
}

window.onload = function(){

    getUserLocation();

    toggleTransportFields();
}