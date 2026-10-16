import os
import sqlite3
from functools import wraps

from flask import (
    Flask, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "campuscart-product-ordering-secret-key"
DB_PATH = os.path.join(os.path.dirname(__file__), "campuscart.db")

SORT_CHOICES = {
    "newest": ("Newest first", "p.id DESC"),
    "price_low": ("Price: low to high", "p.price ASC"),
    "price_high": ("Price: high to low", "p.price DESC"),
    "rating": ("Top rated", "avg_rating DESC, p.id"),
    "name": ("Name A to Z", "p.name ASC"),
}

PAY_MODES = ["Cash on delivery", "UPI on delivery"]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT,
            stock INTEGER DEFAULT 0,
            image_file TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'placed',
            hostel_block TEXT,
            room_no TEXT,
            phone TEXT,
            pay_mode TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price_each REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );

        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            UNIQUE (user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE (user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
        """
    )
    count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        sample = [
            ("Ruled Notebook A5", "200-page ruled notebook with a hard cover and spiral binding.", 129.0, "Stationery", 40, "notebook.svg"),
            ("Mechanical Pencil Set", "Pack of 3 pencils (0.5mm) with spare leads.", 149.0, "Stationery", 60, "pencil.svg"),
            ("Wireless Mouse", "2.4GHz wireless mouse with a USB receiver.", 499.0, "Electronics", 25, "mouse.svg"),
            ("USB-C Cable 1m", "Fast-charging braided cable that lasts long.", 199.0, "Electronics", 80, "cable.svg"),
            ("Desk Lamp", "Adjustable LED desk lamp with 3 brightness levels.", 899.0, "Home", 15, "lamp.svg"),
            ("Ceramic Coffee Mug", "350ml matte-finish mug for late-night study.", 249.0, "Home", 50, "mug.svg"),
            ("Canvas Backpack", "18L water-resistant backpack made for college.", 1099.0, "Bags", 20, "backpack.svg"),
            ("Bluetooth Earbuds", "In-ear earbuds with a charging case.", 1499.0, "Electronics", 18, "earbuds.svg"),
            ("Sticky Notes Pack", "5 colours, 100 sheets each.", 79.0, "Stationery", 100, "sticky.svg"),
            ("Water Bottle 1L", "Leakproof stainless steel bottle.", 349.0, "Home", 35, "bottle.svg"),
            ("Graphic T-Shirt", "100% cotton, unisex fit.", 599.0, "Apparel", 30, "tshirt.svg"),
            ("Laptop Sleeve 14-inch", "Padded neoprene sleeve with a front pocket.", 449.0, "Bags", 22, "sleeve.svg"),
        ]
        db.executemany(
            "INSERT INTO products (name, description, price, category, stock, image_file) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            sample,
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Only allow redirects to pages inside this site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("index")


def read_quantity(text, default=1):
    try:
        return max(int(text), 1)
    except (TypeError, ValueError):
        return default


def cart_lines(db):
    """Return (lines, total) for the session cart. Quantities are capped to stock."""
    cart = session.get("cart", {})
    lines = []
    total = 0
    for pid, qty in cart.items():
        product = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if product is None:
            continue
        qty = min(qty, product["stock"]) if product["stock"] > 0 else 0
        if qty <= 0:
            continue
        subtotal = product["price"] * qty
        total += subtotal
        lines.append({"product": product, "quantity": qty, "subtotal": subtotal})
    return lines, total


@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    wish_count = 0
    if "user_id" in session:
        wish_count = get_db().execute(
            "SELECT COUNT(*) FROM wishlist WHERE user_id = ?", (session["user_id"],)
        ).fetchone()[0]
    return dict(
        cart_count=sum(cart.values()) if cart else 0,
        wish_count=wish_count,
        current_user_name=session.get("user_name"),
    )


@app.template_filter("money")
def money(value):
    return f"₹{value:,.2f}"


@app.template_filter("stars")
def stars(value):
    full = int(round(value or 0))
    return "★" * full + "☆" * (5 - full)


# ---------------------------------------------------------------------------
# Browsing products
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    category = request.args.get("category", "")
    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "newest")
    if sort not in SORT_CHOICES:
        sort = "newest"

    sql = (
        "SELECT p.*, COALESCE((SELECT AVG(rating) FROM reviews WHERE product_id = p.id), 0) AS avg_rating, "
        "(SELECT COUNT(*) FROM reviews WHERE product_id = p.id) AS review_count "
        "FROM products p WHERE 1=1"
    )
    params = []
    if category:
        sql += " AND p.category = ?"
        params.append(category)
    if query:
        sql += " AND (p.name LIKE ? OR p.description LIKE ?)"
        params += [f"%{query}%", f"%{query}%"]
    sql += f" ORDER BY {SORT_CHOICES[sort][1]}"

    products = db.execute(sql, params).fetchall()
    categories = [
        r["category"]
        for r in db.execute("SELECT DISTINCT category FROM products ORDER BY category")
    ]
    wished = set()
    if "user_id" in session:
        wished = {
            r["product_id"]
            for r in db.execute(
                "SELECT product_id FROM wishlist WHERE user_id = ?", (session["user_id"],)
            )
        }
    return render_template(
        "index.html",
        products=products,
        categories=categories,
        active_category=category,
        query=query,
        sort=sort,
        sort_choices=SORT_CHOICES,
        wished=wished,
    )


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash("That product does not exist.", "error")
        return redirect(url_for("index"))

    reviews = db.execute(
        "SELECT r.*, u.name AS reviewer FROM reviews r JOIN users u ON u.id = r.user_id "
        "WHERE r.product_id = ? ORDER BY r.id DESC",
        (product_id,),
    ).fetchall()
    avg_rating = sum(r["rating"] for r in reviews) / len(reviews) if reviews else 0

    is_wished = False
    my_review = None
    if "user_id" in session:
        is_wished = db.execute(
            "SELECT 1 FROM wishlist WHERE user_id = ? AND product_id = ?",
            (session["user_id"], product_id),
        ).fetchone() is not None
        my_review = db.execute(
            "SELECT * FROM reviews WHERE user_id = ? AND product_id = ?",
            (session["user_id"], product_id),
        ).fetchone()

    related = db.execute(
        "SELECT * FROM products WHERE category = ? AND id != ? ORDER BY id LIMIT 4",
        (product["category"], product_id),
    ).fetchall()

    return render_template(
        "product_detail.html",
        product=product,
        reviews=reviews,
        avg_rating=avg_rating,
        is_wished=is_wished,
        my_review=my_review,
        related=related,
    )


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@app.route("/product/<int:product_id>/review", methods=["POST"])
@login_required
def add_review(product_id):
    db = get_db()
    if db.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone() is None:
        flash("That product does not exist.", "error")
        return redirect(url_for("index"))

    try:
        rating = int(request.form.get("rating", 0))
    except ValueError:
        rating = 0
    comment = request.form.get("comment", "").strip()[:500]
    if rating < 1 or rating > 5:
        flash("Please choose a rating from 1 to 5 stars.", "error")
    else:
        db.execute(
            "INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, product_id) DO UPDATE SET rating = excluded.rating, "
            "comment = excluded.comment, created_at = datetime('now')",
            (session["user_id"], product_id, rating, comment),
        )
        db.commit()
        flash("Thanks! Your review has been saved.", "success")
    return redirect(url_for("product_detail", product_id=product_id) + "#reviews")


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------
@app.route("/wishlist")
@login_required
def wishlist():
    items = get_db().execute(
        "SELECT p.* FROM wishlist w JOIN products p ON p.id = w.product_id "
        "WHERE w.user_id = ? ORDER BY w.id DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("wishlist.html", items=items)


@app.route("/wishlist/toggle/<int:product_id>", methods=["POST"])
@login_required
def toggle_wishlist(product_id):
    db = get_db()
    if db.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone() is None:
        flash("That product does not exist.", "error")
        return redirect(url_for("index"))
    existing = db.execute(
        "SELECT id FROM wishlist WHERE user_id = ? AND product_id = ?",
        (session["user_id"], product_id),
    ).fetchone()
    if existing:
        db.execute("DELETE FROM wishlist WHERE id = ?", (existing["id"],))
        flash("Removed from your wishlist.", "success")
    else:
        db.execute(
            "INSERT INTO wishlist (user_id, product_id) VALUES (?, ?)",
            (session["user_id"], product_id),
        )
        flash("Saved to your wishlist.", "success")
    db.commit()
    return redirect(safe_next(request.form.get("back", "")))


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash("That product does not exist.", "error")
        return redirect(url_for("index"))
    if product["stock"] <= 0:
        flash(f"Sorry, {product['name']} is out of stock.", "error")
        return redirect(safe_next(request.form.get("back", "")))

    cart = session.get("cart", {})
    key = str(product_id)
    wanted = cart.get(key, 0) + read_quantity(request.form.get("quantity", 1))
    if wanted > product["stock"]:
        wanted = product["stock"]
        flash(f"Only {product['stock']} of {product['name']} available. Cart updated to the maximum.", "info")
    else:
        flash(f"Added {product['name']} to your cart.", "success")
    cart[key] = wanted
    session["cart"] = cart
    return redirect(safe_next(request.form.get("back", "")))


@app.route("/cart")
def view_cart():
    lines, total = cart_lines(get_db())
    return render_template("cart.html", items=lines, total=total)


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    db = get_db()
    cart = session.get("cart", {})
    key = str(product_id)
    action = request.form.get("action")
    if key in cart:
        product = db.execute("SELECT stock FROM products WHERE id = ?", (product_id,)).fetchone()
        if action == "increase":
            if product and cart[key] < product["stock"]:
                cart[key] += 1
            else:
                flash("You have reached the available stock for this item.", "info")
        elif action == "decrease":
            cart[key] -= 1
            if cart[key] <= 0:
                del cart[key]
        elif action == "remove":
            del cart[key]
    session["cart"] = cart
    return redirect(url_for("view_cart"))


# ---------------------------------------------------------------------------
# Checkout and orders
# ---------------------------------------------------------------------------
@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    db = get_db()
    lines, total = cart_lines(db)
    if not lines:
        flash("Your cart is empty.", "error")
        return redirect(url_for("index"))

    form = {"hostel_block": "", "room_no": "", "phone": "", "pay_mode": PAY_MODES[0]}
    if request.method == "POST":
        form = {
            "hostel_block": request.form.get("hostel_block", "").strip(),
            "room_no": request.form.get("room_no", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "pay_mode": request.form.get("pay_mode", PAY_MODES[0]),
        }
        digits = "".join(ch for ch in form["phone"] if ch.isdigit())
        if not form["hostel_block"] or not form["room_no"]:
            flash("Please enter your hostel/block and room number for delivery.", "error")
        elif len(digits) != 10:
            flash("Please enter a valid 10-digit phone number.", "error")
        elif form["pay_mode"] not in PAY_MODES:
            flash("Please choose a payment option.", "error")
        else:
            cur = db.execute(
                "INSERT INTO orders (user_id, total, status, hostel_block, room_no, phone, pay_mode) "
                "VALUES (?, ?, 'placed', ?, ?, ?, ?)",
                (session["user_id"], total, form["hostel_block"], form["room_no"], digits, form["pay_mode"]),
            )
            order_id = cur.lastrowid
            for line in lines:
                p = line["product"]
                db.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, price_each) VALUES (?, ?, ?, ?)",
                    (order_id, p["id"], line["quantity"], p["price"]),
                )
                db.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ?",
                    (line["quantity"], p["id"]),
                )
            db.commit()
            session["cart"] = {}
            return redirect(url_for("order_success", order_id=order_id))

    return render_template(
        "checkout.html", items=lines, total=total, form=form, pay_modes=PAY_MODES
    )


def load_order(db, order_id):
    order = db.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, session["user_id"])
    ).fetchone()
    if order is None:
        return None, []
    items = db.execute(
        "SELECT oi.*, p.name, p.image_file FROM order_items oi "
        "JOIN products p ON p.id = oi.product_id WHERE oi.order_id = ?",
        (order_id,),
    ).fetchall()
    return order, items


@app.route("/order/<int:order_id>/success")
@login_required
def order_success(order_id):
    order, items = load_order(get_db(), order_id)
    if order is None:
        return redirect(url_for("index"))
    return render_template("order_success.html", order=order, items=items)


@app.route("/orders")
@login_required
def my_orders():
    db = get_db()
    orders = db.execute(
        "SELECT o.*, (SELECT SUM(quantity) FROM order_items WHERE order_id = o.id) AS item_count "
        "FROM orders o WHERE o.user_id = ? ORDER BY o.id DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("orders.html", orders=orders)


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order, items = load_order(get_db(), order_id)
    if order is None:
        flash("Order not found.", "error")
        return redirect(url_for("my_orders"))
    return render_template("order_detail.html", order=order, items=items)


@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    db = get_db()
    order, items = load_order(db, order_id)
    if order is None:
        flash("Order not found.", "error")
    elif order["status"] != "placed":
        flash("Only orders that are still 'placed' can be cancelled.", "error")
    else:
        for item in items:
            db.execute(
                "UPDATE products SET stock = stock + ? WHERE id = ?",
                (item["quantity"], item["product_id"]),
            )
        db.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        db.commit()
        flash("Your order was cancelled and the items went back to stock.", "success")
    return redirect(url_for("order_detail", order_id=order_id))


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        if not name or not email or not password:
            flash("All fields are required.", "error")
        elif len(password) < 6:
            flash("Password should be at least 6 characters.", "error")
        elif db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            flash("An account with that email already exists.", "error")
        else:
            cur = db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            db.commit()
            session["user_id"] = cur.lastrowid
            session["user_name"] = name
            flash(f"Welcome to CampusCart, {name}!", "success")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    next_page = request.values.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            cart = session.get("cart", {})
            session.clear()
            session["cart"] = cart  # keep the items picked before logging in
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash(f"Welcome back, {user['name']}.", "success")
            return redirect(safe_next(next_page))
        flash("Incorrect email or password.", "error")
    return render_template("login.html", next_page=next_page)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
