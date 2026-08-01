import os
import re
import requests
import base64
import random
import smtplib
from datetime import datetime, timedelta
from urllib.parse import quote
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, session, jsonify, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ==================== 📂 PATH CONFIGURATION ====================
base_path = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_path, 'templates')
static_dir = os.path.join(base_path, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# ==================== 🔐 SECURITY & CACHE BUSTER ====================
app.secret_key = 'diu_marketplace_secure_key_2026'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  

# সর্বোচ্চ ৬ মেগাবাইট ফাইল সাইজ আপলোড লিমিট
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024

# --- 🚀 লিমিটার কনফিগারেশন ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20000 per day", "1000 per hour"],
    storage_uri="memory://"
)

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

@app.errorhandler(413)
def request_entity_too_large(error):
    flash('❌ Upload failed! Total image size cannot be larger than 6MB.', 'danger')
    return redirect(request.referrer or url_for('home'))

@app.errorhandler(429)
def ratelimit_handler(e):
    flash(f"⚠️ Action Blocked: {e.description}", "danger")
    return redirect(request.referrer or url_for('home'))

# ==================== 🌐 RENDER KEEP-ALIVE ROUTE ====================
@app.route('/ping')
def ping():
    return "Alive", 200

# ==================== 📱 PWA STATIC ROOT SYSTEM PATHS ====================
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(static_dir, 'manifest.json')

@app.route('/service-worker.js')
def serve_sw():
    return send_from_directory(static_dir, 'service-worker.js')

# ==================== 🔑 ONLINE IMGBB CONFIGURATION ====================
IMGBB_API_KEY = 'd12ec656c77d0cb3c10f66aa908d1627' 

# ==================== 📧 REAL GMAIL SMTP CONFIGURATION ====================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "diumarketplace@gmail.com"        
SENDER_PASSWORD = "zgguayxuxlghwkzq"

def send_otp_email(target_email, otp_code, purpose="Verification"):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email
        msg['Subject'] = f"🔑 DIU Marketplace - {purpose} OTP Code"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 500px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
                <h2 style="color: #007bff; text-align: center;">DIU Student Marketplace</h2>
                <p>Hello,</p>
                <p>Your OTP code for <strong>{purpose}</strong> is:</p>
                <div style="font-size: 24px; font-weight: bold; text-align: center; letter-spacing: 5px; background: #f4f4f4; padding: 10px; margin: 20px 0; border-radius: 5px; color: #333;">
                    {otp_code}
                </div>
                <p style="font-size: 12px; color: #777;">This code is valid for 5 minutes. Please do not share this OTP with anyone.</p>
                <hr style="border: 0; border-top: 1px solid #eee;">
                <p style="font-size: 11px; color: #aaa; text-align: center;">© 2026 DIU Marketplace. All Rights Reserved.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, target_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Email Sending Failed: {str(e)}")
        return False

# ==================== 🖥️ EXPLICIT NEON POSTGRESQL OPTIMIZED CONFIGURATION ====================
DB_CONFIG = {
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "npg_mgZadRT4IBK7",
    "host": "ep-aged-sound-aozt30iz-pooler.c-2.ap-southeast-1.aws.neon.tech",
    "port": 5432,
    "sslmode": "require"
}

def get_db():
    conn = psycopg2.connect(
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        sslmode=DB_CONFIG["sslmode"],
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )
    return conn

@app.before_request
def init_db():
    if getattr(app, '_db_inited', False):
        return
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                student_id VARCHAR(100),
                mobile VARCHAR(50),
                role VARCHAR(50),
                password VARCHAR(255) NOT NULL,
                ip_address VARCHAR(100) DEFAULT '127.0.0.1',
                is_banned INT DEFAULT 0,
                profile_pic VARCHAR(512) DEFAULT 'default_avatar.png'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS otp_verifications (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                otp_code VARCHAR(10) NOT NULL,
                purpose VARCHAR(50) NOT NULL,
                expiry_time TIMESTAMP NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                category VARCHAR(255) NOT NULL,
                price INT NOT NULL,
                offer_price INT DEFAULT 0,
                used_time VARCHAR(255),
                location VARCHAR(255),
                description TEXT,
                whatsapp VARCHAR(50),
                photo_url VARCHAR(512),
                seller_email VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT 'Pending',
                offer_text VARCHAR(255),
                free_delivery BOOLEAN DEFAULT FALSE
            )
        ''')

        cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS offer_price INT DEFAULT 0;")
        cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS offer_text VARCHAR(255);")
        cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS free_delivery BOOLEAN DEFAULT FALSE;")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_images (
                id SERIAL PRIMARY KEY,
                product_id INT NOT NULL,
                image_url VARCHAR(512) NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dynamic_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_announcements (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expiry_time TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                product_id INT,
                message TEXT NOT NULL,
                user_email VARCHAR(255) NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wishlist (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                product_id INT NOT NULL,
                UNIQUE(user_email, product_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                product_id INT NOT NULL,
                user_name VARCHAR(255) NOT NULL,
                user_email VARCHAR(255) NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                product_id INT NOT NULL,
                buyer_email VARCHAR(255) NOT NULL,
                seller_email VARCHAR(255) NOT NULL,
                buyer_name VARCHAR(255) NOT NULL,
                buyer_phone VARCHAR(50) NOT NULL,
                delivery_zone VARCHAR(50) NOT NULL,
                delivery_address TEXT NOT NULL,
                special_note TEXT,
                payment_method VARCHAR(50) NOT NULL,
                sender_number VARCHAR(50) NOT NULL,
                trx_id VARCHAR(100) NOT NULL,
                delivery_charge NUMERIC(10, 2) DEFAULT 0.0,
                order_status VARCHAR(50) DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                FOREIGN KEY (buyer_email) REFERENCES users (email) ON DELETE CASCADE,
                FOREIGN KEY (seller_email) REFERENCES users (email) ON DELETE CASCADE
            )
        ''')
        
        # নিশ্চিত করছি ডাটাবেজের কলাম ডিফোল্ট স্ট্যাটাস 'Pending' থাকবে
        cursor.execute("ALTER TABLE orders ALTER COLUMN order_status SET DEFAULT 'Pending';")
        
        conn.commit()

        cursor.execute("SELECT * FROM users WHERE email = 'admin@diu.edu.bd'")
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            hashed_admin_pwd = generate_password_hash("admin123")
            cursor.execute('''
                INSERT INTO users (email, name, student_id, mobile, role, password, ip_address, is_banned)
                VALUES ('admin@diu.edu.bd', 'System Admin', 'N/A', '01700000000', 'admin', %s, '127.0.0.1', 0)
            ''', (hashed_admin_pwd,))
            conn.commit()

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Database Initialization Error: {str(e)}")

    app._db_inited = True


# ==================== 📦 SAFE ORDER PLACEMENT ROUTE ====================

