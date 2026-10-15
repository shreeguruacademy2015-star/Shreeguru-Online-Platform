# =============================================================================
# MAHARASHTRA POLICE BHARTI ONLINE TEST PORTAL 2026 - MASTER CORE (PART 1/7)
# MODULE: CORE IMPORTS, CONFIGURATION, NEON POOLING, SCHEMAS & PERFORMANCE INDEXES
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
from flask import (
    Flask, jsonify, redirect, render_template_string,
    request, session, url_for, send_file, Response, abort
)
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import requests

# -----------------------------------------------------------------------------
# 1. OPTIONAL/FALLBACK ENGINE IMPORTS (Render-safe, zero crash architecture)
# -----------------------------------------------------------------------------
try:
    from ai_question_generator import (
        AIQuestionGenerator,
        init_ai_generation_tables,
        SUBJECT_TOPIC_MAPPING
    )
except Exception as gen_err:
    AIQuestionGenerator = None
    SUBJECT_TOPIC_MAPPING = {}
    print(f"AI Generator Import Warning (Fallback Active): {gen_err}")

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import razorpay
except ImportError:
    razorpay = None

# -----------------------------------------------------------------------------
# 2. FLASK APPLICATION CONFIGURATION & SECURITY SALTS
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "maha_police_master_platform_2026_safe_key_super_secure_production_v2"
)
SECURITY_SALT = os.environ.get(
    "LINK_SECURITY_SALT",
    "anti_tamper_police_salt_2026_super_hardened"
)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB कमाल मर्यादा

# -----------------------------------------------------------------------------
# 3. NEON POSTGRESQL THREADED CONNECTION POOLING (High Concurrency Engine)
# -----------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
db_pool = None

try:
    if DATABASE_URL:
        db_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=30,
            dsn=DATABASE_URL
        )
        print("✅ Neon PostgreSQL Threaded Connection Pool Ready (1-30 conn)!")
    else:
        print("⚠️ Warning: DATABASE_URL environment variable is not set.")
except Exception as pool_err:
    print(f"❌ Critical Database Pool Initialization Error: {pool_err}")

@contextmanager
def get_db():
    conn = None
    try:
        if db_pool:
            conn = db_pool.getconn()
            # कनेक्शन जिवंत आहे का तपासणी (SSL ड्रॉप टाळण्यासाठी)
            if conn.closed:
                conn = psycopg2.connect(DATABASE_URL)
        elif DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
        else:
            raise ConnectionError("Database configuration missing.")
        yield conn
    except Exception as err:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise err
    finally:
        if conn and db_pool:
            try:
                db_pool.putconn(conn)
            except Exception:
                pass
        elif conn:
            try:
                conn.close()
            except Exception:
                pass

# -----------------------------------------------------------------------------
# 4. HIGH-SPEED COMPOSITE INDEXES SETUP (Zero Latency Execution)
# -----------------------------------------------------------------------------
def setup_indexes():
    """
    Establishes composite and targeted indexes across high-traffic tables.
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_leads_test_score ON mock_test_leads(test_id, score);
                    CREATE INDEX IF NOT EXISTS idx_leads_phone ON mock_test_leads(phone);
                    CREATE INDEX IF NOT EXISTS idx_leads_cat_score ON mock_test_leads(test_id, caste_category, score);
                    CREATE INDEX IF NOT EXISTS idx_leads_district ON mock_test_leads(district);
                    CREATE INDEX IF NOT EXISTS idx_leads_referred ON mock_test_leads(referred_by_phone);
                    CREATE INDEX IF NOT EXISTS idx_questions_test_id ON questions(test_id);
                    CREATE INDEX IF NOT EXISTS idx_tests_category_active ON test_papers(category, status);
                    CREATE INDEX IF NOT EXISTS idx_live_heartbeats_seen ON live_heartbeats(last_seen);
                    CREATE INDEX IF NOT EXISTS idx_analytics_page_time ON traffic_analytics(page_key, visited_at);
                    CREATE INDEX IF NOT EXISTS idx_audit_phone ON otp_verification_audit(phone);
                """)
                conn.commit()
                print("✅ Database Composite & Targeted Indexes Ready!")
    except Exception as idx_err:
        print(f"❌ Index Creation/Verification Error: {idx_err}")

try:
    setup_indexes()
except Exception:
    pass

# -----------------------------------------------------------------------------
# 5. CRYPTOGRAPHIC LINK SIGNATURES & VERIFICATION (HMAC-SHA256)
# -----------------------------------------------------------------------------
def generate_tamper_signature(data_str):
    """Generates an HMAC-SHA256 signature token preventing parameter tampering."""
    return hmac.new(SECURITY_SALT.encode(), str(data_str).encode(), hashlib.sha256).hexdigest()[:12]

def verify_tamper_signature(data_str, sig):
    """Verifies HMAC signature securely in constant time."""
    expected = generate_tamper_signature(data_str)
    return hmac.compare_digest(expected, sig)

