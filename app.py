from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
import mysql.connector
from dotenv import load_dotenv
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from datetime import datetime
from functools import wraps
import csv
import io
from flask import make_response

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuration
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'credit_bazaar')
app.config['ADMIN_EMAIL'] = os.getenv('ADMIN_EMAIL', 'admin@creditbazaar.com')
app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD', 'admin123')

jwt = JWTManager(app)

# Database connection helper
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        return conn
    except mysql.connector.Error as err:
        if err.errno == 1049: # Unknown database
             # Try connecting without DB to create it
            conn = mysql.connector.connect(
                host=app.config['MYSQL_HOST'],
                user=app.config['MYSQL_USER'],
                password=app.config['MYSQL_PASSWORD']
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {app.config['MYSQL_DB']}")
            conn.database = app.config['MYSQL_DB']
            return conn
        else:
            print(f"Error connecting to database: {err}")
            return None

# Initialize Database
def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        # Create Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        ''')

        # Create Loan Applications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loan_applications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                contact_no VARCHAR(20) NOT NULL,
                company_name VARCHAR(255),
                annual_salary VARCHAR(50),
                loan_type VARCHAR(50),
                salary_mode VARCHAR(50),
                pincode VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create Credit Card Applications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credit_card_applications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                contact_no VARCHAR(20) NOT NULL,
                company_name VARCHAR(255),
                annual_salary VARCHAR(50),
                card_type VARCHAR(50),
                salary_mode VARCHAR(50),
                pincode VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized.")

with app.app_context():
    init_db()

# Admin login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def home():
    return render_template('index.html')

# Redirect index.html to root or keep it if needed, but clean naming preferred
@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/loans')
def loans_page():
    return render_template('loans.html')

@app.route('/creditcards')
def credit_cards_page():
    return render_template('credit_cards.html')

@app.route('/calculators')
def calculators_page():
    if os.path.exists(os.path.join(app.template_folder, 'calculators.html')):
         return render_template('calculators.html')
    return "Calculators page not found", 404

# Static file serving (for images inside static folder)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# API Routes
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password') # In production, hash this!

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        access_token = create_access_token(identity=username)
        return jsonify({'access_token': access_token}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/apply-loan', methods=['POST'])
# @jwt_required() # Uncomment to enforce JWT for application
def apply_loan():
    data = request.json
    required_fields = ['customer_name', 'email', 'contact_no', 'annual_salary', 'loan_type', 'salary_mode', 'pincode']
    
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = '''INSERT INTO loan_applications 
                 (customer_name, email, contact_no, company_name, annual_salary, loan_type, salary_mode, pincode) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'''
        values = (
            data['customer_name'], 
            data['email'], 
            data['contact_no'], 
            data.get('company_name', ''), 
            data['annual_salary'], 
            data['loan_type'], 
            data['salary_mode'], 
            data['pincode']
        )
        cursor.execute(sql, values)
        conn.commit()
        return jsonify({'message': 'Loan application submitted successfully!', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        print(err)
        return jsonify({'error': 'Database error'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/apply-credit-card', methods=['POST'])
def apply_credit_card():
    data = request.json
    required_fields = ['customer_name', 'email', 'contact_no', 'annual_salary', 'card_type', 'salary_mode', 'pincode']
    
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = '''INSERT INTO credit_card_applications 
                 (customer_name, email, contact_no, company_name, annual_salary, card_type, salary_mode, pincode) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'''
        values = (
            data['customer_name'], 
            data['email'], 
            data['contact_no'], 
            data.get('company_name', ''), 
            data['annual_salary'], 
            data['card_type'], 
            data['salary_mode'], 
            data['pincode']
        )
        cursor.execute(sql, values)
        conn.commit()
        return jsonify({'message': 'Credit card application submitted successfully!', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        print(err)
        return jsonify({'error': 'Database error'}), 500
    finally:
        cursor.close()
        conn.close()

# Admin Routes - Login (AJAX only, modal on homepage)
@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if email == app.config['ADMIN_EMAIL'] and password == app.config['ADMIN_PASSWORD']:
        session['admin_logged_in'] = True
        session['admin_email'] = email
        return jsonify({'success': True, 'redirect': '/admin/dashboard'}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total counts
    cursor.execute("SELECT COUNT(*) FROM loan_applications")
    loan_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM credit_card_applications")
    credit_card_count = cursor.fetchone()[0]
    
    total_leads = loan_count + credit_card_count
    
    cursor.close()
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         total_leads=total_leads, 
                         loan_count=loan_count, 
                         credit_card_count=credit_card_count)

@app.route('/admin/leads')
@login_required
def admin_leads():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all loan applications
    cursor.execute("SELECT *, 'Loan' as type FROM loan_applications ORDER BY created_at DESC")
    loan_leads = cursor.fetchall()
    
    # Get all credit card applications
    cursor.execute("SELECT *, 'Credit Card' as type FROM credit_card_applications ORDER BY created_at DESC")
    credit_card_leads = cursor.fetchall()
    
    # Combine and sort by created_at
    all_leads = loan_leads + credit_card_leads
    all_leads.sort(key=lambda x: x['created_at'], reverse=True)
    
    cursor.close()
    conn.close()
    
    return render_template('admin_leads.html', leads=all_leads)

@app.route('/admin/export/csv')
@login_required
def export_csv():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all leads
    cursor.execute("SELECT *, 'Loan' as type, loan_type as product_type FROM loan_applications ORDER BY created_at DESC")
    loan_leads = cursor.fetchall()
    
    cursor.execute("SELECT *, 'Credit Card' as type, card_type as product_type FROM credit_card_applications ORDER BY created_at DESC")
    credit_card_leads = cursor.fetchall()
    
    all_leads = loan_leads + credit_card_leads
    all_leads.sort(key=lambda x: x['created_at'], reverse=True)
    
    cursor.close()
    conn.close()
    
    # Create CSV
    si = io.StringIO()
    fieldnames = ['id', 'type', 'customer_name', 'email', 'contact_no', 'company_name', 'annual_salary', 'product_type', 'salary_mode', 'pincode', 'created_at']
    writer = csv.DictWriter(si, fieldnames=fieldnames)
    
    writer.writeheader()
    for lead in all_leads:
        writer.writerow({
            'id': lead['id'],
            'type': lead['type'],
            'customer_name': lead['customer_name'],
            'email': lead['email'],
            'contact_no': lead['contact_no'],
            'company_name': lead.get('company_name', ''),
            'annual_salary': lead['annual_salary'],
            'product_type': lead.get('product_type', ''),
            'salary_mode': lead.get('salary_mode', ''),
            'pincode': lead.get('pincode', ''),
            'created_at': lead['created_at'].strftime('%Y-%m-%d %H:%M:%S') if lead['created_at'] else ''
        })
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=leads_export.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_email', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
