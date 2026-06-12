import os
import sqlite3
import smtplib
import time
import difflib
import re
import platform  # Added for OS detection
from datetime import datetime, date
from email.message import EmailMessage

from flask import Flask, g, render_template, request, redirect, url_for, flash, jsonify, session, render_template_string
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from itsdangerous import URLSafeTimedSerializer
from twilio.rest import Client

from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_sqlalchemy import SQLAlchemy
from flask_admin.menu import MenuLink

# --- OCR CONFIGURATION ---
OCR_AVAILABLE = False
try:
    from PIL import Image, ImageEnhance, ImageFilter
    import pytesseract
    
    # Check if we are on Windows (local) or Linux (server)
    if platform.system() == "Windows":
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    else:
        # Standard path for Tesseract on Linux deployments
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        
    OCR_AVAILABLE = True
except ImportError:
    print("⚠️ OCR Warning: PIL or pytesseract not installed.")
except Exception as e:
    print(f"⚠️ OCR Warning: Tesseract setup error. {e}")

load_dotenv()

# --- APP CONFIGURATION ---
DATABASE = 'medicare.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or 'devsecret'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, DATABASE)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['FLASK_ADMIN_SWATCH'] = 'flatly'
app.config['FLASK_ADMIN_FLUID_LAYOUT'] = True

