import os
import uuid
import datetime
from decimal import Decimal
from flask import Flask, render_template, request, redirect, session, jsonify
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

app = Flask(__name__)

# SECURITY: Use environment variables for secrets
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "generate-a-long-random-string-for-prod")

# ---------------- AWS CONNECTION ----------------
# It is better to rely on EC2 IAM Roles than hardcoded regions if possible
REGION = os.environ.get("AWS_REGION", "ap-south-1")
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)

users_table = dynamodb.Table('travel-Users')
bookings_table = dynamodb.Table('Bookings')

SNS_TOPIC_ARN = "arn:aws:sns:ap-south-1:336449003024:TravelGoNotifications"

# ---------------- LOCAL FALLBACK (DEV) ----------------
local_users = {}
local_bookings = []


def is_credentials_error(error):
    if isinstance(error, (NoCredentialsError, PartialCredentialsError)):
        return True
    return "Unable to locate credentials" in str(error)

# ---------------- STATIC DATA ----------------
bus_data = [
    {"id": "B1", "name": "Super Luxury Bus", "source": "Hyderabad", "dest": "Bangalore", "price": 800},
    {"id": "B2", "name": "Express Bus", "source": "Chennai", "dest": "Hyderabad", "price": 700}
]
train_data = [
    {"id": "T1", "name": "Rajdhani Express", "source": "Hyderabad", "dest": "Delhi", "price": 1500},
    {"id": "T2", "name": "Shatabdi Express", "source": "Chennai", "dest": "Bangalore", "price": 900}
]
flight_data = [
    {"id": "F1", "name": "Indigo 6E203", "source": "Hyderabad", "dest": "Dubai", "price": 8500},
    {"id": "F2", "name": "Air India AI102", "source": "Delhi", "dest": "Singapore", "price": 9500}
]
hotel_data = [
    {"id": "H1", "name": "Grand Palace", "city": "Chennai", "type": "Luxury", "price": 4000},
    {"id": "H2", "name": "Budget Inn", "city": "Hyderabad", "type": "Budget", "price": 1500}
]

# ---------------- HELPER FUNCTIONS ----------------

def get_transport_info(t_id):
    """Identifies the service type and details based on the ID."""
    all_services = [bus_data, train_data, flight_data]
    types = ['Bus', 'Train', 'Flight']
    
    for idx, service_list in enumerate(all_services):
        for item in service_list:
            if item['id'] == t_id:
                return {
                    'type': types[idx],
                    'source': item['source'],
                    'destination': item['dest'],
                    'details': f"{item['name']} ({item['source']} - {item['dest']})"
                }
    
    for h in hotel_data:
        if h['id'] == t_id:
            return {
                'type': 'Hotel',
                'source': h['city'],
                'destination': h['city'],
                'details': f"{h['name']} in {h['city']} ({h['type']})"
            }
            
    return {'type': 'General', 'source': 'Unknown', 'destination': 'Unknown', 'details': 'Transport Details'}

# ---------------- ROUTES ----------------

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_item = {
            'email': request.form['email'],
            'name': request.form['name'],
            'password': request.form['password'],
            'logins': 0
        }
        try:
            users_table.put_item(Item=user_item)
            local_users[user_item['email']] = user_item
            return redirect('/login')
        except Exception as e:
            if is_credentials_error(e):
                local_users[user_item['email']] = user_item
                print("AWS credentials missing. User saved in local memory.")
                return redirect('/login')
            return render_template("register.html", error=f"Registration failed: {e}")
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            response = users_table.get_item(Key={'email': email})
            user = response.get('Item')
        except Exception as e:
            if is_credentials_error(e):
                print("AWS credentials missing. Using local memory for login.")
                user = local_users.get(email)
            else:
                return render_template("login.html", error=str(e))

        if user and user['password'] == password:
            session['user'] = user['email']
            session['name'] = user['name']
            return redirect('/dashboard')
        return render_template("login.html", error="Invalid Credentials")
    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    user_email = session['user']
    
    # IMPROVED: Using Query with GSI instead of Scan
    # Requires a GSI named 'email-index' on the Bookings table
    try:
        response = bookings_table.query(
            IndexName='email-index',
            KeyConditionExpression=Key('email').eq(user_email)
        )
        bookings = response.get('Items', [])
    except Exception as query_error:
        print(f"Query Error: {query_error}. Falling back to scan (Not recommended for prod)")
        try:
            response = bookings_table.scan(FilterExpression=Attr('email').eq(user_email))
            bookings = response.get('Items', [])
        except Exception as scan_error:
            if is_credentials_error(scan_error) or is_credentials_error(query_error):
                print("AWS credentials missing. Loading bookings from local memory.")
                bookings = [b for b in local_bookings if b.get('email') == user_email]
            else:
                print(f"Scan Error: {scan_error}")
                bookings = []

    return render_template("dashboard.html", name=session.get('name', 'User'), bookings=bookings)

