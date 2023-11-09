from flask import Flask, jsonify, request
import pyodbc
from flask_cors import CORS
import jwt
import qrcode
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import secrets
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
@app.route('/api/customers', methods=['GET'])
def get_customers():
    try:
        connection = pyodbc.connect(connection_string)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM customer")
        columns = [column[0] for column in cursor.description]
        customers = []
        for row in cursor.fetchall():
            customer = dict(zip(columns, row))
            customers.append(customer)
        cursor.close()
        connection.close()
        return jsonify(customers)
    except Exception as e:
        return jsonify({'error': str(e)})
def add_room_to_database(email, room_number):
    try:
        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()
        query = f"INSERT INTO Room (Email, RoomNumber) VALUES ('{email}', {room_number})"
        cursor.execute(query)
        connection.commit()
        connection.close()

        return True
    except Exception as e:
        return False, str(e)
from email.mime.text import MIMEText

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
        jwt_token = jwt.encode({'email': email}, secret_key, algorithm='HS256')
        url = f"https://ae.arrive.waysdatalabs.com?token={jwt_token}"
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
        return jsonify({'success': True, 'message': 'Token is valid', 'decoded_token': decoded_token})
    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'error': 'Token has expired'})
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'error': 'Invalid token'})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3012)
