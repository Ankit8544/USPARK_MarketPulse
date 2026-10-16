from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "USPARK MarketPulse is running!"

@app.route("/status")
def status():
    return jsonify({
        "status": "success",
        "message": "USPARK API is running"
    })

if __name__ == "__main__":
    app.run()