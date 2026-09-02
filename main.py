import csv
import os

# user inputs for trip details

travelers = int(input("Number of travelers: "))
destination = input("Enter destination: ")
distance = float(input("One-way distance (km): "))

places_to_visit = int(input("Number of places to visit: "))
per_places_entry_fee = float(input("Places entry fee ($): "))
parking_fee = float(input("Parking fee ($): "))
mileage = float(input("Mileage (km/l): "))
fuel_price = float(input("Fuel price ($/l): "))
food_cost_per_person = float(input("Food cost per person ($): "))
Room_cost = float(input("Room cost ($): "))
toll_charges = float(input("Toll charges ($): "))

#room cost (no of days)


#vehicle_own/rental

vehicle_type = input("Vehicle type (rental/own): ").lower()
if vehicle_type == "rental":
    vehicle_rental_cost = float(input("Vehicle rental cost ($): "))
else:
    vehicle_rental_cost = 0

#Round-trip distance and toll calculation

round_trip = input("Round trip? (yes/no): ").lower()

if round_trip == "yes":
    total_distance = distance * 2
    total_toll_charges = toll_charges * 2
else:
    total_distance = distance
    total_toll_charges = toll_charges

#calculation for trip budget with zero-division guards

fuel_cost = (total_distance / mileage * fuel_price) if mileage > 0 else 0.0
total_budget = (fuel_cost
                 + Room_cost
                 + total_toll_charges 
                 + (per_places_entry_fee * places_to_visit)
                 + parking_fee
                 + vehicle_rental_cost
                 + (food_cost_per_person * travelers))
cost_per_person = (total_budget / travelers) if travelers > 0 else total_budget
per_places_entry_fee_total = places_to_visit * per_places_entry_fee


#final output for trip

print("\nTrip Summary")
print("Number of Travelers: ", travelers)
print("Destination:", destination)
print("Total Distance:", total_distance, "km")

print("Number of places to visit:", places_to_visit)
print("Per Places Entry Fee: $", per_places_entry_fee)
print("Total Places Entry Fee: $", per_places_entry_fee_total)
print("Vehicle Type:", vehicle_type)
print("Mileage:", mileage, "km/l")
print("Fuel Cost: $", round(fuel_cost, 2))
print("Food Total Cost: $", round(food_cost_per_person * travelers, 2))
print("Room Cost: $", round(Room_cost, 2))
print("Toll Charges: $", round(total_toll_charges, 2))
print("Parking Fee: $", round(parking_fee, 2))
print("Vehicle Cost: $", round(vehicle_rental_cost, 2))
print("Total Budget: $", round(total_budget, 2))
print("Cost Per Person: $", round(cost_per_person, 2))

# Save trip details to a CSV file (append mode)

file_exists = os.path.isfile('trip_details.csv') and os.path.getsize('trip_details.csv') > 0

with open('trip_details.csv', mode='a', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    
    # Write the header only if the file is new or empty
    if not file_exists:
        writer.writerow(["Travelers", "Destination", "Total Distance (km)", "Places to Visit", "Places Entry Fee ($)", 
                         "Vehicle Type", "Mileage (km/l)", "Fuel Cost ($)", "Food Cost ($)", "Room Cost ($)", "Toll Charges ($)", 
                         "Parking Fee ($)", "Vehicle Cost ($)", "Total Budget ($)", "Cost Per Person ($)"])
        
    # Append the trip details
    writer.writerow([travelers, destination, total_distance, places_to_visit, per_places_entry_fee_total,
                     vehicle_type, mileage, round(fuel_cost, 2), round(food_cost_per_person * travelers, 2), 
                     round(Room_cost, 2), round(total_toll_charges, 2), round(parking_fee, 2), round(vehicle_rental_cost, 2),
                     round(total_budget, 2), round(cost_per_person, 2)])

print("\nTrip details have been saved to 'trip_details.csv'.")