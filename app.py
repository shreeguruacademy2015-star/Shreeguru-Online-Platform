import json
import os
from datetime import date, datetime, timedelta
from flask import Flask, redirect, render_template_string, request, session, url_for, send_from_directory
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_master_test_platform_2026_ultimate_safe"

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- NEON CLOUD DATABASE CONNECTION ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_master_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS test_papers (
                id SERIAL PRIMARY KEY,
                test_title TEXT NOT NULL,
                test_type TEXT DEFAULT 'Free',
                test_fee REAL DEFAULT 0,
                duration_minutes INTEGER DEFAULT 60,
                status TEXT DEFAULT 'Active'
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
                otp_code TEXT DEFAULT '',
                valid_until TEXT DEFAULT ''
            )''')

            cur.execute('''CREATE TABLE IF NOT EXISTS academy_settings (
                id SERIAL PRIMARY KEY,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL
            )''')

            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('qr_code_url', 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=ShreeguruUPIpayment') ON CONFLICT (setting_key) DO NOTHING")
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('upi_mobile', '9921111960') ON CONFLICT (setting_key) DO NOTHING")
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('admin_pass', 'shreeguru2026') ON CONFLICT (setting_key) DO NOTHING")
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('admin_phone', '9921111960') ON CONFLICT (setting_key) DO NOTHING")
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('admin_otp', '') ON CONFLICT (setting_key) DO NOTHING")
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('insta_link', '') ON CONFLICT (setting_key) DO NOTHING")
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('yt_link', '') ON CONFLICT (setting_key) DO NOTHING")
            cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES ('toppers_link', '') ON CONFLICT (setting_key) DO NOTHING")

            cur.execute('SELECT COUNT(*) as count FROM test_papers')
            if cur.fetchone()['count'] == 0:
                cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active')")
                cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (2, 'आर्मी भरती बौद्धिक व गणित टेस्ट #२', 'Paid', 49, 45, 'Active')")
                conn.commit()

            cur.execute('SELECT COUNT(*) as count FROM questions')
            if cur.fetchone()['count'] == 0:
                default_qs = [
                    (1, "महाराष्ट्राची आर्थिक व व्यापारी राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B", "मुंबई ही महाराष्ट्राची आर्थिक व व्यापारी राजधानी आहे."),
                    (1, "क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A", "अहमदनगर हा क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा आहे."),
                    (2, "भारताचे राष्ट्रीय गीत कोणते?", "जन गण मन", "वंदे मातरम्", "सारा जहाँ से अच्छा", "जय हिंद", "B", "वंदे मातरम् हे बंकिमचंद्र चटोपाध्याय यांनी रचलेले भारताचे राष्ट्रीय गीत आहे.")
                ]
                cur.executemany('INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', default_qs)
                conn.commit()

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
        .top-bar { max-width: 750px; margin: 0 auto 10px; display: flex; justify-content: space-between; align-items: center; background: white; padding: 10px 15px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
        .clock { font-weight: bold; color: #065f46; font-size: 14px; }
        .box { max-width: 750px; margin: 0 auto; background: white; border-radius: 14px; padding: 25px; box-shadow: 0 12px 30px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 26px; font-family: 'Baloo Bhaina 2', cursive; }
        .quote-box { background: #ecfdf5; border-left: 4px solid #059669; padding: 12px 15px; border-radius: 6px; font-size: 15px; color: #065f46; font-weight: 600; text-align: center; margin-bottom: 25px; }
        .test-card { background: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 10px; padding: 18px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; transition: 0.2s; }
        .test-card:hover { border-color: #059669; box-shadow: 0 4px 12px rgba(5,150,105,0.1); }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; box-shadow: 0 3px 8px rgba(5,150,105,0.3); }
        .badge-free { background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-paid { background: #fef9c3; color: #854d0e; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }
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
    <div><a href="/admin/login" style="background:#0f172a; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">⚙ ॲडमिन लॉगिन</a></div>
</div>

<div class="box">
    <h2>⚔️ राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</h2>

    <div class="quote-box">
        🔥 राहिलेल्या दिवसात काबाड कष्ट करायचे आणि वर्दीचे स्वप्न पूर्ण करायचे! 🌟
    </div>

    <p style="font-size:15px; font-weight:600; color:#0b3c5d; margin-bottom:20px; border-bottom:2px solid #e2e8f0; padding-bottom:8px; text-align:center;">
        खालील प्रश्नपत्रिका सोडवा आणि संपूर्ण राज्यात तुमचा रँक तपासा
    </p>

    {% for t in tests %}
    <div class="test-card">
        <div>
            <h4 style="margin:0 0 6px; color:#0f172a; font-size:17px; font-family:'Baloo Bhaina 2', cursive;">{{ t.test_title }}</h4>
            <span class="{{ 'badge-free' if t.test_type == 'Free' else 'badge-paid' }}">
                {{ '🟢 मोफत महासराव टेस्ट' if t.test_type == 'Free' else '⭐ सशुल्क (Paid) टेस्ट - ₹' ~ t.test_fee }}
            </span>
            <div style="font-size:12px; color:#64748b; margin-top:4px;">⏱️ वेळ मर्यादा: {{ t.duration_minutes }} मिनिटे</div>
        </div>
        <a href="/take_test/{{ t.id }}" class="btn-start">✨ टेस्ट सोडवा</a>
    </div>
    {% endfor %}
</div>
</body>
</html>'''