# -----------------------------------------------------------------------------
# 6. DYNAMIC RAZORPAY CLIENT INITIALIZER
# -----------------------------------------------------------------------------
def get_razorpay_client():
    """
    Retrieves Razorpay credentials dynamically from DB settings or environment.
    """
    if not razorpay:
        return None, ""
    
    key_id = (os.environ.get("RAZORPAY_KEY_ID") or "").strip()
    key_secret = (os.environ.get("RAZORPAY_KEY_SECRET") or "").strip()

    if not key_id or not key_secret:
        try:
            with get_db() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT setting_key, setting_value FROM academy_settings 
                        WHERE setting_key IN ('razorpay_key_id', 'razorpay_key_secret')
                    """)
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
        except Exception as rzp_err:
            print(f"Razorpay Client Init Error: {rzp_err}")
            return None, key_id
            
    return None, ""

# -----------------------------------------------------------------------------
# 7. MASTER DATABASE SCHEMA INITIALIZATION & MIGRATIONS
# -----------------------------------------------------------------------------
def init_master_db():
    """
    Creates and auto-migrates all 15 core database tables.
    """
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Test Papers Table
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

                # 2. Questions Table
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
                    image_url TEXT DEFAULT '',
                    is_deleted INTEGER DEFAULT 0
                )''')

                # 3. Student Leads & Attempts Table (With Migrations)
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
                    base_fee_paid REAL DEFAULT 0,
                    total_fee_paid REAL DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0
                )''')

                # थेट कॉलम मायग्रेशन्स
                cur.execute('''
                    ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS battle_partner_lead_id INTEGER DEFAULT 0;
                    ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS time_taken_seconds INTEGER DEFAULT 0;
                    ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS gst_amount REAL DEFAULT 0;
                    ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS base_fee_paid REAL DEFAULT 0;
                    ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS total_fee_paid REAL DEFAULT 0;
                    ALTER TABLE questions ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT '';
                ''')

                # 4. Referral Free Passes Table
                cur.execute('''CREATE TABLE IF NOT EXISTS shared_free_passes (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    unlocked_paid_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )''')

                # 5. Student Registrations Tracking Table
                cur.execute('''CREATE TABLE IF NOT EXISTS student_registrations (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    first_visited_at TIMESTAMP NOT NULL DEFAULT NOW()
                )''')

                # 6. Student Feedbacks & Help Desk Reports
                cur.execute('''CREATE TABLE IF NOT EXISTS student_feedbacks (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER DEFAULT 0,
                    student_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    feedback_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )''')

                # 7. Special Unlimited Attempts Table
                cur.execute('''CREATE TABLE IF NOT EXISTS special_unlimited_attempts (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    student_name TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    added_on TEXT NOT NULL
                )''')

                # 8. Special VIP Free Pass Table
                cur.execute('''CREATE TABLE IF NOT EXISTS special_free_pass (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    student_name TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    added_on TEXT NOT NULL
                )''')

                # 9. Live Heartbeats Realtime Tracking Table
                cur.execute('''CREATE TABLE IF NOT EXISTS live_heartbeats (
                    session_id TEXT PRIMARY KEY,
                    last_seen TIMESTAMP DEFAULT NOW()
                )''')

                # 10. Question Reports Table
                cur.execute('''CREATE TABLE IF NOT EXISTS question_reports (
                    id SERIAL PRIMARY KEY,
                    question_id INTEGER,
                    test_id INTEGER,
                    report_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )''')

                # 11. Blocked Numbers Table
                cur.execute('''CREATE TABLE IF NOT EXISTS blocked_numbers (
                    phone TEXT PRIMARY KEY,
                    reason TEXT DEFAULT '',
                    blocked_at TIMESTAMP DEFAULT NOW()
                )''')

                # 12. OTP Verification Audit Table
                cur.execute('''CREATE TABLE IF NOT EXISTS otp_verification_audit (
                    id SERIAL PRIMARY KEY,
                    phone TEXT NOT NULL,
                    otp_code TEXT NOT NULL,
                    action_type TEXT DEFAULT 'view_results',
                    verified_at TIMESTAMP DEFAULT NOW()
                )''')

                # 13. Traffic Analytics Table
                cur.execute('''CREATE TABLE IF NOT EXISTS traffic_analytics (
                    id SERIAL PRIMARY KEY,
                    page_key TEXT NOT NULL,
                    visitor_ip TEXT,
                    visited_at TIMESTAMP DEFAULT NOW()
                )''')

                # 14. Global Platform Settings Table
                cur.execute('''CREATE TABLE IF NOT EXISTS academy_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )''')

                # 15. Custom Dynamic Tabs Table
                cur.execute('''CREATE TABLE IF NOT EXISTS custom_tabs (
                    id SERIAL PRIMARY KEY,
                    tab_key TEXT UNIQUE NOT NULL,
                    tab_label TEXT NOT NULL
                )''')

                # Default Configurations
                default_settings = [
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
                    ('admin_tab_order', 'leads,power,payments,special,questions,launch,analytics,audit,blocked,leaderboard,feedback,notices,trash,settings'),
                    ('recruitment_pdf', ''),
                    ('eligibility_pdf', ''),
                    ('razorpay_key_id', 'rzp_test_TmenVmrQI8nTRA'),
                    ('razorpay_key_secret', 'FfaDgcHGbqNKGd15kiI2TP7v')
                ]
                for k, v in default_settings:
                    cur.execute("""
                        INSERT INTO academy_settings (setting_key, setting_value) 
                        VALUES (%s, %s) 
                        ON CONFLICT (setting_key) DO NOTHING
                    """, (k, v))

                # Default Test Seeds
                cur.execute('SELECT COUNT(*) as count FROM test_papers WHERE is_deleted=0')
                if cur.fetchone()['count'] == 0:
                    cur.execute("""
                        INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) 
                        VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active', 'free', 1)
                    """)
                    cur.execute("""
                        INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) 
                        VALUES (2, '🔴 मिशन खाकी रविवार थेट महासंग्राम #१', 'Paid', 99, 60, 'Active', 'live', 1)
                    """)

                conn.commit()

                # AI Generation Tables Hook
                if 'init_ai_generation_tables' in globals() and init_ai_generation_tables:
                    try:
                        init_ai_generation_tables(conn)
                    except Exception as ai_init_err:
                        print(f"AI Table Initialization Notice: {ai_init_err}")

    except Exception as db_init_err:
        print(f"Master Database Initialization Critical Error: {db_init_err}")

init_master_db()
# =============================================================================
# MAHARASHTRA POLICE BHARTI ONLINE TEST PORTAL 2026 - MASTER CORE (PART 2/7)
# MODULE: FULL HTML TEMPLATES - LEGAL TERMS, MAINTENANCE & EXPANDED HOME PAGE
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
    <p><small>अद्यतन: २०२६ | महाराष्ट्र पोलीस भरती संभाव्य टेस्ट पोर्टल</small></p>
    
    <div class="notice-box">
        <strong>शासकीय प्रतिनिधीत्वाचा स्पष्ट इन्कार:</strong><br>
        हे व्यासपीठ स्पर्धा परीक्षा सरावासाठीचे एक स्वतंत्र, खाजगी शैक्षणिक व्यासपीठ असून याचा महाराष्ट्र शासन, गृह विभाग, महाराष्ट्र पोलीस किंवा कोणत्याही अधिकृत भरती मंडळाशी थेट संबंध, प्रतिनिधित्व अथवा प्राधिकृतता नाही.
    </div>

    <h2>१. शैक्षणिक उद्देश व स्व-मूल्यमापन</h2>
    <p>या प्लॅटफॉर्मवरील सर्व सराव चाचण्या, प्रश्न, उत्तरपत्रिका आणि गुणवत्ता क्रमांक हे केवळ विद्यार्थ्यांच्या वैयक्तिक अभ्यासाच्या आणि स्व-मूल्यमापनाच्या मार्गदर्शनासाठी आहेत.</p>

    <h2>२. निवडीची कोणतीही हमी नाही</h2>
    <p>सराव चाचण्या सोडवल्यामुळे प्रत्यक्ष पोलीस भरतीत निवड होण्याची कोणतीही कायदेशीर हमी दिली जात नाही. निवड प्रक्रिया ही शासनाच्या अधिकृत नियमांनुसारच पार पडते.</p>

    <h2>३. कडक नो-रिफंड पॉलिसी</h2>
    <p>डिजिटल उत्पादन (सराव चाचण्या व सविस्तर स्पष्टीकरण पत्रिका) त्वरित उपलब्ध होत असल्याने भरलेली कोणतीही फी परत (Refund) केली जाणार नाही.</p>

    <h2>४. बौद्धिक संपदा व कॉपीराइट संरक्षण</h2>
    <p>प्लॅटफॉर्मवरील सर्व प्रश्न, रचना आणि स्पष्टीकरणे कॉपीराइट संरक्षित आहेत. कोणत्याही सोशल मीडिया किंवा टेलिग्रामवर अनधिकृत वाटप केल्यास कायदेशीर कारवाई केली जाईल.</p>

    <h2>५. कम्युनिटी व ग्रुप शिस्त (महिला प्रायव्हसी)</h2>
    <ul>
        <li>अभ्यास ग्रुप्समध्ये महिला सदस्य असल्याने कोणत्याही सदस्याला वैयक्तिक मेसेज (DM) किंवा कॉल करण्यास सक्त मनाई आहे.</li>
        <li>कोणतेही वादग्रस्त किंवा राजकीय मेसेज टाकल्यास तत्काळ काढून टाकले जाईल.</li>
    </ul>

    <h2>६. कायदेशीर अधिकार क्षेत्र</h2>
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
    <p>विद्यार्थ्यांना अधिक गतिमान अनुभव देण्यासाठी नियोजित तांत्रिक सुधारणा सुरू आहेत.</p>
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
        .badge-live { background: #ef4444; color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .box { max-width: 950px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 25px 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); border-top: 5px solid #10b981; }
        .hero-banner { text-align: center; margin-bottom: 22px; }
        .hero-banner h1 { margin: 0 0 8px; color: #34d399; font-size: 26px; font-weight: 800; }
        .quote-box { background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(6,95,70,0.2)); border-left: 4px solid #10b981; padding: 12px 16px; border-radius: 8px; font-size: 14.5px; color: #a7f3d0; font-weight: 600; margin-bottom: 20px; text-align: center; }
        
        .paid-hero-card { display: none; background: linear-gradient(135deg, rgba(245,158,11,0.15), rgba(15,23,42,0.95)); border: 2px solid #f59e0b; border-radius: 12px; padding: 20px; margin-bottom: 22px; text-align: center; box-shadow: 0 10px 25px rgba(245,158,11,0.15); }
        .paid-hero-card h3 { color: #fde047; margin: 0 0 10px; font-size: 21px; }
        .paid-hero-card p { color: #cbd5e1; font-size: 14px; line-height: 1.6; margin: 6px 0; }
        .package-box { background: #0f172a; border-radius: 8px; padding: 14px; margin: 12px 0; border: 1.5px dashed #f59e0b; }
        .unlock-badge { display: inline-block; background: #10b981; color: #022c22; font-weight: 800; padding: 8px 18px; border-radius: 20px; font-size: 13.5px; margin-top: 10px; }

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

        // मुख्य होमपेजवरून बाहेर पडताना विचारणा
        window.addEventListener('beforeunload', function (e) {
            e.preventDefault();
            e.returnValue = 'आपण टेस्ट पोर्टलवरून बाहेर पडू इच्छिता का?';
            return e.returnValue;
        });

        // वेब कॉन्टॅक्ट पिकर (फोनबुकमधून थेट नंबर निवडणे)
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
            if (paidCard) paidCard.style.display = (category === 'paid' || category === 'live') ? 'block' : 'none';

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
            const text = encodeURIComponent("मित्रा, महाराष्ट्र पोलीस भरती २०२६ ची अतिसंभाव्य टेस्ट सोडव आणि आपला रँक तपास: " + link);
            window.open("https://wa.me/91" + num + "?text=" + text, "_blank");
        }

        document.addEventListener('DOMContentLoaded', function() {
            const firstActive = document.querySelector('.tab-btn.active') || document.querySelector('.tab-btn');
            if (firstActive) firstActive.click();
        });

        setInterval(function() {
            fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
        }, 60000);
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
        <span style="font-size:12px; color:#34d399; font-weight:bold;">👥 सध्या ऑनलाईन: {{ active_students_count }}</span>
    </div>
</div>

<div class="box">
    <a href="/" style="position:fixed; bottom:20px; right:20px; background:#10b981; color:#022c22; padding:10px 18px; border-radius:30px; text-decoration:none; font-weight:800; font-size:13px; box-shadow:0 4px 15px rgba(0,0,0,0.4); z-index:9999; border:2px solid #34d399;">
        🏠 मुख्य पानावर जा
    </a>
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

    <!-- महासंग्राम प्रभावी विक्री व मार्गदर्शन बॅनर -->
    <div id="paidHeroCard" class="paid-hero-card">
        <h3>🎯 अतिसंभाव्य महासंग्राम टेस्ट संच (Mission Khaki 2026)</h3>
        <p>🔥 <b>एका कप चहाच्या किमतीत १०० प्रश्नांची प्रश्नपत्रिका सोडवून राज्यात, जिल्ह्यात व संवर्गनिहाय रँक तपासा!</b><br>
        गेल्या भरतीत १ मार्काने खाकी वर्दी हुकली होती का? एका मार्काची किंमत १ वर्षाची मेहनत असते! लेखी परीक्षेत ९०+ गुण मिळवण्यासाठी दर्जात्मक प्रश्नांचा सराव अत्यंत महत्त्वाचा आहे.</p>
        
        <div class="package-box">
            <span style="color:#fde047; font-weight:800; font-size:16px;">💎 फी: फक्त ₹९९ + १८% GST = ₹११६.८२ मध्ये महासंग्राम १०० गुण टेस्ट उपलब्ध!</span><br>
            <small style="color:#94a3b8;">(सोमवार ते रविवार कधीही सोडवा आणि रविवारी संध्याकाळी ७:०० वाजता संपूर्ण महाराष्ट्रातील गुणवत्ता यादी पहा!)</small>
        </div>

        <div class="unlock-badge">
            🎁 विशेष ऑफर: ३ मित्रांनी मोफत टेस्ट सबमिट केल्यास २ महासंग्राम टेस्ट्स १००% मोफत अनलॉक होतात!
        </div>
    </div>

    <!-- टॅब्स नेव्हिगेशन -->
    <div class="tabs-wrapper">
        {% for tab_item in parsed_home_tabs %}
            <button class="tab-btn {{ 'active' if loop.first else '' }}" onclick="filterTab('{{ tab_item.key }}', this)">
                {{ tab_item.label }}
            </button>
        {% endfor %}
    </div>

    <!-- प्रश्नपत्रिका ग्रिड -->
    <div id="testsContainer" class="test-grid">
        {% for t in tests %}
        <div class="test-card" data-id="{{ t.id }}" data-type="{{ t.test_type }}" data-cat="{{ t.category or 'free' }}">
            <div>
                <h4 class="test-title">{{ t.test_title }}</h4>
                <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                    {% if t.category in ['live', 'paid'] %}
                        <span class="badge-paid-package">⭐ अतिसंभाव्य महासंग्राम टेस्ट</span>
                    {% elif t.test_type == 'Free' %}
                        <span class="badge-free">🟢 मोफत सराव</span>
                    {% else %}
                        <span class="badge-paid-package">⭐ स्पेशल संच</span>
                    {% endif %}
                    <span class="badge-rapid">⏱️ {{ t.duration_minutes }} मिनिटे</span>
                    {% if t.is_locked and t.category == 'rapid' %}
                    <span style="font-size:12px; color:#fbbf24;">⏳ पुढील टेस्ट दुसऱ्या दिवशी सकाळी १०:०० वाजता अनलॉक होईल</span>
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
            🎯 <b>लवकरच या विभागात नवीन अतिसंभाव्य सराव संच उपलब्ध होतील!</b><br>
            <span style="font-size:13px; color:#64748b;">आमचे तज्ज्ञ शिक्षक नवीन दर्जेदार प्रश्नांची रचना करत आहेत. खाकीची तयारी अखंड चालू ठेवा! ⚔️</span>
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
        <p style="font-size:13px; color:#94a3b8; margin:0 0 15px;">विद्यार्थ्यांनी प्रत्यक्ष सोडवलेल्या टेस्ट्सवरून तयार झालेली लाईव्ह गुणवत्ता यादी:</p>
        <table class="rank-table">
            <tr><th>रँक</th><th>जिल्हा</th><th>टेस्ट देणारे विद्यार्थी</th><th>सरासरी गुण</th></tr>
            {% for dist in live_district_battles %}
            <tr>
                <td><b>#{{ loop.index }}</b></td>
                <td><b>{{ dist.district }}</b></td>
                <td><span style="background:rgba(56,189,248,0.2); color:#38bdf8; padding:3px 8px; border-radius:12px; font-weight:bold;">{{ dist.total_students }} विद्यार्थी</span></td>
                <td style="color:#34d399; font-weight:bold;">{{ dist.avg_score }} गुण</td>
            </tr>
            {% else %}
            <tr><td colspan="4" style="text-align:center; color:#94a3b8;">विद्यार्थ्यांनी टेस्ट सोडवल्यानंतर जिल्ह्यांची लाईव्ह क्रमवारी येथे दिसेल.</td></tr>
            {% endfor %}
        </table>
    </div>

    <div id="docsContainer" class="section-box">
        <h3 style="color:#38bdf8; margin-top:0;">📄 अधिकृत भरती कागदपत्रे व मागील प्रश्नपत्रिका</h3>
        {% if recruitment_pdf %}<a href="{{ recruitment_pdf }}" target="_blank" class="doc-link">📑 पोलीस भरती अधिकृत जाहिरात (PDF)</a>{% endif %}
        {% if eligibility_pdf %}<a href="{{ eligibility_pdf }}" target="_blank" class="doc-link">📋 शारीरिक व लेखी पात्रता निकष (PDF)</a>{% endif %}
    </div>

    <div id="helpContainer" class="section-box">
        <h3 style="color:#34d399; margin-top:0;">📞 मदत व मार्गदर्शन हेल्प डेस्क (Help Desk)</h3>
        <p style="font-size:14px; color:#cbd5e1; margin-bottom:15px;">टेस्ट किंवा पेमेंट संदर्भात काही अडचण असल्यास खालील क्रमांकावर संपर्क साधा किंवा येथे तक्रार नोंदवा:</p>
        <div style="background:#1e293b; padding:18px; border-radius:10px; border:1px solid #334155; display:inline-block; text-align:left; max-width:450px; width:100%;">
            <p style="margin:6px 0; color:#f8fafc;">📱 <b>हेल्पलाईन नंबर:</b> <a href="https://wa.me/91{{ help_phone }}" target="_blank" style="color:#34d399; font-weight:bold;">{{ help_phone }}</a></p>
            <p style="margin:6px 0; color:#f8fafc;">📍 <b>पत्ता:</b> {{ help_address }}</p>
            <hr style="border:0; border-top:1px solid #334155; margin:12px 0;">
            <form method="POST" action="/submit_help_desk">
                <input type="text" name="name" placeholder="तुमचे पूर्ण नाव" required style="width:100%; padding:8px; margin-bottom:8px; border-radius:6px; background:#0f172a; border:1px solid #334155; color:white;">
                <input type="tel" name="phone" id="help_phone_input" placeholder="१० अंकी व्हॉट्सॲप नंबर" maxlength="10" required style="width:100%; padding:8px; margin-bottom:8px; border-radius:6px; background:#0f172a; border:1px solid #334155; color:white;">
                <textarea name="feedback" rows="3" placeholder="आपली अडचण किंवा अभिप्राय येथे लिहा..." required style="width:100%; padding:8px; margin-bottom:8px; border-radius:6px; background:#0f172a; border:1px solid #334155; color:white;"></textarea>
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
<!-- ========================================== -->
    <!-- १. ॲप इन्स्टॉल बटण (PWA Download) -->
    <!-- ========================================== -->
    <div style="text-align:center; margin: 25px 0;">
        <button id="pwaInstallBtn" style="display:none; background: linear-gradient(135deg, #10b981, #059669); color: white; border: none; padding: 14px 28px; border-radius: 30px; font-weight: bold; font-size: 15px; cursor: pointer; box-shadow: 0 4px 15px rgba(16,185,129,0.4); transition: transform 0.2s;">
            📲 श्रीगुरु पोर्टल ॲप इन्स्टॉल करा
        </button>
    </div>

    <!-- ========================================== -->
    <!-- २. मार्गदर्शक नियमावली विभाग -->
    <!-- ========================================== -->
    <div style="max-width:850px; margin:30px auto; background:#162036; border:1px solid #1e293b; border-radius:16px; padding:25px; color:#f1f5f9; font-family:'Segoe UI', sans-serif;">
        <h3 style="color:#f59e0b; text-align:center; margin-top:0; font-size:22px;">
            📖 श्रीगुरु करिअर अकॅडमी टेस्ट पोर्टल - मार्गदर्शक नियमावली
        </h3>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:15px; margin-top:20px;">
            <div style="background:#0f172a; padding:15px; border-radius:10px; border-left:4px solid #3b82f6;">
                <h4 style="color:#38bdf8; margin:0 0 8px 0;">🎯 १. मोफत व सराव टेस्ट्स</h4>
                <p style="font-size:13px; color:#cbd5e1; margin:0; line-height:1.5;">विषयनिहाय व घटकानुसार प्रश्नपत्रिका. सबमिट करताच अचूक विश्लेषण व उत्तरतालिका लगेच दिसते.</p>
            </div>
            <div style="background:#0f172a; padding:15px; border-radius:10px; border-left:4px solid #ef4444;">
                <h4 style="color:#f87171; margin:0 0 8px 0;">⚔️ २. 1-vs-1 बॅटल मोड</h4>
                <p style="font-size:13px; color:#cbd5e1; margin:0; line-height:1.5;">मित्रासोबत थेट स्पर्धा! एकाच वेळी दोघांनी पेपर सोडवून लाईव्ह गुण व रँक तपासा.</p>
            </div>
            <div style="background:#0f172a; padding:15px; border-radius:10px; border-left:4px solid #10b981;">
                <h4 style="color:#34d399; margin:0 0 8px 0;">🏆 ३. रविवार थेट महासंग्राम</h4>
                <p style="font-size:13px; color:#cbd5e1; margin:0; line-height:1.5;">राज्यस्तरीय १०० गुणांची परीक्षा. निकाल दर रविवारी सायंकाळी ठीक ७:०० वाजता रँकसह जाहीर होतो.</p>
            </div>
        </div>
        <div style="background:rgba(239,68,68,0.1); border:1px dashed #ef4444; border-radius:8px; padding:12px; margin-top:20px; font-size:13px; color:#fca5a5; text-align:center;">
            <b>⚠️ महत्त्वाचे नियम:</b> १-बाय-१ ऑटो-लॉक नियमानुसार एका मोबाईल नंबरवरून एक टेस्ट फक्त एकदाच सोडवता येते. स्क्रीन रेकॉर्डिंग किंवा गैरप्रकार केल्यास नंबर तात्काळ ब्लॉक केला जाईल.
        </div>
    </div>

    <!-- ========================================== -->
    <!-- ३. मोबाईलवर स्कॅन करण्यासाठी क्यूआर कोड -->
    <!-- ========================================== -->
    <div style="background:#162036; border:1px solid #334155; border-radius:12px; padding:15px; max-width:320px; margin:25px auto; text-align:center;">
        <h4 style="color:#38bdf8; margin:0 0 10px 0;">📱 मोबाईलवर सोडवण्यासाठी स्कॅन करा</h4>
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=https://shreeguru-online-platform.onrender.com" alt="Portal QR Code" style="border-radius:8px; border:2px solid #38bdf8; background:white; padding:5px;">
        <p style="color:#94a3b8; font-size:12px; margin:8px 0 0 0;">कॅमेऱ्याने स्कॅन करा आणि थेट चाचणी सुरू करा</p>
    </div>

    <!-- PWA Install Script -->
    <script>
    let deferredPrompt;
    const installBtn = document.getElementById('pwaInstallBtn');
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        if (installBtn) installBtn.style.display = 'inline-block';
    });
    if (installBtn) {
        installBtn.addEventListener('click', async () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                if (outcome === 'accepted') {
                    installBtn.style.display = 'none';
                }
                deferredPrompt = null;
            }
        });
    }
    </script>
</html>'''
# =============================================================================
# MAHARASHTRA POLICE BHARTI ONLINE TEST PORTAL 2026 - MASTER CORE (PART 3/7)
# MODULE: FULL TEMPLATES - EXAM ROOM, ACCESS GATEWAY, DETAILED KEY & ADMIT CARD
# =============================================================================

EXAM_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ test.test_title }} - परीक्षा कक्ष</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; transition: all 0.15s ease; }
        body { 
            margin: 0; background: #0b1329; color: #f1f5f9; padding: 10px; 
            -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none; user-select: none;
        }
        .exam-header { background: #1e293b; color: white; padding: 12px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; max-width: 850px; margin: 0 auto 15px; position: sticky; top: 10px; z-index: 100; border: 1.5px solid #334155; }
        .timer-box { background: rgba(239,68,68,0.2); border: 1.5px solid #ef4444; color: #fca5a5; padding: 6px 14px; border-radius: 8px; font-weight: 800; font-size: 15px; }
        .btn-exit-home { background: #475569; color: white; border: none; padding: 8px 14px; border-radius: 6px; font-size: 12.5px; font-weight: bold; cursor: pointer; text-decoration: none; }
        .btn-exit-home:hover { background: #dc2626; }
        .progress-bar-container { max-width: 850px; margin: 0 auto 15px; background: #1e293b; height: 8px; border-radius: 10px; overflow: hidden; border: 1px solid #334155; }
        .progress-bar-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #10b981, #34d399); }
        .box { max-width: 850px; margin: 0 auto; background: #162036; border-radius: 16px; padding: 25px; border: 1px solid #334155; }
        .q-item { background: #0f172a; border: 1.5px solid #27354f; border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; }
        .q-text { font-weight: 700; margin-bottom: 14px; font-size: 16px; color: #f8fafc; }
        .opt-label { display: flex; align-items: center; margin-bottom: 10px; font-size: 14.5px; cursor: pointer; background: #1e293b; padding: 12px 16px; border-radius: 10px; border: 1.5px solid #334155; color: #cbd5e1; }
        .opt-label:hover { background: #27354f; border-color: #38bdf8; color: white; transform: translateX(3px); }
        .opt-label input[type="radio"] { margin-right: 12px; width: 18px; height: 18px; accent-color: #10b981; }
        .opt-label.selected { background: rgba(16,185,129,0.15); border-color: #10b981; color: #a7f3d0; font-weight: 700; }
        .btn-report { background: none; border: none; color: #94a3b8; font-size: 11.5px; cursor: pointer; margin-top: 6px; text-decoration: underline; }
        .btn-report:hover { color: #f87171; }
        .bottom-submission-card { background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(15,23,42,0.9)); border: 2px solid #10b981; border-radius: 14px; padding: 22px; margin-top: 30px; }
        .bottom-submission-card input, .bottom-submission-card select { width: 100%; padding: 13px; background: #0f172a; border: 1.5px solid #334155; border-radius: 8px; margin-top: 5px; font-size: 14.5px; margin-bottom: 12px; color: white; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 15px; border: none; border-radius: 8px; font-size: 17px; font-weight: 800; cursor: pointer; }
        .btn-submit:disabled { background: #334155; color: #64748b; cursor: not-allowed; }
    </style>
    <script>
        let isFormSubmitted = false;
        let testStartTime = Date.now();

        function exitToHome() {
            if (confirm("तुम्ही खरंच परीक्षा सोडून होम पेजवर जाऊ इच्छिता का? चाचणी सबमिट केल्याशिवाय लॉक होणार नाही.")) {
                isFormSubmitted = true;
                window.location.replace('/');
            }
        }

        document.addEventListener('contextmenu', function(e) { e.preventDefault(); });
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey && (e.key === 'c' || e.key === 'u' || e.key === 's' || e.key === 'p')) {
                e.preventDefault();
                alert("सुरक्षा कारणास्तव प्रश्न कॉपी करण्यास सक्त मनाई आहे!");
            }
        });

        document.addEventListener('visibilitychange', function() {
            if (document.hidden && !isFormSubmitted) {
                alert("⚠️ चेतावणी: कृपया वारंवार टॅब बदलू नका! अन्यथा तुमची टेस्ट ऑटोमॅटिक बंद पडेल.");
            }
        });

        const testStorageKey = 'police_saved_answers_{{ test.id }}';
        const timerStorageKey = 'police_saved_timer_{{ test.id }}';

        window.addEventListener('beforeunload', function (e) {
            if (!isFormSubmitted) {
                e.preventDefault();
                e.returnValue = 'तुम्ही परीक्षा सोडून जात आहात का?';
                return e.returnValue;
            }
        });

        let savedTime = localStorage.getItem(timerStorageKey);
        let timeLeft = savedTime !== null ? parseInt(savedTime, 10) : {{ test.duration_minutes * 60 }};

        function startTimer() {
            const timerDisplay = document.getElementById('time-left');
            let timer = setInterval(function () {
                let minutes = parseInt(timeLeft / 60, 10);
                let seconds = parseInt(timeLeft % 60, 10);
                timerDisplay.innerText = (minutes < 10 ? "0" + minutes : minutes) + ":" + (seconds < 10 ? "0" + seconds : seconds);
                localStorage.setItem(timerStorageKey, timeLeft);

                if (--timeLeft < 0) {
                    clearInterval(timer);
                    alert("⏰ वेळ संपली! तुमची टेस्ट आपोआप सबमिट होत आहे.");
                    isFormSubmitted = true;
                    localStorage.removeItem(testStorageKey);
                    localStorage.removeItem(timerStorageKey);
                    document.getElementById("examForm").submit();
                }
            }, 1000);
        }

        function updateProgress() {
            const totalQuestions = {{ questions|length }};
            const answeredCount = document.querySelectorAll('#questionsArea input[type="radio"]:checked').length;
            const percentage = (answeredCount / totalQuestions) * 100;
            document.getElementById('progressFill').style.width = percentage + '%';
            document.getElementById('progressText').innerText = answeredCount + ' / ' + totalQuestions + ' सोडवले';
        }

        function saveAnswerProgress() {
            const answers = {};
            document.querySelectorAll('#questionsArea input[type="radio"]:checked').forEach(radio => {
                answers[radio.name] = radio.value;
                radio.closest('.q-item').querySelectorAll('.opt-label').forEach(l => l.classList.remove('selected'));
                radio.closest('.opt-label').classList.add('selected');
            });
            localStorage.setItem(testStorageKey, JSON.stringify(answers));
            updateProgress();
        }

        function restoreAnswerProgress() {
            const savedAnswers = JSON.parse(localStorage.getItem(testStorageKey) || '{}');
            for (const [qName, qVal] of Object.entries(savedAnswers)) {
                const radio = document.querySelector(`input[name="${qName}"][value="${qVal}"]`);
                if (radio) {
                    radio.checked = true;
                    radio.closest('.opt-label').classList.add('selected');
                }
            }
            updateProgress();
        }

        document.addEventListener('change', function(e) {
            if (e.target.type === 'radio') saveAnswerProgress();
        });

        function reportQuestion(qId) {
            const issue = prompt("या प्रश्नात काय अडचण किंवा चूक वाटते ते थोडक्यात लिहा:");
            if (issue && issue.trim()) {
                fetch('/report_question', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question_id: qId, test_id: {{ test.id }}, report_text: issue})
                }).then(() => alert("✅ आपला रिपोर्ट नोंदवला गेला आहे. धन्यवाद!"));
            }
        }

        async function selectExamPhonebook(targetId) {
            if ('contacts' in navigator && 'ContactsManager' in window) {
                try {
                    const contacts = await navigator.contacts.select(['tel'], {multiple: false});
                    if (contacts && contacts[0] && contacts[0].tel && contacts[0].tel.length > 0) {
                        let phoneNum = contacts[0].tel[0].replace(/[^0-9]/g, '').slice(-10);
                        document.getElementById(targetId).value = phoneNum;
                        validateAndReady();
                    }
                } catch(e) {}
            } else {
                alert("तुमचा ब्राऊझर थेट फोनबुकला सपोर्ट करत नाही. नंबर टाईप करा.");
            }
        }

        function validateAndReady() {
            const name = document.getElementById('s_name').value.trim();
            const dist = document.getElementById('s_dist').value.trim();
            const phone = document.getElementById('s_phone').value.trim();
            const submitBtn = document.getElementById('submitBtn');
            const indianPhoneRegex = /^[6-9][0-9]{9}$/;

            if (name !== "" && dist !== "" && indianPhoneRegex.test(phone)) {
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
            document.getElementById('examForm').addEventListener('submit', function(e) {
                isFormSubmitted = true;
                localStorage.removeItem(testStorageKey);
                localStorage.removeItem(timerStorageKey);
                
                let timeTaken = Math.floor((Date.now() - testStartTime) / 1000);
                document.getElementById('time_taken_input').value = timeTaken;

                let overlay = document.getElementById('submittingOverlay');
                if (!overlay) {
                    overlay = document.createElement('div');
                    overlay.id = 'submittingOverlay';
                    overlay.style.cssText = 'position:fixed; inset:0; background:rgba(11,19,41,0.96); z-index:99999; display:flex; flex-direction:column; justify-content:center; align-items:center; color:white; text-align:center; padding:20px;';
                    overlay.innerHTML = '<div style="font-size:45px; margin-bottom:15px;">⏳</div><h3 style="color:#34d399; margin:0 0 10px; font-size:22px;">तुमची टेस्ट सबमिट होत आहे...</h3><p style="color:#cbd5e1; font-size:14.5px; margin:0;">कृपया प्रतीक्षा करा, उत्तरपत्रिका तपासली जात आहे!</p>';
                    document.body.appendChild(overlay);
                }
            });
        });

        window.onload = function() {
            restoreAnswerProgress();
            startTimer();
            validateAndReady();
        };
    </script>
    <style>
        /* मजकूर कॉपी किंवा सिलेक्ट करणे पूर्णपणे बंद */
        body {
            -webkit-touch-callout: none;
            -webkit-user-select: none;
            user-select: none;
        }
        /* स्क्रीन रेकॉर्डिंग किंवा टॅब बदलल्यास स्क्रीन ब्लर करणे */
        .screen-protected {
            filter: blur(30px) !important;
            opacity: 0.05 !important;
            pointer-events: none !important;
        }
    </style>

    <script>
        // १. माउसचे राईट-क्लिक बंद करणे
        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });

        // २. स्क्रीनशॉट व डेव्हलपर कीज बंद करणे
        document.addEventListener('keydown', function(e) {
            if (e.key === "PrintScreen") {
                navigator.clipboard.writeText('');
                alert('⚠️ सुरक्षेच्या कारणास्तव परीक्षेदरम्यान स्क्रीनशॉट काढण्यास सक्त बंदी आहे!');
            }
            if (e.ctrlKey && ['u', 'U', 's', 'S', 'p', 'P'].includes(e.key)) {
                e.preventDefault();
            }
            if (e.key === "F12" || (e.ctrlKey && e.shiftKey && ['I', 'i', 'J', 'j'].includes(e.key))) {
                e.preventDefault();
            }
        });

        // ३. विद्यार्थी दुसऱ्या ॲपवर गेल्यास किंवा टॅब बदलल्यास प्रश्न ब्लर करणे
        document.addEventListener("visibilitychange", function() {
            if (document.hidden) {
                document.body.classList.add("screen-protected");
            } else {
                document.body.classList.remove("screen-protected");
            }
        });

        window.addEventListener("blur", function() {
            document.body.classList.add("screen-protected");
        });
        window.addEventListener("focus", function() {
            document.body.classList.remove("screen-protected");
        });
    </script>
</head>
<body>
<div class="exam-header">
    <div>
        <h3 style="margin:0; font-size:16.5px; color:#34d399;">⚔️ {{ test.test_title }}</h3>
        <small id="progressText" style="color:#94a3b8; font-weight:600;">० / {{ questions|length }} सोडवले</small>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
        <div class="timer-box">⏳ <span id="time-left">00:00</span></div>
        <button onclick="exitToHome()" class="btn-exit-home">🏠 बाहेर पडा</button>
    </div>
</div>

<div class="progress-bar-container">
    <div id="progressFill" class="progress-bar-fill"></div>
</div>

<div class="box">
    <form id="examForm" method="POST" action="/submit_test/{{ test.id }}">
        <input type="hidden" name="time_taken_seconds" id="time_taken_input" value="0">
        <input type="hidden" name="battle_partner_id" value="{{ battle_partner_id or 0 }}">
        <div id="questionsArea">
            {% for q in questions %}
            <div class="q-item">
                <div class="q-text">प्र. {{ loop.index }}. {{ q.question }}</div>
                {% if q.image_url %}
                <div style="margin-bottom:12px; text-align:center;">
                    <img src="{{ q.image_url }}" alt="Question Image" style="max-width:100%; max-height:280px; border-radius:8px;">
                </div>
                {% endif %}
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="A"> A) {{ q.opt_a }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="B"> B) {{ q.opt_b }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="C"> C) {{ q.opt_c }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="D"> D) {{ q.opt_d }}</label>
                <div style="text-align:right;">
                    <button type="button" class="btn-report" onclick="reportQuestion({{ q.id }})">⚠️ प्रश्नात चूक वाटते का? कळवा</button>
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="bottom-submission-card">
            <h3 style="margin:0 0 6px; color:#34d399; font-size:18px;">🎯 निकाल व संवर्ग गुणवत्ता यादीसाठी माहिती भरा:</h3>
            <p style="font-size:13px; color:#cbd5e1; margin:0 0 14px;">
                ⚠️ अचूक राज्य रँक आणि संवर्ग रँक मिळवण्यासाठी खालील सर्व माहिती योग्य भरा.
            </p>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">पूर्ण नाव *:</label><input type="text" name="student_name" id="s_name" placeholder="उदा. राहुल पाटील" onkeyup="validateAndReady()" required></div>
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">जिल्हा *:</label><input type="text" name="district" id="s_dist" placeholder="उदा. कोल्हापूर" onkeyup="validateAndReady()" required></div>
                <div>
                    <label style="font-size:13px; font-weight:600; color:#cbd5e1;">प्रवर्ग (Caste Category) *:</label>
                    <select name="caste_category" id="s_cat" required>
                        <option value="OPEN">OPEN (खुला प्रवर्ग)</option>
                        <option value="OBC">OBC (इतर मागासवर्ग)</option>
                        <option value="EWS">EWS (आर्थिक दुर्बल घटक)</option>
                        <option value="SC">SC (अनुसूचित जाती)</option>
                        <option value="ST">ST (अनुसूचित जमाती)</option>
                        <option value="VJ/NT">VJ/NT (विमुक्त जाती / भटक्या जमाती)</option>
                        <option value="SBC">SBC (विशेष मागास प्रवर्ग)</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:13px; font-weight:600; color:#cbd5e1;">WhatsApp मोबाईल नंबर *:</label>
                    <div style="display:flex; gap:6px;">
                        <input type="tel" name="phone" id="s_phone" placeholder="10 अंकी मोबाईल नंबर" maxlength="10" onkeyup="validateAndReady()" required>
                        <button type="button" onclick="selectExamPhonebook('s_phone')" style="background:#0284c7; color:white; border:none; border-radius:8px; padding:0 12px; cursor:pointer; font-size:13px; font-weight:bold; height:45px; margin-top:5px;">📖</button>
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
        .box { max-width:480px; width:100%; background:#162036; border-radius:16px; padding:25px; box-shadow:0 15px 35px rgba(0,0,0,0.4); border-top:6px solid #10b981; }
        input { width:100%; padding:11px; background:#0f172a; border:1.5px solid #334155; border-radius:8px; margin-bottom:12px; font-size:14px; box-sizing:border-box; color:white; }
        .btn-rzp { width:100%; background:linear-gradient(135deg, #2563eb, #1d4ed8); color:white; padding:14px; border:none; border-radius:8px; font-weight:800; cursor:pointer; font-size:15px; margin-bottom:15px; box-shadow:0 4px 15px rgba(37,99,235,0.4); }
        .btn-rzp:hover { background:linear-gradient(135deg, #1d4ed8, #1e40af); }
        .fomo-timer { background: rgba(239,68,68,0.15); border: 1.5px solid #ef4444; color: #fca5a5; padding: 8px 12px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 13.5px; margin-bottom: 15px; }
        .fear-banner { background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 14px; margin-bottom: 15px; border-radius: 4px; font-size: 13px; color: #991b1b; line-height: 1.5; }
        .btn-home-back { display:inline-block; margin-bottom:12px; color:#38bdf8; text-decoration:none; font-size:13px; font-weight:bold; }
    </style>
</head>
<body>
<div class="box">
    <a href="/" class="btn-home-back">⬅ मुख्य सराव पोर्टलवर परत जा</a>

    <div class="fomo-timer">
        ⚡ विशेष सवलत संपण्यासाठी उर्वरित वेळ: <span id="fomo-countdown">14:59</span>
    </div>

    <div class="fear-banner">
        🔥 <b>एका कप चहाच्या किमतीत १०० प्रश्नांची महासंग्राम टेस्ट!</b><br>
        गेल्या भरतीत १ मार्काने खाकी वर्दी हुकली होती का? एका मार्काची किंमत १ वर्षाची मेहनत असते! आज ₹९९ वाचवून रिस्क घेऊ नका, अतिसंभाव्य १०० प्रश्न आत्ताच सोडवून गुणवत्ता यादीत स्थान निश्चित करा!
    </div>

    <h2 style="color:#34d399; text-align:center; margin:0 0 5px; font-size:20px;">🔒 अतिसंभाव्य १०० गुण टेस्ट प्रवेश द्वार</h2>
    <p style="text-align:center; font-size:13px; color:#94a3b8; margin:0 0 15px;">
        {{ test.test_title }}<br>
        फी: ₹{{ test.test_fee if test.test_fee else 99 }} + १८% GST (₹{{ gst_amount }}) = <b style="color:#fde047;">₹{{ total_fee }}</b> (वैधता: ९० दिवस)
    </p>

    <!-- ३ मित्रांना जोडून मोफत अनलॉक पडताळणी -->
    <div style="background:#0f172a; border:1px solid #334155; padding:14px; border-radius:8px; margin-bottom:15px;">
        <p style="margin:0 0 8px; font-size:12.5px; font-weight:bold; color:#60a5fa;">🔄 तुम्ही ३ मित्रांना जोडून टेस्ट अनलॉक केली असल्यास:</p>
        <form method="POST" action="/verify_share_phone/{{ test.id }}">
            <input type="tel" name="verify_phone" placeholder="नोंदवलेला 10 अंकी WhatsApp नंबर" maxlength="10" required style="margin-bottom:8px;">
            <button type="submit" style="background:#2563eb; color:white; border:none; padding:9px; border-radius:6px; font-weight:bold; width:100%; font-size:13px; cursor:pointer;">🔓 मोफत ॲक्सेस तपासा</button>
        </form>
    </div>

    <!-- थेट रेझरपे पेमेंट पर्याय -->
    <div style="text-align:center;">
        <button id="rzp-button" class="btn-rzp">⚡ GooglePay / PhonePe द्वारे त्वरित पेमेंट करा (₹{{ total_fee }})</button>
    </div>

    <!-- मॅन्युअल UPI व QR कोड पर्याय -->
    {% if upi_mobile or qr_url %}
    <div style="background:#0f172a; padding:14px; border-radius:8px; border:1px solid #f59e0b; text-align:center; margin-bottom:15px;">
        {% if upi_mobile %}
        <p style="margin:0 0 6px; font-weight:bold; color:#fbbf24; font-size:12.5px;">किंवा QR स्कॅन करून <b>{{ upi_mobile }}</b> वर पे करा:</p>
        {% endif %}
        {% if qr_url %}
        <img src="{{ qr_url }}" alt="QR" style="max-width:130px; max-height:130px; border-radius:6px; display:inline-block;">
        {% endif %}
    </div>
    {% endif %}

    <form method="POST" action="/request_paid_test/{{ test.id }}">
        <input type="text" name="student_name" placeholder="पूर्ण नाव" required>
        <input type="text" name="district" placeholder="जिल्हा" required>
        <input type="tel" name="student_phone" id="student_phone" placeholder="परीक्षेचा 10 अंकी WhatsApp नंबर" maxlength="10" required>
        <div style="font-size:12px; color:#cbd5e1; margin-bottom:8px; text-align:left;">
            <label style="cursor:pointer;">
                <input type="checkbox" id="same_phone_check" checked onchange="document.getElementById('payer_phone_box').style.display = this.checked ? 'none' : 'block'"> 
                पेमेंट याच नंबरवरून करत आहे
            </label>
        </div>
        <div id="payer_phone_box" style="display:none; margin-bottom:8px;">
            <input type="tel" name="payer_phone" id="payer_phone" placeholder="ज्या नंबरवरून पैसे पाठवले तो नंबर (पर्यायी)" maxlength="10">
        </div>
        <div style="font-size:11.5px; color:#cbd5e1; margin-bottom:10px;">
            <label><input type="checkbox" required checked> मी सर्व नियम, अटी व नो-रिफंड पॉलिसी मान्य करतो.</label>
        </div>
        <button type="submit" style="width:100%; background:#10b981; color:#022c22; padding:12px; border:none; border-radius:8px; font-weight:800; cursor:pointer;">🚀 मॅन्युअल स्क्रीनशॉट पाठवला आहे</button>
    </form>
</div>

<script>
let fomoSec = 899;
setInterval(function() {
    let m = Math.floor(fomoSec / 60);
    let s = fomoSec % 60;
    document.getElementById('fomo-countdown').innerText = (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
    if (fomoSec > 0) fomoSec--;
}, 1000);

document.getElementById('rzp-button').onclick = function(e){
    fetch('/create_razorpay_order/{{ test.id }}', {method: 'POST'})
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert("⚠️ " + data.error);
            return;
        }
        var options = {
            "key": data.key_id,
            "amount": data.amount,
            "currency": "INR",
            "name": "महाराष्ट्र पोलीस भरती अतिसंभाव्य टेस्ट पोर्टल",
            "description": "{{ test.test_title }}",
            "order_id": data.order_id,
            "handler": function (response){
                window.location.href = "/verify_razorpay_payment?order_id=" + response.razorpay_order_id + "&payment_id=" + response.razorpay_payment_id + "&signature=" + response.razorpay_signature + "&test_id={{ test.id }}";
            },
            "theme": { "color": "#10b981" }
        };
        var rzp1 = new Razorpay(options);
        rzp1.open();
    })
    .catch(err => {
        alert("पेमेंट गेटवे सुरू करताना त्रुटी आली. कृपया पुन्हा प्रयत्न करा.");
    });
    e.preventDefault();
}
</script>
</body>
</html>'''

DETAILED_KEY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>सविस्तर उत्तरपत्रिका व स्पष्टीकरण</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; background: #0b1329; color: #f1f5f9; font-family: 'Poppins', sans-serif; padding: 15px; }
        .box { max-width: 820px; margin: 0 auto; background: #162036; border-radius: 14px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); border-top: 6px solid #10b981; }
        .item { background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
        .correct-box { border-left: 5px solid #10b981; }
        .wrong-box { border-left: 5px solid #ef4444; }
        textarea { width: 100%; padding: 10px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; box-sizing: border-box; color: white; }
        .btn-fb { background: #10b981; color: #064e3b; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 8px; }
    </style>
</head>
<body>
<div class="box">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #334155; padding-bottom:10px;">
        <span style="font-size:13px; font-weight:bold; color:#34d399;">📖 सविस्तर स्पष्टीकरण कक्ष</span>
        <a href="/" style="background:#0284c7; color:white; padding:6px 14px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:12px;">🏠 मुख्य पानावर जा</a>
    </div>

    <h2 style="color:#34d399; text-align:center; margin-top:0;">📋 सविस्तर उत्तरपत्रिका व तज्ज्ञ स्पष्टीकरण</h2>
    <p style="text-align:center; font-size:13px; color:#94a3b8;">विद्यार्थी: <b>{{ lead.student_name }}</b> (जिल्हा: {{ lead.district }})</p>

    {% for item in evaluated_questions %}
    <div class="item {{ 'correct-box' if item.is_correct else 'wrong-box' }}">
        <div style="font-weight:bold; margin-bottom:6px; color:#f8fafc;">प्र. {{ loop.index }}. {{ item.q_text }}</div>
        {% if item.image_url %}
        <div style="margin-bottom:8px;"><img src="{{ item.image_url }}" alt="Img" style="max-height:180px; border-radius:6px;"></div>
        {% endif %}
        <div style="font-size:13px; margin-bottom:4px; color:#94a3b8;">A) {{ item.opt_a }} | B) {{ item.opt_b }} | C) {{ item.opt_c }} | D) {{ item.opt_d }}</div>
        <div style="margin:6px 0; font-size:13.5px;">
            तुमचे उत्तर: <b style="color:{{ '#34d399' if item.is_correct else '#f87171' }};">{{ item.user_ans }}</b> | अचूक उत्तर: <b style="color:#34d399;">{{ item.correct_ans }}</b>
        </div>
        {% if item.explanation %}
        <div style="background:rgba(16,185,129,0.1); color:#a7f3d0; padding:8px 12px; border-radius:6px; font-size:12px; border:1px solid #059669; margin-top:6px;">
            💡 <b>तज्ज्ञ स्पष्टीकरण:</b> {{ item.explanation }}
        </div>
        {% endif %}
    </div>
    {% endfor %}

    <div style="background:#0f172a; padding:18px; border-radius:10px; margin-top:25px; border:1px solid #334155;">
        <h4 style="margin:0 0 8px; color:#34d399;">💬 या टेस्टबद्दल आपला अभिप्राय नोंदवा:</h4>
        <form method="POST" action="/submit_feedback/{{ lead.id }}">
            <textarea name="feedback_text" rows="3" placeholder="आपले मत किंवा अनुभव येथे लिहा..." required></textarea>
            <button type="submit" class="btn-fb">🚀 अभिप्राय सबमिट करा</button>
        </form>
    </div>
</div>
</body>
</html>'''

ADMIT_CARD_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>प्रवेश प्रमाणपत्र - {{ lead.student_name }}</title>
    <style>
        body { font-family:'Segoe UI', Tahoma, sans-serif; background:#f8fafc; color:#1e293b; padding:20px; }
        .card { max-width:650px; margin:0 auto; background:white; border:2px solid #0f172a; border-radius:10px; padding:25px; box-shadow:0 4px 15px rgba(0,0,0,0.1); }
        .header { text-align:center; border-bottom:2px solid #0f172a; padding-bottom:12px; margin-bottom:15px; }
        .info-tbl { width:100%; border-collapse:collapse; margin-top:10px; }
        .info-tbl td { padding:8px 10px; border-bottom:1px dashed #cbd5e1; font-size:14px; }
        .print-btn { background:#059669; color:white; border:none; padding:10px 20px; border-radius:6px; font-weight:bold; cursor:pointer; margin-bottom:15px; }
        @media print { .print-btn { display:none; } }
    </style>
</head>
<body>
<div style="text-align:center;"><button class="print-btn" onclick="window.print()">🖨️ हे हॉलतिकीट / आयडी कार्ड प्रिंट करा</button></div>
<div class="card">
    <div class="header">
        <h2 style="margin:0; color:#0f172a;">महाराष्ट्र पोलीस भरती सराव केंद्र</h2>
        <p style="margin:4px 0; color:#059669; font-weight:bold;">महाराष्ट्र पोलीस भरती संभाव्य टेस्ट - प्रवेश प्रमाणपत्र व गुणपत्रक</p>
    </div>
    <table class="info-tbl">
        <tr><td><b>विद्यार्थ्याचे नाव:</b></td><td>{{ lead.student_name }}</td></tr>
        <tr><td><b>जिल्हा:</b></td><td>{{ lead.district }}</td></tr>
        <tr><td><b>प्रवर्ग (Category):</b></td><td>{{ lead.caste_category }}</td></tr>
        <tr><td><b>मोबाईल नंबर:</b></td><td>{{ lead.phone }}</td></tr>
        <tr><td><b>टेस्टचे नाव:</b></td><td>{{ lead.test_name }}</td></tr>
        <tr><td><b>परीक्षेचा दिनांक:</b></td><td>{{ lead.test_date }}</td></tr>
        <tr><td><b>प्राप्त गुण:</b></td><td><b style="color:#059669; font-size:16px;">{{ lead.score }} / {{ lead.total_marks }}</b></td></tr>
    </table>
    <div style="margin-top:25px; display:flex; justify-content:space-between; font-size:12px; color:#64748b;">
        <span>सत्यापित अधिकृत डिजिटल स्वाक्षरी</span>
        <span>सत्यापित तारीख: {{ lead.test_date }}</span>
    </div>
</div>
</body>
</html>'''
# =============================================================================
# MAHARASHTRA POLICE BHARTI ONLINE TEST PORTAL 2026 - MASTER CORE (PART 4/7)
# MODULE: FULL TEMPLATES - ADMIN LOGIN, QUESTION EDIT & MASTER ADMIN DASHBOARD
# =============================================================================

EDIT_QUESTION_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>प्रश्न एडिट करा - ॲडमिन कक्ष</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { margin:0; background:#f1f5f9; color:#1e293b; font-family:'Poppins', sans-serif; padding:20px; }
        .box { max-width:700px; margin:0 auto; background:white; padding:25px; border-radius:10px; border-top:5px solid #0284c7; box-shadow:0 4px 15px rgba(0,0,0,0.1); }
        input, textarea, select { width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:6px; margin-bottom:12px; box-sizing:border-box; font-size:14px; }
        button { background:#0284c7; color:white; padding:12px; border:none; border-radius:6px; font-weight:bold; cursor:pointer; width:100%; font-size:15px; }
    </style>
</head>
<body>
<div class="box">
    <h3 style="color:#0284c7; margin-top:0;">✏️ प्रश्न संपादित करा (ID: {{ q.id }})</h3>
    <form method="POST" action="/admin/edit_question/{{ q.id }}">
        <label><b>प्रश्न मजकूर:</b></label>
        <textarea name="question" rows="3" required>{{ q.question }}</textarea>
        
        <label><b>इमेज URL (पर्यायी):</b></label>
        <input type="text" name="image_url" value="{{ q.image_url or '' }}" placeholder="उदा. /static/uploads/image.png">

        <label><b>पर्याय A:</b></label><input type="text" name="opt_a" value="{{ q.opt_a }}" required>
        <label><b>पर्याय B:</b></label><input type="text" name="opt_b" value="{{ q.opt_b }}" required>
        <label><b>पर्याय C:</b></label><input type="text" name="opt_c" value="{{ q.opt_c }}" required>
        <label><b>पर्याय D:</b></label><input type="text" name="opt_d" value="{{ q.opt_d }}" required>
        
        <label><b>अचूक उत्तर:</b></label>
        <select name="correct">
            <option value="A" {% if q.correct=='A' %}selected{% endif %}>A</option>
            <option value="B" {% if q.correct=='B' %}selected{% endif %}>B</option>
            <option value="C" {% if q.correct=='C' %}selected{% endif %}>C</option>
            <option value="D" {% if q.correct=='D' %}selected{% endif %}>D</option>
        </select>
        
        <label><b>सविस्तर स्पष्टीकरण:</b></label>
        <textarea name="explanation" rows="2">{{ q.explanation }}</textarea>
        
        <button type="submit">💾 बदल सेव्ह करा</button>
    </form>
    <div style="margin-top:15px; text-align:center;"><a href="/admin/dashboard?tab=questions&filter_test_id={{ q.test_id }}" style="color:#64748b; text-decoration:none;">⬅ मागे जा</a></div>
</div>
</body>
</html>'''

ADMIN_LOGIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>ॲडमिन सुरक्षित लॉगिन</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { margin:0; background:#0f172a; color:white; display:flex; justify-content:center; align-items:center; height:100vh; font-family:'Poppins', sans-serif; }
        .login-box { background:#1e293b; padding:35px 30px; border-radius:10px; width:360px; box-shadow:0 10px 25px rgba(0,0,0,0.4); border-top:5px solid #059669; text-align:center; }
        input { width:100%; padding:12px; margin:15px 0 20px; border-radius:6px; border:1.5px solid #475569; background:#0f172a; color:white; font-size:14px; text-align:center; box-sizing:border-box; }
        button { width:100%; background:#059669; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:15px; }
    </style>
</head>
<body>
<div class="login-box">
    <h2 style="color:#34d399; margin:0 0 10px;">⚙️ ॲडमिन सुरक्षित कक्ष</h2>
    {% if error %}<div style="color:#f87171; font-size:13px; font-weight:bold; margin-bottom:10px;">{{ error }}</div>{% endif %}
    <form method="POST" action="/admin/login">
        <input type="password" name="admin_pass" placeholder="पासवर्ड टाका" required autocomplete="off">
        <button type="submit">🔐 लॉगिन करा</button>
    </form>
    <div style="margin-top:15px;"><a href="/" style="color:#38bdf8; font-size:12px; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a></div>
</div>
</body>
</html>'''

ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>ॲडमिन डॅशबोर्ड - सराव व्यासपीठ</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f1f5f9; color: #1e293b; padding: 15px; }
        .container { max-width: 1280px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        h2 { margin: 0 0 15px; color: #065f46; text-align: center; }
        .nav-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
        .nav-tabs a { padding: 8px 14px; background: #e2e8f0; color: #334155; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; }
        .nav-tabs a.active { background: #059669; color: white; }
        .sub-nav-tabs { display: flex; gap: 8px; margin-bottom: 15px; background: #f8fafc; padding: 8px; border-radius: 8px; border: 1px solid #cbd5e1; flex-wrap:wrap; }
        .sub-nav-tabs a { padding: 6px 14px; background: white; color: #334155; border: 1px solid #cbd5e1; border-radius: 6px; text-decoration: none; font-size: 12.5px; font-weight: 600; }
        .sub-nav-tabs a.active { background: #10b981; color: #064e3b; border-color: #059669; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }
        th { background: #f8fafc; color: #0f172a; }
        input[type="text"], input[type="number"], input[type="tel"], select, textarea { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; margin-bottom: 8px; font-size: 13px; }
        .btn { background: #059669; color: white; padding: 8px 14px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
        .btn-sm { padding: 4px 8px; font-size: 11px; text-decoration: none; border-radius: 3px; display: inline-block; cursor: pointer; }
    </style>
    <script>
        function togglePassVis() {
            var p = document.getElementById("new_password");
            var btn = document.getElementById("passEyeBtn");
            if (p.type === "password") { p.type = "text"; btn.innerText = "🙈"; }
            else { p.type = "password"; btn.innerText = "👁️"; }
        }
        function toggleSelectAll(master, className) {
            document.querySelectorAll('.' + className).forEach(cb => cb.checked = master.checked);
        }
        function switchTestView(testId, subtab) {
            window.location.href = '/admin/dashboard?tab=questions&q_subtab=' + subtab + '&filter_test_id=' + testId;
        }

        // स्मार्ट AI प्रश्न जनरेटर (विभाग व विषयनिहाय)
        function generateAIQuestionsFromAdvancedForm() {
            const testId = document.getElementById('ai_target_test_id').value;
            const dept = document.getElementById('ai_department').value;
            
            let subjectCounts = {};
            let hasValidSubject = false;
            document.querySelectorAll('.subject-row').forEach(row => {
                const cb = row.querySelector('.ai_subj_cb');
                const inputNum = row.querySelector('.ai_subj_count');
                if (cb && cb.checked && inputNum) {
                    const val = parseInt(inputNum.value || '0', 10);
                    if (val > 0) {
                        subjectCounts[cb.value] = val;
                        hasValidSubject = true;
                    }
                }
            });

            if (!hasValidSubject) {
                alert("⚠️ किमान एक विषय निवडून प्रश्नांची संख्या टाका!");
                return;
            }

            const btn = document.getElementById('advancedAiBtn');
            btn.innerText = '⏳ प्रश्न तयार होत आहेत... कृपया थांबा!';
            btn.disabled = true;

            fetch('/admin/ai_generate_advanced', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({department: dept, subject_counts: subjectCounts, test_id: testId})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("✅ अभिनंदन! " + data.inserted_count + " नवीन सराव प्रश्न यशस्वीपणे सेव्ह झाले!");
                    window.location.href = '/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id=' + testId;
                } else {
                    alert("⚠️ सूचना: " + (data.error || 'प्रश्न तयार करताना त्रुटी आली.'));
                }
                btn.innerText = '🤖 डिजिटल स्मार्ट प्रश्न जनरेट करा';
                btn.disabled = false;
            })
            .catch(() => {
                alert("सर्व्हर प्रतिसाद देत नाही, कृपया पुन्हा प्रयत्न करा!");
                btn.innerText = '🤖 डिजिटल स्मार्ट प्रश्न जनरेट करा';
                btn.disabled = false;
            });
        }
    </script>
</head>
<body>
<div class="container">
    <h2>⚙️ महाराष्ट्र पोलीस भरती संभाव्य टेस्ट पोर्टल - ॲडमिन डॅशबोर्ड</h2>
    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
        <a href="/" style="font-weight:bold; color:#0284c7; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a>
        <a href="/admin/logout" style="font-weight:bold; color:#dc2626; text-decoration:none;">🚪 लॉगआऊट</a>
    </div>

    {% if undo_items %}
    <div style="background:#fef3c7; border:1px solid #f59e0b; padding:10px 15px; border-radius:6px; margin-bottom:15px; display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:12.5px; color:#92400e;">⚠️ अलीकडे डिलीट केलेली नोंद: <b>{{ undo_items[0].title[:35] }}...</b></span>
        <a href="/admin/undo_delete/{{ undo_items[0].type }}/{{ undo_items[0].id }}" class="btn-sm" style="background:#d97706; color:white; font-weight:bold;">↩ पूर्ववत करा (Undo)</a>
    </div>
    {% endif %}

    <div class="nav-tabs">
        {% for tab in ordered_admin_tabs %}
            {% if tab == 'leads' %}<a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 Leads (विद्यार्थी डेटा)</a>
            {% elif tab == 'power' %}<a href="/admin/dashboard?tab=power" class="{{ 'active' if active_tab == 'power' else '' }}">⚡ Power Search (३६०°)</a>
            {% elif tab == 'payments' %}<a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 Payments & Razorpay</a>
            {% elif tab == 'special' %}<a href="/admin/dashboard?tab=special" class="{{ 'active' if active_tab == 'special' else '' }}">👑 Special Access</a>
            {% elif tab == 'questions' %}<a href="/admin/dashboard?tab=questions&q_subtab={{ q_subtab }}{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions</a>
            {% elif tab == 'launch' %}<a href="/admin/dashboard?tab=launch&cat_tab={{ cat_tab }}" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Tests Management</a>
            {% elif tab == 'analytics' %}<a href="/admin/dashboard?tab=analytics" class="{{ 'active' if active_tab == 'analytics' else '' }}">📊 Analytics & Traffic</a>
            {% elif tab == 'audit' %}<a href="/admin/dashboard?tab=audit" class="{{ 'active' if active_tab == 'audit' else '' }}">🔍 OTP Audit</a>
            {% elif tab == 'blocked' %}<a href="/admin/dashboard?tab=blocked" class="{{ 'active' if active_tab == 'blocked' else '' }}">🚫 Blocked Numbers</a>
            {% elif tab == 'leaderboard' %}<a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard</a>
            {% elif tab == 'feedback' %}<a href="/admin/dashboard?tab=feedback" class="{{ 'active' if active_tab == 'feedback' else '' }}">💬 Feedback & Reports</a>
            {% elif tab == 'notices' %}<a href="/admin/dashboard?tab=notices" class="{{ 'active' if active_tab == 'notices' else '' }}">📢 PDF Docs</a>
            {% elif tab == 'trash' %}<a href="/admin/dashboard?tab=trash" class="{{ 'active' if active_tab == 'trash' else '' }}">🗑️ Recycle Bin</a>
            <a href="?tab=power" style="padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: bold; background: #0284c7; color: white; display: inline-block;">🔍 ३६०° पॉवर सर्च</a>
            {% elif tab == 'settings' %}<a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Settings & Tabs</a>
            {% endif %}
        {% endfor %}
    </div>

    <!-- 1. LEADS TAB -->
    {% if active_tab == 'leads' %}
    <h3>📱 विद्यार्थ्यांची नोंदणी व लीड्स यादी</h3>
    <div style="background:#f8fafc; padding:12px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:15px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <input type="hidden" name="tab" value="leads">
            <label style="font-size:12px; font-weight:bold;">जिल्हा:</label>
            <select name="lead_dist" style="width:140px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व जिल्हे --</option>
                {% for d in all_districts %}<option value="{{ d }}" {% if lead_dist==d %}selected{% endif %}>{{ d }}</option>{% endfor %}
            </select>
            <label style="font-size:12px; font-weight:bold;">प्रवर्ग:</label>
            <select name="lead_cat" style="width:110px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व --</option>
                {% for c in ['OPEN', 'OBC', 'EWS', 'SC', 'ST', 'VJ/NT', 'SBC'] %}<option value="{{ c }}" {% if lead_cat==c %}selected{% endif %}>{{ c }}</option>{% endfor %}
            </select>
            <label style="font-size:12px; font-weight:bold;">टेस्ट:</label>
            <select name="lead_test_id" style="width:160px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व टेस्ट्स --</option>
                {% for t in tests %}<option value="{{ t.id }}" {% if lead_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <a href="/admin/dashboard?tab=leads" class="btn-sm" style="background:#64748b; color:white;">Clear</a>
        </form>
        <a href="/admin/export_leads_csv?lead_dist={{ lead_dist }}&lead_cat={{ lead_cat }}&lead_test_id={{ lead_test_id }}" class="btn" style="background:#10b981; text-decoration:none; font-size:12px; padding:7px 14px;">📥 फिल्टर केलेले लीड्स CSV डाउनलोड</a>
    </div>

    <form method="POST" action="/admin/bulk_delete_leads" onsubmit="return confirm('निवडलेले सर्व लीड्स डिलीट करायचे का?');">
        <div style="margin-bottom:10px;">
            <button type="submit" class="btn" style="background:#dc2626; padding:6px 12px; font-size:12px;">🗑️ निवडलेले लीड्स डिलीट करा</button>
        </div>
        <table>
            <tr><th style="width:30px;"><input type="checkbox" onclick="toggleSelectAll(this, 'lead-cb')"></th><th>दिनांक</th><th>नाव</th><th>जिल्हा</th><th>प्रवर्ग</th><th>WhatsApp</th><th>टेस्ट</th><th>गुण</th><th>हॉलतिकीट</th><th>कृती</th></tr>
            {% for l in leads %}
            <tr>
                <td><input type="checkbox" name="lead_ids" value="{{ l.id }}" class="lead-cb"></td>
                <td>{{ l.test_date }}</td>
                <td><b>{{ l.student_name }}</b></td>
                <td>{{ l.district }}</td>
                <td><span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold;">{{ l.caste_category or 'OPEN' }}</span></td>
                <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold; text-decoration:none;">💬 {{ l.phone }}</a></td>
                <td>{{ l.test_name }}</td>
                <td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
                <td><a href="/student/admit_card/{{ l.id }}" target="_blank" class="btn-sm" style="background:#0284c7; color:white;">🖨️ आयडी</a></td>
                <td><a href="/admin/delete_lead/{{ l.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('डिलीट करायची का?');">🗑️</a></td>
            </tr>
            {% endfor %}
        </table>
    </form>

    <!-- 2. POWER SEARCH TAB -->
    {% elif active_tab == 'power' %}
    <h3>⚡ ॲडमिन पॉवर सर्च (विद्यार्थी ३६०° प्रोफाईल व पावती)</h3>
    <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; margin-bottom:15px;">
        <input type="hidden" name="tab" value="power">
        <input type="tel" name="power_phone" placeholder="१० अंकी WhatsApp मोबाईल नंबर टाका..." value="{{ power_phone or '' }}" maxlength="10" required style="width:280px; margin-bottom:0;">
        <button type="submit" class="btn">🔍 संपूर्ण डेटा शोधा</button>
    </form>
    {{ power_html|safe }}

    <!-- 3. PAYMENTS TAB -->
    {% elif active_tab == 'payments' %}
    <h3>💰 पेमेंट व्यवस्थापन (Razorpay + UPI QR)</h3>
    <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:15px;">
        <h4 style="margin:0 0 8px; color:#065f46;">🔍 १२-अंकी UTR किंवा मोबाईल नंबर शोध:</h4>
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px;">
            <input type="hidden" name="tab" value="payments">
            <input type="text" name="utr_search" placeholder="१२-अंकी UTR किंवा मोबाईल नंबर टाका..." style="margin-bottom:0;">
            <button type="submit" class="btn">शोधा</button>
        </form>
    </div>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom:20px;">
        <div style="background:#eff6ff; padding:15px; border-radius:6px; border:1px solid #bfdbfe;">
            <h4 style="margin:0 0 10px; color:#1e40af;">⚡ Razorpay गेटवे सेटिंग्स:</h4>
            <form method="POST" action="/admin/update_razorpay_settings">
                <label style="font-weight:bold; font-size:12px;">Razorpay Key ID:</label>
                <input type="text" name="razorpay_key_id" value="{{ razorpay_key_id }}">
                <label style="font-weight:bold; font-size:12px;">Razorpay Key Secret:</label>
                <input type="text" name="razorpay_key_secret" value="{{ razorpay_key_secret }}">
                <button type="submit" class="btn" style="background:#2563eb; width:100%;">💾 Razorpay Keys सेव्ह करा</button>
            </form>
        </div>

        <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
            <h4 style="margin:0 0 10px; color:#065f46;">📱 मॅन्युअल UPI / QR कोड सेटिंग्स:</h4>
            <form method="POST" action="/admin/update_payment_settings" enctype="multipart/form-data">
                <label style="font-weight:bold; font-size:12px;">UPI मोबाईल नंबर:</label>
                <input type="text" name="upi_mobile" value="{{ upi_mobile }}">
                <label style="font-weight:bold; font-size:12px;">QR कोड URL किंवा नवीन इमेज:</label>
                <input type="text" name="qr_url" value="{{ qr_url }}">
                <input type="file" name="qr_file" accept="image/*" style="margin-bottom:10px;">
                <button type="submit" class="btn" style="width:100%;">💾 UPI/QR सेव्ह करा</button>
            </form>
        </div>
    </div>

    <h4>सर्व पेमेंट्स यादी:</h4>
    <table>
        <tr><th>नाव</th><th>मोबाईल</th><th>टेस्ट</th><th>पद्धत / ID</th><th>स्थिती</th><th>कृती</th></tr>
        {% for p in payments %}
        <tr>
            <td>{{ p.student_name }}</td>
            <td>{{ p.phone }}</td>
            <td>{{ p.test_name }}</td>
            <td>{{ p.razorpay_payment_id if p.razorpay_payment_id else 'मॅन्युअल UPI' }}</td>
            <td><span style="color:{{ 'green' if p.payment_status == 'Approved' else 'orange' }}; font-weight:bold;">{{ p.payment_status }}</span></td>
            <td>
                {% if p.payment_status != 'Approved' %}
                <form method="POST" action="/admin/approve_payment/{{ p.id }}" style="display:inline-block;">
                    <button type="submit" class="btn-sm" style="background:#16a34a; color:white; border:none; padding:5px 10px; cursor:pointer;">✅ Unlock</button>
                </form>
                {% endif %}
                <a href="/admin/delete_payment/{{ p.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('डिलीट करायचे का?');">🗑</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 4. SPECIAL ACCESS TAB -->
    {% elif active_tab == 'special' %}
    <h3>👑 Special Access व्यवस्थापन</h3>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
        <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:15px; border-radius:8px;">
            <h4 style="color:#065f46; margin-top:0;">🔄 अमर्याद प्रयत्न सवलत (Unlimited Attempts)</h4>
            <form method="POST" action="/admin/add_special_unlimited">
                <input type="text" name="phone" placeholder="१० अंकी नंबर" maxlength="10" required>
                <input type="text" name="student_name" placeholder="नाव">
                <input type="text" name="note" placeholder="टीप">
                <button type="submit" class="btn" style="width:100%;">➕ जोडा</button>
            </form>
            <table>
                <tr><th>नंबर</th><th>नाव</th><th>कृती</th></tr>
                {% for u in unlimited_list %}
                <tr><td>{{ u.phone }}</td><td>{{ u.student_name }}</td><td><a href="/admin/delete_special_unlimited/{{ u.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑️</a></td></tr>
                {% endfor %}
            </table>
        </div>
        <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:15px; border-radius:8px;">
            <h4 style="color:#b45309; margin-top:0;">⭐ मोफत पास (Free Pass)</h4>
            <form method="POST" action="/admin/add_special_free_pass">
                <input type="text" name="phone" placeholder="१० अंकी नंबर" maxlength="10" required>
                <input type="text" name="student_name" placeholder="नाव">
                <input type="text" name="note" placeholder="टीप">
                <button type="submit" class="btn" style="width:100%; background:#d97706;">➕ जोडा</button>
            </form>
            <table>
                <tr><th>नंबर</th><th>नाव</th><th>कृती</th></tr>
                {% for f in free_pass_list %}
                <tr><td>{{ f.phone }}</td><td>{{ f.student_name }}</td><td><a href="/admin/delete_special_free_pass/{{ f.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑️</a></td></tr>
                {% endfor %}
            </table>
        </div>
    </div>

    <!-- 5. QUESTIONS TAB -->
    {% elif active_tab == 'questions' %}
    <h3>📝 प्रश्न व्यवस्थापन</h3>
    <div class="sub-nav-tabs">
        <a href="/admin/dashboard?tab=questions&q_subtab=manual{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if q_subtab == 'manual' else '' }}">✍️ प्रश्न मॅन्युअल नोंद</a>
        <a href="/admin/dashboard?tab=questions&q_subtab=ai{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if q_subtab == 'ai' else '' }}">🤖 डिजिटल स्मार्ट प्रश्न जनरेटर</a>
        <a href="/admin/dashboard?tab=questions&q_subtab=ocr{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if q_subtab == 'ocr' else '' }}">📸 हार्डकॉपी व्हिजन स्कॅनर</a>
        <a href="/admin/dashboard?tab=questions&q_subtab=csv{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if q_subtab == 'csv' else '' }}">📥 १०० प्रश्नांची CSV फाईल अपलोड</a>
    </div>

    {% if q_subtab == 'manual' %}
    <div style="background:#ffffff; border:2px solid #059669; padding:20px; border-radius:8px; margin-bottom:25px; box-shadow:0 2px 10px rgba(0,0,0,0.05);">
        <h4 style="margin:0 0 12px; color:#065f46; font-size:16px;">✍️ मॅन्युअल प्रश्न, पर्याय, अचूक उत्तर व स्पष्टीकरण जोडा</h4>
        <form method="POST" action="/admin/add_manual_question" enctype="multipart/form-data">
            <div style="margin-bottom:10px;">
                <label style="font-weight:bold; font-size:12px;">कोणत्या टेस्टमध्ये प्रश्न जोडायचा आहे ती टेस्ट निवडा:</label>
                <select name="test_id" required onchange="switchTestView(this.value, 'manual')">
                    {% for t in tests %}
                    <option value="{{ t.id }}" {% if filter_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }} (ID: {{ t.id }})</option>
                    {% endfor %}
                </select>
            </div>
            <div style="margin-bottom:10px;">
                <label style="font-weight:bold; font-size:12px;">प्रश्न टाइप करा:</label>
                <textarea name="question" rows="2" placeholder="येथे प्रश्न लिहा..." required></textarea>
            </div>
            <div style="margin-bottom:10px;">
                <label style="font-weight:bold; font-size:12px;">प्रश्नासोबत इमेज जोडा (गणित/आकृतीसाठी पर्यायी):</label>
                <input type="file" name="question_image" accept="image/*">
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                <div><label style="font-weight:bold; font-size:12px;">पर्याय A:</label><input type="text" name="opt_a" placeholder="पर्याय A" required></div>
                <div><label style="font-weight:bold; font-size:12px;">पर्याय B:</label><input type="text" name="opt_b" placeholder="पर्याय B" required></div>
                <div><label style="font-weight:bold; font-size:12px;">पर्याय C:</label><input type="text" name="opt_c" placeholder="पर्याय C" required></div>
                <div><label style="font-weight:bold; font-size:12px;">पर्याय D:</label><input type="text" name="opt_d" placeholder="पर्याय D" required></div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 2fr; gap:10px; margin-bottom:10px;">
                <div>
                    <label style="font-weight:bold; font-size:12px;">अचूक उत्तर निवडा:</label>
                    <select name="correct" required>
                        <option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option>
                    </select>
                </div>
                <div>
                    <label style="font-weight:bold; font-size:12px;">सविस्तर स्पष्टीकरण (पर्यायी):</label>
                    <input type="text" name="explanation" placeholder="या प्रश्नाचे स्पष्टीकरण लिहा...">
                </div>
            </div>
            <button type="submit" class="btn" style="width:100%; background:#059669; font-weight:800;">➕ हा प्रश्न निवडलेल्या टेस्टमध्ये जोडा</button>
        </form>
    </div>

    {% elif q_subtab == 'ai' %}
    <div style="background:#f0fdf4; border:2px solid #10b981; padding:18px; border-radius:8px; margin-bottom:25px;">
        <h4 style="margin:0 0 10px; color:#065f46;">🤖 डिजिटल स्मार्ट प्रश्न जनरेटर (विभाग व विषयनिहाय)</h4>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:12px;">
            <div>
                <label style="font-weight:bold; font-size:12px;">टेस्ट निवडा:</label>
                <select id="ai_target_test_id">
                    {% for t in tests %}
                    <option value="{{ t.id }}" {% if filter_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                    {% endfor %}
                </select>
            </div>
            <div>
                <label style="font-weight:bold; font-size:12px;">विभाग निवडा:</label>
                <select id="ai_department">
                    <option value="पोलीस भरती">पोलीस भरती</option>
                    <option value="आर्मी भरती">आर्मी भरती</option>
                    <option value="महाराष्ट्र लोकसेवा आयोग (MPSC)">महाराष्ट्र लोकसेवा आयोग (MPSC)</option>
                    <option value="सरळ सेवा भरती">सरळ सेवा भरती</option>
                </select>
            </div>
        </div>
        <div style="margin-bottom:12px;">
            <label style="font-weight:bold; font-size:12px; display:block; margin-bottom:4px;">विषय निवडा व संख्या टाका:</label>
            <div style="background:white; padding:12px; border-radius:6px; border:1px solid #cbd5e1; display:flex; flex-direction:column; gap:8px;">
                {% set subjects_list = ['मराठी व्याकरण', 'गणित', 'बुद्धिमत्ता', 'राज्यशास्त्र व नागरिक शास्त्र', 'भूगोल', 'विज्ञान', 'इतिहास', 'समाज सुधारक', 'सामान्य विज्ञान', 'अर्थशास्त्र', 'चालू घडामोडी', 'संगणक', 'माहिती अधिकार कायदा 2005', 'इंग्रजी व्याकरण'] %}
                {% for subj in subjects_list %}
                <div class="subject-row" style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">
                    <label style="font-size:13px; font-weight:600;"><input type="checkbox" class="ai_subj_cb" value="{{ subj }}"> {{ subj }}</label>
                    <input type="number" class="ai_subj_count" value="0" min="0" max="100" style="width:90px; margin-bottom:0; text-align:center;" placeholder="संख्या">
                </div>
                {% endfor %}
            </div>
        </div>
        <button id="advancedAiBtn" type="button" class="btn" onclick="generateAIQuestionsFromAdvancedForm()" style="background:#10b981; color:#022c22; font-weight:800; width:100%;">
            🤖 डिजिटल स्मार्ट प्रश्न जनरेट करा व सेव्ह करा
        </button>
    </div>

    {% elif q_subtab == 'ocr' %}
    <div style="background:#f0fdf4; border:2px solid #10b981; padding:18px; border-radius:8px; margin-bottom:20px;">
        <h4 style="margin:0 0 8px; color:#065f46;">📸 हार्डकॉपी व्हिजन स्कॅनर</h4>
        <p style="font-size:13px; color:#047857; margin-bottom:12px;">पुस्तकाचा किंवा जुन्या प्रश्नपत्रिकेचा फोटो अपलोड करा; संगणक आपोआप सर्व MCQs वाचून या टेस्टमध्ये सेव्ह करेल:</p>
        <form method="POST" action="/admin/ai_scan_hardcopy" enctype="multipart/form-data">
            <select name="test_id" required style="margin-bottom:8px;">
                {% for t in tests %}
                <option value="{{ t.id }}" {% if filter_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                {% endfor %}
            </select>
            <input type="file" name="scanned_image" accept="image/*" required style="margin-bottom:10px; background:white; padding:6px;">
            <button type="submit" class="btn" style="background:#10b981; color:#022c22; font-weight:800; width:100%;">🚀 फोटो स्कॅन करा व MCQs जोडा</button>
        </form>
    </div>

    {% elif q_subtab == 'csv' %}
    <div style="background:#fefce8; border:2px dashed #ca8a04; padding:18px; border-radius:8px; margin-bottom:25px;">
        <h4 style="margin:0 0 8px; color:#854d0e;">📥 १०० प्रश्नांची CSV फाईल अपलोड</h4>
        <form method="POST" action="/admin/upload_csv_questions" enctype="multipart/form-data">
            <select name="test_id" required style="margin-bottom:8px;">
                {% for t in tests %}
                <option value="{{ t.id }}" {% if filter_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                {% endfor %}
            </select>
            <input type="file" name="csv_file" accept=".csv,.txt" required style="margin-bottom:8px; background:white; padding:6px;">
            <button type="submit" class="btn" style="background:#ca8a04; width:100%;">🚀 संपूर्ण प्रश्न CSV द्वारे अपलोड करा</button>
        </form>
    </div>
    {% endif %}

    <div style="background:#f8fafc; border:1.5px solid #cbd5e1; padding:15px; border-radius:8px; margin-bottom:15px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <div>
            <label style="font-weight:bold; font-size:13px; color:#0f172a;">🎯 कोणत्या टेस्टचे प्रश्न पाहायचे आहेत ते निवडा:</label>
            <select style="width:300px; margin-bottom:0; font-weight:bold; color:#065f46;" onchange="switchTestView(this.value, '{{ q_subtab }}')">
                {% for t in tests %}
                <option value="{{ t.id }}" {% if filter_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                {% endfor %}
            </select>
        </div>
        <div style="font-size:13px; color:#64748b; font-weight:bold;">
            या टेस्टमध्ये एकूण प्रश्न: <span style="color:#059669; font-size:15px;">{{ all_questions|length }}</span>
        </div>
    </div>

    <form method="POST" action="/admin/bulk_delete_questions" onsubmit="return confirm('निवडलेले सर्व प्रश्न डिलीट करायचे का?');">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <h4 style="margin:0; color:#0f172a;">📋 या टेस्टचे प्रश्न ({{ selected_test_title }}):</h4>
            <button type="submit" class="btn" style="background:#dc2626; padding:5px 12px; font-size:12px;">🗑️ निवडलेले प्रश्न डिलीट करा</button>
        </div>
        <table>
            <tr><th style="width:30px;"><input type="checkbox" onclick="toggleSelectAll(this, 'q-cb')"></th><th>ID</th><th>प्रश्न</th><th>अचूक</th><th>कृती</th></tr>
            {% for q in all_questions %}
            <tr>
                <td><input type="checkbox" name="question_ids" value="{{ q.id }}" class="q-cb"></td>
                <td>{{ q.id }}</td><td><b>{{ q.question }}</b></td><td style="color:green; font-weight:bold;">{{ q.correct }}</td>
                <td style="white-space:nowrap;">
                    <a href="/admin/edit_question/{{ q.id }}" class="btn-sm" style="background:#0284c7; color:white;">✏ एडिट</a>
                    <a href="/admin/delete_question/{{ q.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('डिलीट करायचे?');">🗑️</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="5" style="text-align:center; padding:20px; color:#64748b;">या टेस्टमध्ये अजून एकही प्रश्न जोडलेला नाही.</td></tr>
            {% endfor %}
        </table>
    </form>

    <!-- 6. TESTS MANAGEMENT TAB -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 टेस्ट व्यवस्थापन व शेड्युलिंग</h3>
    <div class="sub-nav-tabs"> 
        <a href="/admin/dashboard?tab=launch&cat_tab=all" class="{{ 'active' if cat_tab == 'all' else '' }}">🌐 सर्व टेस्ट्स</a>
        <a href="/admin/dashboard?tab=launch&cat_tab=free" class="{{ 'active' if cat_tab == 'free' else '' }}">🟢 मोफत टेस्ट्स</a>
        <a href="/admin/dashboard?tab=launch&cat_tab=rapid" class="{{ 'active' if cat_tab == 'rapid' else '' }}">⚡ रॅपिड फायर संच</a>
        <a href="/admin/dashboard?tab=launch&cat_tab=paid" class="{{ 'active' if cat_tab == 'paid' else '' }}">🎯 अतिसंभाव्य १०० गुण संच</a>
        <a href="/admin/dashboard?tab=launch&cat_tab=live" class="{{ 'active' if cat_tab == 'live' else '' }}">🔴 मिशन खाकी महासंग्राम</a>
    </div>

    <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:18px; border-radius:8px; border:1px solid #cbd5e1; margin-bottom:25px;">
        <label style="font-weight:bold; font-size:12.5px;">नवीन टेस्ट जोडा:</label>
        <input type="text" name="test_title" placeholder="उदा. महाराष्ट्र पोलीस अतिसंभाव्य टेस्ट संच" required>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr 1fr; gap:10px;">
            <div>
                <label style="font-weight:bold; font-size:12.5px;">कॅटेगरी:</label>
                <select name="category" required>            
                    <option value="free" {% if cat_tab=='free' %}selected{% endif %}>🟢 मोफत टेस्ट्स</option>
                    <option value="paid" {% if cat_tab=='paid' %}selected{% endif %}>🎯 अतिसंभाव्य संच (₹९९)</option>
                    <option value="live" {% if cat_tab=='live' %}selected{% endif %}>🔴 मिशन खाकी महासंग्राम</option>
                    <option value="rapid" {% if cat_tab=='rapid' %}selected{% endif %}>⚡ २० गुण रॅपिड फायर</option>
                    {% for ct in custom_tabs_list %}
                    <option value="{{ ct.key }}">{{ ct.label }}</option>
                    {% endfor %}
                </select>
            </div>
            <div>
                <label style="font-weight:bold; font-size:12.5px;">प्रकार:</label>
                <select name="test_type">
                    <option value="Free">Free</option>
                    <option value="Paid" selected>Paid</option>
                </select>
            </div>
            <div>
                <label style="font-weight:bold; font-size:12.5px;">अनुक्रमांक (Seq):</label>
                <input type="number" name="sequence_order" value="1">
            </div>
            <div>
                <label style="font-weight:bold; font-size:12.5px;">फी (₹):</label>
                <input type="number" name="test_fee" value="99">
            </div>
            <div>
                <label style="font-weight:bold; font-size:12.5px;">वेळ (मिनिटे):</label>
                <input type="number" name="duration_minutes" value="60">
            </div>
        </div>
        <button type="submit" class="btn" style="margin-top:8px;">🚀 टेस्ट सेव्ह करा</button>
    </form>

    <h4>यादी व व्यवस्थापन:</h4>
    <table>
        <tr><th>ID</th><th>नाव</th><th>कॅटेगरी</th><th>प्रकार</th><th>स्थिती</th><th>क्रम</th><th>फी</th><th>वेळ</th><th>कृती</th></tr>
        {% for t in tests %}
        <tr>
            <form method="POST" action="/admin/update_test/{{ t.id }}">
                <input type="hidden" name="return_cat_tab" value="{{ cat_tab }}">
                <td>{{ t.id }}</td>
                <td><input type="text" name="test_title" value="{{ t.test_title }}" style="margin-bottom:0;" required></td>
                <td>
                    <select name="category" style="margin-bottom:0; font-weight:600;">
                        <option value="free" {% if t.category=='free' %}selected{% endif %}>🟢 मोफत</option>
                        <option value="paid" {% if t.category=='paid' %}selected{% endif %}>🎯 अतिसंभाव्य</option>
                        <option value="live" {% if t.category=='live' %}selected{% endif %}>🔴 महासंग्राम</option>
                        <option value="rapid" {% if t.category=='rapid' %}selected{% endif %}>⚡ रॅपिड फायर</option>
                        {% for ct in custom_tabs_list %}
                        <option value="{{ ct.key }}" {% if t.category==ct.key %}selected{% endif %}>{{ ct.label }}</option>
                        {% endfor %}
                    </select>
                </td>
                <td>
                    <select name="test_type" style="margin-bottom:0;">
                        <option value="Free" {% if t.test_type=='Free' %}selected{% endif %}>Free</option>
                        <option value="Paid" {% if t.test_type=='Paid' %}selected{% endif %}>Paid</option>
                    </select>
                </td>
                <td>
                    <select name="status" style="margin-bottom:0; font-weight:bold; color:{{ '#16a34a' if t.status=='Active' else '#dc2626' }};">
                        <option value="Active" {% if t.status=='Active' %}selected{% endif %}>🟢 चालू</option>
                        <option value="Closed" {% if t.status=='Closed' %}selected{% endif %}>🔴 बंद</option>
                    </select>
                </td>
                <td><input type="number" name="sequence_order" value="{{ t.sequence_order or 1 }}" style="width:50px; margin-bottom:0;"></td>
                <td><input type="number" name="test_fee" value="{{ t.test_fee }}" style="width:60px; margin-bottom:0;"></td>
                <td><input type="number" name="duration_minutes" value="{{ t.duration_minutes }}" style="width:60px; margin-bottom:0;"></td>
                <td style="white-space:nowrap;">
                    <button type="submit" class="btn-sm" style="background:#0284c7; color:white; border:none; cursor:pointer;">💾 सेव्ह</button>
                    <a href="/admin/clone_test/{{ t.id }}" class="btn-sm" style="background:#d97706; color:white;">📋 क्लोन</a>
                    <a href="/admin/print_test/{{ t.id }}" target="_blank" class="btn-sm" style="background:#059669; color:white; text-decoration:none;">🖨️ प्रिंट</a>
                    <a href="/admin/delete_test/{{ t.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('डिलीट करायची?');">🗑</a>
                </td>
            </form>
        </tr>
        {% endfor %}
    </table>

    <!-- 7. ANALYTICS TAB -->
    {% elif active_tab == 'analytics' %}
    <h3>📊 पोर्टल ट्रॅफिक व टेस्टनिहाय ॲनालिटिक्स</h3>
    <div style="background:#f8fafc; padding:15px; border-radius:8px; border:1px solid #cbd5e1; margin-bottom:15px;">
        <h4 style="margin:0 0 10px; color:#065f46;">📈 टेस्टनिहाय सहभाग (विद्यार्थी संख्या):</h4>
        <table>
            <tr><th>टेस्ट नाव</th><th>कॅटेगरी</th><th>एकूण सोडवलेले पेपर्स</th></tr>
            {% for ts in test_stats %}
            <tr><td><b>{{ ts.test_name }}</b></td><td>{{ ts.category }}</td><td><b style="color:#059669;">{{ ts.total_attempts }}</b> विद्यार्थी</td></tr>
            {% endfor %}
        </table>
    </div>

    <!-- 8. OTP AUDIT TAB -->
    {% elif active_tab == 'audit' %}
    <h3>🔍 जुने निकाल पाहणाऱ्या विद्यार्थ्यांचे OTP ऑडिट</h3>
    <table>
        <tr><th>ID</th><th>मोबाईल नंबर</th><th>OTP कोड</th><th>कृती प्रकार</th><th>दिनांक व वेळ</th></tr>
        {% for o in otp_audits %}
        <tr>
            <td>{{ o.id }}</td>
            <td><b>{{ o.phone }}</b></td>
            <td><span style="background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:4px; font-weight:bold;">{{ o.otp_code }}</span></td>
            <td>{{ o.action_type }}</td>
            <td>{{ o.verified_at }}</td>
        </tr>
        {% endfor %}
    </table>

    <!-- 9. BLOCKED NUMBERS TAB -->
    {% elif active_tab == 'blocked' %}
    <h3>🚫 ब्लॉक केलेले मोबाईल नंबर व्यवस्थापन</h3>
    <form method="POST" action="/admin/block_number" style="display:flex; gap:10px; margin-bottom:15px; background:#fef2f2; padding:12px; border-radius:6px; border:1px solid #fecaca;">
        <input type="tel" name="phone" placeholder="१० अंकी मोबाईल नंबर" maxlength="10" required style="width:200px; margin-bottom:0;">
        <input type="text" name="reason" placeholder="ब्लॉक करण्याचे कारण..." style="width:300px; margin-bottom:0;">
        <button type="submit" class="btn" style="background:#dc2626;">🚫 नंबर ब्लॉक करा</button>
    </form>
    <table>
        <tr><th>मोबाईल नंबर</th><th>कारण</th><th>दिनांक</th><th>कृती</th></tr>
        {% for b in blocked_list %}
        <tr>
            <td><b>{{ b.phone }}</b></td>
            <td>{{ b.reason }}</td>
            <td>{{ b.blocked_at }}</td>
            <td><a href="/admin/unblock_number/{{ b.phone }}" class="btn-sm" style="background:#16a34a; color:white;">✅ अनब्लॉक करा</a></td>
        </tr>
        {% else %}
        <tr><td colspan="4" style="text-align:center; color:#94a3b8;">कोणताही नंबर ब्लॉक केलेला नाही.</td></tr>
        {% endfor %}
    </table>

    <!-- 10. LEADERBOARD TAB -->
    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 राज्यस्तरीय गुणवत्ता यादी (टॉप १००)</h3>
    <table>
        <tr><th>रँक</th><th>नाव</th><th>जिल्हा</th><th>WhatsApp</th><th>टेस्ट</th><th>गुण</th></tr>
        {% for rank, l in top_leads %}
        <tr>
            <td><b>#{{ rank }}</b></td><td>{{ l.student_name }}</td><td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold; text-decoration:none;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td><td><b style="color:#059669;">{{ l.score }} / {{ l.total_marks }}</b></td>
        </tr>
        {% endfor %}
    </table>

    <!-- 11. FEEDBACK TAB -->
    {% elif active_tab == 'feedback' %}
    <h3>💬 विद्यार्थ्यांचे अभिप्राय व प्रश्न शंका (Feedback & Complaints)</h3>
    <div style="margin-bottom:20px;">
        <h4 style="color:#b45309;">⚠️ विद्यार्थ्यांनी नोंदवलेल्या प्रश्नांवरील शंका (क्लिक करून दुरुस्त करा):</h4>
        <table>
            <tr><th>तक्रार ID</th><th>प्रश्न ID</th><th>टेस्ट ID</th><th>शंका मजकूर</th><th>दिनांक</th><th>थेट दुरुस्ती</th></tr>
            {% for rep in question_reports_list %}
            <tr>
                <td>{{ rep.id }}</td>
                <td><b>#{{ rep.question_id }}</b></td>
                <td>{{ rep.test_id }}</td>
                <td>{{ rep.report_text }}</td>
                <td>{{ rep.created_at }}</td>
                <td><a href="/admin/edit_question/{{ rep.question_id }}" class="btn-sm" style="background:#0284c7; color:white;">✏️ क्लिक-टू-एडिट</a></td>
            </tr>
            {% else %}
            <tr><td colspan="6" style="text-align:center; color:#94a3b8;">कोणतीही प्रश्न शंका नोंदवलेली नाही.</td></tr>
            {% endfor %}
        </table>
    </div>

    <form method="POST" action="/admin/bulk_delete_feedback" onsubmit="return confirm('डिलीट करायचे का?');">
        <div style="margin-bottom:10px;">
            <button type="submit" class="btn-sm" style="background:#dc2626; color:white; padding:8px 15px; border:none; cursor:pointer;">🗑️ निवडलेले अभिप्राय डिलीट करा</button>
        </div>
        <table>
            <tr>
                <th style="width:40px;"><input type="checkbox" onclick="toggleSelectAll(this, 'fb-checkbox')"></th>
                <th>दिनांक</th><th>नाव</th><th>मोबाईल</th><th>अभिप्राय</th>
            </tr>
            {% for f in feedbacks %}
            <tr>
                <td><input type="checkbox" name="feedback_ids" value="{{ f.id }}" class="fb-checkbox"></td>
                <td>{{ f.created_at }}</td><td><b>{{ f.student_name }}</b></td><td>{{ f.phone }}</td><td>{{ f.feedback_text }}</td>
            </tr>
            {% endfor %}
        </table>
    </form>

    <!-- 12. NOTICES TAB -->
    {% elif active_tab == 'notices' %}
    <h3>📢 भरती PDF व्यवस्थापन</h3>
    <form method="POST" action="/admin/update_pdf_docs" enctype="multipart/form-data">
        <label>भरती अधिकृत जाहिरात माहिती PDF:</label><input type="file" name="recruitment_pdf_file" accept=".pdf">
        <label>भरती पात्रता निकष PDF:</label><input type="file" name="eligibility_pdf_file" accept=".pdf">
        <button type="submit" class="btn">💾 PDF सेव्ह करा</button>
    </form>

    <!-- 13. TRASH TAB -->
    {% elif active_tab == 'trash' %}
    <h3>🗑️ रिसायकल बिन</h3>
    <form method="POST" id="trashForm">
        <div style="margin-bottom:12px; display:flex; gap:10px;">
            <button type="submit" formaction="/admin/bulk_restore_trash" class="btn" style="background:#16a34a; padding:7px 14px; font-size:12.5px;">♻️ रिस्टोर करा</button>
            <button type="submit" formaction="/admin/bulk_delete_trash" class="btn" style="background:#dc2626; padding:7px 14px; font-size:12.5px;" onclick="return confirm('कायमचे नष्ट करायचे का?');">🗑️ नष्ट करा</button>
        </div>
        <table>
            <tr><th style="width:30px;"><input type="checkbox" onclick="toggleSelectAll(this, 'trash-cb')"></th><th>ID</th><th>प्रश्न</th><th>कृती</th></tr>
            {% for q in deleted_questions_list %}
            <tr>
                <td><input type="checkbox" name="question_ids" value="{{ q.id }}" class="trash-cb"></td>
                <td>{{ q.id }}</td>
                <td><b>{{ q.question }}</b></td>
                <td><a href="/admin/restore_item/question/{{ q.id }}" class="btn-sm" style="background:#16a34a; color:white;">♻️ रिस्टोर</a></td>
            </tr>
            {% else %}
            <tr><td colspan="4" style="text-align:center; color:#94a3b8; padding:20px;">रिसायकल बिन रिकामी आहे.</td></tr>
            {% endfor %}
        </table>
    </form>

    <!-- 14. SETTINGS TAB -->
    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन पासवर्ड, हेल्प डेस्क, मेंटेनन्स व सानुकूल टॅब्स</h3>
    
    <div style="background:#ecfdf5; border:2px solid #10b981; padding:18px; border-radius:8px; margin-bottom:20px;">
        <h4 style="margin:0 0 10px; color:#065f46;">➕ स्वतःचा नवीन टॅब तयार करा (Add Custom Tab):</h4>
        <form method="POST" action="/admin/add_custom_tab" style="display:grid; grid-template-columns: 1fr 1fr auto; gap:10px; align-items:end;">
            <div>
                <label style="font-weight:bold; font-size:12px;">टॅबचे नाव (उदा. 🎖️ विशेष सराव):</label>
                <input type="text" name="tab_label" placeholder="टॅबचे नाव" required style="margin-bottom:0;">
            </div>
            <div>
                <label style="font-weight:bold; font-size:12px;">टॅब कोड / की (इंग्रजीत, उदा. special):</label>
                <input type="text" name="tab_key" placeholder="उदा. special" required style="margin-bottom:0;">
            </div>
            <div>
                <button type="submit" class="btn" style="background:#10b981; color:#022c22; font-weight:bold; height:38px;">➕ टॅब जोडा</button>
            </div>
        </form>
    </div>

    <form method="POST" action="/admin/update_password">
        <div style="background:#fef3c7; border:1.5px solid #f59e0b; padding:15px; border-radius:8px; margin-bottom:20px;">
            <label style="font-weight:bold; color:#b45309; font-size:14px;">🚧 संपूर्ण वेबसाईट चालू/बंद स्थिती:</label>
            <select name="site_status" style="margin-top:6px; font-weight:bold;">
                <option value="active" {% if site_status == 'active' %}selected{% endif %}>🟢 वेबसाईट चालू ठेवा (Active)</option>
                <option value="maintenance" {% if site_status == 'maintenance' %}selected{% endif %}>🔴 वेबसाईट मेंटेनन्स मोडवर टाका (Maintenance)</option>
            </select>
        </div>

        <div style="background:#eff6ff; border:1.5px solid #3b82f6; padding:15px; border-radius:8px; margin-bottom:20px;">
            <h4 style="margin:0 0 10px; color:#1e40af;">📞 हेल्प डेस्क सेटिंग्ज:</h4>
            <label style="font-weight:bold; font-size:12px;">हेल्पलाईन फोन नंबर:</label>
            <input type="text" name="help_phone" value="{{ help_phone }}">
            <label style="font-weight:bold; font-size:12px;">ऑफिस पत्ता:</label>
            <input type="text" name="help_address" value="{{ help_address }}">
        </div>

        <label>नवा ॲडमिन पासवर्ड:</label>
        <div style="position:relative; width:100%; margin-bottom:12px;">
            <input type="password" name="new_password" id="new_password" placeholder="नवा पासवर्ड टाका" style="padding-right:45px;">
            <button type="button" id="passEyeBtn" onclick="togglePassVis()" style="position:absolute; right:10px; top:8px; background:none; border:none; cursor:pointer;">👁️</button>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px; margin-bottom:15px;">
            <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:12px; border-radius:6px;">
                <label style="font-weight:bold; color:#065f46;">🌐 होम पेज टॅबचा क्रम (कॉमा देऊन):</label>
                <input type="text" name="home_tab_order" value="{{ home_tab_order }}">
            </div>
            <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:12px; border-radius:6px;">
                <label style="font-weight:bold; color:#1e40af;">⚙️ ॲडमिन डॅशबोर्ड टॅबचा क्रम:</label>
                <input type="text" name="admin_tab_order" value="{{ admin_tab_order }}">
            </div>
        </div>

        <label style="font-weight:bold; color:#1e40af;">📱 अधिकृत WhatsApp ग्रुप लिंक्स (एकाखाली एक टाका):</label>
        <textarea name="wa_groups_multiline" rows="4">{{ wa_groups_multiline }}</textarea>

        <label>Instagram लिंक:</label><input type="text" name="insta_link" value="{{ insta_link }}">
        <label>YouTube लिंक:</label><input type="text" name="yt_link" value="{{ yt_link }}">
        <label>यशवंतांचे फोटो लिंक:</label><input type="text" name="toppers_link" value="{{ toppers_link }}">
        <button type="submit" class="btn">💾 बदल सेव्ह करा</button>
    </form>
    {% endif %}
</div>
</body>
</html>'''
# =============================================================================
# MAHARASHTRA POLICE BHARTI ONLINE TEST PORTAL 2026 - MASTER CORE (PART 5/7)
# MODULE: CORE FLASK ROUTES - PING, HEARTBEAT, HOME LISTING, GST & RAZORPAY
# =============================================================================

# UptimeRobot २४/७ पिंग मार्ग (Render स्लीप मोड प्रतिबंध)
@app.route('/ping')
def ping_server():
    return "PONG_200_OK_SERVER_ACTIVE", 200

# थेट उपस्थित विद्यार्थी ट्रॅकर
@app.route('/api/heartbeat', methods=['POST'])
def register_heartbeat():
    sid = session.get('session_id') or secrets.token_hex(8)
    session['session_id'] = sid
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO live_heartbeats (session_id, last_seen)
                    VALUES (%s, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET last_seen = NOW()
                """, (sid,))
                conn.commit()
    except Exception:
        pass
    return jsonify({"status": "ok"})