@app.route('/bus')
def bus():
    source = request.args.get('source', '').strip().lower()
    destination = request.args.get('destination', '').strip().lower()
    buses = [
        b for b in bus_data
        if (not source or b['source'].lower() == source)
        and (not destination or b['dest'].lower() == destination)
    ]
    return render_template("bus.html", buses=buses, source=source, destination=destination)

@app.route('/train')
def train():
    source = request.args.get('source', '').strip().lower()
    destination = request.args.get('destination', '').strip().lower()
    trains = [
        t for t in train_data
        if (not source or t['source'].lower() == source)
        and (not destination or t['dest'].lower() == destination)
    ]
    return render_template("train.html", trains=trains, source=source, destination=destination)

@app.route('/flight')
def flight():
    source = request.args.get('source', '').strip().lower()
    destination = request.args.get('destination', '').strip().lower()
    flights = [
        f for f in flight_data
        if (not source or f['source'].lower() == source)
        and (not destination or f['dest'].lower() == destination)
    ]
    return render_template("flight.html", flights=flights, source=source, destination=destination)

@app.route('/hotels')
def hotels():
    city = request.args.get('city', '').strip().lower()
    hotels = [h for h in hotel_data if not city or h['city'].lower() == city]
    return render_template("hotels.html", hotels=hotels, city=city)

@app.route('/seat/<transport_id>/<price>')
def seat(transport_id, price):
    if 'user' not in session: return redirect('/login')
    return render_template("seat.html", id=transport_id, price=price)

@app.route('/book', methods=['POST'])
def book():
    if 'user' not in session: return redirect('/login')
    t_id = request.form['transport_id']
    seats = request.form.get('seat')
    price = request.form['price']
    info = get_transport_info(t_id)
    
    session['booking_flow'] = {
        'transport_id': t_id,
        'type': info['type'],
        'source': info['source'],
        'destination': info['destination'],
        'details': info['details'],
        'seat': seats,
        'price': price,
        'date': str(datetime.date.today())
    }
    return render_template("payment.html", booking=session['booking_flow'])

@app.route('/payment', methods=['POST'])
def payment():
    if 'user' not in session or 'booking_flow' not in session:
        return redirect('/dashboard')

    booking_data = session['booking_flow']
    booking_id = str(uuid.uuid4())[:8]
    booking_data['booking_id'] = booking_id
    booking_data['email'] = session['user']
    booking_data['payment_method'] = request.form.get('method')
    booking_data['payment_reference'] = request.form.get('reference')
    booking_data['price'] = Decimal(str(booking_data['price']))

    try:
        bookings_table.put_item(Item=booking_data)
    except Exception as e:
        if is_credentials_error(e):
            print("AWS credentials missing. Saving booking in local memory.")
            local_bookings.append(booking_data.copy())
        else:
            return render_template("payment.html", booking=booking_data, error=f"Payment save failed: {e}")

    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="TravelGo Booking Confirmed",
            Message=f"Booking ID: {booking_id}\nType: {booking_data['type']}\nDetails: {booking_data['details']}\nSeats: {booking_data['seat']}\nTotal Paid: Rs. {booking_data['price']}"
        )
    except Exception as e:
        if is_credentials_error(e):
            print("AWS credentials missing. Skipping SNS notification.")
        else:
            print(f"SNS Error: {e}")

    final_booking = booking_data.copy()
    session.pop('booking_flow', None)
    return render_template("ticket.html", booking=final_booking)

@app.route('/remove_booking', methods=['POST'])
def remove_booking():
    if 'user' not in session:
        return redirect('/login')

    booking_id = request.form['booking_id']

    try:
        bookings_table.delete_item(
            Key={
                'booking_id': booking_id
            }
        )
        print("Booking deleted from DynamoDB")

    except Exception as e:
        if is_credentials_error(e):
            print("AWS credentials missing. Removing booking from local memory.")
            global local_bookings
            local_bookings = [b for b in local_bookings if b.get('booking_id') != booking_id]
        else:
            print("Delete error:", e)

    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    # Running on 0.0.0.0 for EC2 access, but debug is OFF for safety
    app.run(host='0.0.0.0', port=5000, debug=False)
