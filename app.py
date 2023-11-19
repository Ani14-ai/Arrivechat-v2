from flask import Flask, jsonify, request
import pyodbc
from flask_cors import CORS
import jwt
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import timedelta
import secrets
from dateutil import parser
from flask_socketio import SocketIO
secret_key = secrets.token_hex(32)

app = Flask(__name__)
socketio = SocketIO(app,port=3012,cors_allowed_origins="*")
CORS(app, resources={"/api/*": {"origins": "*"}})
@app.route('/api')
def hello_world():
    return {'message': 'Hello, World!'}

connection_string = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=103.145.51.250;"
    "Database=ArriveChatAppDB;"
    "UID=ArriveDBUsr;"
    "PWD=Arrive@pas12;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)
db_connection_string = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=103.145.51.250;"
    "Database=ArriveChatAppDB;"
    "UID=ArriveDBUsr;"
    "PWD=Arrive@pas12;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

def is_email_verified(email):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"SELECT email FROM customers WHERE email = '{email}'"
        cursor.execute(query)
        result = cursor.fetchone()
        connection.close()

        return result is not None
    except Exception as e:
        return False

def get_checkout_date_from_database(email):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"SELECT departure_date FROM customers WHERE email = '{email}'"
        cursor.execute(query)
        result = cursor.fetchone()
        connection.close()

        if result:
            return result[0]
        else:
            return None
    except Exception as e:
        return None

def generate_jwt_token(email, checkout_date):
    expiration_time = checkout_date + timedelta(days=1)  # Token expires 1 day after checkout
    jwt_token = jwt.encode({'email': email, 'exp': expiration_time}, secret_key, algorithm='HS256')
    return jwt_token

def add_room_to_database(email, room_number):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"""
            UPDATE customers 
            SET 
                room_no = '{room_number}'
            WHERE 
                email = '{email}' """
        cursor.execute(query)
        connection.commit()
        connection.close()

        return True
    except Exception as e:
        return False, str(e)

def send_qr_email(receiver_email, qr_image):
    try:
        sender_email = "dev@waysaheadglobal.com"
        smtp_server = "smtp.office365.com"
        smtp_port = 587
        smtp_username = "dev@waysaheadglobal.com"
        smtp_password = "Singapore@2022"
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = receiver_email
        message['Subject'] = 'QR Code for Authentication'
        html_body = f"""
        <html>
            <body>
                <p>Please scan the QR code below for authentication:</p>
                <img src="cid:qr_code" alt="QR Code">
            </body>
        </html>
        """
        message.attach(MIMEText(html_body, 'html'))
        image_attachment = MIMEImage(qr_image.read())
        image_attachment.add_header('Content-ID', '<qr_code>')
        message.attach(image_attachment)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, receiver_email, message.as_string())

        return True
    except Exception as e:
        return False, str(e)

@app.route('/api/auth/send-qr', methods=['GET'])
def send_qr():
    try:
        email = request.json.get('email')
        if not is_email_verified(email):
            return jsonify({'success': False, 'error': 'Email is not verified'})

        checkout_date = get_checkout_date_from_database(email)

        if checkout_date is None:
            return jsonify({'success': False, 'error': 'Failed to retrieve checkout date from the database'})

        jwt_token = generate_jwt_token(email, checkout_date)
        url = f"https://ae.arrive.waysdatalabs.com?token={jwt_token}"

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color=(153, 76, 0), back_color='white')
        img_stream = io.BytesIO()
        img.save(img_stream)
        img_stream.seek(0)
        success = send_qr_email(email, img_stream)
        room_number = request.json.get('roomno')
        add_room_to_database(email, room_number)

        if success:
            return jsonify({'success': True, 'message': 'QR code sent successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send QR code via email'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/auth/verify-token', methods=['GET'])
def verify_token():
    try:
        token = request.args.get('token')
        decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])
        email = decoded_token.get('email')
        if is_email_verified(email):
            return jsonify({'success': True, 'message': 'Token is valid', 'decoded_token': decoded_token})
        else:
            return jsonify({'success': False, 'error': 'Email is not verified'})

    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'error': 'Token has expired'})
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'error': 'Invalid token'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/customer/add-roomno', methods=['POST'])
def add_room_number():
    try:
        authorization_header = request.headers.get('Authorization')
        if not authorization_header or not authorization_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Invalid Authorization header'})

        jwt_token = authorization_header.split(' ')[1]
        decoded_token = jwt.decode(jwt_token, secret_key, algorithms=['HS256'])

        room_number = request.json.get('roomno')
        email = decoded_token.get('email')
        success = add_room_to_database(email, room_number)

        if success:
            return jsonify({'success': True, 'message': 'Room number added successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to add room number to the database'})

    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'error': 'Token has expired'})
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'error': 'Invalid token'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
def add_customer_to_database(customer_data):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        try:
            arrival_date = parser.parse(customer_data['arrival_date']).strftime('%Y-%m-%d %H:%M:%S')
            departure_date = parser.parse(customer_data['departure_date']).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            raise ValueError(f"Error parsing date strings: {e}")
        query = f"""
            INSERT INTO customers (
                name, email, phone_number, unique_id, arrival_date, departure_date) VALUES (
                '{customer_data['name']}', '{customer_data['email']}', {customer_data['phone_number']},
                '{customer_data['unique_id']}', '{arrival_date}', '{departure_date}')"""
        cursor.execute(query)
        connection.commit()
        connection.close()
        return True
    except Exception as e:
        return False, str(e)
