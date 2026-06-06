from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
import mysql.connector
from dotenv import load_dotenv
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from datetime import datetime
from functools import wraps
import csv
import io
import json
from flask import make_response

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuration
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False  # Disabled for simplicity as per plan
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'credit_bazaar')
app.config['ADMIN_EMAIL'] = os.getenv('ADMIN_EMAIL', 'admin@creditbazaar.com')
app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD', 'admin123')

jwt = JWTManager(app)

# JWT Error Loaders - Redirect to Landing Page if Invalid/Unauthorized
@jwt.unauthorized_loader
def unauthorized_callback(callback):
    return redirect(url_for('home'))

@jwt.invalid_token_loader
def invalid_token_callback(callback):
    return redirect(url_for('home'))

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return redirect(url_for('home'))

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
                referral VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Add referral column for existing installations
        try:
            cursor.execute("ALTER TABLE loan_applications ADD COLUMN referral VARCHAR(255)")
            conn.commit()
        except mysql.connector.Error:
            pass

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

        # Create Job Openings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_openings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                department VARCHAR(255) NOT NULL,
                location VARCHAR(255) DEFAULT 'Remote / Hybrid',
                type VARCHAR(50) DEFAULT 'Full-time',
                description TEXT,
                responsibilities TEXT,
                requirements TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized.")

with app.app_context():
    init_db()

# Removed custom login_required decorator in favor of @jwt_required()

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

