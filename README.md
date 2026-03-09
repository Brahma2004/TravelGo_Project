# ✈️ TravelGo  
### 🌐 A Cloud-Powered Real-Time Travel Booking Platform Using AWS
---
TravelGo is a cloud-based travel booking system built using **Python Flask and AWS services**.
The platform allows users to search and book **buses, trains, flights, and hotels** in real time.

## Technologies Used

* Python (Flask Framework)
* Amazon EC2 – Hosting the application
* Amazon DynamoDB – User and booking database
* Amazon SNS – Booking notifications
* HTML, CSS – Frontend templates
* GitHub – Version control

## Features

* User Registration and Login
* Search for Bus, Train, Flight, and Hotels
* Seat Selection
* Secure Booking and Payment
* Booking Dashboard
* Email Notification using AWS SNS
* Booking History stored in DynamoDB

## Project Architecture

User → Flask Application (EC2) → DynamoDB Database
↓
SNS Notification

## Installation (Local Setup)

Clone the repository:

git clone https://github.com/Brahma2004/TravelGo_Project.git

Move into project folder:

cd TravelGo_Project/TRAVELGO

Install dependencies:

pip install -r requirements.txt

Run the application:

python app.py

Open in browser:

http://localhost:5000

## Team Members

* Brahma K
* Mohammed Saqib
* Joel Mhasraj
* Tejaswini N

## License

This project is for educational purposes.

