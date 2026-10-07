import csv
import io
import json
import os
import re
import secrets
import urllib.parse
import hmac
import hashlib
from datetime import date, datetime, timedelta
from contextlib import contextmanager
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for, send_from_directory
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "shreeguru_master_test_platform_2026_ultimate_safe")

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- टप्पा १: NEON POSTGRESQL THREADED CONNECTION POOLING ---
DATABASE_URL = os.environ.get("DATABASE_URL")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "shreeguru_webhook_secret_key")

db_pool = None
try:
    if DATABASE_URL:
        db_pool = pool.ThreadedConnectionPool(minconn=5, maxconn=50, dsn=DATABASE_URL)
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

def init_master_db():
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # १. टेस्ट पेपर्स टेबल
                cur.execute('''CREATE TABLE IF NOT EXISTS test_papers (
                    id SERIAL PRIMARY KEY,
                    test_title TEXT NOT NULL,
                    test_type TEXT DEFAULT 'Free',
                    test_fee REAL DEFAULT 0,
                    duration_minutes INTEGER DEFAULT 60,
                    status TEXT DEFAULT 'Active'
                )''')

                # २. प्रश्न टेबल
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

                # ३. विद्यार्थी लीड्स व निकाल टेबल
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
                    otp_code TEXT DEFAULT '',
                    valid_until TEXT DEFAULT '',
                    access_token TEXT DEFAULT '',
                    token_expires_at TEXT DEFAULT ''
                )''')

                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS access_token TEXT DEFAULT ''")
                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS token_expires_at TEXT DEFAULT ''")

                # ४. शेअर केलेल्या विद्यार्थ्यांसाठी ५ टेस्ट्स मोफत अनलॉक टेबल
                cur.execute('''CREATE TABLE IF NOT EXISTS shared_free_passes (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    unlocked_until_test INTEGER DEFAULT 5,
                    created_at TEXT NOT NULL
                )''')

                # ५. विद्यार्थी अभिप्राय (Feedback) टेबल
                cur.execute('''CREATE TABLE IF NOT EXISTS student_feedbacks (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER,
                    student_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    feedback_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )''')

                # ६. स्पेशल ॲक्सेस टेबल्स
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

                # ७. ॲकॅडमी सेटिंग्स
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
                    ('recruitment_pdf', ''),
                    ('eligibility_pdf', '')
                ]
                for k, v in defaults:
                    cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO NOTHING", (k, v))

                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_test_score ON mock_test_leads(test_id, score);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON mock_test_leads(phone);")
                
                cur.execute('SELECT COUNT(*) as count FROM test_papers')
                if cur.fetchone()['count'] == 0:
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active')")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (2, 'पोलीस व सैन्य भरती सराव टेस्ट #२', 'Paid', 99, 60, 'Active')")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (3, 'पोलीस व सैन्य भरती सराव टेस्ट #३', 'Paid', 99, 60, 'Active')")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (4, 'पोलीस व सैन्य भरती सराव टेस्ट #४', 'Paid', 99, 60, 'Active')")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (5, 'पोलीस व सैन्य भरती सराव टेस्ट #५', 'Paid', 99, 60, 'Active')")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (6, 'पोलीस व सैन्य भरती ५० टेस्ट्स संच #६', 'Paid', 99, 60, 'Active')")

                conn.commit()
    except Exception as e:
        print(f"Init DB Error: {e}")

init_master_db()

# ----------------- 1. PUBLIC HOME TEMPLATE -----------------
HOME_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</title>
    <link href="https://fonts.googleapis.com/css2?family=Baloo+Bhaina+2:wght@500;700&family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', 'Baloo Bhaina 2', sans-serif; }
        body { margin: 0; background: linear-gradient(135deg, #f0fdf4, #e6fffa); color: #1e293b; padding: 15px; }
        .top-bar { max-width: 850px; margin: 0 auto 10px; display: flex; justify-content: space-between; align-items: center; background: white; padding: 10px 15px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
        .clock { font-weight: bold; color: #065f46; font-size: 14px; }
        .box { max-width: 850px; margin: 0 auto; background: white; border-radius: 14px; padding: 25px; box-shadow: 0 12px 30px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 26px; font-family: 'Baloo Bhaina 2', cursive; }
        .quote-box { background: #ecfdf5; border-left: 4px solid #059669; padding: 12px 15px; border-radius: 6px; font-size: 15px; color: #065f46; font-weight: 600; text-align: center; margin-bottom: 20px; line-height: 1.5; }
        .test-card { background: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 10px; padding: 18px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; transition: 0.2s; }
        .test-card:hover { border-color: #059669; box-shadow: 0 4px 12px rgba(5,150,105,0.1); }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; box-shadow: 0 3px 8px rgba(5,150,105,0.3); }
        .badge-free { background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-paid { background: #fef9c3; color: #854d0e; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .bottom-docs { display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; margin-top: 25px; margin-bottom: 15px; }
        .doc-btn { display: inline-flex; align-items: center; gap: 6px; background: #f1f5f9; color: #0f172a; padding: 9px 16px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600; border: 1.5px solid #cbd5e1; transition: 0.2s; }
        .footer-terms { text-align: center; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 12px; }
        .footer-terms a { color: #0369a1; text-decoration: none; font-weight: 600; }
    </style>
    <script>
        function updateClock() {
            const now = new Date();
            document.getElementById('live-clock').innerText = now.toLocaleDateString('mr-IN') + ' ' + now.toLocaleTimeString();
        }
        setInterval(updateClock, 1000);
    </script>
</head>
<body onload="updateClock()">
<div class="top-bar">
    <div class="clock">🕒 <span id="live-clock">लोडिंग...</span></div>
    {% if is_admin %}
    <div><a href="/admin/dashboard" style="background:#059669; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">⚙ ॲडमिन डॅशबोर्ड</a></div>
    {% endif %}
</div>
<div class="box">
    <h2>⚔ राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</h2>
    <div class="quote-box">
        🔥 हातात उरलेल्या दिवसात काबाड कष्ट करून तुला तुझे वर्दीचे स्वप्न पूर्ण करायचे आहे (लक्षात ठेव तुला घडविण्यासाठी कुणाचे तरी हात झिजत आहेत) 🌟
    </div>
    <p style="font-size:15px; font-weight:600; color:#0b3c5d; margin-bottom:20px; border-bottom:2px solid #e2e8f0; padding-bottom:8px; text-align:center;">
        खालील प्रश्नपत्रिका सोडवा आणि संपूर्ण राज्यात तुमचा रँक तपासा
    </p>
    {% for t in tests %}
    <div class="test-card">
        <div>
            <h4 style="margin:0 0 6px; color:#0f172a; font-size:17px; font-family:'Baloo Bhaina 2', cursive;">{{ t.test_title }}</h4>
            <span class="{{ 'badge-free' if t.test_type == 'Free' else 'badge-paid' }}">
                {{ '🟢 मोफत महासराव टेस्ट' if t.test_type == 'Free' else '⭐ सशुल्क (Paid) टेस्ट संच - ₹' ~ t.test_fee }}
            </span>
            <div style="font-size:12px; color:#64748b; margin-top:4px;">⏱️ वेळ मर्यादा: {{ t.duration_minutes }} मिनिटे</div>
        </div>
        <a href="/take_test/{{ t.id }}" class="btn-start">✨ टेस्ट सोडवा</a>
    </div>
    {% endfor %}
    <div class="bottom-docs">
        {% if recruitment_pdf %}<a href="{{ recruitment_pdf }}" target="_blank" class="doc-btn">📄 भरती अधिकृत माहिती (PDF)</a>{% endif %}
        {% if eligibility_pdf %}<a href="{{ eligibility_pdf }}" target="_blank" class="doc-btn">📋 भरती पात्रता व निकष (PDF)</a>{% endif %}
    </div>
    <div class="footer-terms">
        <span>© 2026 Online Mock Platform. All rights reserved. | </span>
        <a href="/terms-and-conditions" target="_blank">Terms & Conditions</a>
    </div>
</div>
</body>
</html>'''

