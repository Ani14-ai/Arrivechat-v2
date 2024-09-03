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
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from translate import Translator
from openai import OpenAI
import pyodbc
import nltk
import langdetect
from langdetect import detect
app = Flask(__name__)
nltk.download('punkt')
nltk.download('stopwords')
from openai import OpenAI
load_dotenv()
secret_key = os.getenv("SECRET_KEY")
client = OpenAI(api_key=os.getenv("Openai_key"))
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



def send_qr_email(customer_data, jwt_token, img_with_link):
    try:
        sender_email = "dev@waysaheadglobal.com"
        smtp_server = "smtp.office365.com"
        smtp_port = 587
        smtp_username = "dev@waysaheadglobal.com"
        smtp_password = "Singapore@2022"
        msg = MIMEMultipart()
        msg['Subject'] = "Arrive Chat QR Code"
        msg['From'] = sender_email
        msg['To'] = customer_data["email"]

        # Attach HTML content to the email
        html_content = f"""
       <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                text-align: center;
                background-color: #f5f5f5;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 400px;
                margin: auto;
                background-color: #ffffff;
                border-radius: 5px;
                overflow: hidden;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                border: 1px solid #ddd;
            }}
            .logo-container {{
                background-color: #8b4513;
                padding: 3px;
                text-align: center;
            }}
            .logo-container img {{
                max-width: 80%;
                height: auto;
                margin-bottom: 20px;
            }}
            .qr-code {{
               display: flex;
               justify-content: center;
               align-items: center;
               flex-direction: column;
               margin-top: 20px;
               margin-right: 1cm;
            }}
            p {{
                margin: 10px 0;
            }}
           
            .assistant-message {{
                font-style: italic;
            }}
            .ps-line {{
                font-style: italic;
                color: #808080; 
                margin-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo-container">
                <img src="https://ae.arrive.waysdatalabs.com/_next/image?url=%2Fimg%2Farrivechat.png&w=256&q=75" alt="Arrive Chat Logo">
            </div>
            <p>Thank You for Booking with us!</p>
            <p>Hello from Arrivechat! I am your AI assistant and I am here to resolve all of your queries. Please scan the QR below or simply tap on it to activate your Arrivechat buddy.</p>
            <div class="qr-code">
                <a href="https://ae.arrive.waysdatalabs.com?token={jwt_token}" target="_blank">                    
                    <img src="cid:qr_code" alt="QR Code">
                </a>
            </div>
            <p>Customer Name: {customer_data["name"]}</p>
            <p>Email: {customer_data["email"]}</p>
            <p>Mobile no.: {customer_data["phone_number"]}</p>
            <p>Hotel name: Aloft Palm Jumeirah</p>
            <p>Hotel Address: East Crescent, The Palm Jumeirah, Dubai United Arab Emirates</p>
            <p class="ps-line">P.S.- This is a system-generated email; please do not reply.</p>
         </div>
        </body>
     </html>"""
    
        msg.attach(MIMEText(html_content, "html"))      
        image_attachment = MIMEImage(img_with_link.read())
        image_attachment.add_header("Content-ID", "<qr_code>")
        msg.attach(image_attachment)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, customer_data["email"], msg.as_string())

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
            UPDATE customers
            SET language = '{language}'
            WHERE email = '{email}' """
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
            return jsonify({"success": False, "error": "Failed to add customer to the database"})

        checkout_date = get_checkout_date_from_database(email)
        if checkout_date is None:
            return jsonify({"success": False, "error": "Failed to retrieve checkout date from the database"})
        jwt_token = generate_jwt_token(email, checkout_date)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,  
            border=4,
        )
        url = f"https://ae.arrive.waysdatalabs.com?token={jwt_token}"
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color=(153, 76, 0), back_color="white")
        img_buffer = io.BytesIO()
        img.save(img_buffer)
        img_buffer.seek(0)
        send_qr_email(customer_data, jwt_token, img_buffer)
        return jsonify({"success": True, "message": "Customer added successfully, and the mail has been sent"})
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

def get_lang(email):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"SELECT  Language FROM customers WHERE email = '{email}'"
        cursor.execute(query)
        result = cursor.fetchone()
        connection.close()

        if result:
            language=result
            return language
        else:
            return None
    except Exception as e:
        return None
        
@app.route('/api/translate', methods=['POST'])
def translate_text():
    try:
        data = request.get_json()
        text_to_translate = data['text']
        src_language = detect(text_to_translate)
        dest_language = data['to']

        translated_text = translate_text_api(text_to_translate, dest_language, src_language)
        response = {"translated_text": translated_text}

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def translate_text_api(text, dest='en', src='auto'):
    if src == 'auto':
        src_language = detect(text)
    else:
        src_language = src

    translator = Translator(to_lang=dest, from_lang=src_language)
    translated_text = translator.translate(text)
    return translated_text
    
@app.route('/api/chat/v1', methods=['POST'])
def chat_v1():
    email = request.json.get('email')
    source_language= 'en'
    dest_language='en'
    def preprocess_text(text):
        tokens = word_tokenize(text.lower())
        stop_words = set(stopwords.words('english'))
        tokens = [word for word in tokens if word.isalnum() and word not in stop_words]
        porter = PorterStemmer()
        tokens = [porter.stem(word) for word in tokens]
        return ' '.join(tokens)

    def query_gpt4_api(question, dest_language='en'):
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            response_format={"type": "text"},
            temperature = 0.7,
            max_tokens=250,
            messages=[
                {"role": "system", "content": "You are a friendly helpful assistant, called arrivechat, for Aloft Palm Jumeirah. Your job is to help tourists by giving them precise and comprehensive answers within 250 tokens. You only answer questions related to a place and majorly Aloft Palm Jumeirah Hotel Of Dubai. Your responses are tailored to be within 250 tokens, ensuring precision, friendliness, and relevance to the guest's queries. You also recommend UNOMIRU a look before you book platform which can show you a 360 degree view of all the rooms and amenities of the hotel, whenever user requests or wants to see any amenities of the hotel. Unomiru's Website is - https://ae.unomiru.com/. Additionally, you are adept at automatically providing links to specific Hotel amenities based on user queries, ensuring a seamless browsing experience for users,Do not create links of your own."},
                {"role": "user", "content": "{If user asks for a wedding event or has a wedding event request}"},
                {"role": "assistant", "content": "Absolutely! You can host a wedding and get a 360 view of our wedding venue at https://www.unomiru.com/uae/hafla-wedding/"},
                {"role": "user", "content": "If they say, show other properties."},
                {"role": "assistant", "content": "Certainly! You can explore our other property, Millenium Place, at https://unomiru.com/uae/milleniumplace/"},
                {"role": "user", "content": "{If they ask to show Indian restaurant.}"},
                {"role": "assistant", "content": "Sure! You can discover our Indian restaurant at https://www.unomiru.com/singapore/unomirufab/yarana/"},
                {"role": "user", "content": "{If they ask about ballroom visit.}"},
                {"role": "assistant", "content": "Explore the elegance of our ballroom at https://www.unomiru.com/uae/hafla-galadinner/"},
                {"role": "user", "content": "{If they ask for fine dining.}"},
                {"role": "assistant", "content": "Experience exceptional fine dining at https://unomiru.com/uae/vogo/"},
                {"role": "user", "content": "{if they ask about yacht facilities}"},
                {"role": "assistant", "content": "Enjoy the luxury of our yacht facilities at https://www.unomiru.com/uae/voeuxyacht/"},
                {"role": "user", "content": "{If user asks for a wedding event or has a wedding event request}"},
                {"role": "assistant", "content": "Unomiru offers exquisite wedding venues that can turn your special day into an unforgettable experience. You can explore our stunning wedding location and get a 360 view at https://www.unomiru.com/uae/hafla-wedding/"},
            
                {"role": "user", "content": "If the user asks to show other properties."},
                {"role": "assistant", "content": "Sure! Unomiru has several luxurious properties that you can explore. Check out Millenium Place at https://unomiru.com/uae/milleniumplace/ for a wonderful stay."},
            
                {"role": "assistant", "content": "Unomiru offers a variety of splendid properties. Visit https://unomiru.com/uae/milleniumplace/ to discover the Millenium Place and all its amenities."},
            
                {"role": "user", "content": "{If they ask to show Indian restaurant.}"},
                {"role": "assistant", "content": "We have an authentic Indian restaurant that you’ll love. Take a look at Yarana at https://www.unomiru.com/singapore/unomirufab/yarana/ for a delightful dining experience."},
            
                {"role": "assistant", "content": "Craving Indian cuisine? Check out our fantastic Indian restaurant Yarana at https://www.unomiru.com/singapore/unomirufab/yarana/ for a memorable meal."},
            
                {"role": "user", "content": "{If the user asks about ballroom visit or anything about a ballroom.}"},
                {"role": "assistant", "content": "Our elegant ballroom is perfect for any event. You can explore it in detail at https://www.unomiru.com/uae/hafla-galadinner/."},
            
                {"role": "user", "content": "{If they ask for fine dining of the hotel or anything related to fine dining.}"},
                {"role": "assistant", "content": "For a top-notch fine dining experience, check out https://unomiru.com/uae/vogo/. Our fine dining restaurant offers exquisite cuisine and a luxurious atmosphere."},
            
                {"role": "user", "content": "{if they ask about yacht facilities or anything about yachts.}"},
                {"role": "assistant", "content": "Experience the ultimate in luxury with our yacht facilities. You can explore it at https://www.unomiru.com/uae/voeuxyacht/."},

                {"role": "user", "content":"is there a swimming pool?"},
                {"role": "assistant", "content": "Aloft Palm Jumeirah is a trendy hotel in Dubai with modern amenities, beach access, and vibrant social spaces. Enjoy a stylish stay with stunning views of the Palm Jumeirah."},
                {"role": "user", "content": "what are the places to visit from there?"},
                {"role": "assistant", "content": "Explore nearby attractions like Atlantis The Palm, Aquaventure Waterpark, and the Dubai Marina. The hotel's location offers easy access to iconic landmarks and entertainment options."},
                {"role": "user", "content": "what are the your helath and safety measures?"},
                {"role": "assistant", "content": "Experience a worry-free stay with our comprehensive health and safety measures, including daily housekeeping, contactless check-in/check-out, and the availability of face masks for guests. Enjoy peace of mind with physical distancing in dining areas, secured guest accommodation disinfected between stays, and the use of effective cleaning chemicals. Our 24-hour security, CCTV coverage, and staff adherence to safety protocols ensure a secure environment. We prioritize your well-being with enhanced cleaning, optional accommodation cleaning, and the provision of thermometers for guest use. Your safety is our commitment!"},
                {"role": "user", "content": "What if there is Fire"},
                {"role": "assistant", "content": "In case of a fire, please click on the SOS icon to connect with our hotel captain for prompt assistance.Additionally, follow the emergency exit signs, use stairwells, and do not use elevators. Our staff is trained to assist and ensure your safety during such situations."},
                {"role": "user", "content": "What if I have an emergency like a heart attack?"},
                {"role": "assistant", "content": "You can directly contact our hotel captain by clicking on the SOS button.You will be provided with all means of medical assistance. "},
                {"role": "user", "content": "I have clicked on the SOS icon"},
                {"role": "assistant", "content": "Our captain has been notified , you will be provided with all means of assitance in no time."},                
                {"role": "user", "content": "What amenities are present in the rooms at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Each room at Aloft Palm Jumeirah is equipped with modern amenities including a flat-screen TV, mini-fridge, coffee maker, and luxurious bedding for a comfortable stay."},                
                {"role": "user", "content": "Is a heater available in the rooms during colder months?"}, 
                {"role": "assistant", "content": "Yes, the rooms at Aloft Palm Jumeirah are equipped with individual climate control, including heaters for colder months, ensuring guests' comfort year-round."},                
                {"role": "user", "content": "Is the swimming pool at Aloft Palm Jumeirah accessible 24/7?"}, 
                {"role": "assistant", "content": "Yes, the outdoor swimming pool at Aloft Palm Jumeirah is accessible to guests 24 hours a day, offering a refreshing escape at any time."},                
                {"role": "user", "content": "Is there an additional charge for using the swimming pool?"}, 
                {"role": "assistant", "content": "No, access to the swimming pool at Aloft Palm Jumeirah is complimentary for all guests staying at the hotel."},                
                {"role": "user", "content": "Do guests need to pay for room service at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Room service at Aloft Palm Jumeirah is available for an additional fee, allowing guests to enjoy delicious meals and snacks in the comfort of their rooms."},                
                {"role": "user", "content": "Where can guests find the WiFi password during their stay?"}, 
                {"role": "assistant", "content": "The WiFi password is provided upon check-in at Aloft Palm Jumeirah. Guests can also inquire about the password at the front desk for seamless connectivity throughout their stay."},                
                {"role": "user", "content": "What are the available dining options for guests at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Aloft Palm Jumeirah offers a diverse range of dining options, including East & Seaboard for international cuisine, Luchador for Mexican delights, W XYZ Bar for refreshing cocktails, and Aloft Aloha Beach for beachside dining experiences."},                
                {"role": "user", "content": "Are there fitness facilities available for guests at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Yes, guests can maintain their fitness routines during their stay at Aloft Palm Jumeirah, as the hotel provides a well-equipped fitness center with modern exercise equipment."},                
                {"role": "user", "content": "Does Aloft Palm Jumeirah offer laundry services for guests?"}, 
                {"role": "assistant", "content": "Yes, Aloft Palm Jumeirah provides laundry services for guests, ensuring their clothes are cleaned and refreshed during their stay for added convenience."},                
                {"role": "user", "content": "Are there business facilities available for corporate travelers at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Yes, Aloft Palm Jumeirah offers business facilities including meeting rooms and a business center, catering to the needs of corporate travelers seeking a productive stay."},                
                {"role": "user", "content": "Does Aloft Palm Jumeirah offer airport shuttle services for guests?"}, 
                {"role": "assistant", "content": "Yes, Aloft Palm Jumeirah provides airport shuttle services for guests, offering convenient transportation to and from Dubai International Airport for a hassle-free arrival and departure experience."},                
                {"role": "user", "content": "Are there any special promotions or packages available for guests at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Yes, Aloft Palm Jumeirah frequently offers special promotions and packages, including discounted rates, complimentary upgrades, and added perks to enhance guests' stay experiences. Guests can inquire about the latest offers when making reservations."},
                {"role": "user", "content": "Are there any fees for using the hotel's spa facilities or booking spa treatments at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Guests may incur fees for accessing the spa facilities or booking spa treatments at Aloft Palm Jumeirah. Prices for spa services vary depending on the treatment and duration. Guests can inquire about spa fees and packages for a relaxing experience."},                
                {"role": "user", "content": "What are the charges for accessing premium Wi-Fi services at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "While basic Wi-Fi may be complimentary, Aloft Palm Jumeirah may offer premium Wi-Fi services at an additional cost for guests seeking higher speeds or enhanced connectivity. Guests can inquire about premium Wi-Fi options and associated charges during their stay."},                
                {"role": "user", "content": "What type of breakfast options are available for guests at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Aloft Palm Jumeirah offers a variety of breakfast options, including continental, buffet-style, and à la carte selections. Guests can choose from a range of delicious dishes to start their day."},                
                {"role": "user", "content": "Does Aloft Palm Jumeirah provide room service, and what are the available hours?"}, 
                {"role": "assistant", "content": "Yes, Aloft Palm Jumeirah offers room service for guests who prefer to dine in the comfort of their rooms. Guests can enjoy a selection of meals and snacks during designated hours, typically from morning until late evening."},                
                {"role": "user", "content": "Are there any restrictions on bringing outside food or beverages into the hotel rooms at Aloft Palm Jumeirah?"}, 
                {"role": "assistant", "content": "Aloft Palm Jumeirah may have policies regarding outside food and beverages brought into the hotel rooms. Guests are advised to check with the hotel staff regarding any restrictions or guidelines before bringing outside items."},                
                {"role": "user", "content": "What recreational facilities does Aloft Palm Jumeirah offer for guests to enjoy during their stay?"}, 
                {"role": "assistant", "content": "Aloft Palm Jumeirah provides various recreational facilities for guests, such as an outdoor swimming pool, fitness center, and access to nearby beaches. Guests can relax and unwind while enjoying these amenities."},                
                {"role": "user", "content": "Does Aloft Palm Jumeirah offer any special amenities or services for guests celebrating special occasions, such as birthdays or anniversaries?"}, 
                {"role": "assistant", "content": "Aloft Palm Jumeirah may offer special amenities or services for guests celebrating special occasions, such as complimentary upgrades, personalized amenities, or special dining arrangements. Guests can inquire about these options when making reservations or during their stay."},
                {"role": "user", "content": question}
            ]
        )
        return translate_text(response.choices[0].message.content, dest=dest_language)

    def translate_text(text, dest=dest_language, src=source_language):
        translator = Translator(to_lang=dest, from_lang=src)
        translated_text = translator.translate(text)
        return translated_text

    def translat_text(text, dest=dest_language,src=source_language):
        translator = Translator(to_lang=dest,from_lang='en')
        translated_text = translator.translate(text)
        return translated_text

    def create_hotel_chatbot():
        hotel_questions = [
        "Heart attack",
        "I have an emergency",
        "There is a fire",
        "SOS",
        "Do you know which hotel are we talking about?",
        "Where is Aloft Palm Jumeirah located, and what sets it apart?",
        "What are the nearby attractions and communities around Aloft Palm Jumeirah?",
        "Describe the rooms at Aloft Palm Jumeirah and their pricing.",
        "What dining options are available at Aloft Palm Jumeirah?",
        "How can one book a room at Aloft Palm Jumeirah?",
        "What is the star rating of Aloft Palm Jumeirah?",
        "Are there other Aloft Hotels in Dubai?",
        "How far is Aloft Palm Jumeirah from Dubai International Airport (DXB)?",
        "What are the check-in and check-out times at Aloft Palm Jumeirah?",
        "Is parking free at Aloft Palm Jumeirah?",
        "Are pets allowed at Aloft Palm Jumeirah?",
        "What is the cancellation policy of Aloft Palm Jumeirah?",
        "How can guests confirm the cancellation policy for their reservation at Aloft Palm Jumeirah?",
        "What makes Aloft Palm Jumeirah a unique lifestyle experience?",
        "Can you elaborate on the design of the rooms at Aloft Palm Jumeirah?",
        "What amenities are available for kids at Aloft Palm Jumeirah?",
        "What does the culinary experience at Aloft Palm Jumeirah include?",
        "Are there additional amenities provided by the hotel?",
        "How can guests contact the hotel for reservations?",
        "What are the nearby attractions to Aloft Palm Jumeirah?",
        "How are room prices at Aloft Palm Jumeirah determined?",
        "Are there specific types of rooms available, and what are their prices?",
        "How can guests book a room at Aloft Palm Jumeirah online?",
        "What is the star rating of Aloft Palm Jumeirah?",
        "Can guests find other Aloft Hotels in Dubai?",
        "How far is Aloft Palm Jumeirah from Dubai International Airport?",
        "What are the check-in and check-out times at Aloft Palm Jumeirah?",
        "Is parking complimentary for guests at Aloft Palm Jumeirah?",
        "Are pets allowed at Aloft Palm Jumeirah?",
        "What is the cancellation policy of Aloft Palm Jumeirah?"
        ]
        hotel_answers = [
      "Please alert the hotel captain by clicking on the SOS icon.",
      "I'm sorry to hear you're in distress. Please click on the SOS icon to connect with our hotel captain for prompt assistance. Your safety is our top priority",
      "In case of a fire, please click on the SOS icon to alert our hotel captain for prompt assistance.Additionally, follow the emergency exit signs, use stairwells,and do not use elevators. Our staff is trained to assist and ensure your safety during such situations.",
      "I'm sorry to hear you're in distress. Please click on the SOS icon to connect with our hotel captain for prompt assistance. Your safety is our top priority.",
      "Ofcourse!, you are talking about Aloft Palm Jumeirah",
      "Aloft Palm Jumeirah is located on Crescent Road, offering a unique lifestyle experience that combines style, comfort, leisure, and fine dining. It is one of the most affordable hotels in Palm Jumeirah.",
      "Nearby attractions include Waldorf Astoria (4 minutes away), Atlantis, The Palm (6 minutes away), Al Sufouh 2 (20 minutes away), Dubai Marina (22 minutes away), Al Barsha Heights (23 minutes away), and Dubai Harbour (23 minutes away).",
      "The rooms are spacious, fully equipped, and beautifully designed, with bright and beach-vibe colors capturing Palm Jumeirah’s essence. Prices vary, such as 1-king bedroom at 250 AED, 2-twin beds at 259 AED, and others. Prices are subject to change based on factors like seasons and add-ons.",
      "Guests can enjoy amazing delicacies at restaurants like East & Seaboard, Luchador, W XYZ Bar, and Aloft Aloha Beach. Reservations can be made by calling +971 4 247 5555.",
      "Guests can book a room by visiting the official website of Aloft Hotels: https://aloft-hotels.marriott.com/ ,entering location, staying dates, selecting a room, and paying online. Alternatively, Booking.com can be used for booking, often offering discounts and deals.",
      "Aloft Palm Jumeirah is rated as a 4-star hotel.",
      "Yes, Aloft Hotels has various branches across Dubai, including locations like Dubai Creek, Al Mina, Me’aisem, Dubai Airport, and Dubai South.",
      "The hotel is on the edge of the city, and it takes approximately 34 minutes by car to reach Aloft Palm Jumeirah from Dubai International Airport.",
      "Check-in is at 3:00 pm, and check-out is at 12:00 pm.",
      "Yes, parking at Aloft Palm Jumeirah is complimentary for guests.",
      "Unfortunately, pets are not allowed at Aloft Palm Jumeirah.",
      "The cancellation policy can vary based on the specifics of the booking, such as rate and stay dates. It is recommended to contact the hotel directly or refer to the terms and conditions in the booking confirmation for the most accurate information.",
      "Guests can confirm the exact cancellation policy by contacting Aloft Palm Jumeirah directly or reviewing the terms and conditions in their booking confirmation for the most up-to-date information on their specific reservation.",
      "Aloft Palm Jumeirah offers a unique lifestyle experience by combining style, comfort, leisure, and fine dining at affordable prices.",
      "The rooms are designed with high ceilings, stylish amenities, and mesmerizing Arabian sea views. They feature bright and beach-vibe colors to capture the essence of Palm Jumeirah.",
      "The hotel provides safe and various spaces for kids to enjoy and have fun.",
      "Guests can enjoy an unforgettable culinary experience at Aloft Palm Jumeirah, featuring gourmet delicacies at restaurants like East & Seaboard, Luchador, W XYZ Bar, and Aloft Aloha Beach.",
      "Yes, the hotel features sustainability initiatives along with amenities such as private beach access, an outdoor pool, meeting rooms, and a gift shop for souvenirs.",
      "Reservations can be made by calling +971 4 247 5555.",
      "Nearby attractions include Waldorf Astoria (4 minutes away), Atlantis, The Palm (6 minutes away), Al Sufouh 2 (20 minutes away), Dubai Marina (22 minutes away), Al Barsha Heights (23 minutes away), and Dubai Harbour (23 minutes away).",
      "Room prices at Aloft Palm Jumeirah are subject to change based on factors such as seasons, add-ons, and more.",
      "Yes, room types include 1-king bedroom (250 AED), 2-twin beds (259 AED), 1-king room with partial sea view (362 AED), 1-king room with sea view (377 AED), and 2-twin beds with sea view (385 AED).",
      "Guests can visit the official website of Aloft Hotel, enter staying dates, select a room, and pay online. Alternatively, Booking.com can be used for booking.",
      "Aloft Palm Jumeirah is rated as a 4-star hotel.",
      "Yes, Aloft Hotels has various branches across Dubai, including locations like Dubai Creek, Al Mina, Me’aisem, Dubai Airport, and Dubai South.",
      "It takes approximately 34 minutes by car to reach Aloft Palm Jumeirah from Dubai International Airport.",
      "Check-in is at 3:00 pm, and check-out is at 12:00 pm.",
      "Yes, parking at Aloft Palm Jumeirah is complimentary for guests.",
      "Unfortunately, pets are not allowed at Aloft Palm Jumeirah.",
      "The cancellation policy can vary based on factors such as rate and stay dates. Guests are recommended to contact the hotel directly or refer to the terms and conditions in the booking confirmation for the most accurate information."
        ]
        question_db = [preprocess_text(question) for question in hotel_questions]
        answer_db = hotel_answers
        def hotel_chatbot(user_input):
            nonlocal question_db, answer_db
            if dest_language.lower() != 'en':
                user_input_translated = translate_text(user_input, dest='en',src=source_language)
            else:
                user_input_translated = user_input

            user_input_processed = preprocess_text(user_input_translated)
            question_db.append(user_input_processed)

            vectorizer = TfidfVectorizer()
            question_vectors = vectorizer.fit_transform(question_db)
            cosine_similarities = cosine_similarity(question_vectors[-1], question_vectors[:-1]).flatten()
            most_similar_index = cosine_similarities.argmax()
            similarity_threshold = 0.8

            if cosine_similarities[most_similar_index] < similarity_threshold:
                response = query_gpt4_api(user_input_translated, dest_language=dest_language)
            else:
                response = answer_db[most_similar_index]

                if "timings" in user_input_processed:
                    response += "\nFor specific timings, please visit our service section and chat with the hotel captain."
            if dest_language.lower() != 'en':
                response = translat_text(response, dest=dest_language, src=source_language)

            return response

        return hotel_chatbot
    hotel_chatbot_model = create_hotel_chatbot()
    data = request.get_json()
    user_input = data['user_input']
    response = hotel_chatbot_model(user_input)

    return jsonify({'response': response})


@app.route('/api/chat', methods=['POST'])
def chat():
    email = request.json.get('email')
    source_language = 'en'
    dest_language = 'en'
    def translate_text_v2(text, dest=dest_language, src=source_language):
        translator = Translator(to_lang=dest, from_lang=src)
        translated_text = translator.translate(text)
        return translated_text

    def translat_text_v2(text, dest=dest_language,src=source_language):
        translator = Translator(to_lang=dest,from_lang='en')
        translated_text = translator.translate(text)
        return translated_text

    def fetch_gpt4_response(question, dest_language='en'):
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            response_format={"type": "text"},
            temperature=0.7,
            max_tokens=250,
            messages=[      
    {"role": "system", "content": "You are a friendly helpful assistant, called arrivechat, for Hotel Palm Jumeirah. Your job is to help tourists by giving them precise and comprehensive answers within 250 tokens. You only answer questions related to a place and majorly Hotel Palm Jumeirah. Your responses are tailored to be within 250 tokens, ensuring precision, friendliness, and relevance to the guest's queries. You also recommend UNOMIRU a look before you book platform which can show you a 360 degree view of all the rooms and amenities of the hotel, whenever user requests or wants to see any amenities of the hotel. Unomiru's Website is - https://ae.unomiru.com/. Additionally, you are adept at automatically providing links to specific Hotel amenities based on user queries, ensuring a seamless browsing experience for users, Do not create links of your own."},
    {"role": "user", "content": "{If user asks for a wedding event or has a wedding event request}"},
    {"role": "assistant", "content": "Absolutely! You can host a wedding and get a 360 view of our wedding venue at https://www.unomiru.com/uae/hafla-wedding/"},
    {"role": "user", "content": "If they say, show other properties."},
    {"role": "assistant", "content": "Certainly! You can explore our other property, Millenium Place, at https://unomiru.com/uae/milleniumplace/"},
    {"role": "user", "content": "{If they ask to show Indian restaurant.}"},
    {"role": "assistant", "content": "Sure! You can discover our Indian restaurant at https://www.unomiru.com/singapore/unomirufab/yarana/ for a delightful dining experience."},
    {"role": "user", "content": "{If they ask about ballroom visit.}"},
    {"role": "assistant", "content": "Explore the elegance of our ballroom at https://www.unomiru.com/uae/hafla-galadinner/."},
    {"role": "user", "content": "{If they ask for fine dining.}"},
    {"role": "assistant", "content": "Experience exceptional fine dining at https://unomiru.com/uae/vogo/. Our fine dining restaurant offers exquisite cuisine and a luxurious atmosphere."},
    {"role": "user", "content": "{if they ask about yacht facilities}"},
    {"role": "assistant", "content": "Enjoy the luxury of our yacht facilities at https://www.unomiru.com/uae/voeuxyacht/."},
    {"role": "user", "content": "is there a swimming pool?"},
    {"role": "assistant", "content": "Hotel Palm Jumeirah is a trendy hotel in Dubai with modern amenities, beach access, and vibrant social spaces. Enjoy a stylish stay with stunning views of the Palm Jumeirah."},
    {"role": "user", "content": "what are the places to visit from there?"},
    {"role": "assistant", "content": "Explore nearby attractions like Atlantis The Palm, Aquaventure Waterpark, and the Dubai Marina. The hotel's location offers easy access to iconic landmarks and entertainment options."},
    {"role": "user", "content": "what are your health and safety measures?"},
    {"role": "assistant", "content": "Experience a worry-free stay with our comprehensive health and safety measures, including daily housekeeping, contactless check-in/check-out, and the availability of face masks for guests. Enjoy peace of mind with physical distancing in dining areas, secured guest accommodation disinfected between stays, and the use of effective cleaning chemicals. Our 24-hour security, CCTV coverage, and staff adherence to safety protocols ensure a secure environment. We prioritize your well-being with enhanced cleaning, optional accommodation cleaning, and the provision of thermometers for guest use. Your safety is our commitment!"},
    {"role": "user", "content": "What if there is a fire?"},
    {"role": "assistant", "content": "In case of a fire, please click on the SOS icon to connect with our hotel captain for prompt assistance. Additionally, follow the emergency exit signs, use stairwells, and do not use elevators. Our staff is trained to assist and ensure your safety during such situations."},
    {"role": "user", "content": "What if I have an emergency like a heart attack?"},
    {"role": "assistant", "content": "You can directly contact our hotel captain by clicking on the SOS button. You will be provided with all means of medical assistance."},
    {"role": "user", "content": "I have clicked on the SOS icon"},
    {"role": "assistant", "content": "Our captain has been notified, and you will be provided with all means of assistance in no time."},
    {"role": "user", "content": "What amenities are present in the rooms at Hotel Palm Jumeirah?"}, 
    {"role": "assistant", "content": "Each room at Hotel Palm Jumeirah is equipped with modern amenities including a flat-screen TV, mini-fridge, coffee maker, and luxurious bedding for a comfortable stay."},                
    {"role": "user", "content": "Is a heater available in the rooms during colder months?"}, 
    {"role": "assistant", "content": "Yes, the rooms at Hotel Palm Jumeirah are equipped with individual climate control, including heaters for colder months, ensuring guests' comfort year-round."},                
    {"role": "user", "content": "Is the swimming pool at Hotel Palm Jumeirah accessible 24/7?"}, 
    {"role": "assistant", "content": "Yes, the outdoor swimming pool at Hotel Palm Jumeirah is accessible to guests 24 hours a day, offering a refreshing escape at any time."},                
    {"role": "user", "content": "Is there an additional charge for using the swimming pool?"}, 
    {"role": "assistant", "content": "No, access to the swimming pool is included in your stay at Hotel Palm Jumeirah with no additional charge."},                
    {"role": "user", "content": "Are there any nearby dining options or restaurants?"}, 
    {"role": "assistant", "content": "Yes, there are several dining options near Hotel Palm Jumeirah, including both local and international cuisine to suit all tastes."},                
    {"role": "user", "content": "What is the best way to get to Hotel Palm Jumeirah from Dubai International Airport?"}, 
    {"role": "assistant", "content": "The best way to get to Hotel Palm Jumeirah from Dubai International Airport is by taxi or private transfer, which takes about 30 minutes. Alternatively, you can use the Dubai Metro and tram services."},
    {"role": "user", "content": "Where can I find parking at Hotel Palm Jumeirah?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah offers on-site parking for guests. You can access the parking area directly from the hotel's entrance."},
    {"role": "user", "content": "What are the check-in and check-out times at Hotel Palm Jumeirah?"}, 
    {"role": "assistant", "content": "Check-in at Hotel Palm Jumeirah is typically from 3:00 PM, and check-out is by 12:00 PM. Please let us know if you require any adjustments to these times."},
    {"role": "user", "content": "Are pets allowed at Hotel Palm Jumeirah?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah has a pet policy that generally does not allow pets. Please contact the hotel directly for any special requests or exceptions."},
    {"role": "user", "content": "Can I request an early check-in or late check-out?"}, 
    {"role": "assistant", "content": "Early check-in and late check-out requests are subject to availability. Please contact the hotel in advance to arrange these requests."},
    {"role": "user", "content": "Is there a spa or wellness center at Hotel Palm Jumeirah?"}, 
    {"role": "assistant", "content": "Yes, Hotel Palm Jumeirah features a spa and wellness center offering a range of treatments and relaxation options for guests."},
    {"role": "user", "content": "Are there any family-friendly amenities at the hotel?"}, 
    {"role": "assistant", "content": "Yes, Hotel Palm Jumeirah provides family-friendly amenities, including a kids' club, children's pool, and family rooms to ensure a comfortable stay for guests with children."},
    {"role": "user", "content": "Does the hotel offer airport shuttle services?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah offers airport shuttle services. Please inquire with the front desk or concierge for more details and to arrange transportation."},
    {"role": "user", "content": "Are there any special packages or promotions available at the hotel?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah frequently offers special packages and promotions. For the latest deals and offers, please check our website or contact our reservations team directly."},
    {"role": "user", "content": "Can I book a room with a view of the Palm Jumeirah?"}, 
    {"role": "assistant", "content": "Yes, you can book a room with a view of the Palm Jumeirah. When making your reservation, please specify your preference for a room with a view, and we will do our best to accommodate your request."},
    {"role": "user", "content": "What is the cancellation policy for bookings at Hotel Palm Jumeirah?"}, 
    {"role": "assistant", "content": "The cancellation policy at Hotel Palm Jumeirah varies depending on the rate and booking conditions. Please review the terms and conditions at the time of booking or contact our reservations team for detailed information."},
    {"role": "user", "content": "Does Hotel Palm Jumeirah offer any business services or meeting facilities?"}, 
    {"role": "assistant", "content": "Yes, Hotel Palm Jumeirah provides business services and meeting facilities, including conference rooms, audio-visual equipment, and high-speed internet. Contact our events team for more details and to arrange your business needs."},
    {"role": "user", "content": "Is there a fitness center at the hotel?"}, 
    {"role": "assistant", "content": "Yes, Hotel Palm Jumeirah features a well-equipped fitness center with modern exercise equipment for guests to stay active during their stay."},
    {"role": "user", "content": "What are the dining options available at the hotel?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah offers a variety of dining options, including several restaurants and bars with diverse cuisine ranging from international to local specialties. For more details, please visit our website or inquire with our concierge."},
    {"role": "user", "content": "Is there a business center at Hotel Palm Jumeirah?"}, 
    {"role": "assistant", "content": "Yes, Hotel Palm Jumeirah has a business center equipped with computers, printers, and other office supplies to assist with any business needs during your stay."},
    {"role": "user", "content": "Are there any nearby attractions or shopping areas?"}, 
    {"role": "assistant", "content": "Yes, Hotel Palm Jumeirah is conveniently located near various attractions and shopping areas, including The Dubai Mall, Mall of the Emirates, and the Dubai Marina. Enjoy a range of shopping, dining, and entertainment options in the vicinity."},
    {"role": "user", "content": "What types of rooms are available at the hotel?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah offers a range of room types, including standard rooms, deluxe rooms, suites, and villas, each designed to provide luxury and comfort. For specific details and availability, please check our website or contact our reservations team."},
    {"role": "user", "content": "Is Wi-Fi available at the hotel?"}, 
    {"role": "assistant", "content": "Yes, Wi-Fi is available throughout Hotel Palm Jumeirah for all guests, providing convenient and high-speed internet access during your stay."},
    {"role": "user", "content": "What languages are spoken by the staff at the hotel?"}, 
    {"role": "assistant", "content": "The staff at Hotel Palm Jumeirah are multilingual and can assist you in several languages, including English, Arabic, and others to ensure a pleasant and smooth experience."},
    {"role": "user", "content": "Can I make special requests for room amenities or preferences?"}, 
    {"role": "assistant", "content": "Yes, you can make special requests for room amenities or preferences when booking or upon arrival. We will do our best to accommodate your needs and ensure a comfortable stay."},
    {"role": "user", "content": "Is there a laundry service available at the hotel?"}, 
    {"role": "assistant", "content": "Yes, Hotel Palm Jumeirah offers laundry and dry cleaning services for your convenience. Please contact the front desk for more information and to arrange your laundry needs."},
    {"role": "user", "content": "Are there any restrictions or rules for using the hotel's facilities?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah has a few guidelines for using its facilities, such as appropriate swimwear in the pool area, and adherence to quiet hours in common spaces. For detailed information on facility usage rules, please refer to our guest handbook or inquire with our staff."},
    {"role": "user", "content": "Does the hotel offer any transportation services for local sightseeing?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah offers transportation services for local sightseeing, including shuttle services and private car arrangements. Contact the concierge for assistance with planning your local excursions."},
    {"role": "user", "content": "What is the hotel’s policy on smoking?"}, 
    {"role": "assistant", "content": "Hotel Palm Jumeirah has a strict non-smoking policy in all indoor areas. Designated smoking areas are available outside the hotel. Please adhere to these guidelines for the comfort and safety of all guests."},
    {"role": "user", "content": question}]
        )
        return translate_text_v2(response.choices[0].message.content, dest=dest_language)          
    data = request.get_json()
    user_input = data['user_input']
    response= fetch_gpt4_response(user_input, dest_language)
    response = translat_text_v2(response, dest=dest_language, src=source_language)
    return jsonify({"response": response})

if __name__ == "__main__":
    socketio.run(app)
