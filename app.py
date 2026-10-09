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
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "maha_police_master_platform_2026_safe_key")

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
                    publish_at TIMESTAMP DEFAULT NULL,
                    sequence_order INTEGER DEFAULT 1,
                    is_deleted INTEGER DEFAULT 0
                )''')

                # Column safety checks & additions
                for col_query in [
                    "ALTER TABLE test_papers ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'free';",
                    "ALTER TABLE test_papers ADD COLUMN IF NOT EXISTS publish_at TIMESTAMP DEFAULT NULL;",
                    "ALTER TABLE test_papers ADD COLUMN IF NOT EXISTS sequence_order INTEGER DEFAULT 1;",
                    "ALTER TABLE test_papers ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0;"
                ]:
                    try:
                        cur.execute(col_query)
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
                    explanation TEXT DEFAULT '',
                    is_deleted INTEGER DEFAULT 0
                )''')
                try:
                    cur.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0;")
                    conn.commit()
                except Exception:
                    conn.rollback()

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
                    razorpay_payment_id TEXT DEFAULT '',
                    referred_by_phone TEXT DEFAULT '',
                    is_deleted INTEGER DEFAULT 0
                )''')
                try:
                    cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS referred_by_phone TEXT DEFAULT '';")
                    cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0;")
                    conn.commit()
                except Exception:
                    conn.rollback()

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

                cur.execute('''CREATE TABLE IF NOT EXISTS academy_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )''')

                defaults = [
                    ('site_status', 'active'),
                    ('helpdesk_phone', '9921111960'),
                    ('helpdesk_address', 'श्रीगुरु करिअर अकॅडमी, आडूर, कोल्हापूर - कळे मेन रोड'),
                    ('qr_code_url', 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=PoliceBhartiTestPayment'),
                    ('upi_mobile', '9921111960'),
                    ('admin_pass', 'admin2026'),
                    ('admin_phone', '9921111960'),
                    ('insta_link', ''),
                    ('yt_link', ''),
                    ('toppers_link', ''),
                    ('wa_groups_multiline', 'https://chat.whatsapp.com/sampleGroup1'),
                    ('home_tab_order', 'all,live,paid,free,rapid,battle,docs,helpdesk'),
                    ('admin_tab_order', 'leads,payments,special,questions,launch,leaderboard,feedback,notices,trash,settings'),
                    ('recruitment_pdf', ''),
                    ('eligibility_pdf', ''),
                    ('razorpay_key_id', ''),
                    ('razorpay_key_secret', '')
                ]
                for k, v in defaults:
                    cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO NOTHING", (k, v))

                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_test_score ON mock_test_leads(test_id, score);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON mock_test_leads(phone);")

                cur.execute('SELECT COUNT(*) as count FROM test_papers WHERE is_deleted=0')
                if cur.fetchone()['count'] == 0:
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active', 'free', 1)")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) VALUES (2, '🔴 मिशन खाकी रविवार थेट महासंग्राम #१', 'Free', 0, 60, 'Active', 'live', 1)")

                conn.commit()
    except Exception as e:
        print(f"Init DB Error: {e}")

init_master_db()

# ----------------- TEMPLATES SECTION -----------------

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
    <h2>पोर्टलचे तांत्रिक काम सुरू आहे!</h2>
    <p>विद्यार्थ्यांना अधिक चांगला व गतिमान अनुभव देण्यासाठी पोर्टलवर नियोजित तांत्रिक सुधारणा सुरू आहेत.</p>
    <p style="color:#34d399; font-weight:bold;">लवकरच ही वेबसाईट पूर्ण क्षमतेने पूर्ववत सुरू होईल. खाकीच्या तयारीसाठी थोडा वेळ संयम ठेवा! ⚔️</p>
</div>
</body>
</html>'''