db_sqla = SQLAlchemy(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
TWILIO_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_FROM = os.getenv('TWILIO_WHATSAPP_NUMBER')

# 1. BRAND NAME MAPPING
BRAND_MAP = {
    'dolo': 'paracetamol', 'calpol': 'paracetamol', 'crocin': 'paracetamol', 'tylenol': 'paracetamol',
    'combiflam': 'ibuprofen_paracetamol', 'flexon': 'ibuprofen_paracetamol',
    'zerodol': 'aceclofenac', 'zerodol-p': 'aceclofenac', 'zerodol-sp': 'aceclofenac_serratio',
    'meftal': 'mefenamic_acid', 'meftal-spas': 'dicyclomine', 'disprin': 'aspirin', 'ecosprin': 'aspirin',
    'brufen': 'ibuprofen', 'advil': 'ibuprofen', 'volini': 'diclofenac_gel',
    'augmentin': 'amoxiclav', 'moxikind-cv': 'amoxiclav', 'clam': 'amoxiclav',
    'azithral': 'azithromycin', 'aziwok': 'azithromycin',
    'taxim': 'cefixime', 'zipod': 'cefixime', 'monocef': 'ceftriaxone',
    'ciplox': 'ciprofloxacin', 'floxip': 'ciprofloxacin',
    'doxy': 'doxycycline', 'septran': 'cotrimoxazole',
    'benadryl': 'diphenhydramine', 'zeet': 'diphenhydramine',
    'ascoril': 'expectorant_syrup', 'ascoril-d': 'dextromethorphan',
    'grillinctus': 'cough_syrup', 'corex': 'chlorpheniramine_codeine',
    'alex': 'cough_syrup', 'tusq': 'cough_syrup',
    'cheston-cold': 'cetirizine_phenylephrine', 'maxtra': 'phenylephrine_chlorpheniramine',
    'otrivin': 'xylometazoline_drops', 'nasivion': 'oxymetazoline_drops',
    'gelusil': 'antacid_syrup', 'digene': 'antacid_syrup', 'mucaine': 'anesthetic_antacid',
    'pan 40': 'pantoprazole', 'pan d': 'pantoprazole_domperidone', 'pantocid': 'pantoprazole',
    'omez': 'omeprazole', 'rantac': 'ranitidine', 'aciloc': 'ranitidine',
    'eno': 'sodium_bicarbonate', 'cremaffin': 'laxative_syrup', 'duphalac': 'lactulose_syrup',
    'allegra': 'fexofenadine', 'cetzine': 'cetirizine', 'okacet': 'cetirizine',
    'avil': 'pheniramine', 'montek-lc': 'montelukast_levocetirizine',
    'becosules': 'b_complex', 'neurobion': 'b_complex',
    'shelcal': 'calcium_d3', 'cipcal': 'calcium_d3',
    'zincovit': 'multivitamin', 'a-to-z': 'multivitamin',
    'limcee': 'vitamin_c', 'celin': 'vitamin_c',
    'evion': 'vitamin_e', 'liv-52': 'liver_supplement',
    'glycomet': 'metformin', 'januvia': 'sitagliptin',
    'thyronorm': 'levothyroxine', 'eltroxin': 'levothyroxine',
    'sorbate': 'isosorbide', 'viagra': 'sildenafil', 'manforce': 'sildenafil',
}

# 2. DRUG INTERACTION KNOWLEDGE BASE
INTERACTIONS_DB = {
    'aspirin': ['ibuprofen', 'warfarin', 'heparin', 'naproxen'],
    'ibuprofen': ['aspirin', 'naproxen', 'warfarin'],
    'paracetamol': ['warfarin', 'alcohol'], 
    'amoxiclav': ['methotrexate', 'birth_control_pills'],
    'azithromycin': ['antacids', 'warfarin'],
    'metformin': ['furosemide', 'alcohol'],
    'sildenafil': ['nitroglycerin', 'isosorbide', 'amyl nitrate'],
    'tramadol': ['antidepressants', 'ssri', 'alcohol'],
    'levothyroxine': ['calcium_d3', 'iron', 'antacids'],
    'doxycycline': ['milk', 'calcium_d3', 'antacids'],
    'cough_syrup': ['alcohol', 'sedatives', 'antidepressants'],
}

# 3. MEDICINE INFO DATABASE
MEDICINE_DB = {
    'paracetamol': "Paracetamol is a common pain reliever and fever reducer. Safe for most when taken as directed.",
    'ibuprofen': "Ibuprofen is an NSAID for pain and inflammation. Always take with food to avoid stomach upset.",
    'ibuprofen_paracetamol': "Combiflam/Flexon is a combination used for fever, muscle pain, and headache. Take with food.",
    'aceclofenac': "Aceclofenac (Zerodol) is a strong painkiller for arthritis and muscle pain. Avoid if you have kidney issues.",
    'aceclofenac_serratio': "Zerodol-SP contains a muscle relaxant and painkiller. Used for severe swelling and pain.",
    'mefenamic_acid': "Meftal is commonly used for menstrual cramps and stomach pain.",
    'dicyclomine': "Meftal-Spas is an antispasmodic used to treat stomach cramps and pain.",
    'amoxiclav': "Amoxiclav (Augmentin) is a broad-spectrum antibiotic. Complete the full course even if you feel better.",
    'azithromycin': "Azithromycin (Azithral) is an antibiotic for throat and chest infections. Take it 1 hour before food.",
    'cefixime': "Cefixime (Taxim-O) is a strong antibiotic for bacterial infections like typhoid or UTI.",
    'ciprofloxacin': "Ciprofloxacin is used for bacterial infections. Avoid taking with dairy products.",
    'diphenhydramine': "Benadryl is an antihistamine syrup for dry cough and allergies. It may cause drowsiness.",
    'expectorant_syrup': "Ascoril is an expectorant used for wet cough (cough with mucus). Drink plenty of water.",
    'cough_syrup': "General cough syrup (Grillinctus/Alex). Used for soothing throat irritation and cough.",
    'dextromethorphan': "Ascoril-D is a cough suppressant for dry coughs. Do not drive after taking.",
    'antacid_syrup': "Gelusil/Digene is a liquid antacid. Shake well before use. Takes relief in minutes for heartburn.",
    'pantoprazole': "Pan 40 is a PPI that reduces stomach acid. Take it empty stomach in the morning.",
    'pantoprazole_domperidone': "Pan-D treats acidity and nausea/vomiting. Take empty stomach.",
    'omeprazole': "Omez is used to treat indigestion and gastric ulcers. Take before meals.",
    'laxative_syrup': "Cremaffin/Duphalac is a syrup used to treat constipation. Take at night.",
    'b_complex': "Becosules is a Vitamin B-Complex supplement. Good for mouth ulcers and energy.",
    'calcium_d3': "Shelcal is a Calcium + Vitamin D3 supplement for bone health. Do not take with Iron.",
    'multivitamin': "Zincovit/A-to-Z helps boost immunity and energy. Contains Zinc and essential vitamins.",
    'vitamin_c': "Limcee/Celin (Vitamin C) boosts immunity and helps skin health.",
    'liver_supplement': "Liv-52 is a herbal supplement to support liver health and digestion.",
    'metformin': "Metformin is for Type 2 Diabetes to control blood sugar. Take with meals.",
    'levothyroxine': "Thyronorm is for thyroid hormone replacement. Take strictly on an empty stomach in the morning.",
    'sildenafil': "Sildenafil treats erectile dysfunction. ⚠️ DANGER: Never take with heart medicines (Nitrates).",
    'fexofenadine': "Allegra is a non-drowsy allergy medication for runny nose and sneezing.",
    'montelukast_levocetirizine': "Montek-LC is used for allergic rhinitis and asthma symptoms. usually taken at night.",
}

# 4. CHAT RESPONSES
CHAT_RESPONSES = {
    'donate': "To donate, go to the 'Donation Tracking' section and click 'Donate Medicine'. We accept unexpired strips.",
    'reminder': "You can add a reminder by clicking the '+ Add Reminder' button on your dashboard.",
    'ngo': "We have partnered with 10+ NGOs across India. Check the Map tab in the Donate section.",
    'contact': "You can reach support at help@medicare.com.",
    'hello': "Hi! I am your MediCare Assistant. Ask me about medicines or interactions!",
    'hi': "Hello! How can I help you today?",
    'expiry': "We strictly do not accept expired medicines. Please check the date before donating.",
    'thank': "You're welcome! Stay healthy.",
}

def get_generic_name(user_input):
    clean_input = user_input.lower().strip()
    if clean_input in BRAND_MAP:
        return BRAND_MAP[clean_input]
    
    all_keys = list(BRAND_MAP.keys()) + list(MEDICINE_DB.keys())
    matches = difflib.get_close_matches(clean_input, all_keys, n=1, cutoff=0.7)
    if matches:
        matched_term = matches[0]
        return BRAND_MAP.get(matched_term, matched_term)
    return clean_input

# ==========================================
#          FLASK & DATABASE SETUP
# ==========================================

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exc):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('PRAGMA foreign_keys = ON;')
        db.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, phone_number TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, medicine_name TEXT NOT NULL, dosage TEXT, reminder_time TEXT, reminder_date DATE, frequency TEXT DEFAULT 'daily', send_email INTEGER DEFAULT 1, last_sent DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''')
        db.execute('''CREATE TABLE IF NOT EXISTS donations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, medicine_name TEXT NOT NULL, expiry_date DATE, quantity INTEGER, location TEXT, contact TEXT, image_path TEXT, selected_ngo TEXT, status TEXT DEFAULT 'Pending Pickup', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS ngos (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, lat REAL, lng REAL, address TEXT, contact TEXT)''')
        
        if db.execute('SELECT COUNT(*) FROM ngos').fetchone()[0] == 0:
            ngos = [
                ('City Care NGO', 19.0760, 72.8777, 'Mumbai Central, Mumbai', '9898989898'),
                ('MediHelp Foundation', 28.6139, 77.2090, 'Connaught Place, New Delhi', '9797979797'),
                ('LifeSaver Trust', 12.9716, 77.5946, 'MG Road, Bangalore', '9696969696')
            ]
            db.executemany('INSERT INTO ngos (name, lat, lng, address, contact) VALUES (?,?,?,?,?)', ngos)
        db.commit()

init_db()

class User(UserMixin):
    def __init__(self, id, name, email, password_hash, phone_number):
        self.id, self.name, self.email, self.password_hash, self.phone_number = id, name, email, password_hash, phone_number

@login_manager.user_loader
def load_user(user_id):
    row = get_db().execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    return User(row['id'], row['name'], row['email'], row['password'], row['phone_number']) if row else None

def allowed_file(filename): 
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================
#      ADMIN PANEL MODELS & SETUP
# ==========================================

class AdminUser(db_sqla.Model):
    __tablename__ = 'users'
    id = db_sqla.Column(db_sqla.Integer, primary_key=True)
    name = db_sqla.Column(db_sqla.String)
    email = db_sqla.Column(db_sqla.String)
    phone_number = db_sqla.Column(db_sqla.String)
    created_at = db_sqla.Column(db_sqla.DateTime)

class AdminReminder(db_sqla.Model):
    __tablename__ = 'reminders'
    id = db_sqla.Column(db_sqla.Integer, primary_key=True)
    user_id = db_sqla.Column(db_sqla.Integer)
    medicine_name = db_sqla.Column(db_sqla.String)
    dosage = db_sqla.Column(db_sqla.String)
    reminder_time = db_sqla.Column(db_sqla.String)
    frequency = db_sqla.Column(db_sqla.String)

class AdminDonation(db_sqla.Model):
    __tablename__ = 'donations'
    id = db_sqla.Column(db_sqla.Integer, primary_key=True)
    user_id = db_sqla.Column(db_sqla.Integer)
    medicine_name = db_sqla.Column(db_sqla.String)
    quantity = db_sqla.Column(db_sqla.Integer)
    location = db_sqla.Column(db_sqla.String)
    status = db_sqla.Column(db_sqla.String)

class AdminNgo(db_sqla.Model):
    __tablename__ = 'ngos'
    id = db_sqla.Column(db_sqla.Integer, primary_key=True)
    name = db_sqla.Column(db_sqla.String)
    lat = db_sqla.Column(db_sqla.Float)
    lng = db_sqla.Column(db_sqla.Float)
    address = db_sqla.Column(db_sqla.String)
    contact = db_sqla.Column(db_sqla.String)

class SecureModelView(ModelView):
    def is_accessible(self):
        return session.get('admin_logged_in') is True

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin_login'))

class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        
        total_users = AdminUser.query.count()
        total_donations = AdminDonation.query.count()
        total_reminders = AdminReminder.query.count()
        total_ngos = AdminNgo.query.count()
        
        return self.render('admin/custom_index.html', 
                           total_users=total_users, 
                           total_donations=total_donations,
                           total_reminders=total_reminders,
                           total_ngos=total_ngos)

admin = Admin(app, name='MediCare Admin', index_view=MyAdminIndexView())
admin.add_link(MenuLink(name='Logout', category='', url='/admin-logout'))
admin.add_view(SecureModelView(AdminUser, db_sqla.session, name="Users"))
admin.add_view(SecureModelView(AdminReminder, db_sqla.session, name="Reminders"))
admin.add_view(SecureModelView(AdminDonation, db_sqla.session, name="Donations"))
admin.add_view(SecureModelView(AdminNgo, db_sqla.session, name="NGOs"))

def send_email(to_email, subject, body):
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD: return False
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            msg = EmailMessage()
            sender_with_name = f"Medicare <{EMAIL_ADDRESS}>"
            msg['Subject'], msg['From'], msg['To'] = subject, sender_with_name, to_email
            msg.set_content(body)
            smtp.send_message(msg)
        return True
    except: return False

def send_whatsapp(to_number, message_body):
    if not TWILIO_SID or not TWILIO_AUTH: return False
    try:
        Client(TWILIO_SID, TWILIO_AUTH).messages.create(from_=f"whatsapp:{TWILIO_FROM}", body=message_body, to=f"whatsapp:{to_number}")
        return True
    except: return False

def check_and_send_reminders():
    with app.app_context():
        print(f"⏰ Checking reminders... {datetime.now().strftime('%H:%M:%S')}")
        db = get_db()
        now = datetime.now()
        current_time_str = now.strftime('%H:%M')
        today_iso = date.today().isoformat()
        
        rows = db.execute('SELECT r.*, u.email, u.phone_number, u.name FROM reminders r LEFT JOIN users u ON r.user_id = u.id').fetchall()
        
        for r in rows:
            if not r['reminder_time'] or r['reminder_time'].strip() != current_time_str: continue
            if r['frequency'] == 'once' and r['reminder_date'] and r['reminder_date'] != today_iso: continue
            if r['last_sent'] and (now - datetime.fromisoformat(r['last_sent'])).total_seconds() < 60: continue

            sent = False
            if r['email'] and r['send_email']: 
                sent = send_email(r['email'], f"Reminder: {r['medicine_name']}", f"Hello {r['name']}, it's time to take your {r['medicine_name']} ({r['dosage']}).")
            if r['phone_number']: 
                sent = send_whatsapp(r['phone_number'], f"Hello {r['name']}, take {r['medicine_name']} ({r['dosage']}) now.")
            
            if sent:
                db.execute('UPDATE reminders SET last_sent=? WHERE id=?', (now.isoformat(), r['id']))
                db.commit()

# ==========================================
#                ROUTES
# ==========================================

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'admin' and password == 'medicare2026': 
            session['admin_logged_in'] = True
            return redirect('/admin/')
        else:
            flash('Invalid Admin Credentials', 'danger')
            
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head><title>Admin Login</title><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"></head>
    <body class="bg-dark d-flex justify-content-center align-items-center vh-100">
        <div class="card shadow-lg p-5" style="width: 400px; border-radius: 15px;">
            <h2 class="text-center mb-4 text-primary fw-bold">MediCare Admin</h2>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
              {% endif %}
            {% endwith %}

            <form method="POST">
                <div class="mb-3">
                    <label class="form-label text-muted fw-bold">Admin Username</label>
                    <input type="text" name="username" class="form-control form-control-lg" placeholder="e.g. admin" required>
                </div>
                <div class="mb-4">
                    <label class="form-label text-muted fw-bold">Master Password</label>
                    <input type="password" name="password" class="form-control form-control-lg" required>
                </div>
                <button type="submit" class="btn btn-primary btn-lg w-100 fw-bold">Login to Dashboard</button>
            </form>
        </div>
    </body>
    </html>
    ''')

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin-login')

