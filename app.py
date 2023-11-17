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
secret_key = secrets.token_hex(32)

app = Flask(__name__)
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

        if not success:
            return jsonify({'success': False, 'error': 'Failed to add customer to the database'})
        jwt_token = jwt.encode({'email': customer_data['email']}, secret_key, algorithm='HS256')

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


def generate_captain_token(email):
    try:
        token = jwt.encode({'email': email}, secret_key, algorithm='HS256')
        return token
    except Exception as e:
        return None

def verify_captain_token(token):
    try:
        decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])
        captain_email = decoded_token.get('email')
        captain_email_db = get_captain_email_from_database(captain_email)
        if captain_email_db and captain_email_db == captain_email:
            return True
        else:
            return False
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False
    except Exception as e:
        return False
@app.route('/api/captain/auth/login', methods=['POST'])
def captain_login():
    try:
        email = request.json.get('email')

        if not email:
            return jsonify({'success': False, 'error': 'Email not provided'})
        captain_email_db = get_captain_email_from_database(email)
        if not captain_email_db:
            return jsonify({'success': False, 'error': 'Captain not found'})
        token = generate_captain_token(email)
        
        if (verify_captain_token(token)):
             return jsonify({'success': True, 'token': token,' message': 'Captain logged in successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to generate token'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
if __name__ == '__main__':
    app.run(port=3012)