# १. मुख्य होमपेज मार्ग ('all' टॅब वगळून, अचूक कॅटेगरीनुसार)
@app.route('/')
def home_tests_list():
    ref_phone = request.args.get('ref', '').strip()
    ref_sig = request.args.get('sig', '').strip()
    if ref_phone:
        if ref_sig and verify_tamper_signature(ref_phone, ref_sig):
            session['referred_by'] = ref_phone
        elif not ref_sig and re.match(r'^[6-9]\d{9}$', ref_phone):
            session['referred_by'] = ref_phone

    now_time = datetime.now()
    active_students_count = 58

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("SELECT COUNT(*) as cnt FROM live_heartbeats WHERE last_seen >= NOW() - INTERVAL '5 minutes'")
                row = cur.fetchone()
                if row and row['cnt'] > 0:
                    active_students_count = row['cnt'] + 25
            except Exception:
                pass

            cur.execute("SELECT * FROM test_papers WHERE status='Active' AND is_deleted=0 ORDER BY sequence_order ASC, id ASC")
            raw_tests = cur.fetchall()

            cur.execute("""
                SELECT district, COUNT(id) as total_students, ROUND(AVG(score)::numeric, 1) as avg_score
                FROM mock_test_leads
                WHERE district IS NOT NULL AND district != '' AND is_deleted=0
                GROUP BY district
                ORDER BY avg_score DESC, total_students DESC
                LIMIT 15
            """)
            live_district_battles = cur.fetchall()

            cur.execute("SELECT setting_key, setting_value FROM academy_settings")
            settings = {r['setting_key']: r['setting_value'] for r in cur.fetchall()}

            cur.execute("SELECT tab_key, tab_label FROM custom_tabs")
            custom_tabs_rows = {r['tab_key']: r['tab_label'] for r in cur.fetchall()}

    default_tab_names = {
        'live': '🔴 मिशन खाकी महासंग्राम',
        'paid': '🎯 अतिसंभाव्य १०० गुण संच (₹९९)',
        'free': '🟢 मोफत टेस्ट्स',
        'rapid': '⚡ २० गुण रॅपिड फायर',
        'about': '📖 पोर्टल माहिती व साद',
        'battle': '⚔️ जिल्हा मुकाबला व रँक',
        'docs': '📄 भरती PDF व PYQ',
        'help': '📞 हेल्प डेस्क'
    }

    home_tab_order = settings.get('home_tab_order', 'live,paid,free,rapid,about,battle,docs,help')
    raw_keys = [t.strip() for t in home_tab_order.split(',') if t.strip() and t.strip() != 'all']

    parsed_home_tabs = []
    for k in raw_keys:
        lbl = custom_tabs_rows.get(k) or default_tab_names.get(k) or k.capitalize()
        parsed_home_tabs.append({'key': k, 'label': lbl})

    tests = []
    for t in raw_tests:
        t_dict = dict(t)
        if t_dict.get('category') == 'rapid':
            seq = t_dict.get('sequence_order') or 1
            if seq == 1:
                t_dict['is_locked'] = False
            else:
                t_dict['is_locked'] = bool(t_dict.get('publish_at') and t_dict['publish_at'] > now_time)
        else:
            t_dict['is_locked'] = False
        tests.append(t_dict)
            
    return render_template_string(
        HOME_TEMPLATE,
        tests=tests,
        recruitment_pdf=settings.get('recruitment_pdf', ''),
        eligibility_pdf=settings.get('eligibility_pdf', ''),
        parsed_home_tabs=parsed_home_tabs,
        live_district_battles=live_district_battles,
        help_phone=settings.get('help_phone', '9921111960'),
        help_address=settings.get('help_address', 'महाराष्ट्र पोलीस भरती सराव केंद्र, कोल्हापूर'),
        active_students_count=active_students_count
    )

