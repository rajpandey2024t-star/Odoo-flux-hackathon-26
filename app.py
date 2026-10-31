import os
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "local-hackathon-session-key-change-before-deploy")
DATABASE = Path(__file__).with_name("subscriptions.db")

DEFAULT_PLANS = [
    ("Starter", 1299, "month", "For individuals and small teams getting started."),
    ("Growth", 4499, "month", "For growing teams that need more room."),
    ("Enterprise", 24999, "year", "For larger teams with advanced needs."),
]
SAMPLE_SUBSCRIPTIONS = [
    ("Acme Corporation", "billing@acme.co", "Enterprise", 24999, "year", "2026-11-12", "Active"),
    ("Studio North", "hello@studionorth.in", "Growth", 4499, "month", "2026-11-14", "Active"),
    ("Monarch Brands", "finance@monarch.io", "Starter", 1299, "month", "2026-11-16", "Trial"),
    ("Greenfield Co.", "accounts@greenfield.co", "Growth", 42000, "year", "2026-10-28", "Past due"),
    ("Paper & Pine", "team@paperpine.com", "Starter", 1299, "month", "2026-11-20", "Active"),
]


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_db_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                amount INTEGER NOT NULL,
                billing_cycle TEXT NOT NULL CHECK (billing_cycle IN ('month', 'year')),
                description TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer TEXT NOT NULL,
                email TEXT NOT NULL,
                plan TEXT NOT NULL,
                amount INTEGER NOT NULL,
                billing_cycle TEXT NOT NULL,
                next_billing TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                subscription_id INTEGER NOT NULL,
                customer TEXT NOT NULL,
                email TEXT NOT NULL,
                plan TEXT NOT NULL,
                amount INTEGER NOT NULL,
                invoice_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                billing_period TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Draft',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subscription_id, billing_period),
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS discounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                discount_type TEXT NOT NULL CHECK (discount_type IN ('fixed', 'percentage')),
                value INTEGER NOT NULL,
                minimum_amount INTEGER NOT NULL DEFAULT 0,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                usage_limit INTEGER NOT NULL DEFAULT 0,
                used_count INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                method TEXT NOT NULL,
                amount INTEGER NOT NULL,
                payment_date TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'staff', 'customer')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        invoice_columns = {row["name"] for row in connection.execute("PRAGMA table_info(invoices)").fetchall()}
        if "subtotal" not in invoice_columns:
            connection.execute("ALTER TABLE invoices ADD COLUMN subtotal INTEGER NOT NULL DEFAULT 0")
            connection.execute("UPDATE invoices SET subtotal = amount")
        if "discount_amount" not in invoice_columns:
            connection.execute("ALTER TABLE invoices ADD COLUMN discount_amount INTEGER NOT NULL DEFAULT 0")
        plan_count = connection.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        if plan_count == 0:
            connection.executemany(
                "INSERT INTO plans (name, amount, billing_cycle, description) VALUES (?, ?, ?, ?)",
                DEFAULT_PLANS,
            )
        subscription_count = connection.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
        if subscription_count == 0:
            connection.executemany("""
                INSERT INTO subscriptions
                    (customer, email, plan, amount, billing_cycle, next_billing, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, SAMPLE_SUBSCRIPTIONS)


def serialize_plan(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "amount": row["amount"],
        "billing_cycle": row["billing_cycle"],
        "description": row["description"],
        "active": bool(row["active"]),
    }


def serialize_subscription(row):
    return {
        "id": row["id"],
        "customer": row["customer"],
        "email": row["email"],
        "plan": row["plan"],
        "amount": row["amount"],
        "billing_cycle": row["billing_cycle"],
        "next_billing": row["next_billing"],
        "status": row["status"],
    }


def serialize_invoice(row):
    return {
        "id": row["id"],
        "invoice_number": row["invoice_number"],
        "subscription_id": row["subscription_id"],
        "customer": row["customer"],
        "email": row["email"],
        "plan": row["plan"],
        "amount": row["amount"],
        "subtotal": row["subtotal"] if "subtotal" in row.keys() else row["amount"],
        "discount_amount": row["discount_amount"] if "discount_amount" in row.keys() else 0,
        "invoice_date": row["invoice_date"],
        "due_date": row["due_date"],
        "status": row["status"],
        "amount_paid": row["amount_paid"] if "amount_paid" in row.keys() else 0,
        "balance_due": row["balance_due"] if "balance_due" in row.keys() else row["amount"],
    }


def serialize_discount(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "discount_type": row["discount_type"],
        "value": row["value"],
        "minimum_amount": row["minimum_amount"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "usage_limit": row["usage_limit"],
        "used_count": row["used_count"],
        "active": bool(row["active"]),
    }


def serialize_payment(row):
    return {
        "id": row["id"],
        "invoice_number": row["invoice_number"],
        "customer": row["customer"],
        "method": row["method"],
        "amount": row["amount"],
        "payment_date": row["payment_date"],
        "note": row["note"],
    }


def get_plan_catalog(connection):
    rows = connection.execute(
        "SELECT name, amount, billing_cycle FROM plans WHERE active = 1"
    ).fetchall()
    return {row["name"]: {"amount": row["amount"], "cycle": row["billing_cycle"]} for row in rows}


def find_eligible_discount(connection, subtotal, today):
    rules = connection.execute("""
        SELECT * FROM discounts
        WHERE active = 1 AND start_date <= ? AND end_date >= ?
          AND (usage_limit = 0 OR used_count < usage_limit)
          AND minimum_amount <= ?
        ORDER BY id ASC
    """, (today, today, subtotal)).fetchall()
    if not rules:
        return None, 0
    rule = rules[0]
    if rule["discount_type"] == "percentage":
        discount_amount = round(subtotal * rule["value"] / 100)
    else:
        discount_amount = rule["value"]
    return rule, min(subtotal, discount_amount)


@app.before_request
def load_logged_in_user():
    if request.endpoint in ("static", "setup", "login", "signup", "logout"):
        return
    user_id = session.get("user_id")
    if user_id:
        with get_db_connection() as connection:
            g.user = connection.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if g.user:
            if g.user["role"] == "customer":
                allowed = {"customer_portal", "customer_overview", "customer_subscriptions", "customer_invoices", "logout"}
                if request.endpoint not in allowed:
                    if request.path.startswith("/api/"):
                        return jsonify({"error": "Customers can only view their own portal data."}), 403
                    return redirect(url_for("customer_portal"))
            return
        session.clear()
    with get_db_connection() as connection:
        users_exist = connection.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if request.path.startswith("/api/"):
        return jsonify({"error": "Please sign in to continue."}), 401
    return redirect(url_for("login" if users_exist else "setup"))


@app.context_processor
def add_current_user_to_templates():
    return {"current_user": getattr(g, "user", None)}


@app.route("/setup", methods=["GET", "POST"])
def setup():
    with get_db_connection() as connection:
        users_exist = connection.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if users_exist:
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        valid_password = (
            len(password) > 8
            and re.search(r"[A-Z]", password)
            and re.search(r"[a-z]", password)
            and re.search(r"[^A-Za-z0-9]", password)
        )
        if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            error = "Please enter your name and a valid email address."
        elif not valid_password:
            error = "Password must be more than 8 characters and include uppercase, lowercase and a special character."
        else:
            try:
                with get_db_connection() as connection:
                    cursor = connection.execute(
                        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                        (name, email, generate_password_hash(password, method="pbkdf2:sha256")),
                    )
                session.clear()
                session["user_id"] = cursor.lastrowid
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                error = "An account with this email already exists."
    return render_template("setup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    with get_db_connection() as connection:
        users_exist = connection.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if not users_exist:
        return redirect(url_for("setup"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db_connection() as connection:
            user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("customer_portal" if user["role"] == "customer" else "dashboard"))
        error = "Email or password is incorrect."
    return render_template("login.html", error=error)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        valid_password = (
            len(password) > 8
            and re.search(r"[A-Z]", password)
            and re.search(r"[a-z]", password)
            and re.search(r"[^A-Za-z0-9]", password)
        )
        if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            error = "Please enter your name and a valid email address."
        elif not valid_password:
            error = "Password must be more than 8 characters and include uppercase, lowercase and a special character."
        else:
            with get_db_connection() as connection:
                has_subscription = connection.execute(
                    "SELECT 1 FROM subscriptions WHERE lower(email) = ? LIMIT 1", (email,)
                ).fetchone()
            if not has_subscription:
                error = "We could not find a subscription for this email. Check the address or contact the Brightloop team."
            else:
                try:
                    with get_db_connection() as connection:
                        cursor = connection.execute(
                            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'customer')",
                            (name, email, generate_password_hash(password, method="pbkdf2:sha256")),
                        )
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    return redirect(url_for("customer_portal"))
                except sqlite3.IntegrityError:
                    error = "An account with this email already exists. Try signing in."
    return render_template("signup.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/portal")
def customer_portal():
    if g.user["role"] != "customer":
        return redirect(url_for("dashboard"))
    return render_template("portal.html")


@app.route("/api/customer/overview")
def customer_overview():
    if g.user["role"] != "customer":
        return jsonify({"error": "Customer account required."}), 403
    email = g.user["email"].lower()
    with get_db_connection() as connection:
        subscription_count = connection.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE lower(email) = ? AND status = 'Active'", (email,)
        ).fetchone()[0]
        invoices = connection.execute("""
            SELECT COALESCE(SUM(invoices.amount - COALESCE(paid.total, 0)), 0)
            FROM invoices
            LEFT JOIN (SELECT invoice_id, SUM(amount) AS total FROM payments GROUP BY invoice_id) paid
                ON paid.invoice_id = invoices.id
            WHERE lower(invoices.email) = ?
        """, (email,)).fetchone()[0]
    return jsonify({"active_subscriptions": subscription_count, "balance_due": invoices})


@app.route("/api/customer/subscriptions")
def customer_subscriptions():
    if g.user["role"] != "customer":
        return jsonify({"error": "Customer account required."}), 403
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM subscriptions WHERE lower(email) = ? ORDER BY id DESC",
            (g.user["email"].lower(),),
        ).fetchall()
    return jsonify([serialize_subscription(row) for row in rows])


@app.route("/api/customer/invoices")
def customer_invoices():
    if g.user["role"] != "customer":
        return jsonify({"error": "Customer account required."}), 403
    with get_db_connection() as connection:
        rows = connection.execute("""
            SELECT invoices.*,
                COALESCE(SUM(payments.amount), 0) AS amount_paid,
                invoices.amount - COALESCE(SUM(payments.amount), 0) AS balance_due
            FROM invoices LEFT JOIN payments ON payments.invoice_id = invoices.id
            WHERE lower(invoices.email) = ?
            GROUP BY invoices.id ORDER BY invoices.id DESC
        """, (g.user["email"].lower(),)).fetchall()
    return jsonify([serialize_invoice(row) for row in rows])


@app.route("/api/plans", methods=["GET"])
def list_plans():
    with get_db_connection() as connection:
        rows = connection.execute("SELECT * FROM plans ORDER BY amount").fetchall()
    return jsonify([serialize_plan(row) for row in rows])


@app.route("/api/discounts", methods=["GET"])
def list_discounts():
    with get_db_connection() as connection:
        rows = connection.execute("SELECT * FROM discounts ORDER BY id DESC").fetchall()
    return jsonify([serialize_discount(row) for row in rows])


@app.route("/api/discounts", methods=["POST"])
def create_discount():
    if g.user["role"] != "admin":
        return jsonify({"error": "Only an admin can create discount rules."}), 403
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    discount_type = str(data.get("discount_type", "")).strip()
    start_date = str(data.get("start_date", "")).strip()
    end_date = str(data.get("end_date", "")).strip()
    try:
        value = int(data.get("value", 0))
        minimum_amount = int(data.get("minimum_amount", 0) or 0)
        usage_limit = int(data.get("usage_limit", 0) or 0)
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a value, valid dates and whole-number limits."}), 400

    if not name or len(name) > 60:
        return jsonify({"error": "Discount name is required (up to 60 characters)."}), 400
    if discount_type not in ("fixed", "percentage"):
        return jsonify({"error": "Choose a fixed or percentage discount."}), 400
    if value < 1 or (discount_type == "percentage" and value > 100):
        return jsonify({"error": "Enter a valid discount value."}), 400
    if minimum_amount < 0 or usage_limit < 0 or start > end:
        return jsonify({"error": "Check the minimum amount, usage limit and date range."}), 400
    try:
        with get_db_connection() as connection:
            cursor = connection.execute("""
                INSERT INTO discounts
                    (name, discount_type, value, minimum_amount, start_date, end_date, usage_limit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, discount_type, value, minimum_amount, start_date, end_date, usage_limit))
            row = connection.execute("SELECT * FROM discounts WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "A discount rule with this name already exists."}), 409
    return jsonify(serialize_discount(row)), 201


@app.route("/api/plans", methods=["POST"])
def create_plan():
    if g.user["role"] != "admin":
        return jsonify({"error": "Only an admin can create plans."}), 403
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    cycle = str(data.get("billing_cycle", "")).strip()
    try:
        amount = int(data.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0

    if not name or len(name) > 60:
        return jsonify({"error": "Plan name is required (up to 60 characters)."}), 400
    if amount < 1:
        return jsonify({"error": "Enter a price greater than zero."}), 400
    if cycle not in ("month", "year"):
        return jsonify({"error": "Choose monthly or yearly billing."}), 400

    try:
        with get_db_connection() as connection:
            cursor = connection.execute("""
                INSERT INTO plans (name, amount, billing_cycle, description)
                VALUES (?, ?, ?, ?)
            """, (name, amount, cycle, description))
            row = connection.execute("SELECT * FROM plans WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "A plan with this name already exists."}), 409
    return jsonify(serialize_plan(row)), 201


@app.route("/api/subscriptions", methods=["GET"])
def list_subscriptions():
    with get_db_connection() as connection:
        rows = connection.execute("SELECT * FROM subscriptions ORDER BY id DESC").fetchall()
    return jsonify([serialize_subscription(row) for row in rows])


@app.route("/api/subscriptions", methods=["POST"])
def create_subscription():
    data = request.get_json(silent=True) or {}
    customer = str(data.get("customer", "")).strip()
    email = str(data.get("email", "")).strip()
    plan = str(data.get("plan", "")).strip()
    start_date = str(data.get("start", "")).strip()

    if not customer or not email or not plan or not start_date:
        return jsonify({"error": "Customer, email, plan and start date are required."}), 400
    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        return jsonify({"error": "Please choose a valid start date."}), 400

    with get_db_connection() as connection:
        plan_info = get_plan_catalog(connection).get(plan)
        if not plan_info:
            return jsonify({"error": "Choose an available plan."}), 400
        if plan_info["cycle"] == "year":
            try:
                next_billing = start.replace(year=start.year + 1)
            except ValueError:
                next_billing = start.replace(year=start.year + 1, day=28)
        else:
            month = start.month % 12 + 1
            year = start.year + (start.month // 12)
            next_month = date(year, month, 1)
            next_billing = next_month + timedelta(days=min(start.day, 28) - 1)
        cursor = connection.execute("""
            INSERT INTO subscriptions
                (customer, email, plan, amount, billing_cycle, next_billing, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Active')
        """, (customer, email, plan, plan_info["amount"], plan_info["cycle"], next_billing.isoformat()))
        row = connection.execute("SELECT * FROM subscriptions WHERE id = ?", (cursor.lastrowid,)).fetchone()

    return jsonify(serialize_subscription(row)), 201


@app.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary():
    with get_db_connection() as connection:
        subscriptions = connection.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN status = 'Active' AND billing_cycle = 'month' THEN amount
                                  WHEN status = 'Active' AND billing_cycle = 'year' THEN amount / 12.0
                                  ELSE 0 END), 0) AS monthly_recurring_revenue,
                SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_subscriptions,
                COUNT(DISTINCT email) AS customers
            FROM subscriptions
        """).fetchone()
        invoices = connection.execute("""
            SELECT
                COALESCE(SUM(invoices.amount - COALESCE(paid.total, 0)), 0) AS outstanding,
                SUM(CASE WHEN invoices.due_date < ? AND invoices.amount > COALESCE(paid.total, 0)
                         THEN 1 ELSE 0 END) AS overdue_count
            FROM invoices
            LEFT JOIN (
                SELECT invoice_id, SUM(amount) AS total FROM payments GROUP BY invoice_id
            ) AS paid ON paid.invoice_id = invoices.id
        """, (date.today().isoformat(),)).fetchone()
        revenue = connection.execute("SELECT COALESCE(SUM(amount), 0) FROM payments").fetchone()[0]
    return jsonify({
        "monthly_recurring_revenue": round(subscriptions["monthly_recurring_revenue"]),
        "active_subscriptions": subscriptions["active_subscriptions"] or 0,
        "customers": subscriptions["customers"] or 0,
        "outstanding": invoices["outstanding"] or 0,
        "overdue_invoices": invoices["overdue_count"] or 0,
        "revenue_received": revenue,
    })


@app.route("/api/invoices", methods=["GET"])
def list_invoices():
    with get_db_connection() as connection:
        rows = connection.execute("""
            SELECT invoices.*,
                COALESCE(SUM(payments.amount), 0) AS amount_paid,
                invoices.amount - COALESCE(SUM(payments.amount), 0) AS balance_due
            FROM invoices LEFT JOIN payments ON payments.invoice_id = invoices.id
            GROUP BY invoices.id ORDER BY invoices.id DESC
        """).fetchall()
    return jsonify([serialize_invoice(row) for row in rows])


@app.route("/api/invoices/generate-due", methods=["POST"])
def generate_due_invoices():
    today = date.today().isoformat()
    created = 0
    with get_db_connection() as connection:
        due_subscriptions = connection.execute("""
            SELECT * FROM subscriptions
            WHERE next_billing <= ? AND status IN ('Active', 'Past due')
        """, (today,)).fetchall()
        for subscription in due_subscriptions:
            try:
                subtotal = subscription["amount"]
                discount_rule, discount_amount = find_eligible_discount(connection, subtotal, today)
                total = subtotal - discount_amount
                cursor = connection.execute("""
                    INSERT INTO invoices
                        (invoice_number, subscription_id, customer, email, plan, amount,
                         subtotal, discount_amount, invoice_date, due_date, billing_period, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"TEMP-{subscription['id']}-{subscription['next_billing']}",
                    subscription["id"], subscription["customer"], subscription["email"],
                    subscription["plan"], total, subtotal, discount_amount, today,
                    subscription["next_billing"], subscription["next_billing"],
                    "Paid" if total == 0 else "Draft",
                ))
                invoice_id = cursor.lastrowid
                invoice_number = f"BL-{date.today().year}-{invoice_id:05d}"
                connection.execute(
                    "UPDATE invoices SET invoice_number = ? WHERE id = ?",
                    (invoice_number, invoice_id),
                )
                if discount_rule:
                    connection.execute(
                        "UPDATE discounts SET used_count = used_count + 1 WHERE id = ?",
                        (discount_rule["id"],),
                    )
                created += 1
            except sqlite3.IntegrityError:
                # This subscription already has an invoice for this billing date.
                continue
        rows = connection.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
    return jsonify({"created": created, "invoices": [serialize_invoice(row) for row in rows]})


@app.route("/api/payments", methods=["GET"])
def list_payments():
    with get_db_connection() as connection:
        rows = connection.execute("""
            SELECT payments.*, invoices.invoice_number, invoices.customer
            FROM payments JOIN invoices ON invoices.id = payments.invoice_id
            ORDER BY payments.id DESC
        """).fetchall()
    return jsonify([serialize_payment(row) for row in rows])


@app.route("/api/payments", methods=["POST"])
def create_payment():
    data = request.get_json(silent=True) or {}
    method = str(data.get("method", "")).strip()
    payment_date = str(data.get("payment_date", "")).strip()
    note = str(data.get("note", "")).strip()
    try:
        invoice_id = int(data.get("invoice_id", 0))
        amount = int(data.get("amount", 0))
        date.fromisoformat(payment_date)
    except (TypeError, ValueError):
        return jsonify({"error": "Choose an invoice, enter an amount and select a valid date."}), 400

    if method not in ("UPI", "Bank transfer", "Card", "Cash"):
        return jsonify({"error": "Choose a payment method."}), 400
    if amount < 1:
        return jsonify({"error": "Payment amount must be greater than zero."}), 400

    with get_db_connection() as connection:
        invoice = connection.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not invoice:
            return jsonify({"error": "That invoice could not be found."}), 404
        already_paid = connection.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ?", (invoice_id,)
        ).fetchone()[0]
        balance_due = invoice["amount"] - already_paid
        if amount > balance_due:
            return jsonify({"error": f"Payment is higher than the remaining balance of ₹{balance_due:,}."}), 400
        cursor = connection.execute("""
            INSERT INTO payments (invoice_id, method, amount, payment_date, note)
            VALUES (?, ?, ?, ?, ?)
        """, (invoice_id, method, amount, payment_date, note))
        new_paid_total = already_paid + amount
        new_status = "Paid" if new_paid_total == invoice["amount"] else "Partially paid"
        connection.execute("UPDATE invoices SET status = ? WHERE id = ?", (new_status, invoice_id))
        row = connection.execute("""
            SELECT payments.*, invoices.invoice_number, invoices.customer
            FROM payments JOIN invoices ON invoices.id = payments.invoice_id
            WHERE payments.id = ?
        """, (cursor.lastrowid,)).fetchone()
    return jsonify(serialize_payment(row)), 201


@app.route("/api/team", methods=["GET"])
def list_team_members():
    if g.user["role"] != "admin":
        return jsonify({"error": "Only an admin can view team members."}), 403
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, email, role FROM users WHERE role = 'staff' ORDER BY name"
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/team", methods=["POST"])
def create_team_member():
    if g.user["role"] != "admin":
        return jsonify({"error": "Only an admin can add a staff member."}), 403
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    valid_password = (
        len(password) > 8
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[^A-Za-z0-9]", password)
    )
    if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"error": "Please enter a name and valid email address."}), 400
    if not valid_password:
        return jsonify({"error": "Password must be more than 8 characters with uppercase, lowercase and a special character."}), 400
    try:
        with get_db_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'staff')",
                (name, email, generate_password_hash(password, method="pbkdf2:sha256")),
            )
            row = connection.execute(
                "SELECT id, name, email, role FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists."}), 409
    return jsonify(dict(row)), 201


initialize_database()

if __name__ == "__main__":
    app.run(debug=True)