@app.route('/')
def index():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = get_db().execute('SELECT * FROM users WHERE email=?', (request.form['email'].lower(),)).fetchone()
        if user and check_password_hash(user['password'], request.form['password']):
            login_user(User(user['id'], user['name'], user['email'], user['password'], user['phone_number']))
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        try:
            get_db().execute('INSERT INTO users (name, email, password, phone_number) VALUES (?,?,?,?)', 
                           (request.form['name'], request.form['email'].lower(), generate_password_hash(request.form['password']), '+91'+request.form.get('phone', '').strip()))
            get_db().commit()
            return redirect(url_for('login'))
        except: flash('Email exists', 'warning')
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    reminders = [dict(row) for row in db.execute('SELECT * FROM reminders WHERE user_id=? ORDER BY id DESC', (current_user.id,)).fetchall()]
    donations = [dict(row) for row in db.execute('SELECT * FROM donations WHERE user_id=? ORDER BY id DESC', (current_user.id,)).fetchall()]
    
    for d in donations:
        if isinstance(d['created_at'], str):
            try: d['created_at'] = datetime.strptime(d['created_at'], '%Y-%m-%d %H:%M:%S')
            except: pass 
    for r in reminders:
        if isinstance(r['created_at'], str):
            try: r['created_at'] = datetime.strptime(r['created_at'], '%Y-%m-%d %H:%M:%S')
            except: pass

    return render_template('dashboard.html', reminders=reminders, donations=donations)

