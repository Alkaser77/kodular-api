from flask import Flask, request, jsonify
import time

app = Flask(__name__)
GOOGLE_DRIVE_LINK = "https://drive.google.com/uc?export=download&id=1bB0Tkx2Oc5Dc8DBCjHBQryvkUGj3GWKT"

@app.route('/')
def home():
    return "API is Running"

@app.route('/check', methods=['POST'])
def check():
    data = request.get_json()
    return jsonify({"status":"active","key":"50523a49","expire":int(time.time()*1000)+86400000,"link":GOOGLE_DRIVE_LINK})

if __name__ == '__main__':
    app.run()
