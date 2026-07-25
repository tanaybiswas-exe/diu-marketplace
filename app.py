from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta  
from urllib.parse import quote    
from flask import send_from_directory         
import os
import re
import requests
import base64
import psycopg2
from psycopg2.extras import RealDictCursor

# --- 📧 OTP সিস্টেমের জন্য প্রয়োজনীয় মডিউল ---
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 🛡️ রেট লিমিটিং মডিউল ---
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

# ফাইল সাইজ লিমিট এক্সসিড করলে হ্যান্ডলার
@app.errorhandler(413)
def request_entity_too_large(error):
    flash('❌ Upload failed! Total image size cannot be larger than 6MB.', 'danger')
    return redirect(request.referrer or url_for('home'))

# রেট লিমিট ক্রস করলে ইউজারকে আটকানোর হ্যান্ডলার
@app.errorhandler(429)
def ratelimit_handler(e):
    flash(f"⚠️ Action Blocked: {e.description}", "danger")
    return redirect(request.referrer or url_for('home'))

# ==================== 🌐 RENDER KEEP-ALIVE ROUTE ====================
@app.route('/ping')
def ping():
    """UptimeRobot দিয়ে সার্ভার অল-টাইম একটিভ রাখার রাউট"""
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
SENDER_EMAIL = "admin094103@gmail.com"        
SENDER_PASSWORD = "fhfc gmih isil mkpn"      