@app.route('/reminders/add', methods=['GET','POST'])
@login_required
def add_reminder():
    if request.method == 'POST':
        db = get_db()
        raw_med_name = request.form['medicine_name']
        new_med_generic = get_generic_name(raw_med_name)
        
        existing_rows = db.execute('SELECT medicine_name FROM reminders WHERE user_id=?', (current_user.id,)).fetchall()
        warnings = []
        
        for row in existing_rows:
            existing_generic = get_generic_name(row['medicine_name'])
            if new_med_generic in INTERACTIONS_DB and existing_generic in INTERACTIONS_DB[new_med_generic]:
                 warnings.append(f"⚠️ DANGER: {raw_med_name.title()} interacts with {row['medicine_name'].title()}!")
            if existing_generic in INTERACTIONS_DB and new_med_generic in INTERACTIONS_DB[existing_generic]:
                 warnings.append(f"⚠️ DANGER: {row['medicine_name'].title()} interacts with {raw_med_name.title()}!")

        db.execute('INSERT INTO reminders (user_id, medicine_name, dosage, reminder_time, reminder_date, frequency, send_email) VALUES (?,?,?,?,?,?,?)',
                   (current_user.id, raw_med_name, request.form['dosage'], request.form['reminder_time'], request.form.get('reminder_date'), request.form.get('frequency'), 1 if request.form.get('send_email') else 0))
        db.commit()
        
        if warnings:
            for w in warnings: flash(w, 'warning')
        else:
            flash(f'Reminder set for {raw_med_name}.', 'success')
            
        return redirect(url_for('dashboard'))
    return render_template('add_reminder.html')