@app.route('/place-order/<int:product_id>', methods=['POST'])
def place_order(product_id):
    # 🔴 ১. লগইন না থাকলে সরাসরি আটকে দিয়ে লগইন পেজে পাঠাবে
    if 'user_email' not in session:
        flash('❌ Please login first to place an order!', 'danger')
        return redirect(url_for('login'))

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # প্রোডাক্ট এবং সেলারের ইনফরমেশন আনা
        cursor.execute("""
            SELECT p.*, u.mobile AS seller_mobile, u.name AS seller_name 
            FROM products p
            LEFT JOIN users u ON LOWER(p.seller_email) = LOWER(u.email)
            WHERE p.id = %s
        """, (product_id,))
        product = cursor.fetchone()

        if not product:
            cursor.close()
            conn.close()
            flash('❌ Product not found!', 'danger')
            return redirect(url_for('home'))

        # তথ্য নেওয়া
        delivery_zone = request.form.get('delivery_zone')
        delivery_charge = 0.0 if delivery_zone == 'inside_campus' else 49.0

        buyer_name = request.form.get('buyer_name')
        buyer_phone = request.form.get('buyer_phone')
        delivery_address = request.form.get('delivery_address')
        special_note = request.form.get('special_note')
        payment_method = request.form.get('payment_method')
        sender_number = request.form.get('sender_number')
        trx_id = request.form.get('trx_id')

        # 🎯 STRICT ORDER STATUS FORCE: নিশ্চিতভাবে 'Pending' স্ট্যাটাসে অর্ডার ইনসার্ট হবে
        initial_order_status = 'Pending'

        # অর্ডার ডাটাবেজে ডাটা ঢোকানো
        cursor.execute('''
            INSERT INTO orders (
                product_id, buyer_email, seller_email, buyer_name, buyer_phone,
                delivery_zone, delivery_address, special_note, payment_method,
                sender_number, trx_id, delivery_charge, order_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (
            product['id'], session['user_email'], product['seller_email'], buyer_name, buyer_phone,
            delivery_zone, delivery_address, special_note, payment_method,
            sender_number, trx_id, delivery_charge, initial_order_status
        ))

        new_order_id = cursor.fetchone()['id']

        # নোটিফিকেশন পাঠানো
        alert_msg = f"📦 New Order Received! Item: '{product['title']}' from {buyer_name}. Status: Pending"
        cursor.execute('INSERT INTO notifications (product_id, message, user_email) VALUES (%s, %s, %s)', 
                       (product['id'], alert_msg, product['seller_email']))

        conn.commit()
        cursor.close()
        conn.close()

        host_url = request.host_url.rstrip('/')
        manage_order_url = f"{host_url}/seller/orders"

        if product.get('seller_email'):
            subject = f"📦 New Order Request (#{new_order_id}) - {product['title']} - DIU Marketplace"
            
            email_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; background-color: #f4f6f9; padding: 20px; margin: 0;">
    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 25px; border: 1px solid #e0e0e0;">
        <h2 style="color: #0d6efd; margin-top: 0;">🎉 You Have Received a New Order Request!</h2>
        <p>Hello <b>{product.get('seller_name', 'Seller')}</b>,</p>
        <p>A buyer has placed an order for your item. Order status is currently <b><span style="color: #ffc107; background: #212529; padding: 3px 8px; border-radius: 4px;">Pending</span></b>. Please review and Approve/Confirm or Cancel the order from your dashboard.</p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        
        <h3 style="color: #333;">📦 Product Details</h3>
        <p><b>Product:</b> {product['title']}<br>
        <b>Product Price:</b> ৳{product['price']} (Cash on Delivery)</p>

        <h3 style="color: #333;">👤 Buyer & Delivery Information</h3>
        <p><b>Name:</b> {buyer_name}<br>
        <b>Phone:</b> <a href="tel:{buyer_phone}">{buyer_phone}</a><br>
        <b>Zone:</b> {delivery_zone.replace('_', ' ').title() if delivery_zone else 'N/A'}<br>
        <b>Drop Location:</b> {delivery_address}<br>
        <b>Special Note:</b> {special_note or 'None'}</p>

        <h3 style="color: #333;">💳 Advance Delivery Fee Details</h3>
        <p><b>Payment Method:</b> {payment_method.upper() if payment_method else 'N/A'}<br>
        <b>Sender Number:</b> {sender_number}<br>
        <b>TrxID:</b> <span style="background: #e9ecef; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{trx_id}</span><br>
        <b>Amount Paid:</b> ৳{delivery_charge}</p>

        <div style="margin-top: 30px; text-align: center;">
            <a href="{manage_order_url}" target="_blank" style="background-color: #198754; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; font-size: 16px;">
               ✅ Manage & Action Order
            </a>
        </div>
        <br>
        <p style="font-size: 12px; color: #777; text-align: center;">You can Approve/Confirm the order or mark it as Delivered once handed over to the buyer.</p>
    </div>
</body>
</html>"""

            try:
                msg = MIMEMultipart('alternative')
                msg['From'] = SENDER_EMAIL
                msg['To'] = product['seller_email']
                msg['Subject'] = subject
                msg.attach(MIMEText(email_html, 'html'))

                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, product['seller_email'], msg.as_string())
                server.quit()
            except Exception as e:
                print(f"⚠️ Order Mail Sending Error: {str(e)}")

        flash('🎉 Order placed successfully!', 'success')
        return redirect(url_for('order_success', order_id=new_order_id))

    except Exception as e:
        flash(f"Failed to place order: {str(e)}", "danger")
        return redirect(url_for('home'))


@app.route('/order-success/<int:order_id>')
def order_success(order_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT o.*, 
                   p.title as product_title, p.price as product_price, p.photo_url,
                   u.name as seller_name, u.mobile as seller_mobile, u.email as seller_email_addr
            FROM orders o
            JOIN products p ON o.product_id = p.id
            LEFT JOIN users u ON o.seller_email = u.email
            WHERE o.id = %s AND o.buyer_email = %s
        ''', (order_id, session['user_email']))
        
        order_raw = cursor.fetchone()
        cursor.close()
        conn.close()

        if not order_raw:
            flash("Order not found or unauthorized!", "danger")
            return redirect(url_for('home'))

        order_dict = dict(order_raw)
        
        order_dict['product'] = {
            'title': order_dict.get('product_title'),
            'price': order_dict.get('product_price'),
            'photo_url': order_dict.get('photo_url')
        }

        order_dict['seller'] = {
            'name': order_dict.get('seller_name'),
            'mobile': order_dict.get('seller_mobile'),
            'email': order_dict.get('seller_email_addr')
        }

        user_data = {
            'email': session.get('user_email'),
            'name': session.get('user_name'),
            'role': session.get('user_role')
        }

        return render_template('order-success.html', order=order_dict, user=user_data, current_user=user_data)
    except Exception as e:
        return f"Error loading order success page: {str(e)}"


# ==================== 🛠️ SELLER ORDERS ROUTE ====================