def send_otp_email(target_email, otp_code, purpose="Verification"):
    """সরাসরি ইউজারের অফিশিয়াল মেইলে ওটিপি পাঠানোর কোর ফাংশন"""
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
    """হাই-ট্রাফিক হ্যান্ডেল করার জন্য অপটিমাইজড কানেকশন মেথড"""
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
                used_time VARCHAR(255),
                location VARCHAR(255),
                description TEXT,
                whatsapp VARCHAR(50),
                photo_url VARCHAR(512),
                seller_email VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT 'Pending'
            )
        ''')

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
            print("👑 Default Admin Account (admin@diu.edu.bd) injected successfully!")

        cursor.close()
        conn.close()
        print("✅ Neon PostgreSQL Database initialized successfully!")
    except Exception as e:
        print(f"⚠️ Database Initialization Error: {str(e)}")

    app._db_inited = True


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
            WHERE user_email = %s AND is_read = FALSE 
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


# ==================== ❤️ AJAX WISHLIST TOGGLE SYSTEM ====================

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
        
        cursor.execute('SELECT id FROM wishlist WHERE user_email = %s AND product_id = %s', (user_email, product_id))
        item = cursor.fetchone()
        
        if item:
            cursor.execute('DELETE FROM wishlist WHERE user_email = %s AND product_id = %s', (user_email, product_id))
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
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
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


# ==================== 🔑 FORGOT PASSWORD & OTP SYSTEM ROUTES ====================

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
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
                flash("📥 An OTP has been sent to your email. Enter it below to change password.", "success")
                return redirect(url_for('verify_otp', purpose='Reset'))
            else:
                flash("❌ Failed to send OTP email.", "danger")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            
    return render_template('forgot_password.html')


@app.route('/resend-otp/<purpose>')
@limiter.limit("5 per minute", error_message="Too many requests! Please wait 1 minute before requesting a new OTP.")
def resend_otp(purpose):
    email = session.get('reg_data', {}).get('email') if purpose == 'Registration' else session.get('reset_email')
    
    if not email:
        flash("Session expired! Please start the process again.", "danger")
        return redirect(url_for('register', role='buyer') if purpose == 'Registration' else url_for('forgot_password'))

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM otp_verifications WHERE email = %s AND purpose = %s', (email, purpose))
        
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
            flash("Session expired or invalid. Please try again.", "danger")
            return redirect(url_for('home'))

        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('''
                SELECT * FROM otp_verifications 
                WHERE email = %s AND otp_code = %s AND purpose = %s AND expiry_time > %s
                ORDER BY id DESC LIMIT 1
            ''', (email, input_otp, purpose, datetime.now()))
            
            valid_otp = cursor.fetchone()
            
            if valid_otp:
                cursor.execute('DELETE FROM otp_verifications WHERE email = %s', (email,))
                
                if purpose == 'Registration':
                    reg = session.get('reg_data')
                    cursor.execute('''
                        INSERT INTO users (email, name, student_id, mobile, role, password, ip_address, is_banned) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                    ''', (reg['email'], reg['name'], reg['student_id'], reg['mobile'], reg['role'], reg['password'], reg['ip_address']))
                    conn.commit()
                    
                    session.pop('reg_data', None)
                    flash(" Verification successful! Account is active. Please login.", "success")
                    return redirect(url_for('login'))
                    
                elif purpose == 'Reset':
                    if not new_pass:
                        flash("Please provide a new password.", "danger")
                        return redirect(url_for('verify_otp', purpose='Reset'))
                        
                    hashed_pwd = generate_password_hash(new_pass)
                    cursor.execute('UPDATE users SET password = %s WHERE email = %s', (hashed_pwd, email))
                    conn.commit()
                    
                    session.pop('reset_email', None)
                    flash("✅ Password updated successfully! Login with your new password.", "success")
                    return redirect(url_for('login'))
            else:
                flash("❌ Invalid or Expired OTP Code! Please try again.", "danger")
                
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
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and check_password_hash(user['password'], password):
                if user['is_banned'] == 1:
                    flash("❌ Your account has been suspended by the administrator for violating marketplace rules.", "danger")
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
            SELECT p.*, u.name AS seller_name 
            FROM products p
            LEFT JOIN users u ON p.seller_email = u.email
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
                cursor.execute('SELECT * FROM wishlist WHERE user_email = %s AND product_id = %s', (user_data['email'], p['id']))
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
        return render_template('index.html', user=user_data, products=final_products, announcement=announcement_text, live_categories=live_categories, selected_category=category_filter)
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
            LEFT JOIN users u ON p.seller_email = u.email
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
            cursor.execute('SELECT * FROM wishlist WHERE user_email = %s AND product_id = %s', (session['user_email'], product_id))
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
            
        return render_template('product-details.html', product=product_dict, user=user_data)
    except Exception as e:
        return f"<h1>Error loading product details</h1><p>{str(e)}</p>"


@app.route('/user/profile/<email>')
def user_profile(email):
    if 'user_email' not in session and not session.get('is_admin'):
        return redirect(url_for('login'))

    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        profile_user = cursor.fetchone()

        if profile_user:
            profile_user_dict = dict(profile_user)
            
            cursor.execute('''
                SELECT p.*, u.name AS seller_name 
                FROM products p 
                JOIN users u ON p.seller_email = u.email 
                WHERE p.seller_email = %s 
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
                'role': session.get('user_role')
            }

            cursor.close()
            conn.close()
            return render_template(
                'user_profile.html', 
                profile_user=profile_user_dict, 
                user=profile_user_dict, 
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
                cursor.execute('UPDATE users SET profile_pic = %s WHERE email = %s', (imgbb_url, session['user_email']))
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
        used_time = request.form.get('used_time')
        location = request.form.get('location')
        description = request.form.get('description')
        whatsapp = request.form.get('whatsapp')

        try:
            price = int(price_raw)
        except ValueError:
            price = 0

        file = request.files.get('product_photo')
        photo_url = "https://placehold.co/600x400?text=No+Image"

        if file and file.filename != '':
            try:
                img_stream = file.read()
                base64_image = base64.b64encode(img_stream).decode('utf-8')
                payload = {'key': IMGBB_API_KEY, 'image': base64_image}
                r = requests.post('https://api.imgbb.com/1/upload', data=payload)
                res_data = r.json()
                if res_data['success']:
                    photo_url = res_data['data']['url']
            except Exception as e:
                flash(f"Main Image Upload Error: {str(e)}", "danger")

        try:
            conn = get_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute('''
                INSERT INTO products (title, category, price, used_time, location, description, whatsapp, photo_url, seller_email, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending') RETURNING id
            ''', (title, category, price, used_time, location, description, whatsapp, photo_url, session['user_email']))
            
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
                        
                        if add_response.status_code == 200 and add_res_data['success']:
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
        cursor.execute("UPDATE products SET status = 'Sold Out' WHERE id = %s AND seller_email = %s", (product_id, session['user_email']))
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
        cursor.execute("UPDATE products SET status = 'Available' WHERE id = %s AND seller_email = %s", (product_id, session['user_email']))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Product marked as Available again!", "success")
    except Exception:
        pass
    return redirect(url_for('user_profile', email=session['user_email']))

@app.route('/edit-product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM products WHERE id = %s AND seller_email = %s", (product_id, session['user_email']))
    product = cursor.fetchone()
    
    if not product:
        cursor.close()
        conn.close()
        flash("Unauthorized or Product not found!", "danger")
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')  
        price = request.form.get('price')
        used_time = request.form.get('used_time')
        location = request.form.get('location')
        description = request.form.get('description')
        whatsapp = request.form.get('whatsapp')
        
        if not category or category.strip() == "":
            category = product['category'] 
        
        cursor.execute('''
            UPDATE products 
            SET title=%s, category=%s, price=%s, used_time=%s, location=%s, description=%s, whatsapp=%s, status='Pending'
            WHERE id=%s
        ''', (title, category, price, used_time, location, description, whatsapp, product_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Product updated successfully! Awaiting Admin re-verification.", "success")
        return redirect(url_for('user_profile', email=session['user_email']))
        
    cursor.execute("SELECT name FROM dynamic_categories ORDER BY name ASC")
    live_categories = [row['name'] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    
    return render_template('edit_product.html', product=product, live_categories=live_categories)

@app.route('/delete-product/<int:product_id>', methods=['GET', 'POST'])
def delete_product(product_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = %s AND seller_email = %s", (product_id, session['user_email']))
        cursor.execute("DELETE FROM wishlist WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM comments WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM product_images WHERE product_id = %s", (product_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Product deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting product: {str(e)}", "danger")
    return redirect(url_for('user_profile', email=session['user_email']))


# ==================== 👑 BUYER INTERACTION ROUTES ====================

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
        cursor.execute('SELECT * FROM wishlist WHERE user_email = %s AND product_id = %s', (user_email, product_id))
        fav = cursor.fetchone()
        if fav:
            cursor.execute('DELETE FROM wishlist WHERE user_email = %s AND product_id = %s', (user_email, product_id))
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
            LEFT JOIN users u ON p.seller_email = u.email
            JOIN wishlist w ON p.id = w.product_id 
            WHERE w.user_email = %s ORDER BY w.id DESC
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
        return render_template('index.html', user=user_data, products=final_products, is_wishlist_page=True, live_categories=[])
    except Exception as e:
        print(f"⚠️ Wishlist Page Error: {str(e)}")
        return redirect(url_for('home'))

@app.route('/add-comment/<int:product_id>', methods=['POST'])
@limiter.limit("10 per minute", error_message="You are commenting too fast! Please slow down.")
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
            cursor.execute('SELECT * FROM users WHERE email = %s', (user_email,))
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
            cursor.execute('UPDATE users SET password = %s WHERE email = %s', (hashed_password, user_email))
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


# ==================== 🛠️ ADMIN PANEL SYSTEM ====================

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
                cursor.execute('SELECT * FROM users WHERE email = %s', (admin_email,))
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

        stats = {
            "total_users": total_users,
            "total_sellers": total_sellers,
            "total_buyers": total_buyers,
            "total_products": total_products,
            "pending_products_count": pending_products_count
        }

        cursor.execute("SELECT * FROM users")
        all_users = [dict(u) for u in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM products ORDER BY id DESC")
        all_products = [dict(p) for p in cursor.fetchall()]

        cursor.execute("SELECT * FROM dynamic_categories ORDER BY id DESC")
        all_categories = [dict(cat) for cat in cursor.fetchall()]

        cursor.execute('''
            SELECT c.id, c.user_name, c.text, c.created_at as timestamp, p.title as product_title, u.student_id 
            FROM comments c
            JOIN products p ON c.product_id = p.id
            JOIN users u ON c.user_email = u.email
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
            all_products=all_products, 
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

# ==================== 📢 OVERWRITE/DELETE ACTIVE NOTICE ROUTE ====================
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
        cursor.execute("UPDATE users SET is_banned = 1 WHERE email = %s", (email,))
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
        cursor.execute("UPDATE users SET is_banned = 0 WHERE email = %s", (email,))
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
            cursor.execute('SELECT email FROM users WHERE email != %s', (p['seller_email'],))
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
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        cursor.execute("DELETE FROM wishlist WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM comments WHERE product_id = %s", (product_id,))
        cursor.execute("DELETE FROM product_images WHERE product_id = %s", (product_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Delete Product Error: {str(e)}")
    return redirect(url_for('view_registered_users'))

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/diu-secret-gateway-2026')


# ==================== ⚖️ OFFICIAL PLATFORM COMPLIANCE PATHS ====================

@app.route('/about')
def about_us():
    return render_template('about.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms.html')


# ==================== 🔔 CLEAR NOTIFICATION API ROUTE ====================

@app.route('/api/notifications/clear', methods=['POST'])
def clear_all_notifications():
    if 'user_email' not in session:
        return jsonify({'status': 'unauthorized', 'message': 'Please login first'}), 401
        
    user_email = session['user_email']
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM notifications WHERE user_email = %s', (user_email,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
