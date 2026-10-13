# =============================================================================
# विभाग १: डेटाबेस स्कीमा, मायग्रेशन्स व इंडेक्सिंग (Core Setup & Database)
# =============================================================================
import csv
import io
import json
import os
import re
import secrets
import hmac
import hashlib
import urllib.parse
from datetime import date, datetime, timedelta
from contextlib import contextmanager
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for, send_file, Response
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import requests

# --- प्रश्न जनरेटर इंटीग्रेशन (पार्श्वभूमी ऑटोमेशन) ---
try:
    from ai_question_generator import AIQuestionGenerator, init_ai_generation_tables, SUBJECT_TOPIC_MAPPING
except Exception as e:
    AIQuestionGenerator = None
    SUBJECT_TOPIC_MAPPING = {}
    print(f"Generator Import Warning: {e}")

# --- सुरक्षित Google GenAI इम्पोर्ट (रेन्डर क्रॅश-प्रूफ) ---
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- सुरक्षित RAZORPAY इम्पोर्ट ---
try:
    import razorpay
except ImportError:
    razorpay = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "maha_police_master_platform_2026_safe_key_super_secure")
SECURITY_SALT = os.environ.get("LINK_SECURITY_SALT", "anti_tamper_police_salt_2026")

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- NEON POSTGRESQL POOLING व ५०० एरर-प्रूफ कनेक्शन ---
DATABASE_URL = os.environ.get("DATABASE_URL")
db_pool = None
try:
    if DATABASE_URL:
        db_pool = pool.ThreadedConnectionPool(minconn=1, maxconn=20, dsn=DATABASE_URL)
        print("✅ Neon PostgreSQL Threaded Connection Pool Ready!")
except Exception as e:
    print(f"❌ DB Pool Error: {e}")

@contextmanager
def get_db():
    conn = None
    try:
        if db_pool:
            conn = db_pool.getconn()
        else:
            conn = psycopg2.connect(DATABASE_URL)
        yield conn
    except Exception as err:
        if conn:
            conn.rollback()
        raise err
    finally:
        if conn and db_pool:
            db_pool.putconn(conn)
        elif conn:
            conn.close()