@app.route('/seller/orders')
def seller_orders():
    if 'user_email' not in session:
        flash("Please login to view your sales orders.", "danger")
        return redirect(url_for('login'))

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT o.*, p.title as product_title, p.price as product_price, p.photo_url 
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE LOWER(o.seller_email) = LOWER(%s) 
            ORDER BY o.created_at DESC
        ''', (session['user_email'],))
        
        raw_orders = cursor.fetchall()
        orders = []

        for row in raw_orders:
            order_dict = dict(row)
            order_dict['product'] = {
                'title': order_dict.get('product_title'),
                'price': order_dict.get('product_price'),
                'photo_url': order_dict.get('photo_url')
            }
            orders.append(order_dict)

        cursor.close()
        conn.close()

        user_data = {
            'email': session.get('user_email'),
            'name': session.get('user_name'),
            'role': session.get('user_role')
        }

        return render_template('seller-orders.html', orders=orders, user=user_data, current_user=user_data)
    except Exception as e:
        return f"Error loading seller orders: {str(e)}"


@app.route('/update-order-status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if 'user_email' not in session and not session.get('is_admin'):
        flash("Unauthorized action", "danger")
        return redirect(url_for('login'))

    status = request.form.get('status')
    if status not in ['Pending', 'Approved', 'Confirmed', 'Delivered', 'Cancelled', 'Rejected']:
        flash("Invalid status update!", "danger")
        return redirect(url_for('seller_orders'))

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT o.*, p.title as product_title FROM orders o JOIN products p ON o.product_id = p.id WHERE o.id = %s", (order_id,))
        order = cursor.fetchone()

        if not order:
            cursor.close()
            conn.close()
            flash('Order not found', 'danger')
            return redirect(url_for('home'))

        # Check if caller is seller or admin
        if not session.get('is_admin') and order['seller_email'].lower() != session['user_email'].lower():
            cursor.close()
            conn.close()
            flash('Unauthorized action', 'danger')
            return redirect(url_for('home'))

        cursor.execute("UPDATE orders SET order_status = %s WHERE id = %s", (status, order_id))
        
        alert_msg = f"🚚 Update on Order #{order_id}: Your order status for '{order['product_title']}' has been updated to '{status}' by the seller."
        cursor.execute('INSERT INTO notifications (product_id, message, user_email) VALUES (%s, %s, %s)', 
                       (order['product_id'], alert_msg, order['buyer_email']))

        conn.commit()
        cursor.close()
        conn.close()

        try:
            buyer_email = order['buyer_email']
            subject = f"🔔 Order #{order_id} Update: Status changed to {status}"
            
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 20px;">
                <div style="max-width: 550px; margin: 0 auto; background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #ddd;">
                    <h2 style="color: #0d6efd;">DIU Smart Marketplace</h2>
                    <p>Hello <b>{order['buyer_name']}</b>,</p>
                    <p>The status of your order has been updated by the seller.</p>
                    <hr style="border: 0; border-top: 1px solid #eee;">
                    <p><b>Order ID:</b> #{order_id}</p>
                    <p><b>Product:</b> {order['product_title']}</p>
                    <p><b>New Status:</b> <span style="color: #198754; font-weight: bold; font-size: 16px;">{status}</span></p>
                    <hr style="border: 0; border-top: 1px solid #eee;">
                    <p style="font-size: 13px; color: #6c757d;">Thank you for shopping on DIU Smart Marketplace!</p>
                </div>
            </body>
            </html>
            """
            
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = buyer_email
            msg['Subject'] = subject
            msg.attach(MIMEText(email_body, 'html'))

            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, buyer_email, msg.as_string())
            server.quit()
        except Exception as mail_err:
            print(f"⚠️ Buyer notification email failed: {str(mail_err)}")

        flash(f'Order #{order_id} status updated to {status}. Notification sent to buyer!', 'success')
    except Exception as e:
        flash(f"Error updating order status: {str(e)}", "danger")

    return redirect(request.referrer or url_for('seller_orders'))


# ==================== 🔔 NOTIFICATION API ROUTES ====================

@app.route('/api/notifications')
def get_notifications():
    if 'user_email' not in session:
        return jsonify([])
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT * FROM notifications 
            WHERE LOWER(user_email) = LOWER(%s) AND is_read = FALSE 
            ORDER BY id DESC
        ''', (session['user_email'],))
        notifs = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify([dict(n) for n in notifs])
    except Exception:
        return jsonify([])

@app.route('/click-notification/<int:notif_id>/<int:product_id>')
def click_notification(notif_id, product_id):
    if 'user_email' not in session:
        return jsonify({'status': 'unauthorized'}), 401
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE notifications SET is_read = TRUE WHERE id = %s', (notif_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'product_id': product_id})
    except Exception:
        return jsonify({'status': 'error'}), 500


# ==================== ❤️ WISHLIST TOGGLE SYSTEM ====================

@app.route('/toggle-wishlist', methods=['POST'])
def toggle_wishlist():
    if 'user_email' not in session:
        return jsonify({'status': 'unauthorized', 'message': 'Please login first to add items to your wishlist!'}), 401
        
    data = request.get_json() or {}
    product_id = data.get('product_id')
    
    if not product_id:
        return jsonify({'status': 'error', 'message': 'Missing product ID'}), 400
        
    user_email = session['user_email']
    
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT id FROM wishlist WHERE LOWER(user_email) = LOWER(%s) AND product_id = %s', (user_email, product_id))
        item = cursor.fetchone()
        
        if item:
            cursor.execute('DELETE FROM wishlist WHERE LOWER(user_email) = LOWER(%s) AND product_id = %s', (user_email, product_id))
            status = 'removed'
        else:
            cursor.execute('INSERT INTO wishlist (user_email, product_id) VALUES (%s, %s)', (user_email, product_id))
            status = 'added'
            
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'action': status})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== USER ROUTES ====================

@app.route('/')
def main_index():
    return redirect(url_for('home'))

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    if request.method == 'POST':
        name = request.form.get('name')
        student_id = request.form.get('student_id')
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('mobile')
        password = request.form.get('password')

        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if not user_ip or user_ip == '::1' or user_ip == '127.0.0.1':
            user_ip = '127.0.0.1'

        if not re.match(r"^[a-zA-Z0-9._%+-]+@diu\.edu\.bd$", email) and email != 'admin@diu.edu.bd':
            flash("Invalid email! Only @diu.edu.bd emails are allowed.", "danger")
            return redirect(url_for('register', role=role))

        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(%s)', (email,))
            user = cursor.fetchone()

            if user:
                flash("This email is already registered.", "danger")
                cursor.close()
                conn.close()
                return redirect(url_for('register', role=role))

            session['reg_data'] = {
                'name': name, 'student_id': student_id, 'email': email,
                'mobile': mobile, 'password': generate_password_hash(password), 'role': role, 'ip_address': user_ip
            }

            otp = str(random.randint(100000, 999999))
            expiry = datetime.now() + timedelta(minutes=5)

            cursor.execute('INSERT INTO otp_verifications (email, otp_code, purpose, expiry_time) VALUES (%s, %s, \'Registration\', %s)', 
                           (email, otp, expiry))
            conn.commit()
            cursor.close()
            conn.close()

            if send_otp_email(email, otp, "Registration"):
                flash(f"📥 A verification OTP has been sent to {email}. Verify to complete registration.", "success")
                return redirect(url_for('verify_otp', purpose='Registration'))
            else:
                flash("❌ Failed to send OTP. Please check your network or SMTP credentials.", "danger")
                return redirect(url_for('register', role=role))

        except Exception as e:
            flash(f"Database error: {str(e)}", "danger")
            return redirect(url_for('register', role=role))

    return render_template('register.html', role=role)


# ==================== FORGOT PASSWORD & OTP ====================

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(%s)', (email,))
            user = cursor.fetchone()
            
            if not user:
                flash("No account found with this official email address.", "danger")
                cursor.close()
                conn.close()
                return redirect(url_for('forgot_password'))
                
            otp = str(random.randint(100000, 999999))
            expiry = datetime.now() + timedelta(minutes=5)
            
            cursor.execute('INSERT INTO otp_verifications (email, otp_code, purpose, expiry_time) VALUES (%s, %s, \'Reset\', %s)', 
                           (email, otp, expiry))
            conn.commit()
            cursor.close()
            conn.close()
            
            session['reset_email'] = email
            
            if send_otp_email(email, otp, "Password Reset"):
                flash("📥 An OTP has been sent to your email.", "success")
                return redirect(url_for('verify_otp', purpose='Reset'))
            else:
                flash("❌ Failed to send OTP email.", "danger")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            
    return render_template('forgot_password.html')


