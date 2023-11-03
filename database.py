from flask import Flask, jsonify
import pyodbc

app = Flask(__name__)
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3012)
