from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import OperationalError
import os
import time
import random
from datetime import datetime

app = Flask(__name__)

db_url = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://student:student123@localhost:3307/student_db"

)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ===============================
# WAIT FOR MYSQL (Docker safe)
# ===============================
retries = 5
while retries > 0:
    try:
        with app.app_context():
            db.engine.connect()
        print("Connected to MySQL!")
        break
    except OperationalError:
        print("Waiting for MySQL...")
        time.sleep(5)
        retries -= 1

# ===============================
# MODELS
# ===============================

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(15))
    password_hash = db.Column(db.String(200))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Account(db.Model):
    account_number = db.Column(db.String(12), primary_key=True)
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customer.id"),
        nullable=False
    )
    account_type = db.Column(db.String(20))
    balance = db.Column(db.Float, default=0.0)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(
        db.String(12),
        db.ForeignKey("account.account_number"),
        nullable=False
    )
    type = db.Column(db.String(20))  # deposit / withdraw
    amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

# ===============================
# HELPER FUNCTIONS
# ===============================

def generate_account_number():
    return str(random.randint(10**11, 10**12 - 1))


def notify(message):
    # Console notification (can upgrade to email later)
    print(f"🔔 NOTIFICATION: {message}")

# ===============================
# ROUTES
# ===============================

@app.route("/")
def home():
    return {"message": "Advanced Bank API Running 🚀"}


# -------------------------------
# CREATE CUSTOMER
# -------------------------------
@app.route("/customers", methods=["POST"])
def create_customer():
    data = request.json

    if Customer.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 400

    c = Customer(
        name=data["name"],
        email=data["email"],
        phone=data["phone"]
    )
    c.set_password(data["password"])

    db.session.add(c)
    db.session.commit()

    notify(f"Customer {c.name} created successfully!")

    return jsonify({"id": c.id})


# -------------------------------
# CREATE ACCOUNT
# -------------------------------
@app.route("/accounts", methods=["POST"])
def create_account():
    data = request.json

    acc_no = generate_account_number()

    acc = Account(
        account_number=acc_no,
        customer_id=data["customer_id"],
        account_type=data["account_type"],
        balance=data.get("balance", 0.0)
    )

    db.session.add(acc)
    db.session.commit()

    notify(f"Account {acc_no} created successfully!")

    return jsonify({"account_number": acc_no})


# -------------------------------
# GET ACCOUNT
# -------------------------------
@app.route("/accounts/<acc_no>")
def get_account(acc_no):
    acc = Account.query.get_or_404(acc_no)
    return jsonify({
        "account_number": acc.account_number,
        "balance": acc.balance
    })


# -------------------------------
# DEPOSIT
# -------------------------------
@app.route("/deposit", methods=["POST"])
def deposit():
    data = request.json
    acc = Account.query.get_or_404(data["account_number"])

    amount = float(data["amount"])
    acc.balance += amount

    transaction = Transaction(
        account_number=acc.account_number,
        type="deposit",
        amount=amount
    )

    db.session.add(transaction)
    db.session.commit()

    notify(f"{amount} deposited to {acc.account_number}")

    return jsonify({"new_balance": acc.balance})


# -------------------------------
# WITHDRAW
# -------------------------------
@app.route("/withdraw", methods=["POST"])
def withdraw():
    data = request.json
    acc = Account.query.get_or_404(data["account_number"])

    amount = float(data["amount"])

    if acc.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    acc.balance -= amount

    transaction = Transaction(
        account_number=acc.account_number,
        type="withdraw",
        amount=amount
    )

    db.session.add(transaction)
    db.session.commit()

    notify(f"{amount} withdrawn from {acc.account_number}")

    return jsonify({"new_balance": acc.balance})


# -------------------------------
# TRANSACTION HISTORY
# -------------------------------
@app.route("/transactions/<acc_no>")
def transactions(acc_no):
    txns = Transaction.query.filter_by(account_number=acc_no).all()

    return jsonify([
        {
            "type": t.type,
            "amount": t.amount,
            "timestamp": t.timestamp
        }
        for t in txns
    ])


# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