@app.route('/resend-otp/<purpose>')
@limiter.limit("5 per minute")
def resend_otp(purpose):
    email = session.get('reg_data', {}).get('email') if purpose == 'Registration' else session.get('reset_email')
    
    if not email:
        flash("Session expired! Please start the process again.", "danger")
        return redirect(url_for('register', role='buyer') if purpose == 'Registration' else url_for('forgot_password'))

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM otp_verifications WHERE LOWER(email) = LOWER(%s) AND purpose = %s', (email, purpose))
        
        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=5)
        
        cursor.execute('INSERT INTO otp_verifications (email, otp_code, purpose, expiry_time) VALUES (%s, %s, %s, %s)', 
                       (email, otp, purpose, expiry))
        conn.commit()
        cursor.close()
        conn.close()
        
        email_purpose = "Registration" if purpose == 'Registration' else "Password Reset"
        if send_otp_email(email, otp, email_purpose):
            flash("📥 A new OTP code has been sent to your email!", "success")
        else:
            flash("❌ Failed to resend OTP email.", "danger")
            
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        
    return redirect(url_for('verify_otp', purpose=purpose))


@app.route('/verify-otp/<purpose>', methods=['GET', 'POST'])
def verify_otp(purpose):
    if request.method == 'POST':
        input_otp = request.form.get('otp')
        new_pass = request.form.get('new_password')
        
        email = session.get('reg_data', {}).get('email') if purpose == 'Registration' else session.get('reset_email')
        
        if not email:
            flash("Session expired or invalid.", "danger")
            return redirect(url_for('home'))

        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('''
                SELECT * FROM otp_verifications 
                WHERE LOWER(email) = LOWER(%s) AND otp_code = %s AND purpose = %s AND expiry_time > %s
                ORDER BY id DESC LIMIT 1
            ''', (email, input_otp, purpose, datetime.now()))
            
            valid_otp = cursor.fetchone()
            
            if valid_otp:
                cursor.execute('DELETE FROM otp_verifications WHERE LOWER(email) = LOWER(%s)', (email,))
                
                if purpose == 'Registration':
                    reg = session.get('reg_data')
                    cursor.execute('''
                        INSERT INTO users (email, name, student_id, mobile, role, password, ip_address, is_banned) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                    ''', (reg['email'], reg['name'], reg['student_id'], reg['mobile'], reg['role'], reg['password'], reg['ip_address']))
                    conn.commit()
                    
                    session.pop('reg_data', None)
                    flash("Verification successful! Account is active.", "success")
                    return redirect(url_for('login'))
                    
                elif purpose == 'Reset':
                    if not new_pass:
                        flash("Please provide a new password.", "danger")
                        return redirect(url_for('verify_otp', purpose='Reset'))
                        
                    hashed_pwd = generate_password_hash(new_pass)
                    cursor.execute('UPDATE users SET password = %s WHERE LOWER(email) = LOWER(%s)', (hashed_pwd, email))
                    conn.commit()
                    
                    session.pop('reset_email', None)
                    flash("✅ Password updated successfully!", "success")
                    return redirect(url_for('login'))
            else:
                flash("❌ Invalid or Expired OTP Code!", "danger")
                
            cursor.close()
            conn.close()
        except Exception as e:
            flash(f"Verification Error: {str(e)}", "danger")

    return render_template('verify_otp.html', purpose=purpose)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_email' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(%s)', (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and check_password_hash(user['password'], password):
                if user['is_banned'] == 1:
                    flash("❌ Your account has been suspended.", "danger")
                    return redirect(url_for('login'))

                session.clear()
                session['user_email'] = user['email']
                session['user_name'] = user['name']
                session['user_role'] = user['role']
                session['user_mobile'] = user['mobile']
                session['user_student_id'] = user['student_id']
                
                if user['role'] == 'admin':
                    session['is_admin'] = True
                    return redirect(url_for('view_registered_users')) 

                session.permanent = True
                return redirect(url_for('home'))
            else:
                flash("Invalid email or password!", "danger")
        except Exception as e:
            flash(f"Database error: {str(e)}", "danger")

    return render_template('login.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_email' in session or session.get('is_admin'):
        user_data = {
            'email': session.get('user_email', 'admin@diu.edu.bd'),
            'name': session.get('user_name', 'System Admin'),
            'role': session.get('user_role', 'admin'),
            'mobile': session.get('user_mobile', 'N/A'),
            'student_id': session.get('user_student_id', 'N/A')
        }
    else:
        user_data = None
    
    if request.method == 'POST':
        search_query = request.form.get('search', '').lower()
        category_filter = request.form.get('category', '')
    else:
        search_query = request.args.get('search', '').lower()
        category_filter = request.args.get('category', '')

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT p.*, u.name AS seller_name, u.mobile AS seller_mobile 
            FROM products p
            LEFT JOIN users u ON LOWER(p.seller_email) = LOWER(u.email)
            WHERE p.status IN ('Available', 'Sold Out')
        """
        params = []

        if search_query:
            query += " AND (LOWER(p.title) LIKE %s OR LOWER(p.description) LIKE %s)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])
        if category_filter:
            query += " AND p.category = %s"
            params.append(category_filter)

        query += " ORDER BY p.id DESC"
        cursor.execute(query, params)
        products_list = cursor.fetchall()

        final_products = []
        for p in products_list:
            p_dict = dict(p)
            
            cursor.execute('SELECT * FROM comments WHERE product_id = %s ORDER BY id ASC', (p['id'],))
            p_dict['comments'] = [dict(c) for c in cursor.fetchall()]

            if user_data:
                cursor.execute('SELECT * FROM wishlist WHERE LOWER(user_email) = LOWER(%s) AND product_id = %s', (user_data['email'], p['id']))
                fav = cursor.fetchone()
                p_dict['is_fav'] = True if fav else False
            else:
                p_dict['is_fav'] = False

            cursor.execute('SELECT image_url FROM product_images WHERE product_id = %s', (p['id'],))
            p_dict['additional_photos'] = [row['image_url'] for row in cursor.fetchall()]

            final_products.append(p_dict)

        current_time = datetime.now()
        cursor.execute("""
            SELECT text FROM system_announcements 
            WHERE expiry_time > %s OR expiry_time IS NULL 
            ORDER BY id DESC LIMIT 1
        """, (current_time,))
        latest_announcement = cursor.fetchone()
        announcement_text = latest_announcement['text'] if latest_announcement else None

        cursor.execute("SELECT name FROM dynamic_categories ORDER BY name ASC")
        live_categories = [row['name'] for row in cursor.fetchall()]

        cursor.close()
        conn.close()
        return render_template('index.html', user=user_data, current_user=user_data, products=final_products, announcement=announcement_text, live_categories=live_categories, selected_category=category_filter)
    except Exception as e:
        return f"<h1>Database Error inside Home Feed</h1><p>{str(e)}</p>"


# ==================== 🛍️ PRODUCT DETAILS ROUTES ====================

@app.route('/product-details')
def product_details_query():
    product_id = request.args.get('id')
    if not product_id:
        flash("Product ID missing!", "danger")
        return redirect(url_for('home'))
    return redirect(url_for('product_details_path', product_id=product_id))

@app.route('/product/<int:product_id>')
def product_details_path(product_id):
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT p.*, u.name AS seller_name, u.mobile AS seller_mobile
            FROM products p
            LEFT JOIN users u ON LOWER(p.seller_email) = LOWER(u.email)
            WHERE p.id = %s
        ''', (product_id,))
        product = cursor.fetchone()
        
        if not product:
            cursor.close()
            conn.close()
            flash("Product not found!", "danger")
            return redirect(url_for('home'))
            
        product_dict = dict(product)
        
        cursor.execute('SELECT image_url FROM product_images WHERE product_id = %s', (product_id,))
        product_dict['additional_photos'] = [row['image_url'] for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM comments WHERE product_id = %s ORDER BY id ASC', (product_id,))
        product_dict['comments'] = [dict(c) for c in cursor.fetchall()]
        
        if 'user_email' in session:
            cursor.execute('SELECT * FROM wishlist WHERE LOWER(user_email) = LOWER(%s) AND product_id = %s', (session['user_email'], product_id))
            product_dict['is_fav'] = True if cursor.fetchone() else False
        else:
            product_dict['is_fav'] = False
            
        cursor.close()
        conn.close()
        
        user_data = None
        if 'user_email' in session or session.get('is_admin'):
            user_data = {
                'email': session.get('user_email', 'admin@diu.edu.bd'),
                'name': session.get('user_name', 'System Admin'),
                'role': session.get('user_role', 'admin')
            }
            
        return render_template('product-details.html', product=product_dict, user=user_data, current_user=user_data)
    except Exception as e:
        return f"<h1>Error loading product details</h1><p>{str(e)}</p>"


# ==================== 👤 USER PROFILE ROUTE ====================

@app.route('/user/profile/<email>')
def user_profile(email):
    if 'user_email' not in session and not session.get('is_admin'):
        return redirect(url_for('login'))

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(%s)', (email,))
        profile_user = cursor.fetchone()

        if profile_user:
            profile_user_dict = dict(profile_user)
            
            cursor.execute('''
                SELECT p.*, u.name AS seller_name 
                FROM products p 
                JOIN users u ON LOWER(p.seller_email) = LOWER(u.email) 
                WHERE LOWER(p.seller_email) = LOWER(%s) 
                ORDER BY p.id DESC
            ''', (email,))
            products_list = cursor.fetchall()
            
            products = []
            if products_list:
                for p in products_list:
                    p_dict = dict(p)
                    cursor.execute('SELECT image_url FROM product_images WHERE product_id = %s', (p['id'],))
                    p_dict['additional_photos'] = [row['image_url'] for row in cursor.fetchall()]
                    products.append(p_dict)

            logged_in_user = {
                'email': session.get('user_email'),
                'name': session.get('user_name'),
                'role': session.get('user_role'),
                'is_admin': session.get('is_admin', False)
            }

            cursor.close()
            conn.close()
            
            template_name = 'user_profile.html' if os.path.exists(os.path.join(template_dir, 'user_profile.html')) else 'profile.html'
            
            return render_template(
                template_name, 
                profile_user=profile_user_dict, 
                user=logged_in_user, 
                current_user=logged_in_user, 
                products=products
            )

        cursor.close()
        conn.close()
        flash("User not found!", "danger")
        return redirect(url_for('home'))
    except Exception as e:
        return f"Error loading profile: {str(e)}"


# ==================== 📸 IMGBB PROFILE & PRODUCT UPLOADER ====================

@app.route('/update_profile_pic', methods=['POST'])
def update_profile_pic():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    if 'profile_pic' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('user_profile', email=session['user_email']))
    
    file = request.files['profile_pic']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('user_profile', email=session['user_email']))
    
    if file:
        try:
            url = "https://api.imgbb.com/1/upload"
            payload = {"key": IMGBB_API_KEY}
            files = {"image": (file.filename, file.read(), file.mimetype)}
            
            r = requests.post(url, data=payload, files=files)
            res_data = r.json()
            
            if r.status_code == 200 and res_data.get('success'):
                imgbb_url = res_data['data']['url']
                
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET profile_pic = %s WHERE LOWER(email) = LOWER(%s)', (imgbb_url, session['user_email']))
                conn.commit()
                cursor.close()
                conn.close()
                
                flash('Profile picture updated successfully via ImgBB!', 'success')
            else:
                error_msg = res_data.get('error', {}).get('message', 'Unknown error')
                flash(f'ImgBB Upload Failed: {error_msg}', 'danger')
        except Exception as e:
            flash(f'Error uploading to ImgBB: {str(e)}', 'danger')
            
    return redirect(url_for('user_profile', email=session['user_email']))


@app.route('/delete_profile_pic', methods=['POST'])
def delete_profile_pic():
    if 'user_email' not in session:
        return redirect(url_for('login'))
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET profile_pic = 'default_avatar.png' WHERE LOWER(email) = LOWER(%s)", (session['user_email'],))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Profile picture removed successfully!', 'success')
    except Exception as e:
        flash(f'Error removing picture: {str(e)}', 'danger')
        
    return redirect(url_for('user_profile', email=session['user_email']))


@app.route('/add-product', methods=['GET', 'POST'])
def add_product():
    if 'user_email' not in session:
        flash("Please login first to list products!", "danger")
        return redirect(url_for('login'))
        
    if session.get('user_role') != 'seller':
        flash("Only sellers can list products!", "danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        price_raw = request.form.get('price', '0')
        offer_price_raw = request.form.get('offer_price', '0')
        used_time = request.form.get('used_time')
        location = request.form.get('location')
        description = request.form.get('description')
        whatsapp = request.form.get('whatsapp')

        offer_text = request.form.get('offer_text', '').strip()
        free_delivery = True if request.form.get('free_delivery') in ['true', 'on', '1'] else False

        try:
            price = int(price_raw)
        except ValueError:
            price = 0

        try:
            offer_price = int(offer_price_raw) if offer_price_raw else 0
        except ValueError:
            offer_price = 0

        file = request.files.get('product_photo')
        photo_url = "https://placehold.co/600x400?text=No+Image"

        if file and file.filename != '':
            try:
                img_stream = file.read()
                base64_image = base64.b64encode(img_stream).decode('utf-8')
                payload = {'key': IMGBB_API_KEY, 'image': base64_image}
                r = requests.post('https://api.imgbb.com/1/upload', data=payload)
                res_data = r.json()
                if res_data.get('success'):
                    photo_url = res_data['data']['url']
            except Exception as e:
                flash(f"Main Image Upload Error: {str(e)}", "danger")

        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute('''
                INSERT INTO products (title, category, price, offer_price, used_time, location, description, whatsapp, photo_url, seller_email, status, offer_text, free_delivery)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending', %s, %s) RETURNING id
            ''', (title, category, price, offer_price, used_time, location, description, whatsapp, photo_url, session['user_email'], offer_text, free_delivery))
            
            new_product_id = cursor.fetchone()['id']
            conn.commit()

            additional_files = request.files.getlist('additional_photos')
            for add_file in additional_files:
                if add_file and add_file.filename != '':
                    try:
                        add_img_stream = add_file.read()
                        add_base64 = base64.b64encode(add_img_stream).decode('utf-8')
                        add_payload = {'key': IMGBB_API_KEY, 'image': add_base64}
                        add_response = requests.post('https://api.imgbb.com/1/upload', data=add_payload)
                        add_res_data = add_response.json()
                        
                        if add_response.status_code == 200 and add_res_data.get('success'):
                            add_photo_url = add_res_data['data']['url']
                            cursor.execute('''
                                INSERT INTO product_images (product_id, image_url) VALUES (%s, %s)
                            ''', (new_product_id, add_photo_url))
                    except Exception as e:
                        print(f"⚠️ Secondary Image Upload Error: {str(e)}")

            conn.commit()
            cursor.close()
            conn.close()
            flash("⏳ Product submitted! It will be live once verified by Admin.", "info")
            return redirect(url_for('home'))
        except Exception as e:
            flash(f"Failed to publish product: {str(e)}", "danger")

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT name FROM dynamic_categories ORDER BY name ASC")
        live_categories = [row['name'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
    except Exception:
        live_categories = []

    return render_template('add_product.html', live_categories=live_categories)

# ==================== 🔄 SELLER PRODUCT MANAGEMENT ====================

@app.route('/mark-sold/<int:product_id>')
def mark_sold(product_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET status = 'Sold Out' WHERE id = %s AND LOWER(seller_email) = LOWER(%s)", (product_id, session['user_email']))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Product marked as Sold Out!", "success")
    except Exception:
        pass
    return redirect(url_for('user_profile', email=session['user_email']))

@app.route('/mark-available/<int:product_id>')
def mark_available(product_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET status = 'Available' WHERE id = %s AND LOWER(seller_email) = LOWER(%s)", (product_id, session['user_email']))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Product marked as Available again!", "success")
    except Exception:
        pass
    return redirect(url_for('user_profile', email=session['user_email']))

@app.route('/edit-product/<int:product_id>', methods=['GET', 'POST'])
@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'user_email' not in session and not session.get('is_admin'):
        flash("Please login to edit your product.", "danger")
        return redirect(url_for('login'))
        
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        
        if not product or (product['seller_email'].lower() != session.get('user_email', '').lower() and not session.get('is_admin')):
            cursor.close()
            conn.close()
            flash("Unauthorized access or product not found!", "danger")
            return redirect(url_for('home'))
            
        if request.method == 'POST':
            title = request.form.get('title')
            category = request.form.get('category') or product['category']
            price_raw = request.form.get('price', product['price'])
            offer_price_raw = request.form.get('offer_price', '0')
            used_time = request.form.get('used_time')
            location = request.form.get('location')
            description = request.form.get('description')
            whatsapp = request.form.get('whatsapp')
            offer_text = request.form.get('offer_text', '').strip()
            free_delivery = True if request.form.get('free_delivery') in ['true', 'on', '1'] else False
            
            try:
                price = int(price_raw)
            except ValueError:
                price = product['price']

            try:
                offer_price = int(offer_price_raw) if offer_price_raw else 0
            except ValueError:
                offer_price = 0

            photo_url = product['photo_url']
            file = request.files.get('product_photo')
            if file and file.filename != '':
                try:
                    img_stream = file.read()
                    base64_image = base64.b64encode(img_stream).decode('utf-8')
                    payload = {'key': IMGBB_API_KEY, 'image': base64_image}
                    r = requests.post('https://api.imgbb.com/1/upload', data=payload)
                    res_data = r.json()
                    if res_data.get('success'):
                        photo_url = res_data['data']['url']
                except Exception as e:
                    print(f"Update Main Image Error: {str(e)}")

            cursor.execute('''
                UPDATE products 
                SET title=%s, category=%s, price=%s, offer_price=%s, used_time=%s, location=%s, description=%s, whatsapp=%s, photo_url=%s, status='Pending', offer_text=%s, free_delivery=%s
                WHERE id=%s
            ''', (title, category, price, offer_price, used_time, location, description, whatsapp, photo_url, offer_text, free_delivery, product_id))
            
            additional_files = request.files.getlist('additional_photos')
            for add_file in additional_files:
                if add_file and add_file.filename != '':
                    try:
                        add_img_stream = add_file.read()
                        add_base64 = base64.b64encode(add_img_stream).decode('utf-8')
                        add_payload = {'key': IMGBB_API_KEY, 'image': add_base64}
                        add_response = requests.post('https://api.imgbb.com/1/upload', data=add_payload)
                        add_res_data = add_response.json()
                        
                        if add_response.status_code == 200 and add_res_data.get('success'):
                            add_photo_url = add_res_data['data']['url']
                            cursor.execute('''
                                INSERT INTO product_images (product_id, image_url) VALUES (%s, %s)
                            ''', (product_id, add_photo_url))
                    except Exception as e:
                        print(f"⚠️ Secondary Image Upload Error: {str(e)}")

            conn.commit()
            cursor.close()
            conn.close()
            
            flash("✅ Product updated! It was submitted for admin re-approval.", "success")
            return redirect(url_for('user_profile', email=session['user_email']))
            
        cursor.execute("SELECT name FROM dynamic_categories ORDER BY name ASC")
        live_categories = [row['name'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        
        return render_template('edit_product.html', product=dict(product), live_categories=live_categories)
    except Exception as e:
        flash(f"Error editing product: {str(e)}", "danger")
        return redirect(url_for('home'))

@app.route('/delete-product/<int:product_id>', methods=['GET', 'POST'])
def delete_product(product_id):
    if 'user_email' not in session and not session.get('is_admin'):
        flash("Please login first!", "danger")
        return redirect(url_for('login'))
        
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT seller_email FROM products WHERE id = %s", (product_id,))
        prod = cursor.fetchone()
        
        if not prod:
            cursor.close()
            conn.close()
            flash("Product not found!", "danger")
            return redirect(url_for('home'))

        if prod['seller_email'].lower() != session.get('user_email', '').lower() and not session.get('is_admin'):
            cursor.close()
            conn.close()
            flash("Unauthorized action!", "danger")
            return redirect(url_for('home'))

        cursor.execute("DELETE FROM orders WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM wishlist WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM comments WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM product_images WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM notifications WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("🗑️ Product deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting product: {str(e)}", "danger")
        
    return redirect(request.referrer or url_for('home'))


# ==================== BUYER INTERACTION ====================

@app.route('/connect/<int:product_id>')
def connect_buyer(product_id):
    if 'user_email' not in session:
        flash("Please login first to contact the seller!", "danger")
        return redirect(url_for('login'))
        
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
        product_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if product_data:
            raw_number = str(product_data['whatsapp']).strip().replace("+", "").replace(" ", "").replace("-", "")
            
            if raw_number.startswith('01'):
                whatsapp_number = "88" + raw_number
            elif raw_number.startswith('8801'):
                whatsapp_number = raw_number
            else:
                whatsapp_number = raw_number  
                
            msg = f"Hello! I am interested in your item '{product_data['title']}' listed on DIU Marketplace."
            encoded_msg = quote(msg)  
            return redirect(f"https://api.whatsapp.com/send?phone={whatsapp_number}&text={encoded_msg}")
    except Exception as e:
        print(f"⚠️ WhatsApp Route Error: {str(e)}")
        
    return redirect(url_for('home'))

@app.route('/toggle-wishlist-fallback/<int:product_id>')
def toggle_wishlist_fallback(product_id):
    if 'user_email' not in session:
        flash("Please login first to manage your wishlist!", "danger")
        return redirect(url_for('login'))
    user_email = session['user_email']
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM wishlist WHERE LOWER(user_email) = LOWER(%s) AND product_id = %s', (user_email, product_id))
        fav = cursor.fetchone()
        if fav:
            cursor.execute('DELETE FROM wishlist WHERE LOWER(user_email) = LOWER(%s) AND product_id = %s', (user_email, product_id))
        else:
            cursor.execute('INSERT INTO wishlist (user_email, product_id) VALUES (%s, %s)', (user_email, product_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Wishlist Toggle Error: {str(e)}")
    return redirect(request.referrer or url_for('home'))

@app.route('/my-wishlist')
def my_wishlist():
    if 'user_email' not in session:
        flash("Please login first to view your wishlist!", "danger")
        return redirect(url_for('login'))
    user_data = {
        'email': session.get('user_email'),
        'name': session.get('user_name'),
        'role': session.get('user_role')
    }
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT p.*, u.name AS seller_name FROM products p 
            LEFT JOIN users u ON LOWER(p.seller_email) = LOWER(u.email)
            JOIN wishlist w ON p.id = w.product_id 
            WHERE LOWER(w.user_email) = LOWER(%s) ORDER BY w.id DESC
        ''', (user_data['email'],))
        products_list = cursor.fetchall()
        final_products = []
        for p in products_list:
            p_dict = dict(p)
            cursor.execute('SELECT * FROM comments WHERE product_id = %s ORDER BY id ASC', (p['id'],))
            p_dict['comments'] = [dict(c) for c in cursor.fetchall()]
            p_dict['is_fav'] = True

            cursor.execute('SELECT image_url FROM product_images WHERE product_id = %s', (p['id'],))
            p_dict['additional_photos'] = [row['image_url'] for row in cursor.fetchall()]

            final_products.append(p_dict)
        cursor.close()
        conn.close()
        return render_template('index.html', user=user_data, current_user=user_data, products=final_products, is_wishlist_page=True, live_categories=[])
    except Exception as e:
        print(f"⚠️ Wishlist Page Error: {str(e)}")
        return redirect(url_for('home'))

@app.route('/add-comment/<int:product_id>', methods=['POST'])
@limiter.limit("10 per minute")
def add_comment(product_id):
    if 'user_email' not in session and not session.get('is_admin'):
        flash("Please login first to ask questions or comment!", "danger")
        return redirect(url_for('login'))
        
    comment_text = request.form.get('comment_text')
    if comment_text and comment_text.strip():
        try:
            if session.get('is_admin'):
                user_name = "System Admin"
                user_email = "admin@diu.edu.bd"
            else:
                user_name = session['user_name']
                user_email = session['user_email']

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO comments (product_id, user_name, user_email, text) VALUES (%s, %s, %s, %s)',
                           (product_id, user_name, user_email, comment_text.strip()))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Comment Thread Error: {str(e)}")
            
    if session.get('is_admin'):
        return redirect(url_for('view_registered_users'))
        
    return redirect(url_for('home', _anchor=f"product-{product_id}"))

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        password_input = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        user_email = session['user_email']
        
        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(%s)', (user_email,))
            user = cursor.fetchone()
            if not check_password_hash(user['password'], current_password):
                flash("Current password is incorrect!", "danger")
                cursor.close()
                conn.close()
                return redirect(url_for('change_password'))
            if password_input != confirm_password:
                flash("New passwords do not match!", "danger")
                cursor.close()
                conn.close()
                return redirect(url_for('change_password'))
            hashed_password = generate_password_hash(password_input)
            cursor.execute('UPDATE users SET password = %s WHERE LOWER(email) = LOWER(%s)', (hashed_password, user_email))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Password updated successfully!", "success")
            return redirect(url_for('home'))
        except Exception as e:
            flash(f"Database error: {str(e)}", "danger")
            return redirect(url_for('change_password'))
            
    return render_template('change_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ==================== 🛠️ ADMIN PANEL ====================

@app.route('/diu-secret-gateway-2026', methods=['GET', 'POST'])
def admin_login():
    if 'is_admin' in session:
        return redirect(url_for('view_registered_users'))

    if request.method == 'POST':
        admin_email = request.form.get('email', '').strip().lower()
        admin_password = request.form.get('password')
        
        if admin_email == "admin@diu.edu.bd":
            try:
                conn = get_db()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(%s)', (admin_email,))
                user = cursor.fetchone()
                cursor.close()
                conn.close()

                if user and check_password_hash(user['password'], admin_password):
                    session.clear() 
                    session['is_admin'] = True
                    session['user_email'] = user['email']
                    session['user_name'] = user['name']
                    session['user_role'] = "admin"
                    return redirect(url_for('view_registered_users'))
            except Exception as e:
                flash(f"Database error: {str(e)}", "danger")
                
        flash("Access Denied! Incorrect Admin Credentials.", "danger")
    return render_template('admin_login.html')

@app.route('/admin/users')
def view_registered_users():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'seller'")
        total_sellers = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'buyer'")
        total_buyers = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM products")
        total_products = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM products WHERE status = 'Pending'")
        pending_products_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM orders")
        total_orders = cursor.fetchone()['count']

        stats = {
            "total_users": total_users,
            "total_sellers": total_sellers,
            "total_buyers": total_buyers,
            "total_products": total_products,
            "pending_products_count": pending_products_count,
            "total_orders": total_orders
        }

        cursor.execute("SELECT * FROM users WHERE role = 'seller' ORDER BY name ASC")
        all_sellers = [dict(u) for u in cursor.fetchall()]

        cursor.execute("SELECT * FROM users WHERE role = 'buyer' ORDER BY name ASC")
        all_buyers = [dict(u) for u in cursor.fetchall()]

        cursor.execute("SELECT * FROM users ORDER BY name ASC")
        all_users = [dict(u) for u in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM products ORDER BY id DESC")
        all_products = [dict(p) for p in cursor.fetchall()]

        cursor.execute('''
            SELECT o.*, p.title as product_title, p.price as product_price 
            FROM orders o
            JOIN products p ON o.product_id = p.id
            ORDER BY o.created_at DESC
        ''')
        all_orders = [dict(ord_item) for ord_item in cursor.fetchall()]

        cursor.execute("SELECT * FROM dynamic_categories ORDER BY id DESC")
        all_categories = [dict(cat) for cat in cursor.fetchall()]

        cursor.execute('''
            SELECT c.id, c.user_name, c.text, c.created_at as timestamp, p.title as product_title, u.student_id 
            FROM comments c
            JOIN products p ON c.product_id = p.id
            JOIN users u ON LOWER(c.user_email) = LOWER(u.email)
            ORDER BY c.id DESC
        ''')
        all_comments = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT category, COUNT(*) as count FROM products GROUP BY category")
        chart_rows = cursor.fetchall()
        chart_labels = [row['category'] for row in chart_rows]
        chart_data = [row['count'] for row in chart_rows]

        cursor.execute("SELECT * FROM system_announcements ORDER BY id DESC LIMIT 1")
        active_notice = cursor.fetchone()

        cursor.execute("SELECT * FROM system_announcements ORDER BY id DESC")
        all_announcements = [dict(row) for row in cursor.fetchall()]

        cursor.close()
        conn.close()
        
        return render_template(
            'admin_users.html', 
            all_users=all_users, 
            all_sellers=all_sellers,
            all_buyers=all_buyers,
            all_products=all_products, 
            all_orders=all_orders,
            stats=stats,
            all_categories=all_categories,
            all_comments=all_comments,
            chart_labels=chart_labels,
            chart_data=chart_data,
            all_announcements=all_announcements,
            active_notice=active_notice  
        )
    except Exception as e:
        return f"Admin Panel Fetch Error: {str(e)}"


# ==================== 💳 PAYMENT VERIFICATION ROUTES ====================

@app.route('/admin/approve-payment/<int:order_id>')
def admin_approve_payment(order_id):
    if not session.get('is_admin'):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin_login'))

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("UPDATE orders SET order_status = 'Approved' WHERE id = %s", (order_id,))
        
        cursor.execute("SELECT buyer_email, product_id FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
        
        if order:
            alert_msg = f"✅ Payment Approved! Your order #{order_id} has been verified and approved."
            cursor.execute('INSERT INTO notifications (product_id, message, user_email) VALUES (%s, %s, %s)',
                           (order['product_id'], alert_msg, order['buyer_email']))
        
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Order #{order_id} payment approved successfully!", "success")
    except Exception as e:
        flash(f"Error approving payment: {str(e)}", "danger")

    return redirect(url_for('view_registered_users'))


@app.route('/admin/reject-payment/<int:order_id>')
def admin_reject_payment(order_id):
    if not session.get('is_admin'):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin_login'))

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("UPDATE orders SET order_status = 'Rejected' WHERE id = %s", (order_id,))
        
        cursor.execute("SELECT buyer_email, product_id FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
        
        if order:
            alert_msg = f"❌ Payment Rejected! Verification failed for order #{order_id}."
            cursor.execute('INSERT INTO notifications (product_id, message, user_email) VALUES (%s, %s, %s)',
                           (order['product_id'], alert_msg, order['buyer_email']))

        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Order #{order_id} payment rejected!", "warning")
    except Exception as e:
        flash(f"Error rejecting payment: {str(e)}", "danger")

    return redirect(url_for('view_registered_users'))


@app.route('/admin/delete-payment/<int:order_id>')
@app.route('/admin/delete-order/<int:order_id>')
def admin_delete_order(order_id):
    if not session.get('is_admin'):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin_login'))

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Order #{order_id} deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting order: {str(e)}", "danger")

    return redirect(url_for('view_registered_users'))


@app.route('/admin/delete-user/<email>')
def delete_user_by_admin(email):
    if not session.get('is_admin'):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin_login'))

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM product_images WHERE product_id IN (SELECT id FROM products WHERE LOWER(seller_email) = LOWER(%s))", (email,))
        cursor.execute("DELETE FROM orders WHERE LOWER(seller_email) = LOWER(%s) OR LOWER(buyer_email) = LOWER(%s)", (email, email))
        cursor.execute("DELETE FROM products WHERE LOWER(seller_email) = LOWER(%s)", (email,))
        cursor.execute("DELETE FROM comments WHERE LOWER(user_email) = LOWER(%s)", (email,))
        cursor.execute("DELETE FROM wishlist WHERE LOWER(user_email) = LOWER(%s)", (email,))
        cursor.execute("DELETE FROM notifications WHERE LOWER(user_email) = LOWER(%s)", (email,))
        cursor.execute("DELETE FROM otp_verifications WHERE LOWER(email) = LOWER(%s)", (email,))
        cursor.execute("DELETE FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
        
        conn.commit()
        cursor.close()
        conn.close()

        flash(f"User ({email}) and all related data deleted permanently!", "success")
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", "danger")

    return redirect(url_for('view_registered_users'))

@app.route('/admin/send-announcement', methods=['POST'])
def admin_send_announcement():
    if not session.get('is_admin'):
        return "Unauthorized", 403
    
    notice_text = request.form.get('announcement_text')
    duration_hours = request.form.get('notice_duration')  
    
    if notice_text and notice_text.strip():
        try:
            hours = int(duration_hours) if duration_hours else 24
            expiry_datetime = datetime.now() + timedelta(hours=hours)  

            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM system_announcements")
            cursor.execute("""
                INSERT INTO system_announcements (text, expiry_time) 
                VALUES (%s, %s)
            """, (notice_text.strip(), expiry_datetime))
            
            conn.commit()
            cursor.close()
            conn.close()
            flash(f"📢 Global Notice broadcasted successfully for {hours} Hours!", "success")
        except Exception as e:
            flash(f"Error publishing notice: {str(e)}", "danger")
    else:
        flash("⚠️ Notice field cannot be left blank!", "warning")
        
    return redirect(url_for('view_registered_users'))

@app.route('/admin/delete-announcement/<int:notice_id>')
def admin_delete_announcement(notice_id):
    if not session.get('is_admin'):
        return "Unauthorized", 403
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM system_announcements WHERE id = %s", (notice_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("📢 Global Notice has been stopped and deleted successfully!", "success")
    except Exception as e:
        flash(f"Error stopping notice: {str(e)}", "danger")
    return redirect(url_for('view_registered_users'))

@app.route('/admin/add-category', methods=['POST'])
def admin_add_category():
    if not session.get('is_admin'):
        return "Unauthorized", 403
    category_name = request.form.get('category_name')
    if category_name:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO dynamic_categories (name) VALUES (%s)", (category_name.strip(),))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Category added!", "success")
        except Exception:
            flash("Category already exists or Database Error", "danger")
    return redirect(url_for('view_registered_users'))

@app.route('/admin/delete-category/<int:cat_id>')
def admin_delete_category(cat_id):
    if not session.get('is_admin'):
        return "Unauthorized", 403
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dynamic_categories WHERE id = %s", (cat_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Delete Category Error: {str(e)}")
    return redirect(url_for('view_registered_users'))

@app.route('/admin/delete-comment/<int:comment_id>')
def admin_delete_comment(comment_id):
    if not session.get('is_admin'):
        return "Unauthorized", 403
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comments WHERE id = %s", (comment_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Delete Comment Error: {str(e)}")
    return redirect(url_for('view_registered_users'))

@app.route('/admin/ban-user/<email>')
def admin_ban_user(email):
    if not session.get('is_admin'):
        return "Unauthorized", 403
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 1 WHERE LOWER(email) = LOWER(%s)", (email,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Ban User Error: {str(e)}")
    return redirect(url_for('view_registered_users'))

@app.route('/admin/unban-user/<email>')
def admin_unban_user(email):
    if not session.get('is_admin'):
        return "Unauthorized", 403
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 0 WHERE LOWER(email) = LOWER(%s)", (email,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Unban User Error: {str(e)}")
    return redirect(url_for('view_registered_users'))

@app.route('/admin/approve-product/<int:product_id>')
def admin_approve_product(product_id):
    if not session.get('is_admin'):
        return "Unauthorized", 403
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("UPDATE products SET status = 'Available' WHERE id = %s", (product_id,))
        
        cursor.execute("SELECT title, category, price, seller_email FROM products WHERE id = %s", (product_id,))
        p = cursor.fetchone()
        
        if p:
            cursor.execute('SELECT email FROM users WHERE LOWER(email) != LOWER(%s)', (p['seller_email'],))
            other_users = cursor.fetchall()
            for u in other_users:
                alert_msg = f"📢 New Item Alert: '{p['title']}' listed in {p['category']} for ৳{p['price']}."
                cursor.execute('INSERT INTO notifications (product_id, message, user_email) VALUES (%s, %s, %s)', 
                               (product_id, alert_msg, u['email']))
                               
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Approve Product Error: {str(e)}")
    return redirect(url_for('view_registered_users'))

@app.route('/admin/delete-product/<int:product_id>')
def admin_delete_product(product_id):
    if not session.get('is_admin'):
        return "Unauthorized", 403
    return delete_product(product_id)

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/diu-secret-gateway-2026')


# ==================== ⚖️ OFFICIAL PLATFORM PATHS ====================

@app.route('/about')
def about_us():
    return render_template('about.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms.html')


# ==================== CLEAR NOTIFICATION API ====================

@app.route('/api/notifications/clear', methods=['POST'])
def clear_all_notifications():
    if 'user_email' not in session:
        return jsonify({'status': 'unauthorized', 'message': 'Please login first'}), 401
        
    user_email = session['user_email']
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notifications WHERE LOWER(user_email) = LOWER(%s)', (user_email,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
