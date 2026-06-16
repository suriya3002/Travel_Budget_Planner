# 🌍 Travel Budget Planner

A professional Flask-based web application that helps users estimate and manage travel expenses efficiently.

## 🚀 Features

### 💰 Budget Calculation
- Calculate total trip budget
- Calculate cost per traveler
- Fuel cost estimation
- Food expense calculation
- Room cost calculation
- Toll charge calculation
- Parking fee calculation
- Tourist place entry fee calculation

### 🚗 Vehicle Management
- Own Vehicle option
- Rental Vehicle option
- Automatic rental cost visibility
- Mileage-based fuel calculation

### 🗺 Travel Planning
- Destination selection
- One-way and Round-trip calculation
- Distance tracking
- Google Maps route integration
- Live route navigation

### 📊 Reporting
- Professional Trip Summary
- Share Report button
- Download PDF report
- Download Image option
- Travel destination image display

### 🎨 User Interface
- Responsive design
- Mobile-friendly layout
- Modern travel-themed UI
- Professional dashboard

---

## 📂 Project Structure

```text
Travel_Budget_Planner/
│
├── app.py
│
├── static/
│   └── style.css
│
├── templates/
│   ├── index.html
│   └── result.html
│
└── README.md
```

---

## 🛠 Technologies Used

- Python
- Flask
- HTML5
- CSS3
- JavaScript
- Google Maps Integration
- Jinja2 Templates

---

## 📦 Installation

### Clone the Repository

```bash
git clone https://github.com/yourusername/travel-budget-planner.git
```

### Navigate to Project

```bash
cd travel-budget-planner
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

Windows:

```bash
venv\Scripts\activate
```

Linux/Mac:

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install flask
```

---

## ▶ Run the Application

```bash
python app.py
```

Open browser:

```text
http://127.0.0.1:5000
```

---

## 📋 Input Parameters

| Parameter | Description |
|------------|------------|
| Travelers | Number of travelers |
| Destination | Travel destination |
| Distance | Trip distance in km |
| Places to Visit | Number of tourist places |
| Entry Fee | Fee per tourist place |
| Vehicle Type | Own or Rental |
| Vehicle Rental Cost | Rental vehicle charge |
| Parking Fee | Parking charges |
| Mileage | Vehicle mileage |
| Fuel Price | Fuel cost per litre |
| Food Cost | Food expense per person |
| Room Cost | Accommodation cost |
| Toll Charges | Highway toll fees |
| Round Trip | Yes / No |

---

## 🧮 Budget Formula

```text
Total Budget =
Fuel Cost
+ Food Cost
+ Room Cost
+ Toll Charges
+ Parking Fee
+ Entry Fees
+ Vehicle Rental Cost
```

```text
Cost Per Person =
Total Budget / Number of Travelers
```

---

## ✨ Key Features

### Fuel Cost Calculation

```python
fuel_cost = (total_distance / mileage) * fuel_price
```

### Round Trip Support

```python
if round_trip == "yes":
    total_distance = distance * 2
```

### Rental Vehicle Support

```python
if vehicle_type == "rental":
    vehicle_cost = vehicle_rental_cost
else:
    vehicle_cost = 0
```

### Google Maps Route

- Opens route from current location to destination
- Live navigation support
- Real-time travel directions

---

## 📸 Screenshots

### Home Page

- Enter travel details
- Select vehicle type
- Add expenses
- Calculate budget

### Report Page

- Destination image
- Expense breakdown
- Total budget
- Cost per person
- Share report
- Download PDF
- Google Maps route

---

## 🔮 Future Enhancements

- Weather Forecast API
- Expense Pie Chart using Chart.js
- Hotel Recommendation System
- Fuel Station Finder
- SQLite Database Integration
- User Authentication
- Trip History Management
- AI Travel Assistant
- Export to Excel
- Email Report Sharing

---

## 🎯 Learning Outcomes

This project demonstrates:

- Python Programming
- Flask Framework
- HTML Forms
- CSS Styling
- JavaScript Functions
- Web Application Development
- Route Handling
- Budget Calculations
- Dynamic Templates
- Google Maps Integration

---

## 👨‍💻 Author

**Lily**

Python Developer | Flask Learner | Travel Enthusiast

---

## 📄 License

This project is open-source and available for learning and educational purposes.