def setup_indexes():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_leads_test_score ON mock_test_leads(test_id, score);
                CREATE INDEX IF NOT EXISTS idx_leads_phone ON mock_test_leads(phone);
                CREATE INDEX IF NOT EXISTS idx_leads_cat_score ON mock_test_leads(test_id, caste_category, score);
                CREATE INDEX IF NOT EXISTS idx_questions_test_id ON questions (test_id);
                CREATE INDEX IF NOT EXISTS idx_tests_category_active ON test_papers (category, status);
            """)
            conn.commit()
            cur.close()
    except Exception as e:
        print(f"❌ Index error: {e}")

try:
    setup_indexes()
except Exception:
    pass

def generate_tamper_signature(data_str):
    return hmac.new(SECURITY_SALT.encode(), str(data_str).encode(), hashlib.sha256).hexdigest()[:12]

def verify_tamper_signature(data_str, sig):
    expected = generate_tamper_signature(data_str)
    return hmac.compare_digest(expected, sig)

def get_razorpay_client():
    if not razorpay:
        return None, ""
    
    key_id = (os.environ.get("RAZORPAY_KEY_ID") or "").strip()
    key_secret = (os.environ.get("RAZORPAY_KEY_SECRET") or "").strip()

    if not key_id or not key_secret:
        try:
            with get_db() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT setting_key, setting_value FROM academy_settings WHERE setting_key IN ('razorpay_key_id', 'razorpay_key_secret')")
                    for row in cur.fetchall():
                        val = (row['setting_value'] or "").strip()
                        if row['setting_key'] == 'razorpay_key_id' and val:
                            key_id = val
                        elif row['setting_key'] == 'razorpay_key_secret' and val:
                            key_secret = val
        except Exception:
            pass

    if not key_id:
        key_id = "rzp_test_TmenVmrQI8nTRA"
    if not key_secret:
        key_secret = "FfaDgcHGbqNKGd15kiI2TP7v"
      
    if key_id and key_secret:
        try:
            client = razorpay.Client(auth=(key_id, key_secret))
            return client, key_id
        except Exception as e:
            return None, key_id
            
    return None, ""

def init_master_db():
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''CREATE TABLE IF NOT EXISTS test_papers (
                    id SERIAL PRIMARY KEY,
                    test_title TEXT NOT NULL,
                    test_type TEXT DEFAULT 'Free',
                    test_fee REAL DEFAULT 0,
                    duration_minutes INTEGER DEFAULT 60,
                    status TEXT DEFAULT 'Active',
                    category TEXT DEFAULT 'free',
                    publish_at TIMESTAMP DEFAULT NULL,
                    sequence_order INTEGER DEFAULT 1,
                    is_deleted INTEGER DEFAULT 0
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    test_id INTEGER DEFAULT 1,
                    question TEXT NOT NULL,
                    opt_a TEXT NOT NULL,
                    opt_b TEXT NOT NULL,
                    opt_c TEXT NOT NULL,
                    opt_d TEXT NOT NULL,
                    correct TEXT NOT NULL,
                    explanation TEXT DEFAULT '',
                    is_deleted INTEGER DEFAULT 0
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS mock_test_leads (
                    id SERIAL PRIMARY KEY,
                    test_id INTEGER DEFAULT 1,
                    test_date TEXT NOT NULL,
                    student_name TEXT NOT NULL,
                    district TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    caste_category TEXT DEFAULT 'OPEN',
                    whatsapp_verified INTEGER DEFAULT 0,
                    payment_status TEXT DEFAULT 'Pending',
                    utr_number TEXT DEFAULT '',
                    score REAL DEFAULT 0,
                    total_marks INTEGER DEFAULT 0,
                    test_name TEXT NOT NULL,
                    answers_json TEXT DEFAULT '',
                    access_token TEXT DEFAULT '',
                    token_expires_at TEXT DEFAULT '',
                    is_used INTEGER DEFAULT 0,
                    device_fingerprint TEXT DEFAULT '',
                    razorpay_order_id TEXT DEFAULT '',
                    razorpay_payment_id TEXT DEFAULT '',
                    referred_by_phone TEXT DEFAULT '',
                    battle_partner_lead_id INTEGER DEFAULT 0,
                    time_taken_seconds INTEGER DEFAULT 0,
                    gst_amount REAL DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0
                )''')

                # सुरक्षित कॉलम मायग्रेशन्स
                cur.execute('''
                    ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS battle_partner_lead_id INTEGER DEFAULT 0;
                    ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS time_taken_seconds INTEGER DEFAULT 0;
                    ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS gst_amount REAL DEFAULT 0;
                ''')

                cur.execute('''CREATE TABLE IF NOT EXISTS shared_free_passes (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    unlocked_paid_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS student_registrations (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    first_visited_at TIMESTAMP NOT NULL DEFAULT NOW()
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS student_feedbacks (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER,
                    student_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    feedback_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS special_unlimited_attempts (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    student_name TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    added_on TEXT NOT NULL
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS special_free_pass (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    student_name TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    added_on TEXT NOT NULL
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS live_heartbeats (
                    session_id TEXT PRIMARY KEY,
                    last_seen TIMESTAMP DEFAULT NOW()
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS question_reports (
                    id SERIAL PRIMARY KEY,
                    question_id INTEGER,
                    test_id INTEGER,
                    report_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS blocked_numbers (
                    phone TEXT PRIMARY KEY,
                    reason TEXT DEFAULT '',
                    blocked_at TIMESTAMP DEFAULT NOW()
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS otp_verification_audit (
                    id SERIAL PRIMARY KEY,
                    phone TEXT NOT NULL,
                    otp_code TEXT NOT NULL,
                    action_type TEXT DEFAULT 'view_results',
                    verified_at TIMESTAMP DEFAULT NOW()
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS traffic_analytics (
                    id SERIAL PRIMARY KEY,
                    page_key TEXT NOT NULL,
                    visitor_ip TEXT,
                    visited_at TIMESTAMP DEFAULT NOW()
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS academy_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS custom_tabs (
                    id SERIAL PRIMARY KEY,
                    tab_key TEXT UNIQUE NOT NULL,
                    tab_label TEXT NOT NULL
                )''')

                defaults = [
                    ('site_status', 'active'),
                    ('qr_code_url', ''),
                    ('upi_mobile', '9921111960'),
                    ('admin_pass', 'admin2026'),
                    ('admin_phone', '9921111960'),
                    ('help_phone', '9921111960'),
                    ('help_address', 'महाराष्ट्र पोलीस भरती सराव केंद्र - कळे मेन रोड, आडूर, करवीर, कोल्हापूर'),
                    ('insta_link', 'https://instagram.com'),
                    ('yt_link', 'https://youtube.com'),
                    ('toppers_link', '/'),
                    ('wa_groups_multiline', 'https://chat.whatsapp.com/sampleGroup1'),
                    ('home_tab_order', 'live,paid,free,rapid,about,battle,docs,help'),
                    ('admin_tab_order', 'leads,payments,special,questions,power,launch,analytics,audit,blocked,leaderboard,feedback,notices,trash,settings'),
                    ('recruitment_pdf', ''),
                    ('eligibility_pdf', ''),
                    ('razorpay_key_id', 'rzp_test_TmenVmrQI8nTRA'),
                    ('razorpay_key_secret', 'FfaDgcHGbqNKGd15kiI2TP7v')
                ]
                for k, v in defaults:
                    cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO NOTHING", (k, v))

                cur.execute('SELECT COUNT(*) as count FROM test_papers WHERE is_deleted=0')
                if cur.fetchone()['count'] == 0:
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active', 'free', 1)")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) VALUES (2, '🔴 मिशन खाकी रविवार थेट महासंग्राम #१', 'Paid', 99, 60, 'Active', 'live', 1)")

                conn.commit()

                if 'init_ai_generation_tables' in globals() and init_ai_generation_tables:
                    try:
                        init_ai_generation_tables(conn)
                    except Exception as e_ai:
                        pass
    except Exception as e:
        print(f"Init DB Error: {e}")

init_master_db()
# =============================================================================
# विभाग २: ब्रँडिंग, नेव्हिगेशन, फोनबुक व पोर्टल माहिती टेम्पलेट्स (Front-end)
# =============================================================================

TERMS_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>नियम, अटी व कायदेशीर घोषणापत्र - महाराष्ट्र पोलीस भरती संभाव्य टेस्ट पोर्टल</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; padding: 25px 15px; line-height: 1.6; }
        .terms-container { max-width: 850px; margin: 0 auto; background: white; border-radius: 12px; padding: 35px 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.06); border-top: 5px solid #059669; }
        h1 { color: #065f46; font-size: 24px; margin-top: 0; }
        h2 { color: #1e293b; font-size: 16px; margin: 20px 0 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
        .notice-box { background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; margin: 15px 0 20px; color: #991b1b; font-size: 13.5px; border-radius: 0 6px 6px 0; }
        p, li { font-size: 13.5px; color: #475569; margin: 6px 0; }
        ul { padding-left: 20px; margin: 6px 0; }
        .back-link { display: inline-block; margin-top: 25px; background: #0284c7; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 13px; }
    </style>
</head>
<body>
<div class="terms-container">
    <h1>नियम, अटी व कायदेशीर घोषणापत्र (Terms & Conditions)</h1>
    <p><small>अद्यतन: ऑक्टोबर २०२६ | महाराष्ट्र पोलीस भरती संभाव्य टेस्ट पोर्टल</small></p>
    
    <div class="notice-box">
        <strong>शासकीय प्रतिनिधीत्वाचा स्पष्ट इन्कार:</strong><br>
        हे व्यासपीठ स्पर्धा परीक्षा सरावासाठीचे एक स्वतंत्र, खाजगी शैक्षणिक व्यासपीठ असून याचा महाराष्ट्र शासन, गृह विभाग, महाराष्ट्र पोलीस किंवा कोणत्याही अधिकृत भरती मंडळाशी थेट संबंध, प्रतिनिधित्व अथवा प्राधिकृतता नाही.
    </div>
    <h2>१. शैक्षणिक उद्देश व स्व-मूल्यमापन</h2>
    <p>या प्लॅटफॉर्मवरील सर्व सराव चाचण्या, प्रश्न, उत्तरपत्रिका आणि गुणवत्ता क्रमांक हे केवळ विद्यार्थ्यांच्या वैयक्तिक अभ्यासाच्या आणि स्व-मूल्यमापनाच्या मार्गदर्शनासाठी आहेत.</p>
    <h2>२. कडक नो-रिफंड पॉलिसी</h2>
    <p>डिजिटल उत्पादन (सराव चाचण्या व सविस्तर स्पष्टीकरण पत्रिका) त्वरित उपलब्ध होत असल्याने भरलेली कोणतीही फी परत (Refund) केली जाणार नाही.</p>
    <h2>३. कायदेशीर अधिकार क्षेत्र</h2>
    <p>कोणत्याही वादाच्या संदर्भात कायदेशीर अधिकार क्षेत्र कोल्हापूर जिल्हा न्यायालय, महाराष्ट्र राहील.</p>
    <a href="/" class="back-link">⬅ मुख्य सराव पोर्टलवर परत जा</a>
</div>
</body>
</html>'''

MAINTENANCE_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>पोर्टल मेंटेनन्स सुरू आहे</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { margin:0; background:#0b1329; color:#f1f5f9; font-family:'Poppins', sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; padding:20px; }
        .m-box { max-width:540px; background:#162036; border:2px solid #f59e0b; border-radius:16px; padding:35px 25px; text-align:center; box-shadow:0 15px 35px rgba(0,0,0,0.5); }
        h2 { color:#fbbf24; margin-top:0; font-size:22px; }
        p { color:#cbd5e1; font-size:14.5px; line-height:1.6; }
    </style>
</head>
<body>
<div class="m-box">
    <div style="font-size:45px; margin-bottom:10px;">🚧</div>
    <h2>महाराष्ट्र पोलीस भरती अतिसंभाव्य टेस्ट पोर्टलचे तांत्रिक काम सुरू आहे!</h2>
    <p>विद्यार्थ्यांना अधिक वेगवान अनुभव देण्यासाठी नियोजित तांत्रिक सुधारणा सुरू आहेत.</p>
    <p style="color:#34d399; font-weight:bold;">लवकरच ही वेबसाईट पूर्ण क्षमतेने सुरू होईल. खाकीच्या तयारीसाठी थोडा वेळ संयम ठेवा! ⚔️</p>
</div>
</body>
</html>'''

HOME_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>महाराष्ट्र पोलीस भरती अतिसंभाव्य टेस्ट पोर्टल २०२६</title>
    <link href="https://fonts.googleapis.com/css2?family=Baloo+Bhaina+2:wght@500;700;800&family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', 'Baloo Bhaina 2', sans-serif; transition: all 0.2s ease; }
        body { margin: 0; background: #0f172a; color: #f8fafc; padding: 12px; }
        .top-bar { max-width: 950px; margin: 0 auto 15px; display: flex; justify-content: space-between; align-items: center; background: #1e293b; padding: 12px 18px; border-radius: 12px; border: 1px solid #334155; }
        .badge-live { background: #ef4444; color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .box { max-width: 950px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 25px 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); border-top: 5px solid #10b981; }
        .hero-banner { text-align: center; margin-bottom: 22px; }
        .hero-banner h1 { margin: 0 0 8px; color: #34d399; font-size: 26px; font-weight: 800; }
        .quote-box { background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(6,95,70,0.2)); border-left: 4px solid #10b981; padding: 12px 16px; border-radius: 8px; font-size: 14.5px; color: #a7f3d0; font-weight: 600; margin-bottom: 20px; text-align: center; }
        
        .paid-hero-card { display: none; background: linear-gradient(135deg, rgba(245,158,11,0.15), rgba(15,23,42,0.95)); border: 2px solid #f59e0b; border-radius: 12px; padding: 20px; margin-bottom: 22px; text-align: center; }
        .paid-hero-card h3 { color: #fde047; margin: 0 0 10px; font-size: 21px; }
        .package-box { background: #0f172a; border-radius: 8px; padding: 14px; margin: 12px 0; border: 1.5px dashed #f59e0b; }

        .tabs-wrapper { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-bottom: 20px; }
        .tab-btn { background: #334155; color: #cbd5e1; border: 1.5px solid #475569; padding: 10px 16px; border-radius: 30px; font-size: 13px; font-weight: 700; cursor: pointer; }
        .tab-btn:hover, .tab-btn.active { background: #10b981; color: #022c22; border-color: #34d399; }
        .test-grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
        .test-card { background: #0f172a; border: 1.5px solid #334155; border-radius: 12px; padding: 18px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
        .test-title { margin: 0 0 6px; color: #f1f5f9; font-size: 17px; font-weight: 700; }
        .badge-free { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #059669; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .badge-paid-package { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #d97706; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .badge-rapid { background: rgba(59,130,246,0.2); color: #60a5fa; border: 1px solid #2563eb; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .btn-start { background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 10px 22px; border-radius: 8px; text-decoration: none; font-weight: 800; font-size: 13.5px; border:none; cursor:pointer; }
        .btn-pay-unlock { background: linear-gradient(135deg, #f59e0b, #d97706); color: #0f172a; padding: 10px 22px; border-radius: 8px; text-decoration: none; font-weight: 800; font-size: 13.5px; border:none; cursor:pointer; }
        .btn-locked { background: #334155; color: #94a3b8; padding: 10px 18px; border-radius: 8px; font-weight: bold; font-size: 12.5px; cursor: not-allowed; display: inline-block; }
        .section-box { display: none; background: #0f172a; border: 1.5px solid #334155; border-radius: 12px; padding: 22px; text-align: center; }
        .rank-table { width: 100%; border-collapse: collapse; margin-top: 15px; text-align: left; font-size: 13.5px; }
        .rank-table th, .rank-table td { padding: 10px 12px; border-bottom: 1px solid #334155; }
        .rank-table th { color: #34d399; }
        .doc-link { display: inline-block; background: #1e293b; color: #38bdf8; border: 1.5px solid #0284c7; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 13px; margin: 6px; }
        .footer { text-align: center; font-size: 12px; color: #64748b; margin-top: 25px; border-top: 1px solid #334155; padding-top: 15px; }
        
        .loading-modal { display: none; position: fixed; inset: 0; background: rgba(11,19,41,0.95); z-index: 9999; justify-content: center; align-items: center; padding: 15px; }
        .modal-content { background: #162036; border: 2px solid #10b981; border-radius: 16px; padding: 30px 20px; max-width: 480px; text-align: center; box-shadow: 0 15px 40px rgba(0,0,0,0.6); }
        .phonebook-btn { background: #0284c7; color: white; border: none; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: bold; }
    </style>
    <script>
        window.onpageshow = function(event) {
            var modal = document.getElementById('loadingNoticeModal');
            if (modal) modal.style.display = 'none';
        };

        // होम पेजवरून बाहेर पडताना विचारणा
        window.addEventListener('beforeunload', function (e) {
            e.preventDefault();
            e.returnValue = 'आपण टेस्ट पोर्टलवरून बाहेर पडू इच्छिता का?';
            return e.returnValue;
        });

        // फोनबुकमधून संपर्क निवड
        async function selectContact(targetId) {
            if ('contacts' in navigator && 'ContactsManager' in window) {
                try {
                    const contacts = await navigator.contacts.select(['tel'], {multiple: false});
                    if (contacts && contacts[0] && contacts[0].tel && contacts[0].tel.length > 0) {
                        let phoneNum = contacts[0].tel[0].replace(/[^0-9]/g, '').slice(-10);
                        document.getElementById(targetId).value = phoneNum;
                    }
                } catch (err) {}
            } else {
                alert("तुमचा ब्राऊझर थेट फोनबुक ॲक्सेसला सपोर्ट करत नाही. कृपया १० अंकी नंबर टाईप करा.");
            }
        }

        function filterTab(category, btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            if(btn) btn.classList.add('active');

            var paidCard = document.getElementById('paidHeroCard');
            if (paidCard) paidCard.style.display = (category === 'paid') ? 'block' : 'none';

            document.getElementById('testsContainer').style.display = 'none';
            document.getElementById('battleContainer').style.display = 'none';
            document.getElementById('docsContainer').style.display = 'none';
            document.getElementById('helpContainer').style.display = 'none';
            document.getElementById('aboutContainer').style.display = 'none';

            if (category === 'battle') {
                document.getElementById('battleContainer').style.display = 'block';
            } else if (category === 'docs') {
                document.getElementById('docsContainer').style.display = 'block';
            } else if (category === 'help') {
                document.getElementById('helpContainer').style.display = 'block';
            } else if (category === 'about') {
                document.getElementById('aboutContainer').style.display = 'block';
            } else {
                document.getElementById('testsContainer').style.display = 'grid';
                let visibleCount = 0;
                document.querySelectorAll('.test-card').forEach(card => {
                    const cardCat = card.getAttribute('data-cat') || 'free';
                    if (cardCat === category) {
                        card.style.display = 'flex';
                        visibleCount++;
                    } else {
                        card.style.display = 'none';
                    }
                });
                const noTestMsg = document.getElementById('noTestMsg');
                if (noTestMsg) noTestMsg.style.display = (visibleCount === 0) ? 'block' : 'none';
            }
        }

        let pendingTestUrl = '';
        function openLoadingNotice(url) {
            pendingTestUrl = url;
            document.getElementById('loadingNoticeModal').style.display = 'flex';
        }
        function proceedToTest() {
            if (pendingTestUrl) window.location.href = pendingTestUrl;
        }

        function inviteFriendWhatsApp() {
            const num = document.getElementById('friend_invite_phone').value.trim();
            if(!/^[6-9][0-9]{9}$/.test(num)) {
                alert("कृपया वैध १० अंकी मोबाईल नंबर टाका!");
                return;
            }
            const link = window.location.origin + "/?ref=" + num;
            const text = encodeURIComponent("मित्रा, महाराष्ट्र पोलीस भरती २०२६ ची अतिसंभाव्य टेस्ट सोडव आणि आपला संवर्ग रँक तपास: " + link);
            window.open("https://wa.me/91" + num + "?text=" + text, "_blank");
        }

        document.addEventListener('DOMContentLoaded', function() {
            const firstActive = document.querySelector('.tab-btn.active') || document.querySelector('.tab-btn');
            if (firstActive) firstActive.click();
        });
    </script>
</head>
<body>
<div id="loadingNoticeModal" class="loading-modal">
    <div class="modal-content">
        <h3 style="color:#34d399; margin:0 0 10px; font-size:20px;">🛡️ परीक्षा कक्ष सुरू होत आहे...</h3>
        <p style="color:#cbd5e1; font-size:14px; line-height:1.6; margin:0 0 20px;">
            ⏳ <b>महाराष्ट्र पोलीस भरती संभाव्य टेस्ट पोर्टलवर आपले स्वागत आहे!</b><br>आपले प्रश्नपत्र पेज लोड होत आहे, कृपया पुढे जाण्यासाठी बटण दाबा.
        </p>
        <button onclick="proceedToTest()" style="background:linear-gradient(135deg, #10b981, #059669); color:#022c22; border:none; padding:12px 28px; border-radius:8px; font-weight:800; font-size:15px; cursor:pointer; width:100%;">
            🚀 पुढे चला (कंटिन्यू) ➔
        </button>
    </div>
</div>

<div class="top-bar">
    <div style="font-weight:bold; font-size:13.5px; color:#a7f3d0; display:flex; align-items:center; gap:8px;">
        <span class="badge-live">LIVE</span> 🕒 81M मिशन खाकी २०२६ सराव कक्ष
    </div>
    <div style="display:flex; gap:12px; align-items:center;">
        <a href="/my_results" style="color:#38bdf8; font-size:12.5px; font-weight:bold; text-decoration:none; background:#0f172a; padding:6px 12px; border-radius:6px; border:1px solid #38bdf8;">👤 माझे जुने निकाल (OTP)</a>
        <span style="font-size:12px; color:#34d399; font-weight:bold;">👥 ऑनलाईन: {{ active_students_count }}</span>
    </div>
</div>

<div class="box">
    <div class="hero-banner">
        <h1>⚔️ महाराष्ट्र पोलीस भरती अतिसंभाव्य टेस्ट पोर्टल</h1>
        <div class="quote-box">
            🔥 "मैदानावर खाकीची जिद्द दाखवली, आता लेखी परीक्षेत तुमची तयारी किती आहे ते सिद्ध करा!" 🌟
        </div>
    </div>

    <!-- मित्राला थेट व्हॉट्सॲप आमंत्रण बॉक्स -->
    <div style="background:#0f172a; border:1.5px solid #38bdf8; border-radius:10px; padding:14px; margin-bottom:18px; text-align:center;">
        <span style="color:#38bdf8; font-weight:bold; font-size:14px;">📲 मित्राला थेट WhatsApp वर टेस्ट पाठवा:</span>
        <div style="display:flex; gap:8px; justify-content:center; margin-top:8px; flex-wrap:wrap;">
            <input type="tel" id="friend_invite_phone" placeholder="१० अंकी मोबाईल नंबर" maxlength="10" style="padding:8px; border-radius:6px; border:1px solid #475569; background:#1e293b; color:white; width:200px;">
            <button onclick="selectContact('friend_invite_phone')" class="phonebook-btn">📖 फोनबुक</button>
            <button onclick="inviteFriendWhatsApp()" style="background:#25D366; color:white; border:none; padding:8px 16px; border-radius:6px; font-weight:bold; cursor:pointer;">पाठवा ➔</button>
        </div>
    </div>

    <div id="paidHeroCard" class="paid-hero-card">
        <h3>🎯 अतिसंभाव्य महासंग्राम टेस्ट संच (Mission Khaki 2026)</h3>
        <p>🔥 <b>एका कप चहाच्या किमतीत १०० प्रश्नांची प्रश्नपत्रिका सोडवून राज्यात, जिल्ह्यात व संवर्गनिहाय रँक तपासा!</b><br>
        गेल्या भरतीत १ मार्काने खाकी वर्दी हुकली होती का? एका मार्काची किंमत १ वर्षाची मेहनत असते!</p>
        
        <div class="package-box">
            <span style="color:#fde047; font-weight:800; font-size:16px;">💎 फी: फक्त ₹९९ + १८% GST = ₹११६.८२ मध्ये महासंग्राम संच उपलब्ध!</span><br>
            <small style="color:#94a3b8;">सोमवार ते रविवार कधीही सोडवा आणि रविवारी संध्याकाळी ७:०० वाजता महा-निकाल पहा!</small>
        </div>
        <div style="background:#10b981; color:#022c22; font-weight:800; padding:6px 14px; border-radius:20px; font-size:12px; display:inline-block; margin-top:8px;">
            🎁 ऑफर: ३ मित्रांनी फ्री टेस्ट सबमिट केल्यास २ महासंग्राम टेस्ट्स १००% मोफत!
        </div>
    </div>

    <div class="tabs-wrapper">
        {% for tab_item in parsed_home_tabs %}
            <button class="tab-btn {{ 'active' if loop.first else '' }}" onclick="filterTab('{{ tab_item.key }}', this)">
                {{ tab_item.label }}
            </button>
        {% endfor %}
    </div>

    <div id="testsContainer" class="test-grid">
        {% for t in tests %}
        <div class="test-card" data-id="{{ t.id }}" data-type="{{ t.test_type }}" data-cat="{{ t.category or 'free' }}">
            <div>
                <h4 class="test-title">{{ t.test_title }}</h4>
                <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                    {% if t.category in ['live', 'paid'] %}
                        <span class="badge-paid-package">⭐ अतिसंभाव्य महासंग्राम टेस्ट (₹{{ t.test_fee }} + GST)</span>
                    {% elif t.test_type == 'Free' %}
                        <span class="badge-free">🟢 मोफत सराव</span>
                    {% else %}
                        <span class="badge-paid-package">⭐ स्पेशल संच</span>
                    {% endif %}
                    <span class="badge-rapid">⏱️ {{ t.duration_minutes }} मिनिटे</span>
                    {% if t.is_locked and t.category == 'rapid' %}
                    <span style="font-size:12px; color:#fbbf24;">⏳ पुढील टेस्ट दुसऱ्या दिवशी सकाळी १०:०० ला अनलॉक होईल</span>
                    {% endif %}
                </div>
            </div>
            <div>
                {% if t.is_locked %}
                    <span class="btn-locked">🔒 सकाळी १०:०० ला उघडेल</span>
                {% elif t.category in ['live', 'paid'] %}
                    <a href="/take_test/{{ t.id }}" class="btn-pay-unlock">🔓 अनलॉक करा / सोडवा</a>
                {% else %}
                    <button onclick="openLoadingNotice('/take_test/{{ t.id }}')" class="btn-start">🚀 टेस्ट सोडवा</button>
                {% endif %}
            </div>
        </div>
        {% endfor %}
        <div id="noTestMsg" style="display:none; text-align:center; padding:35px 20px; background:#0f172a; border-radius:12px; border:1px dashed #475569; color:#94a3b8; font-size:15px;">
            🎯 <b>लवकरच या विभागात नवीन अतिसंभाव्य सराव संच उपलब्ध होतील!</b>
        </div>
    </div>

    <!-- पोर्टल माहिती व भावनिक साद टॅब -->
    <div id="aboutContainer" class="section-box" style="text-align:left;">
        <h3 style="color:#34d399; margin-top:0;">📖 पोर्टलची वैशिष्ट्ये, कार्यपद्धती व भावनिक साद</h3>
        <p style="font-size:14px; color:#cbd5e1; line-height:1.7;">
            <b>१. रॅपिड फायर टेस्ट:</b> रोज सकाळी १० वाजता नवीन २० गुणांची गतिमान टेस्ट उपलब्ध होते. १ दिवस = १ टेस्ट या क्रमाने तुमचा अभ्यास तपासला जातो.<br>
            <b>२. मिशन खाकी महासंग्राम:</b> १०० गुणांची संपूर्ण पोलीस भरती पॅटर्न टेस्ट. सोमवार ते रविवार कधीही सोडवा आणि रविवारी संध्याकाळी ठीक ७:०० वाजता महाराष्ट्र राज्य रँक पहा.<br>
            <b>३. मित्राला चॅलेंज:</b> टेस्ट सोडवल्यानंतर मित्राला आव्हान देऊन कोणाचे गुण जास्त आणि कोण जलद हे तपासू शकता.
        </p>
        <div style="background:#162036; border-left:4px solid #f59e0b; padding:15px; border-radius:8px; margin-top:15px; color:#fde68a; font-size:13.5px; line-height:1.7;">
            ❤️ <b>आमची भावनिक साद:</b><br>
            "स्पर्धा परीक्षेतील प्रत्येक विद्यार्थ्याचे स्वप्न पूर्ण व्हावे यासाठी हे तंत्रज्ञान अत्यंत प्रामाणिकपणे, प्रचंड कष्ट व खर्च करून विकसित करण्यात आले आहे. 
            या पोर्टलवरील सशुल्क (Paid) टेस्ट्समधून मिळणाऱ्या नाममात्र शुल्कातील काही हिस्सा गरजू, होतकरू मुला-मुलींच्या शैक्षणिक मदतीसाठी वापरला जातो. 
            तुम्ही सशुल्क टेस्ट घेऊन स्वतःची तयारी तर सिद्ध करालच, शिवाय एका समाजकार्यातही हातभार लावाल! जय हिंद!"
        </div>
    </div>

    <div id="battleContainer" class="section-box">
        <h3 style="color:#f59e0b; margin-top:0;">🏆 राज्यस्तरीय जिल्हा मुकाबला (लाईव्ह लीड्स व सरासरी गुण)</h3>
        <table class="rank-table">
            <tr><th>रँक</th><th>जिल्हा</th><th>टेस्ट देणारे विद्यार्थी</th><th>सरासरी गुण</th></tr>
            {% for dist in live_district_battles %}
            <tr>
                <td><b>#{{ loop.index }}</b></td>
                <td><b>{{ dist.district }}</b></td>
                <td><span style="background:rgba(56,189,248,0.2); color:#38bdf8; padding:3px 8px; border-radius:12px; font-weight:bold;">{{ dist.total_students }}</span></td>
                <td style="color:#34d399; font-weight:bold;">{{ dist.avg_score }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div id="docsContainer" class="section-box">
        <h3 style="color:#38bdf8; margin-top:0;">📄 अधिकृत भरती कागदपत्रे व मागील प्रश्नपत्रिका</h3>
        {% if recruitment_pdf %}<a href="{{ recruitment_pdf }}" target="_blank" class="doc-link">📑 पोलीस भरती जाहिरात (PDF)</a>{% endif %}
        {% if eligibility_pdf %}<a href="{{ eligibility_pdf }}" target="_blank" class="doc-link">📋 शारीरिक व लेखी पात्रता (PDF)</a>{% endif %}
    </div>

    <div id="helpContainer" class="section-box">
        <h3 style="color:#34d399; margin-top:0;">📞 हेल्प डेस्क व विद्यार्थी तक्रार/अभिप्राय</h3>
        <p style="font-size:13.5px; color:#cbd5e1;">हेल्पलाईन: <b>{{ help_phone }}</b> | पत्ता: {{ help_address }}</p>
        <div style="background:#162036; padding:15px; border-radius:10px; max-width:500px; margin:15px auto; text-align:left;">
            <h4 style="margin:0 0 8px; color:#38bdf8;">📝 आपली समस्या किंवा अभिप्राय नोंदवा:</h4>
            <form method="POST" action="/submit_help_desk">
                <input type="text" name="name" placeholder="तुमचे नाव" required style="width:100%; padding:8px; margin-bottom:8px; border-radius:6px; background:#0f172a; border:1px solid #334155; color:white;">
                <input type="tel" name="phone" id="help_phone_input" placeholder="१० अंकी व्हॉट्सॲप नंबर" maxlength="10" required style="width:100%; padding:8px; margin-bottom:8px; border-radius:6px; background:#0f172a; border:1px solid #334155; color:white;">
                <textarea name="feedback" rows="3" placeholder="आपली अडचण येथे सविस्तर लिहा..." required style="width:100%; padding:8px; margin-bottom:8px; border-radius:6px; background:#0f172a; border:1px solid #334155; color:white;"></textarea>
                <button type="submit" style="background:#10b981; color:#022c22; font-weight:bold; border:none; padding:10px 18px; border-radius:6px; cursor:pointer; width:100%;">🚀 तक्रार/अभिप्राय पाठवा</button>
            </form>
        </div>
    </div>

    <div class="footer">
        <span>© २०२६ महाराष्ट्र पोलीस भरती संभाव्य टेस्ट पोर्टल | </span>
        <a href="/terms-and-conditions" target="_blank" style="color:#38bdf8;">नियम व अटी (Terms & Conditions)</a>
    </div>
</div>
</body>
</html>'''
# =============================================================================
# विभाग ३: परीक्षा कक्ष, टॅब चेतावणी, सुरक्षित प्रयत्न व निकाल टेम्पलेट्स
# =============================================================================

EXAM_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ test.test_title }} - परीक्षा कक्ष</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #0b1329; color: #f1f5f9; padding: 10px; user-select: none; }
        .exam-header { background: #1e293b; color: white; padding: 12px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; max-width: 850px; margin: 0 auto 15px; position: sticky; top: 10px; z-index: 100; border: 1.5px solid #334155; }
        .timer-box { background: rgba(239,68,68,0.2); border: 1.5px solid #ef4444; color: #fca5a5; padding: 6px 14px; border-radius: 8px; font-weight: 800; font-size: 15px; }
        .btn-exit-home { background: #475569; color: white; border: none; padding: 8px 14px; border-radius: 6px; font-size: 12.5px; font-weight: bold; cursor: pointer; }
        .box { max-width: 850px; margin: 0 auto; background: #162036; border-radius: 16px; padding: 25px; border: 1px solid #334155; }
        .q-item { background: #0f172a; border: 1.5px solid #27354f; border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; }
        .q-text { font-weight: 700; margin-bottom: 14px; font-size: 16px; color: #f8fafc; }
        .opt-label { display: flex; align-items: center; margin-bottom: 10px; font-size: 14.5px; cursor: pointer; background: #1e293b; padding: 12px 16px; border-radius: 10px; border: 1.5px solid #334155; color: #cbd5e1; }
        .opt-label:hover { background: #27354f; border-color: #38bdf8; }
        .opt-label input[type="radio"] { margin-right: 12px; width: 18px; height: 18px; accent-color: #10b981; }
        .bottom-submission-card { background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(15,23,42,0.9)); border: 2px solid #10b981; border-radius: 14px; padding: 22px; margin-top: 30px; }
        .bottom-submission-card input, .bottom-submission-card select { width: 100%; padding: 12px; background: #0f172a; border: 1.5px solid #334155; border-radius: 8px; margin-bottom: 12px; color: white; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 15px; border: none; border-radius: 8px; font-size: 17px; font-weight: 800; cursor: pointer; }
    </style>
    <script>
        let isFormSubmitted = false;
        let testStartTime = Date.now();

        function exitToHome() {
            if (confirm("तुम्ही परीक्षा सोडून होम पेजवर जाऊ इच्छिता का? सोडवलेली उत्तरे सुरक्षित राहतील व पुन्हा सोडवता येतील.")) {
                isFormSubmitted = true;
                window.location.replace('/');
            }
        }

        // टॅब बदलल्यास फक्त चेतावणी पॉपअप
        document.addEventListener('visibilitychange', function() {
            if (document.hidden && !isFormSubmitted) {
                alert("⚠️ चेतावणी: कृपया वारंवार टॅब बदलू नका! अन्यथा तुमची टेस्ट ऑटोमॅटिक बंद पडेल.");
            }
        });

        const timerStorageKey = 'police_timer_{{ test.id }}';
        let savedTime = localStorage.getItem(timerStorageKey);
        let timeLeft = savedTime !== null ? parseInt(savedTime, 10) : {{ test.duration_minutes * 60 }};

        function startTimer() {
            const timerDisplay = document.getElementById('time-left');
            let timer = setInterval(function () {
                let m = parseInt(timeLeft / 60, 10);
                let s = parseInt(timeLeft % 60, 10);
                timerDisplay.innerText = (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
                localStorage.setItem(timerStorageKey, timeLeft);

                if (--timeLeft < 0) {
                    clearInterval(timer);
                    alert("⏰ वेळ संपली! तुमची टेस्ट सबमिट होत आहे.");
                    isFormSubmitted = true;
                    localStorage.removeItem(timerStorageKey);
                    document.getElementById("examForm").submit();
                }
            }, 1000);
        }

        async function selectPhonebook(id) {
            if ('contacts' in navigator && 'ContactsManager' in window) {
                try {
                    const c = await navigator.contacts.select(['tel'], {multiple: false});
                    if (c && c[0] && c[0].tel) {
                        document.getElementById(id).value = c[0].tel[0].replace(/[^0-9]/g, '').slice(-10);
                        validateAndReady();
                    }
                } catch(e) {}
            }
        }

        function validateAndReady() {
            const name = document.getElementById('s_name').value.trim();
            const dist = document.getElementById('s_dist').value.trim();
            const phone = document.getElementById('s_phone').value.trim();
            const submitBtn = document.getElementById('submitBtn');
            if (name !== "" && dist !== "" && /^[6-9][0-9]{9}$/.test(phone)) {
                submitBtn.disabled = false;
                submitBtn.innerText = "🏆 टेस्ट सबमिट करा व निकाल पहा";
                submitBtn.style.opacity = "1";
            } else {
                submitBtn.disabled = true;
                submitBtn.innerText = "⚠️ नाव, जिल्हा व १० अंकी WhatsApp नंबर भरा";
                submitBtn.style.opacity = "0.6";
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('examForm').addEventListener('submit', function() {
                isFormSubmitted = true;
                localStorage.removeItem(timerStorageKey);
                let timeTaken = Math.floor((Date.now() - testStartTime) / 1000);
                document.getElementById('time_taken_input').value = timeTaken;
            });
        });

        window.onload = function() {
            startTimer();
            validateAndReady();
        };
    </script>
</head>
<body>
<div class="exam-header">
    <div>
        <h3 style="margin:0; font-size:16.5px; color:#34d399;">⚔️ {{ test.test_title }}</h3>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
        <div class="timer-box">⏳ <span id="time-left">00:00</span></div>
        <button onclick="exitToHome()" class="btn-exit-home">🏠 बाहेर पडा</button>
    </div>
</div>

<div class="box">
    <form id="examForm" method="POST" action="/submit_test/{{ test.id }}">
        <input type="hidden" name="time_taken_seconds" id="time_taken_input" value="0">
        <input type="hidden" name="battle_partner_id" value="{{ battle_partner_id or 0 }}">
        <div id="questionsArea">
            {% for q in questions %}
            <div class="q-item">
                <div class="q-text">प्र. {{ loop.index }}. {{ q.question }}</div>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="A"> A) {{ q.opt_a }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="B"> B) {{ q.opt_b }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="C"> C) {{ q.opt_c }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="D"> D) {{ q.opt_d }}</label>
            </div>
            {% endfor %}
        </div>

        <div class="bottom-submission-card">
            <h3 style="margin:0 0 10px; color:#34d399; font-size:18px;">🎯 निकाल व संवर्ग रँकसाठी माहिती भरा:</h3>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
                <div><label>पूर्ण नाव *:</label><input type="text" name="student_name" id="s_name" onkeyup="validateAndReady()" required></div>
                <div><label>जिल्हा *:</label><input type="text" name="district" id="s_dist" onkeyup="validateAndReady()" required></div>
                <div>
                    <label>प्रवर्ग *:</label>
                    <select name="caste_category" id="s_cat" required>
                        <option value="OPEN">OPEN</option><option value="OBC">OBC</option>
                        <option value="EWS">EWS</option><option value="SC">SC</option>
                        <option value="ST">ST</option><option value="VJ/NT">VJ/NT</option>
                    </select>
                </div>
                <div>
                    <label>WhatsApp मोबाईल नंबर *:</label>
                    <div style="display:flex; gap:4px;">
                        <input type="tel" name="phone" id="s_phone" maxlength="10" onkeyup="validateAndReady()" required>
                        <button type="button" onclick="selectPhonebook('s_phone')" style="background:#0284c7; color:white; border:none; border-radius:6px; padding:0 8px; cursor:pointer;">📖</button>
                    </div>
                </div>
            </div>
        </div>
        <button type="submit" id="submitBtn" class="btn-submit" disabled>⚠️ नाव, जिल्हा व WhatsApp नंबर भरा</button>
    </form>
</div>
</body>
</html>'''

ACCESS_CHECK_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>सशुल्क टेस्ट प्रवेश द्वार - {{ test.test_title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        body { font-family:'Poppins', sans-serif; background:#0b1329; color:#f1f5f9; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }
        .box { max-width:480px; width:100%; background:#162036; border-radius:16px; padding:25px; border-top:6px solid #10b981; }
        input { width:100%; padding:11px; background:#0f172a; border:1.5px solid #334155; border-radius:8px; margin-bottom:12px; color:white; }
        .btn-rzp { width:100%; background:linear-gradient(135deg, #2563eb, #1d4ed8); color:white; padding:14px; border:none; border-radius:8px; font-weight:800; cursor:pointer; font-size:15px; margin-bottom:15px; }
        .fear-banner { background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 14px; margin-bottom: 15px; font-size: 13px; color: #991b1b; }
    </style>
</head>
<body>
<div class="box">
    <a href="/" style="color:#38bdf8; text-decoration:none; font-size:13px; font-weight:bold;">⬅ मुख्य सराव पोर्टलवर परत जा</a>
    <div class="fear-banner">
        🔥 <b>एका कप चहाच्या किमतीत १०० प्रश्नांची महासंग्राम टेस्ट!</b><br>
        आज ₹९९ वाचवून रिस्क घेऊ नका, अतिसंभाव्य १०० प्रश्न आत्ताच सोडवून गुणवत्ता यादीत आपले स्थान निश्चित करा!
    </div>
    <h2 style="color:#34d399; text-align:center; margin:0 0 5px; font-size:20px;">🔒 अतिसंभाव्य महासंग्राम टेस्ट प्रवेश द्वार</h2>
    <p style="text-align:center; font-size:13px; color:#94a3b8; margin:0 0 15px;">
        {{ test.test_title }}<br>
        फी: ₹{{ test.test_fee }} + १८% GST (₹{{ gst_amount }}) = <b>₹{{ total_fee }}</b> (वैधता: ९० दिवस)
    </p>

    <div style="text-align:center;">
        <button id="rzp-button" class="btn-rzp">⚡ GooglePay / PhonePe द्वारे त्वरित पे करा (₹{{ total_fee }})</button>
    </div>

    {% if upi_mobile or qr_url %}
    <div style="background:#0f172a; padding:12px; border-radius:8px; border:1px solid #f59e0b; text-align:center; margin-bottom:15px;">
        {% if upi_mobile %}<p style="margin:0 0 6px; font-weight:bold; color:#fbbf24; font-size:12.5px;">किंवा QR स्कॅन करून <b>{{ upi_mobile }}</b> वर पे करा:</p>{% endif %}
        {% if qr_url %}<img src="{{ qr_url }}" alt="QR" style="max-width:130px; max-height:130px; border-radius:6px;">{% endif %}
    </div>
    {% endif %}

    <form method="POST" action="/request_paid_test/{{ test.id }}">
        <input type="text" name="student_name" placeholder="पूर्ण नाव" required>
        <input type="text" name="district" placeholder="जिल्हा" required>
        <input type="tel" name="student_phone" placeholder="परीक्षेचा १० अंकी WhatsApp नंबर" maxlength="10" required>
        <button type="submit" style="width:100%; background:#10b981; color:#022c22; padding:12px; border:none; border-radius:8px; font-weight:800; cursor:pointer;">🚀 मॅन्युअल स्क्रीनशॉट पाठवला आहे</button>
    </form>
</div>
<script>
document.getElementById('rzp-button').onclick = function(e){
    fetch('/create_razorpay_order/{{ test.id }}', {method: 'POST'})
    .then(res => res.json())
    .then(data => {
        if (data.error) { alert("⚠️ " + data.error); return; }
        var options = {
            "key": data.key_id, "amount": data.amount, "currency": "INR",
            "name": "महाराष्ट्र पोलीस भरती अतिसंभाव्य टेस्ट पोर्टल",
            "description": "{{ test.test_title }}", "order_id": data.order_id,
            "handler": function (response){
                window.location.href = "/verify_razorpay_payment?order_id=" + response.razorpay_order_id + "&payment_id=" + response.razorpay_payment_id + "&test_id={{ test.id }}";
            },
            "theme": { "color": "#10b981" }
        };
        var rzp1 = new Razorpay(options);
        rzp1.open();
    });
    e.preventDefault();
}
</script>
</body>
</html>'''
# =============================================================================
# विभाग ४: महासंग्राम साप्ताहिक सायकल, GST व २ मित्रांमधील मुकाबला (Battle)
# =============================================================================

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    token = request.args.get('token')
    battle_partner_id = request.args.get('battle_id', 0)
    current_phone = session.get('user_phone', '')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ब्लॉक तपासणी
            if current_phone:
                cur.execute("SELECT phone FROM blocked_numbers WHERE phone=%s", (current_phone,))
                if cur.fetchone():
                    return "<h3 style='color:#ef4444; text-align:center; padding:40px;'>⚠️ तुमचा मोबाईल नंबर प्रशासकीय कारणास्तव ब्लॉक करण्यात आला आहे!</h3>", 403

            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
            if not test:
                return "<h3 style='color:#ef4444; text-align:center; padding:40px;'>टेस्ट सापडली नाही!</h3>", 404

            is_paid_test = (test.get('category') in ['paid', 'live'] or test.get('test_type') == 'Paid' or float(test.get('test_fee') or 0) > 0)

            # मोफत टेस्ट थेट सुरू
            if not is_paid_test:
                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
                return render_template_string(EXAM_TEMPLATE, test=test, questions=questions, battle_partner_id=battle_partner_id)

            # सशुल्क/महासंग्राम पडताळणी
            # १. रेफरल पास तपासणी
            has_free_pass = False
            if current_phone:
                cur.execute("SELECT unlocked_paid_count FROM shared_free_passes WHERE phone=%s", (current_phone,))
                p_row = cur.fetchone()
                if p_row and p_row['unlocked_paid_count'] >= 2:
                    has_free_pass = True

            # २. टोकन तपासणी (९० दिवस वैधता)
            token_valid = False
            if token:
                cur.execute("SELECT * FROM mock_test_leads WHERE access_token=%s AND payment_status='Approved' AND is_deleted=0", (token,))
                lead = cur.fetchone()
                if lead:
                    if lead.get('token_expires_at'):
                        exp = datetime.strptime(str(lead['token_expires_at']).split('.')[0], "%Y-%m-%d %H:%M:%S")
                        if datetime.now() <= exp:
                            token_valid = True

            if has_free_pass or token_valid:
                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
                return render_template_string(EXAM_TEMPLATE, test=test, questions=questions, battle_partner_id=battle_partner_id)

            # थेट प्रवेश रोखणे व GST सह पेमेंट स्क्रीन दाखवणे
            base_fee = float(test.get('test_fee') or 99.0)
            gst_amount = round(base_fee * 0.18, 2)
            total_fee = round(base_fee + gst_amount, 2)

            cur.execute("SELECT setting_key, setting_value FROM academy_settings WHERE setting_key IN ('upi_mobile', 'qr_code_url')")
            s_map = {r['setting_key']: r['setting_value'] for r in cur.fetchall()}

            return render_template_string(
                ACCESS_CHECK_TEMPLATE,
                test=test,
                gst_amount=gst_amount,
                total_fee=total_fee,
                upi_mobile=s_map.get('upi_mobile', '9921111960'),
                qr_url=s_map.get('qr_code_url', '')
            )

@app.route('/create_razorpay_order/<int:test_id>', methods=['POST'])
def create_razorpay_order(test_id):
    client, key_id = get_razorpay_client()
    if not client or not key_id:
        return jsonify({"error": "Razorpay Keys सेट केलेल्या नाहीत!"}), 400
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT test_fee FROM test_papers WHERE id=%s", (test_id,))
                t_row = cur.fetchone()
                base_fee = float(t_row['test_fee']) if t_row else 99.0
        total_fee = round(base_fee * 1.18, 2)
        amount_paise = int(total_fee * 100)
        order = client.order.create({
            "amount": amount_paise, "currency": "INR",
            "receipt": f"rcpt_{test_id}_{int(datetime.now().timestamp())}",
            "payment_capture": 1
        })
        return jsonify({"order_id": order['id'], "amount": amount_paise, "key_id": key_id})
    except Exception as e:
        return jsonify({"error": f"पेमेंट एरर: {str(e)}"}), 500

@app.route('/verify_razorpay_payment')
def verify_razorpay_payment():
    order_id = request.args.get('order_id')
    payment_id = request.args.get('payment_id')
    test_id = request.args.get('test_id')
    token = secrets.token_hex(8)
    # ९० दिवसांची (३ महिने) वैधता
    expires = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, access_token, token_expires_at, razorpay_order_id, razorpay_payment_id, test_name, is_used)
                VALUES (%s, %s, 'Paid Candidate', 'Maharashtra', '9999999999', 'Approved', %s, %s, %s, %s, 'Paid Mock Pack', 0)
            """, (test_id, date.today().strftime("%Y-%m-%d"), token, expires, order_id, payment_id))
            conn.commit()

    return redirect(f"/take_test/{test_id}?token={token}")
    # =============================================================================
