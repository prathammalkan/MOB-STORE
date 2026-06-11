import datetime
import os
import random
from functools import wraps

import psycopg2
from psycopg2 import extras
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:  # Optional in local development until dependencies are installed.
    cloudinary = None


app = Flask(__name__)
_secret_key = os.environ.get("SECRET_KEY", "fallback-secret-for-development")
app.secret_key = _secret_key

@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    import traceback
    tb = traceback.format_exc()
    return f"<h1>Internal Server Error</h1><p>An unexpected error occurred:</p><pre>{tb}</pre>", 500

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"


DEFAULT_IMAGE = "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=80"
DEMO_PRODUCTS = [
    {
        "brand": "Apple",
        "model": "iPhone 15 Pro",
        "price": 134900,
        "ram": "8 GB",
        "storage": "256 GB",
        "battery": "3274 mAh",
        "category": "Flagship",
        "stock": 12,
        "description": "Titanium finish, pro camera system, and all-day premium performance.",
        "image_url": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?auto=format&fit=crop&w=900&q=80",
    },
    {
        "brand": "Samsung",
        "model": "Galaxy S24 Ultra",
        "price": 129999,
        "ram": "12 GB",
        "storage": "512 GB",
        "battery": "5000 mAh",
        "category": "Flagship",
        "stock": 10,
        "description": "AI features, S Pen productivity, and an elite display tuned for creators.",
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?auto=format&fit=crop&w=900&q=80",
    },
    {
        "brand": "OnePlus",
        "model": "OnePlus 12",
        "price": 64999,
        "ram": "12 GB",
        "storage": "256 GB",
        "battery": "5400 mAh",
        "category": "Performance",
        "stock": 18,
        "description": "Fast charging, smooth OxygenOS experience, and flagship-class speed.",
        "image_url": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?auto=format&fit=crop&w=900&q=80",
    },
]


def configure_cloudinary():
    if cloudinary is None:
        return
    if os.environ.get("CLOUDINARY_URL"):
        cloudinary.config(secure=True)
        return

    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")
    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )


def connect():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(database_url, cursor_factory=extras.RealDictCursor)


def query_all(query, params=None):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchall()


def query_one(query, params=None):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchone()


def execute(query, params=None, fetchone=False, fetchall=False):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            result = None
            if fetchone:
                result = cur.fetchone()
            elif fetchall:
                result = cur.fetchall()
            conn.commit()
            return result


def generate_imei():
    return str(random.randint(100000000000000, 999999999999999))


def format_currency(amount):
    return f"{int(amount):,}"


def normalize_product(product):
    if not product:
        return product

    product["stock"] = product.get("stock") if product.get("stock") is not None else 0
    product["description"] = product.get("description") or "Premium smartphone with flagship styling and dependable performance."
    product["image_url"] = product.get("image_url") or DEFAULT_IMAGE
    return product


def upload_product_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None

    if cloudinary is None or not cloudinary.config().cloud_name:
        return None, None

    result = cloudinary.uploader.upload(
        file_storage,
        folder="mobstore/products",
        resource_type="image",
    )
    return result.get("secure_url"), result.get("public_id")


