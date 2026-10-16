from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "USPARK - Ujjivan Small Finance Bank"

@app.route("/status")
def status():
    return jsonify({
        "status": "success",
        "message": "USPARK API is running"
    })

if __name__ == "__main__":
    app.run(debug=True)