# Data for individual loan-type pages (linked from the Loans dropdown)
LOAN_TYPE_PAGES = {
    'personal-loan': {
        'loan_name': 'Personal Loan',
        'loan_value': 'Personal Loan',
        'hero_image': 'personal_loan_service.png',
        'headline': 'Funds for Life’s Unscripted Moments',
        'subtext': 'Get an unsecured Personal Loan with minimal documentation, quick approval, and flexible repayment tenure for any personal need - medical emergencies, weddings, travel, or home renovation.',
        'meta_description': 'Apply for a Personal Loan with Creditsbazaar. Collateral-free funding, quick approval, and flexible tenure of 1-7 years at competitive interest rates.',
        'intro': "A personal loan is an unsecured loan offered by banks and financial institutions to meet personal financial needs such as medical emergencies, weddings, travel, home renovation, or debt consolidation. Since it is collateral-free, borrowers do not need to pledge any assets.",
        'rate': "Personal loan interest rates in India generally range from 9.99% to 24% per year, depending on your credit score, income, loan amount, and repayment tenure.",
        'eligibility': ["Age between 21 and 60 years", "Minimum monthly income ₹15,000 or above", "Stable job or business", "Good CIBIL score (700+)"],
        'documents': ["PAN Card", "Aadhaar Card", "Address proof", "Salary slips", "Bank statements (last 3–6 months)"],
        'benefits': ["No collateral required", "Quick approval and instant disbursal", "Flexible loan tenure (1–7 years)", "Can be used for multiple purposes"],
        'apply_steps': ["Check eligibility on CreditsBazaar website", "Fill out the online personal loan application", "Upload required documents", "Get approval and receive funds in your bank account"],
        'conclusion': "A personal loan is a fast and flexible financing option for urgent expenses. Before applying, compare interest rates, processing fees, and repayment terms to choose the best loan offer.",
        'gallery': ['personal_loan.png', 'personal_loan_service.png']
    },
    'business-loan': {
        'loan_name': 'Business Loan',
        'loan_value': 'Business Loan',
        'hero_image': 'business_loan_service.png',
        'headline': 'Fuel Your Business Growth',
        'subtext': 'Working capital, equipment purchase, expansion, or hiring - get a Business Loan tailored for small businesses, startups, MSMEs, and self-employed professionals.',
        'meta_description': 'Apply for a Business Loan with Creditsbazaar. Quick approval, flexible repayment, and competitive interest rates for MSMEs, startups, and self-employed professionals.',
        'intro': "A business loan is a financial solution provided by banks and financial institutions to help businesses grow and manage expenses. Entrepreneurs can use a business loan for working capital, purchasing equipment, expanding operations, hiring staff, or managing cash flow. Business loans are available for small businesses, startups, MSMEs, and self-employed professionals.",
        'rate': "The business loan interest rate in India usually ranges between 11% to 24% per year, depending on the lender, business turnover, credit score, and loan amount. Factors affecting the rate include your business credit score, annual turnover, business stability, loan tenure, and repayment capacity.",
        'eligibility': ["Age between 21 and 65 years", "Minimum 1–3 years of business operation", "Stable business income", "Good credit score (650+)", "Indian citizenship"],
        'documents': ["PAN Card", "Aadhaar Card", "Business registration proof", "Bank statements (last 6–12 months)", "Income Tax Returns (ITR)", "GST registration (if applicable)"],
        'benefits': ["Helps in business expansion", "Improves cash flow management", "No collateral required in many cases", "Quick loan approval", "Flexible repayment options"],
        'apply_steps': ["Choose a bank or NBFC offering business loans", "Fill out the online business loan application", "Submit required documents", "Get loan approval after verification", "Receive the loan amount in your bank account"],
        'conclusion': "A business loan is an effective way to finance business growth and manage working capital. Before applying, compare interest rates, loan terms, and processing fees to choose the best lender for your business needs.",
        'gallery': ['business_loan.png', 'business_loan_service.png']
    },
    'loan-against-property': {
        'loan_name': 'Loan Against Property',
        'loan_value': 'Loan Against Property',
        'hero_image': 'home_loan_service.png',
        'headline': 'Unlock the Value of Your Property',
        'subtext': 'Pledge your residential, commercial, or industrial property to secure a high-value loan at lower interest rates with longer repayment tenure of up to 15-20 years.',
        'meta_description': 'Apply for a Loan Against Property with Creditsbazaar. Lower interest rates, higher loan amounts, and longer tenure using your property as collateral.',
        'intro': "A Loan Against Property (LAP) is a secured loan where borrowers pledge their residential, commercial, or industrial property as collateral to get funds from banks or financial institutions. It is one of the most affordable loan options because the interest rate is usually lower than personal loans. People commonly use LAP funds for business expansion, education, medical emergencies, debt consolidation, or other large financial needs.",
        'rate': "The loan against property interest rate in India typically ranges from 8% to 14% per year, depending on the lender, property value, credit score, and loan amount. Factors affecting the rate include the property's value and location, the applicant's credit score, income and repayment capacity, loan tenure, and loan amount.",
        'eligibility': ["Age between 21 and 65 years", "Stable income or business", "Ownership of residential or commercial property", "Good credit score (650 or above)", "Indian citizenship"],
        'documents': ["PAN Card", "Aadhaar Card", "Address proof", "Property ownership documents", "Income proof (salary slips or business income proof)", "Bank statements (last 6–12 months)"],
        'benefits': ["Lower interest rates compared to personal loans", "Higher loan amount based on property value", "Longer repayment tenure (up to 15–20 years)", "Flexible use of funds", "Suitable for business or large financial needs"],
        'apply_steps': ["Choose a bank or financial institution offering LAP loans", "Fill out the loan against property application form", "Submit KYC and property documents", "Property evaluation and verification by the lender", "Loan approval and disbursal to your bank account"],
        'conclusion': "A loan against property is a cost-effective way to raise large funds by using your property as security. Before applying, compare interest rates, loan tenure, and processing fees to select the best loan option.",
        'gallery': ['home_loan.png', 'home_loan_service.png']
    },
    'home-loan': {
        'loan_name': 'Home Loan',
        'loan_value': 'Home Loan',
        'hero_image': 'home_loan_service.png',
        'headline': 'The Keys to Your Dream Home',
        'subtext': 'Buy, build, or renovate your home with attractive interest rates, high loan-to-value funding, and repayment tenures of up to 30 years.',
        'meta_description': 'Apply for a Home Loan with Creditsbazaar. Attractive interest rates, up to 90% property funding, and tenures of up to 30 years.',
        'intro': "A home loan is a loan provided by banks or financial institutions to help individuals purchase a residential property, such as a house or apartment. The property acts as security (collateral) for the loan until it is fully repaid. Home loans allow buyers to finance a large portion of the property cost and repay it in monthly EMIs over a long tenure.",
        'rate': "In India, home loan interest rates generally range between 7.90% and 10.5% per year, depending on the lender, credit score, loan amount, and repayment profile. Borrowers with a higher credit score often receive lower interest rates.",
        'example': {
            'heading': "Loan Amount & Tenure",
            'text': "Banks usually offer 70% to 90% of the property value as a home loan. For example, on a property priced at ₹50,00,000, a bank may finance ₹40,00,000 (80%) while the buyer pays ₹10,00,000 as down payment. Home loans usually have a repayment period between 5 years and 30 years, helping borrowers manage their monthly EMI payments."
        },
        'eligibility': ["Age between 21 and 65 years", "Stable income or employment", "Good CIBIL score (700 or above)", "Indian citizenship", "Ability to repay EMI"],
        'documents': ["Identity Proof: PAN Card, Aadhaar Card, Passport or Voter ID", "Address Proof: Utility bills, Aadhaar Card, Passport", "Income Proof: Salary slips, bank statements, Form 16 (or ITR & business proof for self-employed)", "Property Documents: Sale agreement, title documents, builder/project approval documents"],
        'benefits': ["Helps in buying a house", "Lower interest rates compared to many other loans", "Long repayment tenure", "High loan amount available", "Tax benefits under Indian income tax laws"],
        'apply_steps': ["Choose a bank or financial institution offering home loans", "Fill out the home loan application form", "Submit required documents", "Bank verifies income and property documents", "Loan approval and sanction", "Loan amount disbursed to the seller or builder"],
        'conclusion': "A home loan helps individuals purchase property with manageable monthly payments. Before applying, compare interest rates, processing fees, loan tenure, and repayment terms to select the best loan option.",
        'gallery': ['home_loan.png', 'home_loan_service.png']
    },
    'overdraft': {
        'loan_name': 'OverDraft',
        'loan_value': 'OverDraft',
        'hero_image': 'overdraft_service.png',
        'headline': 'Instant Access to Extra Funds, On Demand',
        'subtext': 'Withdraw more than your account balance up to a pre-approved limit and pay interest only on the amount you use - perfect for managing short-term cash flow needs.',
        'meta_description': 'Apply for an Overdraft facility with Creditsbazaar. Flexible withdrawal limits with interest charged only on the amount used.',
        'intro': "An overdraft is a financial facility provided by banks that allows customers to withdraw more money from their bank account than the available balance. It helps individuals or businesses manage short-term cash shortages and urgent expenses. The bank lends you money up to a pre-approved limit, and you only pay interest on the amount you use. There are two types: Secured Overdraft (against FD, property, insurance, shares/bonds) and Unsecured Overdraft (offered to salaried individuals with a strong credit history).",
        'example': {
            'heading': "How an Overdraft Works",
            'text': "The bank sets a maximum borrowing limit for the account holder. If the account balance becomes zero, the customer can still withdraw money up to the approved limit. For example, if your overdraft limit is ₹2,00,000 and your account balance is ₹0, you can withdraw up to ₹2,00,000. Interest will be charged only on the amount you use and for the number of days you use it."
        },
        'rate': "Overdraft interest rates vary depending on the bank and type of overdraft. Typical rates in India range from 10% to 20% per year. Interest is calculated daily on the used amount, not on the full limit.",
        'comparison_table': {
            'heading': "Difference Between Overdraft and Loan",
            'rows': [
                {'feature': "Type", 'overdraft': "Credit limit", 'loan': "Fixed amount"},
                {'feature': "Interest", 'overdraft': "Charged on used amount", 'loan': "Charged on full loan"},
                {'feature': "Usage", 'overdraft': "Flexible withdrawal", 'loan': "Lump sum payment"},
                {'feature': "Repayment", 'overdraft': "Flexible", 'loan': "Fixed EMIs"},
            ]
        },
        'eligibility': ["Age between 21 and 65 years", "Stable income or business", "Good credit score", "Active bank account with the lender", "Good repayment history"],
        'documents': ["PAN Card", "Aadhaar Card", "Address proof", "Bank statements", "Income proof (salary slips or business documents)", "Additional collateral documents (for secured overdraft)"],
        'benefits': ["Instant access to extra funds", "Interest charged only on used amount", "Flexible repayment option", "Helps manage short-term cash flow issues", "Suitable for both individuals and businesses"],
        'apply_steps': ["Approach your bank for an overdraft facility", "Submit KYC and income/collateral documents as required", "Get your overdraft limit sanctioned", "Withdraw funds as needed up to your limit", "Repay flexibly and pay interest only on the amount used"],
        'conclusion': "An overdraft facility is a useful financial tool for handling short-term cash shortages. It provides flexibility, quick access to funds, and interest is charged only on the amount used. Businesses and individuals often use overdrafts to manage temporary financial needs.",
        'gallery': ['overdraft.png', 'overdraft_service.png']
    },
    'credit-card': {
        'loan_name': 'Credit Card',
        'loan_value': 'Credit Card',
        'hero_image': 'credit_card_benefits.png',
        'headline': 'Smarter Spending Starts Here',
        'subtext': 'Compare and apply for Credit Cards with attractive rewards, cashback, and offers tailored to your spending habits and lifestyle.',
        'meta_description': 'Apply for a Credit Card with Creditsbazaar. Compare top cards with the best rewards, cashback, and welcome offers.',
        'intro': "A credit card lets you make purchases on credit up to a pre-approved limit and repay the amount later, often with added benefits like rewards, cashback, and discounts. It's a convenient tool for managing everyday expenses, building a credit history, and accessing short-term, interest-free credit when bills are paid in full and on time.",
        'rate': "Credit cards typically charge 2% to 4% per month (24%–48% annually) on outstanding balances if not paid in full, along with annual or joining fees that vary by card type and issuer.",
        'eligibility': ["Age between 18 and 65 years", "Stable income (salaried or self-employed)", "Good credit score (700+ preferred)", "Indian citizenship", "Existing relationship with the bank (preferred for some cards)"],
        'documents': ["PAN Card", "Aadhaar Card", "Address proof", "Income proof (salary slips or ITR)", "Passport-size photographs"],
        'benefits': ["Rewards, cashback, and discount offers", "Builds your credit score with responsible usage", "Interest-free credit period on purchases", "Add-on cards for family members", "Useful for emergencies and large purchases"],
        'apply_steps': ["Compare credit card offers on the CreditsBazaar website", "Choose a card that matches your spending habits", "Fill out the online application form", "Submit KYC and income documents", "Get approval and receive your card"],
        'conclusion': "A credit card is a convenient financial tool when used responsibly. Compare annual fees, interest rates, and reward programs before choosing the right card for you.",
        'gallery': ['credit_card.png', 'credit_card_benefits.png', 'credit_cards_hero_realistic.png']
    },
    'car-loan': {
        'loan_name': 'Car Loan',
        'loan_value': 'Car Loan',
        'hero_image': 'car_loan.jpg',
        'headline': 'Drive Home Your Dream Car',
        'subtext': 'Finance your new or used car purchase with competitive interest rates, quick approvals, and flexible repayment tenures.',
        'meta_description': 'Apply for a Car Loan with Creditsbazaar. Competitive interest rates, quick approvals, and flexible repayment tenure for new and used cars.',
        'intro': "A car loan is a secured loan offered by banks and financial institutions to help individuals purchase a new or used car. The vehicle itself serves as collateral until the loan is fully repaid, which allows lenders to offer relatively lower interest rates compared to unsecured loans.",
        'rate': "Car loan interest rates in India generally range from 8% to 14% per year, depending on the lender, your credit score, the loan amount, tenure, and whether the car is new or used.",
        'eligibility': ["Age between 21 and 65 years", "Stable income or business", "Good credit score (700+ preferred)", "Indian citizenship", "Valid driving license (recommended)"],
        'documents': ["PAN Card", "Aadhaar Card", "Address proof", "Income proof (salary slips or ITR)", "Bank statements (last 3–6 months)", "Car quotation / proforma invoice"],
        'benefits': ["Lower interest rates due to collateral-backed structure", "Up to 100% on-road funding for select cars", "Flexible tenure of up to 7 years", "Quick approval and disbursal", "Available for both new and used cars"],
        'apply_steps': ["Check eligibility on the CreditsBazaar website", "Fill out the online car loan application", "Upload required documents and car quotation", "Get approval and loan sanction", "Receive disbursal directly to the dealer"],
        'conclusion': "A car loan makes vehicle ownership affordable through manageable EMIs. Compare interest rates, processing fees, and tenure options before choosing the best lender.",
        'gallery': ['car_loan.jpg']
    },
}

