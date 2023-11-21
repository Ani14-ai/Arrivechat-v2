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
from datetime import datetime
from dateutil import parser
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv

load_dotenv()
secret_key = os.getenv("SECRET_KEY")
app = Flask(__name__)
socketio = SocketIO(app, port=3012, cors_allowed_origins="*")
CORS(app, resources={"/api/*": {"origins": "*"}})


@app.route("/api")
def hello_world():
    return {"message": "Hello, World!"}


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
    expiration_time = checkout_date + timedelta(
        days=1
    )  # Token expires 1 day after checkout
    jwt_token = jwt.encode(
        {"email": email, "exp": expiration_time}, secret_key, algorithm="HS256"
    )
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
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = "QR Code for Authentication"
        html_body = f"""
        <html>
            <body>
                <p>Please scan the QR code below for authentication:</p>
                <img src="cid:qr_code" alt="QR Code">
            </body>
        </html>
        """
        message.attach(MIMEText(html_body, "html"))
        image_attachment = MIMEImage(qr_image.read())
        image_attachment.add_header("Content-ID", "<qr_code>")
        message.attach(image_attachment)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, receiver_email, message.as_string())

        return True
    except Exception as e:
        return False, str(e)


@app.route("/api/auth/send-qr", methods=["GET"])
def send_qr():
    try:
        email = request.json.get("email")
        if not is_email_verified(email):
            return jsonify({"success": False, "error": "Email is not verified"})

        checkout_date = get_checkout_date_from_database(email)

        if checkout_date is None:
            return jsonify(
                {
                    "success": False,
                    "error": "Failed to retrieve checkout date from the database",
                }
            )

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
        img = qr.make_image(fill_color=(153, 76, 0), back_color="white")
        img_stream = io.BytesIO()
        img.save(img_stream)
        img_stream.seek(0)
        success = send_qr_email(email, img_stream)
        room_number = request.json.get("roomno")
        add_room_to_database(email, room_number)

        if success:
            return jsonify({"success": True, "message": "QR code sent successfully"})
        else:
            return jsonify(
                {"success": False, "error": "Failed to send QR code via email"}
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def get_user_info_from_database(email):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"SELECT room_no, language, arrival_date, departure_date FROM customers WHERE email = '{email}'"
        cursor.execute(query)
        result = cursor.fetchone()
        connection.close()

        if result:
            room_number, language, arrival_date, departure_date = result
            return room_number, language, arrival_date, departure_date
        else:
            return None, None, None, None
    except Exception as e:
        return None, None, None, None


@app.route("/api/auth/verify-token", methods=["GET"])
def verify_token():
    try:
        token = request.args.get("token")
        decoded_token = jwt.decode(token, secret_key, algorithms=["HS256"])
        email = decoded_token.get("email")
        if not is_email_verified(email):
            return jsonify({"success": False, "error": "Email is not verified"})
        (
            room_number,
            language,
            arrival_date,
            departure_date,
        ) = get_user_info_from_database(email)
        if arrival_date and departure_date:
            num_days_stayed = (departure_date - arrival_date).days
        else:
            num_days_stayed = None

        response_data = {
            "success": True,
            "message": "Token is valid",
            "decoded_token": decoded_token,
            "room_number": room_number,
            "language": language,
            "num_days_stayed": num_days_stayed,
        }

        return jsonify(response_data)

    except jwt.ExpiredSignatureError:
        return jsonify({"success": False, "error": "Token has expired"})
    except jwt.InvalidTokenError:
        return jsonify({"success": False, "error": "Invalid token"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def update_language_in_database(email, language):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"""
            UPDATE language
            SET language = '{language}'
            email = '{email}' """
        cursor.execute(query)
        connection.commit()
        connection.close()

        return True
    except Exception as e:
        return False, str(e)


@app.route("/api/language", methods=["POST"])
def api_update_language():
    try:
        authorization_header = request.headers.get("Authorization")
        if not authorization_header or not authorization_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "Invalid Authorization header"})

        jwt_token = authorization_header.split(" ")[1]
        decoded_token = jwt.decode(jwt_token, secret_key, algorithms=["HS256"])

        language = request.json.get("language")
        email = decoded_token.get("email")
        success = update_language_in_database(email, language)

        if not success:
            return jsonify(
                {"success": False, "error": "Failed to update language in the database"}
            )

        return jsonify({"success": True, "message": "Language updated successfully"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/customer/add-roomno", methods=["POST"])
def add_room_number():
    try:
        authorization_header = request.headers.get("Authorization")
        if not authorization_header or not authorization_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "Invalid Authorization header"})

        jwt_token = authorization_header.split(" ")[1]
        decoded_token = jwt.decode(jwt_token, secret_key, algorithms=["HS256"])

        room_number = request.json.get("roomno")
        email = decoded_token.get("email")
        success = add_room_to_database(email, room_number)

        if success:
            return jsonify(
                {"success": True, "message": "Room number added successfully"}
            )
        else:
            return jsonify(
                {"success": False, "error": "Failed to add room number to the database"}
            )

    except jwt.ExpiredSignatureError:
        return jsonify({"success": False, "error": "Token has expired"})
    except jwt.InvalidTokenError:
        return jsonify({"success": False, "error": "Invalid token"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def add_customer_to_database(customer_data):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        try:
            arrival_date = parser.parse(customer_data["arrival_date"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            departure_date = parser.parse(customer_data["departure_date"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
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


@app.route("/api/customer", methods=["POST"])
def add_customer():
    try:
        customer_data = request.json
        success = add_customer_to_database(customer_data)
        email = request.json.get("email")
        if not success:
            return jsonify(
                {"success": False, "error": "Failed to add customer to the database"}
            )
        checkout_date = get_checkout_date_from_database(email)
        if checkout_date is None:
            return jsonify(
                {
                    "success": False,
                    "error": "Failed to retrieve checkout date from the database",
                }
            )
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
        img = qr.make_image(fill_color=(153, 76, 0), back_color="white")
        img_stream = io.BytesIO()
        img.save(img_stream)
        img_stream.seek(0)

        # Send QR code via email
        send_qr_email(customer_data["email"], img_stream)

        return jsonify(
            {
                "success": True,
                "message": "Customer added successfully and mail has been sent",
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


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
        token = jwt.encode({"emp_id": employee_id}, secret_key, algorithm="HS256")
        return token
    except Exception as e:
        return None


@app.route("/api/captain/auth/login", methods=["POST"])
def captain_login():
    try:
        employee_id = request.json.get("employee_id")
        password = request.json.get("password")

        if not employee_id or not password:
            return jsonify(
                {"success": False, "error": "Employee ID or password not provided"}
            )

        captain_email_db = get_captain_email_from_database(employee_id, password)

        if not captain_email_db:
            return jsonify({"success": False, "error": "Captain not found"})

        token = generate_captain_token(employee_id)

        if token:
            return jsonify(
                {
                    "success": True,
                    "token": token,
                    "message": "Captain logged in successfully",
                }
            )
        else:
            return jsonify({"success": False, "error": "Failed to generate token"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/get-services-by-room/<int:roomno>", methods=["GET"])
def get_services_by_room(roomno):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"SELECT service FROM services WHERE room = {roomno}"
        cursor.execute(query)

        result = cursor.fetchall()
        connection.close()

        services = [row.service for row in result]

        return jsonify({"success": True, "services": services})

    except Exception as e:
        print(e)
        return jsonify({"success": False, "error": "Internal Server Error"}), 500


responses = {
    "How can I book a room?": "To book a room, you can visit our official website or call our reservation hotline. Our user-friendly online booking system allows you to choose your preferred dates, room type, and any additional amenities you might need.",
    "What types of rooms do you offer?": "We offer a variety of room types to cater to different preferences. Our options include standard rooms, suites, and deluxe rooms. Each is designed to provide comfort and meet the diverse needs of our guests.",
    "What are the room rates?": "Room rates vary based on factors such as room type, view, and the dates of your stay. For the most accurate and up-to-date rates, we recommend checking our website or contacting our reservations team.",
    "Are there any discounts available?": "Yes, we offer various discounts for early bookings, loyalty members, and special promotions. For detailed information on current discounts, please check our website or get in touch with our reservations team.",
    "Can I cancel my reservation?": "Yes, you can cancel your reservation. Our cancellation policy allows for flexibility. You can manage your reservation by logging into your account on our website or by contacting our reservations team directly.",
    "Tell me about your check-in/check-out process.": "Check-in time is at 3:00 PM, and check-out time is at 11:00 AM. If you require early check-in or late check-out, please let us know in advance, and we'll do our best to accommodate your request.",
    "What amenities do the rooms have?": "Our rooms are equipped with modern amenities, including free Wi-Fi, TV, air conditioning, a minibar, and comfortable bedding. Feel free to contact our front desk for specific details or additional requests.",
    "Is breakfast included in the room rate?": "Yes, breakfast is included in the room rate. We offer a complimentary breakfast buffet for our guests, featuring a variety of delicious options to start your day.",
    "Do you have a gym or fitness center?": "Absolutely! We have a fully equipped gym and fitness center available for our guests. Maintain your workout routine during your stay with us.",
    "Are pets allowed in the hotel?": "Yes, we are a pet-friendly hotel. We understand that pets are part of the family, so feel free to inform us in advance if you plan to bring your furry friend along.",
    "How can I reach the hotel from the airport?": "You can reach the hotel from the airport by taking a taxi, using our shuttle service, or using public transportation. For detailed directions and transportation options, please contact us.",
    "What's the Wi-Fi password?": "The Wi-Fi password for our hotel is 'Arrive123'. Enjoy complimentary high-speed internet access during your stay.",
    "Do you offer room service?": "Yes, we offer room service for your convenience. You can find the room service menu in your room, offering a selection of delicious meals and snacks.",
    "Is there parking available?": "Yes, we have parking available for our guests. Please note that there may be a fee depending on the type of parking.",
    "Tell me about nearby attractions.": "Nearby attractions include parks, museums, and shopping centers. Our front desk can provide personalized recommendations based on your interests and preferences.",
    "Are there any restaurants nearby?": "There are several restaurants within walking distance of the hotel, offering a variety of cuisines. Explore the local dining scene for a delightful culinary experience.",
    "Can I request a late check-out?": "Late check-out requests are subject to availability. Please contact our front desk on the day of your departure to inquire about the possibility of a late check-out.",
    "What's your cancellation policy?": "Our cancellation policy varies depending on the type of reservation. For specific details, please refer to your confirmation email or contact our reservations team.",
    "Do you have a pool?": "Yes, we have a swimming pool available for our guests to enjoy. Relax and unwind by taking a refreshing dip in our inviting pool area.",
}


@socketio.on("connect")
def handle_connect():
    print("Client connected")
    socketio.emit(
        "bot_chat",
        {
            "conversation": [
                {"user": "System", "bot": "Welcome! How can I assist you today?"}
            ]
        },
    )


@socketio.on("bot_chat")
def handle_bot_chat(data):
    user_input = data["data"]
    response = responses.get(
        user_input,
        "I'm sorry, I didn't understand your question. Please ask something else.",
    )
    conversation = [{"user": user_input, "bot": response}]
    socketio.emit("bot_chat", {"conversation": conversation})


if __name__ == "__main__":
    socketio.run(app)
