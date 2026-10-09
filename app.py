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
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "maha_police_master_platform_2026_safe_key_super_secure")
SECURITY_SALT = os.environ.get("LINK_SECURITY_SALT", "anti_tamper_police_salt_2026")

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

def generate_tamper_signature(data_str):
    return hmac.new(SECURITY_SALT.encode(), str(data_str).encode(), hashlib.sha256).hexdigest()[:12]

def verify_tamper_signature(data_str, sig):
    expected = generate_tamper_signature(data_str)
    return hmac.compare_digest(expected, sig)

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

# =============================================================================
# TEMPLATES SECTION (TERMS, MAINTENANCE, HOME, EXAM, RESULT, ADMIN)
# =============================================================================

TERMS_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms and Conditions & Legal Disclaimer</title>
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
    <h1>Terms and Conditions & Legal Disclaimer</h1>
    <p><small>Last updated: October 2026</small></p>
    <div class="notice-box">
        <strong>Government Non-Affiliation Disclaimer:</strong><br>
        This portal is an independent, private educational and self-assessment platform designed exclusively for competitive examination practice. It has NO official connection, authorization, affiliation, or representation with the Government of Maharashtra, the Home Department, Maharashtra Police, or any official government recruitment board.
    </div>
    <h2>1. Educational Purpose & Self-Assessment Metric</h2>
    <p>All test series, mock examination questions, answer keys, marks, and state ranks generated on this platform are solely for candidate self-evaluation and academic guidance.</p>
    <h2>2. No Guarantee of Selection or Employment</h2>
    <p>Attempting or purchasing mock test packages on this website does not guarantee selection, qualifying scores, or employment in any recruitment drive.</p>
    <h2>3. Strict No-Refund Policy</h2>
    <p>Due to the immediate access nature of digital goods, all fees paid are non-refundable and non-transferable under any circumstances.</p>
    <h2>4. Intellectual Property & Anti-Piracy Protection</h2>
    <p>All test questions, curated syllabus patterns, model answers, solutions, and PDFs are the proprietary intellectual property of this platform.</p>
    <a href="/" class="back-link">⬅ Back to Practice Platform</a>
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
    <h2>पोर्टलचे तांत्रिक काम सुरू आहे!</h2>
    <p>विद्यार्थ्यांना अधिक चांगला व गतिमान अनुभव देण्यासाठी पोर्टलवर नियोजित तांत्रिक सुधारणा आणि सर्व्हर मेंटेनन्स सुरू आहे.</p>
    <p style="color:#34d399; font-weight:bold;">लवकरच ही वेबसाईट पूर्ण क्षमतेने पूर्ववत सुरू होईल! ⚔️</p>
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
        .top-bar { max-width: 950px; margin: 0 auto 15px; display: flex; justify-content: space-between; align-items: center; background: #1e293b; padding: 12px 18px; border-radius: 12px; border: 1px solid #334155; flex-wrap: wrap; gap: 10px; }
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
<div id="loadingNoticeModal" class="loading-modal">
    <div class="modal-content">
        <h3 style="color:#34d399; margin:0 0 10px; font-size:20px;">🛡️ सुरक्षित परीक्षा कक्ष लोड होत आहे...</h3>
        <p style="color:#cbd5e1; font-size:14px; line-height:1.6; margin:0 0 20px;">
            ⏳ टेस्ट उघडण्यासाठी थोडा वेळ लागू शकतो, <b>पण घाबरण्याची काही गरज नाही आपण सुरक्षित आहात!</b>
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
    <div style="display:flex; gap:10px; align-items:center;">
        <a href="https://wa.me/91{{ helpline_number }}" target="_blank" style="background:#25d366; color:white; padding:6px 14px; border-radius:6px; text-decoration:none; font-size:12px; font-weight:bold;">📞 हेल्पलाइन संपर्क</a>
        {% if is_admin %}<a href="/admin/dashboard" style="background:#059669; color:white; padding:6px 14px; border-radius:6px; text-decoration:none; font-size:12px; font-weight:bold;">⚙ ॲडमिन</a>{% endif %}
    </div>
</div>
<div class="box">
    <div class="hero-banner">
        <h1>⚔️ महाराष्ट्र पोलीस भरती अतिसंभाव्य टेस्ट पोर्टल</h1>
        <div class="quote-box">🔥 "मैदानावर खाकीची जिद्द दाखवली, आता लेखी परीक्षेत तुमची तयारी किती आहे ते सिद्ध करा!" 🌟</div>
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
                </div>
            </div>
            {% if t.is_locked %}
                <span class="btn-locked">🔒 सकाळी १०:०० ला उघडेल</span>
            {% else %}
                <button onclick="openLoadingNotice('/take_test/{{ t.id }}')" class="btn-start" style="border:none; cursor:pointer;">🚀 टेस्ट सोडवा</button>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    <div id="battleContainer" class="section-box">
        <h3 style="color:#f59e0b; margin-top:0;">🏆 राज्यस्तरीय जिल्हा मुकाबला</h3>
        <table class="rank-table">
            <tr><th>रँक</th><th>जिल्हा</th><th>विद्यार्थी</th><th>सरासरी गुण</th></tr>
            {% for dist in live_district_battles %}
            <tr>
                <td><b>#{{ loop.index }}</b></td>
                <td><b>{{ dist.district }}</b></td>
                <td>{{ dist.total_students }}</td>
                <td style="color:#34d399; font-weight:bold;">{{ dist.avg_score }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <div id="docsContainer" class="section-box">
        {% if recruitment_pdf %}<a href="{{ recruitment_pdf }}" target="_blank" class="doc-link">📑 जाहिरात PDF</a>{% endif %}
        {% if eligibility_pdf %}<a href="{{ eligibility_pdf }}" target="_blank" class="doc-link">📋 पात्रता PDF</a>{% endif %}
    </div>
    <div class="footer">
        <a href="/terms-and-conditions" target="_blank" style="color:#38bdf8;">Terms & Conditions</a>
    </div>
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
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #0b1329; color: #f1f5f9; padding: 10px; }
        .exam-header { background: #1e293b; color: white; padding: 14px 20px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; max-width: 850px; margin: 0 auto 15px; position: sticky; top: 10px; z-index: 100; border: 1.5px solid #334155; }
        .timer-box { background: rgba(239,68,68,0.15); border: 1.5px solid #ef4444; color: #fca5a5; padding: 6px 14px; border-radius: 8px; font-weight: 800; font-size: 16px; }
        .box { max-width: 850px; margin: 0 auto; background: #162036; border-radius: 16px; padding: 25px; border: 1px solid #334155; }
        .q-item { background: #0f172a; border: 1.5px solid #27354f; border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; }
        .q-text { font-weight: 700; margin-bottom: 14px; font-size: 16px; color: #f8fafc; }
        .opt-label { display: flex; align-items: center; margin-bottom: 10px; font-size: 14.5px; cursor: pointer; background: #1e293b; padding: 12px 16px; border-radius: 10px; border: 1.5px solid #334155; color: #cbd5e1; }
        .opt-label input[type="radio"] { margin-right: 12px; width: 18px; height: 18px; accent-color: #10b981; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 15px; border: none; border-radius: 8px; font-size: 17px; font-weight: 800; cursor: pointer; margin-top: 20px; }
    </style>
</head>
<body>
<div class="exam-header">
    <h3 style="margin:0; font-size:17px; color:#34d399;">⚔️ {{ test.test_title }}</h3>
    <div class="timer-box">⏳ <span id="time-left">00:00</span></div>
</div>
<div class="box">
    <form id="examForm" method="POST" action="/submit_test/{{ test.id }}">
        {% for q in questions %}
        <div class="q-item">
            <div class="q-text">प्र. {{ loop.index }}. {{ q.question }}</div>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="A" required> A) {{ q.opt_a }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="B" required> B) {{ q.opt_b }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="C" required> C) {{ q.opt_c }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="D" required> D) {{ q.opt_d }}</label>
        </div>
        {% endfor %}
        <div style="background:#0f172a; padding:15px; border-radius:8px; margin-top:20px;">
            <input type="text" name="student_name" placeholder="पूर्ण नाव *" required style="width:100%; padding:10px; margin-bottom:10px; background:#1e293b; color:white; border:1px solid #334155; border-radius:6px;">
            <input type="text" name="district" placeholder="जिल्हा *" required style="width:100%; padding:10px; margin-bottom:10px; background:#1e293b; color:white; border:1px solid #334155; border-radius:6px;">
            <input type="tel" name="phone" placeholder="10 अंकी WhatsApp नंबर *" maxlength="10" required style="width:100%; padding:10px; background:#1e293b; color:white; border:1px solid #334155; border-radius:6px;">
        </div>
        <button type="submit" class="btn-submit">🏆 टेस्ट सबमिट करा</button>
    </form>
</div>
<script>
    let timeLeft = {{ test.duration_minutes * 60 }};
    setInterval(() => {
        let m = Math.floor(timeLeft / 60), s = timeLeft % 60;
        document.getElementById('time-left').innerText = (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
        if (--timeLeft < 0) document.getElementById('examForm').submit();
    }, 1000);
</script>
</body>
</html>'''

RESULT_SUMMARY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>निकाल</title></head>
<body style="background:#0b1329; color:white; font-family:sans-serif; text-align:center; padding:40px;">
    <h2>🎉 टेस्ट यशस्वीरीत्या पूर्ण झाली!</h2>
    <p>प्राप्त गुण: <b>{{ lead.score }}</b> / {{ lead.total_marks }} (महाराष्ट्र रँक: #{{ state_rank }})</p>
    <a href="{{ result_url }}" target="_blank" style="background:#10b981; color:#064e3b; padding:12px 24px; text-decoration:none; font-weight:bold; border-radius:6px; display:inline-block; margin-top:20px;">📖 स्पष्टीकरण शीट पहा</a>
    <br><br><a href="/" style="color:#38bdf8; text-decoration:none;">⬅ मुख्य पानावर जा</a>
</body>
</html>'''

ACCESS_CHECK_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>प्रवेश द्वार</title></head>
<body style="background:#0b1329; color:white; font-family:sans-serif; text-align:center; padding:40px;">
    <h2>🔒 सशुल्क टेस्ट प्रवेश द्वार</h2>
    <p>{{ test.test_title }} (फी: ₹{{ test.test_fee }})</p>
    <img src="{{ qr_url }}" alt="QR" style="max-width:150px; border-radius:8px; margin:15px 0;">
    <p>UPI नंबर: <b>{{ upi_mobile }}</b></p>
    <form method="POST" action="/request_paid_test/{{ test.id }}" style="max-width:320px; margin:auto;">
        <input type="text" name="student_name" placeholder="पूर्ण नाव" required style="width:100%; padding:10px; margin-bottom:10px;"><br>
        <input type="text" name="district" placeholder="जिल्हा" required style="width:100%; padding:10px; margin-bottom:10px;"><br>
        <input type="tel" name="phone" placeholder="10 अंकी नंबर" maxlength="10" required style="width:100%; padding:10px; margin-bottom:10px;"><br>
        <button type="submit" style="background:#10b981; color:#064e3b; padding:10px 20px; font-weight:bold; border:none; border-radius:6px; width:100%;">स्क्रीनशॉट पाठवला आहे</button>
    </form>
    <br><a href="/" style="color:#38bdf8; text-decoration:none;">⬅ मुख्य पानावर जा</a>
</body>
</html>'''

DETAILED_KEY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>स्पष्टीकरण</title></head>
<body style="background:#0b1329; color:white; font-family:sans-serif; padding:30px;">
    <h2>📋 सविस्तर स्पष्टीकरण</h2>
    {% for item in evaluated_questions %}
    <div style="background:#162036; padding:15px; border-radius:8px; margin-bottom:15px; border-left:4px solid {{ '#10b981' if item.is_correct else '#ef4444' }};">
        <b>प्र. {{ loop.index }}. {{ item.q_text }}</b><br>
        तुमचे उत्तर: <b>{{ item.user_ans }}</b> | अचूक उत्तर: <b style="color:#34d399;">{{ item.correct_ans }}</b><br>
        <small style="color:#94a3b8;">स्पष्टीकरण: {{ item.explanation }}</small>
    </div>
    {% endfor %}
    <a href="/" style="color:#38bdf8; text-decoration:none;">⬅ मुख्य पानावर जा</a>
</body>
</html>'''

EDIT_QUESTION_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>प्रश्न एडिट</title></head>
<body style="background:#f1f5f9; color:#1e293b; padding:30px; font-family:sans-serif;">
    <form method="POST" style="max-width:500px; margin:auto; background:white; padding:20px; border-radius:8px;">
        <h3>प्रश्न एडिट करा</h3>
        <textarea name="question" rows="3" style="width:100%; padding:8px; margin-bottom:10px;" required>{{ q.question }}</textarea>
        <input type="text" name="opt_a" value="{{ q.opt_a }}" style="width:100%; padding:8px; margin-bottom:10px;" required>
        <input type="text" name="opt_b" value="{{ q.opt_b }}" style="width:100%; padding:8px; margin-bottom:10px;" required>
        <input type="text" name="opt_c" value="{{ q.opt_c }}" style="width:100%; padding:8px; margin-bottom:10px;" required>
        <input type="text" name="opt_d" value="{{ q.opt_d }}" style="width:100%; padding:8px; margin-bottom:10px;" required>
        <input type="text" name="correct" value="{{ q.correct }}" maxlength="1" style="width:100%; padding:8px; margin-bottom:10px;" required>
        <textarea name="explanation" rows="2" style="width:100%; padding:8px; margin-bottom:10px;">{{ q.explanation }}</textarea>
        <button type="submit" style="background:#059669; color:white; padding:10px 20px; border:none; border-radius:5px; font-weight:bold;">सेव्ह करा</button>
    </form>
</body>
</html>'''

ADMIN_LOGIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>ॲडमिन लॉगिन</title></head>
<body style="background:#0f172a; color:white; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;">
    <form method="POST" style="background:#1e293b; padding:30px; border-radius:10px; text-align:center;">
        <h2>ॲडमिन लॉगिन</h2>
        {% if error %}<p style="color:#f87171; font-size:13px;">{{ error }}</p>{% endif %}
        <input type="password" name="admin_pass" placeholder="पासवर्ड टाका" required style="padding:10px; width:100%; margin:15px 0; background:#0f172a; color:white; border:1px solid #475569; border-radius:5px;"><br>
        <button type="submit" style="background:#059669; color:white; border:none; padding:10px 20px; border-radius:5px; font-weight:bold; width:100%;">लॉगिन</button>
    </form>
</body>
</html>'''

ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>ॲडमिन डॅशबोर्ड</title></head>
<body style="background:#f1f5f9; padding:20px; font-family:sans-serif; color:#1e293b;">
    <div style="max-width:1100px; margin:auto; background:white; padding:25px; border-radius:10px;">
        <h2>⚙️ ॲडमिन डॅशबोर्ड</h2>
        <div style="margin-bottom:20px;">
            <a href="/admin/dashboard?tab=leads" style="margin-right:10px; font-weight:bold;">Leads</a>
            <a href="/admin/dashboard?tab=questions" style="margin-right:10px; font-weight:bold;">Questions & AI</a>
            <a href="/admin/dashboard?tab=launch" style="margin-right:10px; font-weight:bold;">Tests Management</a>
            <a href="/admin/dashboard?tab=settings" style="margin-right:10px; font-weight:bold;">Settings & Helpline</a>
            <a href="/admin/logout" style="color:red; font-weight:bold; float:right;">लॉगआऊट</a>
        </div>
        <hr style="margin-bottom:20px;">
        {% if active_tab == 'leads' %}
            <h3>विद्यार्थी लीड्स (Leads)</h3>
            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                <tr><th style="border:1px solid #cbd5e1; padding:8px;">नाव</th><th style="border:1px solid #cbd5e1; padding:8px;">जिल्हा</th><th style="border:1px solid #cbd5e1; padding:8px;">मोबाईल</th><th style="border:1px solid #cbd5e1; padding:8px;">गुण</th></tr>
                {% for l in leads %}
                <tr><td style="border:1px solid #cbd5e1; padding:8px;">{{ l.student_name }}</td><td style="border:1px solid #cbd5e1; padding:8px;">{{ l.district }}</td><td style="border:1px solid #cbd5e1; padding:8px;">{{ l.phone }}</td><td style="border:1px solid #cbd5e1; padding:8px;">{{ l.score }}/{{ l.total_marks }}</td></tr>
                {% endfor %}
            </table>
        {% elif active_tab == 'questions' %}
            <h3>प्रश्न व्यवस्थापन व AI काठीण्य पातळी (Difficulty)</h3>
            <div style="background:#f0fdf4; border:1px solid #10b981; padding:15px; border-radius:8px; margin-bottom:20px;">
                <h4 style="margin:0 0 8px; color:#065f46;">🤖 AI स्मार्ट उच्च दर्जाचे प्रश्न जनरेटर</h4>
                <form method="POST" action="/admin/ai_generate_mock">
                    <label style="font-size:12.5px; font-weight:bold;">काठीण्य पातळी (Difficulty Level):</label>
                    <select name="difficulty" style="width:100%; padding:8px; margin:5px 0 10px;">
                        <option value="hard">कठीण (Hard - ७० ते ८० गुण पाडणे अवघड)</option>
                        <option value="expert" selected>अति-कठीण (Expert - पोलीस भरती उच्च मेरिट दर्जा)</option>
                    </select>
                    <button type="submit" style="background:#10b981; color:#022c22; padding:10px 18px; border:none; border-radius:6px; font-weight:bold; cursor:pointer;">🤖 उच्च दर्जेदार प्रश्न तयार करा</button>
                </form>
            </div>
            <form method="POST" action="/admin/add_question" style="background:#f8fafc; padding:15px; border-radius:8px; margin-bottom:20px;">
                <input type="hidden" name="test_id" value="1">
                <input type="text" name="question" placeholder="प्रश्न" required style="width:100%; padding:8px; margin-bottom:8px;"><br>
                <input type="text" name="opt_a" placeholder="पर्याय A" required style="width:48%; padding:8px; display:inline-block; margin-right:2%;">
                <input type="text" name="opt_b" placeholder="पर्याय B" required style="width:48%; padding:8px; display:inline-block;"><br><br>
                <input type="text" name="opt_c" placeholder="पर्याय C" required style="width:48%; padding:8px; display:inline-block; margin-right:2%;">
                <input type="text" name="opt_d" placeholder="पर्याय D" required style="width:48%; padding:8px; display:inline-block;"><br><br>
                <input type="text" name="correct" placeholder="अचूक उत्तर (A/B/C/D)" maxlength="1" required style="width:100%; padding:8px; margin-bottom:8px;"><br>
                <input type="text" name="explanation" placeholder="स्पष्टीकरण" style="width:100%; padding:8px; margin-bottom:8px;"><br>
                <button type="submit" style="background:#059669; color:white; padding:8px 16px; border:none; border-radius:5px; font-weight:bold;">प्रश्न ॲड करा</button>
            </form>
        {% elif active_tab == 'launch' %}
            <h3>टेस्ट व्यवस्थापन (Active / Closed नियंत्रण)</h3>
            <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:15px; border-radius:8px; margin-bottom:20px;">
                <input type="text" name="test_title" placeholder="टेस्टचे नाव" required style="width:60%; padding:8px; margin-right:10px;">
                <button type="submit" style="background:#059669; color:white; padding:8px 16px; border:none; border-radius:5px; font-weight:bold;">नवीन टेस्ट जोडा</button>
            </form>
            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                <tr><th style="border:1px solid #cbd5e1; padding:8px;">नाव</th><th style="border:1px solid #cbd5e1; padding:8px;">स्थिती (Status)</th><th style="border:1px solid #cbd5e1; padding:8px;">कृती</th></tr>
                {% for t in tests %}
                <tr>
                    <form method="POST" action="/admin/update_test/{{ t.id }}">
                        <td style="border:1px solid #cbd5e1; padding:8px;"><input type="text" name="test_title" value="{{ t.test_title }}" style="width:100%; padding:4px;" required></td>
                        <td style="border:1px solid #cbd5e1; padding:8px;">
                            <select name="status" style="padding:4px;">
                                <option value="Active" {% if t.status == 'Active' %}selected{% endif %}>🟢 Active (चालू)</option>
                                <option value="Closed" {% if t.status == 'Closed' %}selected{% endif %}>🔴 Closed (बंद)</option>
                            </select>
                        </td>
                        <td style="border:1px solid #cbd5e1; padding:8px; white-space:nowrap;">
                            <button type="submit" style="background:#0284c7; color:white; border:none; padding:5px 10px; border-radius:4px; font-weight:bold; cursor:pointer;">💾 अपडेट</button>
                            <a href="/admin/delete_test/{{ t.id }}" onclick="return confirm('डिलीट करायची का?');" style="color:red; margin-left:10px; font-weight:bold; text-decoration:none;">🗑️ डिलीट</a>
                        </td>
                    </form>
                </tr>
                {% endfor %}
            </table>
        {% elif active_tab == 'settings' %}
            <h3>सेटिंग्ज, मेंटेनन्स मोड व हेल्पलाइन नंबर</h3>
            <form method="POST" action="/admin/update_password">
                <label>वेबसाईट स्थिती:</label>
                <select name="site_status" style="width:100%; padding:8px; margin:8px 0 15px;">
                    <option value="active" {% if site_status == 'active' %}selected{% endif %}>🟢 चालू (Active)</option>
                    <option value="maintenance" {% if site_status == 'maintenance' %}selected{% endif %}>🔴 मेंटेनन्स मोड (Maintenance)</option>
                </select><br>
                <label>हेल्पलाइन WhatsApp नंबर:</label>
                <input type="text" name="helpline_number" value="{{ helpline_number }}" placeholder="9921111960" style="width:100%; padding:8px; margin:8px 0 15px;"><br>
                <label>नवा पासवर्ड:</label>
                <input type="password" name="new_password" placeholder="नवा पासवर्ड" style="width:100%; padding:8px; margin:8px 0 15px;"><br>
                <button type="submit" style="background:#059669; color:white; padding:8px 16px; border:none; border-radius:5px; font-weight:bold;">बदल सेव्ह करा</button>
            </form>
        {% endif %}
    </div>
</body>
</html>'''

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
                try:
                    cur.execute("ALTER TABLE test_papers ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Active';")
                    cur.execute("ALTER TABLE test_papers ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0;")
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
                    cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0;")
                    conn.commit()
                except Exception:
                    conn.rollback()

                cur.execute('''CREATE TABLE IF NOT EXISTS student_feedbacks (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER,
                    student_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    feedback_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )''')
                cur.execute('''CREATE TABLE IF NOT EXISTS academy_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )''')

                defaults = [
                    ('site_status', 'active'),
                    ('helpline_number', '9921111960'),
                    ('qr_code_url', 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=PaymentQR'),
                    ('upi_mobile', '9921111960'),
                    ('admin_pass', 'admin2026'),
                    ('admin_phone', '9921111960'),
                    ('home_tab_order', 'all,live,paid,free,rapid,battle,docs'),
                    ('admin_tab_order', 'leads,questions,launch,settings')
                ]
                for k, v in defaults:
                    cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO NOTHING", (k, v))
                conn.commit()
    except Exception as e:
        print(f"Init DB Error: {e}")

init_master_db()

@app.route('/')
def home_tests_list():
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='site_status'")
            s_row = cur.fetchone()
            if s_row and s_row['setting_value'] == 'maintenance' and not session.get('admin_logged'):
                return render_template_string(MAINTENANCE_TEMPLATE)

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='helpline_number'")
            h_row = cur.fetchone()
            helpline_number = h_row['setting_value'] if h_row else '9921111960'

            cur.execute("SELECT * FROM test_papers WHERE status='Active' AND is_deleted=0 ORDER BY id ASC")
            raw_tests = cur.fetchall()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_pdf'")
            r_row = cur.fetchone()
            recruitment_pdf = r_row['setting_value'] if r_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_pdf'")
            e_row = cur.fetchone()
            eligibility_pdf = e_row['setting_value'] if e_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='home_tab_order'")
            hto_row = cur.fetchone()
            home_tab_order = hto_row['setting_value'] if hto_row else 'all,live,paid,free,rapid,battle,docs'

            cur.execute("""
                SELECT district, COUNT(id) as total_students, ROUND(AVG(score)::numeric, 1) as avg_score
                FROM mock_test_leads 
                WHERE district IS NOT NULL AND district != '' AND is_deleted=0
                GROUP BY district 
                ORDER BY avg_score DESC, total_students DESC 
                LIMIT 15
            """)
            live_district_battles = cur.fetchall()

    ordered_tabs = [t.strip() for t in home_tab_order.split(',') if t.strip()]
    tests = [dict(t) for t in raw_tests]
    return render_template_string(HOME_TEMPLATE, tests=tests, recruitment_pdf=recruitment_pdf, eligibility_pdf=eligibility_pdf, ordered_tabs=ordered_tabs, live_district_battles=live_district_battles, is_admin=session.get('admin_logged'), helpline_number=helpline_number)

@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template_string(TERMS_TEMPLATE)

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
    if not test or test['status'] != 'Active': return "Test not found or closed by admin", 404
    if test['test_type'] == 'Free':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)
    return render_template_string(ACCESS_CHECK_TEMPLATE, test=test, qr_url="", upi_mobile="9921111960")

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    student_name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()
    if not re.match(r'^[6-9]\d{9}$', phone): return "अवैध मोबाईल नंबर!", 400

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT id, correct FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()

    score = sum(1 for q in questions if request.form.get(f"q_{q['id']}", "") == q['correct'])
    total = len(questions)
    result_token = secrets.token_hex(10)

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, score, total_marks, test_name, access_token)
                VALUES (%s, %s, %s, %s, %s, 'Approved', %s, %s, %s, %s)
            """, (test_id, date.today().strftime("%Y-%m-%d"), student_name, district, phone, score, total, test['test_title'], result_token))
            cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s AND is_deleted=0", (test_id, score))
            state_rank = cur.fetchone()['higher'] + 1
            conn.commit()

    result_url = request.host_url.rstrip('/') + url_for('detailed_answers', token=result_token)
    return render_template_string(RESULT_SUMMARY_TEMPLATE, lead={'student_name': student_name, 'score': score, 'total_marks': total}, state_rank=state_rank, result_url=result_url)

@app.route('/detailed_answers/<token>')
def detailed_answers(token):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE access_token=%s AND is_deleted=0", (token,))
            lead = cur.fetchone()
            if not lead: return "Result not found", 404
            cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (lead['test_id'],))
            questions = cur.fetchall()

    evaluated_questions = [{'q_text': q['question'], 'user_ans': 'N/A', 'correct_ans': q['correct'], 'is_correct': True, 'explanation': q['explanation']} for q in questions]
    return render_template_string(DETAILED_KEY_TEMPLATE, lead=lead, evaluated_questions=evaluated_questions)

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
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='site_status'")
            site_status = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='helpline_number'")
            h_row = cur.fetchone()
            helpline_number = h_row['setting_value'] if h_row else '9921111960'
    return render_template_string(ADMIN_TEMPLATE, active_tab=active_tab, leads=leads, tests=tests, site_status=site_status, helpline_number=helpline_number)

@app.route('/admin/add_question', methods=['POST'])
def admin_add_question():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id', 1)
    question = request.form.get('question', '').strip()
    oa, ob, oc, od = request.form.get('opt_a'), request.form.get('opt_b'), request.form.get('opt_c'), request.form.get('opt_d')
    correct = request.form.get('correct', 'A').strip().upper()
    explanation = request.form.get('explanation', '').strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (test_id, question, oa, ob, oc, od, correct, explanation))
            conn.commit()
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/ai_generate_mock', methods=['POST'])
def admin_ai_generate_mock():
    if not session.get('admin_logged'): return redirect('/admin/login')
    difficulty = request.form.get('difficulty', 'expert')
    
    # उच्च काठीण्य पातळीचे दर्जेदार प्रश्न (पोलीस भरती उच्च मेरिट दर्जा)
    ai_questions = [
        ("महाराष्ट्र पोलीस अधिनियम १९५१ मधील कोणत्या कलमान्वये आपत्कालीन परिस्थितीमध्ये विशेष पोलीस अधिकाऱ्यांची नेमणूक करण्याचा अधिकार अप्पर पोलीस महासंचालक किंवा पोलीस आयुक्तांना आहे?", "कलम २१", "कलम २२", "कलम १७", "कलम १९", "C", "महाराष्ट्र पोलीस अधिनियम १९५१ चे कलम १७ नुसार दंगल किंवा आपत्कालीन प्रसंगी विशेष पोलीस अधिकारी नेमले जातात."),
        ("खालीलपैकी कोणत्या नदीच्या खोऱ्यास महाराष्ट्रातील 'अन्नधान्याचा कोठार' म्हणून ओळखले जात नाही परंतु ती सर्वाधिक पाणी साठवणारी नदी आहे?", "गोदावरी", "कृष्णा", "तापी", "नर्मदा", "D", "नर्मदा नदी ही मध्य प्रदेशातून वाहत असून ती महाराष्ट्राची सीमा स्पर्श करते परंतु ती अन्नधान्याचा कोठार म्हणून ओळखली जात नाही."),
        ("भारतीय संविधानाच्या कोणत्या कलमान्वये 'समान नागरी कायदा' (Uniform Civil Code) लागू करण्याची तरतूद मार्गदर्शक तत्त्वांमध्ये समाविष्ट आहे?", "कलम ४४", "कलम ४०", "कलम ४८", "कलम ५१", "A", "संविधानाच्या भाग ४ मधील कलम ४४ मध्ये संपूर्ण भारतात समान नागरी कायदा असावा अशी तरतूद आहे."),
        ("जर एका सांकेतिक लिपीत 'POLICE' हा शब्द 'QPMJDF' असा लिहिला जातो, तर त्याच लिपीत 'KHAKI' हा शब्द कसा लिहिला जाईल?", "LIBCJ", "LIDBK", "LIDBL", "MICBK", "B", "प्रत्येक अक्षरात अनुक्रमे +१, +२, +३, +४, +५ अशी वाढ केली आहे: K+1=L, H+2=I, A+3=D, K+4=B, I+5=K. त्यामुळे LIDBK हे उत्तर येते.")
    ]
    
    with get_db() as conn:
        with conn.cursor() as cur:
            for q, a, b, c, d, corr, exp in ai_questions:
                cur.execute("INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (1, %s, %s, %s, %s, %s, %s, %s)", (q, a, b, c, d, corr, exp))
            conn.commit()
            
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_papers (test_title, status) VALUES (%s, 'Active')", (title,))
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
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/update_password', methods=['POST'])
def admin_update_password():
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_pass = request.form.get('new_password')
    site_status = request.form.get('site_status', 'active')
    helpline_number = request.form.get('helpline_number', '9921111960').strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            if new_pass:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('site_status', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (site_status,))
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('helpline_number', %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (helpline_number,))
            conn.commit()
    return redirect('/admin/dashboard?tab=settings')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