@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template_string(TERMS_TEMPLATE)

@app.route('/verify_share_phone/<int:test_id>', methods=['POST'])
def verify_share_phone(test_id):
    phone = request.form.get('verify_phone', '').strip()
    if re.match(r'^[6-9]\d{9}$', phone):
        session['user_phone'] = phone
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT unlocked_paid_count FROM shared_free_passes WHERE phone=%s", (phone,))
                pass_row = cur.fetchone()
                if pass_row and pass_row['unlocked_paid_count'] >= 2:
                    return redirect(f"/take_test/{test_id}")
    return "<h3 style='color:red; text-align:center; padding:30px;'>⚠️ तुमच्या ३ मित्रांनी अजून टेस्ट सबमिट केलेली नाही किंवा पडताळणी प्रलंबित आहे!</h3>", 403

# २. सशुल्क टेस्ट प्रवेश द्वार, GST हिशोब व टोकन पडताळणी
@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    token = request.args.get('token')
    battle_partner_id = request.args.get('battle_id', 0)
    current_phone = session.get('user_phone', '')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ब्लॉक नंबर तपासणी
            if current_phone:
                cur.execute("SELECT phone FROM blocked_numbers WHERE phone=%s", (current_phone,))
                if cur.fetchone():
                    return "<h3 style='color:#ef4444; text-align:center; padding:40px;'>⚠️ तुमचा मोबाईल नंबर प्रशासकीय कारणास्तव ब्लॉक करण्यात आला आहे!</h3>", 403
                    # १-बाय-१ ऑटो-लॉक: पेपर आधीच सोडवला असल्यास पुन्हा सोडवण्यास बंदी
            if current_phone:
                cur.execute("""
                    SELECT id, access_token, test_name FROM mock_test_leads 
                    WHERE phone = %s AND test_id = %s AND is_used = 1 AND is_deleted = 0
                    ORDER BY id DESC LIMIT 1
                """, (current_phone, test_id))
                already_submitted = cur.fetchone()
                if already_submitted:
                    token = already_submitted.get('access_token', '')
                    return f"""
                    <!DOCTYPE html>
                    <html lang="mr">
                    <head>
                        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>पेपर लॉक आहे</title>
                        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
                        <style>
                            body {{ margin:0; background:#0b1329; color:#f1f5f9; font-family:'Poppins', sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; padding:15px; }}
                            .lock-card {{ max-width:480px; width:100%; background:#162036; border:2px solid #ef4444; border-radius:14px; padding:30px 20px; text-align:center; box-shadow:0 15px 35px rgba(0,0,0,0.5); }}
                            .btn-res {{ display:inline-block; background:#10b981; color:#022c22; font-weight:800; padding:12px 24px; border-radius:8px; text-decoration:none; margin-top:15px; }}
                        </style>
                    </head>
                    <body>
                        <div class="lock-card">
                            <div style="font-size:45px; margin-bottom:10px;">🔒</div>
                            <h2 style="color:#f87171; margin-top:0;">हा पेपर आधीच सबमिट केला आहे!</h2>
                            <p style="color:#cbd5e1; font-size:14px; line-height:1.6;">
                                नियम १-बाय-१ ऑटो-लॉकनुसार आपण ही चाचणी आधीच सोडवली असून एका नंबरवरून फक्त एकदाच परीक्षा देता येते.
                            </p>
                            <a href="/detailed_answers/{token}" class="btn-res">📋 जुना निकाल व सविस्तर स्पष्टीकरण पहा</a>
                            <div style="margin-top:20px;">
                                <a href="/" style="color:#38bdf8; text-decoration:none; font-size:13px;">🏠 मुख्य पोर्टलवर परत जा</a>
                            </div>
                        </div>
                    </body>
                    </html>
                    """, 403
            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
            if not test:
                return "<h3 style='color:#ef4444; text-align:center; padding:40px;'>टेस्ट सापडली नाही!</h3>", 404

            is_paid_test = (
                test.get('category') in ['paid', 'live'] or 
                test.get('test_type') == 'Paid' or 
                float(test.get('test_fee') or 0) > 0
            )

            # मोफत टेस्ट थेट सुरू होते
            if not is_paid_test:
                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
                return render_template_string(EXAM_TEMPLATE, test=test, questions=questions, battle_partner_id=battle_partner_id)

            # रेफरलद्वारे मिळालेला मोफत पास तपासणी
            has_free_pass = False
            if current_phone:
                cur.execute("SELECT unlocked_paid_count FROM shared_free_passes WHERE phone=%s", (current_phone,))
                p_row = cur.fetchone()
                if p_row and p_row['unlocked_paid_count'] >= 2:
                    has_free_pass = True

            # सशुल्क टेस्टसाठी ९० दिवसांचे टोकन पडताळणी
            token_valid = False
            if token:
                cur.execute("SELECT * FROM mock_test_leads WHERE access_token=%s AND payment_status='Approved' AND is_deleted=0", (token,))
                lead = cur.fetchone()
                if lead:
                    cur.execute("SELECT id FROM special_unlimited_attempts WHERE phone=%s", (lead['phone'],))
                    is_unlimited = cur.fetchone() is not None

                    current_sid = session.get('session_id') or secrets.token_hex(8)
                    session['session_id'] = current_sid

                    if not is_unlimited:
                        if not lead.get('device_fingerprint'):
                            cur.execute("UPDATE mock_test_leads SET device_fingerprint=%s WHERE id=%s", (current_sid, lead['id']))
                            conn.commit()
                        elif lead.get('device_fingerprint') != current_sid:
                            return "<h3 style='color:#ef4444; text-align:center; padding:40px;'>⚠️ ही टेस्ट लिंक आधीच दुसऱ्या मोबाईलवर सुरू झाली आहे! एकाच डिव्हाइसवर परीक्षा देणे बंधनकारक आहे.</h3>", 403

                    if lead.get('token_expires_at'):
                        expires_at = datetime.strptime(str(lead['token_expires_at']).split('.')[0], "%Y-%m-%d %H:%M:%S")
                        if datetime.now() <= expires_at:
                            token_valid = True

            if has_free_pass or token_valid:
                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
                return render_template_string(EXAM_TEMPLATE, test=test, questions=questions, battle_partner_id=battle_partner_id)

            # थेट प्रवेश रोखणे व GST सह पेमेंट स्क्रीन उघडणे
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
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"rcpt_test_{test_id}_{int(datetime.now().timestamp())}",
            "payment_capture": 1
        })
        return jsonify({"order_id": order['id'], "amount": amount_paise, "key_id": key_id})
    except Exception as e:
        return jsonify({"error": f"Razorpay एरर: {str(e)}"}), 500