# ----------------- 2. PAID ACCESS CHECK OR EXAM TEMPLATE -----------------
ACCESS_CHECK_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>पेमेंट पडताळणी - {{ test.test_title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .box { max-width: 500px; width: 100%; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 20px; }
        input[type="text"], input[type="tel"] { width: 100%; padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
        .btn { width: 100%; background: #059669; color: white; padding: 12px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 15px; }
    </style>
</head>
<body>
<div class="box">
    <h2>🔒 सशुल्क टेस्ट प्रवेश द्वार</h2>
    <p style="text-align:center; font-size:13px; color:#475569;">{{ test.test_title }} (फी: ₹{{ test.test_fee }})</p>
    
    {% if error %}<div style="color:red; font-size:12px; font-weight:bold; text-align:center; margin-bottom:10px;">{{ error }}</div>{% endif %}
    
    <div style="background:#fffbeb; padding:15px; border-radius:6px; border:1px solid #fcd34d; text-align:center; margin-bottom:15px;">
        <p style="margin:0 0 10px; font-weight:bold; color:#92400e; font-size:13px;">QR कोड स्कॅन करून किंवा <b>{{ upi_mobile }}</b> वर पे करा:</p>
        {% if qr_url.startswith('/') %}
        <img src="{{ qr_url }}" alt="QR" style="width:140px; height:140px; border-radius:6px; border:1px solid #cbd5e1;">
        {% else %}
        <img src="{{ qr_url }}" alt="QR" style="width:140px; height:140px; border-radius:6px; border:1px solid #cbd5e1;">
        {% endif %}
        <p style="font-size:12px; color:#b45309; font-weight:bold; margin-top:8px;">⚠️ पेमेंट करून झाल्यावर <b>{{ upi_mobile }}</b> या नंबरवर आपले नाव व पेमेंट स्क्रीनशॉट पाठवा!</p>
    </div>

    <form method="POST" action="/request_paid_test/{{ test.id }}">
        <label style="font-size:13px; font-weight:bold;">पूर्ण नाव:</label>
        <input type="text" name="student_name" placeholder="तुमचे नाव" required>
        <label style="font-size:13px; font-weight:bold;">जिल्हा:</label>
        <input type="text" name="district" placeholder="जिल्हा" required>
        <label style="font-size:13px; font-weight:bold;">व्हॉट्सॲप मोबाईल नंबर:</label>
        <input type="tel" name="phone" placeholder="१० अंकी मोबाईल नंबर" pattern="[0-9]{10}" required>
        <label style="font-size:13px; font-weight:bold;">UTR / UPI Ref Number:</label>
        <input type="text" name="utr_number" placeholder="पेमेंट ट्रान्झॅक्शन आयडी टाका" required>
        <button type="submit" class="btn">🚀 ॲडमिनकडे अप्रूवलसाठी पाठवा</button>
    </form>
    <div style="text-align:center; margin-top:15px;"><a href="/" style="font-size:12px; color:#0284c7; text-decoration:none;">⬅️ मुख्य पानावर जा</a></div>
</div>
</body>
</html>'''

OTP_VERIFY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OTP पडताळणी - राज्यस्तरीय प्लॅटफॉर्म</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .box { max-width: 450px; width: 100%; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 6px solid #059669; text-align: center; }
        input[type="text"] { width: 100%; padding: 12px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-bottom: 12px; font-size: 18px; text-align: center; letter-spacing: 3px; font-weight: bold; }
        .btn { width: 100%; background: #059669; color: white; padding: 12px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 15px; }
    </style>
</head>
<body>
<div class="box">
    <h2>🔐 व्हॉट्सॲप OTP पडताळणी</h2>
    <p style="font-size:13px; color:#475569;">ॲडमिनने तुमचे पेमेंट अप्रूव केले आहे. तुमच्या व्हॉट्सॲपवर पाठवलेला 4 अंकी OTP खाली टाका:</p>
    {% if error %}<div style="color:red; font-size:12px; font-weight:bold; margin-bottom:10px;">{{ error }}</div>{% endif %}
    <form method="POST">
        <input type="text" name="entered_otp" placeholder="XXXX" maxlength="4" required>
        <button type="submit" class="btn">✅ OTP तपासा व टेस्ट सुरू करा</button>
    </form>
</div>
</body>
</html>'''

EXAM_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ test.test_title }} - राज्यस्तरीय परीक्षा कक्ष</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #eef2f7; color: #1e293b; padding: 10px; }
        .exam-header { background: #065f46; color: white; padding: 12px 20px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; max-width: 800px; margin: 0 auto 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        .box { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border-top: 5px solid #059669; }
        .timer-box { background: #fee2e2; border: 2px solid #ef4444; color: #991b1b; padding: 8px 15px; border-radius: 6px; font-weight: bold; font-size: 15px; display: inline-block; }
        .q-item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; margin-bottom: 18px; }
        .q-text { font-weight: bold; margin-bottom: 10px; font-size: 15px; color: #0f172a; }
        .opt-label { display: block; margin-bottom: 8px; font-size: 14px; cursor: pointer; background: white; padding: 8px 12px; border-radius: 6px; border: 1px solid #e2e8f0; }
        .opt-label:hover { background: #f1f5f9; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #059669, #047857); color: white; padding: 14px; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 12px rgba(5,150,105,0.3); }
    </style>
    <script>
        let timeLeft = {{ test.duration_minutes * 60 }};
        function startTimer() {
            const timerDisplay = document.getElementById('time-left');
            let timer = setInterval(function () {
                let minutes = parseInt(timeLeft / 60, 10);
                let seconds = parseInt(timeLeft % 60, 10);
                minutes = minutes < 10 ? "0" + minutes : minutes;
                seconds = seconds < 10 ? "0" + seconds : seconds;
                timerDisplay.innerText = minutes + ":" + seconds;
                if (--timeLeft < 0) {
                    clearInterval(timer);
                    alert("⏰ वेळ संपली! तुमची टेस्ट ऑटोमॅटिक सबमिट होत आहे.");
                    document.getElementById("examForm").submit();
                }
            }, 1000);
        }
        window.onload = startTimer;
    </script>
</head>
<body>
<div class="exam-header">
    <div>
        <h3 style="margin:0; font-size:18px;">⚔️ {{ test.test_title }}</h3>
        <small style="opacity:0.9;">राज्यस्तरीय पोलीस भरती सराव परीक्षा कक्ष</small>
    </div>
    <div class="timer-box">
        ⏳ वेळ: <span id="time-left">00:00</span>
    </div>
</div>

<div class="box">
    <form id="examForm" method="POST" action="/submit_test/{{ test.id }}">
        {% for q in questions %}
        <div class="q-item">
            <div class="q-text">प्र. {{ loop.index }}. {{ q.question }}</div>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="A" required> A) {{ q.opt_a }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="B"> B) {{ q.opt_b }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="C"> C) {{ q.opt_c }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="D"> D) {{ q.opt_d }}</label>
        </div>
        {% endfor %}

        <button type="submit" class="btn-submit">✅ टेस्ट सबमिट करा</button>
    </form>
</div>
</body>
</html>'''

# ----------------- 3. RESULT & CERTIFICATE TEMPLATE -----------------
RESULT_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>टेस्ट निकाल - राज्यस्तरीय प्लॅटफॉर्म</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; }
        .box { max-width: 750px; margin: 20px auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 24px; }
        .sub { text-align: center; color: #475569; font-size: 13px; margin-bottom: 25px; }
        .cert-box { background: linear-gradient(135deg, #fefce8, #fef3c7); border: 4px double #d97706; padding: 25px; border-radius: 10px; text-align: center; margin-top: 25px; }
        .promo-box { background: #f0fdf4; border: 2px dashed #059669; padding: 15px; border-radius: 8px; text-align: center; margin-top: 20px; }
        .btn-link { display: inline-block; background: #25D366; color: white; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 13px; margin: 4px; }
    </style>
</head>
<body>
<div class="box">
    <h2>⚔️ राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</h2>
    <div class="sub">परीक्षेचा निकाल व प्रशस्तीपत्र डॅशबोर्ड</div>

    <div style="background:#f0fdf4; border:2px solid #86efac; border-radius:8px; padding:20px; text-align:center; margin-bottom:20px;">
        <h3 style="margin:0 0 5px; color:#166534;">टेस्ट यशस्वीरीत्या पूर्ण झाली! 🎉</h3>
        <p style="font-size:16px; margin:8px 0;">विद्यार्थ्याचे नाव: <b>{{ lead.student_name }}</b> (जिल्हा: {{ lead.district }})</p>
        <p style="font-size:20px; margin:8px 0;">प्राप्त गुण: <b style="color:#059669; font-size:26px;">{{ lead.score }} / {{ lead.total_marks }}</b></p>
        <p style="font-size:16px; color:#b45309; font-weight:bold; margin-top:10px;">
            🏆 अभिनंदन! तुम्ही संपूर्ण महाराष्ट्रातील विद्यार्थ्यांमध्ये <b style="font-size:20px; color:#92400e;">क्र. #{{ state_rank }}</b> क्रमांकाने यशस्वी झाला आहात! 🌟
        </p>
    </div>

    <!-- DIGITAL CERTIFICATE -->
    <div class="cert-box">
        <h3 style="color:#92400e; margin:0 0 5px;">📜 सहभाग व अभिनंदनपर डिजिटल प्रशस्तीपत्र (Certificate)</h3>
        <p style="font-size:12px; color:#78350f; margin-bottom:15px;">राज्यस्तरीय ऑनलाईन प्लॅटफॉर्म तर्फे गुणवंत विद्यार्थ्यांसाठी गौरवास्पद प्रमाणपत्र</p>
        <div style="background:white; padding:15px; border-radius:6px; border:1px dashed #b45309;">
            <p style="font-size:13px; margin:5px 0;">प्रमाणित करण्यात येते की,</p>
            <h2 style="color:#065f46; margin:5px 0; font-size:22px;">{{ lead.student_name }}</h2>
            <p style="font-size:13px; margin:5px 0;">यांनी <b>{{ lead.test_name }}</b> मध्ये सहभाग घेऊन उत्तम यश मिळवले आहे.</p>
            <p style="font-size:12px; color:#555; margin-top:10px;">— परीक्षा नियंत्रक, राज्यस्तरीय पोलीस भरती सराव कक्ष</p>
        </div>
    </div>

    <!-- SOCIAL & ACADEMY LINKS PROMO -->
    <div class="promo-box">
        <h4 style="margin:0 0 8px; color:#065f46;">🌟 आमच्या अधिकृत सोशल मीडिया व यशोगाथा लिंक्स:</h4>
        <p style="font-size:12px; color:#334155; margin-bottom:12px;">पुढील अपडेट्स, चालू घडामोडी आणि यशस्वी विद्यार्थ्यांच्या मुलाखतींसाठी खालील लिंक्स जॉईन करा:</p>
        {% if insta_link %}<a href="{{ insta_link }}" target="_blank" class="btn-link" style="background:#E1306C;">📸 Instagram Join</a>{% endif %}
        {% if yt_link %}<a href="{{ yt_link }}" target="_blank" class="btn-link" style="background:#FF0000;">▶️ YouTube Channel</a>{% endif %}
        {% if toppers_link %}<a href="{{ toppers_link }}" target="_blank" class="btn-link" style="background:#0284c7;">🏆 यशस्वी विद्यार्थ्यांचे फोटो पहा</a>{% endif %}
    </div>

    <!-- ANSWER KEY & EXPLANATIONS -->
    <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:20px; border-radius:8px; margin-top:20px;">
        <h3 style="color:#065f46; margin-top:0;">📋 सविस्तर उत्तरपत्रिका व स्पष्टीकरण (Answer Key)</h3>
        {% for item in evaluated_questions %}
        <div style="background:white; border:1px solid {{ '#bbf7d0' if item.is_correct else '#fecaca' }}; padding:12px; border-radius:6px; margin-bottom:12px;">
            <div style="font-weight:bold; font-size:14px; margin-bottom:6px;">प्र. {{ loop.index }}. {{ item.q_text }}</div>
            <div style="font-size:13px; margin-bottom:4px;">तुम्ही दिलेला पर्याय: <b style="color:{{ 'green' if item.is_correct else 'red' }};">{{ item.user_ans }}</b> | अचूक उत्तर: <b style="color:green;">{{ item.correct_ans }}</b></div>
            {% if item.explanation %}
            <div style="font-size:12px; color:#166534; background:#f0fdf4; padding:6px; border-radius:4px; margin-top:6px;">💡 स्पष्टीकरण: {{ item.explanation }}</div>
            {% endif %}
        </div>
        {% endfor %}
        <div style="text-align:center; margin-top:20px;">
            <a href="/" style="background:#0284c7; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold;">🏠 मुख्य प्लॅटफॉर्मकडे जा</a>
        </div>
    </div>
</div>
</body>
</html>'''

# ----------------- 4. ADMIN LOGIN & FORGOT TEMPLATE (With Show/Hide Password) -----------------
ADMIN_LOGIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ॲडमिन लॉगिन - राज्यस्तरीय प्लॅटफॉर्म</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #0f172a; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-box { background: #1e293b; padding: 30px; border-radius: 10px; width: 380px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); border-top: 5px solid #059669; }
        h2 { text-align: center; color: #34d399; margin-top: 0; }
        .pass-group { position: relative; width: 100%; margin: 10px 0 15px; }
        input { width: 100%; padding: 10px; border-radius: 5px; border: 1px solid #475569; background: #0f172a; color: white; font-size: 14px; text-align: center; }
        .eye-btn { position: absolute; right: 10px; top: 10px; background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 16px; }
        button { width: 100%; background: #059669; color: white; border: none; padding: 10px; border-radius: 5px; font-weight: bold; cursor: pointer; }
        .err { color: #f87171; font-size: 12px; text-align: center; margin-bottom: 10px; }
        .succ { color: #34d399; font-size: 12px; text-align: center; margin-bottom: 10px; }
    </style>
    <script>
        function togglePassword() {
            var passInput = document.getElementById("admin_pass");
            var eyeBtn = document.getElementById("eyeIcon");
            if (passInput.type === "password") {
                passInput.type = "text";
                eyeBtn.innerText = "🙈";
            } else {
                passInput.type = "password";
                eyeBtn.innerText = "👁️";
            }
        }
    </script>
</head>
<body>
<div class="login-box">
    <h2>⚙️ ॲडमिन लॉगिन</h2>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    {% if success %}<div class="succ">{{ success }}</div>{% endif %}
    
    {% if not otp_sent %}
    <form method="POST" action="/admin/login">
        <label style="font-size:13px;">पासवर्ड टाका:</label>
        <div class="pass-group">
            <input type="password" name="admin_pass" id="admin_pass" placeholder="पासवर्ड" required>
            <button type="button" class="eye-btn" id="eyeIcon" onclick="togglePassword()">👁️</button>
        </div>
        <button type="submit">लॉगिन करा</button>
    </form>
    <div style="margin-top:15px; border-top:1px solid #334155; padding-top:12px; text-align:center;">
        <form method="POST" action="/admin/forgot_password">
            <button type="submit" style="background:#d97706; font-size:12px; padding:8px;">🔑 पासवर्ड विसरलात? (WhatsApp वर OTP मिळवा)</button>
        </form>
    </div>
    {% else %}
    <form method="POST" action="/admin/verify_otp">
        <label style="font-size:13px; color:#34d399;">WhatsApp वर पाठवलेला 4 अंकी OTP टाका:</label>
        <input type="text" name="entered_otp" placeholder="XXXX" maxlength="4" required style="letter-spacing: 4px; font-weight: bold; font-size: 18px;">
        <button type="submit" style="background:#25D366;">📲 OTP तपासा व लॉगिन करा</button>
    </form>
    {% endif %}

    <div style="text-align:center; margin-top:15px;"><a href="/" style="color:#38bdf8; font-size:12px; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a></div>
</div>
</body>
</html>'''

# ----------------- 5. ADMIN DASHBOARD TEMPLATE -----------------
ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ॲडमिन डॅशबोर्ड - राज्यस्तरीय प्लॅटफॉर्म</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f1f5f9; color: #1e293b; padding: 15px; }
        .container { max-width: 1100px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
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
            if (p.type === "password") { p.type = "text"; } else { p.type = "password"; }
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

    <!-- MASTER SUB-TABS -->
    <div class="nav-tabs">
        <a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 Leads (चौकशी)</a>
        <a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 Payments & QR (पेमेंट्स व QR)</a>
        <a href="/admin/dashboard?tab=questions" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions (प्रश्न व्यवस्थापन)</a>
        <a href="/admin/dashboard?tab=launch" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Test Launch (टेस्ट लॉन्च)</a>
        <a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard (टॉपर लिस्ट)</a>
        <a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Security & Links (सेटिंग्स व लिंक्स)</a>
    </div>

    <!-- 1. LEADS SUB-TAB -->
    {% if active_tab == 'leads' %}
    <h3>📱 सर्व विद्यार्थ्यांची टेस्ट माहिती, कॉन्टॅक्ट्स व लीड्स व्यवस्थापन</h3>
    <table>
        <tr><th>दिनांक</th><th>विद्यार्थी नाव</th><th>जिल्हा</th><th>मोबाईल नंबर (WhatsApp)</th><th>टेस्टचे नाव</th><th>गुण</th><th>कृती</th></tr>
        {% for l in leads %}
        <tr>
            <td>{{ l.test_date }}</td>
            <td><b>{{ l.student_name }}</b></td>
            <td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td>
            <td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
            <td>
                <a href="/admin/delete_lead/{{ l.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('ही लीड डिलीट करायची का?');">🗑️ डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 2. PAYMENTS SUB-TAB -->
    {% elif active_tab == 'payments' %}
    <h3>💰 पेमेंट वैधता डेस्क, युपीआय नंबर आणि QR कोड अपलोड व्यवस्थापन</h3>
    <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <h4 style="margin:0 0 10px; color:#065f46;">💳 पेमेंट मोबाईल नंबर व नवीन QR कोड इमेज अपलोड करा:</h4>
        <form method="POST" action="/admin/update_payment_settings" enctype="multipart/form-data">
            <label style="font-weight:bold; font-size:12px;">पेमेंट मोबाईल नंबर / UPI ID:</label>
            <input type="text" name="upi_mobile" value="{{ upi_mobile }}" required>
            <label style="font-weight:bold; font-size:12px;">QR कोड इमेज फाईल अपलोड करा (JPG/PNG):</label>
            <input type="file" name="qr_file" accept="image/*" style="margin-bottom:10px;">
            <button type="submit" class="btn" style="margin-top:5px;">💾 पेमेंट सेटिंग्ज अपडेट करा</button>
        </form>
    </div>

    <table>
        <tr><th>विद्यार्थी नाव</th><th>मोबाईल</th><th>टेस्ट</th><th>UTR / Ref Number</th><th>वैधता (Validity)</th><th>स्थिती</th><th>कृती</th></tr>
        {% for p in payments %}
        <tr>
            <td>{{ p.student_name }}</td>
            <td>{{ p.phone }}</td>
            <td>{{ p.test_name }}</td>
            <td><b>{{ p.utr_number if p.utr_number else 'N/A' }}</b></td>
            <td>{{ p.valid_until if p.valid_until else 'अजून नाही' }}</td>
            <td><span style="color:{{ 'green' if p.payment_status == 'Approved' else 'orange' }}; font-weight:bold;">{{ p.payment_status }}</span></td>
            <td>
                {% if p.payment_status != 'Approved' %}
                <form method="POST" action="/admin/approve_payment/{{ p.id }}" style="display:inline-flex; gap:5px; align-items:center;">
                    <select name="validity_days" style="padding:4px; margin-bottom:0; font-size:11px;" required>
                        <option value="1">१ दिवस</option>
                        <option value="7">७ दिवस</option>
                        <option value="30" selected>३० दिवस</option>
                        <option value="365">१ वर्ष</option>
                    </select>
                    <button type="submit" class="btn-sm" style="background:#16a34a; color:white; border:none; padding:5px 8px; cursor:pointer;">✅ Approve</button>
                </form>
                {% else %}
                <span style="color:green; font-weight:bold;">Approved</span>
                {% endif %}
                <a href="/admin/delete_payment/{{ p.id }}" class="btn-sm" style="background:#dc2626; color:white; margin-left:5px;" onclick="return confirm('ही पेमेंट नोंद डिलीट करायची का?');">🗑️ डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 3. QUESTIONS SUB-TAB -->
    {% elif active_tab == 'questions' %}
    <h3>📝 प्रश्न व्यवस्थापन (Test-wise Filter, Single & Errorless Bulk Upload)</h3>
    
    <div style="background:#ecfdf5; padding:12px; border-radius:6px; margin-bottom:20px; border:1px solid #a7f3d0;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; align-items:center;">
            <input type="hidden" name="tab" value="questions">
            <label style="font-weight:bold; font-size:13px; color:#065f46;">प्रश्न पाहण्यासाठी टेस्ट निवडा:</label>
            <select name="filter_test_id" onchange="this.form.submit()" style="max-width:300px; margin-bottom:0;">
                <option value="">-- सर्व टेस्ट्सचे प्रश्न --</option>
                {% for t in tests %}
                <option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                {% endfor %}
            </select>
        </form>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:25px;">
        <form method="POST" action="/admin/add_question" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
            <h4 style="margin-top:0; color:#065f46;">➕ एक प्रश्न ॲड करा</h4>
            <label style="font-weight:bold; font-size:12px;">टेस्ट निवडा:</label>
            <select name="test_id">
                {% for t in tests %}<option value="{{ t.id }}">{{ t.test_title }}</option>{% endfor %}
            </select>
            <label style="font-weight:bold; font-size:12px;">प्रश्न:</label>
            <input type="text" name="question" placeholder="प्रश्नाची माहिती लिहा" required>
            <input type="text" name="opt_a" placeholder="पर्याय A" required>
            <input type="text" name="opt_b" placeholder="पर्याय B" required>
            <input type="text" name="opt_c" placeholder="पर्याय C" required>
            <input type="text" name="opt_d" placeholder="पर्याय D" required>
            <label style="font-weight:bold; font-size:12px;">अचूक उत्तर (A, B, C किंवा D):</label>
            <input type="text" name="correct" placeholder="उदा. B" maxlength="1" required style="width:100px;">
            <label style="font-weight:bold; font-size:12px;">स्पष्टीकरण:</label>
            <input type="text" name="explanation" placeholder="स्पष्टीकरण लिहा">
            <button type="submit" class="btn" style="margin-top:5px;">प्रश्न सेव्ह करा</button>
        </form>

        <form method="POST" action="/admin/bulk_questions" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
            <h4 style="margin-top:0; color:#065f46;">⚡ एररलेस बल्क (Bulk) प्रश्न अपलोड</h4>
            <label style="font-weight:bold; font-size:12px;">टेस्ट निवडा:</label>
            <select name="test_id">
                {% for t in tests %}<option value="{{ t.id }}">{{ t.test_title }}</option>{% endfor %}
            </select>
            <label style="font-weight:bold; font-size:12px;">फॉरमॅट: प्रश्न | पर्यायA | पर्यायB | पर्यायC | पर्यायD | अचूक | स्पष्टीकरण</label>
            <textarea name="bulk_data" rows="8" placeholder="महाराष्ट्राची राजधानी कोणती? | पुणे | मुंबई | नागपूर | नाशिक | B | मुंबई ही राजधानी आहे." required style="font-size:12px;"></textarea>
            <button type="submit" class="btn" style="margin-top:5px; background:#0284c7;">⚡ सर्व प्रश्न एररलेस अपलोड करा</button>
        </form>
    </div>

    <h4>सध्याच्या निवडीनुसार प्रश्न यादी व कृती:</h4>
    <table>
        <tr><th>ID</th><th>टेस्ट ID</th><th>प्रश्न</th><th>अचूक उत्तर</th><th>कृती</th></tr>
        {% for q in all_questions %}
        <tr>
            <td>{{ q.id }}</td>
            <td>{{ q.test_id }}</td>
            <td><b>{{ q.question }}</b></td>
            <td style="color:green; font-weight:bold;">{{ q.correct }}</td>
            <td>
                <a href="/admin/delete_question/{{ q.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('हा प्रश्न डिलीट करायचा आहे का?');">🗑️ डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 4. TEST LAUNCH SUB-TAB -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 नवीन टेस्ट लॉन्च व व्यवस्थापन (Print / Edit / Status Toggle)</h3>
    <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <label style="font-weight:bold; font-size:12px;">नवीन टेस्टचे नाव:</label>
        <input type="text" name="test_title" placeholder="उदा. पोलीस भरती विशेष टेस्ट #३" required>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;">
            <div>
                <label style="font-weight:bold; font-size:12px;">प्रकार:</label>
                <select name="test_type">
                    <option value="Free">Free (मोफत)</option>
                    <option value="Paid">Paid (सशुल्क)</option>
                </select>
            </div>
            <div>
                <label style="font-weight:bold; font-size:12px;">फी (रुपये):</label>
                <input type="number" name="test_fee" value="0">
            </div>
            <div>
                <label style="font-weight:bold; font-size:12px;">वेळ (मिनिटे):</label>
                <input type="number" name="duration_minutes" value="60">
            </div>
        </div>
        <button type="submit" class="btn" style="margin-top:5px;">🚀 नवीन टेस्ट लॉन्च करा</button>
    </form>

    <h4>सध्याच्या लाईव्ह टेस्ट्स, वेळ व स्टेटस बदला:</h4>
    <table>
        <tr><th>ID</th><th>टेस्ट नाव</th><th>प्रकार</th><th>फी</th><th>वेळ (मि.)</th><th>स्थिती</th><th>कृती / बदल</th></tr>
        {% for t in tests %}
        <tr>
            <form method="POST" action="/admin/update_test/{{ t.id }}">
                <td>{{ t.id }}</td>
                <td><input type="text" name="test_title" value="{{ t.test_title }}" style="margin-bottom:0;" required></td>
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
                        <option value="Active" {% if t.status=='Active' %}selected{% endif %}>Active (चालू)</option>
                        <option value="Closed" {% if t.status=='Closed' %}selected{% endif %}>Closed (बंद)</option>
                    </select>
                </td>
                <td>
                    <button type="submit" class="btn-sm" style="background:#0284c7; color:white; border:none; padding:5px 8px; cursor:pointer;">💾 सेव्ह</button>
                    <a href="/admin/print_test/{{ t.id }}" target="_blank" class="btn-sm" style="background:#059669; color:white; margin-left:4px;">🖨️ प्रिंट</a>
                    <a href="/admin/delete_test/{{ t.id }}" class="btn-sm" style="background:#dc2626; color:white; margin-left:4px;" onclick="return confirm('टेस्ट डिलीट करायची का?');">🗑️ डिलीट</a>
                </td>
            </form>
        </tr>
        {% endfor %}
    </table>

    <!-- 5. LEADERBOARD SUB-TAB -->
    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 टेस्ट वाईज राज्यस्तरीय लीडरबोर्ड / टॉपर लिस्ट (पहिले १०० टॉपर्स)</h3>
    
    <div style="background:#ecfdf5; padding:12px; border-radius:6px; margin-bottom:20px; border:1px solid #a7f3d0;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; align-items:center;">
            <input type="hidden" name="tab" value="leaderboard">
            <label style="font-weight:bold; font-size:13px; color:#065f46;">टेस्ट निवडून टॉपर्स पहा:</label>
            <select name="lb_test_id" onchange="this.form.submit()" style="max-width:300px; margin-bottom:0;">
                <option value="">-- सर्व टेस्ट्सचे टॉपर्स --</option>
                {% for t in tests %}
                <option value="{{ t.id }}" {% if lb_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                {% endfor %}
            </select>
        </form>
    </div>

    <table>
        <tr><th>रँक</th><th>विद्यार्थ्याचे नाव</th><th>जिल्हा</th><th>WhatsApp नंबर</th><th>टेस्टचे नाव</th><th>गुण</th></tr>
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

    <!-- 6. SECURITY & PASSWORD SETTINGS SUB-TAB -->
    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन पासवर्ड बदल, सुरक्षा व सोशल मीडिया लिंक्स सेटिंग्स</h3>
    <div style="background:#f8fafc; padding:20px; border-radius:6px; border:1px solid #cbd5e1; max-width:600px;">
        <h4 style="margin-top:0; color:#065f46;">🔑 ॲडमिन पासवर्ड व सोशल मीडिया लिंक्स बदला:</h4>
        <form method="POST" action="/admin/update_password">
            <label style="font-weight:bold; font-size:12px;">फॉरगेट पासवर्ड WhatsApp OTP साठीचा मोबाईल नंबर:</label>
            <input type="text" name="admin_phone" value="{{ admin_phone }}" placeholder="१० अंकी मोबाईल नंबर" required>
            
            <label style="font-weight:bold; font-size:12px; margin-top:10px; display:block;">नवा ॲडमिन पासवर्ड:</label>
            <div style="position:relative; width:100%;">
                <input type="password" name="new_password" id="new_password" placeholder="नवा पासवर्ड टाका" required style="text-align:left; padding-right:40px;">
                <button type="button" onclick="togglePassVis()" style="position:absolute; right:5px; top:5px; background:none; border:none; cursor:pointer; font-size:16px;">👁️</button>
            </div>

            <hr style="margin:15px 0; border:0; border-top:1px solid #cbd5e1;">
            
            <label style="font-weight:bold; font-size:12px;">Instagram पेज लिंक:</label>
            <input type="text" name="insta_link" value="{{ insta_link }}" placeholder="https://instagram.com/...">

            <label style="font-weight:bold; font-size:12px;">YouTube चॅनेल लिंक:</label>
            <input type="text" name="yt_link" value="{{ yt_link }}" placeholder="https://youtube.com/...">

            <label style="font-weight:bold; font-size:12px;">यशस्वी विद्यार्थ्यांचे फोटो/माहिती लिंक:</label>
            <input type="text" name="toppers_link" value="{{ toppers_link }}" placeholder="https://...">

            <button type="submit" class="btn" style="margin-top:10px;">💾 सर्व सेटिंग्ज सेव्ह करा</button>
        </form>
    </div>
    {% endif %}

</div>
</body>
</html>'''

# ----------------- FLASK ROUTES -----------------

@app.route('/')
def home_tests_list():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE status='Active' ORDER BY id ASC")
            tests = cur.fetchall()
    return render_template_string(HOME_TEMPLATE, tests=tests)

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='qr_code_url'")
            qr_row = cur.fetchone()
            qr_url = qr_row['setting_value'] if qr_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='upi_mobile'")
            upi_row = cur.fetchone()
            upi_mobile = upi_row['setting_value'] if upi_row else '9921111960'

    if not test or test['status'] != 'Active': return "Test not found or currently closed", 404

    if test['test_type'] == 'Free':
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)
    
    return render_template_string(ACCESS_CHECK_TEMPLATE, test=test, qr_url=qr_url, upi_mobile=upi_mobile, error=None)

@app.route('/request_paid_test/<int:test_id>', methods=['POST'])
def request_paid_test(test_id):
    name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()
    utr_number = request.form.get('utr_number', '').strip()
    t_date = date.today().strftime("%Y-%m-%d")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()

    if not test: return "Test not found", 404

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE test_id=%s AND phone=%s", (test_id, phone))
            existing = cur.fetchone()
            if existing:
                lead_id = existing['id']
            else:
                cur.execute("""
                    INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, utr_number, score, total_marks, test_name)
                    VALUES (%s, %s, %s, %s, %s, 'Pending', %s, 0, 0, %s) RETURNING id
                """, (test_id, t_date, name, district, phone, utr_number, test['test_title']))
                lead_id = cur.fetchone()['id']
                conn.commit()

    return render_template_string('''<!DOCTYPE html><html lang="mr"><head><meta charset="UTF-8"><title>पेमेंट प्रलंबित</title></head>
    <body style="font-family:sans-serif; text-align:center; padding:50px; background:#f0fdf4;">
        <div style="max-width:450px; margin:auto; background:white; padding:30px; border-radius:10px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
            <h3 style="color:#d97706;">⏳ पेमेंट अप्रूवल प्रलंबित आहे!</h3>
            <p style="font-size:14px; color:#475569;">तुम्ही सबमिट केलेले UTR/Ref Number ॲडमिनकडे पडताळणीसाठी पाठवले आहे. ॲडमिनने अप्रूव केल्यानंतर तुम्हाला WhatsApp वर OTP पाठवला जाईल.</p>
            <a href="/" style="background:#059669; color:white; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:bold; display:inline-block; margin-top:15px;">🏠 मुख्य पानावर जा</a>
        </div>
    </body></html>''')

@app.route('/verify_paid_otp/<int:test_id>', methods=['GET', 'POST'])
def verify_paid_otp(test_id):
    error = None
    if request.method == 'POST':
        entered_otp = request.form.get('entered_otp', '').strip()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM mock_test_leads WHERE test_id=%s AND otp_code=%s AND payment_status='Approved'", (test_id, entered_otp))
                lead = cur.fetchone()
        
        if lead:
            if lead['valid_until'] and datetime.now().strftime('%Y-%m-%d') > lead['valid_until']:
                return "❌ या टेस्टची वैधता (Validity) संपली आहे!", 403
            session[f'paid_access_{test_id}'] = True
            return redirect(f'/take_approved_test/{test_id}')
        else:
            error = "❌ चुकीचा OTP किंवा पेमेंट अजून ॲडमिनने अप्रूव केलेले नाही!"
            
    return render_template_string(OTP_VERIFY_TEMPLATE, error=error)

@app.route('/take_approved_test/<int:test_id>')
def take_approved_test(test_id):
    if not session.get(f'paid_access_{test_id}'):
        return redirect(f'/verify_paid_otp/{test_id}')
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()
            
    return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
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
        with conn.cursor() as cur:
            if test['test_type'] == 'Free':
                cur.execute("""
                    INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, whatsapp_verified, payment_status, score, total_marks, test_name, answers_json)
                    VALUES (%s, %s, 'विद्यार्थी', 'महाराष्ट्र', '0000000000', 1, 'Not Required', %s, %s, %s, %s) RETURNING id
                """, (test_id, t_date, score, total, test['test_title'], ans_json_str))
                new_id = cur.fetchone()['id']
                conn.commit()
                return redirect(f'/result_view/{new_id}')
            else:
                cur.execute("""
                    UPDATE mock_test_leads SET score=%s, total_marks=%s, answers_json=%s WHERE test_id=%s AND payment_status='Approved'
                """, (score, total, ans_json_str, test_id))
                conn.commit()
                cur.execute("SELECT id FROM mock_test_leads WHERE test_id=%s AND payment_status='Approved' ORDER BY id DESC LIMIT 1", (test_id,))
                row = cur.fetchone()
                new_id = row['id'] if row else 1
                return redirect(f'/result_view/{new_id}')

@app.route('/result_view/<int:lead_id>')
def result_view(lead_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead: return "Result not found", 404

            cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s", (lead['test_id'], lead['score']))
            higher_count = cur.fetchone()['higher']
            state_rank = higher_count + 1
            
            user_ans_dict = json.loads(lead['answers_json'] or '{}')
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (lead['test_id'],))
            questions = cur.fetchall()

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_row = cur.fetchone()
            insta_link = insta_row['setting_value'] if insta_row else ''

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_row = cur.fetchone()
            yt_link = yt_row['setting_value'] if yt_row else ''

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            top_row = cur.fetchone()
            toppers_link = top_row['setting_value'] if top_row else ''

    evaluated_questions = []
    for q in questions:
        u_ans = user_ans_dict.get(str(q['id']), 'सोडवले नाही')
        is_corr = (u_ans == q['correct'])
        evaluated_questions.append({
            'q_text': q['question'],
            'user_ans': u_ans,
            'correct_ans': q['correct'],
            'is_correct': is_corr,
            'explanation': q['explanation']
        })

    # WhatsApp निकाल पाठवण्याची सिम्युलेशन लिंक तयार करणे
    res_link = request.host_url + f"result_view/{lead_id}"
    print(f"--- WHATSAPP RESULT LINK --- To: {lead['phone']} | Link: {res_link} | Score: {lead['score']}/{lead['total_marks']}")

    return render_template_string(RESULT_TEMPLATE, lead=lead, state_rank=state_rank, evaluated_questions=evaluated_questions, insta_link=insta_link, yt_link=yt_link, toppers_link=toppers_link)

# ----------------- ADMIN SECURITY & DASHBOARD ROUTES -----------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error, success = None, None
    otp_sent = session.get('admin_otp_sent', False)
    
    if request.method == 'POST':
        if 'admin_pass' in request.form:
            password = request.form.get('admin_pass')
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_pass'")
                    row = cur.fetchone()
                    db_pass = row['setting_value'] if row else 'shreeguru2026'

            if password == db_pass:
                session['admin_logged'] = True
                session.pop('admin_otp_sent', None)
                return redirect('/admin/dashboard')
            else:
                error = "चुकीचा पासवर्ड! कृपया पुन्हा प्रयत्न करा."
                
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=error, success=success, otp_sent=otp_sent)

@app.route('/admin/forgot_password', methods=['POST'])
def admin_forgot_password():
    import random
    gen_otp = str(random.randint(1000, 9999))
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_phone'")
            ph_row = cur.fetchone()
            admin_phone = ph_row['setting_value'] if ph_row else '9921111960'
            
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_otp'", (gen_otp,))
            conn.commit()

    session['admin_otp_sent'] = True
    print(f"--- ADMIN WHATSAPP OTP --- To: {admin_phone} | OTP: {gen_otp}")
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=None, success=f"📲 WhatsApp वर OTP पाठवला आहे! (सिम्युलेशन OTP: {gen_otp})", otp_sent=True)

@app.route('/admin/verify_otp', methods=['POST'])
def admin_verify_otp():
    entered_otp = request.form.get('entered_otp', '').strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_otp'")
            row = cur.fetchone()
            db_otp = row['setting_value'] if row else ''

    if entered_otp and entered_otp == db_otp:
        session['admin_logged'] = True
        session.pop('admin_otp_sent', None)
        return redirect('/admin/dashboard')
    else:
        return render_template_string(ADMIN_LOGIN_TEMPLATE, error="❌ चुकीचा OTP! पुन्हा प्रयत्न करा.", success=None, otp_sent=True)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged', None)
    session.pop('admin_otp_sent', None)
    return redirect('/admin/login')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged'):
        return redirect('/admin/login')

    active_tab = request.args.get('tab', 'leads')
    filter_test_id = request.args.get('filter_test_id', '')
    lb_test_id = request.args.get('lb_test_id', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads ORDER BY id DESC")
            leads = cur.fetchall()
            cur.execute("SELECT * FROM test_papers ORDER BY id ASC")
            tests = cur.fetchall()

            if filter_test_id:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id DESC", (filter_test_id,))
            else:
                cur.execute("SELECT * FROM questions ORDER BY id DESC")
            all_questions = cur.fetchall()

            cur.execute("SELECT * FROM mock_test_leads WHERE payment_status != 'Not Required' ORDER BY id DESC")
            payments = cur.fetchall()

            if lb_test_id:
                cur.execute("SELECT * FROM mock_test_leads WHERE test_id=%s ORDER BY score DESC, id ASC LIMIT 100", (lb_test_id,))
            else:
                cur.execute("SELECT * FROM mock_test_leads ORDER BY score DESC, id ASC LIMIT 100")
            all_leads_sorted = cur.fetchall()

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='qr_code_url'")
            qr_row = cur.fetchone()
            qr_url = qr_row['setting_value'] if qr_row else ''

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='upi_mobile'")
            upi_row = cur.fetchone()
            upi_mobile = upi_row['setting_value'] if upi_row else '9921111960'

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_phone'")
            aph_row = cur.fetchone()
            admin_phone = aph_row['setting_value'] if aph_row else '9921111960'

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_link = cur.fetchone()['setting_value'] if cur.fetchone() else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_link = cur.fetchone()['setting_value'] if cur.fetchone() else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            toppers_link = cur.fetchone()['setting_value'] if cur.fetchone() else ''

    top_leads = []
    for idx, l in enumerate(all_leads_sorted, start=1):
        top_leads.append((idx, l))

    return render_template_string(ADMIN_TEMPLATE, active_tab=active_tab, leads=leads, tests=tests, all_questions=all_questions, payments=payments, top_leads=top_leads, qr_url=qr_url, upi_mobile=upi_mobile, admin_phone=admin_phone, filter_test_id=filter_test_id, lb_test_id=lb_test_id, insta_link=insta_link, yt_link=yt_link, toppers_link=toppers_link)

@app.route('/admin/update_payment_settings', methods=['POST'])
def admin_update_payment_settings():
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_mobile = request.form.get('upi_mobile')
    qr_file = request.files.get('qr_file')
    
    qr_url = None
    if qr_file and qr_file.filename != '':
        filename = secure_filename(qr_file.filename)
        qr_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        qr_url = f"/static/uploads/{filename}"

    with get_db() as conn:
        with conn.cursor() as cur:
            if qr_url:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='qr_code_url'", (qr_url,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='upi_mobile'", (new_mobile,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/update_password', methods=['POST'])
def admin_update_password():
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_pass = request.form.get('new_password')
    new_phone = request.form.get('admin_phone')
    insta = request.form.get('insta_link', '')
    yt = request.form.get('yt_link', '')
    top = request.form.get('toppers_link', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_phone'", (new_phone,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='insta_link'", (insta,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='yt_link'", (yt,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='toppers_link'", (top,))
            conn.commit()
    return redirect('/admin/dashboard?tab=settings')

@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title')
    ttype = request.form.get('test_type')
    fee = float(request.form.get('test_fee', 0))
    duration = int(request.form.get('duration_minutes', 60))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status) VALUES (%s, %s, %s, %s, 'Active')", (title, ttype, fee, duration))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/update_test/<int:test_id>', methods=['POST'])
def admin_update_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title')
    ttype = request.form.get('test_type')
    fee = float(request.form.get('test_fee', 0))
    duration = int(request.form.get('duration_minutes', 60))
    status = request.form.get('status', 'Active')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE test_papers SET test_title=%s, test_type=%s, test_fee=%s, duration_minutes=%s, status=%s WHERE id=%s", (title, ttype, fee, duration, status, test_id))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/print_test/<int:test_id>')
def admin_print_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
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

@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM questions WHERE test_id=%s", (test_id,))
            cur.execute("DELETE FROM test_papers WHERE id=%s", (test_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/delete_lead/<int:lead_id>')
def admin_delete_lead(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mock_test_leads WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/add_question', methods=['POST'])
def admin_add_question():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    question = request.form.get('question')
    oa = request.form.get('opt_a')
    ob = request.form.get('opt_b')
    oc = request.form.get('opt_c')
    od = request.form.get('opt_d')
    correct = request.form.get('correct').upper()
    explanation = request.form.get('explanation', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (test_id, question, oa, ob, oc, od, correct, explanation))
            conn.commit()
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/bulk_questions', methods=['POST'])
def admin_bulk_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    bulk_data = request.form.get('bulk_data', '')

    lines = bulk_data.strip().split('\n')
    with get_db() as conn:
        with conn.cursor() as cur:
            for line in lines:
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 6:
                    q, a, b, c, d, corr = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5].upper()
                    exp = parts[6] if len(parts) > 6 else ''
                    cur.execute("INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                (test_id, q, a, b, c, d, corr, exp))
            conn.commit()
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/delete_question/<int:q_id>')
def admin_delete_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM questions WHERE id=%s", (q_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/approve_payment/<int:lead_id>', methods=['POST'])
def admin_approve_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    validity_days = int(request.form.get('validity_days', 30))
    valid_date = (datetime.now() + timedelta(days=validity_days)).strftime('%Y-%m-%d')
    import random
    gen_otp = str(random.randint(1000, 9999))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT phone FROM mock_test_leads WHERE id=%s", (lead_id,))
            row = cur.fetchone()
            phone = row['phone'] if row else ''
            
            cur.execute("UPDATE mock_test_leads SET payment_status='Approved', otp_code=%s, valid_until=%s WHERE id=%s", (gen_otp, valid_date, lead_id))
            conn.commit()

    print(f"--- WHATSAPP OTP SMS --- To: {phone} | OTP: {gen_otp} | Valid Till: {valid_date}")
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/delete_payment/<int:lead_id>')
def admin_delete_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mock_test_leads WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
