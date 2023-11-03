from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
@app.route('/api')
def hello_world():
    return {'message': 'Hello, World!'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3012)
