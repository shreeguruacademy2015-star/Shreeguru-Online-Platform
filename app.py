import csv
import io
import json
import os
import re
import secrets
import urllib.parse
from datetime import date, datetime, timedelta
from contextlib import contextmanager
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

# --- SURAKSHIT RAZORPAY IMPORT (RENDER CRASH-PROOF) ---
try:
    import razorpay
except ImportError:
    razorpay = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "shreeguru_master_test_platform_2026_ultimate_safe")

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- NEON POSTGRESQL POOLING ---
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
    finally:
        if conn and db_pool:
            db_pool.putconn(conn)
        elif conn:
            conn.close()

def get_razorpay_client():
    if not razorpay:
        return None, ""
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT setting_key, setting_value FROM academy_settings WHERE setting_key IN ('razorpay_key_id', 'razorpay_key_secret')")
                rows = cur.fetchall()
                for r in rows:
                    if r['setting_key'] == 'razorpay_key_id' and r['setting_value']:
                        key_id = r['setting_value']
                    elif r['setting_key'] == 'razorpay_key_secret' and r['setting_value']:
                        key_secret = r['setting_value']
    except Exception:
        pass
    
    if key_id and key_secret:
        try:
            return razorpay.Client(auth=(key_id, key_secret)), key_id
        except Exception:
            return None, key_id
    return None, key_id

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
                    publish_at TIMESTAMP DEFAULT NULL
                )''')

                # Column safety check
                try:
                    cur.execute("ALTER TABLE test_papers ADD COLUMN category TEXT DEFAULT 'free';")
                    conn.commit()
                except Exception:
                    conn.rollback()

                try:
                    cur.execute("ALTER TABLE test_papers ADD COLUMN publish_at TIMESTAMP DEFAULT NULL;")
                    conn.commit()
                except Exception:
                    conn.rollback()

                cur.execute('''CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    test_id INTEGER DEFAULT 1,
                    question TEXT NOT NULL,
                    opt_a TEXT NOT NULL,
                    opt_b TEXT NOT NULL,
                    opt_c TEXT NOT NULL,
                    opt_d TEXT NOT NULL,
                    correct TEXT NOT NULL,
                    explanation TEXT DEFAULT ''
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS mock_test_leads (
                    id SERIAL PRIMARY KEY,
                    test_id INTEGER DEFAULT 1,
                    test_date TEXT NOT NULL,
                    student_name TEXT NOT NULL,
                    district TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    whatsapp_verified INTEGER DEFAULT 0,
                    payment_status TEXT DEFAULT 'Pending',
                    utr_number TEXT DEFAULT '',
                    score REAL DEFAULT 0,
                    total_marks INTEGER DEFAULT 0,
                    test_name TEXT NOT NULL,
                    answers_json TEXT DEFAULT '',
                    access_token TEXT DEFAULT '',
                    token_expires_at TEXT DEFAULT '',
                    razorpay_order_id TEXT DEFAULT '',
                    razorpay_payment_id TEXT DEFAULT ''
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS shared_free_passes (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    unlocked_until_test INTEGER DEFAULT 5,
                    created_at TEXT NOT NULL
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS referral_clicks (
                    id SERIAL PRIMARY KEY,
                    referrer_phone TEXT NOT NULL,
                    visitor_ip TEXT NOT NULL,
                    clicked_at TEXT NOT NULL
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

                cur.execute('''CREATE TABLE IF NOT EXISTS academy_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )''')

                defaults = [
                    ('qr_code_url', 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=ShreeguruUPIpayment'),
                    ('upi_mobile', '9921111960'),
                    ('admin_pass', 'shreeguru2026'),
                    ('admin_phone', '9921111960'),
                    ('insta_link', ''),
                    ('yt_link', ''),
                    ('toppers_link', ''),
                    ('wa_group_link', ''),
                    ('wa_group_link_2', ''),
                    ('tab_order', 'all,live,paid,free,rapid,battle,docs'),
                    ('recruitment_pdf', ''),
                    ('eligibility_pdf', ''),
                    ('razorpay_key_id', ''),
                    ('razorpay_key_secret', '')
                ]
                for k, v in defaults:
                    cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO NOTHING", (k, v))

                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_test_score ON mock_test_leads(test_id, score);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON mock_test_leads(phone);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_ref_clicks_phone ON referral_clicks(referrer_phone);")

                cur.execute('SELECT COUNT(*) as count FROM test_papers')
                if cur.fetchone()['count'] == 0:
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active', 'free')")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category) VALUES (2, '🔴 मिशन खाकी रविवार थेट महासंग्राम #१', 'Free', 0, 60, 'Active', 'live')")

                conn.commit()
    except Exception as e:
        print(f"Init DB Error: {e}")

init_master_db()

# ----------------- TEMPLATES -----------------

HOME_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>महाराष्ट्र पोलीस भरती २०२६ - मिशन खाकी महा-पोर्टल</title>
    <link href="https://fonts.googleapis.com/css2?family=Baloo+Bhaina+2:wght@500;700;800&family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', 'Baloo Bhaina 2', sans-serif; transition: all 0.2s ease; }
        body { margin: 0; background: #0f172a; color: #f8fafc; padding: 12px; }
        .top-bar { max-width: 950px; margin: 0 auto 15px; display: flex; justify-content: space-between; align-items: center; background: #1e293b; padding: 12px 18px; border-radius: 12px; border: 1px solid #334155; }
        .badge-live { background: #ef4444; color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .box { max-width: 950px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 25px 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); border-top: 5px solid #10b981; }
        .hero-banner { text-align: center; margin-bottom: 22px; }
        .hero-banner h1 { margin: 0 0 8px; color: #34d399; font-size: 28px; font-weight: 800; font-family: 'Baloo Bhaina 2', cursive; }
        .quote-box { background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(6,95,70,0.2)); border-left: 4px solid #10b981; padding: 12px 16px; border-radius: 8px; font-size: 14.5px; color: #a7f3d0; font-weight: 600; margin-bottom: 20px; text-align: center; }
        .tabs-wrapper { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-bottom: 25px; }
        .tab-btn { background: #334155; color: #cbd5e1; border: 1.5px solid #475569; padding: 10px 16px; border-radius: 30px; font-size: 13px; font-weight: 700; cursor: pointer; }
        .tab-btn:hover, .tab-btn.active { background: #10b981; color: #064e3b; border-color: #34d399; }
        .test-grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
        .test-card { background: #0f172a; border: 1.5px solid #334155; border-radius: 12px; padding: 18px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
        .test-title { margin: 0 0 6px; color: #f1f5f9; font-size: 17px; font-weight: 700; }
        .badge-free { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #059669; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .badge-paid { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #d97706; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .badge-rapid { background: rgba(59,130,246,0.2); color: #60a5fa; border: 1px solid #2563eb; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .btn-start { background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 10px 22px; border-radius: 8px; text-decoration: none; font-weight: 800; font-size: 13.5px; }
        .btn-locked { background: #475569; color: #cbd5e1; padding: 10px 18px; border-radius: 8px; font-weight: bold; font-size: 13px; text-decoration: none; cursor: not-allowed; }
        .section-box { display: none; background: #0f172a; border: 1.5px solid #334155; border-radius: 12px; padding: 22px; text-align: center; }
        .rank-table { width: 100%; border-collapse: collapse; margin-top: 15px; text-align: left; font-size: 13.5px; }
        .rank-table th, .rank-table td { padding: 10px 12px; border-bottom: 1px solid #334155; }
        .rank-table th { color: #34d399; }
        .doc-link { display: inline-block; background: #1e293b; color: #38bdf8; border: 1.5px solid #0284c7; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 13px; margin: 6px; }
        .footer { text-align: center; font-size: 12px; color: #64748b; margin-top: 25px; border-top: 1px solid #334155; padding-top: 15px; }
        
        /* Loading splash buffer popup */
        .loading-modal { display: none; position: fixed; inset: 0; background: rgba(11,19,41,0.92); z-index: 9999; justify-content: center; align-items: center; padding: 15px; }
        .modal-content { background: #162036; border: 2px solid #10b981; border-radius: 16px; padding: 30px 20px; max-width: 480px; text-align: center; box-shadow: 0 15px 40px rgba(0,0,0,0.6); }
    </style>
    <script>
        function filterTab(category, btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            document.getElementById('testsContainer').style.display = 'none';
            document.getElementById('battleContainer').style.display = 'none';
            document.getElementById('docsContainer').style.display = 'none';

            if (category === 'battle') {
                document.getElementById('battleContainer').style.display = 'block';
            } else if (category === 'docs') {
                document.getElementById('docsContainer').style.display = 'block';
            } else {
                document.getElementById('testsContainer').style.display = 'grid';
                let visibleCount = 0;
                document.querySelectorAll('.test-card').forEach(card => {
                    const cardCat = card.getAttribute('data-cat') || 'free';
                    if (category === 'all' || cardCat === category) {
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
    </script>
</head>
<body>
<!-- Loading Safety Buffer Modal -->
<div id="loadingNoticeModal" class="loading-modal">
    <div class="modal-content">
        <h3 style="color:#34d399; margin:0 0 10px; font-size:20px;">🛡️ सुरक्षित परीक्षा कक्ष लोड होत आहे...</h3>
        <p style="color:#cbd5e1; font-size:14.5px; line-height:1.6; margin:0 0 20px;">
            ⏳ सर्व्हरशी सुरक्षित संपर्क प्रस्थापित होत आहे. काही सेकंद वेळ लागू शकतो, <b>पण घाबरण्याची अजिबात गरज नाही; आपण पूर्णपणे सुरक्षित आहात!</b> खाकीच्या सरावासाठी सज्ज व्हा!
        </p>
        <button onclick="proceedToTest()" style="background:linear-gradient(135deg, #10b981, #059669); color:#022c22; border:none; padding:12px 28px; border-radius:8px; font-weight:800; font-size:15px; cursor:pointer; width:100%;">
            🚀 पुढे चला (कंटिन्यू) ➔
        </button>
    </div>
</div>

<div class="top-bar">
    <div style="font-weight:bold; font-size:13.5px; color:#a7f3d0; display:flex; align-items:center; gap:8px;">
        <span class="badge-live">LIVE</span> 🕒 मिशन खाकी २०२६ सराव कक्ष
    </div>
    {% if is_admin %}<a href="/admin/dashboard" style="background:#059669; color:white; padding:6px 14px; border-radius:6px; text-decoration:none; font-size:12px; font-weight:bold;">⚙ ॲडमिन</a>{% endif %}
</div>

<div class="box">
    <div class="hero-banner">
        <h1>⚔️ महाराष्ट्र पोलीस अतिसंभाव्य टेस्ट महा-पोर्टल</h1>
        <div class="quote-box">
            🔥 "मैदानावर खाकीची जिद्द दाखवली, आता लेखी परीक्षेत तुमची तयारी किती आहे ते सिद्ध करा!" 🌟
        </div>
    </div>

    <!-- ॲडमिनद्वारे बदलता येणारा टॅब क्रम -->
    <div class="tabs-wrapper">
        {% for tab_key in ordered_tabs %}
            {% if tab_key == 'all' %}<button class="tab-btn active" onclick="filterTab('all', this)">🌐 सर्व संच</button>
            {% elif tab_key == 'live' %}<button class="tab-btn" onclick="filterTab('live', this)">🔴 मिशन खाकी महासंग्राम</button>
            {% elif tab_key == 'paid' %}<button class="tab-btn" onclick="filterTab('paid', this)">🎯 अतिसंभाव्य १०० गुण संच (₹९९)</button>
            {% elif tab_key == 'free' %}<button class="tab-btn" onclick="filterTab('free', this)">🟢 मोफत टेस्ट्स</button>
            {% elif tab_key == 'rapid' %}<button class="tab-btn" onclick="filterTab('rapid', this)">⚡ २० गुण रॅपिड फायर</button>
            {% elif tab_key == 'battle' %}<button class="tab-btn" onclick="filterTab('battle', this)">⚔️ जिल्हा मुकाबला व रँक</button>
            {% elif tab_key == 'docs' %}<button class="tab-btn" onclick="filterTab('docs', this)">📄 भरती PDF व PYQ</button>
            {% endif %}
        {% endfor %}
    </div>

    <div id="testsContainer" class="test-grid">
        {% for t in tests %}
        <div class="test-card" data-id="{{ t.id }}" data-type="{{ t.test_type }}" data-cat="{{ t.category or 'free' }}">
            <div>
                <h4 class="test-title">{{ t.test_title }}</h4>
                <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                    <span class="{{ 'badge-free' if t.test_type == 'Free' else 'badge-paid' }}">
                        {{ '🟢 मोफत महासराव' if t.test_type == 'Free' else '⭐ अतिसंभाव्य संच - ₹' ~ t.test_fee }}
                    </span>
                    <span class="badge-rapid">⏱️ {{ t.duration_minutes }} मिनिटे</span>
                    {% if t.is_locked %}
                    <span style="font-size:12px; color:#fbbf24;">⏳ दररोज सकाळी १०:०० वाजता अनलॉक होईल</span>
                    {% endif %}
                </div>
            </div>
            {% if t.is_locked %}
                <span class="btn-locked">🔒 सकाळी १०:०० ला उघडेल</span>
            {% else %}
                <button onclick="openLoadingNotice('/take_test/{{ t.id }}')" class="btn-start" style="border:none; cursor:pointer;">🚀 टेस्ट सोडवा</button>
            {% endif %}
        </div>
        {% endfor %}
        <div id="noTestMsg" style="display:none; text-align:center; padding:35px 20px; background:#0f172a; border-radius:12px; border:1px dashed #475569; color:#94a3b8; font-size:15px;">
            🎯 <b>लवकरच या विभागात अतिसंभाव्य व दर्जेदार प्रश्नसंच उपलब्ध होतील!</b><br>
            <span style="font-size:13px; color:#64748b;">आमचे तज्ज्ञ शिक्षक नवीन दर्जेदार प्रश्नांची रचना करत आहेत. खाकीची तयारी अखंड चालू ठेवा! ⚔️</span>
        </div>
    </div>

    <!-- लाईव्ह जिल्हा मुकाबला (थेट डेटाबेसमधून रिअल गणना) -->
    <div id="battleContainer" class="section-box">
        <h3 style="color:#f59e0b; margin-top:0;">🏆 राज्यस्तरीय जिल्हा मुकाबला (लाईव्ह लीड्स व सरासरी गुण)</h3>
        <p style="font-size:13px; color:#94a3b8; margin:0 0 15px;">महाराष्ट्रभरातील विद्यार्थ्यांनी सोडवलेल्या टेस्ट्सवरून थेट तयार झालेली वास्तविक गुणवत्ता क्रमवारी:</p>
        <table class="rank-table">
            <tr><th>रँक</th><th>जिल्हा</th><th>टेस्ट देणारे एकूण विद्यार्थी (लीड्स)</th><th>सरासरी गुण</th></tr>
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

    <div class="footer">
        <span>© 2026 मिशन खाकी ऑनलाईन महा-सराव कक्ष | </span>
        <a href="/terms-and-conditions" target="_blank" style="color:#38bdf8;">Terms & Conditions</a>
    </div>
</div>
</body>
</html>'''

TERMS_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms and Conditions</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; padding: 25px 15px; line-height: 1.6; }
        .terms-container { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 35px; box-shadow: 0 10px 25px rgba(0,0,0,0.06); border-top: 5px solid #059669; }
        h1 { color: #065f46; font-size: 24px; margin-top: 0; }
        p { font-size: 13.5px; color: #475569; margin: 6px 0 12px; }
        .back-link { display: inline-block; margin-top: 20px; color: #0284c7; text-decoration: none; font-weight: 600; font-size: 13px; }
    </style>
</head>
<body>
<div class="terms-container">
    <h1>Terms and Conditions</h1>
    <p>Last updated: October 2026</p>
    <p>This platform provides practice examinations for preparation. Mock scores are self-assessment metrics.</p>
    <a href="/" class="back-link">⬅ Back to Home Platform</a>
</div>
</body>
</html>'''

EXAM_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ test.test_title }} - परीक्षा कक्ष</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; transition: all 0.15s ease; }
        body { margin: 0; background: #0b1329; color: #f1f5f9; padding: 10px; }
        .exam-header { background: #1e293b; color: white; padding: 14px 20px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; max-width: 850px; margin: 0 auto 15px; position: sticky; top: 10px; z-index: 100; border: 1.5px solid #334155; }
        .timer-box { background: rgba(239,68,68,0.15); border: 1.5px solid #ef4444; color: #fca5a5; padding: 6px 14px; border-radius: 8px; font-weight: 800; font-size: 16px; }
        .progress-bar-container { max-width: 850px; margin: 0 auto 15px; background: #1e293b; height: 8px; border-radius: 10px; overflow: hidden; border: 1px solid #334155; }
        .progress-bar-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #10b981, #34d399); }
        .box { max-width: 850px; margin: 0 auto; background: #162036; border-radius: 16px; padding: 25px; border: 1px solid #334155; }
        .q-item { background: #0f172a; border: 1.5px solid #27354f; border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; }
        .q-text { font-weight: 700; margin-bottom: 14px; font-size: 16px; color: #f8fafc; }
        .opt-label { display: flex; align-items: center; margin-bottom: 10px; font-size: 14.5px; cursor: pointer; background: #1e293b; padding: 12px 16px; border-radius: 10px; border: 1.5px solid #334155; color: #cbd5e1; }
        .opt-label:hover { background: #27354f; border-color: #38bdf8; color: white; transform: translateX(3px); }
        .opt-label input[type="radio"] { margin-right: 12px; width: 18px; height: 18px; accent-color: #10b981; }
        .opt-label.selected { background: rgba(16,185,129,0.15); border-color: #10b981; color: #a7f3d0; font-weight: 700; }
        .bottom-submission-card { background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(15,23,42,0.9)); border: 2px solid #10b981; border-radius: 14px; padding: 22px; margin-top: 30px; }
        .bottom-submission-card input { width: 100%; padding: 13px; background: #0f172a; border: 1.5px solid #334155; border-radius: 8px; margin-top: 5px; font-size: 14.5px; margin-bottom: 12px; color: white; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 15px; border: none; border-radius: 8px; font-size: 17px; font-weight: 800; cursor: pointer; }
        .btn-submit:disabled { background: #334155; color: #64748b; cursor: not-allowed; }
    </style>
    <script>
        let isFormSubmitted = false;
        const testStorageKey = 'shreeguru_saved_answers_{{ test.id }}';
        const timerStorageKey = 'shreeguru_saved_timer_{{ test.id }}';

        window.addEventListener('beforeunload', function (e) {
            if (!isFormSubmitted) {
                e.preventDefault();
                e.returnValue = 'तुम्ही खरंच परीक्षा सोडून बाहेर पडू इच्छिता का?';
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
                submitBtn.innerText = "⚠️ खाली नाव, जिल्हा व १० अंकी WhatsApp नंबर भरा";
                submitBtn.style.opacity = "0.6";
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('examForm').addEventListener('submit', function() {
                isFormSubmitted = true;
                localStorage.removeItem(testStorageKey);
                localStorage.removeItem(timerStorageKey);
            });
        });

        window.onload = function() {
            restoreAnswerProgress();
            startTimer();
            validateAndReady();
        };
    </script>
</head>
<body>
<div class="exam-header">
    <div>
        <h3 style="margin:0; font-size:17px; color:#34d399;">⚔️ {{ test.test_title }}</h3>
        <small id="progressText" style="color:#94a3b8; font-weight:600;">० / {{ questions|length }} सोडवले</small>
    </div>
    <div class="timer-box">⏳ <span id="time-left">00:00</span></div>
</div>

<div class="progress-bar-container">
    <div id="progressFill" class="progress-bar-fill"></div>
</div>

<div class="box">
    <form id="examForm" method="POST" action="/submit_test/{{ test.id }}">
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
            <h3 style="margin:0 0 6px; color:#34d399; font-size:18px;">🎯 निकाल व स्पष्टीकरणासाठी माहिती भरा:</h3>
            <p style="font-size:13px; color:#94a3b8; margin:0 0 14px;">
                {% if test.category == 'rapid' %}
                    ⚠️ आपण खाली टाकत असलेल्या WhatsApp नंबरवर रोज सकाळी १०:०० वाजता रॅपिड फायर टेस्टची लिंक व उत्तरतालिका पाठवली जाईल.
                {% else %}
                    ⚠️ १०० प्रश्नांची अचूक उत्तरतालिका याच WhatsApp नंबरवर पाठवली जाईल.
                {% endif %}
            </p>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">पूर्ण नाव *:</label><input type="text" name="student_name" id="s_name" placeholder="उदा. राहुल पाटील" onkeyup="validateAndReady()" required></div>
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">जिल्हा *:</label><input type="text" name="district" id="s_dist" placeholder="उदा. कोल्हापूर" onkeyup="validateAndReady()" required></div>
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">WhatsApp मोबाईल नंबर *:</label><input type="tel" name="phone" id="s_phone" placeholder="10 अंकी मोबाईल नंबर" maxlength="10" onkeyup="validateAndReady()" required></div>
            </div>
        </div>
        <button type="submit" id="submitBtn" class="btn-submit" disabled>⚠️ खाली नाव, जिल्हा व WhatsApp नंबर भरा</button>
    </form>
</div>
</body>
</html>'''

RESULT_SUMMARY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>टेस्ट निकाल - अभिनंदन</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #0b1329; color: #f1f5f9; padding: 15px; }
        .box { max-width: 760px; margin: 15px auto; background: #162036; border-radius: 16px; padding: 25px; box-shadow: 0 15px 35px rgba(0,0,0,0.4); border-top: 6px solid #10b981; }
        .cutoff-warning-box { background: rgba(239,68,68,0.15); border: 2px solid #ef4444; border-radius: 12px; padding: 16px; margin: 15px 0; color: #fca5a5; text-align: center; }
        .cert-card { background: linear-gradient(135deg, #1e293b, #0f172a); color: white; border: 3px double #f59e0b; padding: 22px; border-radius: 12px; margin: 20px 0; text-align: center; }
        .btn-wa { display: inline-block; background: #25D366; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 15px; margin: 8px 4px; cursor: pointer; border: none; }
        .btn-group { display: block; background: linear-gradient(135deg, #25D366, #128C7E); color: white; padding: 14px 20px; border-radius: 10px; text-decoration: none; font-weight: 800; font-size: 15px; text-align: center; margin: 20px 0; box-shadow: 0 6px 18px rgba(37,211,102,0.3); border: 1.5px solid #86efac; cursor: pointer; }
        .btn-pay { display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706); color: #0f172a; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 800; font-size: 16px; margin-top: 10px; }
        .promo-box { background: #0f172a; border: 1.5px solid #334155; padding: 15px; border-radius: 10px; margin-top: 20px; text-align: center; }
        .btn-link { display: inline-block; color: white; padding: 8px 15px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; margin: 4px; cursor: pointer; border: none; }
        input[type="tel"] { width: 100%; max-width: 280px; padding: 11px; background: #0f172a; border: 1.5px solid #334155; border-radius: 8px; color: white; font-size: 14px; text-align: center; margin-bottom: 10px; }

        /* Privacy Rules Modal for WhatsApp Group Entry */
        .rules-modal { display: none; position: fixed; inset: 0; background: rgba(11,19,41,0.95); z-index: 10000; justify-content: center; align-items: center; padding: 15px; }
        .rules-content { background: #162036; border: 2px solid #25D366; border-radius: 14px; padding: 25px; max-width: 580px; max-height: 90vh; overflow-y: auto; text-align: left; }
    </style>
    <script>
        function openRulesModal() {
            document.getElementById('waRulesModal').style.display = 'flex';
        }
        function closeRulesModal() {
            document.getElementById('waRulesModal').style.display = 'none';
        }
        function handleSocialLink(url) {
            if (url && url.trim() !== '') {
                window.open(url, '_blank');
            } else {
                alert("🌟 संपूर्ण प्रवासाची यशोगाथा लवकरच आपल्या भेटीस येत आहे! खाकीचे स्वप्न नक्की पूर्ण होणार! ⚔️");
            }
        }
    </script>
</head>
<body>

<!-- व्हॉट्सॲप ग्रुप नियम व प्रायव्हसी मोडल (Rules Modal) -->
<div id="waRulesModal" class="rules-modal">
    <div class="rules-content">
        <h3 style="color:#25D366; margin-top:0; text-align:center;">🚨 अधिकृत सराव ग्रुप नियम व अटी</h3>
        <p style="font-size:13px; color:#cbd5e1; line-height:1.5;">या ग्रुपचा उद्देश केवळ पोलीस भरती परीक्षेचा सराव, मोफत टेस्ट्स आणि अभ्यासाची माहिती देणे हा आहे. ग्रुपमध्ये सहभागी होण्यापूर्वी खालील नियमांचे पालन करणे बंधनकारक आहे:</p>
        
        <div style="background:#0f172a; padding:12px; border-radius:8px; border-left:4px solid #ef4444; margin-bottom:10px;">
            <b style="color:#fca5a5; font-size:13px;">१. प्रायव्हसी व महिलांचा सन्मान (Privacy Rules):</b>
            <p style="font-size:12px; color:#cbd5e1; margin:4px 0;">ग्रुपमध्ये महिला/विद्यार्थिनी सदस्य देखील आहेत. कोणत्याही सदस्याने इतर सदस्याला (विशेषतः महिलांना) परस्पर वैयक्तिक मेसेज किंवा कॉल करणे सक्त मनाई आहे. असा प्रकार आढळल्यास नंबर त्वरित ब्लॉक केला जाईल.</p>
        </div>

        <div style="background:#0f172a; padding:12px; border-radius:8px; border-left:4px solid #38bdf8; margin-bottom:10px;">
            <b style="color:#7dd3fc; font-size:13px;">२. फक्त अभ्यास चर्चा:</b>
            <p style="font-size:12px; color:#cbd5e1; margin:4px 0;">कोणतेही राजकीय, वैयक्तिक, वादग्रस्त किंवा धार्मिक फॉरवर्ड मेसेज टाकण्यास सक्त बंदी आहे. फक्त पोलीस भरती सराव प्रश्न शेअर करावेत.</p>
        </div>

        <div style="background:#0f172a; padding:12px; border-radius:8px; border-left:4px solid #f59e0b; margin-bottom:15px;">
            <b style="color:#fde047; font-size:13px;">३. कायदेशीर अस्वीकरण (Disclaimer / ॲडमिन जबाबदारी):</b>
            <p style="font-size:12px; color:#cbd5e1; margin:4px 0;"><b>हा ग्रुप फक्त शैक्षणिक अभ्यासासाठी आहे. ग्रुपमधील सदस्यांच्या कोणत्याही परस्पर वैयक्तिक संभाषणाला किंवा गैरवर्तनाला ग्रुप ॲडमिन जबाबदार असणार नाही.</b> कोणीही परस्पर संपर्क साधल्यास ती त्यांची स्वतःची जबाबदारी राहील.</p>
        </div>

        <div style="display:flex; gap:10px;">
            <a href="{{ wa_active_link }}" target="_blank" onclick="closeRulesModal()" style="flex:2; background:#25D366; color:#064e3b; text-align:center; padding:12px; border-radius:6px; font-weight:bold; font-size:14px; text-decoration:none;">
                ✅ नियम मान्य आहेत — ग्रुपमध्ये सामील व्हा
            </a>
            <button onclick="closeRulesModal()" style="flex:1; background:#475569; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer;">रद्द करा</button>
        </div>
    </div>
</div>

<div class="box">
    <h2 style="color:#34d399; margin:0 0 5px; text-align:center;">🎉 टेस्ट यशस्वीरीत्या पूर्ण झाली!</h2>
    <div style="background:#0f172a; border:1px solid #334155; border-radius:12px; padding:18px; margin:15px 0; text-align:center;">
        <p style="font-size:16px; margin:4px 0; color:#cbd5e1;">परीक्षार्थी: <b>{{ lead.student_name }}</b> (जिल्हा: <b>{{ lead.district }}</b>)</p>
        <p style="font-size:24px; color:#fbbf24; font-weight:bold; margin-top:8px;">🏆 संपूर्ण महाराष्ट्रातील रँक: <b style="color:#34d399; font-size:32px;">#{{ state_rank }}</b> 🌟</p>
        <p style="font-size:20px; font-weight:bold; color:#f8fafc; margin-top:4px;">प्राप्त गुण: <span style="color:#10b981;">{{ lead.score }}</span> / {{ lead.total_marks }}</p>
    </div>

    <!-- अधिकृत WhatsApp ग्रुप जॉइन बटण (नियम पडताळणीसह) -->
    {% if wa_active_link %}
    <button onclick="openRulesModal()" class="btn-group">
        📲 दररोज सकाळी १०:०० वाजता मोफत रॅपिड टेस्ट मिळवण्यासाठी अधिकृत WhatsApp ग्रुपमध्ये सामील व्हा ➔
    </button>
    {% endif %}

    {% if test_category != 'rapid' %}
    <div class="cutoff-warning-box">
        <h4 style="margin:0 0 5px; color:#ef4444; font-size:17px;">⚠️ सावधान! मेरिट लिस्ट धोक्यात आहे!</h4>
        <p style="font-size:14px; margin:0; line-height:1.5;">तुमच्या <b>{{ lead.district }}</b> जिल्ह्याचा संभाव्य कट-ऑफ <b>८२ गुण</b> आहे, आणि तुमचे <b>{{ lead.score }} गुण</b> आले आहेत.</p>
        <a href="/take_test/6" class="btn-pay">⚡ '५० संभाव्य टेस्ट्स संच' फक्त ₹९९ मध्ये आत्ताच अनलॉक करा</a>
    </div>
    {% endif %}

    <!-- स्वाभिमान डिजिटल चॅलेंज कार्ड (व्हायरल वाक्यासह) -->
    <div class="cert-card">
        <h3 style="color:#fde047; margin:0 0 6px; font-size:20px;">🎖️ मिशन खाकी २०२६ — स्वाभिमान चॅलेंज</h3>
        <p style="font-size:15px; color:#a7f3d0; margin:10px 0; font-weight:bold; line-height:1.5;">
            "🔥 तुझ्यासोबत तुझा मित्रही भरती झाला पाहिजे! त्यालाही ही लिंक पाठव आणि उद्याची रॅपिड टेस्ट मिळव!"
        </p>
        <a href="https://wa.me/?text={{ ego_share_encoded }}" target="_blank" class="btn-wa">⚔️ मित्रांना WhatsApp वर चॅलेंज द्या</a>
    </div>

    {% if test_category == 'rapid' %}
    <div style="background:#0f172a; border:2px solid #10b981; border-radius:12px; padding:22px; text-align:center; margin-top:20px;">
        <h3 style="color:#34d399; margin-top:0;">📖 सविस्तर स्पष्टीकरण पाहण्यासाठी:</h3>
        <p style="font-size:13.5px; color:#cbd5e1; margin-bottom:12px;">कृपया तुम्ही फॉर्ममध्ये भरलेला तुमचा <b>मूळ १० अंकी WhatsApp नंबर</b> येथे टाका:</p>
        <form method="POST" action="/verify_rapid_key/{{ lead.access_token }}">
            <input type="tel" name="verify_phone" placeholder="१० अंकी WhatsApp नंबर" maxlength="10" required><br>
            <button type="submit" style="background:#10b981; color:#064e3b; padding:10px 24px; border:none; border-radius:6px; font-weight:800; cursor:pointer;">🔓 स्पष्टीकरण शीट उघडा</button>
        </form>
    </div>
    {% else %}
    <div style="text-align:center; margin:20px 0;">
        <a href="{{ result_url }}" target="_blank" style="background:#10b981; color:#064e3b; padding:12px 26px; border-radius:8px; text-decoration:none; font-weight:800; display:inline-block;">📖 सविस्तर स्पष्टीकरण शीट पहा</a>
    </div>
    {% endif %}

    <!-- सोशल मीडिया टॅब्स (लिंक नसल्यास प्रेरणादायी मेसेज) -->
    <div class="promo-box">
        <h4 style="margin:0 0 10px; color:#34d399;">🌟 अधिकृत सोशल मीडिया व यशोगाथा लिंक्स:</h4>
        <button onclick="handleSocialLink('{{ insta_link }}')" class="btn-link" style="background:#E1306C;">📸 Instagram</button>
        <button onclick="handleSocialLink('{{ yt_link }}')" class="btn-link" style="background:#FF0000;">▶ YouTube</button>
        <button onclick="handleSocialLink('{{ toppers_link }}')" class="btn-link" style="background:#0284c7;">🏆 यशवंतांचे फोटो</button>
    </div>
</div>
</body>
</html>'''

ACCESS_CHECK_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>सशुल्क टेस्ट प्रवेश द्वार - {{ test.test_title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        body { font-family:'Poppins', sans-serif; background:#0b1329; color:#f1f5f9; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }
        .box { max-width:480px; width:100%; background:#162036; border-radius:16px; padding:25px; box-shadow:0 15px 35px rgba(0,0,0,0.4); border-top:6px solid #10b981; }
        input { width:100%; padding:11px; background:#0f172a; border:1.5px solid #334155; border-radius:8px; margin-bottom:12px; font-size:14px; box-sizing:border-box; color:white; }
        .btn-rzp { width:100%; background:linear-gradient(135deg, #2563eb, #1d4ed8); color:white; padding:14px; border:none; border-radius:8px; font-weight:800; cursor:pointer; font-size:15px; margin-bottom:15px; }
    </style>
</head>
<body>
<div class="box">
    <h2 style="color:#34d399; text-align:center; margin:0 0 5px;">🔒 ५० टेस्ट्स महासंच प्रवेश द्वार</h2>
    <p style="text-align:center; font-size:13px; color:#94a3b8;">{{ test.test_title }} (फी: ₹{{ test.test_fee }})</p>

    <div style="background:rgba(245,158,11,0.15); border:1px solid #f59e0b; border-radius:8px; padding:12px; margin-bottom:15px; text-align:center;">
        <p style="color:#fde68a; font-size:12.5px; margin:0; font-weight:600;">
            ⚡ <b>विशेष सूचना:</b> पेमेंट यशस्वी झाल्यानंतर <b>पहिल्या ३ टेस्ट्स त्वरित अनलॉक होतील</b>. उर्वरित टेस्ट्स तुमच्या सराव सातत्यासाठी <b>दररोज सकाळी १०:०० वाजता आपोआप अनलॉक होत राहतील!</b>
        </p>
    </div>

    <div style="text-align:center;">
        <button id="rzp-button" class="btn-rzp">⚡ GooglePay / PhonePe द्वारे त्वरित अनलॉक करा (₹९९)</button>
    </div>

    <div style="background:#0f172a; padding:14px; border-radius:8px; border:1px solid #f59e0b; text-align:center; margin-bottom:15px;">
        <p style="margin:0 0 6px; font-weight:bold; color:#fbbf24; font-size:12px;">किंवा QR स्कॅन करून <b>{{ upi_mobile }}</b> वर पे करा:</p>
        <img src="{{ qr_url }}" alt="QR" style="max-width:130px; max-height:130px; border-radius:6px;">
    </div>

    <form method="POST" action="/request_paid_test/{{ test.id }}">
        <input type="text" name="student_name" placeholder="पूर्ण नाव" required>
        <input type="text" name="district" placeholder="जिल्हा" required>
        <input type="tel" name="phone" placeholder="10 अंकी WhatsApp नंबर" maxlength="10" required>
        <button type="submit" style="width:100%; background:#10b981; color:#064e3b; padding:11px; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">🚀 मॅन्युअल स्क्रीनशॉट पाठवला आहे</button>
    </form>
</div>

<script>
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
            "name": "श्रीगुरु करिअर अकॅडमी",
            "description": "{{ test.test_title }}",
            "order_id": data.order_id,
            "handler": function (response){
                window.location.href = "/verify_razorpay_payment?order_id=" + response.razorpay_order_id + "&payment_id=" + response.razorpay_payment_id + "&signature=" + response.razorpay_signature + "&test_id={{ test.id }}";
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

DETAILED_KEY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>सविस्तर उत्तरपत्रिका व स्पष्टीकरण</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
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

    <h2 style="color:#34d399; text-align:center; margin-top:0;">📋 सविस्तर उत्तरपत्रिका व स्पष्टीकरण</h2>
    <p style="text-align:center; font-size:13px; color:#94a3b8;">विद्यार्थी: <b>{{ lead.student_name }}</b> (जिल्हा: {{ lead.district }})</p>

    {% for item in evaluated_questions %}
    <div class="item {{ 'correct-box' if item.is_correct else 'wrong-box' }}">
        <div style="font-weight:bold; margin-bottom:6px; color:#f8fafc;">प्र. {{ loop.index }}. {{ item.q_text }}</div>
        <div style="font-size:13px; margin-bottom:4px; color:#94a3b8;">A) {{ item.opt_a }} | B) {{ item.opt_b }} | C) {{ item.opt_c }} | D) {{ item.opt_d }}</div>
        <div style="margin:6px 0; font-size:13.5px;">
            तुमचे उत्तर: <b style="color:{{ '#34d399' if item.is_correct else '#f87171' }};">{{ item.user_ans }}</b> | अचूक: <b style="color:#34d399;">{{ item.correct_ans }}</b>
        </div>
        {% if item.explanation %}
        <div style="background:rgba(16,185,129,0.1); color:#a7f3d0; padding:8px 12px; border-radius:6px; font-size:12px; border:1px solid #059669; margin-top:6px;">
            💡 <b>स्पष्टीकरण:</b> {{ item.explanation }}
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

EDIT_QUESTION_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>प्रश्न संपादित करा</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f1f5f9; padding: 20px; }
        .box { max-width: 650px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 5px solid #059669; }
        input, textarea, select { width: 100%; padding: 9px; margin: 6px 0 14px; border: 1px solid #cbd5e1; border-radius: 5px; }
        .btn { background: #059669; color: white; border: none; padding: 10px 18px; border-radius: 5px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
<div class="box">
    <h3 style="color:#065f46; margin-top:0;">✏️ प्रश्न व पर्याय संपादित करा (ID: {{ q.id }})</h3>
    <form method="POST">
        <label style="font-weight:600; font-size:13px;">प्रश्न:</label>
        <textarea name="question" rows="3" required>{{ q.question }}</textarea>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
            <div><label style="font-weight:600; font-size:13px;">पर्याय A:</label><input type="text" name="opt_a" value="{{ q.opt_a }}" required></div>
            <div><label style="font-weight:600; font-size:13px;">पर्याय B:</label><input type="text" name="opt_b" value="{{ q.opt_b }}" required></div>
            <div><label style="font-weight:600; font-size:13px;">पर्याय C:</label><input type="text" name="opt_c" value="{{ q.opt_c }}" required></div>
            <div><label style="font-weight:600; font-size:13px;">पर्याय D:</label><input type="text" name="opt_d" value="{{ q.opt_d }}" required></div>
        </div>
        <label style="font-weight:600; font-size:13px;">अचूक उत्तर:</label>
        <select name="correct">
            <option value="A" {% if q.correct=='A' %}selected{% endif %}>A</option>
            <option value="B" {% if q.correct=='B' %}selected{% endif %}>B</option>
            <option value="C" {% if q.correct=='C' %}selected{% endif %}>C</option>
            <option value="D" {% if q.correct=='D' %}selected{% endif %}>D</option>
        </select>
        <label style="font-weight:600; font-size:13px;">स्पष्टीकरण:</label>
        <textarea name="explanation" rows="2">{{ q.explanation }}</textarea>
        <button type="submit" class="btn">💾 बदल सेव्ह करा</button>
        <a href="/admin/dashboard?tab=questions&filter_test_id={{ q.test_id }}" style="margin-left:10px; color:#dc2626; text-decoration:none; font-weight:600;">रद्द करा</a>
    </form>
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
    <meta charset="UTF-8"><title>ॲडमिन डॅशबोर्ड</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f1f5f9; color: #1e293b; padding: 15px; }
        .container { max-width: 1250px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        h2 { margin: 0 0 15px; color: #065f46; text-align: center; }
        .nav-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
        .nav-tabs a { padding: 8px 14px; background: #e2e8f0; color: #334155; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; }
        .nav-tabs a.active { background: #059669; color: white; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }
        th { background: #f8fafc; color: #0f172a; }
        input[type="text"], input[type="number"], select, textarea { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; margin-bottom: 8px; font-size: 13px; }
        .btn { background: #059669; color: white; padding: 8px 14px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
        .btn-sm { padding: 4px 8px; font-size: 11px; text-decoration: none; border-radius: 3px; display: inline-block; }
    </style>
    <script>
        function togglePassVis() {
            var p = document.getElementById("new_password");
            var btn = document.getElementById("passEyeBtn");
            if (p.type === "password") { p.type = "text"; btn.innerText = "🙈"; }
            else { p.type = "password"; btn.innerText = "👁️"; }
        }
    </script>
</head>
<body>
<div class="container">
    <h2>⚙️ राज्यस्तरीय परीक्षा प्लॅटफॉर्म - ॲडमिन डॅशबोर्ड</h2>
    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
        <a href="/" style="font-weight:bold; color:#0284c7; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a>
        <a href="/admin/logout" style="font-weight:bold; color:#dc2626; text-decoration:none;">🚪 लॉगआऊट</a>
    </div>

    <div class="nav-tabs">
        <a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 Leads (विद्यार्थी डेटा)</a>
        <a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 Payments & Razorpay</a>
        <a href="/admin/dashboard?tab=special" class="{{ 'active' if active_tab == 'special' else '' }}">👑 Special Access</a>
        <a href="/admin/dashboard?tab=questions" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions</a>
        <a href="/admin/dashboard?tab=launch" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Tests Management (टॅब निवड)</a>
        <a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard</a>
        <a href="/admin/dashboard?tab=feedback" class="{{ 'active' if active_tab == 'feedback' else '' }}">💬 Feedback</a>
        <a href="/admin/dashboard?tab=notices" class="{{ 'active' if active_tab == 'notices' else '' }}">📢 PDF Docs</a>
        <a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Settings (टॅब क्रम व WhatsApp)</a>
    </div>

    <!-- 1. LEADS TAB -->
    {% if active_tab == 'leads' %}
    <h3>📱 विद्यार्थ्यांची लीड्स यादी</h3>
    <div style="background:#f8fafc; padding:12px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:15px;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <input type="hidden" name="tab" value="leads">
            <label style="font-size:12px; font-weight:bold;">जिल्हा फिल्टर:</label>
            <select name="lead_dist" style="width:160px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व जिल्हे --</option>
                {% for d in all_districts %}<option value="{{ d }}" {% if lead_dist==d %}selected{% endif %}>{{ d }}</option>{% endfor %}
            </select>
            <label style="font-size:12px; font-weight:bold; margin-left:10px;">टेस्ट फिल्टर:</label>
            <select name="lead_test_id" style="width:200px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व टेस्ट्स --</option>
                {% for t in tests %}<option value="{{ t.id }}" {% if lead_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <a href="/admin/dashboard?tab=leads" class="btn-sm" style="background:#64748b; color:white;">Clear</a>
        </form>
    </div>
    <table>
        <tr><th>दिनांक</th><th>नाव</th><th>जिल्हा</th><th>WhatsApp</th><th>टेस्ट</th><th>गुण</th><th>कृती</th></tr>
        {% for l in leads %}
        <tr>
            <td>{{ l.test_date }}</td>
            <td><b>{{ l.student_name }}</b></td>
            <td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td>
            <td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
            <td><a href="/admin/delete_lead/{{ l.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('डिलीट करायची का?');">🗑️</a></td>
        </tr>
        {% endfor %}
    </table>

    <!-- 2. PAYMENTS & RAZORPAY TAB -->
    {% elif active_tab == 'payments' %}
    <h3>💰 पेमेंट व्यवस्थापन (Razorpay + UPI QR)</h3>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom:20px;">
        <div style="background:#eff6ff; padding:15px; border-radius:6px; border:1px solid #bfdbfe;">
            <h4 style="margin:0 0 10px; color:#1e40af;">⚡ Razorpay ऑटोमॅटिक गेटवे सेटिंग्स:</h4>
            <form method="POST" action="/admin/update_razorpay_settings">
                <label style="font-weight:bold; font-size:12px;">Razorpay Key ID:</label>
                <input type="text" name="razorpay_key_id" value="{{ razorpay_key_id }}" placeholder="उदा. rzp_live_xxxxxxxx">
                <label style="font-weight:bold; font-size:12px;">Razorpay Key Secret:</label>
                <input type="text" name="razorpay_key_secret" value="{{ razorpay_key_secret }}" placeholder="उदा. abc123xyz...">
                <button type="submit" class="btn" style="background:#2563eb; width:100%;">💾 Razorpay Keys सेव्ह करा</button>
            </form>
        </div>

        <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
            <h4 style="margin:0 0 10px; color:#065f46;">📱 मॅन्युअल UPI / QR कोड सेटिंग्स:</h4>
            <form method="POST" action="/admin/update_payment_settings" enctype="multipart/form-data">
                <label style="font-weight:bold; font-size:12px;">UPI मोबाईल नंबर:</label>
                <input type="text" name="upi_mobile" value="{{ upi_mobile }}" required>
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

    <!-- 3. SPECIAL ACCESS TAB -->
    {% elif active_tab == 'special' %}
    <h3>👑 Special Access व्यवस्थापन</h3>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
        <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:15px; border-radius:8px;">
            <h4 style="color:#065f46; margin-top:0;">🔄 अमर्याद प्रयत्न सवलत (Unlimited)</h4>
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

    <!-- 4. QUESTIONS TAB -->
    {% elif active_tab == 'questions' %}
    <h3>📝 प्रश्न व्यवस्थापन</h3>
    <div style="background:#ecfdf5; padding:15px; border-radius:6px; margin-bottom:20px; border:1px solid #a7f3d0;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; align-items:center;">
            <input type="hidden" name="tab" value="questions">
            <label style="font-weight:bold; font-size:13px; color:#065f46;">टेस्ट निवडा:</label>
            <select name="filter_test_id" onchange="this.form.submit()" style="max-width:320px; margin-bottom:0;">
                <option value="">-- सर्व टेस्ट्सचे प्रश्न --</option>
                {% for t in tests %}
                <option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                {% endfor %}
            </select>
        </form>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:25px;">
        <form method="POST" action="/admin/add_question" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
            <h4 style="margin:0 0 8px; color:#065f46;">➕ एक प्रश्न ॲड करा</h4>
            <select name="test_id">
                {% for t in tests %}<option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <input type="text" name="question" placeholder="प्रश्न लिहा" required>
            <input type="text" name="opt_a" placeholder="पर्याय A" required>
            <input type="text" name="opt_b" placeholder="पर्याय B" required>
            <input type="text" name="opt_c" placeholder="पर्याय C" required>
            <input type="text" name="opt_d" placeholder="पर्याय D" required>
            <input type="text" name="correct" placeholder="अचूक उत्तर (A, B, C, D)" maxlength="1" required style="width:140px;">
            <input type="text" name="explanation" placeholder="स्पष्टीकरण">
            <button type="submit" class="btn">सेव्ह करा</button>
        </form>

        <form method="POST" action="/admin/bulk_questions" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
            <h4 style="margin:0 0 8px; color:#065f46;">⚡ बल्क प्रश्न अपलोडर (Pipe |)</h4>
            <select name="test_id" required>
                {% for t in tests %}<option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <textarea name="bulk_questions_text" rows="5" placeholder="प्रश्न | पर्यायA | पर्यायB | पर्यायC | पर्यायD | अचूक उत्तर | स्पष्टीकरण" required></textarea>
            <button type="submit" class="btn" style="background:#0284c7; width:100%;">📥 अपलोड करा</button>
        </form>
    </div>

    <form method="POST" action="/admin/upload_csv_questions" enctype="multipart/form-data" style="background:#f0fdf4; border:2px dashed #059669; padding:15px; border-radius:8px; margin-bottom:20px;">
        <h4 style="margin:0 0 8px; color:#065f46;">📥 १०० प्रश्नांची CSV फाईल अपलोड करा:</h4>
        <select name="test_id" required>
            {% for t in tests %}<option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
        </select>
        <input type="file" name="csv_file" accept=".csv" required style="margin-bottom:10px;">
        <button type="submit" class="btn" style="width:100%;">🚀 संपूर्ण १०० प्रश्न CSV द्वारे अपलोड करा</button>
    </form>

    <table>
        <tr><th>ID</th><th>प्रश्न</th><th>अचूक</th><th>स्पष्टीकरण</th><th>कृती</th></tr>
        {% for q in all_questions %}
        <tr>
            <td>{{ q.id }}</td><td><b>{{ q.question }}</b></td><td style="color:green; font-weight:bold;">{{ q.correct }}</td>
            <td>{{ q.explanation }}</td>
            <td style="white-space:nowrap;">
                <a href="/admin/edit_question/{{ q.id }}" class="btn-sm" style="background:#0284c7; color:white;">✏ एडिट</a>
                <a href="/admin/delete_question/{{ q.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('डिलीट करायचे?');">🗑️</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 5. TEST MANAGEMENT TAB -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 नवीन टेस्ट लॉन्च करा व टॅब निवडा</h3>

    <div style="background:#ecfdf5; border:2px solid #10b981; padding:15px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <div>
            <h4 style="margin:0; color:#065f46;">⚡ १-क्लिक ऑटोमॅटिक शेड्युलिंग (50 Tests + 50 Rapid + Demo)</h4>
            <small style="color:#047857;">१ डेमो टेस्ट, ५० रॅपिड फायर टेस्ट्स आणि ५० पेड टेस्ट्स दररोज सकाळी १०:०० वाजता आपोआप अनलॉक होतील.</small>
        </div>
        <form method="POST" action="/admin/bulk_schedule_all" onsubmit="return confirm('सर्व ५० टेस्ट्स व ५० रॅपिड टेस्ट्स रोज सकाळी १० ला शेड्युल करायच्या का?');">
            <button type="submit" class="btn" style="background:#10b981; color:#022c22; font-weight:bold;">🚀 ५० टेस्ट्स + ५० रॅपिड रोज सकाळी १० ला शेड्युल करा</button>
        </form>
    </div>

    <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:18px; border-radius:8px; border:1px solid #cbd5e1; margin-bottom:25px;">
        <label style="font-weight:bold; font-size:12.5px;">टेस्टचे नाव:</label>
        <input type="text" name="test_title" placeholder="उदा. महाराष्ट्र पोलीस अतिसंभाव्य टेस्ट संच #१०" required>
        
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:12px;">
            <div>
                <label style="font-weight:bold; font-size:12.5px;">होम पेज टॅब (कॅटेगरी):</label>
                <select name="category" required>
                    <option value="free">🟢 मोफत टेस्ट्स</option>
                    <option value="paid" selected>🎯 अतिसंभाव्य संच (₹९९)</option>
                    <option value="live">🔴 मिशन खाकी महासंग्राम</option>
                    <option value="rapid">⚡ २० गुण रॅपिड फायर</option>
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
                <label style="font-weight:bold; font-size:12.5px;">फी (₹):</label>
                <input type="number" name="test_fee" placeholder="फी" value="99">
            </div>
            <div>
                <label style="font-weight:bold; font-size:12.5px;">वेळ (मिनिटे):</label>
                <input type="number" name="duration_minutes" placeholder="वेळ" value="60">
            </div>
        </div>
        <button type="submit" class="btn" style="margin-top:8px;">🚀 नवीन टेस्ट सेव्ह करा</button>
    </form>

    <h4>सर्व टेस्ट्स यादी व प्रिंट व्यवस्थापन:</h4>
    <table>
        <tr><th>ID</th><th>नाव</th><th>होम पेज टॅब</th><th>प्रकार</th><th>फी</th><th>वेळ</th><th>स्थिती</th><th>कृती (प्रिंट व अपडेट)</th></tr>
        {% for t in tests %}
        <tr>
            <form method="POST" action="/admin/update_test/{{ t.id }}">
                <td>{{ t.id }}</td>
                <td><input type="text" name="test_title" value="{{ t.test_title }}" style="margin-bottom:0;" required></td>
                <td>
                    <select name="category" style="margin-bottom:0; font-weight:600;">
                        <option value="free" {% if t.category=='free' %}selected{% endif %}>🟢 मोफत टेस्ट्स</option>
                        <option value="paid" {% if t.category=='paid' %}selected{% endif %}>🎯 अतिसंभाव्य संच</option>
                        <option value="live" {% if t.category=='live' %}selected{% endif %}>🔴 महासंग्राम</option>
                        <option value="rapid" {% if t.category=='rapid' %}selected{% endif %}>⚡ रॅपिड फायर</option>
                    </select>
                </td>
                <td>
                    <select name="test_type" style="margin-bottom:0;">
                        <option value="Free" {% if t.test_type=='Free' %}selected{% endif %}>Free</option>
                        <option value="Paid" {% if t.test_type=='Paid' %}selected{% endif %}>Paid</option>
                    </select>
                </td>
                <td><input type="number" name="test_fee" value="{{ t.test_fee }}" style="width:70px; margin-bottom:0;"></td>
                <td><input type="number" name="duration_minutes" value="{{ t.duration_minutes }}" style="width:70px; margin-bottom:0;"></td>
                <td>
                    <select name="status" style="margin-bottom:0;">
                        <option value="Active" {% if t.status=='Active' %}selected{% endif %}>Active</option>
                        <option value="Closed" {% if t.status=='Closed' %}selected{% endif %}>Closed</option>
                    </select>
                </td>
                <td style="white-space:nowrap;">
                    <button type="submit" class="btn-sm" style="background:#0284c7; color:white; border:none; cursor:pointer;">💾 अपडेट</button>
                    <a href="/admin/print_test/{{ t.id }}" target="_blank" class="btn-sm" style="background:#059669; color:white;">🖨️ प्रिंट</a>
                    <a href="/admin/delete_test/{{ t.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('डिलीट करायची का?');">🗑</a>
                </td>
            </form>
        </tr>
        {% endfor %}
    </table>

    <!-- 6. LEADERBOARD TAB -->
    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 राज्यस्तरीय गुणवत्ता यादी (टॉप १००)</h3>
    <table>
        <tr><th>रँक</th><th>नाव</th><th>जिल्हा</th><th>WhatsApp</th><th>टेस्ट</th><th>गुण</th></tr>
        {% for rank, l in top_leads %}
        <tr>
            <td><b>#{{ rank }}</b></td><td>{{ l.student_name }}</td><td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td><td><b style="color:#059669;">{{ l.score }} / {{ l.total_marks }}</b></td>
        </tr>
        {% endfor %}
    </table>

    <!-- 7. FEEDBACK TAB -->
    {% elif active_tab == 'feedback' %}
    <h3>💬 विद्यार्थ्यांचे अभिप्राय</h3>
    <table>
        <tr><th>दिनांक</th><th>नाव</th><th>मोबाईल</th><th>अभिप्राय</th></tr>
        {% for f in feedbacks %}
        <tr>
            <td>{{ f.created_at }}</td><td><b>{{ f.student_name }}</b></td><td>{{ f.phone }}</td><td>{{ f.feedback_text }}</td>
        </tr>
        {% endfor %}
    </table>

    <!-- 8. RECRUITMENT PDF TAB -->
    {% elif active_tab == 'notices' %}
    <h3>📢 भरती PDF व्यवस्थापन (६ व्या टॅबसाठी)</h3>
    <form method="POST" action="/admin/update_pdf_docs" enctype="multipart/form-data">
        <label>भरती अधिकृत माहिती PDF:</label><input type="file" name="recruitment_pdf_file" accept=".pdf">
        <label>भरती पात्रता PDF:</label><input type="file" name="eligibility_pdf_file" accept=".pdf">
        <button type="submit" class="btn">सेव्ह करा</button>
    </form>

    <!-- 9. SETTINGS TAB (टॅब क्रम व WhatsApp ओव्हरफ्लो सेटिंग्स) -->
    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन पासवर्ड, टॅब क्रम व WhatsApp व्यवस्थापन</h3>
    <form method="POST" action="/admin/update_password">
        <label>नवा पासवर्ड:</label>
        <div style="position:relative; width:100%; margin-bottom:12px;">
            <input type="password" name="new_password" id="new_password" placeholder="नवा पासवर्ड टाका" style="padding-right:45px;">
            <button type="button" id="passEyeBtn" onclick="togglePassVis()" style="position:absolute; right:10px; top:8px; background:none; border:none; cursor:pointer;">👁️</button>
        </div>

        <label style="font-weight:bold; color:#065f46;">🌐 होम पेज टॅबचा क्रम (कॉमाने वेगळे करा):</label>
        <input type="text" name="tab_order" value="{{ tab_order }}" placeholder="उदा. all,rapid,paid,free,live,battle,docs">
        <small style="display:block; color:#64748b; margin-top:-5px; margin-bottom:10px;">(पर्याय: all, live, paid, free, rapid, battle, docs)</small>

        <label style="font-weight:bold; color:#1e40af;">📱 अधिकृत WhatsApp ग्रुप १ लिंक (प्राथमिक):</label>
        <input type="text" name="wa_group_link" value="{{ wa_group_link }}" placeholder="उदा. https://chat.whatsapp.com/XXXXX1">

        <label style="font-weight:bold; color:#b45309;">📱 अधिकृत WhatsApp ग्रुप २ लिंक (गट मर्यादा संपल्यास बॅकअप):</label>
        <input type="text" name="wa_group_link_2" value="{{ wa_group_link_2 }}" placeholder="उदा. https://chat.whatsapp.com/XXXXX2">

        <label>Instagram लिंक:</label><input type="text" name="insta_link" value="{{ insta_link }}">
        <label>YouTube लिंक:</label><input type="text" name="yt_link" value="{{ yt_link }}">
        <label>यशवंतांचे फोटो लिंक:</label><input type="text" name="toppers_link" value="{{ toppers_link }}">
        <button type="submit" class="btn">💾 बदल सेव्ह करा</button>
    </form>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- FLASK MAIN ROUTES -----------------

@app.route('/')
def home_tests_list():
    is_admin = session.get('admin_logged', False)
    ref_phone = request.args.get('ref', '').strip()
    visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()

    if ref_phone and re.match(r'^[6-9]\d{9}$', ref_phone):
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM referral_clicks WHERE referrer_phone=%s AND visitor_ip=%s", (ref_phone, visitor_ip))
                already_clicked = cur.fetchone()
                if not already_clicked:
                    c_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                    cur.execute("INSERT INTO referral_clicks (referrer_phone, visitor_ip, clicked_at) VALUES (%s, %s, %s)", (ref_phone, visitor_ip, c_time))
                    cur.execute("SELECT COUNT(DISTINCT visitor_ip) as total_clicks FROM referral_clicks WHERE referrer_phone=%s", (ref_phone,))
                    count_row = cur.fetchone()
                    if count_row and count_row['total_clicks'] >= 3:
                        cur.execute("""
                            INSERT INTO shared_free_passes (phone, unlocked_until_test, created_at)
                            VALUES (%s, 5, %s)
                            ON CONFLICT (phone) DO UPDATE SET unlocked_until_test=5
                        """, (ref_phone, c_time))
                    conn.commit()

    now_time = datetime.now()
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE status='Active' ORDER BY id ASC")
            raw_tests = cur.fetchall()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_pdf'")
            r_row = cur.fetchone()
            recruitment_pdf = r_row['setting_value'] if r_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_pdf'")
            e_row = cur.fetchone()
            eligibility_pdf = e_row['setting_value'] if e_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='tab_order'")
            to_row = cur.fetchone()
            tab_order_str = to_row['setting_value'] if to_row else 'all,live,paid,free,rapid,battle,docs'

            # थेट डेटाबेसमधून रिअल जिल्हा मुकाबला गणना
            cur.execute("""
                SELECT district, COUNT(id) as total_students, ROUND(AVG(score)::numeric, 1) as avg_score
                FROM mock_test_leads
                WHERE district IS NOT NULL AND district != ''
                GROUP BY district
                ORDER BY avg_score DESC, total_students DESC
                LIMIT 15
            """)
            live_district_battles = cur.fetchall()

    ordered_tabs = [t.strip() for t in tab_order_str.split(',') if t.strip()]

    tests = []
    for t in raw_tests:
        t_dict = dict(t)
        if t_dict.get('publish_at') and t_dict['publish_at'] > now_time:
            t_dict['is_locked'] = True
        else:
            t_dict['is_locked'] = False
        tests.append(t_dict)
            
    return render_template_string(
        HOME_TEMPLATE,
        tests=tests,
        recruitment_pdf=recruitment_pdf,
        eligibility_pdf=eligibility_pdf,
        is_admin=is_admin,
        ordered_tabs=ordered_tabs,
        live_district_battles=live_district_battles
    )

@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template_string(TERMS_TEMPLATE)

@app.route('/api/check_referral_status/<phone>')
def check_referral_status(phone):
    phone = phone.strip()
    if not re.match(r'^[6-9]\d{9}$', phone):
        return jsonify({'clicks': 0, 'unlocked': False})
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(DISTINCT visitor_ip) as total_clicks FROM referral_clicks WHERE referrer_phone=%s", (phone,))
            row = cur.fetchone()
            clicks = row['total_clicks'] if row else 0
            cur.execute("SELECT unlocked_until_test FROM shared_free_passes WHERE phone=%s", (phone,))
            pass_row = cur.fetchone()
            unlocked = True if (pass_row and pass_row['unlocked_until_test'] >= 5) else False
            
    return jsonify({'clicks': min(clicks, 3), 'unlocked': unlocked})

@app.route('/verify_share_phone/<int:test_id>', methods=['POST'])
def verify_share_phone(test_id):
    phone = request.form.get('verify_phone', '').strip()
    if re.match(r'^[6-9]\d{9}$', phone):
        session['user_phone'] = phone
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT unlocked_until_test FROM shared_free_passes WHERE phone=%s", (phone,))
                pass_row = cur.fetchone()
                if pass_row and test_id <= pass_row['unlocked_until_test']:
                    return redirect(f"/take_test/{test_id}")
    return "<h3 style='color:red; text-align:center; padding:30px;'>⚠️ या नंबरवर ३ मित्रांच्या व्हिजिट्स पूर्ण झालेल्या नाहीत किंवा तुम्ही टेस्ट ६ च्या पुढील टेस्ट उघडत आहात!</h3>", 403

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    token = request.args.get('token', '')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='qr_code_url'")
            qr_row = cur.fetchone()
            qr_url = qr_row['setting_value'] if qr_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='upi_mobile'")
            upi_row = cur.fetchone()
            upi_mobile = upi_row['setting_value'] if upi_row else '9921111960'

    if not test or test['status'] != 'Active': return "Test not found or closed", 404

    # शेड्युलिंग लॉक तपासणी
    if test.get('publish_at') and test['publish_at'] > datetime.now():
        return "<h3 style='color:#ef4444; text-align:center; padding:40px;'>⏳ ही टेस्ट दररोज सकाळी १०:०० वाजता अनलॉक होईल! कृपया वेळेवर भेट द्या.</h3>", 403

    if test['test_type'] == 'Free':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

    user_phone = session.get('user_phone', '')
    is_share_unlocked = False
    if user_phone and test_id <= 5:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT unlocked_until_test FROM shared_free_passes WHERE phone=%s", (user_phone,))
                pass_row = cur.fetchone()
                if pass_row and test_id <= pass_row['unlocked_until_test']:
                    is_share_unlocked = True

    if is_share_unlocked:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

    if token:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM mock_test_leads WHERE test_id=%s AND access_token=%s AND payment_status='Approved'", (test_id, token))
                lead = cur.fetchone()
        if lead and lead['token_expires_at']:
            expires_at = datetime.strptime(lead['token_expires_at'], "%Y-%m-%d %H:%M:%S")
            if datetime.now() <= expires_at:
                with get_db() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                        questions = cur.fetchall()
                return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

    return render_template_string(ACCESS_CHECK_TEMPLATE, test=test, qr_url=qr_url, upi_mobile=upi_mobile)

# --- RAZORPAY ORDERS & VERIFY ---
@app.route('/create_razorpay_order/<int:test_id>', methods=['POST'])
def create_razorpay_order(test_id):
    client, key_id = get_razorpay_client()
    if not client or not key_id:
        return jsonify({"error": "Razorpay Keys सेट केलेल्या नाहीत!"}), 400

    try:
        order = client.order.create({
            "amount": 9900,
            "currency": "INR",
            "receipt": f"rcpt_test_{test_id}_{int(datetime.now().timestamp())}",
            "payment_capture": 1
        })
        return jsonify({"order_id": order['id'], "amount": 9900, "key_id": key_id})
    except Exception as e:
        return jsonify({"error": f"Razorpay एरर: {str(e)}"}), 500

@app.route('/verify_razorpay_payment')
def verify_razorpay_payment():
    order_id = request.args.get('order_id')
    payment_id = request.args.get('payment_id')
    test_id = request.args.get('test_id')
    token = secrets.token_hex(8)
    expires = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, access_token, token_expires_at, razorpay_order_id, razorpay_payment_id, test_name)
                VALUES (%s, %s, 'Razorpay Student', 'Maharashtra', '9999999999', 'Approved', %s, %s, %s, %s, 'Paid Pack')
            """, (test_id, date.today().strftime("%Y-%m-%d"), token, expires, order_id, payment_id))
            conn.commit()

    return redirect(f"/take_test/{test_id}?token={token}")

@app.route('/request_paid_test/<int:test_id>', methods=['POST'])
def request_paid_test(test_id):
    name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()
    t_date = date.today().strftime("%Y-%m-%d")

    if not re.match(r'^[6-9]\d{9}$', phone):
        return "<h3 style='color:red; text-align:center;'>⚠️ चुकीचा मोबाईल नंबर!</h3>", 400

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            if not test: return "Test not found", 404

            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, score, total_marks, test_name)
                VALUES (%s, %s, %s, %s, %s, 'Pending', 0, 0, %s)
            """, (test_id, t_date, name, district, phone, test['test_title']))
            conn.commit()

    return "<h3 style='color:green; text-align:center; padding:40px;'>✅ मॅन्युअल पडताळणी प्रलंबित! २४ तासांत लिंक WhatsApp वर मिळेल.</h3>"

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    student_name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()

    if not re.match(r'^[6-9]\d{9}$', phone):
        return "⚠️ अवैध मोबाईल नंबर!", 400

    session['user_phone'] = phone

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT id, correct FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()

    if not test: return "Test not found", 404

    score = 0
    total = len(questions)
    user_answers = {}

    for q in questions:
        ans = request.form.get(f"q_{q['id']}", "")
        user_answers[str(q['id'])] = ans
        if ans == q['correct']:
            score += 1

    t_date = date.today().strftime("%Y-%m-%d")
    ans_json_str = json.dumps(user_answers)
    result_token = secrets.token_hex(10)

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, whatsapp_verified, payment_status, score, total_marks, test_name, answers_json, access_token)
                VALUES (%s, %s, %s, %s, %s, 1, 'Approved', %s, %s, %s, %s, %s) RETURNING id
            """, (test_id, t_date, student_name, district, phone, score, total, test['test_title'], ans_json_str, result_token))
            
            cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s", (test_id, score))
            state_rank = cur.fetchone()['higher'] + 1
            
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            i_row = cur.fetchone()
            insta_link = i_row['setting_value'] if i_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            y_row = cur.fetchone()
            yt_link = y_row['setting_value'] if y_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            tp_row = cur.fetchone()
            toppers_link = tp_row['setting_value'] if tp_row else ''
            
            # व्हॉट्सॲप ग्रुप बॅकअप व ऑटोमॅटिक स्विचिंग लॉजिक
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='wa_group_link'")
            wg_row = cur.fetchone()
            wa_group_link = wg_row['setting_value'] if wg_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='wa_group_link_2'")
            wg2_row = cur.fetchone()
            wa_group_link_2 = wg2_row['setting_value'] if wg2_row else ''

            cur.execute("SELECT COUNT(*) as cnt FROM mock_test_leads")
            total_leads_count = cur.fetchone()['cnt']
            # जर विद्यार्थी संख्या १००० पेक्षा जास्त असेल आणि दुसरा ग्रुप दिलेला असेल तर ग्रुप २ वर पाठवा
            wa_active_link = wa_group_link_2 if (total_leads_count >= 1000 and wa_group_link_2) else wa_group_link

            conn.commit()

    main_portal_url = request.host_url.rstrip('/')
    result_url = main_portal_url + url_for('detailed_answers', token=result_token)
    student_tracking_url = f"{main_portal_url}/?ref={phone}"
    
    # थेट मुख्य पानावर नेणारा अचूक चॅलेंज मेसेज
    ego_msg = f"🏆 *महाराष्ट्र पोलीस भरती ओपन चॅलेंज* 🏆\\nमैदानावर खाकीची जिद्द दाखवली, आता लेखी परीक्षेत तुमची तयारी किती आहे ते सिद्ध करा!\\nमला {total} पैकी {score} गुण मिळाले आणि ऑल महाराष्ट्र रँक #{state_rank} आलाय!\\n🔥 तुझ्यासोबत तुझा मित्रही भरती झाला पाहिजे! त्यालाही ही लिंक पाठव आणि उद्याची रॅपिड टेस्ट मिळव!\\n👉 मोफत टेस्ट सोडवण्यासाठी येथे क्लिक करा:\\n{student_tracking_url}"
    ego_share_encoded = urllib.parse.quote(ego_msg)

    return render_template_string(
        RESULT_SUMMARY_TEMPLATE,
        lead={'student_name': student_name, 'district': district, 'phone': phone, 'test_name': test['test_title'], 'score': score, 'total_marks': total, 'access_token': result_token},
        state_rank=state_rank,
        result_url=result_url,
        main_portal_url=main_portal_url,
        ego_share_encoded=ego_share_encoded,
        test_category=test.get('category', 'free'),
        insta_link=insta_link,
        yt_link=yt_link,
        toppers_link=toppers_link,
        wa_active_link=wa_active_link
    )

# रॅपिड टेस्टसाठी ओरिजनल WhatsApp नंबर पडताळणी राऊट
@app.route('/verify_rapid_key/<token>', methods=['POST'])
def verify_rapid_key(token):
    phone = request.form.get('verify_phone', '').strip()
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT phone FROM mock_test_leads WHERE access_token=%s", (token,))
            lead = cur.fetchone()
            if lead and lead['phone'] == phone:
                return redirect(url_for('detailed_answers', token=token))
    return "<h3 style='color:red; text-align:center; padding:30px;'>⚠️ चुकीचा WhatsApp नंबर! कृपया टेस्ट सबमिट करताना वापरलेला मूळ नंबर टाका.</h3>", 403

@app.route('/detailed_answers/<token>')
def detailed_answers(token):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE access_token=%s", (token,))
            lead = cur.fetchone()
            if not lead: return "Result not found", 404

            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (lead['test_id'],))
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
            'user_ans': u_ans,
            'correct_ans': q['correct'],
            'is_correct': (u_ans == q['correct']),
            'explanation': q['explanation']
        })

    return render_template_string(DETAILED_KEY_TEMPLATE, lead=lead, evaluated_questions=evaluated_questions)

@app.route('/submit_feedback/<int:lead_id>', methods=['POST'])
def submit_feedback(lead_id):
    fb_text = request.form.get('feedback_text', '').strip()
    if fb_text:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT student_name, phone, access_token FROM mock_test_leads WHERE id=%s", (lead_id,))
                lead = cur.fetchone()
                if lead:
                    c_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                    cur.execute("""
                        INSERT INTO student_feedbacks (lead_id, student_name, phone, feedback_text, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (lead_id, lead['student_name'], lead['phone'], fb_text, c_date))
                    conn.commit()
                    return redirect(f"/detailed_answers/{lead['access_token']}")
    return redirect('/')

# ----------------- ADMIN CONTROLS -----------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('admin_pass')
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_pass'")
                row = cur.fetchone()
                db_pass = row['setting_value'] if row else 'shreeguru2026'

        if password == db_pass:
            session['admin_logged'] = True
            return redirect('/admin/dashboard')
        else:
            error = "चुकीचा पासवर्ड! कृपया पुन्हा प्रयत्न करा."
            
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged', None)
    return redirect('/admin/login')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged'): return redirect('/admin/login')

    active_tab = request.args.get('tab', 'leads')
    filter_test_id = request.args.get('filter_test_id', '')
    lead_dist = request.args.get('lead_dist', '')
    lead_test_id = request.args.get('lead_test_id', '')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM mock_test_leads WHERE 1=1"
            params = []
            if lead_dist:
                query += " AND district = %s"
                params.append(lead_dist)
            if lead_test_id:
                query += " AND test_id = %s"
                params.append(lead_test_id)
            query += " ORDER BY id DESC"
            cur.execute(query, tuple(params))
            leads = cur.fetchall()

            cur.execute("SELECT DISTINCT district FROM mock_test_leads WHERE district != ''")
            all_districts = [r['district'] for r in cur.fetchall()]

            cur.execute("SELECT * FROM test_papers ORDER BY id ASC")
            tests = cur.fetchall()

            if filter_test_id:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id DESC", (filter_test_id,))
            else:
                cur.execute("SELECT * FROM questions ORDER BY id DESC")
            all_questions = cur.fetchall()

            cur.execute("SELECT * FROM mock_test_leads WHERE payment_status != 'Not Required' ORDER BY id DESC")
            payments = cur.fetchall()

            cur.execute("SELECT * FROM mock_test_leads ORDER BY score DESC, id ASC LIMIT 100")
            all_leads_sorted = cur.fetchall()

            cur.execute("SELECT * FROM student_feedbacks ORDER BY id DESC")
            feedbacks = cur.fetchall()
            cur.execute("SELECT * FROM special_unlimited_attempts ORDER BY id DESC")
            unlimited_list = cur.fetchall()
            cur.execute("SELECT * FROM special_free_pass ORDER BY id DESC")
            free_pass_list = cur.fetchall()

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='qr_code_url'")
            qr_url = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='upi_mobile'")
            upi_mobile = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='razorpay_key_id'")
            r_kid = cur.fetchone()
            razorpay_key_id = r_kid['setting_value'] if r_kid else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='razorpay_key_secret'")
            r_ksec = cur.fetchone()
            razorpay_key_secret = r_ksec['setting_value'] if r_ksec else ''

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            toppers_link = cur.fetchone()['setting_value']
            
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='wa_group_link'")
            wg_val = cur.fetchone()
            wa_group_link = wg_val['setting_value'] if wg_val else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='wa_group_link_2'")
            wg2_val = cur.fetchone()
            wa_group_link_2 = wg2_val['setting_value'] if wg2_val else ''

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='tab_order'")
            t_order_val = cur.fetchone()
            tab_order = t_order_val['setting_value'] if t_order_val else 'all,live,paid,free,rapid,battle,docs'

    top_leads = [(idx, l) for idx, l in enumerate(all_leads_sorted, start=1)]

    return render_template_string(
        ADMIN_TEMPLATE,
        active_tab=active_tab,
        leads=leads,
        tests=tests,
        all_questions=all_questions,
        payments=payments,
        top_leads=top_leads,
        feedbacks=feedbacks,
        unlimited_list=unlimited_list,
        free_pass_list=free_pass_list,
        all_districts=all_districts,
        lead_dist=lead_dist,
        lead_test_id=lead_test_id,
        filter_test_id=filter_test_id,
        qr_url=qr_url,
        upi_mobile=upi_mobile,
        razorpay_key_id=razorpay_key_id,
        razorpay_key_secret=razorpay_key_secret,
        insta_link=insta_link,
        yt_link=yt_link,
        toppers_link=toppers_link,
        wa_group_link=wa_group_link,
        wa_group_link_2=wa_group_link_2,
        tab_order=tab_order
    )

# --- १-क्लिक बल्क शेड्युलिंग राऊट (50 Tests + 50 Rapid + Demo) ---
@app.route('/admin/bulk_schedule_all', methods=['POST'])
def admin_bulk_schedule_all():
    if not session.get('admin_logged'): return redirect('/admin/login')

    today = date.today()
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # १. मोफत डेमो टेस्ट (त्वरित खुली)
            cur.execute("""
                INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status, category, publish_at)
                VALUES ('🟢 पोलीस भरती मोफत डेमो टेस्ट पेपर', 'Free', 0, 60, 'Active', 'free', NULL)
            """)

            # २. ५० सशुल्क १००-गुणांचे संच (पहिले ३ आज सुरू, उरलेले दररोज सकाळी १०:०० वाजता)
            for i in range(1, 51):
                if i <= 3:
                    publish_time = None
                else:
                    target_day = today + timedelta(days=(i - 3))
                    publish_time = datetime(target_day.year, target_day.month, target_day.day, 10, 0, 0)
                cur.execute("""
                    INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status, category, publish_at)
                    VALUES (%s, 'Paid', 99, 60, 'Active', 'paid', %s)
                """, (f'🎯 महाराष्ट्र पोलीस अतिसंभाव्य टेस्ट पेपर #{i}', publish_time))

            # ३. ५० रॅपिड फायर टेस्ट्स (दररोज सकाळी १०:०० वाजता एक-एक)
            for j in range(1, 51):
                target_day = today + timedelta(days=(j - 1))
                publish_time = datetime(target_day.year, target_day.month, target_day.day, 10, 0, 0)
                cur.execute("""
                    INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status, category, publish_at)
                    VALUES (%s, 'Free', 0, 15, 'Active', 'rapid', %s)
                """, (f'⚡ दैनिक रॅपिड फायर टेस्ट #{j} (सकाळी १०:००)', publish_time))

            conn.commit()

    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/update_razorpay_settings', methods=['POST'])
def admin_update_razorpay_settings():
    if not session.get('admin_logged'): return redirect('/admin/login')
    kid = request.form.get('razorpay_key_id', '').strip()
    ksec = request.form.get('razorpay_key_secret', '').strip()

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO academy_settings (setting_key, setting_value) VALUES ('razorpay_key_id', %s)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value
            """, (kid,))
            cur.execute("""
                INSERT INTO academy_settings (setting_key, setting_value) VALUES ('razorpay_key_secret', %s)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value
            """, (ksec,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/update_payment_settings', methods=['POST'])
def admin_update_payment_settings():
    if not session.get('admin_logged'): return redirect('/admin/login')
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
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if final_qr_url:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='qr_code_url'", (final_qr_url,))
            if new_mobile:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='upi_mobile'", (new_mobile,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/add_question', methods=['POST'])
def admin_add_question():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    question = request.form.get('question', '').strip()
    oa = request.form.get('opt_a', '').strip()
    ob = request.form.get('opt_b', '').strip()
    oc = request.form.get('opt_c', '').strip()
    od = request.form.get('opt_d', '').strip()
    correct = request.form.get('correct', 'A').strip().upper()
    explanation = request.form.get('explanation', '').strip()

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (test_id, question, oa, ob, oc, od, correct, explanation))
            conn.commit()
    return redirect(f'/admin/dashboard?tab=questions&filter_test_id={test_id}')

@app.route('/admin/edit_question/<int:q_id>', methods=['GET', 'POST'])
def admin_edit_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if request.method == 'POST':
                q_text = request.form.get('question', '').strip()
                oa = request.form.get('opt_a', '').strip()
                ob = request.form.get('opt_b', '').strip()
                oc = request.form.get('opt_c', '').strip()
                od = request.form.get('opt_d', '').strip()
                correct = request.form.get('correct', 'A').strip().upper()
                explanation = request.form.get('explanation', '').strip()

                cur.execute("""
                    UPDATE questions
                    SET question=%s, opt_a=%s, opt_b=%s, opt_c=%s, opt_d=%s, correct=%s, explanation=%s
                    WHERE id=%s
                """, (q_text, oa, ob, oc, od, correct, explanation, q_id))
                conn.commit()

                cur.execute("SELECT test_id FROM questions WHERE id=%s", (q_id,))
                q_row = cur.fetchone()
                test_id = q_row['test_id'] if q_row else ''
                return redirect(f'/admin/dashboard?tab=questions&filter_test_id={test_id}')

            cur.execute("SELECT * FROM questions WHERE id=%s", (q_id,))
            question = cur.fetchone()

    if not question: return "प्रश्न सापडला नाही!", 404
    return render_template_string(EDIT_QUESTION_TEMPLATE, q=question)

@app.route('/admin/bulk_questions', methods=['POST'])
def admin_bulk_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    bulk_data = request.form.get('bulk_questions_text', '').strip()

    lines = [l.strip() for l in bulk_data.split('\n') if l.strip()]
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 6:
                    q = parts[0]
                    oa, ob, oc, od = parts[1], parts[2], parts[3], parts[4]
                    corr = parts[5].upper()
                    exp = parts[6] if len(parts) > 6 else ''
                    cur.execute("""
                        INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (test_id, q, oa, ob, oc, od, corr, exp))
            conn.commit()

    return redirect(f'/admin/dashboard?tab=questions&filter_test_id={test_id}')

@app.route('/admin/upload_csv_questions', methods=['POST'])
def admin_upload_csv_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    file = request.files.get('csv_file')

    if not file or not file.filename.endswith(('.csv', '.txt')):
        return "कृपया वैध CSV फाईल अपलोड करा!", 400

    stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
    csv_reader = csv.reader(stream)

    questions_to_insert = []
    for row in csv_reader:
        if len(row) >= 6:
            q = row[0].strip()
            oa, ob, oc, od = row[1].strip(), row[2].strip(), row[3].strip(), row[4].strip()
            corr = row[5].strip().upper()
            exp = row[6].strip() if len(row) > 6 else ''
            if q and corr in ['A', 'B', 'C', 'D']:
                questions_to_insert.append((test_id, q, oa, ob, oc, od, corr, exp))

    if questions_to_insert:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.executemany("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, questions_to_insert)
                conn.commit()

    return redirect(f'/admin/dashboard?tab=questions&filter_test_id={test_id}')

@app.route('/admin/delete_question/<int:q_id>')
def admin_delete_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT test_id FROM questions WHERE id=%s", (q_id,))
            q_row = cur.fetchone()
            t_id = q_row['test_id'] if q_row else ''
            cur.execute("DELETE FROM questions WHERE id=%s", (q_id,))
            conn.commit()
    return redirect(f'/admin/dashboard?tab=questions&filter_test_id={t_id}')

@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    category = request.form.get('category', 'paid')
    ttype = request.form.get('test_type', 'Paid')
    fee = float(request.form.get('test_fee', 99) or 0)
    duration = int(request.form.get('duration_minutes', 60) or 60)
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("""
                    INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status, category) 
                    VALUES (%s, %s, %s, %s, 'Active', %s)
                """, (title, ttype, fee, duration, category))
                conn.commit()
            except Exception:
                conn.rollback()
                try:
                    cur.execute("ALTER TABLE test_papers ADD COLUMN category TEXT DEFAULT 'free';")
                    cur.execute("""
                        INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status, category) 
                        VALUES (%s, %s, %s, %s, 'Active', %s)
                    """, (title, ttype, fee, duration, category))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    cur.execute("INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status) VALUES (%s, %s, %s, %s, 'Active')", (title, ttype, fee, duration))
                    conn.commit()

    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/update_test/<int:test_id>', methods=['POST'])
def admin_update_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    category = request.form.get('category', 'paid')
    ttype = request.form.get('test_type', 'Paid')
    fee = float(request.form.get('test_fee', 0) or 0)
    duration = int(request.form.get('duration_minutes', 60) or 60)
    status = request.form.get('status', 'Active')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("""
                    UPDATE test_papers 
                    SET test_title=%s, test_type=%s, test_fee=%s, duration_minutes=%s, status=%s, category=%s 
                    WHERE id=%s
                """, (title, ttype, fee, duration, status, category, test_id))
                conn.commit()
            except Exception:
                conn.rollback()
                cur.execute("UPDATE test_papers SET test_title=%s, test_type=%s, test_fee=%s, duration_minutes=%s, status=%s WHERE id=%s", (title, ttype, fee, duration, status, test_id))
                conn.commit()

    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM questions WHERE test_id=%s", (test_id,))
            cur.execute("DELETE FROM test_papers WHERE id=%s", (test_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/print_test/<int:test_id>')
def admin_print_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()

    html = f'''<!DOCTYPE html><html lang="mr"><head><meta charset="UTF-8"><title>{test['test_title']} - Print</title></head>
    <body style="font-family:sans-serif; padding:30px; color:#000;">
        <h2 style="text-align:center;">राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</h2>
        <h3 style="text-align:center;">{test['test_title']}</h3>
        <p style="text-align:center;"><b>वेळ:</b> {test['duration_minutes']} मिनिटे | <b>एकूण प्रश्न:</b> {len(questions)}</p>
        <hr>
        <ol>{ "".join([f"<li style='margin-bottom:15px;'><b>{q['question']}</b><br>A) {q['opt_a']}&nbsp;&nbsp;&nbsp;B) {q['opt_b']}&nbsp;&nbsp;&nbsp;C) {q['opt_c']}&nbsp;&nbsp;&nbsp;D) {q['opt_d']}<br><small style='color:green;'>अचूक उत्तर: {q['correct']} | स्पष्टीकरण: {q['explanation']}</small></li>" for q in questions]) }</ol>
        <script>window.print();</script>
    </body></html>'''
    return render_template_string(html)

@app.route('/admin/approve_payment/<int:lead_id>', methods=['POST'])
def admin_approve_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    token = secrets.token_hex(8)
    expires = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

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
    if not session.get('admin_logged'): return redirect('/admin/login')
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
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM special_unlimited_attempts WHERE id=%s", (uid,))
            conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/add_special_free_pass', methods=['POST'])
def add_special_free_pass():
    if not session.get('admin_logged'): return redirect('/admin/login')
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
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM special_free_pass WHERE id=%s", (fid,))
            conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/update_pdf_docs', methods=['POST'])
def admin_update_pdf_docs():
    if not session.get('admin_logged'): return redirect('/admin/login')
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
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_pass = request.form.get('new_password')
    tab_order = request.form.get('tab_order', 'all,live,paid,free,rapid,battle,docs').strip()
    wa_group = request.form.get('wa_group_link', '').strip()
    wa_group_2 = request.form.get('wa_group_link_2', '').strip()
    insta = request.form.get('insta_link', '')
    yt = request.form.get('yt_link', '')
    top = request.form.get('toppers_link', '')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if new_pass:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
            cur.execute("""
                INSERT INTO academy_settings (setting_key, setting_value) VALUES ('tab_order', %s)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value
            """, (tab_order,))
            cur.execute("""
                INSERT INTO academy_settings (setting_key, setting_value) VALUES ('wa_group_link', %s)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value
            """, (wa_group,))
            cur.execute("""
                INSERT INTO academy_settings (setting_key, setting_value) VALUES ('wa_group_link_2', %s)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value
            """, (wa_group_2,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='insta_link'", (insta,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='yt_link'", (yt,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='toppers_link'", (top,))
            conn.commit()
    return redirect('/admin/dashboard?tab=settings')

@app.route('/admin/delete_lead/<int:lead_id>')
def admin_delete_lead(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM mock_test_leads WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/delete_payment/<int:lead_id>')
def admin_delete_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM mock_test_leads WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