# विभाग ५: व्हायरल रेफरल इंजिन, निकाल व २४ तास व्हॉट्सॲप मेसेज
# =============================================================================

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    try:
        student_name = request.form.get('student_name', '').strip()
        district = request.form.get('district', '').strip()
        caste_category = request.form.get('caste_category', 'OPEN').strip().upper()
        phone = request.form.get('phone', '').strip()
        time_taken = int(request.form.get('time_taken_seconds', 0) or 0)
        battle_partner_id = int(request.form.get('battle_partner_id', 0) or 0)
        referred_by = session.get('referred_by', '')

        if not re.match(r'^[6-9]\d{9}$', phone):
            return "<h3 style='color:red; text-align:center;'>अवैध मोबाईल नंबर!</h3>", 400

        session['user_phone'] = phone

        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # ब्लॉक तपासणी
                cur.execute("SELECT phone FROM blocked_numbers WHERE phone=%s", (phone,))
                if cur.fetchone():
                    return "<h3 style='color:red; text-align:center;'>नंबर ब्लॉक आहे!</h3>", 403

                cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
                test = cur.fetchone()
                if not test: return "Test not found", 404

                cur.execute("SELECT id, question, correct FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()

                score = 0
                total = len(questions)
                user_answers = {}

                sub_scores = {
                    "मराठी व्याकरण व शब्दसंपदा": {"score": 0, "total": 0},
                    "अंकगणित": {"score": 0, "total": 0},
                    "बुद्धिमत्ता चाचणी": {"score": 0, "total": 0},
                    "सामान्य अध्ययन व चालू घडामोडी": {"score": 0, "total": 0}
                }

                for idx, q in enumerate(questions, 1):
                    ans = request.form.get(f"q_{q['id']}", "")
                    user_answers[str(q['id'])] = ans
                    is_cr = (ans == q['correct'])
                    if is_cr: score += 1

                    if idx <= 25: s_key = "मराठी व्याकरण व शब्दसंपदा"
                    elif idx <= 50: s_key = "अंकगणित"
                    elif idx <= 75: s_key = "बुद्धिमत्ता चाचणी"
                    else: s_key = "सामान्य अध्ययन व चालू घडामोडी"

                    sub_scores[s_key]["total"] += 1
                    if is_cr: sub_scores[s_key]["score"] += 1

                t_date = date.today().strftime("%Y-%m-%d")
                ans_json_str = json.dumps(user_answers)
                result_token = secrets.token_hex(10)

                # सबमिशन झाल्यावरच is_used=1 (सुरक्षित ऑटो-लॉक)
                cur.execute("""
                    INSERT INTO mock_test_leads (test_id, test_date, student_name, district, caste_category, phone, whatsapp_verified, payment_status, score, total_marks, test_name, answers_json, access_token, referred_by_phone, battle_partner_lead_id, time_taken_seconds, is_used)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, 'Approved', %s, %s, %s, %s, %s, %s, %s, %s, 1) RETURNING id
                """, (test_id, t_date, student_name, district, caste_category, phone, score, total, test['test_title'], ans_json_str, result_token, referred_by, battle_partner_id, time_taken))
                lead_id = cur.fetchone()['id']

                # रेफरल पेअर अनलॉक (३ मित्र = २ महासंग्राम टेस्ट अनलॉक)
                completed_friends_count = 0
                if referred_by and test.get('category') == 'free':
                    cur.execute("""
                        SELECT COUNT(DISTINCT phone) as valid_friends 
                        FROM mock_test_leads
                        WHERE referred_by_phone=%s AND test_id=%s AND is_deleted=0
                    """, (referred_by, test_id))
                    f_res = cur.fetchone()
                    if f_res and f_res['valid_friends'] >= 3:
                        unlocked_count = (f_res['valid_friends'] // 3) * 2
                        c_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                        cur.execute("""
                            INSERT INTO shared_free_passes (phone, unlocked_paid_count, created_at)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (phone) DO UPDATE SET unlocked_paid_count=%s
                        """, (referred_by, unlocked_count, c_time, unlocked_count))

                cur.execute("SELECT COUNT(DISTINCT phone) as my_friends FROM mock_test_leads WHERE referred_by_phone=%s AND is_deleted=0", (phone,))
                f_row = cur.fetchone()
                if f_row: completed_friends_count = f_row['my_friends']

                # रँक गणना
                cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND is_deleted=0 AND score > %s", (test_id, score))
                state_rank = (cur.fetchone()['higher'] + 1)

                cur.execute("SELECT COUNT(*) as higher_dist FROM mock_test_leads WHERE test_id=%s AND district ILIKE %s AND is_deleted=0 AND score > %s", (test_id, district, score))
                district_rank = (cur.fetchone()['higher_dist'] + 1)

                cur.execute("SELECT COUNT(*) as higher_cat FROM mock_test_leads WHERE test_id=%s AND caste_category = %s AND is_deleted=0 AND score > %s", (test_id, caste_category, score))
                category_rank = (cur.fetchone()['higher_cat'] + 1)

                # २ मित्रांमधील मुकाबला तुलना
                battle_result_text = ""
                if battle_partner_id > 0:
                    cur.execute("SELECT student_name, score, time_taken_seconds FROM mock_test_leads WHERE id=%s", (battle_partner_id,))
                    partner = cur.fetchone()
                    if partner:
                        if score > partner['score']:
                            battle_result_text = f"🏆 अभिनंदन! तुम्ही तुमच्या मित्राला ({partner['student_name']}) हरवले आहे! (तुमचे गुण: {score}, मित्राचे: {partner['score']})"
                        elif score < partner['score']:
                            battle_result_text = f"⚔️ चुरशीची लढत! तुमचा मित्र ({partner['student_name']}) पुढे गेला. (मित्राचे गुण: {partner['score']}, तुमचे: {score})"
                        else:
                            if time_taken < partner['time_taken_seconds']:
                                battle_result_text = f"⚡ गुण समान! पण तुम्ही मित्रापेक्षा लवकर सोडवून बाजी मारली!"
                            else:
                                battle_result_text = f"🤝 दोघांचेही गुण समान झाले आहेत!"

                cur.execute("SELECT setting_key, setting_value FROM academy_settings WHERE setting_key IN ('insta_link', 'yt_link', 'toppers_link', 'wa_groups_multiline')")
                settings_dict = {r['setting_key']: r['setting_value'] for r in cur.fetchall()}
                conn.commit()

        subject_breakdown = []
        for k, v in sub_scores.items():
            pct = round((v['score'] / v['total'] * 100), 1) if v['total'] > 0 else 0
            subject_breakdown.append({"name": k, "obtained": v['score'], "total": v['total'], "percentage": pct})

        main_portal_url = request.host_url.rstrip('/')
        result_url = main_portal_url + url_for('detailed_answers', token=result_token)
        battle_invite_url = f"{main_portal_url}/take_test/{test_id}?battle_id={lead_id}"
        
        ego_msg = f"महाराष्ट्र पोलीस भरती महासराव टेस्टमध्ये मला {score}/{total} गुण व रँक #{category_rank} मिळाला! बघू तू माझ्या आधी किंवा जास्त गुणांनी सोडवतोस का: {battle_invite_url}"
        ego_share_encoded = urllib.parse.quote(ego_msg)

        return render_template_string(
            RESULT_SUMMARY_TEMPLATE,
            lead={'id': lead_id, 'student_name': student_name, 'district': district, 'caste_category': caste_category, 'phone': phone, 'test_name': test['test_title'], 'score': score, 'total_marks': total, 'access_token': result_token},
            state_rank=state_rank, district_rank=district_rank, category_rank=category_rank,
            result_url=result_url, ego_share_encoded=ego_share_encoded,
            test_category=test.get('category', 'free'),
            insta_link=settings_dict.get('insta_link', ''), yt_link=settings_dict.get('yt_link', ''),
            toppers_link=settings_dict.get('toppers_link', '/'),
            wa_active_link=settings_dict.get('wa_groups_multiline', '').split('\n')[0] if settings_dict.get('wa_groups_multiline') else '',
            completed_friends_count=completed_friends_count,
            subject_breakdown=subject_breakdown,
            battle_result_text=battle_result_text
        )
    except Exception as e:
        return f"<h3 style='color:red;'>सर्व्हर त्रुटी: {str(e)}</h3>", 500

@app.route('/submit_help_desk', methods=['POST'])
def submit_help_desk():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    feedback = request.form.get('feedback', '').strip()
    if name and phone and feedback:
        with get_db() as conn:
            with conn.cursor() as cur:
                c_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                cur.execute("INSERT INTO student_feedbacks (lead_id, student_name, phone, feedback_text, created_at) VALUES (0, %s, %s, %s, %s)", (name, phone, feedback, c_date))
                conn.commit()
    return "<h3 style='color:green; text-align:center; padding:40px;'>✅ आपली समस्या/अभिप्राय नोंदवला गेला आहे! लवकरच संपर्क साधू.<br><br><a href='/'>होम पेजवर परत जा</a></h3>"
# =============================================================================
# विभाग ६: 'माझे जुने निकाल' WhatsApp OTP पडताळणी व ऑडिट
# =============================================================================

@app.route('/my_results', methods=['GET', 'POST'])
def student_my_results():
    step = request.args.get('step', 'request_phone')
    phone = session.get('my_results_phone', '')
    results = []
    error = None

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'send_otp':
            phone = request.form.get('phone', '').strip()
            if not re.match(r'^[6-9]\d{9}$', phone):
                error = "कृपया वैध १० अंकी मोबाईल नंबर टाका!"
            else:
                generated_otp = str(secrets.randbelow(900000) + 100000)
                session['results_otp'] = generated_otp
                session['my_results_phone'] = phone

                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO otp_verification_audit (phone, otp_code, action_type)
                            VALUES (%s, %s, 'view_results')
                        """, (phone, generated_otp))
                        conn.commit()

                step = 'verify_otp'
        elif action == 'verify_otp':
            entered_otp = request.form.get('otp', '').strip()
            if entered_otp == session.get('results_otp'):
                step = 'show_results'
                session['results_authenticated'] = True
            else:
                error = "चुकीचा OTP! कृपया पुन्हा प्रयत्न करा."
                step = 'verify_otp'

    if step == 'show_results' and session.get('results_authenticated'):
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM mock_test_leads WHERE phone=%s AND is_deleted=0 ORDER BY id DESC", (phone,))
                results = cur.fetchall()

    otp_display = session.get('results_otp', '') if step == 'verify_otp' else ''

    html = f'''<!DOCTYPE html>
    <html lang="mr">
    <head>
        <meta charset="UTF-8"><title>माझे जुने निकाल - सुरक्षित OTP पडताळणी</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ margin:0; background:#0b1329; color:#f1f5f9; font-family:'Poppins', sans-serif; padding:15px; }}
            .box {{ max-width:850px; margin:0 auto; background:#162036; border-radius:16px; padding:25px; border-top:6px solid #38bdf8; }}
            input {{ padding:10px; background:#0f172a; border:1px solid #334155; color:white; border-radius:6px; }}
            button {{ padding:10px 18px; background:#10b981; color:#022c22; font-weight:bold; border:none; border-radius:6px; cursor:pointer; }}
            table {{ width:100%; border-collapse:collapse; margin-top:15px; }}
            th, td {{ padding:10px; border-bottom:1px solid #334155; text-align:left; }}
            th {{ background:#1e293b; color:#38bdf8; }}
        </style>
    </head>
    <body>
    <div class="box">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h2 style="color:#38bdf8; margin:0;">👤 माझे जुने निकाल व प्रगती कक्ष</h2>
            <a href="/" style="color:#cbd5e1; text-decoration:none; font-weight:bold;">🏠 मुख्य पानावर जा</a>
        </div>
        {f'<p style="color:#f87171; font-weight:bold;">{error}</p>' if error else ''}
        
        {"''' if step == 'request_phone' else ''}
        <form method="POST" style="margin-top:20px;">
            <input type="hidden" name="action" value="send_otp">
            <label>नोंदणीकृत WhatsApp मोबाईल नंबर टाका:</label><br>
            <div style="display:flex; gap:10px; margin-top:8px;">
                <input type="tel" name="phone" placeholder="१० अंकी नंबर" maxlength="10" required>
                <button type="submit">📲 OTP मिळवा</button>
            </div>
        </form>
        {' ' if step == 'request_phone' else ''}

        {f'''
        <div style="background:#0f172a; padding:15px; border-radius:8px; margin-top:20px; border:1px solid #f59e0b;">
            <p style="color:#fbbf24; margin:0 0 10px;">⚡ तुमच्या WhatsApp वर पाठवलेला ६-अंकी OTP टाका (चाचणीसाठी: <b>{otp_display}</b>):</p>
            <form method="POST" style="display:flex; gap:10px;">
                <input type="hidden" name="action" value="verify_otp">
                <input type="text" name="otp" placeholder="६ अंकी OTP" maxlength="6" required>
                <button type="submit">🔐 पडताळणी करा</button>
            </form>
        </div>
        ''' if step == 'verify_otp' else ''}

        {' ' if step == 'show_results' else ''}
        <h4 style="margin:20px 0 8px; color:#34d399;">परीक्षेचा इतिहास व गुणपत्रिका:</h4>
        <table>
            <tr><th>दिनांक</th><th>टेस्ट नाव</th><th>नाव</th><th>जिल्हा</th><th>गुण</th><th>कृती</th></tr>
            {''.join([f"<tr><td>{r['test_date']}</td><td><b>{r['test_name']}</b></td><td>{r['student_name']}</td><td>{r['district']}</td><td style='color:#34d399; font-weight:bold;'>{r['score']} / {r['total_marks']}</td><td><a href='/detailed_answers/{r['access_token']}' style='color:#38bdf8; font-weight:bold;'>📖 उत्तरपत्रिका</a> | <a href='/student/admit_card/{r['id']}' target='_blank' style='color:#fbbf24; font-weight:bold;'>🖨️ आयडी</a></td></tr>" for r in results]) if results else "<tr><td colspan='6' style='text-align:center;'>नोंदी आढळल्या नाहीत.</td></tr>"}
        </table>
        {' ' if step == 'show_results' else ''}
    </div>
    </body>
    </html>'''
    return render_template_string(html)
    # =============================================================================
# विभाग ७: ॲडमिन पॉवर डॅशबोर्ड, ३६०° सर्च, ऑडिट व त्रुटीमुक्त व्यवस्थापन
# =============================================================================

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged'): return redirect('/admin/login')

    active_tab = request.args.get('tab', 'leads')
    q_subtab = request.args.get('q_subtab', 'manual')
    cat_tab = request.args.get('cat_tab', 'all')
    sort_by = request.args.get('sort_by', 'seq')
    filter_test_id = request.args.get('filter_test_id', '')
    power_search_phone = request.args.get('power_phone', '').strip()

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # १. पॉवर सर्च (विद्यार्थी ३६०° प्रोफाईल)
            student_profile = None
            student_tests = []
            if power_search_phone:
                cur.execute("SELECT * FROM mock_test_leads WHERE phone=%s AND is_deleted=0 ORDER BY id DESC", (power_search_phone,))
                student_tests = cur.fetchall()
                if student_tests:
                    student_profile = student_tests[0]

            # २. OTP ऑडिट
            cur.execute("SELECT * FROM otp_verification_audit ORDER BY id DESC LIMIT 50")
            otp_audits = cur.fetchall()

            # ३. ब्लॉक नंबर्स यादी
            cur.execute("SELECT * FROM blocked_numbers ORDER BY blocked_at DESC")
            blocked_list = cur.fetchall()

            # ४. इतर सर्व मूळ डेटा
            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=0 ORDER BY id DESC")
            leads = cur.fetchall()

            cur.execute("SELECT * FROM test_papers WHERE is_deleted=0 ORDER BY sequence_order ASC, id ASC")
            tests = cur.fetchall()

            if not filter_test_id and tests:
                filter_test_id = str(tests[0]['id'])

            cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id DESC", (filter_test_id,) if filter_test_id else (1,))
            all_questions = cur.fetchall()

            cur.execute("SELECT * FROM mock_test_leads WHERE payment_status != 'Not Required' AND is_deleted=0 ORDER BY id DESC")
            payments = cur.fetchall()

            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=0 ORDER BY score DESC LIMIT 100")
            top_leads = [(idx, l) for idx, l in enumerate(cur.fetchall(), 1)]

            cur.execute("SELECT * FROM student_feedbacks ORDER BY id DESC")
            feedbacks = cur.fetchall()

            cur.execute("SELECT setting_key, setting_value FROM academy_settings")
            settings_map = {r['setting_key']: r['setting_value'] for r in cur.fetchall()}

    admin_tab_order = settings_map.get('admin_tab_order', 'leads,payments,special,questions,power,launch,analytics,audit,blocked,leaderboard,feedback,notices,trash,settings')
    ordered_admin_tabs = [t.strip() for t in admin_tab_order.split(',') if t.strip()]

    # पॉवर सर्च HTML कार्ड
    power_html = ""
    if student_profile:
        power_html = f"""
        <div style="background:#eff6ff; border:2px solid #3b82f6; padding:20px; border-radius:10px; margin-top:15px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="color:#1e40af; margin:0;">विद्यार्थी ३६०° प्रोफाईल: {student_profile['student_name']}</h3>
                <button onclick="window.print()" class="btn" style="background:#2563eb;">🖨️ संपूर्ण प्रोफाईल प्रिंट करा</button>
            </div>
            <p>जिल्हा: <b>{student_profile['district']}</b> | प्रवर्ग: <b>{student_profile['caste_category']}</b> | WhatsApp: <b>{student_profile['phone']}</b></p>
            <h4>सोडवलेल्या टेस्ट्स व गुण:</h4>
            <table>
                <tr><th>दिनांक</th><th>टेस्टचे नाव</th><th>मिळालेले गुण</th><th>पेमेंट स्थिती</th></tr>
                {''.join([f"<tr><td>{t['test_date']}</td><td>{t['test_name']}</td><td><b>{t['score']}/{t['total_marks']}</b></td><td>{t['payment_status']}</td></tr>" for t in student_tests])}
            </table>
        </div>
        """

    return render_template_string(
        ADMIN_TEMPLATE,
        active_tab=active_tab, q_subtab=q_subtab, cat_tab=cat_tab, sort_by=sort_by,
        leads=leads, tests=tests, all_questions=all_questions, payments=payments,
        top_leads=top_leads, feedbacks=feedbacks, unlimited_list=[], free_pass_list=[],
        all_districts=[], lead_dist='', lead_cat='', lead_test_id='', filter_test_id=filter_test_id,
        selected_test_title='निवडलेली टेस्ट', qr_url=settings_map.get('qr_code_url', ''),
        upi_mobile=settings_map.get('upi_mobile', '9921111960'), razorpay_key_id=settings_map.get('razorpay_key_id', ''),
        razorpay_key_secret=settings_map.get('razorpay_key_secret', ''), help_phone=settings_map.get('help_phone', ''),
        help_address=settings_map.get('help_address', ''), insta_link=settings_map.get('insta_link', ''),
        yt_link=settings_map.get('yt_link', ''), toppers_link=settings_map.get('toppers_link', ''),
        wa_groups_multiline=settings_map.get('wa_groups_multiline', ''), home_tab_order=settings_map.get('home_tab_order', ''),
        admin_tab_order=admin_tab_order, ordered_admin_tabs=ordered_admin_tabs,
        site_status=settings_map.get('site_status', 'active'), custom_tabs_list=[], undo_items=[], deleted_questions_list=[]
    )

# नंबर ब्लॉक आणि अनब्लॉक राऊट्स
@app.route('/admin/block_number', methods=['POST'])
def admin_block_number():
    if not session.get('admin_logged'): return redirect('/admin/login')
    phone = request.form.get('phone', '').strip()
    reason = request.form.get('reason', '').strip()
    if phone:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO blocked_numbers (phone, reason) VALUES (%s, %s) ON CONFLICT (phone) DO UPDATE SET reason=EXCLUDED.reason", (phone, reason))
                conn.commit()
    return redirect('/admin/dashboard?tab=blocked')

@app.route('/admin/unblock_number/<phone>')
def admin_unblock_number(phone):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM blocked_numbers WHERE phone=%s", (phone,))
            conn.commit()
    return redirect('/admin/dashboard?tab=blocked')

# ५००/५०५ एरर-प्रूफ सॉफ्ट डिलीट
@app.route('/admin/safe_delete_lead/<int:lead_id>')
def admin_safe_delete_lead(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=leads')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