HOME_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>महाराष्ट्र पोलीस भरती २०२६ - सराव प्रश्नसंच ऑनलाईन प्लॅटफॉर्म</title>
    <link href="https://fonts.googleapis.com/css2?family=Baloo+Bhaina+2:wght@500;700;800&family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', 'Baloo Bhaina 2', sans-serif; transition: all 0.2s ease; }
        body { margin: 0; background: #0f172a; color: #f8fafc; padding: 12px; }
        .top-bar { max-width: 950px; margin: 0 auto 15px; display: flex; justify-content: space-between; align-items: center; background: #1e293b; padding: 12px 18px; border-radius: 12px; border: 1px solid #334155; }
        .badge-live { background: #ef4444; color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .box { max-width: 950px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 25px 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); border-top: 5px solid #10b981; }
        .hero-banner { text-align: center; margin-bottom: 22px; }
        .hero-banner h1 { margin: 0 0 8px; color: #34d399; font-size: 27px; font-weight: 800; font-family: 'Baloo Bhaina 2', cursive; }
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
        .btn-locked { background: #334155; color: #94a3b8; padding: 10px 18px; border-radius: 8px; font-weight: bold; font-size: 12.5px; cursor: not-allowed; display: inline-block; }
        .section-box { display: none; background: #0f172a; border: 1.5px solid #334155; border-radius: 12px; padding: 22px; text-align: center; }
        .rank-table { width: 100%; border-collapse: collapse; margin-top: 15px; text-align: left; font-size: 13.5px; }
        .rank-table th, .rank-table td { padding: 10px 12px; border-bottom: 1px solid #334155; }
        .rank-table th { color: #34d399; }
        .doc-link { display: inline-block; background: #1e293b; color: #38bdf8; border: 1.5px solid #0284c7; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 13px; margin: 6px; }
        .footer { text-align: center; font-size: 12px; color: #64748b; margin-top: 25px; border-top: 1px solid #334155; padding-top: 15px; }
        .loading-modal { display: none; position: fixed; inset: 0; background: rgba(11,19,41,0.94); z-index: 9999; justify-content: center; align-items: center; padding: 15px; }
        .modal-content { background: #162036; border: 2px solid #10b981; border-radius: 16px; padding: 30px 20px; max-width: 480px; text-align: center; box-shadow: 0 15px 40px rgba(0,0,0,0.6); }
    </style>
    <script>
        function filterTab(category, btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            document.getElementById('testsContainer').style.display = 'none';
            document.getElementById('battleContainer').style.display = 'none';
            document.getElementById('docsContainer').style.display = 'none';
            document.getElementById('helpdeskContainer').style.display = 'none';

            if (category === 'battle') {
                document.getElementById('battleContainer').style.display = 'block';
            } else if (category === 'docs') {
                document.getElementById('docsContainer').style.display = 'block';
            } else if (category === 'helpdesk') {
                document.getElementById('helpdeskContainer').style.display = 'block';
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
<div id="loadingNoticeModal" class="loading-modal">
    <div class="modal-content">
        <h3 style="color:#34d399; margin:0 0 10px; font-size:20px;">🛡️ सुरक्षित परीक्षा कक्ष लोड होत आहे...</h3>
        <p style="color:#cbd5e1; font-size:14px; line-height:1.6; margin:0 0 20px;">
            ⏳ टेस्ट उघडण्यासाठी थोडा वेळ लागू शकतो, <b>पण घाबरण्याची काही गरज नाही आपण सुरक्षित आहात!</b> खाकीच्या अभ्यासासाठी सज्ज व्हा!
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
    <div style="font-size:12px; color:#94a3b8;">ऑनलाईन सराव व्यासपीठ</div>
</div>

<div class="box">
    <div class="hero-banner">
        <h1>⚔️ महाराष्ट्र पोलीस भरती अतिसंभाव्य टेस्ट पोर्टल</h1>
        <div class="quote-box">
            🔥 "मैदानावर खाकीची जिद्द दाखवली, आता लेखी परीक्षेत तुमची तयारी किती आहे ते सिद्ध करा!" 🌟
        </div>
    </div>

    <div class="tabs-wrapper">
        {% for tab_key in ordered_tabs %}
            {% if tab_key == 'all' %}<button class="tab-btn active" onclick="filterTab('all', this)">🌐 सर्व संच</button>
            {% elif tab_key == 'live' %}<button class="tab-btn" onclick="filterTab('live', this)">🔴 मिशन खाकी महासंग्राम</button>
            {% elif tab_key == 'paid' %}<button class="tab-btn" onclick="filterTab('paid', this)">🎯 अतिसंभाव्य १०० गुण संच (₹९९)</button>
            {% elif tab_key == 'free' %}<button class="tab-btn" onclick="filterTab('free', this)">🟢 मोफत टेस्ट्स</button>
            {% elif tab_key == 'rapid' %}<button class="tab-btn" onclick="filterTab('rapid', this)">⚡ २० गुण रॅपिड फायर</button>
            {% elif tab_key == 'battle' %}<button class="tab-btn" onclick="filterTab('battle', this)">⚔️ जिल्हा मुकाबला व रँक</button>
            {% elif tab_key == 'docs' %}<button class="tab-btn" onclick="filterTab('docs', this)">📄 भरती PDF व PYQ</button>
            {% elif tab_key == 'helpdesk' %}<button class="tab-btn" onclick="filterTab('helpdesk', this)">☎️ हेल्प डेस्क</button>
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
                    {% if t.is_locked and t.category == 'rapid' %}
                    <span style="font-size:12px; color:#fbbf24;">⏳ रोज सकाळी १०:०० वाजता अनलॉक होईल</span>
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
                <td>{{ dist.total_students }} विद्यार्थी</td>
                <td style="color:#34d399; font-weight:bold;">{{ dist.avg_score }} गुण</td>
            </tr>
            {% else %}
            <tr><td colspan="4" style="text-align:center; color:#94a3b8;">माहिती उपलब्ध नाही.</td></tr>
            {% endfor %}
        </table>
    </div>

    <div id="docsContainer" class="section-box">
        <h3 style="color:#38bdf8; margin-top:0;">📄 अधिकृत भरती कागदपत्रे व मागील प्रश्नपत्रिका</h3>
        {% if recruitment_pdf %}<a href="{{ recruitment_pdf }}" target="_blank" class="doc-link">📑 पोलीस भरती अधिकृत जाहिरात (PDF)</a>{% endif %}
        {% if eligibility_pdf %}<a href="{{ eligibility_pdf }}" target="_blank" class="doc-link">📋 शारीरिक व लेखी पात्रता निकष (PDF)</a>{% endif %}
    </div>

    <div id="helpdeskContainer" class="section-box">
        <h3 style="color:#34d399; margin-top:0;">☎️ मदत व मार्गदर्शक हेल्प डेस्क</h3>
        <p style="color:#cbd5e1; font-size:15px;">अकॅडमी पत्ता: <b>{{ helpdesk_address }}</b></p>
        <p style="color:#cbd5e1; font-size:15px;">हेल्पलाइन नंबर / WhatsApp: <a href="https://wa.me/91{{ helpdesk_phone }}" target="_blank" style="color:#25D366; font-weight:bold;">💬 {{ helpdesk_phone }}</a></p>
    </div>

    <div class="footer">
        <span>© 2026 महाराष्ट्र पोलीस भरती सराव प्रश्नसंच ऑनलाईन व्यासपीठ | </span>
        <a href="/terms-and-conditions" target="_blank" style="color:#38bdf8;">Terms & Conditions</a>
    </div>
</div>
</body>
</html>'''

TERMS_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms and Conditions - Practice Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; padding: 25px 15px; line-height: 1.6; }
        .terms-container { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 35px; box-shadow: 0 10px 25px rgba(0,0,0,0.06); border-top: 5px solid #059669; }
        h1 { color: #065f46; font-size: 24px; margin-top: 0; }
        .notice-box { background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; margin: 15px 0; color: #991b1b; font-size: 13.5px; }
        p { font-size: 13.5px; color: #475569; margin: 6px 0 12px; }
        .back-link { display: inline-block; margin-top: 20px; color: #0284c7; text-decoration: none; font-weight: 600; font-size: 13px; }
    </style>
</head>
<body>
<div class="terms-container">
    <h1>Terms and Conditions & Official Disclaimer</h1>
    <p>Last updated: October 2026</p>
    
    <div class="notice-box">
        <b>Government Non-Affiliation Disclaimer:</b><br>
        This portal is an independent private educational and self-assessment platform for competitive examination preparation and has no official affiliation, connection, or representation with any government department or official recruitment board.
    </div>

    <p>1. This portal is strictly an independent private educational platform designed for competitive exam practice and self-evaluation.</p>
    <p>2. Mock test scores and ranks generated here are solely for guidance and candidate performance analysis, not official selection guarantees.</p>
    <p>3. All practice test questions are curated for educational advancement purposes only.</p>

    <a href="/" class="back-link">⬅ Back to Practice Platform</a>
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
        .opt-label input[type="radio"] { margin-right: 12px; width: 18px; height: 18px; accent-color: #10b981; }
        .bottom-submission-card { background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(15,23,42,0.9)); border: 2px solid #10b981; border-radius: 14px; padding: 22px; margin-top: 30px; }
        .bottom-submission-card input { width: 100%; padding: 13px; background: #0f172a; border: 1.5px solid #334155; border-radius: 8px; margin-top: 5px; font-size: 14.5px; margin-bottom: 12px; color: white; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 15px; border: none; border-radius: 8px; font-size: 17px; font-weight: 800; cursor: pointer; }
    </style>
</head>
<body>
<div class="exam-header">
    <div>
        <h3 style="margin:0; font-size:17px; color:#34d399;">⚔️ {{ test.test_title }}</h3>
        <small id="progressText" style="color:#94a3b8; font-weight:600;">० / {{ questions|length }} सोडवले</small>
    </div>
    <div class="timer-box">⏳ <span id="time-left">00:00</span></div>
</div>
<div class="progress-bar-container"><div id="progressFill" class="progress-bar-fill"></div></div>
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
            <input type="text" name="student_name" id="s_name" placeholder="पूर्ण नाव" required>
            <input type="text" name="district" id="s_dist" placeholder="जिल्हा" required>
            <input type="tel" name="phone" id="s_phone" placeholder="10 अंकी WhatsApp नंबर" maxlength="10" required>
        </div>
        <button type="submit" id="submitBtn" class="btn-submit">🏆 टेस्ट सबमिट करा व निकाल पहा</button>
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
    <h2 style="color:#34d399; margin:0 0 10px;">⚙️ सुरक्षित ॲडमिन कक्ष</h2>
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
        function toggleSelectAllFeedbacks(master) {
            document.querySelectorAll('.fb-checkbox').forEach(cb => cb.checked = master.checked);
        }
        function generateAIQuestions() {
            const btn = document.getElementById('aiBtn');
            btn.innerText = '⏳ AI प्रश्न तयार करत आहे...';
            btn.disabled = true;
            fetch('/admin/ai_generate_mock', {method: 'POST'})
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const box = document.getElementById('bulkTextarea');
                    box.value = (box.value ? box.value + "\\n" : "") + data.questions_text;
                    alert("✅ AI द्वारे सराव प्रश्न यशस्वीपणे तयार केले गेले!");
                }
                btn.innerText = '🤖 AI द्वारे प्रश्न ऑटो-जनरेट करा';
                btn.disabled = false;
            });
        }
    </script>
</head>
<body>
<div class="container">
    <h2>⚙️ महाराष्ट्र पोलीस भरती सराव प्लॅटफॉर्म - ॲडमिन डॅशबोर्ड</h2>
    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
        <a href="/" style="font-weight:bold; color:#0284c7; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a>
        <a href="/admin/logout" style="font-weight:bold; color:#dc2626; text-decoration:none;">🚪 लॉगआऊट</a>
    </div>

    <div class="nav-tabs">
        {% for tab in ordered_admin_tabs %}
            {% if tab == 'leads' %}<a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 Leads</a>
            {% elif tab == 'payments' %}<a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 Payments</a>
            {% elif tab == 'special' %}<a href="/admin/dashboard?tab=special" class="{{ 'active' if active_tab == 'special' else '' }}">👑 Special</a>
            {% elif tab == 'questions' %}<a href="/admin/dashboard?tab=questions" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions & AI</a>
            {% elif tab == 'launch' %}<a href="/admin/dashboard?tab=launch" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Tests</a>
            {% elif tab == 'leaderboard' %}<a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard</a>
            {% elif tab == 'feedback' %}<a href="/admin/dashboard?tab=feedback" class="{{ 'active' if active_tab == 'feedback' else '' }}">💬 Feedback</a>
            {% elif tab == 'notices' %}<a href="/admin/dashboard?tab=notices" class="{{ 'active' if active_tab == 'notices' else '' }}">📢 PDFs</a>
            {% elif tab == 'trash' %}<a href="/admin/dashboard?tab=trash" class="{{ 'active' if active_tab == 'trash' else '' }}">🗑️ Recycle Bin</a>
            {% elif tab == 'settings' %}<a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Settings</a>
            {% endif %}
        {% endfor %}
    </div>

    {% if active_tab == 'leads' %}
    <h3>📱 विद्यार्थ्यांची लीड्स यादी</h3>
    <table>
        <tr><th>दिनांक</th><th>नाव</th><th>जिल्हा</th><th>WhatsApp</th><th>टेस्ट</th><th>गुण</th><th>कृती</th></tr>
        {% for l in leads %}
        <tr>
            <td>{{ l.test_date }}</td><td><b>{{ l.student_name }}</b></td><td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td><td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
            <td><a href="/admin/delete_lead/{{ l.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('रिसायकल बिनमध्ये टाकायचे का?');">🗑️</a></td>
        </tr>
        {% endfor %}
    </table>

    {% elif active_tab == 'payments' %}
    <h3>💰 पेमेंट व्यवस्थापन</h3>
    <table>
        <tr><th>नाव</th><th>मोबाईल</th><th>टेस्ट</th><th>स्थिती</th><th>कृती</th></tr>
        {% for p in payments %}
        <tr>
            <td>{{ p.student_name }}</td><td>{{ p.phone }}</td><td>{{ p.test_name }}</td>
            <td><span style="color:{{ 'green' if p.payment_status == 'Approved' else 'orange' }}; font-weight:bold;">{{ p.payment_status }}</span></td>
            <td>
                {% if p.payment_status != 'Approved' %}
                <form method="POST" action="/admin/approve_payment/{{ p.id }}" style="display:inline-block;"><button type="submit" class="btn-sm" style="background:#16a34a; color:white;">✅ Unlock</button></form>
                {% endif %}
                <a href="/admin/delete_payment/{{ p.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    {% elif active_tab == 'special' %}
    <h3>👑 Special Access व्यवस्थापन</h3>
    <form method="POST" action="/admin/add_special_unlimited" style="background:#f8fafc; padding:15px; border-radius:8px; margin-bottom:15px;">
        <h4 style="margin:0 0 8px; color:#065f46;">🔄 अमर्याद प्रयत्न सवलत (Unlimited)</h4>
        <input type="text" name="phone" placeholder="१० अंकी नंबर" maxlength="10" required>
        <input type="text" name="student_name" placeholder="नाव">
        <button type="submit" class="btn">➕ जोडा</button>
    </form>

    {% elif active_tab == 'questions' %}
    <h3>📝 प्रश्न व्यवस्थापन व AI प्रश्न जनरेटर</h3>
    <div style="background:#f0fdf4; border:2px dashed #10b981; padding:15px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
        <div>
            <h4 style="margin:0; color:#065f46;">🤖 AI स्मार्ट मॉक प्रश्न जनरेटर</h4>
            <small style="color:#047857;">पोलीस भरतीसाठी संभाव्य प्रश्न एका क्लिकवर आपोआप तयार करा.</small>
        </div>
        <button id="aiBtn" type="button" class="btn" onclick="generateAIQuestions()" style="background:#10b981; color:#022c22; font-weight:800;">🤖 AI द्वारे प्रश्न ऑटो-जनरेट करा</button>
    </div>
    <form method="POST" action="/admin/bulk_questions" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <h4 style="margin:0 0 8px; color:#065f46;">⚡ बल्क प्रश्न अपलोडर (Pipe |)</h4>
        <select name="test_id" required>
            {% for t in tests %}<option value="{{ t.id }}">{{ t.test_title }}</option>{% endfor %}
        </select>
        <textarea id="bulkTextarea" name="bulk_questions_text" rows="4" placeholder="प्रश्न | पर्यायA | पर्यायB | पर्यायC | पर्यायD | अचूक उत्तर | स्पष्टीकरण" required></textarea>
        <button type="submit" class="btn" style="background:#0284c7; width:100%;">📥 अपलोड करा</button>
    </form>
    <table>
        <tr><th>ID</th><th>प्रश्न</th><th>अचूक</th><th>कृती</th></tr>
        {% for q in all_questions %}
        <tr>
            <td>{{ q.id }}</td><td><b>{{ q.question }}</b></td><td style="color:green; font-weight:bold;">{{ q.correct }}</td>
            <td>
                <a href="/admin/edit_question/{{ q.id }}" class="btn-sm" style="background:#0284c7; color:white;">✏ एडिट</a>
                <a href="/admin/delete_question/{{ q.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑️</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    {% elif active_tab == 'launch' %}
    <h3>🚀 टेस्ट व्यवस्थापन व ॲक्टिव्ह/क्लोज स्थिती</h3>
    <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:18px; border-radius:8px; border:1px solid #cbd5e1; margin-bottom:25px;">
        <input type="text" name="test_title" placeholder="टेस्टचे नाव" required>
        <select name="status"><option value="Active">Active (चालू)</option><option value="Closed">Closed (बंद)</option></select>
        <button type="submit" class="btn">🚀 नवीन टेस्ट सेव्ह करा</button>
    </form>
    <table>
        <tr><th>ID</th><th>नाव</th><th>स्थिती</th><th>कृती</th></tr>
        {% for t in tests %}
        <tr>
            <form method="POST" action="/admin/update_test/{{ t.id }}">
                <td>{{ t.id }}</td>
                <td><input type="text" name="test_title" value="{{ t.test_title }}" style="margin-bottom:0;" required></td>
                <td>
                    <select name="status" style="margin-bottom:0;">
                        <option value="Active" {% if t.status=='Active' %}selected{% endif %}>Active</option>
                        <option value="Closed" {% if t.status=='Closed' %}selected{% endif %}>Closed</option>
                    </select>
                </td>
                <td>
                    <button type="submit" class="btn-sm" style="background:#0284c7; color:white;">💾 अपडेट</button>
                    <a href="/admin/delete_test/{{ t.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑</a>
                </td>
            </form>
        </tr>
        {% endfor %}
    </table>

    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 राज्यस्तरीय गुणवत्ता यादी</h3>
    <table>
        <tr><th>रँक</th><th>नाव</th><th>जिल्हा</th><th>गुण</th></tr>
        {% for rank, l in top_leads %}
        <tr><td><b>#{{ rank }}</b></td><td>{{ l.student_name }}</td><td>{{ l.district }}</td><td><b>{{ l.score }} / {{ l.total_marks }}</b></td></tr>
        {% endfor %}
    </table>

    {% elif active_tab == 'feedback' %}
    <h3>💬 विद्यार्थ्यांचे अभिप्राय</h3>
    <form method="POST" action="/admin/bulk_delete_feedback" onsubmit="return confirm('निवडलेले सर्व अभिप्राय डिलीट करायचे का?');">
        <div style="margin-bottom:10px;"><button type="submit" class="btn-sm" style="background:#dc2626; color:white; padding:6px 12px;">🗑️ निवडलेले अभिप्राय डिलीट करा</button></div>
        <table>
            <tr><th style="width:40px;"><input type="checkbox" onclick="toggleSelectAllFeedbacks(this)"></th><th>नाव</th><th>अभिप्राय</th></tr>
            {% for f in feedbacks %}
            <tr><td><input type="checkbox" name="feedback_ids" value="{{ f.id }}" class="fb-checkbox"></td><td><b>{{ f.student_name }}</b></td><td>{{ f.feedback_text }}</td></tr>
            {% endfor %}
        </table>
    </form>

    {% elif active_tab == 'notices' %}
    <h3>📢 भरती PDF व्यवस्थापन</h3>
    <form method="POST" action="/admin/update_pdf_docs" enctype="multipart/form-data">
        <label>भरती अधिकृत माहिती PDF:</label><input type="file" name="recruitment_pdf_file" accept=".pdf">
        <label>भरती पात्रता PDF:</label><input type="file" name="eligibility_pdf_file" accept=".pdf">
        <button type="submit" class="btn">सेव्ह करा</button>
    </form>

    {% elif active_tab == 'trash' %}
    <h3>🗑️ रिसायकल बिन (Trash / Deleted Items)</h3>
    <p style="font-size:13px; color:#64748b;">येथे डिलीट केलेले प्रश्न व लीड्स आहेत. तुम्ही हवे तेव्हा त्यांना 'Restore' करू शकता.</p>
    <table>
        <tr><th>टाईप</th><th>नाव / प्रश्न</th><th>कृती</th></tr>
        {% for item in trash_questions %}
        <tr><td>प्रश्न</td><td>{{ item.question[:50] }}...</td><td><a href="/admin/restore_item/question/{{ item.id }}" class="btn-sm" style="background:#10b981; color:white;">♻️ Restore</a></td></tr>
        {% endfor %}
        {% for item in trash_leads %}
        <tr><td>विद्यार्थी लीड</td><td>{{ item.student_name }} ({{ item.phone }})</td><td><a href="/admin/restore_item/lead/{{ item.id }}" class="btn-sm" style="background:#10b981; color:white;">♻️ Restore</a></td></tr>
        {% endfor %}
    </table>

    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन सेटिंग्स, मेंटेनन्स मोड व हेल्प डेस्क</h3>
    <form method="POST" action="/admin/update_password">
        <div style="background:#fef3c7; border:1.5px solid #f59e0b; padding:15px; border-radius:8px; margin-bottom:20px;">
            <label style="font-weight:bold; color:#b45309;">🚧 संपूर्ण वेबसाईट चालू/बंद स्थिती (पॉवर बटण):</label>
            <select name="site_status" style="margin-top:6px; font-weight:bold;">
                <option value="active" {% if site_status == 'active' %}selected{% endif %}>🟢 वेबसाईट पूर्णपणे चालू ठेवा (Active)</option>
                <option value="maintenance" {% if site_status == 'maintenance' %}selected{% endif %}>🔴 वेबसाईट मेंटेनन्स मोडवर टाका (Under Maintenance)</option>
            </select>
        </div>

        <label>नवा पासवर्ड:</label>
        <input type="password" name="new_password" placeholder="नवा पासवर्ड टाका">

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
            <div><label>हेल्प डेस्क फोन नंबर:</label><input type="text" name="helpdesk_phone" value="{{ helpdesk_phone }}"></div>
            <div><label>हेल्प डेस्क पत्ता:</label><input type="text" name="helpdesk_address" value="{{ helpdesk_address }}"></div>
        </div>

        <label>होम पेज टॅबचा क्रम:</label><input type="text" name="home_tab_order" value="{{ home_tab_order }}">
        <label>ॲडमिन डॅशबोर्ड टॅबचा क्रम:</label><input type="text" name="admin_tab_order" value="{{ admin_tab_order }}">
        <button type="submit" class="btn">💾 बदल सेव्ह करा</button>
    </form>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- FLASK MAIN ROUTES -----------------

@app.route('/')
def home_tests_list():
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='site_status'")
            s_row = cur.fetchone()
            if s_row and s_row['setting_value'] == 'maintenance' and not session.get('admin_logged'):
                return render_template_string(MAINTENANCE_TEMPLATE)

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE status='Active' AND is_deleted=0 ORDER BY id ASC")
            raw_tests = cur.fetchall()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_pdf'")
            recruitment_pdf = cur.fetchone()['setting_value'] if cur.fetchone() else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_pdf'")
            eligibility_pdf = cur.fetchone()['setting_value'] if cur.fetchone() else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='home_tab_order'")
            home_tab_order = cur.fetchone()['setting_value'] if cur.fetchone() else 'all,live,paid,free,rapid,battle,docs,helpdesk'
            
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='helpdesk_phone'")
            helpdesk_phone = cur.fetchone()['setting_value'] if cur.fetchone() else '9921111960'
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='helpdesk_address'")
            helpdesk_address = cur.fetchone()['setting_value'] if cur.fetchone() else ''

            cur.execute("""
                SELECT district, COUNT(id) as total_students, ROUND(AVG(score)::numeric, 1) as avg_score
                FROM mock_test_leads WHERE district IS NOT NULL AND district != '' AND is_deleted=0
                GROUP BY district ORDER BY avg_score DESC LIMIT 15
            """)
            live_district_battles = cur.fetchall()

    ordered_tabs = [t.strip() for t in home_tab_order.split(',') if t.strip()]
    tests = [dict(t) for t in raw_tests]

    return render_template_string(
        HOME_TEMPLATE, tests=tests, recruitment_pdf=recruitment_pdf, eligibility_pdf=eligibility_pdf,
        ordered_tabs=ordered_tabs, live_district_battles=live_district_battles,
        helpdesk_phone=helpdesk_phone, helpdesk_address=helpdesk_address
    )

@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template_string(TERMS_TEMPLATE)

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
            if not test or test['status'] != 'Active': return "Test not found or closed", 404
            cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()
    return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    student_name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT id, correct FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()

    score = sum(1 for q in questions if request.form.get(f"q_{q['id']}", "") == q['correct'])
    total = len(questions)

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, score, total_marks, test_name)
                VALUES (%s, %s, %s, %s, %s, 'Approved', %s, %s, %s)
            """, (test_id, date.today().strftime("%Y-%m-%d"), student_name, district, phone, score, total, test['test_title']))
            conn.commit()

    return f"<h2 style='color:green; text-align:center; padding:40px;'>🎉 टेस्ट यशस्वीरीत्या सबमिट झाली! तुमचे गुण: {score} / {total}</h2><div style='text-align:center;'><a href='/'>मुख्य पानावर जा</a></div>"

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('admin_pass')
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_pass'")
                db_pass = cur.fetchone()['setting_value']
        if password == db_pass:
            session['admin_logged'] = True
            return redirect('/admin/dashboard')
        else:
            error = "चुकीचा पासवर्ड!"
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged', None)
    return redirect('/admin/login')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged'): return redirect('/admin/login')

    active_tab = request.args.get('tab', 'leads')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=0 ORDER BY id DESC")
            leads = cur.fetchall()
            cur.execute("SELECT * FROM test_papers WHERE is_deleted=0 ORDER BY id ASC")
            tests = cur.fetchall()
            cur.execute("SELECT * FROM questions WHERE is_deleted=0 ORDER BY id DESC")
            all_questions = cur.fetchall()
            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=0 ORDER BY score DESC LIMIT 100")
            all_leads_sorted = cur.fetchall()
            cur.execute("SELECT * FROM student_feedbacks ORDER BY id DESC")
            feedbacks = cur.fetchall()
            
            cur.execute("SELECT * FROM questions WHERE is_deleted=1")
            trash_questions = cur.fetchall()
            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=1")
            trash_leads = cur.fetchall()

            for key in ['site_status', 'helpdesk_phone', 'helpdesk_address', 'home_tab_order', 'admin_tab_order']:
                cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key=%s", (key,))
                val = cur.fetchone()
                locals()[key] = val['setting_value'] if val else ''

    top_leads = [(idx, l) for idx, l in enumerate(all_leads_sorted, start=1)]
    ordered_admin_tabs = [t.strip() for t in admin_tab_order.split(',') if t.strip()]

    return render_template_string(
        ADMIN_TEMPLATE, active_tab=active_tab, leads=leads, tests=tests, all_questions=all_questions,
        payments=leads, top_leads=top_leads, feedbacks=feedbacks, trash_questions=trash_questions,
        trash_leads=trash_leads, site_status=site_status, helpdesk_phone=helpdesk_phone,
        helpdesk_address=helpdesk_address, home_tab_order=home_tab_order, admin_tab_order=admin_tab_order,
        ordered_admin_tabs=ordered_admin_tabs
    )

@app.route('/admin/ai_generate_mock', methods=['POST'])
def admin_ai_generate_mock():
    if not session.get('admin_logged'): return redirect('/admin/login')
    sample_questions = [
        "महाराष्ट्रातील सर्वोच्च शिखर कोणते? | कळसूबाई | साल्हेर | महाबळेश्वर | त्र्यंबकेश्वर | A | कळसूबाई हे सर्वोच्च शिखर आहे.",
        "भारताची राजधानी कोणती? | मुंबई | नवी दिल्ली | कोलकाता | चेन्नई | B | नवी दिल्ली ही भारताची राजधानी आहे."
    ]
    return jsonify({"success": True, "questions_text": "\n".join(sample_questions)})

@app.route('/admin/bulk_delete_feedback', methods=['POST'])
def admin_bulk_delete_feedback():
    if not session.get('admin_logged'): return redirect('/admin/login')
    selected_ids = request.form.getlist('feedback_ids')
    if selected_ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM student_feedbacks WHERE id = ANY(%s)", (selected_ids,))
                conn.commit()
    return redirect('/admin/dashboard?tab=feedback')

@app.route('/admin/delete_question/<int:q_id>')
def admin_delete_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE questions SET is_deleted=1 WHERE id=%s", (q_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/delete_lead/<int:l_id>')
def admin_delete_lead(l_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id=%s", (l_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/restore_item/<item_type>/<int:item_id>')
def admin_restore_item(item_type, item_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            if item_type == 'question':
                cur.execute("UPDATE questions SET is_deleted=0 WHERE id=%s", (item_id,))
            elif item_type == 'lead':
                cur.execute("UPDATE mock_test_leads SET is_deleted=0 WHERE id=%s", (item_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=trash')

@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    status = request.form.get('status', 'Active')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_papers (test_title, status) VALUES (%s, %s)", (title, status))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/update_test/<int:test_id>', methods=['POST'])
def admin_update_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    status = request.form.get('status', 'Active')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE test_papers SET test_title=%s, status=%s WHERE id=%s", (title, status, test_id))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE test_papers SET is_deleted=1 WHERE id=%s", (test_id,))
            conn.query("UPDATE questions SET is_deleted=1 WHERE test_id=%s", (test_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/update_password', methods=['POST'])
def admin_update_password():
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_pass = request.form.get('new_password')
    site_status = request.form.get('site_status', 'active')
    helpdesk_phone = request.form.get('helpdesk_phone', '')
    helpdesk_address = request.form.get('helpdesk_address', '')
    home_tab_order = request.form.get('home_tab_order', '')
    admin_tab_order = request.form.get('admin_tab_order', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            if new_pass:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
            for k, v in [('site_status', site_status), ('helpdesk_phone', helpdesk_phone), ('helpdesk_address', helpdesk_address), ('home_tab_order', home_tab_order), ('admin_tab_order', admin_tab_order)]:
                cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (k, v))
            conn.commit()
    return redirect('/admin/dashboard?tab=settings')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