def seed_demo_products():
    count = query_one("SELECT COUNT(*) AS count FROM products")
    if count and count["count"] > 0:
        return

    for product in DEMO_PRODUCTS:
        execute(
            """
            INSERT INTO products
            (brand, model, price, ram, storage, battery, category, stock, description, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                product["brand"],
                product["model"],
                product["price"],
                product["ram"],
                product["storage"],
                product["battery"],
                product["category"],
                product["stock"],
                product["description"],
                product["image_url"],
            ),
        )


def ensure_schema():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    brand VARCHAR(100) NOT NULL,
                    model VARCHAR(150) NOT NULL,
                    price NUMERIC(10, 2) NOT NULL,
                    ram VARCHAR(50),
                    storage VARCHAR(50),
                    battery VARCHAR(50),
                    category VARCHAR(100),
                    stock INTEGER NOT NULL DEFAULT 0,
                    description TEXT,
                    image_url TEXT,
                    image_public_id VARCHAR(255),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS cart (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(user_id, product_id)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    user_email VARCHAR(255) NOT NULL,
                    total_price NUMERIC(10, 2) NOT NULL,
                    imei VARCHAR(20) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'Completed',
                    order_date TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                    product_name VARCHAR(255) NOT NULL,
                    price NUMERIC(10, 2) NOT NULL,
                    quantity INTEGER NOT NULL,
                    line_total NUMERIC(10, 2) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS service_requests (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    imei VARCHAR(20) NOT NULL,
                    issue TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
            )

            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(150)")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()")
            cur.execute("UPDATE users SET name = COALESCE(NULLIF(name, ''), split_part(email, '@', 1))")

            cur.execute("ALTER TABLE admins ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()")

            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS ram VARCHAR(50)")
            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS storage VARCHAR(50)")
            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS battery VARCHAR(50)")
            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS category VARCHAR(100)")
            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS stock INTEGER NOT NULL DEFAULT 0")
            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS description TEXT")
            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT")
            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_public_id VARCHAR(255)")
            cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()")
            cur.execute("UPDATE products SET image_url = %s WHERE image_url IS NULL OR image_url = ''", (DEFAULT_IMAGE,))
            cur.execute(
                """
                UPDATE products
                SET description = 'Premium smartphone with flagship styling and dependable performance.'
                WHERE description IS NULL OR description = ''
                """
            )

            cur.execute("ALTER TABLE cart ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1")

            cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS user_id INTEGER")
            cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'Completed'")
            cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_date TIMESTAMP NOT NULL DEFAULT NOW()")

            cur.execute("ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS user_id INTEGER")
            cur.execute("ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'Pending'")
            cur.execute("ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()")

            cur.execute("SELECT COUNT(*) AS count FROM admins")
            if cur.fetchone()["count"] == 0:
                admin_username = os.environ.get("ADMIN_USERNAME", "admin")
                admin_password = os.environ.get("ADMIN_PASSWORD")
                if not admin_password:
                    import secrets as _sec
                    admin_password = _sec.token_urlsafe(16)
                    print(
                        "\n" + "=" * 60 + "\n"
                        "  ADMIN_PASSWORD env var is not set.\n"
                        f"  A one-time password has been generated:\n\n"
                        f"      Username : {admin_username}\n"
                        f"      Password : {admin_password}\n\n"
                        "  Set ADMIN_PASSWORD in your environment to keep\n"
                        "  a stable password across restarts.\n"
                        + "=" * 60 + "\n",
                        flush=True,
                    )
                cur.execute(
                    """
                    INSERT INTO admins (username, password)
                    VALUES (%s, %s)
                    """,
                    (admin_username, generate_password_hash(admin_password)),
                )
        conn.commit()

    seed_demo_products()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "admin" not in session:
            flash("Admin access required.", "warning")
            return redirect(url_for("admin"))
        return view(*args, **kwargs)

    return wrapped_view


def get_cart_summary(user_id):
    rows = query_all(
        """
        SELECT
            c.product_id,
            c.quantity,
            p.brand,
            p.model,
            p.price,
            p.stock,
            p.image_url
        FROM cart c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = %s
        ORDER BY c.id DESC
        """,
        (user_id,),
    )

    items = []
    total = 0
    for row in rows:
        row["image_url"] = row.get("image_url") or DEFAULT_IMAGE
        subtotal = float(row["price"]) * row["quantity"]
        total += subtotal
        row["subtotal"] = subtotal
        items.append(row)
    return items, total


def get_order_history(user_id):
    orders = query_all(
        """
        SELECT
            o.*,
            COALESCE(SUM(oi.quantity), 0) AS units
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.user_id = %s
        GROUP BY o.id
        ORDER BY o.order_date DESC
        """,
        (user_id,),
    )

    for order in orders:
        order["items"] = query_all(
            """
            SELECT *
            FROM order_items
            WHERE order_id = %s
            ORDER BY id ASC
            """,
            (order["id"],),
        )
    return orders


@app.context_processor
def inject_globals():
    cart_count = 0
    if session.get("user_id"):
        result = query_one(
            "SELECT COALESCE(SUM(quantity), 0) AS count FROM cart WHERE user_id = %s",
            (session["user_id"],),
        )
        cart_count = result["count"] if result else 0

    return {
        "cart_count": cart_count,
        "current_year": datetime.datetime.now().year,
        "currency": format_currency,
    }


@app.route("/")
def landing():
    featured_products = [
        normalize_product(product) for product in query_all(
        """
        SELECT * FROM products
        ORDER BY created_at DESC
        LIMIT 3
        """
        )
    ]
    stats = query_one(
        """
        SELECT
            (SELECT COUNT(*) FROM products) AS products,
            (SELECT COUNT(*) FROM users) AS users,
            (SELECT COUNT(*) FROM orders) AS orders
        """
    )
    return render_template("landing.html", featured_products=featured_products, stats=stats)


@app.route("/store")
def store():
    search = request.args.get("search", "").strip()
    brand = request.args.get("brand", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "latest")

    conditions = []
    params = []
    if search:
        conditions.append("(brand ILIKE %s OR model ILIKE %s OR description ILIKE %s)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern])
    if brand:
        conditions.append("brand = %s")
        params.append(brand)
    if category:
        conditions.append("category = %s")
        params.append(category)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_map = {
        "price_low": "price ASC",
        "price_high": "price DESC",
        "brand": "brand ASC, model ASC",
        "latest": "created_at DESC",
    }
    order_clause = order_map.get(sort, order_map["latest"])

    products = [
        normalize_product(product) for product in query_all(
        f"""
        SELECT * FROM products
        {where_clause}
        ORDER BY {order_clause}
        """,
        params,
        )
    ]
    brands = query_all("SELECT DISTINCT brand FROM products ORDER BY brand ASC")
    categories = query_all("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category <> '' ORDER BY category ASC")

    return render_template(
        "home.html",
        products=products,
        filters={"search": search, "brand": brand, "category": category, "sort": sort},
        brands=brands,
        categories=categories,
    )


@app.route("/product/<int:product_id>")
def product(product_id):
    selected_product = normalize_product(query_one("SELECT * FROM products WHERE id = %s", (product_id,)))
    if not selected_product:
        flash("Product not found.", "danger")
        return redirect(url_for("store"))

    related_products = [
        normalize_product(product) for product in query_all(
        """
        SELECT * FROM products
        WHERE category = %s AND id <> %s
        ORDER BY created_at DESC
        LIMIT 3
        """,
        (selected_product["category"], product_id),
        )
    ]
    return render_template("product.html", product=selected_product, related_products=related_products)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("store"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        existing_user = query_one("SELECT id FROM users WHERE email = %s", (email,))
        if existing_user:
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        user = execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (%s, %s, %s)
            RETURNING id, email
            """,
            (name, email, generate_password_hash(password)),
            fetchone=True,
        )
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["user_name"] = name
        flash("Account created successfully.", "success")
        return redirect(url_for("store"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("store"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE email = %s", (email,))

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_name"] = user.get("name") or email.split("@")[0]
            flash("Welcome back.", "success")
            return redirect(url_for("store"))

        flash("Invalid login credentials.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("landing"))


@app.route("/add_to_cart/<int:product_id>", methods=["GET", "POST"])
@login_required
def add_to_cart(product_id):
    quantity = int(request.form.get("quantity", 1))
    product = query_one("SELECT id, stock FROM products WHERE id = %s", (product_id,))
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("store"))

    existing = query_one(
        "SELECT id, quantity FROM cart WHERE user_id = %s AND product_id = %s",
        (session["user_id"], product_id),
    )
    desired_quantity = quantity + (existing["quantity"] if existing else 0)

    if product["stock"] <= 0:
        flash("This product is currently out of stock.", "danger")
        return redirect(url_for("product", product_id=product_id))

    if desired_quantity > product["stock"]:
        flash("Requested quantity exceeds available stock.", "warning")
        return redirect(url_for("cart" if existing else "product", product_id=product_id))

    if existing:
        execute(
            "UPDATE cart SET quantity = %s WHERE id = %s",
            (desired_quantity, existing["id"]),
        )
    else:
        execute(
            "INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s)",
            (session["user_id"], product_id, quantity),
        )

    flash("Added to cart.", "success")
    return redirect(url_for("cart"))


@app.route("/cart")
@login_required
def cart():
    items, total = get_cart_summary(session["user_id"])
    return render_template("cart.html", items=items, total=total)


@app.route("/update_cart/<int:product_id>", methods=["POST"])
@login_required
def update_cart(product_id):
    quantity = max(1, int(request.form.get("quantity", 1)))
    product = query_one("SELECT stock FROM products WHERE id = %s", (product_id,))
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("cart"))

    if quantity > product["stock"]:
        flash("Requested quantity exceeds available stock.", "warning")
        return redirect(url_for("cart"))

    execute(
        "UPDATE cart SET quantity = %s WHERE user_id = %s AND product_id = %s",
        (quantity, session["user_id"], product_id),
    )
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.route("/remove_cart/<int:product_id>")
@login_required
def remove_cart(product_id):
    execute(
        "DELETE FROM cart WHERE user_id = %s AND product_id = %s",
        (session["user_id"], product_id),
    )
    flash("Item removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items, total = get_cart_summary(session["user_id"])
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("store"))

    if request.method == "POST":
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (user_id, user_email, total_price, imei)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, order_date, imei, total_price
                    """,
                    (
                        session["user_id"],
                        session["user_email"],
                        total,
                        generate_imei(),
                    ),
                )
                order = cur.fetchone()

                for item in items:
                    line_total = float(item["price"]) * item["quantity"]
                    cur.execute(
                        """
                        INSERT INTO order_items
                        (order_id, product_id, product_name, price, quantity, line_total)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            order["id"],
                            item["product_id"],
                            f'{item["brand"]} {item["model"]}',
                            item["price"],
                            item["quantity"],
                            line_total,
                        ),
                    )
                    cur.execute(
                        "UPDATE products SET stock = stock - %s WHERE id = %s",
                        (item["quantity"], item["product_id"]),
                    )

                cur.execute("DELETE FROM cart WHERE user_id = %s", (session["user_id"],))
            conn.commit()

        flash("Order placed successfully.", "success")
        return redirect(url_for("invoice", order_id=order["id"]))

    return render_template("checkout.html", items=items, total=total)