TERMS_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><title>Terms and Conditions</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { font-family:'Poppins', sans-serif; background:#f8fafc; padding:30px 15px; color:#1e293b; line-height:1.6; }
        .terms-container { max-width:800px; margin:auto; background:white; padding:35px; border-radius:12px; border-top:5px solid #059669; box-shadow:0 10px 25px rgba(0,0,0,0.06); }
    </style>
</head>
<body>
<div class="terms-container">
    <h2>Terms and Conditions</h2>
    <p>Last updated: October 2026. This online mock exam platform is intended for government exam preparation.</p>
    <a href="/" style="color:#0284c7; text-decoration:none; font-weight:bold;">⬅ Back to Home</a>
</div>
</body>
</html>'''

# ----------------- 2. परीक्षा कक्ष (AUTO-SAVE + EXIT CONFIRMATION) -----------------
EXAM_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ test.test_title }} - परीक्षा कक्ष</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #eef2f7; color: #1e293b; padding: 10px; }
        .exam-header { background: #065f46; color: white; padding: 12px 20px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; max-width: 800px; margin: 0 auto 15px; position: sticky; top: 10px; z-index: 100; box-shadow: 0 4px 10px rgba(0,0,0,0.15); }
        .box { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border-top: 5px solid #059669; }
        .timer-box { background: #fee2e2; border: 2px solid #ef4444; color: #991b1b; padding: 8px 15px; border-radius: 6px; font-weight: bold; font-size: 15px; }
        .q-item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; margin-bottom: 18px; }
        .q-text { font-weight: bold; margin-bottom: 10px; font-size: 15px; color: #0f172a; }
        .opt-label { display: block; margin-bottom: 8px; font-size: 14px; cursor: pointer; background: white; padding: 9px 12px; border-radius: 6px; border: 1px solid #e2e8f0; }
        .opt-label:hover { background: #f1f5f9; }
        .bottom-submission-card { background: #f0fdf4; border: 2px solid #86efac; border-radius: 10px; padding: 20px; margin-top: 25px; margin-bottom: 15px; }
        .bottom-submission-card input { width: 100%; padding: 11px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-top: 4px; font-size: 14px; margin-bottom: 10px; }
        .phone-error-msg { display: none; color: #b91c1c; font-size: 12px; font-weight: bold; background: #fee2e2; border-left: 3px solid #dc2626; padding: 6px 10px; border-radius: 4px; margin-bottom: 10px; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #059669, #047857); color: white; padding: 14px; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.2s; }
    </style>
    <script>
        let isFormSubmitted = false;
        const testStorageKey = 'shreeguru_saved_answers_{{ test.id }}';
        const timerStorageKey = 'shreeguru_saved_timer_{{ test.id }}';

        // १. चुकून बाहेर पडण्याचा प्रयत्न केल्यास खात्रीचा इशारा
        window.addEventListener('beforeunload', function (e) {
            if (!isFormSubmitted) {
                e.preventDefault();
                e.returnValue = 'तुम्ही खरंच टेस्ट सोडून बाहेर पडू इच्छिता का?';
                return e.returnValue;
            }
        });

        // २. उरलेला वेळ (टायमर) व्यवस्थापन (Auto-save)
        let savedTime = localStorage.getItem(timerStorageKey);
        let timeLeft = savedTime !== null ? parseInt(savedTime, 10) : {{ test.duration_minutes * 60 }};

        function startTimer() {
            const timerDisplay = document.getElementById('time-left');
            let timer = setInterval(function () {
                let minutes = parseInt(timeLeft / 60, 10);
                let seconds = parseInt(timeLeft % 60, 10);
                minutes = minutes < 10 ? "0" + minutes : minutes;
                seconds = seconds < 10 ? "0" + seconds : seconds;
                timerDisplay.innerText = minutes + ":" + seconds;

                localStorage.setItem(timerStorageKey, timeLeft);

                if (--timeLeft < 0) {
                    clearInterval(timer);
                    alert("⏰ वेळ संपली! टेस्ट आपोआप सबमिट होत आहे.");
                    isFormSubmitted = true;
                    localStorage.removeItem(testStorageKey);
                    localStorage.removeItem(timerStorageKey);
                    document.getElementById("examForm").submit();
                }
            }, 1000);
        }

        // ३. विद्यार्थ्याने निवडलेले पर्याय सेव्ह करणे
        function saveAnswerProgress() {
            const answers = {};
            const selectedRadios = document.querySelectorAll('#questionsArea input[type="radio"]:checked');
            selectedRadios.forEach(radio => {
                answers[radio.name] = radio.value;
            });
            localStorage.setItem(testStorageKey, JSON.stringify(answers));
        }

        // ४. फोन पुन्हा चालू झाल्यावर आधी सोडवलेले प्रश्न पूर्ववत करणे
        function restoreAnswerProgress() {
            const savedAnswers = JSON.parse(localStorage.getItem(testStorageKey) || '{}');
            for (const [qName, qVal] of Object.entries(savedAnswers)) {
                const radio = document.querySelector(`input[name="${qName}"][value="${qVal}"]`);
                if (radio) {
                    radio.checked = true;
                }
            }
        }

        document.addEventListener('change', function(e) {
            if (e.target.type === 'radio') {
                saveAnswerProgress();
            }
        });

        // ५. फॉर्म व्हॅलिडेशन (शेवटी अचूक नंबर घेण्यासाठी)
        function validateAndReady() {
            const name = document.getElementById('s_name').value.trim();
            const dist = document.getElementById('s_dist').value.trim();
            const phoneInput = document.getElementById('s_phone');
            const phone = phoneInput.value.trim();
            const phoneErr = document.getElementById('phoneErrorNotice');
            const submitBtn = document.getElementById('submitBtn');
            const indianPhoneRegex = /^[6-9][0-9]{9}$/;

            if (phone.length > 0 && !['6', '7', '8', '9'].includes(phone.charAt(0))) {
                phoneErr.style.display = 'block';
                phoneErr.innerText = '⚠️ आपण चुकीचा मोबाईल नंबर टाकत आहात!';
                submitBtn.disabled = true;
                return;
            } else if (phone.length === 10 && indianPhoneRegex.test(phone)) {
                phoneErr.style.display = 'none';
                if (name !== "" && dist !== "") {
                    submitBtn.disabled = false;
                    submitBtn.innerText = "✅ टेस्ट सबमिट करा व निकाल पहा";
                    submitBtn.style.opacity = "1";
                    return;
                }
            } else {
                phoneErr.style.display = 'none';
            }
            submitBtn.disabled = true;
            submitBtn.innerText = "⚠️ कृपया खाली नाव, जिल्हा व WhatsApp नंबर भरा";
            submitBtn.style.opacity = "0.6";
        }

        document.addEventListener('DOMContentLoaded', function() {
            const examForm = document.getElementById('examForm');
            if (examForm) {
                examForm.addEventListener('submit', function() {
                    isFormSubmitted = true;
                    localStorage.removeItem(testStorageKey);
                    localStorage.removeItem(timerStorageKey);
                });
            }
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
        <h3 style="margin:0; font-size:18px;">⚔️ {{ test.test_title }}</h3>
        <small style="opacity:0.9;">राज्यस्तरीय पोलीस व सैन्य भरती महा-सराव कक्ष</small>
    </div>
    <div class="timer-box">
        ⏳ वेळ: <span id="time-left">00:00</span>
    </div>
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
            <h3 style="margin:0 0 6px; color:#065f46; font-size:17px;">
                🎯 निकाल, महाराष्ट्र रँक व सविस्तर स्पष्टीकरणासाठी माहिती भरा:
            </h3>
            <p style="font-size:13px; color:#475569; margin:0 0 12px;">
                ⚠️ <b>टीप:</b> टेस्ट सबमिट करताच तुमचे गुण स्क्रीनवर दिसतील, आणि सविस्तर स्पष्टीकरणाची लिंक खालील WhatsApp नंबरवर पाठवली जाईल.
            </p>

            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px;">
                <div>
                    <label style="font-size:13px; font-weight:600;">पूर्ण नाव *:</label>
                    <input type="text" name="student_name" id="s_name" placeholder="उदा. राहुल तानाजी पाटील" onkeyup="validateAndReady()" required>
                </div>
                <div>
                    <label style="font-size:13px; font-weight:600;">जिल्हा *:</label>
                    <input type="text" name="district" id="s_dist" placeholder="उदा. कोल्हापूर" onkeyup="validateAndReady()" required>
                </div>
                <div>
                    <label style="font-size:13px; font-weight:600;">WhatsApp मोबाईल नंबर *:</label>
                    <input type="tel" name="phone" id="s_phone" placeholder="10 अंकी मोबाईल नंबर" pattern="[6-9][0-9]{9}" maxlength="10" onkeyup="validateAndReady()" required>
                    <div id="phoneErrorNotice" class="phone-error-msg"></div>
                </div>
            </div>
        </div>

        <button type="submit" id="submitBtn" class="btn-submit" disabled>⚠️ कृपया खाली नाव, जिल्हा व WhatsApp नंबर भरा</button>
    </form>
</div>
</body>
</html>'''

# ----------------- 3. सशुल्क प्रवेशद्वार (TEST 6 ONWARDS) -----------------
ACCESS_CHECK_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>सशुल्क टेस्ट प्रवेश द्वार - {{ test.test_title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { font-family:'Poppins', sans-serif; background:#f0fdf4; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }
        .box { max-width:480px; width:100%; background:white; border-radius:12px; padding:25px; box-shadow:0 10px 25px rgba(0,0,0,0.1); border-top:6px solid #059669; }
        input { width:100%; padding:10px; border:1.5px solid #cbd5e1; border-radius:6px; margin-bottom:12px; font-size:14px; box-sizing:border-box; }
        .btn { width:100%; background:#059669; color:white; padding:12px; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size:15px; }
    </style>
</head>
<body>
<div class="box">
    <h2 style="color:#065f46; text-align:center; margin:0 0 5px;">🔒 ५० टेस्ट्स महासंच प्रवेश द्वार</h2>
    <p style="text-align:center; font-size:13px; color:#475569;">{{ test.test_title }} (फी: ₹{{ test.test_fee }})</p>

    <div style="background:#fee2e2; border:1.5px solid #ef4444; color:#991b1b; padding:10px; border-radius:6px; font-size:13px; text-align:center; margin-bottom:12px;">
        ⚠️ <b>तुमचा ५ मोफत टेस्ट्सचा कोटा पूर्ण झाला आहे!</b> पुढील सर्व टेस्ट्स अनलॉक करण्यासाठी फक्त ₹९९ चा पूर्ण संच मिळवा.
    </div>

    <div style="background:#fffbeb; padding:15px; border-radius:6px; border:1px solid #fcd34d; text-align:center; margin-bottom:15px;">
        <p style="margin:0 0 10px; font-weight:bold; color:#92400e; font-size:13px;">QR कोड स्कॅन करून किंवा <b>{{ upi_mobile }}</b> वर पे करा:</p>
        <img src="{{ qr_url }}" alt="QR" style="max-width:160px; max-height:160px; border-radius:6px; border:1px solid #cbd5e1;">
        <p style="font-size:12px; color:#b45309; font-weight:bold; margin-top:8px;">⚠️ पेमेंट करून झाल्यावर नाव व स्क्रीनशॉट <b>{{ upi_mobile }}</b> वर पाठवा!</p>
    </div>

    <form method="POST" action="/request_paid_test/{{ test.id }}">
        <label style="font-size:13px; font-weight:bold;">पूर्ण नाव:</label>
        <input type="text" name="student_name" placeholder="तुमचे नाव" required>
        <label style="font-size:13px; font-weight:bold;">जिल्हा:</label>
        <input type="text" name="district" placeholder="जिल्हा" required>
        <label style="font-size:13px; font-weight:bold;">व्हॉट्सॲप मोबाईल नंबर:</label>
        <input type="tel" name="phone" placeholder="10 अंकी मोबाईल नंबर" pattern="[6-9][0-9]{9}" maxlength="10" required>
        <button type="submit" class="btn">🚀 पेमेंट स्क्रीनशॉट पाठवला आहे (सुरू करा)</button>
    </form>
    <div style="text-align:center; margin-top:15px;"><a href="/" style="font-size:12px; color:#0284c7; text-decoration:none;">⬅️ मुख्य पानावर जा</a></div>
</div>
</body>
</html>'''

# ----------------- 4. आक्रमक व्हायरल रिजल्ट टेम्पलेट (SHARE TO UNLOCK 5 TESTS) -----------------
RESULT_SUMMARY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>टेस्ट निकाल - अभिनंदन</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; }
        .box { max-width: 740px; margin: 20px auto; background: white; border-radius: 14px; padding: 25px; box-shadow: 0 12px 30px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        
        .cutoff-warning-box { background: #fee2e2; border: 2px solid #ef4444; border-radius: 10px; padding: 16px; margin: 15px 0; color: #991b1b; text-align: center; }
        .cutoff-warning-box h4 { margin: 0 0 6px; font-size: 17px; }
        .timer-badge { display: inline-block; background: #b91c1c; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-top: 5px; }
        
        .cert-card { background: linear-gradient(135deg, #0f172a, #1e293b); color: white; border: 3px double #f59e0b; padding: 20px; border-radius: 12px; margin: 20px 0; text-align: center; }
        
        .share-lock-box { background: #fefce8; border: 2px dashed #ca8a04; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: center; color: #854d0e; }
        
        .referral-box { background: #ecfdf5; border: 2px solid #10b981; border-radius: 10px; padding: 18px; margin: 20px 0; text-align: center; color: #065f46; }
        
        .btn-wa { display: inline-block; background: #25D366; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 15px; margin: 8px 4px; cursor: pointer; border: none; }
        .btn-pay { display: inline-block; background: #d97706; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 16px; margin-top: 10px; box-shadow: 0 4px 12px rgba(217,119,6,0.3); }
    </style>
    <script>
        let currentShareCount = 0;
        function recordShare() {
            const waShareMsg = encodeURIComponent("🚨 *महाराष्ट्र पोलीस भरती २०२६ महा-सराव टेस्ट* 🚨\\nमी आत्ताच १०० गुणांचा महा-सराव पेपर सोडवला! संपूर्ण महाराष्ट्रात माझा रँक आलाय.\\nतुझ्यात दम असेल तर मला हरवून दाखव! मोफत टेस्ट लिंक:\\n{{ main_portal_url }}");
            window.open("https://wa.me/?text=" + waShareMsg, "_blank");

            currentShareCount++;
            document.getElementById('shareProgressCount').innerText = currentShareCount;

            if (currentShareCount >= 3) {
                fetch('/api/claim_share_bonus', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ phone: '{{ lead.phone }}' })
                })
                .then(res => res.json())
                .then(data => {
                    document.getElementById('shareLockSection').style.display = 'none';
                    document.getElementById('unlockedResultSection').style.display = 'block';
                    alert("🎉 अभिनंदन! तुम्ही ३ ग्रुप्सवर शेअर केले आहे. टेस्ट क्र. १ ते ५ तुमच्यासाठी १००% मोफत अनलॉक झाल्या आहेत!");
                })
                .catch(err => console.error(err));
            }
        }
    </script>
</head>
<body>
<div class="box">
    <h2 style="color:#065f46; margin:0 0 5px; text-align:center;">🎉 टेस्ट यशस्वीरीत्या पूर्ण झाली!</h2>
    <p style="font-size:14px; color:#64748b; margin-bottom:15px; text-align:center;">राज्यस्तरीय पोलीस व सैन्य भरती महा-सराव कक्ष २०२६</p>

    <!-- मार्क आणि रँक -->
    <div style="background:#ecfdf5; border:1px solid #86efac; border-radius:8px; padding:18px; margin-bottom:15px; text-align:center;">
        <p style="font-size:16px; margin:4px 0;">परीक्षार्थी: <b>{{ lead.student_name }}</b> (जिल्हा: <b>{{ lead.district }}</b>)</p>
        <p style="font-size:24px; color:#b45309; font-weight:bold; margin-top:8px;">
            🏆 संपूर्ण महाराष्ट्रातील रँक: <b style="color:#047857; font-size:30px;">#{{ state_rank }}</b> 🌟
        </p>
        <p style="font-size:20px; font-weight:bold; color:#0f172a; margin-top:4px;">
            प्राप्त गुण: <span style="color:#16a34a;">{{ lead.score }}</span> / {{ lead.total_marks }}
        </p>
    </div>

    <!-- १. रँक-प्रेशर आणि जिल्हा कट-ऑफ वॉर्निंग -->
    <div class="cutoff-warning-box">
        <h4>⚠️ सावधान! मेरिट लिस्ट धोक्यात आहे!</h4>
        <p style="font-size:13.5px; margin:0; line-height:1.5;">
            तुमच्या <b>{{ lead.district }}</b> जिल्ह्याचा संभाव्य कट-ऑफ <b>८२ गुण</b> आहे, आणि तुमचे <b>{{ lead.score }} गुण</b> आले आहेत. <br>
            फक्त काही प्रश्नांमुळे तुमचे खाकीचे स्वप्न हुकू देऊ नका!
        </p>
        <div style="margin-top:10px;">
            <a href="/take_test/6" class="btn-pay">⚡ '५० संभाव्य टेस्ट्स संच' फक्त ₹९९ मध्ये आत्ताच अनलॉक करा</a>
        </div>
        <div class="timer-badge">⏳ ही सवलत फक्त पुढील १५ मिनिटांसाठी वैध आहे!</div>
    </div>

    <!-- २. ईगो कार्ड (स्वाभिमान स्टेटस) -->
    <div class="cert-card">
        <h3 style="color:#fde047; margin:0 0 4px; font-size:19px;">🎖️ मिशन खाकी २०२६ — स्वाभिमान प्रमाणपत्र</h3>
        <p style="font-size:12px; color:#94a3b8; margin-bottom:12px;">"मी सज्ज आहे, तुम्ही आहात का?"</p>
        <div style="background:rgba(255,255,255,0.06); padding:15px; border-radius:8px; border:1px dashed #f59e0b;">
            <h2 style="color:#ffffff; margin:4px 0; font-size:22px;">{{ lead.student_name }}</h2>
            <p style="font-size:13px; margin:4px 0; color:#cbd5e1;">यांनी <b>{{ lead.test_name }}</b> मध्ये <b style="color:#34d399;">{{ lead.score }} गुण</b> मिळवून रँक <b style="color:#fde047;">#{{ state_rank }}</b> पटकावला आहे!</p>
            <p style="font-size:12px; color:#fca5a5; font-weight:bold; margin-top:6px;">"मैदानावर ५० पैकी ५० मारले, लेखी परीक्षेत दम असेल तर मला हरवून दाखवा!"</p>
        </div>
        <p style="font-size:11px; color:#cbd5e1; margin-top:8px;">📸 स्क्रीनशॉट काढा आणि खालील बटण दाबून मित्रांना स्टेटस चॅलेंज द्या:</p>
        <a href="https://wa.me/?text={{ ego_share_encoded }}" target="_blank" class="btn-wa">⚔️ मित्रांना WhatsApp वर चॅलेंज द्या</a>
    </div>

    <!-- ३. ग्रुप-अनलॉक चॅलेंज (शेअर केल्यावर ५ टेस्ट्स मोफत अनलॉक) -->
    <div id="shareLockSection" class="share-lock-box">
        <h3 style="margin:0 0 6px; font-size:17px; color:#92400e;">🔒 ५ टेस्ट्स मोफत अनलॉक ऑफर!</h3>
        <p style="font-size:13px; margin:0 0 10px; line-height:1.5;">
            सविस्तर स्पष्टीकरण पाहण्यासाठी आणि <b>पुढील ५ टेस्ट्स मोफत अनलॉक करण्यासाठी</b> ही टेस्ट तुमच्या <b>३ WhatsApp ग्रुप्सवर शेअर करा</b>.
        </p>
        <p style="font-weight:bold; font-size:14px; color:#065f46;">
            शेअर प्रगती: <span id="shareProgressCount">०</span> / ३ ग्रुप्स
        </p>
        <button onclick="recordShare()" class="btn-wa">📲 ३ WhatsApp ग्रुप्सवर शेअर करा (५ टेस्ट्स मोफत मिळवा)</button>
    </div>

    <!-- अनलॉक झालेले उत्तरतालिका व टेस्ट्स बटण -->
    <div id="unlockedResultSection" style="display:none; text-align:center; margin:20px 0; background:#dcfce7; padding:15px; border-radius:8px; border:1px solid #86efac;">
        <h4 style="color:#166534; margin:0 0 8px;">✅ अभिनंदन! सविस्तर उत्तरतालिका व पुढील ५ टेस्ट्स मोफत अनलॉक झाल्या आहेत!</h4>
        <a href="{{ result_url }}" target="_blank" style="background:#059669; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block; margin-right:5px;">📖 स्पष्टीकरण शीट उघडा</a>
        <a href="/" style="background:#0284c7; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block;">🎯 पुढील ५ टेस्ट्स सोडवा</a>
    </div>

    <!-- ४. रेफरल फ्री पास -->
    <div class="referral-box">
        <h4 style="margin:0 0 6px; font-size:16px;">🎁 पैसे नाहीत? हरकत नाही! संपूर्ण ५० टेस्ट्स मोफत मिळवा!</h4>
        <p style="font-size:12.5px; margin:0 0 10px; line-height:1.5;">
            तुमची खास लिंक तुमच्या ५ मित्रांना शेअर करा. त्यांनी मोफत टेस्ट सबमिट करताच तुमची <b>₹९९ ची संपूर्ण ५० टेस्ट्स सिरीज आपोआप मोफत अनलॉक होईल!</b>
        </p>
        <a href="https://wa.me/?text={{ referral_share_encoded }}" target="_blank" class="btn-wa" style="background:#059669;">
            🚀 ५ मित्रांना पाठवून मोफत पास मिळवा
        </a>
    </div>

    <div style="margin-top:20px; text-align:center;">
        <a href="/" style="background:#0b3c5d; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px;">🏠 मुख्य पानावर जा</a>
    </div>
</div>
</body>
</html>'''

# ----------------- 5. DETAILED KEY TEMPLATE -----------------
DETAILED_KEY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>सविस्तर उत्तरपत्रिका व स्पष्टीकरण</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; padding: 15px; }
        .box { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border-top: 6px solid #059669; }
        .item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .correct-box { border-left: 5px solid #16a34a; }
        .wrong-box { border-left: 5px solid #dc2626; }
        .feedback-card { background: #f0fdf4; border: 2px dashed #059669; border-radius: 10px; padding: 20px; margin-top: 20px; }
        .feedback-card textarea { width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; margin: 10px 0; }
        .btn-feedback { background: #059669; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
<div class="box">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">
        <span style="font-size:12px; font-weight:bold; color:#065f46;">📖 सविस्तर स्पष्टीकरण कक्ष</span>
        <a href="/" style="background:#0284c7; color:white; padding:6px 14px; border-radius:5px; text-decoration:none; font-weight:bold; font-size:12px;">🏠 मुख्य पानावर जा</a>
    </div>

    <h2 style="color:#065f46; margin:0 0 5px; text-align:center;">📋 सविस्तर उत्तरपत्रिका व स्पष्टीकरण</h2>
    <p style="text-align:center; font-size:13px; color:#64748b; margin-bottom:20px;">विद्यार्थी: <b>{{ lead.student_name }}</b> (जिल्हा: {{ lead.district }})</p>

    {% for item in evaluated_questions %}
    <div class="item {{ 'correct-box' if item.is_correct else 'wrong-box' }}">
        <div style="font-weight:bold; font-size:15px; margin-bottom:8px; color:#0f172a;">
            प्र. {{ loop.index }}. {{ item.q_text }}
        </div>
        <div style="font-size:13px; margin-bottom:4px; padding-left:10px;">
            A) {{ item.opt_a }} &nbsp;|&nbsp; B) {{ item.opt_b }} &nbsp;|&nbsp; C) {{ item.opt_c }} &nbsp;|&nbsp; D) {{ item.opt_d }}
        </div>
        <div style="display:flex; gap:15px; font-size:13px; margin:8px 0; padding-left:10px;">
            <div>तुमचे उत्तर: <b style="color:{{ 'green' if item.is_correct else 'red' }}; font-size:15px;">{{ item.user_ans }}</b></div>
            <div>अचूक उत्तर: <b style="color:#16a34a; font-size:15px;">{{ item.correct_ans }}</b></div>
        </div>
        {% if item.explanation %}
        <div style="font-size:12px; color:#166534; background:#f0fdf4; padding:8px 12px; border-radius:6px; margin-top:6px; border:1px solid #bbf7d0;">
            💡 <b>स्पष्टीकरण:</b> {{ item.explanation }}
        </div>
        {% endif %}
    </div>
    {% endfor %}

    <div class="feedback-card">
        <h4 style="margin:0; color:#065f46;">✍ आपला मौल्यवान अभिप्राय (Feedback) नोंदवा:</h4>
        {% if feedback_done %}
        <div style="background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-weight:bold; font-size:13px; margin-top:10px; text-align:center;">
            ✅ धन्यवाद! तुमचा अभिप्राय यशस्वीरीत्या नोंदवला गेला आहे.
        </div>
        {% else %}
        <form method="POST" action="/submit_feedback/{{ lead.id }}">
            <textarea name="feedback_text" rows="3" placeholder="येथे आपला अभिप्राय लिहा..." required></textarea>
            <button type="submit" class="btn-feedback">📩 अभिप्राय सबमिट करा</button>
        </form>
        {% endif %}
    </div>
</div>
</body>
</html>'''

# ----------------- 6. ADMIN DASHBOARD TEMPLATES (ALL 9 TABS FULL) -----------------
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
        .container { max-width: 1180px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
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
</head>
<body>
<div class="container">
    <h2>⚙️ राज्यस्तरीय परीक्षा प्लॅटफॉर्म - ॲडमिन डॅशबोर्ड</h2>
    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
        <a href="/" style="font-weight:bold; color:#0284c7; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a>
        <a href="/admin/logout" style="font-weight:bold; color:#dc2626; text-decoration:none;">🚪 लॉगआऊट</a>
    </div>

    <div class="nav-tabs">
        <a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 Leads (चौकशी व फिल्टर्स)</a>
        <a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 Payments & QR</a>
        <a href="/admin/dashboard?tab=special" class="{{ 'active' if active_tab == 'special' else '' }}">👑 Special Access</a>
        <a href="/admin/dashboard?tab=questions" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions (CSV & Bulk)</a>
        <a href="/admin/dashboard?tab=launch" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Test Management</a>
        <a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard</a>
        <a href="/admin/dashboard?tab=feedback" class="{{ 'active' if active_tab == 'feedback' else '' }}">💬 Feedback</a>
        <a href="/admin/dashboard?tab=notices" class="{{ 'active' if active_tab == 'notices' else '' }}">📢 Recruitment PDF</a>
        <a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Settings</a>
    </div>

    <!-- 1. LEADS TAB -->
    {% if active_tab == 'leads' %}
    <h3>📱 विद्यार्थ्यांची लीड्स यादी (जिल्हा व टेस्ट वाईस)</h3>
    <div style="background:#f8fafc; padding:12px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:15px;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <input type="hidden" name="tab" value="leads">
            <select name="lead_dist" style="width:160px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व जिल्हे --</option>
                {% for d in all_districts %}<option value="{{ d }}" {% if lead_dist==d %}selected{% endif %}>{{ d }}</option>{% endfor %}
            </select>
            <select name="lead_test_id" style="width:200px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व टेस्ट्स --</option>
                {% for t in tests %}<option value="{{ t.id }}" {% if lead_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <a href="/admin/dashboard?tab=leads" class="btn-sm" style="background:#64748b; color:white;">Clear</a>
        </form>
    </div>
    <table>
        <tr><th>दिनांक</th><th>विद्यार्थी नाव</th><th>जिल्हा</th><th>WhatsApp नंबर</th><th>टेस्टचे नाव</th><th>गुण</th><th>कृती</th></tr>
        {% for l in leads %}
        <tr>
            <td>{{ l.test_date }}</td>
            <td><b>{{ l.student_name }}</b></td>
            <td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td>
            <td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
            <td><a href="/admin/delete_lead/{{ l.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('लीड डिलीट करायची का?');">🗑️</a></td>
        </tr>
        {% endfor %}
    </table>

    <!-- 2. PAYMENTS TAB -->
    {% elif active_tab == 'payments' %}
    <h3>💰 पेमेंट व QR कोड व्यवस्थापन</h3>
    <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <form method="POST" action="/admin/update_payment_settings" enctype="multipart/form-data">
            <label style="font-weight:bold; font-size:12px;">पेमेंट मोबाईल नंबर / UPI ID:</label>
            <input type="text" name="upi_mobile" value="{{ upi_mobile }}" required>
            <label style="font-weight:bold; font-size:12px;">QR कोड URL किंवा नवीन इमेज:</label>
            <input type="text" name="qr_url" value="{{ qr_url }}">
            <input type="file" name="qr_file" accept="image/*" style="margin-bottom:10px;">
            <button type="submit" class="btn">💾 पेमेंट सेटिंग्ज अपडेट करा</button>
        </form>
    </div>
    <table>
        <tr><th>विद्यार्थी नाव</th><th>मोबाईल</th><th>टेस्ट</th><th>स्थिती</th><th>कृती</th></tr>
        {% for p in payments %}
        <tr>
            <td>{{ p.student_name }}</td>
            <td>{{ p.phone }}</td>
            <td>{{ p.test_name }}</td>
            <td><span style="color:{{ 'green' if p.payment_status == 'Approved' else 'orange' }}; font-weight:bold;">{{ p.payment_status }}</span></td>
            <td>
                {% if p.payment_status != 'Approved' %}
                <form method="POST" action="/admin/approve_payment/{{ p.id }}" style="display:inline-block;">
                    <button type="submit" class="btn-sm" style="background:#16a34a; color:white; border:none; padding:5px 10px; cursor:pointer;">✅ २४ तासांसाठी Unlock करा</button>
                </form>
                {% else %}
                <span style="color:green; font-weight:bold;">Active</span>
                {% endif %}
                <a href="/admin/delete_payment/{{ p.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('पेमेंट डिलीट करायचे का?');">🗑</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 3. SPECIAL ACCESS TAB -->
    {% elif active_tab == 'special' %}
    <h3>👑 Special Access (विशेष सवलत व्यवस्थापन)</h3>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
        <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:15px; border-radius:8px;">
            <h4 style="color:#065f46; margin-top:0;">🔄 १. अमर्याद प्रयत्न सवलत (Unlimited Attempts)</h4>
            <form method="POST" action="/admin/add_special_unlimited">
                <input type="text" name="phone" placeholder="१० अंकी मोबाईल नंबर" pattern="[6-9][0-9]{9}" required>
                <input type="text" name="student_name" placeholder="नाव">
                <input type="text" name="note" placeholder="टीप / संदर्भ">
                <button type="submit" class="btn" style="width:100%;">➕ अमर्याद सवलतीत जोडा</button>
            </form>
            <table>
                <tr><th>नंबर</th><th>नाव</th><th>कृती</th></tr>
                {% for u in unlimited_list %}
                <tr><td>{{ u.phone }}</td><td>{{ u.student_name }}</td><td><a href="/admin/delete_special_unlimited/{{ u.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑️</a></td></tr>
                {% endfor %}
            </table>
        </div>
        <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:15px; border-radius:8px;">
            <h4 style="color:#b45309; margin-top:0;">⭐ २. सशुल्क टेस्ट्स मोफत पास (Free Pass)</h4>
            <form method="POST" action="/admin/add_special_free_pass">
                <input type="text" name="phone" placeholder="१० अंकी मोबाईल नंबर" pattern="[6-9][0-9]{9}" required>
                <input type="text" name="student_name" placeholder="नाव">
                <input type="text" name="note" placeholder="टीप / संदर्भ">
                <button type="submit" class="btn" style="width:100%; background:#d97706;">➕ मोफत पास जोडा</button>
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
    <h3>📝 प्रश्न व्यवस्थापन (CSV Bulk Upload & Manual Form)</h3>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:20px;">
        <form method="POST" action="/admin/upload_csv_questions" enctype="multipart/form-data" style="background:#f0fdf4; border:2px dashed #059669; padding:15px; border-radius:8px;">
            <h4 style="margin:0 0 8px; color:#065f46;">📥 १०० प्रश्नांची CSV फाईल अपलोड करा:</h4>
            <label style="font-size:12px; font-weight:bold;">टेस्ट निवडा:</label>
            <select name="test_id" required>
                {% for t in tests %}<option value="{{ t.id }}">{{ t.test_title }}</option>{% endfor %}
            </select>
            <label style="font-size:12px; font-weight:bold;">CSV फाईल निवडा:</label>
            <input type="file" name="csv_file" accept=".csv" required style="margin-bottom:10px;">
            <button type="submit" class="btn" style="width:100%;">🚀 संपूर्ण १०० प्रश्न अपलोड करा</button>
        </form>

        <form method="POST" action="/admin/add_question" style="background:#f8fafc; padding:15px; border-radius:8px; border:1px solid #cbd5e1;">
            <h4 style="margin:0 0 8px; color:#065f46;">➕ एक प्रश्न टाईप करा:</h4>
            <select name="test_id">
                {% for t in tests %}<option value="{{ t.id }}">{{ t.test_title }}</option>{% endfor %}
            </select>
            <input type="text" name="question" placeholder="प्रश्न लिहा" required>
            <input type="text" name="opt_a" placeholder="पर्याय A" required>
            <input type="text" name="opt_b" placeholder="पर्याय B" required>
            <input type="text" name="opt_c" placeholder="पर्याय C" required>
            <input type="text" name="opt_d" placeholder="पर्याय D" required>
            <input type="text" name="correct" placeholder="अचूक उत्तर (A/B/C/D)" maxlength="1" required style="width:100px;">
            <input type="text" name="explanation" placeholder="स्पष्टीकरण">
            <button type="submit" class="btn">सेव्ह करा</button>
        </form>
    </div>

    <h4>प्रश्नांची यादी (एकूण प्रश्न: {{ all_questions|length }}):</h4>
    <table>
        <tr><th>ID</th><th>प्रश्न</th><th>अचूक</th><th>कृती</th></tr>
        {% for q in all_questions %}
        <tr>
            <td>{{ q.id }}</td>
            <td><b>{{ q.question }}</b></td>
            <td style="color:green; font-weight:bold;">{{ q.correct }}</td>
            <td><a href="/admin/delete_question/{{ q.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑️</a></td>
        </tr>
        {% endfor %}
    </table>

    <!-- 5. TEST MANAGEMENT TAB -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 नवीन टेस्ट लॉन्च करा व व्यवस्थापित करा</h3>
    <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <input type="text" name="test_title" placeholder="नवीन टेस्टचे नाव" required>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;">
            <select name="test_type">
                <option value="Free">Free (मोफत)</option>
                <option value="Paid">Paid (सशुल्क)</option>
            </select>
            <input type="number" name="test_fee" placeholder="फी (₹)" value="0">
            <input type="number" name="duration_minutes" placeholder="वेळ (मिनिटे)" value="60">
        </div>
        <button type="submit" class="btn">🚀 नवीन टेस्ट सेव्ह करा</button>
    </form>
    <table>
        <tr><th>ID</th><th>नाव</th><th>प्रकार</th><th>फी</th><th>स्थिती</th><th>कृती</th></tr>
        {% for t in tests %}
        <tr>
            <form method="POST" action="/admin/update_test/{{ t.id }}">
                <td>{{ t.id }}</td>
                <td><input type="text" name="test_title" value="{{ t.test_title }}" required style="margin-bottom:0;"></td>
                <td>
                    <select name="test_type" style="margin-bottom:0;">
                        <option value="Free" {% if t.test_type=='Free' %}selected{% endif %}>Free</option>
                        <option value="Paid" {% if t.test_type=='Paid' %}selected{% endif %}>Paid</option>
                    </select>
                </td>
                <td><input type="number" name="test_fee" value="{{ t.test_fee }}" style="width:75px; margin-bottom:0;"></td>
                <td>
                    <select name="status" style="margin-bottom:0;">
                        <option value="Active" {% if t.status=='Active' %}selected{% endif %}>Active</option>
                        <option value="Closed" {% if t.status=='Closed' %}selected{% endif %}>Closed</option>
                    </select>
                </td>
                <td>
                    <button type="submit" class="btn-sm" style="background:#0284c7; color:white; border:none; padding:5px 9px;">💾 अपडेट</button>
                    <a href="/admin/print_test/{{ t.id }}" target="_blank" class="btn-sm" style="background:#059669; color:white;">🖨️</a>
                    <a href="/admin/delete_test/{{ t.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑</a>
                </td>
            </form>
        </tr>
        {% endfor %}
    </table>

    <!-- 6. LEADERBOARD TAB -->
    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 राज्यस्तरीय लीडरबोर्ड (टॉप १०० विद्यार्थी)</h3>
    <table>
        <tr><th>रँक</th><th>विद्यार्थी नाव</th><th>जिल्हा</th><th>मोबाईल</th><th>टेस्ट</th><th>गुण</th></tr>
        {% for rank, l in top_leads %}
        <tr>
            <td><b>#{{ rank }}</b></td>
            <td>{{ l.student_name }}</td>
            <td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td>
            <td><b style="color:#059669;">{{ l.score }} / {{ l.total_marks }}</b></td>
        </tr>
        {% endfor %}
    </table>

    <!-- 7. FEEDBACK TAB -->
    {% elif active_tab == 'feedback' %}
    <h3>💬 विद्यार्थ्यांचे अभिप्राय (Feedback)</h3>
    <table>
        <tr><th>क्र.</th><th>दिनांक</th><th>विद्यार्थी</th><th>मोबाईल</th><th>अभिप्राय</th></tr>
        {% for f in feedbacks %}
        <tr>
            <td>{{ loop.index }}</td><td>{{ f.created_at }}</td><td><b>{{ f.student_name }}</b></td>
            <td><a href="https://wa.me/91{{ f.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ f.phone }}</a></td>
            <td>{{ f.feedback_text }}</td>
        </tr>
        {% endfor %}
    </table>

    <!-- 8. RECRUITMENT PDF TAB -->
    {% elif active_tab == 'notices' %}
    <h3>📢 भरती PDF व्यवस्थापन</h3>
    <form method="POST" action="/admin/update_pdf_docs" enctype="multipart/form-data">
        <label>भरती अधिकृत माहिती PDF:</label>
        <input type="file" name="recruitment_pdf_file" accept=".pdf">
        <label>भरती पात्रता PDF:</label>
        <input type="file" name="eligibility_pdf_file" accept=".pdf">
        <button type="submit" class="btn">सेव्ह करा</button>
    </form>

    <!-- 9. SETTINGS TAB -->
    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन पासवर्ड व सोशल सेटिंग्स</h3>
    <form method="POST" action="/admin/update_password">
        <label>नवा पासवर्ड:</label>
        <input type="password" name="new_password">
        <label>Instagram लिंक:</label>
        <input type="text" name="insta_link" value="{{ insta_link }}">
        <label>YouTube लिंक:</label>
        <input type="text" name="yt_link" value="{{ yt_link }}">
        <label>टॉपर फोटो लिंक:</label>
        <input type="text" name="toppers_link" value="{{ toppers_link }}">
        <button type="submit" class="btn">सेव्ह करा</button>
    </form>
    {% endif %}

</div>
</body>
</html>'''

# ----------------- 7. FLASK MAIN ROUTES & CONTROLLERS -----------------

@app.route('/')
def home_tests_list():
    is_admin = session.get('admin_logged', False)
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE status='Active' ORDER BY id ASC")
            tests = cur.fetchall()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_pdf'")
            r_row = cur.fetchone()
            recruitment_pdf = r_row['setting_value'] if r_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_pdf'")
            e_row = cur.fetchone()
            eligibility_pdf = e_row['setting_value'] if e_row else ''
    return render_template_string(HOME_TEMPLATE, tests=tests, recruitment_pdf=recruitment_pdf, eligibility_pdf=eligibility_pdf, is_admin=is_admin)

@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template_string(TERMS_TEMPLATE)

# शेअर बोनस क्लेम API (३ ग्रुप्सवर शेअर केल्यावर ५ टेस्ट्स मोफत अनलॉक)
@app.route('/api/claim_share_bonus', methods=['POST'])
def claim_share_bonus():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    if re.match(r'^[6-9]\d{9}$', phone):
        session['user_phone'] = phone
        c_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO shared_free_passes (phone, unlocked_until_test, created_at)
                    VALUES (%s, 5, %s)
                    ON CONFLICT (phone) DO UPDATE SET unlocked_until_test=5
                """, (phone, c_date))
                conn.commit()
        return jsonify({'status': 'success', 'unlocked_until': 5})
    return jsonify({'status': 'invalid_phone'}), 400

# परीक्षा सुरू करण्याचा राऊट (फक्त ५ टेस्ट्स मोफत तपासणीसह)
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

    # १. मोफत टेस्ट थेट सुरू होईल
    if test['test_type'] == 'Free':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

    # २. शेअर बोनस तपासणी: टेस्ट २ ते ५ पर्यंत मोफत ॲक्सेस
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

    # ३. सशुल्क टोकन तपासणी
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

    # टेस्ट ६ पासून पुढे किंवा ५ चा कोटा संपल्यावर थेट ₹९९ चा पेमेंट गेटवे
    return render_template_string(ACCESS_CHECK_TEMPLATE, test=test, qr_url=qr_url, upi_mobile=upi_mobile)

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

    return render_template_string('''<!DOCTYPE html><html lang="mr"><head><meta charset="UTF-8"><title>पेमेंट प्रलंबित</title></head>
    <body style="font-family:sans-serif; text-align:center; padding:50px; background:#f0fdf4;">
        <div style="max-width:450px; margin:auto; background:white; padding:30px; border-radius:10px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
            <h3 style="color:#d97706;">⏳ पडताळणी प्रलंबित आहे!</h3>
            <p style="font-size:14px; color:#475569;">स्क्रीनशॉट पडताळणीनंतर २४ तासांची संपूर्ण ५० टेस्ट्स ॲक्सेस लिंक तुमच्या WhatsApp वर पाठवली जाईल.</p>
            <a href="/" style="background:#059669; color:white; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:bold; display:inline-block; margin-top:15px;">🏠 मुख्य पानावर जा</a>
        </div>
    </body></html>''')

# --- टेस्ट सबमिशन व आक्रमक व्हायरल रिझल्ट रूट ---
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

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, whatsapp_verified, payment_status, score, total_marks, test_name, answers_json)
                VALUES (%s, %s, %s, %s, %s, 1, 'Approved', %s, %s, %s, %s) RETURNING id
            """, (test_id, t_date, student_name, district, phone, score, total, test['test_title'], ans_json_str))
            new_id = cur.fetchone()['id']

            cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s", (test_id, score))
            state_rank = cur.fetchone()['higher'] + 1
            conn.commit()

    main_portal_url = request.host_url.rstrip('/')
    result_url = main_portal_url + url_for('detailed_answers', lead_id=new_id)

    ego_msg = f"🏆 *महाराष्ट्र पोलीस भरती ओपन चॅलेंज* 🏆\\nमला १०० पैकी {score} गुण मिळाले आणि ऑल महाराष्ट्र रँक #{state_rank} आलाय!\\nमैदानावर ५० पैकी ५० मारले, लेखी परीक्षेत दम असेल तर मला हरवून दाखवा!\\n👉 टेस्ट लिंक: {main_portal_url}"
    ego_share_encoded = urllib.parse.quote(ego_msg)

    ref_msg = f"🎁 मित्रांनो, पोलीस भरती १०० गुणांचा सराव पेपर मोफत सोडवा आणि रँक तपासा! ५ मित्रांनी टेस्ट दिल्यास ₹९९ ची संपूर्ण सिरीज मोफत मिळेल:\\n👉 {main_portal_url}"
    referral_share_encoded = urllib.parse.quote(ref_msg)

    return render_template_string(
        RESULT_SUMMARY_TEMPLATE,
        lead={'student_name': student_name, 'district': district, 'phone': phone, 'test_name': test['test_title'], 'score': score, 'total_marks': total},
        state_rank=state_rank,
        result_url=result_url,
        main_portal_url=main_portal_url,
        ego_share_encoded=ego_share_encoded,
        referral_share_encoded=referral_share_encoded
    )

@app.route('/detailed_answers/<int:lead_id>')
def detailed_answers(lead_id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead: return "Result not found", 404

            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (lead['test_id'],))
            questions = cur.fetchall()

            cur.execute("SELECT COUNT(*) as cnt FROM student_feedbacks WHERE lead_id=%s", (lead_id,))
            feedback_done = cur.fetchone()['cnt'] > 0

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

    return render_template_string(
        DETAILED_KEY_TEMPLATE, 
        lead=lead, 
        evaluated_questions=evaluated_questions, 
        feedback_done=feedback_done
    )

@app.route('/submit_feedback/<int:lead_id>', methods=['POST'])
def submit_feedback(lead_id):
    fb_text = request.form.get('feedback_text', '').strip()
    if fb_text:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT student_name, phone FROM mock_test_leads WHERE id=%s", (lead_id,))
                lead = cur.fetchone()
                if lead:
                    c_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                    cur.execute("""
                        INSERT INTO student_feedbacks (lead_id, student_name, phone, feedback_text, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (lead_id, lead['student_name'], lead['phone'], fb_text, c_date))
                    conn.commit()
    return redirect(f'/detailed_answers/{lead_id}')

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
            r = cur.fetchone()
            qr_url = r['setting_value'] if r else ''

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='upi_mobile'")
            r = cur.fetchone()
            upi_mobile = r['setting_value'] if r else '9921111960'

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            toppers_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_pdf'")
            recruitment_pdf = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_pdf'")
            eligibility_pdf = cur.fetchone()['setting_value']

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
        insta_link=insta_link,
        yt_link=yt_link,
        toppers_link=toppers_link,
        recruitment_pdf=recruitment_pdf,
        eligibility_pdf=eligibility_pdf
    )

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

@app.route('/admin/delete_question/<int:q_id>')
def admin_delete_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM questions WHERE id=%s", (q_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title')
    ttype = request.form.get('test_type')
    fee = float(request.form.get('test_fee', 0))
    duration = int(request.form.get('duration_minutes', 60))
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status) VALUES (%s, %s, %s, %s, 'Active')", (title, ttype, fee, duration))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/update_test/<int:test_id>', methods=['POST'])
def admin_update_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    ttype = request.form.get('test_type', 'Free')
    fee = float(request.form.get('test_fee', 0))
    duration = int(request.form.get('duration_minutes', 60))
    status = request.form.get('status', 'Active')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE test_papers 
                SET test_title=%s, test_type=%s, test_fee=%s, duration_minutes=%s, status=%s 
                WHERE id=%s
            """, (title, ttype, fee, duration, status, test_id))
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

@app.route('/admin/approve_payment/<int:lead_id>', methods=['POST'])
def admin_approve_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    token = secrets.token_hex(8)
    expires = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE mock_test_leads 
                SET payment_status='Approved', access_token=%s, token_expires_at=%s 
                WHERE id=%s RETURNING test_id, phone
            """, (token, expires, lead_id))
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
    insta = request.form.get('insta_link', '')
    yt = request.form.get('yt_link', '')
    top = request.form.get('toppers_link', '')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if new_pass:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
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
        <hr>
        <ol>{ "".join([f"<li style='margin-bottom:15px;'><b>{q['question']}</b><br>A) {q['opt_a']}&nbsp;&nbsp;&nbsp;B) {q['opt_b']}&nbsp;&nbsp;&nbsp;C) {q['opt_c']}&nbsp;&nbsp;&nbsp;D) {q['opt_d']}<br><small style='color:green;'>अचूक उत्तर: {q['correct']} | स्पष्टीकरण: {q['explanation']}</small></li>" for q in questions]) }</ol>
        <script>window.print();</script>
    </body></html>'''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