@app.route('/api/customer', methods=['POST'])
def add_customer():
    try:
        customer_data = request.json
        success = add_customer_to_database(customer_data)
        email=request.json.get('email')
        if not success:
            return jsonify({'success': False, 'error': 'Failed to add customer to the database'})
        checkout_date = get_checkout_date_from_database(email)
        if checkout_date is None:
            return jsonify({'success': False, 'error': 'Failed to retrieve checkout date from the database'})
        jwt_token = generate_jwt_token(email, checkout_date)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        url = f"https://ae.arrive.waysdatalabs.com?token={jwt_token}"
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color=(153, 76, 0), back_color='white')
        img_stream = io.BytesIO()
        img.save(img_stream)
        img_stream.seek(0)

        # Send QR code via email
        send_qr_email(customer_data['email'], img_stream)

        return jsonify({'success': True, 'message': 'Customer added successfully and mail has been sent'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
def get_captain_email_from_database(employee_id, password):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"SELECT email FROM Captain WHERE employee_id = '{employee_id}' AND password = '{password}'"
        cursor.execute(query)
        result = cursor.fetchone()
        connection.close()

        return result[0] if result else None
    except Exception as e:
        return None

def generate_captain_token(employee_id):
    try:
        token = jwt.encode({'emp_id': employee_id}, secret_key, algorithm='HS256')
        return token
    except Exception as e:
        return None

@app.route('/api/captain/auth/login', methods=['POST'])
def captain_login():
    try:
        employee_id = request.json.get('employee_id')
        password = request.json.get('password')

        if not employee_id or not password:
            return jsonify({'success': False, 'error': 'Employee ID or password not provided'})

        captain_email_db = get_captain_email_from_database(employee_id, password)

        if not captain_email_db:
            return jsonify({'success': False, 'error': 'Captain not found'})

        token = generate_captain_token(employee_id)

        if token:
             return jsonify({'success': True, 'token': token, 'message': 'Captain logged in successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to generate token'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@socketio.on('bot_chat')
def handle_bot_chat(data):
   conversation_pairs = [
    {"user": "How can I book a room?", "bot": "To book a room, you can visit our official website or call our reservation hotline. Our user-friendly online booking system allows you to choose your preferred dates, room type, and any additional amenities you might need."},
    {"user": "What types of rooms do you offer?", "bot": "We offer a variety of room types to cater to different preferences. Our options include standard rooms, suites, and deluxe rooms. Each is designed to provide comfort and meet the diverse needs of our guests."},
    {"user": "What are the room rates?", "bot": "Room rates vary based on factors such as room type, view, and the dates of your stay. For the most accurate and up-to-date rates, we recommend checking our website or contacting our reservations team."},
    {"user": "Are there any discounts available?", "bot": "Yes, we offer various discounts for early bookings, loyalty members, and special promotions. For detailed information on current discounts, please check our website or get in touch with our reservations team."},
    {"user": "Can I cancel my reservation?", "bot": "Yes, you can cancel your reservation. Our cancellation policy allows for flexibility. You can manage your reservation by logging into your account on our website or by contacting our reservations team directly."},
    {"user": "Tell me about your check-in/check-out process.", "bot": "Check-in time is at 3:00 PM, and check-out time is at 11:00 AM. If you require early check-in or late check-out, please let us know in advance, and we'll do our best to accommodate your request."},
    {"user": "What amenities do the rooms have?", "bot": "Our rooms are equipped with modern amenities, including free Wi-Fi, TV, air conditioning, a minibar, and comfortable bedding. Feel free to contact our front desk for specific details or additional requests."},
    {"user": "Is breakfast included in the room rate?", "bot": "Yes, breakfast is included in the room rate. We offer a complimentary breakfast buffet for our guests, featuring a variety of delicious options to start your day."},
    {"user": "Do you have a gym or fitness center?", "bot": "Absolutely! We have a fully equipped gym and fitness center available for our guests. Maintain your workout routine during your stay with us."},
    {"user": "Are pets allowed in the hotel?", "bot": "Yes, we are a pet-friendly hotel. We understand that pets are part of the family, so feel free to inform us in advance if you plan to bring your furry friend along."},
    {"user": "How can I reach the hotel from the airport?", "bot": "You can reach the hotel from the airport by taking a taxi, using our shuttle service, or using public transportation. For detailed directions and transportation options, please contact us."},
    {"user": "What's the Wi-Fi password?", "bot": "The Wi-Fi password for our hotel is 'Arrive123'. Enjoy complimentary high-speed internet access during your stay."},
    {"user": "Do you offer room service?", "bot": "Yes, we offer room service for your convenience. You can find the room service menu in your room, offering a selection of delicious meals and snacks."},
    {"user": "Is there parking available?", "bot": "Yes, we have parking available for our guests. Please note that there may be a fee depending on the type of parking."},
    {"user": "Tell me about nearby attractions.", "bot": "Nearby attractions include parks, museums, and shopping centers. Our front desk can provide personalized recommendations based on your interests and preferences."},
    {"user": "Are there any restaurants nearby?", "bot": "There are several restaurants within walking distance of the hotel, offering a variety of cuisines. Explore the local dining scene for a delightful culinary experience."},
    {"user": "Can I request a late check-out?", "bot": "Late check-out requests are subject to availability. Please contact our front desk on the day of your departure to inquire about the possibility of a late check-out."},
    {"user": "What's your cancellation policy?", "bot": "Our cancellation policy varies depending on the type of reservation. For specific details, please refer to your confirmation email or contact our reservations team."},
    {"user": "Do you have a pool?", "bot": "Yes, we have a swimming pool available for our guests to enjoy. Relax and unwind by taking a refreshing dip in our inviting pool area."}
]
   conversation = []
   for pair in conversation_pairs:
        socketio.sleep(1)
        conversation.append(pair)
        socketio.emit('bot_chat', {'conversation': conversation})
if __name__ == '__main__':
    socketio.run(app, debug=False)