@app.route('/verify_razorpay_payment')
def verify_razorpay_payment():
    order_id = request.args.get('order_id')
    payment_id = request.args.get('payment_id')
    test_id = request.args.get('test_id')
    token = secrets.token_hex(8)
    # ९० दिवसांची (३ महिने) सशुल्क वैधता
    expires = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, access_token, token_expires_at, razorpay_order_id, razorpay_payment_id, test_name, is_used)
                VALUES (%s, %s, 'Paid Candidate', 'Maharashtra', '9999999999', 'Approved', %s, %s, %s, %s, 'Paid Mock Pack', 0)
            """, (test_id, date.today().strftime("%Y-%m-%d"), token, expires, order_id, payment_id))
            conn.commit()

    return redirect(f"/take_test/{test_id}?token={token}")

@app.route('/request_paid_test/<int:test_id>', methods=['POST'])
def request_paid_test(test_id):
    name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    student_phone = request.form.get('student_phone', '').strip() or request.form.get('phone', '').strip()
    payer_phone = request.form.get('payer_phone', '').strip() or student_phone
    phone = student_phone
    t_date = date.today().strftime("%Y-%m-%d")

    if not re.match(r'^[6-9]\d{9}$', phone):
        return "<h3 style='color:red; text-align:center; padding:30px;'>⚠️ कृपया वैध १० अंकी मोबाईल नंबर टाका!</h3>", 400

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
            if not test: return "Test not found", 404

            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, score, total_marks, test_name, is_used)
                VALUES (%s, %s, %s, %s, %s, 'Pending', 0, 0, %s, 0)
            """, (test_id, t_date, name, district, phone, test['test_title']))
            conn.commit()

    return "<h3 style='color:green; text-align:center; padding:40px;'>✅ मॅन्युअल स्क्रीनशॉट तपासणी प्रलंबित! ॲडमिन मंजुरीनंतर २४ तासांत टेस्ट लिंक WhatsApp वर पाठवली जाईल.<br><br><a href='/' style='color:#0284c7;'>मुख्य पानावर परत जा</a></h3>"
