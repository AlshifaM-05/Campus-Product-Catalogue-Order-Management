# CampusCart — Product Browsing and Order System

CodeAlpha Full Stack Development Internship — Task 1

A web app where students can browse campus essentials, save their favourites,
add items to a cart and place an order that is delivered to their hostel.

## Features
- Product pictures and a banner on the home page
- Category filter, search box and sorting (price, name, top rated)
- Product page with rating, reviews and "more in this category"
- Wishlist: tap the heart to save a product for later
- Star ratings and written reviews (one review per student, can be updated)
- Cart with quantity control that respects the available stock
- Sign up and log in (passwords are stored in a hashed form)
- Checkout with hostel, room number, phone and payment option
- Order history, order details and order cancellation (stock goes back)
- "Only a few left" warning for items that are running low

## Tech used
- Backend: Python, Flask
- Database: SQLite (built-in `sqlite3`, no ORM)
- Frontend: HTML, Jinja2 templates, plain CSS, SVG pictures

## How to run

```bash
cd CampusCart
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5001`. The database file `campuscart.db` is created
automatically on the first run with 12 sample products.

## Folder layout
```
CampusCart/
├── app.py
├── requirements.txt
├── static/
│   ├── css/style.css
│   └── img/
│       ├── hero.svg
│       └── products/        # one picture for each product
└── templates/
    ├── base.html
    ├── index.html           # product list, filter, sort
    ├── product_detail.html  # details, reviews, related items
    ├── wishlist.html
    ├── cart.html
    ├── checkout.html
    ├── order_success.html
    ├── orders.html
    ├── order_detail.html    # details and cancel button
    ├── login.html
    └── register.html
```

## Notes
- This is a demo project. No online payment is used; the amount is paid on delivery.
- `campuscart.db` is created when the app runs and is not part of the zip.
- To add your own picture for a product, put the file in `static/img/products/`
  and set the product's `image_file` name in `app.py`.