@app.route('/loans/<slug>')
def loan_type_page(slug):
    data = LOAN_TYPE_PAGES.get(slug)
    if not data:
        return redirect(url_for('loans_page'))
    return render_template('loan_type.html', slug=slug, content_json=json.dumps(data), **data)

@app.route('/creditcards')
def credit_cards_page():
    return render_template('credit_cards.html')

@app.route('/calculators')
def calculators_page():
    if os.path.exists(os.path.join(app.template_folder, 'calculators.html')):
         return render_template('calculators.html')
    return "Calculators page not found", 404

@app.route('/glossary')
def glossary_page():
     return render_template('glossary.html')

@app.route('/terms-condition')
def terms_condition_page():
     return render_template('terms_condition.html')

@app.route('/disclaimer')
def disclaimer_page():
     return render_template('disclaimer.html')

@app.route('/privacy-policy')
def privacy_policy_page():
     return render_template('privacy_policy.html')

@app.route('/faq')
def faq_page():
     return render_template('faq.html')

@app.route('/contact')
def contact_page():
    return render_template('contact.html')

@app.route('/careers')
def careers_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM job_openings ORDER BY created_at DESC")
    jobs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('careers.html', jobs=jobs)

# Static file serving (for images inside static folder)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

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
                 (customer_name, email, contact_no, company_name, annual_salary, loan_type, salary_mode, pincode, referral)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)'''
        referral = data.get('referral', '')
        if referral == 'Other' and data.get('referral_other'):
            referral = data['referral_other']
        values = (
            data['customer_name'],
            data['email'],
            data['contact_no'],
            data.get('company_name', ''),
            data['annual_salary'],
            data['loan_type'],
            data['salary_mode'],
            data['pincode'],
            referral
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

# Admin Routes - Login using JWT (Cookies)
from flask_jwt_extended import  set_access_cookies, unset_jwt_cookies

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if email == app.config['ADMIN_EMAIL'] and password == app.config['ADMIN_PASSWORD']:
        # Create JWT token
        access_token = create_access_token(identity=email)
        
        # Set token in cookies
        resp = jsonify({'success': True, 'redirect': '/admin/dashboard'})
        set_access_cookies(resp, access_token)
        return resp, 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/admin/check_auth')
@jwt_required()
def check_auth():
    return jsonify({'authenticated': True}), 200

@app.route('/admin/dashboard')
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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

@app.route('/admin/jobs')
@jwt_required()
def admin_jobs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM job_openings ORDER BY created_at DESC")
    jobs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_jobs.html', jobs=jobs)

@app.route('/admin/jobs/add', methods=['POST'])
@jwt_required()
def admin_add_job():
    data = request.json
    title = data.get('title')
    department = data.get('department')
    location = data.get('location', 'Remote / Hybrid')
    job_type = data.get('type', 'Full-time')
    responsibilities = data.get('responsibilities', '')
    requirements = data.get('requirements', '')
    
    if not title or not department:
         return jsonify({'error': 'Title and Department are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO job_openings (title, department, location, type, responsibilities, requirements)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (title, department, location, job_type, responsibilities, requirements))
        conn.commit()
        return jsonify({'success': True}), 201
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/jobs/delete/<int:job_id>', methods=['DELETE'])
@jwt_required()
def admin_delete_job(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM job_openings WHERE id = %s", (job_id,))
        conn.commit()
        return jsonify({'success': True}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
         cursor.close()
         conn.close()


@app.route('/admin/logout')
def admin_logout():
    resp = redirect(url_for('home'))
    unset_jwt_cookies(resp)
    return resp

if __name__ == '__main__':
    app.run(debug=True, port=5000)