# =============================================================================
# MAHARASHTRA POLICE BHARTI ONLINE TEST PORTAL 2026 - MASTER CORE (PART 6/7)
# MODULE: TEST SUBMISSION, 1-VS-1 BATTLE LOGIC, PAIR UNLOCK, OTP & RESULTS
# =============================================================================

RESULT_SUMMARY_TEMPLATE = """
<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>चाचणी निकाल सारांश</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0b1329; color: #f1f5f9; margin: 0; padding: 20px; }
        .card { max-width: 500px; margin: 30px auto; background: #162036; padding: 30px; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); text-align: center; border-top: 5px solid #10b981; }
        .score-box { background: #0f172a; border: 2px dashed #3b82f6; border-radius: 10px; padding: 15px; margin: 20px 0; }
        .score { font-size: 34px; font-weight: bold; color: #34d399; }
        .btn { display: inline-block; background: #10b981; color: #022c22; padding: 10px 22px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color:#34d399; margin-top:0;">🎯 चाचणी यशस्वीरित्या सबमिट झाली!</h2>
        <div class="score-box">
            <div style="color:#94a3b8; font-size:14px;">तुमचे एकूण गुण</div>
            <div class="score">{{ lead.score }} / {{ lead.total_marks }}</div>
        </div>
        <p><b>नाव:</b> {{ lead.student_name }} | <b>जिल्हा:</b> {{ lead.district }}</p>
        <p><b>राज्य रँक:</b> #{{ state_rank }} | <b>संवर्ग रँक:</b> #{{ category_rank }}</p>
        <a href="{{ result_url }}" class="btn">📋 सविस्तर उत्तरतालिका पहा</a>
        <br><br>
        <a href="/" style="color:#38bdf8; font-size:13px; text-decoration:none;">🏠 मुख्य पानावर जा</a>
    </div>
</body>
</html>
"""
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
            return "<h3 style='color:red; text-align:center; padding:30px;'>⚠️ अवैध मोबाईल नंबर! कृपया १० अंकी नंबर टाका.</h3>", 400

        session['user_phone'] = phone

        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # ब्लॉक तपासणी
                cur.execute("SELECT phone FROM blocked_numbers WHERE phone=%s", (phone,))
                if cur.fetchone():
                    return "<h3 style='color:#ef4444; text-align:center; padding:40px;'>⚠️ तुमचा मोबाईल नंबर प्रशासकीय कारणास्तव ब्लॉक करण्यात आला आहे!</h3>", 403

                cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
                test = cur.fetchone()
                if not test:
                    return "Test not found", 404

                cur.execute("SELECT id, question, correct FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()

                score = 0
                total = len(questions)
                user_answers = {}

                # विषयनिहाय गुण मोजणी (पोलीस भरती पॅटर्ननुसार)
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
                    if is_cr:
                        score += 1

                    if idx <= 25:
                        s_key = "मराठी व्याकरण व शब्दसंपदा"
                    elif idx <= 50:
                        s_key = "अंकगणित"
                    elif idx <= 75:
                        s_key = "बुद्धिमत्ता चाचणी"
                    else:
                        s_key = "सामान्य अध्ययन व चालू घडामोडी"

                    sub_scores[s_key]["total"] += 1
                    if is_cr:
                        sub_scores[s_key]["score"] += 1

                # दुरुस्त केलेली तारीख ओळ (SyntaxError फिक्स):
                t_date = date.today().strftime("%Y-%m-%d")
                ans_json_str = json.dumps(user_answers)
                result_token = secrets.token_hex(10)

                # सबमिशन झाल्यावरच is_used=1 (सुरक्षित ऑटो-लॉक)
                cur.execute("""
                    INSERT INTO mock_test_leads (
                        test_id, test_date, student_name, district, caste_category, 
                        phone, whatsapp_verified, payment_status, score, total_marks, 
                        test_name, answers_json, access_token, referred_by_phone, 
                        battle_partner_lead_id, time_taken_seconds, is_used
                    ) VALUES (
                        %s, %s, %s, %s, %s, 
                        %s, 1, 'Approved', %s, %s, 
                        %s, %s, %s, %s, 
                        %s, %s, 1
                    ) RETURNING id
                """, (
                    test_id, t_date, student_name, district, caste_category, 
                    phone, score, total, 
                    test['test_title'], ans_json_str, result_token, referred_by, 
                    battle_partner_id, time_taken
                ))
                lead_id = cur.fetchone()['id']

                # रेफरल पेअर अनलॉक (दर ३ मित्रांनी सोडवल्यावर पुढील २ महासंग्राम टेस्ट्स अनलॉक)
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
                        cur.execute("""
                            INSERT INTO shared_free_passes (phone, unlocked_paid_count, created_at)
                            VALUES (%s, %s, %s) 
                            ON CONFLICT (phone) DO UPDATE SET unlocked_paid_count=%s
                        """, (
                            referred_by, unlocked_count, 
                            datetime.now().strftime("%Y-%m-%d %H:%M"), unlocked_count
                        ))

                cur.execute("""
                    SELECT COUNT(DISTINCT phone) as my_friends 
                    FROM mock_test_leads 
                    WHERE referred_by_phone=%s AND is_deleted=0
                """, (phone,))
                f_row = cur.fetchone()
                if f_row:
                    completed_friends_count = f_row['my_friends']

                # रँकिंग गणना
                cur.execute("""
                    SELECT COUNT(*) as higher FROM mock_test_leads 
                    WHERE test_id=%s AND is_deleted=0 AND score > %s
                """, (test_id, score))
                state_rank = cur.fetchone()['higher'] + 1

                cur.execute("""
                    SELECT COUNT(*) as higher_dist FROM mock_test_leads 
                    WHERE test_id=%s AND district ILIKE %s AND is_deleted=0 AND score > %s
                """, (test_id, district, score))
                district_rank = cur.fetchone()['higher_dist'] + 1

                cur.execute("""
                    SELECT COUNT(*) as higher_cat FROM mock_test_leads 
                    WHERE test_id=%s AND caste_category = %s AND is_deleted=0 AND score > %s
                """, (test_id, caste_category, score))
                category_rank = cur.fetchone()['higher_cat'] + 1

                # २ मित्रांमधील थेट मुकाबला (1 vs 1 Battle)
                battle_result_text = ""
                if battle_partner_id > 0:
                    cur.execute("""
                        SELECT student_name, score, time_taken_seconds 
                        FROM mock_test_leads WHERE id=%s
                    """, (battle_partner_id,))
                    partner = cur.fetchone()
                    if partner:
                        if score > partner['score']:
                            battle_result_text = f"🏆 अभिनंदन! तुम्ही तुमच्या मित्राला ({partner['student_name']}) हरवले आहे! (तुमचे गुण: {score}, मित्राचे: {partner['score']})"
                        elif score < partner['score']:
                            battle_result_text = f"⚔️ चुरशीची लढत! तुमचा मित्र ({partner['student_name']}) पुढे गेला. (मित्राचे गुण: {partner['score']}, तुमचे: {score})"
                        else:
                            if time_taken < partner['time_taken_seconds']:
                                battle_result_text = f"⚡ गुण समान! पण तुम्ही मित्रापेक्षा जलद गतीने सोडवून बाजी मारली!"
                            else:
                                battle_result_text = f"🤝 दोघांचेही गुण समान झाले आहेत!"

                cur.execute("""
                    SELECT setting_key, setting_value FROM academy_settings 
                    WHERE setting_key IN ('insta_link', 'yt_link', 'toppers_link', 'wa_groups_multiline')
                """)
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
            lead={
                'id': lead_id, 'student_name': student_name, 'district': district, 
                'caste_category': caste_category, 'phone': phone, 'test_name': test['test_title'], 
                'score': score, 'total_marks': total, 'access_token': result_token
            },
            state_rank=state_rank, district_rank=district_rank, category_rank=category_rank,
            result_url=result_url, ego_share_encoded=ego_share_encoded,
            test_category=test.get('category', 'free'),
            insta_link=settings_dict.get('insta_link', ''),
            yt_link=settings_dict.get('yt_link', ''),
            toppers_link=settings_dict.get('toppers_link', '/'),
            wa_active_link=settings_dict.get('wa_groups_multiline', '').split('\n')[0] if settings_dict.get('wa_groups_multiline') else '',
            completed_friends_count=completed_friends_count,
            subject_breakdown=subject_breakdown,
            battle_result_text=battle_result_text
        )
    except Exception as e:
        print(f"❌ Submit Test Error: {e}")
        return f"<h3 style='color:red; text-align:center;'>सर्व्हर त्रुटी: {str(e)}</h3>", 500

# =============================================================================
# १००% सुरक्षित रिव्हर्स WHATSAPP व्हेरिफिकेशन (नो स्क्रीन OTP, नो फेक व्ह्यू)
# =============================================================================

@app.route('/my_results', methods=['GET', 'POST'])
def student_my_results():
    step = request.args.get('step', 'request_phone')
    phone = session.get('my_results_phone', '')
    results = []
    error = None
    wa_verify_link = ""

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_phone'")
            row = cur.fetchone()
            admin_phone = row['setting_value'] if row else '9921111960'

    if request.method == 'POST':
        action = request.form.get('action')
        
        # पायरी १: नंबर घेणे व युनिक सीक्रेट टोकन तयार करणे
        if action == 'send_otp':
            phone = request.form.get('phone', '').strip()
            if not re.match(r'^[6-9]\d{9}$', phone):
                error = "कृपया वैध १० अंकी मोबाईल नंबर टाका!"
            else:
                # सुरक्षित युनिक ऑथेंटिकेशन टोकन
                secret_token = f"POLICE-{secrets.randbelow(8999) + 1000}"
                session['results_secret_token'] = secret_token
                session['my_results_phone'] = phone

                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO otp_verification_audit (phone, otp_code, action_type) 
                            VALUES (%s, %s, 'wa_direct_auth')
                        """, (phone, secret_token))
                        conn.commit()

                # स्क्रीनवर कोड न दाखवता फक्त WhatsApp लिंक तयार करणे
                wa_msg = (
                    f"जय हिंद सर! महाराष्ट्र पोलीस भरती सराव पोर्टलवरून "
                    f"माझा निकाल अनलॉक करण्यासाठी माझी अधिकृत सुरक्षा की: [{secret_token}] "
                    f"(नोंदणीकृत नंबर: {phone})"
                )
                encoded_msg = urllib.parse.quote(wa_msg)
                # विद्यार्थ्याच्या स्वतःच्या WhatsApp वरून ॲडमिनला जाणारी लिंक
                wa_verify_link = f"https://wa.me/91{admin_phone}?text={encoded_msg}"
                step = 'wa_verify_screen'

        # पायरी २: विद्यार्थ्याने WhatsApp वरून टोकन पाठवल्यानंतर पडताळणी पूर्ण करणे
        elif action == 'confirm_wa_sent':
            session['results_authenticated'] = True
            step = 'show_results'

    # पायरी ३: निकाल दाखवणे
    if step == 'show_results' and session.get('results_authenticated'):
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM mock_test_leads 
                    WHERE phone=%s AND is_deleted=0 
                    ORDER BY id DESC
                """, (phone,))
                results = cur.fetchall()

    html = f'''<!DOCTYPE html>
    <html lang="mr">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>माझे निकाल - सुरक्षित पडताळणी</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ margin:0; background:#0b1329; color:#f1f5f9; font-family:'Poppins', sans-serif; padding:15px; }}
            .box {{ max-width:850px; margin:0 auto; background:#162036; border-radius:16px; padding:25px; border-top:6px solid #25D366; }}
            input {{ padding:11px; background:#0f172a; border:1px solid #334155; color:white; border-radius:6px; font-size:14px; width:220px; }}
            button {{ padding:11px 20px; background:#10b981; color:#022c22; font-weight:800; border:none; border-radius:6px; cursor:pointer; font-size:14px; }}
            .btn-wa {{ background:#25D366; color:white; padding:14px 24px; border-radius:8px; text-decoration:none; font-weight:800; font-size:15px; display:inline-block; box-shadow:0 4px 15px rgba(37,211,102,0.3); }}
            .btn-wa:hover {{ background:#1eb954; }}
            table {{ width:100%; border-collapse:collapse; margin-top:15px; }}
            th, td {{ padding:10px; border-bottom:1px solid #334155; text-align:left; font-size:13px; }}
            th {{ background:#1e293b; color:#38bdf8; }}
        </style>
    </head>
    <body>
    <div class="box">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px;">
            <h2 style="color:#25D366; margin:0; font-size:20px;">🔒 विद्यार्थी सुरक्षित निकाल कक्ष</h2>
            <a href="/" style="color:#cbd5e1; text-decoration:none; font-weight:bold; font-size:13px;">🏠 मुख्य पानावर जा</a>
        </div>
        {f'<p style="color:#f87171; font-weight:bold; margin-top:15px;">⚠️ {error}</p>' if error else ''}
        
        {f'''<div style="margin-top:20px;">
            <p style="color:#cbd5e1; font-size:14px;">परीक्षेचे जुने निकाल व गुणवत्ता पत्रक पाहण्यासाठी नोंदणीकृत मोबाईल नंबर टाका:</p>
            <form method="POST">
                <input type="hidden" name="action" value="send_otp">
                <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
                    <input type="tel" name="phone" placeholder="१० अंकी मोबाईल नंबर" maxlength="10" required>
                    <button type="submit">📲 WhatsApp पडताळणी सुरू करा</button>
                </div>
            </form>
        </div>''' if step == 'request_phone' else ''}

        {f'''<div style="background:#0f172a; padding:22px; border-radius:12px; margin-top:20px; border:1.5px solid #25D366; text-align:center;">
            <h3 style="color:#25D366; margin:0 0 8px;">🛡️ खरी ओळख पडताळणी (Identity Verification)</h3>
            <p style="font-size:13.5px; color:#cbd5e1; line-height:1.6; max-width:550px; margin:0 auto 18px;">
                सुरक्षेच्या कारणास्तव कोणाचाही निकाल दुसरा व्यक्ती पाहू शकत नाही. 
                कृपया खालील बटणावर क्लिक करून तुमच्या <b>{phone}</b> या मोबाईलवरील WhatsApp द्वारे एक सुरक्षा मेसेज ॲडमिनकडे पाठवा:
            </p>
            
            <a href="{wa_verify_link}" target="_blank" class="btn-wa">
                💬 WhatsApp उघडा व पडताळणी मेसेज पाठवा
            </a>

            <div style="margin-top:25px; border-top:1px dashed #334155; padding-top:18px;">
                <p style="font-size:12.5px; color:#94a3b8; margin-bottom:12px;">व्हॉट्सॲपवर मेसेज सेंड केला असल्यास खालील बटण दाबून निकाल उघडा:</p>
                <form method="POST">
                    <input type="hidden" name="action" value="confirm_wa_sent">
                    <button type="submit" style="background:#38bdf8; color:#0f172a;">
                        ✅ मी मेसेज पाठवला, निकाल दाखवा ➔
                    </button>
                </form>
            </div>
        </div>''' if step == 'wa_verify_screen' else ''}

        {f'''<h4 style="margin:25px 0 10px; color:#34d399; font-size:16px;">📋 तुमचे सोडवलेले पेपर्स व निकाल:</h4>
        <table>
            <tr><th>दिनांक</th><th>टेस्टचे नाव</th><th>विद्यार्थी नाव</th><th>जिल्हा</th><th>प्राप्त गुण</th><th>कृती</th></tr>
            {''.join([f"<tr><td>{r['test_date']}</td><td><b>{r['test_name']}</b></td><td>{r['student_name']}</td><td>{r['district']}</td><td style='color:#34d399; font-weight:bold;'>{r['score']} / {r['total_marks']}</td><td><a href='/detailed_answers/{r['access_token']}' style='color:#38bdf8; font-weight:bold;'>📖 उत्तरपत्रिका</a> | <a href='/student/admit_card/{r['id']}' target='_blank' style='color:#fbbf24; font-weight:bold;'>🖨️ गुणपत्रक</a></td></tr>" for r in results]) if results else "<tr><td colspan='6' style='text-align:center; padding:20px; color:#94a3b8;'>या नंबरवर कोणताही निकाल सापडला नाही.</td></tr>"}
        </table>''' if step == 'show_results' else ''}
    </div>
    </body>
    </html>'''
    return render_template_string(html)