@app.route("/invoice/<int:order_id>")
@login_required
def invoice(order_id):
    order = query_one(
        """
        SELECT * FROM orders
        WHERE id = %s AND user_id = %s
        """,
        (order_id, session["user_id"]),
    )
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("store"))

    items = query_all(
        """
        SELECT * FROM order_items
        WHERE order_id = %s
        ORDER BY id ASC
        """,
        (order_id,),
    )
    return render_template("invoice.html", order=order, items=items)


@app.route("/orders")
@login_required
def orders():
    user_orders = get_order_history(session["user_id"])
    return render_template("orders.html", orders=user_orders)


@app.route("/service", methods=["GET", "POST"])
def service():
    if request.method == "POST":
        imei = request.form.get("imei", "").strip()
        issue = request.form.get("problem", "").strip()
        execute(
            """
            INSERT INTO service_requests (user_id, imei, issue)
            VALUES (%s, %s, %s)
            """,
            (session.get("user_id"), imei, issue),
        )
        flash("Service request submitted successfully.", "success")
        return redirect(url_for("service"))

    recent_requests = []
    if session.get("user_id"):
        recent_requests = query_all(
            """
            SELECT * FROM service_requests
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (session["user_id"],),
        )
    return render_template("service.html", recent_requests=recent_requests)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin_user = query_one("SELECT * FROM admins WHERE username = %s", (username,))

        if admin_user and check_password_hash(admin_user["password"], password):
            session["admin"] = admin_user["username"]
            flash("Admin login successful.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "danger")

    return render_template("admin_login.html")


@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("admin"))


@app.route("/admin_dashboard", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        price = request.form.get("price", "0").strip()
        ram = request.form.get("ram", "").strip()
        storage = request.form.get("storage", "").strip()
        battery = request.form.get("battery", "").strip()
        category = request.form.get("category", "").strip()
        stock = request.form.get("stock", "0").strip()
        description = request.form.get("description", "").strip()
        image_url = request.form.get("image_url", "").strip()
        uploaded_image_url, public_id = upload_product_image(request.files.get("image"))

        final_image_url = uploaded_image_url or image_url or DEFAULT_IMAGE
        execute(
            """
            INSERT INTO products
            (brand, model, price, ram, storage, battery, category, stock, description, image_url, image_public_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                brand,
                model,
                price,
                ram,
                storage,
                battery,
                category,
                stock,
                description,
                final_image_url,
                public_id,
            ),
        )
        flash("Product added successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    stats = query_one(
        """
        SELECT
            (SELECT COUNT(*) FROM users) AS users,
            (SELECT COUNT(*) FROM orders) AS orders,
            (SELECT COUNT(*) FROM products) AS products,
            (SELECT COALESCE(SUM(total_price), 0) FROM orders) AS revenue
        """
    )
    products = [normalize_product(product) for product in query_all("SELECT * FROM products ORDER BY created_at DESC")]
    orders = query_all(
        """
        SELECT o.id, o.user_email, o.total_price, o.status, o.order_date,
               COALESCE(SUM(oi.quantity), 0) AS units
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        GROUP BY o.id
        ORDER BY o.order_date DESC
        LIMIT 8
        """
    )
    service_requests = query_all(
        """
        SELECT * FROM service_requests
        ORDER BY created_at DESC
        LIMIT 8
        """
    )
    return render_template(
        "admin_dashboard.html",
        stats=stats,
        products=products,
        orders=orders,
        service_requests=service_requests,
        cloudinary_enabled=bool(cloudinary and cloudinary.config().cloud_name),
    )