@app.route('/reminders/edit/<int:id>', methods=['GET','POST'])
@login_required
def edit_reminder(id):
    db = get_db()
    if request.method == 'POST':
        db.execute('UPDATE reminders SET medicine_name=?, dosage=?, reminder_time=?, reminder_date=?, frequency=?, send_email=? WHERE id=?',
                   (request.form['medicine_name'], request.form['dosage'], request.form['reminder_time'], request.form.get('reminder_date'), request.form['frequency'], 1 if request.form.get('send_email') else 0, id))
        db.commit()
        return redirect(url_for('dashboard'))
    r = db.execute('SELECT * FROM reminders WHERE id=? AND user_id=?', (id, current_user.id)).fetchone()
    return render_template('edit_reminder.html', r=r)

@app.route('/reminders/delete/<int:id>', methods=['POST'])
@login_required
def delete_reminder(id):
    get_db().execute('DELETE FROM reminders WHERE id=? AND user_id=?', (id, current_user.id)).connection.commit()
    return redirect(url_for('dashboard'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        token = s.dumps(email, salt='password-reset-salt')
        link = url_for('reset_password', token=token, _external=True)
        
        if send_email(email, "Password Reset", f"Click here to reset your password: {link}"):
            flash('Reset link sent to your email.', 'info')
        else:
            flash('Error sending email. Check server logs.', 'danger')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The reset link is invalid or expired.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        get_db().execute('UPDATE users SET password=? WHERE email=?', 
                         (generate_password_hash(request.form['password']), email)).connection.commit()
        flash('Password updated! You can now login.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

@app.route('/api/chat', methods=['POST'])
def chat_bot():
    user_msg = request.json.get('message', '').lower()
    
    # 1. 👇 CHECK CHAT_RESPONSES FIRST 👇
    for key, reply in CHAT_RESPONSES.items():
        if key in user_msg: 
            return jsonify({'response': reply})
    # -----------------------------------
    
    all_brands = list(BRAND_MAP.keys())
    all_generics = list(MEDICINE_DB.keys())
    all_terms = all_brands + all_generics

    found_meds_generic = []
    found_meds_display = []

    def add_med(term, is_correction=False):
        generic = BRAND_MAP.get(term, term)
        if generic not in found_meds_generic:
            found_meds_generic.append(generic)
            display = term.title()
            if is_correction: display += " (corrected)"
            found_meds_display.append(display)

    user_words = user_msg.split()
    for word in user_words:
        clean_word = word.strip(".,?!")
        if len(clean_word) < 4: continue
        
        if clean_word in all_terms:
            add_med(clean_word)
        else:
            matches = difflib.get_close_matches(clean_word, all_terms, n=1, cutoff=0.6)
            if matches: add_med(matches[0], is_correction=True)

    if len(found_meds_generic) >= 2:
        med1, med2 = found_meds_generic[0], found_meds_generic[1]
        conflict = False
        if med1 in INTERACTIONS_DB and med2 in INTERACTIONS_DB[med1]: conflict = True
        if med2 in INTERACTIONS_DB and med1 in INTERACTIONS_DB[med2]: conflict = True
        
        if conflict: return jsonify({'response': f"❌ **INTERACTION ALERT:** Do NOT take **{found_meds_display[0]}** with **{found_meds_display[1]}**."})
        else: return jsonify({'response': f"✅ **Safe:** No interaction found between **{found_meds_display[0]}** and **{found_meds_display[1]}**."})

    elif len(found_meds_generic) == 1:
        info = MEDICINE_DB.get(found_meds_generic[0])
        if info: return jsonify({'response': f"💊 **{found_meds_display[0]}:**\n{info}"})
        else: return jsonify({'response': f"I recognize **{found_meds_display[0]}**, but I don't have detailed info yet."})

    return jsonify({'response': "I didn't understand. Try typing the medicine name correctly (e.g., 'Dolo')."})

@app.route('/donate', methods=['GET', 'POST'])
@login_required
def donate():
    db = get_db()
    if request.method == 'POST':
        filename = None
        file = request.files.get('medicine_image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        db.execute('INSERT INTO donations (user_id, medicine_name, expiry_date, quantity, location, contact, image_path, selected_ngo, status) VALUES (?,?,?,?,?,?,?,?,?)',
                   (current_user.id, request.form['medicine_name'], request.form['expiry_date'], request.form['quantity'], request.form['location'], request.form['contact'], filename, request.form.get('selected_ngo'), 'Pending Pickup'))
        db.commit()
        flash('Donation recorded!', 'success')
        return redirect(url_for('dashboard'))
    ngos = [dict(row) for row in db.execute('SELECT * FROM ngos').fetchall()]
    return render_template('donate.html', ngos=ngos)

@app.route('/api/scan_medicine', methods=['POST'])
def scan_medicine():
    if 'file' not in request.files: return jsonify({'success': False, 'message': 'No file uploaded'})
    if not OCR_AVAILABLE: return jsonify({'success': False, 'message': 'OCR engine (Tesseract) is not installed on server.'})
    
    try:
        f = request.files['file']
        path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename))
        f.save(path)
        
        img = Image.open(path).convert('L')
        text = pytesseract.image_to_string(img)
        
        detected_med = None
        detected_expiry = None
        known_medicines = list(BRAND_MAP.keys()) + list(MEDICINE_DB.keys())
        
        lines = text.split('\n')
        for line in lines:
            cleaned_line = re.sub(r'(\d+)', r' \1 ', line) 
            
            if not detected_med:
                words = cleaned_line.split()
                for word in words:
                    clean_word = re.sub(r'[^a-zA-Z]', '', word).lower()
                    if len(clean_word) < 3: continue 
                    matches = difflib.get_close_matches(clean_word, known_medicines, n=1, cutoff=0.6)
                    if matches:
                        detected_med = matches[0].title() 
            
            date_match = re.search(r'\b(0[1-9]|1[0-2])[\/\-](20\d{2}|\d{2})\b', line)
            if date_match:
                detected_expiry = date_match.group(0)
            
            if not detected_expiry:
                text_date_match = re.search(r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[\s\-]?(20\d{2}|\d{2})\b', line.upper())
                if text_date_match:
                    detected_expiry = text_date_match.group(0)

        return jsonify({
            'success': True, 
            'medicine': detected_med, 
            'expiry': detected_expiry,
            'raw_text': text 
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/ngos')
def api_ngos(): return jsonify([dict(row) for row in get_db().execute('SELECT * FROM ngos').fetchall()])

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/api/due', methods=['GET'])
@login_required
def get_due_medications():
    now = datetime.now()
    current_time_str = now.strftime('%H:%M')
    today_iso = date.today().isoformat()
    
    db = get_db()
    rows = db.execute('''
        SELECT medicine_name, dosage, reminder_time, reminder_date, frequency 
        FROM reminders 
        WHERE user_id = ?
    ''', (current_user.id,)).fetchall()
    
    due_meds = []
    for r in rows:
        if r['reminder_time'] == current_time_str:
            if r['frequency'] == 'once' and r['reminder_date'] != today_iso:
                continue
            due_meds.append({
                'medicine_name': r['medicine_name'],
                'dosage': r['dosage']
            })
            
    return jsonify(due_meds)

@app.route('/firebase-messaging-sw.js')
def service_worker():
    return jsonify({})

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_and_send_reminders, trigger="interval", seconds=60)
    scheduler.start()
    
    try:
        app.run(debug=True, use_reloader=False) 
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()