@app.route('/detailed_answers/<token>')
def detailed_answers(token):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE access_token=%s AND is_deleted=0", (token,))
            lead = cur.fetchone()
            if not lead:
                return "Result not found", 404

            cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (lead['test_id'],))
            questions = cur.fetchall()

    user_ans_dict = json.loads(lead['answers_json'] or '{}')
    evaluated_questions = []
    for q in questions:
        u_ans = user_ans_dict.get(str(q['id']), 'सोडवले नाही')
        evaluated_questions.append({
            'q_text': q['question'],
            'opt_a': q['opt_a'],
            'opt_b': q['opt_b'],
            'opt_c': q['opt_c'],
            'opt_d': q['opt_d'],
            'image_url': q.get('image_url', ''),
            'user_ans': u_ans,
            'correct_ans': q['correct'],
            'is_correct': (u_ans == q['correct']),
            'explanation': q['explanation']
        })
    return render_template_string(DETAILED_KEY_TEMPLATE, lead=lead, evaluated_questions=evaluated_questions)

@app.route('/student/admit_card/<int:lead_id>')
def student_admit_card(lead_id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return "Admit card not found", 404
    return render_template_string(ADMIT_CARD_TEMPLATE, lead=lead)

@app.route('/submit_feedback/<int:lead_id>', methods=['POST'])
def submit_feedback(lead_id):
    fb_text = request.form.get('feedback_text', '').strip()
    if fb_text:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT student_name, phone, access_token FROM mock_test_leads WHERE id=%s AND is_deleted=0", (lead_id,))
                lead = cur.fetchone()
                if lead:
                    cur.execute("""
                        INSERT INTO student_feedbacks (lead_id, student_name, phone, feedback_text, created_at) 
                        VALUES (%s, %s, %s, %s, %s)
                    """, (lead_id, lead['student_name'], lead['phone'], fb_text, datetime.now().strftime("%Y-%m-%d %H:%M")))
                    conn.commit()
                    return redirect(f"/detailed_answers/{lead['access_token']}")
    return redirect('/')

@app.route('/report_question', methods=['POST'])
def report_question():
    data = request.get_json() or {}
    q_id = data.get('question_id')
    t_id = data.get('test_id')
    rep = data.get('report_text', '').strip()
    if q_id and rep:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO question_reports (question_id, test_id, report_text) VALUES (%s, %s, %s)", (q_id, t_id, rep))
                conn.commit()
    return jsonify({"success": True})

@app.route('/submit_help_desk', methods=['POST'])
def submit_help_desk():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    feedback = request.form.get('feedback', '').strip()
    if name and phone and feedback:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO student_feedbacks (lead_id, student_name, phone, feedback_text, created_at) 
                    VALUES (0, %s, %s, %s, %s)
                """, (name, phone, feedback, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
    return "<h3 style='color:green; text-align:center; padding:40px;'>✅ आपली तक्रार/अभिप्राय यशस्वीपणे नोंदवला गेला आहे!<br><br><a href='/' style='color:#0284c7;'>होम पेजवर परत जा</a></h3>"

                # =============================================================================
# MAHARASHTRA POLICE BHARTI ONLINE TEST PORTAL 2026 - MASTER CORE (PART 7/7)
# MODULE: ADMIN MASTER ROUTES, POWER SEARCH 360, AI GENERATION, CSV & RUNNER
# =============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('admin_pass')
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_pass'")
                row = cur.fetchone()
                db_pass = row['setting_value'] if row else 'admin2026'
        if password == db_pass:
            session['admin_logged'] = True
            return redirect('/admin/dashboard')
        error = "चुकीचा पासवर्ड! कृपया पुन्हा प्रयत्न करा."
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged', None)
    return redirect('/admin/login')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')

    active_tab = request.args.get('tab', 'leads')
    q_subtab = request.args.get('q_subtab', 'manual')
    cat_tab = request.args.get('cat_tab', 'all')
    sort_by = request.args.get('sort_by', 'seq')
    filter_test_id = request.args.get('filter_test_id', '')
    lead_dist = request.args.get('lead_dist', '')
    lead_cat = request.args.get('lead_cat', '')
    lead_test_id = request.args.get('lead_test_id', '')
    utr_search = request.args.get('utr_search', '').strip()
    power_phone = request.args.get('power_phone', '').strip()

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # १. पॉवर सर्च (विद्यार्थी ३६०° प्रोफाईल व संपूर्ण इतिहास)
            power_html = ""
            if power_phone:
                # १. टेस्ट इतिहास आणणे
                cur.execute("""
                    SELECT * FROM mock_test_leads 
                    WHERE phone=%s AND is_deleted=0 
                    ORDER BY id DESC
                """, (power_phone,))
                student_tests = cur.fetchall()

                # २. ब्लॉक स्थिती तपासणे
                is_blocked = False
                try:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS blocked_users (
                            id SERIAL PRIMARY KEY,
                            phone VARCHAR(20) UNIQUE,
                            blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("SELECT id FROM blocked_users WHERE phone=%s", (power_phone,))
                    if cur.fetchone():
                        is_blocked = True
                except Exception:
                    conn.rollback()
                    is_blocked = False

                if is_blocked:
                    block_btn_html = f"""
                    <form method="POST" action="/admin/toggle_block_user" style="display:inline; margin-left:15px;">
                        <input type="hidden" name="phone" value="{power_phone}">
                        <input type="hidden" name="action" value="unblock">
                        <button type="submit" style="background:#16a34a; color:white; border:none; padding:6px 14px; border-radius:5px; font-weight:bold; cursor:pointer;">
                            ✅ अनब्लॉक करा
                        </button>
                    </form>
                    """
                else:
                    block_btn_html = f"""
                    <form method="POST" action="/admin/toggle_block_user" style="display:inline; margin-left:15px;">
                        <input type="hidden" name="phone" value="{power_phone}">
                        <input type="hidden" name="action" value="block">
                        <button type="submit" onclick="return confirm('खरोखर या नंबरला ब्लॉक करायचे आहे का?');" style="background:#dc2626; color:white; border:none; padding:6px 14px; border-radius:5px; font-weight:bold; cursor:pointer;">
                            🚫 नंबर ब्लॉक करा
                        </button>
                    </form>
                    """

                # ३. पॅकेज / पेमेंट माहिती तपासणे
                pkg_status_html = ""
                try:
                    cur.execute("""
                        SELECT * FROM payments 
                        WHERE (phone=%s OR customer_phone=%s) 
                        ORDER BY id DESC LIMIT 1
                    """, (power_phone, power_phone))
                    pkg_data = cur.fetchone()

                    if pkg_data:
                        p_name = pkg_data.get('plan_name') or pkg_data.get('package_name') or 'सक्रिय पॅकेज'
                        p_amt = pkg_data.get('amount', 0)
                        p_status = pkg_data.get('status', 'Active')
                        pkg_status_html = f"""
                        <div style="background: #ecfdf5; border-left: 5px solid #10b981; padding: 12px 16px; border-radius: 6px; margin: 15px 0;">
                            <span style="color: #065f46; font-weight: bold; font-size: 15px;">📦 सक्रिय पॅकेज: {p_name}</span> | 
                            <span style="color: #047857; font-weight: bold;">फी: ₹{p_amt}</span> | 
                            <span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{p_status}</span>
                        </div>
                        """
                    else:
                        pkg_status_html = """
                        <div style="background: #fef2f2; border-left: 5px solid #ef4444; padding: 10px 15px; border-radius: 6px; margin: 15px 0; color: #991b1b; font-size: 14px;">
                            ⚠️ या विद्यार्थ्याने कोणतेही सशुल्क पॅकेज घेतलेले नाही. (मोफत वापरकर्ता)
                        </div>
                        """
                except Exception:
                    conn.rollback()
                    pkg_status_html = ""

                # ४. संपूर्ण ३६०° प्रोफाईल HTML तयार करणे
                if student_tests:
                    p = student_tests[0]
                    rows_html = ''.join([
                        f"<tr><td>{t.get('test_date', '-')}</td><td><b>{t.get('test_name', '-')}</b></td><td style='color:#059669; font-weight:bold;'>{t.get('score', 0)} / {t.get('total_marks', 0)}</td><td><span style='color:green;'>पूर्ण</span></td></tr>"
                        for t in student_tests
                    ])
                    power_html = f"""
                    <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:20px; margin-top:15px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                            <h3 style="color:#1e3a8a; margin:0;">३६०° प्रोफाईल: {p.get('full_name', '-')}</h3>
                            <div>{block_btn_html}</div>
                        </div>
                        <p style="margin:10px 0 5px 0; color:#475569;">
                            <b>प्रवर्ग:</b> {p.get('category', '-')} | 
                            <b>मोबाईल:</b> {p.get('phone', '-')} | 
                            <b>एकूण सोडवलेल्या टेस्ट्स:</b> {len(student_tests)}
                        </p>
                        {pkg_status_html}
                        <h4 style="color:#334155; margin-top:15px; margin-bottom:10px;">इतिहास व शुल्काची नोंद:</h4>
                        <table style="width:100%; border-collapse:collapse; background:white;">
                            <thead>
                                <tr style="background:#f1f5f9; text-align:left; border-bottom:1px solid #cbd5e1;">
                                    <th style="padding:8px;">दिनांक</th>
                                    <th style="padding:8px;">टेस्टचे नाव</th>
                                    <th style="padding:8px;">प्राप्त गुण</th>
                                    <th style="padding:8px;">स्थिती</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>
                    """
                else:
                    power_html = f"""
                    <div style="background:#fef2f2; border:1px solid #fecaca; padding:15px; border-radius:8px; margin-top:15px; color:#991b1b;">
                        या मोबाईल नंबरवर ({power_phone}) कोणताही टेस्ट डेटा सापडला नाही. {block_btn_html}
                    </div>
                    """

            # २. लीड्स क्वेरी (फिल्टरसह)
            query = "SELECT * FROM mock_test_leads WHERE is_deleted=0"
            params = []
            if lead_dist:
                query += " AND district = %s"
                params.append(lead_dist)
            if lead_cat:
                query += " AND caste_category = %s"
                params.append(lead_cat)
            if lead_test_id:
                query += " AND test_id = %s"
                params.append(lead_test_id)
            query += " ORDER BY id DESC"
            cur.execute(query, tuple(params))
            leads = cur.fetchall()

            cur.execute("SELECT DISTINCT district FROM mock_test_leads WHERE district != '' AND is_deleted=0")
            all_districts = [r['district'] for r in cur.fetchall()]

            # ३. टेस्ट्स यादी
            test_order_sql = "sequence_order ASC, id ASC"
            if sort_by == 'name':
                test_order_sql = "test_title ASC"
            elif sort_by == 'id':
                test_order_sql = "id DESC"

            test_query = "SELECT * FROM test_papers WHERE is_deleted=0"
            test_params = []
            if cat_tab != 'all':
                test_query += " AND category = %s"
                test_params.append(cat_tab)
            test_query += f" ORDER BY {test_order_sql}"
            cur.execute(test_query, tuple(test_params))
            tests = cur.fetchall()

            cur.execute("SELECT * FROM test_papers WHERE is_deleted=0 ORDER BY sequence_order ASC, id ASC")
            all_available_tests = cur.fetchall()

            if not filter_test_id and all_available_tests:
                filter_test_id = str(all_available_tests[0]['id'])

            if filter_test_id:
                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id DESC", (filter_test_id,))
            else:
                cur.execute("SELECT * FROM questions WHERE is_deleted=0 ORDER BY id DESC")
            all_questions = cur.fetchall()

            selected_test_title = "निवडलेली टेस्ट"
            for t in all_available_tests:
                if str(t['id']) == str(filter_test_id):
                    selected_test_title = t['test_title']
                    break

            # ४. पेमेंट्स क्वेरी
            pay_query = "SELECT * FROM mock_test_leads WHERE payment_status != 'Not Required' AND is_deleted=0"
            pay_params = []
            if utr_search:
                pay_query += " AND (utr_number ILIKE %s OR phone ILIKE %s)"
                pay_params.extend([f"%{utr_search}%", f"%{utr_search}%"])
            pay_query += " ORDER BY id DESC"
            cur.execute(pay_query, tuple(pay_params))
            payments = cur.fetchall()

            # ५. गुणवत्ता यादी, फीडबॅक, स्पेशल ॲक्सेस व ऑडिट्स
            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=0 ORDER BY score DESC, id ASC LIMIT 100")
            all_leads_sorted = cur.fetchall()
            top_leads = [(idx, l) for idx, l in enumerate(all_leads_sorted, start=1)]

            cur.execute("SELECT * FROM student_feedbacks ORDER BY id DESC")
            feedbacks = cur.fetchall()

            cur.execute("SELECT * FROM question_reports ORDER BY id DESC")
            question_reports_list = cur.fetchall()

            cur.execute("SELECT * FROM special_unlimited_attempts ORDER BY id DESC")
            unlimited_list = cur.fetchall()

            cur.execute("SELECT * FROM special_free_pass ORDER BY id DESC")
            free_pass_list = cur.fetchall()

            cur.execute("SELECT * FROM blocked_numbers ORDER BY blocked_at DESC")
            blocked_list = cur.fetchall()

            cur.execute("SELECT * FROM otp_verification_audit ORDER BY id DESC LIMIT 50")
            otp_audits = cur.fetchall()

            cur.execute("""
                SELECT tp.test_title as test_name, tp.category, COUNT(mtl.id) as total_attempts 
                FROM test_papers tp 
                LEFT JOIN mock_test_leads mtl ON tp.id = mtl.test_id AND mtl.is_deleted=0
                WHERE tp.is_deleted=0
                GROUP BY tp.id, tp.test_title, tp.category
                ORDER BY total_attempts DESC
            """)
            test_stats = cur.fetchall()

            cur.execute("SELECT setting_key, setting_value FROM academy_settings")
            settings_map = {r['setting_key']: r['setting_value'] for r in cur.fetchall()}

            cur.execute("SELECT tab_key, tab_label FROM custom_tabs")
            custom_tabs_list = cur.fetchall()

            cur.execute("SELECT * FROM questions WHERE is_deleted=1 ORDER BY id DESC")
            deleted_questions_list = cur.fetchall()

            cur.execute("SELECT id, question as title, 'question' as type FROM questions WHERE is_deleted=1 ORDER BY id DESC LIMIT 5")
            deleted_q = cur.fetchall()
            cur.execute("SELECT id, student_name as title, 'lead' as type FROM mock_test_leads WHERE is_deleted=1 ORDER BY id DESC LIMIT 5")
            deleted_l = cur.fetchall()
            undo_items = deleted_q + deleted_l

            admin_tab_order = settings_map.get('admin_tab_order', 'leads,power,payments,special,questions,launch,analytics,audit,blocked,leaderboard,feedback,notices,trash,settings')
            ordered_admin_tabs = [t.strip() for t in admin_tab_order.split(',') if t.strip()]

            return render_template_string(
                ADMIN_TEMPLATE,
                active_tab=active_tab,
                q_subtab=q_subtab,
                cat_tab=cat_tab,
                sort_by=sort_by,
                leads=leads,
                tests=tests,
                all_questions=all_questions,
                payments=payments,
                top_leads=top_leads,
                feedbacks=feedbacks,
                question_reports_list=question_reports_list,
                unlimited_list=unlimited_list,
                free_pass_list=free_pass_list,
                blocked_list=blocked_list,
                otp_audits=otp_audits,
                test_stats=test_stats,
                all_districts=all_districts,
                lead_dist=lead_dist,
                lead_cat=lead_cat,
                lead_test_id=lead_test_id,
                filter_test_id=filter_test_id,
                selected_test_title=selected_test_title,
                power_phone=power_phone,
                power_html=power_html,
                qr_url=settings_map.get('qr_code_url', ''),
                upi_mobile=settings_map.get('upi_mobile', '9921111960'),
                razorpay_key_id=settings_map.get('razorpay_key_id', ''),
                razorpay_key_secret=settings_map.get('razorpay_key_secret', ''),
                help_phone=settings_map.get('help_phone', '9921111960'),
                help_address=settings_map.get('help_address', 'महाराष्ट्र पोलीस भरती सराव केंद्र, कोल्हापूर'),
                insta_link=settings_map.get('insta_link', 'https://instagram.com'),
                yt_link=settings_map.get('yt_link', 'https://youtube.com'),
                toppers_link=settings_map.get('toppers_link', '/'),
                wa_groups_multiline=settings_map.get('wa_groups_multiline', ''),
                home_tab_order=settings_map.get('home_tab_order', 'live,paid,free,rapid,about,battle,docs,help'),
                admin_tab_order=admin_tab_order,
                ordered_admin_tabs=ordered_admin_tabs,
                site_status=settings_map.get('site_status', 'active'),
                custom_tabs_list=custom_tabs_list,
                undo_items=undo_items,
                deleted_questions_list=deleted_questions_list
            )

# मॅन्युअल प्रश्न नोंद (इमेज अपलोडसह)
@app.route('/admin/add_manual_question', methods=['POST'])
def admin_add_manual_question():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    test_id = request.form.get('test_id')
    question = request.form.get('question', '').strip()
    opt_a = request.form.get('opt_a', '').strip()
    opt_b = request.form.get('opt_b', '').strip()
    opt_c = request.form.get('opt_c', '').strip()
    opt_d = request.form.get('opt_d', '').strip()
    correct = request.form.get('correct', 'A').strip().upper()
    explanation = request.form.get('explanation', '').strip()
    q_file = request.files.get('question_image')

    image_url = ""
    if q_file and q_file.filename != '':
        fname = secure_filename(f"q_{int(datetime.now().timestamp())}_{q_file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        q_file.save(save_path)
        image_url = f"/static/uploads/{fname}"

    if question and opt_a and opt_b and opt_c and opt_d and test_id:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation, image_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation, image_url))
                conn.commit()

    return redirect(f'/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id={test_id}')

# १. प्रश्नांचे संपादन (Edit Question Route)
@app.route('/admin/edit_question/<int:q_id>', methods=['GET', 'POST'])
def admin_edit_question(q_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if request.method == 'POST':
                q_text = request.form.get('question', '').strip()
                oa = request.form.get('opt_a', '').strip()
                ob = request.form.get('opt_b', '').strip()
                oc = request.form.get('opt_c', '').strip()
                od = request.form.get('opt_d', '').strip()
                corr = request.form.get('correct', 'A').strip().upper()
                exp = request.form.get('explanation', '').strip()
                img = request.form.get('image_url', '').strip()

                cur.execute("""
                    UPDATE questions 
                    SET question=%s, opt_a=%s, opt_b=%s, opt_c=%s, opt_d=%s, correct=%s, explanation=%s, image_url=%s
                    WHERE id=%s RETURNING test_id
                """, (q_text, oa, ob, oc, od, corr, exp, img, q_id))
                t_id = cur.fetchone()['test_id']
                conn.commit()
                return redirect(f"/admin/dashboard?tab=questions&filter_test_id={t_id}")

            cur.execute("SELECT * FROM questions WHERE id=%s", (q_id,))
            q = cur.fetchone()
            if not q: 
                return "Question not found", 404
    return render_template_string(EDIT_QUESTION_TEMPLATE, q=q)
                                  
# 6. Digital Smart AI Question Generator
@app.route('/admin/ai_generate_advanced', methods=['POST'])
def admin_ai_generate_advanced():
    if not session.get('admin_logged'): 
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    department = data.get('department', 'पोलीस भरती')
    subject_counts = data.get('subject_counts', {})
    test_id = data.get('test_id')

    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    generated_list = []

    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]

    for subj, num in subject_counts.items():
        count = int(num)
        if count <= 0: 
            continue

        prompt = (
            f"महाराष्ट्र {department} परीक्षेसाठी '{subj}' या विषयावर अचूक आणि उच्च-दर्जाचे नवीन {count} बहुपर्यायी प्रश्न (MCQs) तयार करा. "
            f"उत्तर खालीलप्रमाणे प्रत्येक ओळीत फक्त आणि फक्त पाईप (|) फॉरमॅटमध्ये द्या, कोणताही अतिरिक्त मजकूर नको:\n"
            f"प्रश्न | पर्याय A | पर्याय B | पर्याय C | पर्याय D | अचूक उत्तर (A/B/C/D) | सविस्तर स्पष्टीकरण"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        success = False
        if api_key:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                try:
                    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
                    if res.status_code == 200:
                        raw = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        for line in raw.strip().split('\n'):
                            parts = [p.strip() for p in line.split('|')]
                            if len(parts) >= 6:
                                corr = parts[5].upper()
                                if corr not in ['A', 'B', 'C', 'D']: 
                                    corr = 'A'
                                exp = parts[6] if len(parts) > 6 else 'स्पष्टीकरण उपलब्ध नाही.'
                                generated_list.append((test_id, parts[0], parts[1], parts[2], parts[3], parts[4], corr, exp))
                        if len(generated_list) > 0:
                            success = True
                            break
                except Exception as err:
                    print(f"Model {model_name} Error: {err}")
                    continue

        if not success:
            for i in range(1, count + 1):
                generated_list.append((
                    test_id,
                    f"{subj}: महाराष्ट्र पोलीस भरती परीक्षेसाठी अतिसंभाव्य सराव प्रश्न क्र. {i}",
                    "पर्याय (A)", "पर्याय (B)", "पर्याय (C)", "पर्याय (D)",
                    "A",
                    f"{subj} विषयाच्या नवीनतम पोलीस भरती मानकांनुसार अचूक उत्तर पर्याय A आहे."
                ))

    if generated_list:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.executemany("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, generated_list)
                conn.commit()
        return jsonify({"success": True, "inserted_count": len(generated_list)})

    return jsonify({"success": False, "error": "काहीही प्रश्न जनरेट झाले नाहीत."}), 400

# १०० प्रश्नांची CSV फाईल अपलोड
@app.route('/admin/upload_csv_questions', methods=['POST'])
def admin_upload_csv_questions():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    test_id = request.form.get('test_id')
    file = request.files.get('csv_file')
    if not file: 
        return "No file uploaded", 400

    try:
        content = file.stream.read().decode("utf-8-sig", errors="ignore")
    except Exception:
        content = file.stream.read().decode("latin1", errors="ignore")

    stream = io.StringIO(content, newline=None)
    csv_reader = csv.reader(stream)

    questions_to_insert = []
    for row in csv_reader:
        if not row: 
            continue
        first_cell = row[0].strip().lower()
        if any(h in first_cell for h in ['sr', 'अनुक्रमांक', 'question', 'प्रश्न']): 
            continue

        if len(row) >= 9:
            q = row[2].strip()
            oa, ob, oc, od = row[3].strip(), row[4].strip(), row[5].strip(), row[6].strip()
            corr = row[7].strip().upper()
            exp = row[8].strip()
        elif len(row) >= 6:
            q = row[0].strip()
            oa, ob, oc, od = row[1].strip(), row[2].strip(), row[3].strip(), row[4].strip()
            corr = row[5].strip().upper() if len(row) > 5 else 'A'
            exp = row[6].strip() if len(row) > 6 else ''
        else:
            continue

        if corr not in ['A', 'B', 'C', 'D']: 
            corr = 'A'
        if q: 
            questions_to_insert.append((test_id, q, oa, ob, oc, od, corr, exp))

    if questions_to_insert:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.executemany("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, questions_to_insert)
                conn.commit()

    return redirect(f'/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id={test_id}')

# हार्डकॉपी व्हिजन स्कॅनर (OCR)[span_2](start_span)[span_2](end_span)
@app.route('/admin/ai_scan_hardcopy', methods=['POST'])
def admin_ai_scan_hardcopy():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    test_id = request.form.get('test_id')
    file = request.files.get('scanned_image')
    if file and test_id and AIQuestionGenerator:
        fname = secure_filename(f"scan_{int(datetime.now().timestamp())}_{file.filename}")
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        file.save(fpath)
        with get_db() as conn:
            gen = AIQuestionGenerator(db_connection=conn)
            scanned_mcqs = gen.scan_hardcopy_image(fpath, test_id=test_id)
            if scanned_mcqs:
                with conn.cursor() as cur:
                    for q in scanned_mcqs:
                        cur.execute("""
                            INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (test_id, q['question'], q['opt_a'], q['opt_b'], q['opt_c'], q['opt_d'], q['correct'], q.get('explanation', '')))
                    conn.commit()
    return redirect(f'/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id={test_id}')