@app.route("/admin/product/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    existing_product = normalize_product(query_one("SELECT * FROM products WHERE id = %s", (product_id,)))
    if not existing_product:
        flash("Product not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        image_url = request.form.get("image_url", "").strip() or existing_product["image_url"]
        uploaded_image_url, public_id = upload_product_image(request.files.get("image"))
        execute(
            """
            UPDATE products
            SET brand = %s,
                model = %s,
                price = %s,
                ram = %s,
                storage = %s,
                battery = %s,
                category = %s,
                stock = %s,
                description = %s,
                image_url = %s,
                image_public_id = %s
            WHERE id = %s
            """,
            (
                request.form.get("brand", "").strip(),
                request.form.get("model", "").strip(),
                request.form.get("price", "0").strip(),
                request.form.get("ram", "").strip(),
                request.form.get("storage", "").strip(),
                request.form.get("battery", "").strip(),
                request.form.get("category", "").strip(),
                request.form.get("stock", "0").strip(),
                request.form.get("description", "").strip(),
                uploaded_image_url or image_url,
                public_id or existing_product["image_public_id"],
                product_id,
            ),
        )
        flash("Product updated successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("product_form.html", product=existing_product)


@app.route("/delete_product/<int:product_id>")
@admin_required
def delete_product(product_id):
    linked_order = query_one(
        "SELECT id FROM order_items WHERE product_id = %s LIMIT 1",
        (product_id,),
    )
    if linked_order:
        flash("This product is linked to existing orders and cannot be deleted. Set stock to 0 or edit it instead.", "warning")
        return redirect(url_for("admin_dashboard"))

    execute("DELETE FROM products WHERE id = %s", (product_id,))
    flash("Product deleted.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    execute(
        "UPDATE orders SET status = %s WHERE id = %s",
        (request.form.get("status", "Completed"), order_id),
    )
    flash("Order status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/service/<int:request_id>/status", methods=["POST"])
@admin_required
def update_service_status(request_id):
    execute(
        "UPDATE service_requests SET status = %s WHERE id = %s",
        (request.form.get("status", "Pending"), request_id),
    )
    flash("Service request updated.", "success")
    return redirect(url_for("admin_dashboard"))


configure_cloudinary()

# Lazy schema initialisation — runs once on the first request so that
# Vercel serverless cold-starts don't crash at import time when the
# database connection is not yet available.
_schema_initialised = False


@app.before_request
def _lazy_ensure_schema():
    global _schema_initialised
    if not _schema_initialised:
        try:
            ensure_schema()
            _schema_initialised = True
        except Exception as exc:  # noqa: BLE001
            # Log but don't crash — the route handler will surface a proper
            # error when it tries to use the database.
            import traceback
            traceback.print_exc()
            print(f"[WARN] Schema initialisation failed: {exc}", flush=True)


@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    import traceback
    tb = traceback.format_exc()
    return f"<h1>Internal Server Error</h1><p>An unexpected error occurred:</p><pre>{tb}</pre>", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