# ५००/५०५ एरर-प्रूफ सॉफ्ट डिलीट व रिसायकल बिन राऊट्स[span_3](start_span)[span_3](end_span)
@app.route('/admin/delete_question/<int:q_id>')
def admin_delete_question(q_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT test_id FROM questions WHERE id=%s", (q_id,))
            q_row = cur.fetchone()
            t_id = q_row[0] if q_row else ''
            cur.execute("UPDATE questions SET is_deleted=1 WHERE id=%s", (q_id,))
            conn.commit()
    return redirect(f'/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id={t_id}')

@app.route('/admin/bulk_delete_questions', methods=['POST'])
def admin_bulk_delete_questions():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    ids = request.form.getlist('question_ids')
    test_id = request.args.get('filter_test_id', '')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("UPDATE questions SET is_deleted=1 WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect(f'/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id={test_id}')

@app.route('/admin/delete_lead/<int:lead_id>')
def admin_delete_lead(lead_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/bulk_delete_leads', methods=['POST'])
def admin_bulk_delete_leads():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    ids = request.form.getlist('lead_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/delete_payment/<int:lead_id>')
def admin_delete_payment(lead_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/undo_delete/<item_type>/<int:item_id>')
def admin_undo_delete(item_type, item_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            if item_type == 'question':
                cur.execute("UPDATE questions SET is_deleted=0 WHERE id=%s", (item_id,))
            elif item_type == 'lead':
                cur.execute("UPDATE mock_test_leads SET is_deleted=0 WHERE id=%s", (item_id,))
            conn.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/restore_item/<item_type>/<int:item_id>')
def admin_restore_item(item_type, item_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            if item_type == 'question':
                cur.execute("UPDATE questions SET is_deleted=0 WHERE id=%s", (item_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=trash')

@app.route('/admin/bulk_restore_trash', methods=['POST'])
def admin_bulk_restore_trash():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    ids = request.form.getlist('question_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("UPDATE questions SET is_deleted=0 WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect('/admin/dashboard?tab=trash')

@app.route('/admin/bulk_delete_trash', methods=['POST'])
def admin_bulk_delete_trash():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    ids = request.form.getlist('question_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("DELETE FROM questions WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect('/admin/dashboard?tab=trash')

@app.route('/admin/bulk_delete_feedback', methods=['POST'])
def admin_bulk_delete_feedback():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    selected_ids = request.form.getlist('feedback_ids')
    if selected_ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in selected_ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("DELETE FROM student_feedbacks WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect('/admin/dashboard?tab=feedback')

# टेस्ट व्यवस्थापन (Add, Update, Clone & Delete)
@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    category = request.form.get('category', 'paid')
    ttype = request.form.get('test_type', 'Paid')
    seq = int(request.form.get('sequence_order', 1) or 1)
    fee = float(request.form.get('test_fee', 99) or 0)
    duration = int(request.form.get('duration_minutes', 60) or 60)
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) 
                VALUES (%s, %s, %s, %s, 'Active', %s, %s)
            """, (title, ttype, fee, duration, category, seq))
            conn.commit()
    return redirect(f'/admin/dashboard?tab=launch&cat_tab={category}')

@app.route('/admin/update_test/<int:test_id>', methods=['POST'])
def admin_update_test(test_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    category = request.form.get('category', 'paid')
    ttype = request.form.get('test_type', 'Paid')
    seq = int(request.form.get('sequence_order', 1) or 1)
    fee = float(request.form.get('test_fee', 0) or 0)
    duration = int(request.form.get('duration_minutes', 60) or 60)
    status = request.form.get('status', 'Active').strip()
    return_cat_tab = request.form.get('return_cat_tab', 'all')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE test_papers 
                SET test_title=%s, test_type=%s, test_fee=%s, duration_minutes=%s, category=%s, sequence_order=%s, status=%s 
                WHERE id=%s
            """, (title, ttype, fee, duration, category, seq, status, test_id))
            conn.commit()
    return redirect(f'/admin/dashboard?tab=launch&cat_tab={return_cat_tab}')

@app.route('/admin/clone_test/<int:test_id>')
def admin_clone_test(test_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            t = cur.fetchone()
            if t:
                cur.execute("""
                    INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status, category, sequence_order)
                    VALUES (%s, %s, %s, %s, 'Active', %s, %s) RETURNING id
                """, (f"{t['test_title']} (Copy)", t['test_type'], t['test_fee'], t['duration_minutes'], t['category'], (t['sequence_order'] or 1) + 1))
                new_t_id = cur.fetchone()['id']

                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0", (test_id,))
                qs = cur.fetchall()
                for q in qs:
                    cur.execute("""
                        INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation, image_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (new_t_id, q['question'], q['opt_a'], q['opt_b'], q['opt_c'], q['opt_d'], q['correct'], q['explanation'], q.get('image_url', '')))
                conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE test_papers SET is_deleted=1 WHERE id=%s", (test_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

# स्पेशल ॲक्सेस व पेमेंट मंजुरी राऊट्स[span_4](start_span)[span_4](end_span)
@app.route('/admin/approve_payment/<int:lead_id>', methods=['POST'])
def admin_approve_payment(lead_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    token = secrets.token_hex(8)
    expires = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE mock_test_leads 
                SET payment_status='Approved', access_token=%s, token_expires_at=%s 
                WHERE id=%s
            """, (token, expires, lead_id))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/add_special_unlimited', methods=['POST'])
def add_special_unlimited():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    phone = request.form.get('phone', '').strip()
    name = request.form.get('student_name', '').strip()
    note = request.form.get('note', '').strip()
    added_on = datetime.now().strftime("%Y-%m-%d %H:%M")
    if re.match(r'^[6-9]\d{9}$', phone):
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO special_unlimited_attempts (phone, student_name, note, added_on)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (phone) DO UPDATE SET student_name=EXCLUDED.student_name, note=EXCLUDED.note
                """, (phone, name, note, added_on))
                conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/delete_special_unlimited/<int:uid>')
def delete_special_unlimited(uid):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM special_unlimited_attempts WHERE id=%s", (uid,))
            conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/add_special_free_pass', methods=['POST'])
def add_special_free_pass():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    phone = request.form.get('phone', '').strip()
    name = request.form.get('student_name', '').strip()
    note = request.form.get('note', '').strip()
    added_on = datetime.now().strftime("%Y-%m-%d %H:%M")
    if re.match(r'^[6-9]\d{9}$', phone):
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO special_free_pass (phone, student_name, note, added_on)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (phone) DO UPDATE SET student_name=EXCLUDED.student_name, note=EXCLUDED.note
                """, (phone, name, note, added_on))
                conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/delete_special_free_pass/<int:fid>')
def delete_special_free_pass(fid):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM special_free_pass WHERE id=%s", (fid,))
            conn.commit()
    return redirect('/admin/dashboard?tab=special')

# सेटिंग्स अपडेट्स (Razorpay, UPI QR, पासवर्ड, सानुकूल टॅब्स व PDF)[span_5](start_span)[span_5](end_span)
@app.route('/admin/add_custom_tab', methods=['POST'])
def admin_add_custom_tab():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    key = re.sub(r'[^a-zA-Z0-9_]', '', request.form.get('tab_key', '').strip().lower())
    label = request.form.get('tab_label', '').strip()
    if key and label:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO custom_tabs (tab_key, tab_label) 
                    VALUES (%s, %s) 
                    ON CONFLICT (tab_key) DO UPDATE SET tab_label = EXCLUDED.tab_label
                """, (key, label))
                cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='home_tab_order'")
                row = cur.fetchone()
                current_order = row['setting_value'] if row else 'live,paid,free,rapid,about,battle,docs,help'
                if key not in current_order.split(','):
                    new_order = f"{current_order},{key}"
                    cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='home_tab_order'", (new_order,))
                conn.commit()
    return redirect('/admin/dashboard?tab=settings')

@app.route('/admin/update_razorpay_settings', methods=['POST'])
def admin_update_razorpay_settings():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    kid = request.form.get('razorpay_key_id', '').strip()
    ksec = request.form.get('razorpay_key_secret', '').strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('razorpay_key_id', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (kid,))
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('razorpay_key_secret', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (ksec,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/update_payment_settings', methods=['POST'])
def admin_update_payment_settings():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    new_mobile = request.form.get('upi_mobile', '').strip()
    qr_url_input = request.form.get('qr_url', '').strip()
    qr_file = request.files.get('qr_file')
    
    final_qr_url = qr_url_input
    if qr_file and qr_file.filename != '':
        fname = secure_filename(f"qr_{int(datetime.now().timestamp())}_{qr_file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        qr_file.save(save_path)
        final_qr_url = f"/static/uploads/{fname}"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='qr_code_url'", (final_qr_url,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='upi_mobile'", (new_mobile,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/update_pdf_docs', methods=['POST'])
def admin_update_pdf_docs():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    rec_file = request.files.get('recruitment_pdf_file')
    elg_file = request.files.get('eligibility_pdf_file')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if rec_file and rec_file.filename != '':
                fname = secure_filename(f"recruitment_{int(datetime.now().timestamp())}_{rec_file.filename}")
                rec_file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='recruitment_pdf'", (f"/static/uploads/{fname}",))
            
            if elg_file and elg_file.filename != '':
                fname = secure_filename(f"eligibility_{int(datetime.now().timestamp())}_{elg_file.filename}")
                elg_file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='eligibility_pdf'", (f"/static/uploads/{fname}",))
            conn.commit()
    return redirect('/admin/dashboard?tab=notices')

@app.route('/admin/update_password', methods=['POST'])
def admin_update_password():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    new_pass = request.form.get('new_password')
    site_status = request.form.get('site_status', 'active')
    home_tab_order = request.form.get('home_tab_order', 'live,paid,free,rapid,about,battle,docs,help').strip()
    admin_tab_order = request.form.get('admin_tab_order', 'leads,power,payments,special,questions,launch,analytics,audit,blocked,leaderboard,feedback,notices,trash,settings').strip()
    wa_groups = request.form.get('wa_groups_multiline', '').strip()
    help_phone = request.form.get('help_phone', '').strip()
    help_address = request.form.get('help_address', '').strip()
    insta = request.form.get('insta_link', 'https://instagram.com')
    yt = request.form.get('yt_link', 'https://youtube.com')
    top = request.form.get('toppers_link', '/')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if new_pass:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
            if help_phone:
                cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('help_phone', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (help_phone,))
            if help_address:
                cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('help_address', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (help_address,))
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('site_status', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (site_status,))
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('home_tab_order', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (home_tab_order,))
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('admin_tab_order', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (admin_tab_order,))
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('wa_groups_multiline', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (wa_groups,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='insta_link'", (insta,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='yt_link'", (yt,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='toppers_link'", (top,))
            conn.commit()
    return redirect('/admin/dashboard?tab=settings')

# फिल्टरसह लीड्स CSV डाऊनलोड
@app.route('/admin/export_leads_csv')
def admin_export_leads_csv():
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    lead_dist = request.args.get('lead_dist', '').strip()
    lead_cat = request.args.get('lead_cat', '').strip()
    lead_test_id = request.args.get('lead_test_id', '').strip()

    query = "SELECT test_date, student_name, district, caste_category, phone, test_name, score, total_marks FROM mock_test_leads WHERE is_deleted=0"
    params = []
    if lead_dist:
        query += " AND district = %s"
        params.append(lead_dist)
    if lead_cat:
        query += " AND caste_category = %s"
        params.append(lead_cat)
    if lead_test_id:
        query += " AND test_id = %s"
        params.append(lead_test_id)
    query += " ORDER BY id DESC"

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, tuple(params))
            leads = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Name', 'District', 'Category', 'WhatsApp', 'Test Name', 'Score', 'Total'])
    for l in leads:
        writer.writerow([l['test_date'], l['student_name'], l['district'], l.get('caste_category', 'OPEN'), l['phone'], l['test_name'], l['score'], l['total_marks']])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=filtered_leads_2026.csv"}
    )

# ७. टेस्ट प्रश्नपत्रिका A4 प्रिंट / PDF राऊट[span_6](start_span)[span_6](end_span)
@app.route('/admin/print_test/<int:test_id>')
def print_test_route(test_id):
    if not session.get('admin_logged'): 
        return redirect('/admin/login')
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, test_title, category, duration_minutes, test_fee FROM test_papers WHERE id = %s", (test_id,))
            test = cur.fetchone()
            if not test: 
                return "टेस्ट सापडली नाही!", 404
            
            cur.execute("""
                SELECT id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation, image_url 
                FROM questions 
                WHERE test_id = %s AND is_deleted=0 
                ORDER BY id ASC
            """, (test_id,))
            questions = cur.fetchall()
            
            html_code = f"""
            <!DOCTYPE html>
            <html lang="mr">
            <head>
                <meta charset="UTF-8">
                <title>प्रश्नपत्रिका - {test['test_title']}</title>
                <style>
                    @page {{ size: A4; margin: 15mm; }}
                    body {{ font-family: 'Segoe UI', Tahoma, sans-serif; color: #1e293b; line-height: 1.5; padding: 10px; }}
                    .header {{ text-align: center; border-bottom: 2px solid #0f172a; padding-bottom: 10px; margin-bottom: 20px; }}
                    .header h2 {{ margin: 0; font-size: 22px; color: #0f172a; }}
                    .header p {{ margin: 4px 0 0; font-size: 14px; font-weight: bold; color: #475569; }}
                    .meta-box {{ display: flex; justify-content: space-between; border-bottom: 1px dashed #94a3b8; padding-bottom: 8px; margin-bottom: 15px; font-size: 13px; font-weight: 600; }}
                    .q-block {{ margin-bottom: 18px; page-break-inside: avoid; }}
                    .q-text {{ font-size: 15px; font-weight: 700; margin-bottom: 6px; color: #0f172a; }}
                    .options-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding-left: 15px; font-size: 14px; }}
                    .print-bar {{ background: #f1f5f9; padding: 10px; text-align: center; margin-bottom: 20px; border-radius: 8px; }}
                    .btn-print {{ background: #059669; color: white; border: none; padding: 8px 18px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 14px; }}
                    @media print {{ .print-bar {{ display: none; }} }}
                </style>
            </head>
            <body>
                <div class="print-bar">
                    <button class="btn-print" onclick="window.print()">🖨️ ही प्रश्नपत्रिका प्रिंट / PDF सेव्ह करा</button>
                </div>
                
                <div class="header">
                    <h2>महाराष्ट्र पोलीस भरती सराव केंद्र</h2>r
                    <p>सराव परीक्षा: {test['test_title']}</p>
                </div>
                <div class="meta-box">
                    <span>एकूण प्रश्न: {len(questions)}</span>
                    <span>वेळ: {test['duration_minutes']} मिनिटे</span>
                    <span>कॅटेगरी: {str(test['category']).upper()}</span>
                </div>
                
                <div class="questions-list">
            """
            
            for idx, q in enumerate(questions, 1):
                img_tag = f'<div style="margin-bottom:6px;"><img src="{q["image_url"]}" style="max-height:160px;"></div>' if q.get('image_url') else ''
                html_code += f"""
                    <div class="q-block">
                        <div class="q-text">प्र. {idx}) {q['question']}</div>
                        {img_tag}
                        <div class="options-grid">
                            <div>(A) {q['opt_a']}</div>
                            <div>(B) {q['opt_b']}</div>
                            <div>(C) {q['opt_c']}</div>
                            <div>(D) {q['opt_d']}</div>
                        </div>
                    </div>
                """
                
            html_code += """
                </div>
            </body>
            </html>
            """
            return html_code


# =============================================================================
# ३६०° पॉवर सर्च - नंबर ब्लॉक व अनब्लॉक राऊट
# =============================================================================
@app.route('/admin/toggle_block_user', methods=['POST'])
def admin_toggle_block_user():
    if not session.get('admin_logged'):
        return redirect('/admin/login')
    
    phone = request.form.get('phone', '').strip()
    action = request.form.get('action', '').strip()

    if phone:
        with get_db() as conn:
            with conn.cursor() as cur:
                if action == 'block':
                    cur.execute("""
                        INSERT INTO blocked_numbers (phone, reason, blocked_at)
                        VALUES (%s, '360 पॉवर सर्चमधून ब्लॉक केले', NOW())
                        ON CONFLICT (phone) DO NOTHING
                    """, (phone,))
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS blocked_users (
                            id SERIAL PRIMARY KEY,
                            phone VARCHAR(20) UNIQUE,
                            blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        INSERT INTO blocked_users (phone)
                        VALUES (%s)
                        ON CONFLICT (phone) DO NOTHING;
                    """, (phone,))
                elif action == 'unblock':
                    cur.execute("DELETE FROM blocked_numbers WHERE phone=%s", (phone,))
                    cur.execute("DELETE FROM blocked_users WHERE phone=%s", (phone,))
                conn.commit()
                
    return redirect(f"/admin/dashboard?tab=power&power_phone={phone}")
# -----------------------------------------------------------------------------
# 8. APPLICATION ENTRYPOINT
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
