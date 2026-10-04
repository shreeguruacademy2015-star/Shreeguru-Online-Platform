import json
import os
import secrets
from datetime import date, datetime, timedelta
from flask import Flask, redirect, render_template_string, request, session, url_for
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
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
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

                # सेफ कॉलम मायग्रेशन
                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS access_token TEXT DEFAULT ''")
                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS token_expires_at TEXT DEFAULT ''")

                # ४. ॲकॅडमी सेटिंग्स व भरती माहिती
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
                    ('razorpay_key_id', ''),
                    ('razorpay_key_secret', ''),
                    ('recruitment_info', 'महाराष्ट्र पोलीस भरती व आर्मी भरती पूर्वतयारी सराव संच नियमित सोडवा.'),
                    ('eligibility_info', 'पोलीस भरती पात्रता: १२ वी उत्तीर्ण, वय १८ ते २८ वर्षे, उंची: मुले १६५ सेमी, मुली १५५ सेमी.')
                ]
                for k, v in defaults:
                    cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO NOTHING", (k, v))

                cur.execute('SELECT COUNT(*) as count FROM test_papers')
                if cur.fetchone()['count'] == 0:
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active')")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (2, 'आर्मी भरती बौद्धिक व गणित टेस्ट #२', 'Paid', 49, 45, 'Active')")

                cur.execute('SELECT COUNT(*) as count FROM questions')
                if cur.fetchone()['count'] == 0:
                    default_qs = [
                        (1, "महाराष्ट्राची आर्थिक व व्यापारी राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B", "मुंबई ही महाराष्ट्राची आर्थिक व व्यापारी राजधानी आहे."),
                        (1, "क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A", "अहमदनगर हा क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा आहे."),
                        (2, "भारताचे राष्ट्रीय गीत कोणते?", "जन गण मन", "वंदे मातरम्", "सारा जहाँ से अच्छा", "जय हिंद", "B", "वंदे मातरम् हे बंकिमचंद्र चटोपाध्याय यांनी रचलेले भारताचे राष्ट्रीय गीत आहे.")
                    ]
                    cur.executemany('INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', default_qs)
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
        .info-card { background: #fffbeb; border: 1.5px solid #fde68a; border-radius: 8px; padding: 15px; margin-bottom: 20px; }
        .info-title { font-weight: bold; color: #92400e; font-size: 15px; margin-bottom: 6px; }
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
        🔥 हातात उरलेल्या दिवसात काबाड कष्ट करून तुला तुझे वर्दीचे स्वप्न पूर्ण करायचे आहे (लक्षात ठेव तुला घडविण्यासाठी कुणाचे तरी हात झिजत आहेत) 🌟
    </div>

    <!-- भरती माहिती व पात्रता बॉक्स (फक्त वाचण्यासाठी) -->
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:15px; margin-bottom:20px;">
        <div class="info-card">
            <div class="info-title">📢 भरती अधिकृत सूचना / माहिती:</div>
            <div style="font-size:13px; color:#451a03; line-height:1.5;">{{ recruitment_info }}</div>
        </div>
        <div class="info-card" style="background:#eff6ff; border-color:#bfdbfe;">
            <div class="info-title" style="color:#1e40af;">📋 भरती पात्रता व निकष:</div>
            <div style="font-size:13px; color:#172554; line-height:1.5;">{{ eligibility_info }}</div>
        </div>
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

# ----------------- 2. EXAM TEMPLATE (Lock Before Details) -----------------
EXAM_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ test.test_title }} - परीक्षा कक्ष</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #eef2f7; color: #1e293b; padding: 10px; }
        .exam-header { background: #065f46; color: white; padding: 12px 20px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; max-width: 800px; margin: 0 auto 15px; }
        .box { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border-top: 5px solid #059669; }
        .timer-box { background: #fee2e2; border: 2px solid #ef4444; color: #991b1b; padding: 8px 15px; border-radius: 6px; font-weight: bold; font-size: 15px; }
        .student-details { background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 8px; padding: 18px; margin-bottom: 20px; }
        .student-details input { width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 4px; font-size: 14px; margin-bottom: 12px; }
        .q-item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; margin-bottom: 18px; transition: 0.3s; }
        .q-locked { opacity: 0.45; pointer-events: none; user-select: none; }
        .q-text { font-weight: bold; margin-bottom: 10px; font-size: 15px; color: #0f172a; }
        .opt-label { display: block; margin-bottom: 8px; font-size: 14px; cursor: pointer; background: white; padding: 8px 12px; border-radius: 6px; border: 1px solid #e2e8f0; }
        .opt-label:hover { background: #f1f5f9; }
        .submit-notice { background: #fef3c7; border: 1px solid #f59e0b; color: #92400e; padding: 10px 15px; border-radius: 6px; font-size: 13px; font-weight: bold; text-align: center; margin-bottom: 12px; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #059669, #047857); color: white; padding: 14px; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; }
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
                    alert("⏰ वेळ संपली! टेस्ट सबमिट होत आहे.");
                    document.getElementById("examForm").submit();
                }
            }, 1000);
        }

        function checkStudentDetails() {
            const name = document.getElementById('s_name').value.trim();
            const dist = document.getElementById('s_dist').value.trim();
            const phone = document.getElementById('s_phone').value.trim();
            const questionsArea = document.getElementById('questionsArea');
            const submitNotice = document.getElementById('submitNotice');
            const submitBtn = document.getElementById('submitBtn');

            if (name !== "" && dist !== "" && phone.length === 10) {
                questionsArea.classList.remove('q-locked');
                submitBtn.disabled = false;
                submitNotice.innerHTML = "✅ तुमची माहिती यशस्वीरीत्या भरली आहे. सर्व प्रश्न सोडवून टेस्ट सबमिट करा.";
                submitNotice.style.background = "#dcfce7";
                submitNotice.style.borderColor = "#86efac";
                submitNotice.style.color = "#166534";
            } else {
                questionsArea.classList.add('q-locked');
                submitBtn.disabled = true;
                submitNotice.innerHTML = "⚠️ कृपया सुरुवातीला तुमचे नाव, जिल्हा व १० अंकी WhatsApp नंबर भरा. त्याशिवाय प्रश्न सोडवता किंवा सबमिट करता येणार नाहीत.";
                submitNotice.style.background = "#fef3c7";
                submitNotice.style.borderColor = "#f59e0b";
                submitNotice.style.color = "#92400e";
            }
        }
        window.onload = function() {
            startTimer();
            checkStudentDetails();
        };
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
        
        <!-- विद्यार्थी माहिती बॉक्स -->
        <div class="student-details">
            <h4 style="margin:0 0 10px; color:#065f46;">👤 तुमची माहिती भरा (ही भरल्याशिवाय प्रश्न सोडवता येणार नाहीत):</h4>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px;">
                <div>
                    <label style="font-size:13px; font-weight:600;">पूर्ण नाव *:</label>
                    <input type="text" name="student_name" id="s_name" placeholder="उदा. राहुल तानाजी पाटील" onkeyup="checkStudentDetails()" required>
                </div>
                <div>
                    <label style="font-size:13px; font-weight:600;">जिल्हा *:</label>
                    <input type="text" name="district" id="s_dist" placeholder="उदा. कोल्हापूर" onkeyup="checkStudentDetails()" required>
                </div>
                <div>
                    <label style="font-size:13px; font-weight:600;">WhatsApp मोबाईल नंबर *:</label>
                    <input type="tel" name="phone" id="s_phone" placeholder="१० अंकी नंबर" pattern="[0-9]{10}" onkeyup="checkStudentDetails()" required>
                </div>
            </div>
        </div>

        <!-- प्रश्न यादी (माहिती भरेपर्यंत लॉक) -->
        <div id="questionsArea" class="q-locked">
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

        <div id="submitNotice" class="submit-notice">
            आपले गुण व बरोबर/चूक प्रश्न पाहण्यासाठी येथे दिलेला WhatsApp नंबर तपासून टेस्ट सबमिट करा.
        </div>

        <button type="submit" id="submitBtn" class="btn-submit" disabled>✅ टेस्ट सबमिट करा</button>
    </form>
</div>
</body>
</html>'''

# ----------------- 3. RESULT SUBMISSION SUMMARY (Secure WhatsApp Link) -----------------
RESULT_SUMMARY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>टेस्ट निकाल - अभिनंदन</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; }
        .box { max-width: 700px; margin: 20px auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 6px solid #059669; text-align: center; }
        .cert-box { background: linear-gradient(135deg, #fefce8, #fef3c7); border: 4px double #d97706; padding: 25px; border-radius: 10px; margin: 20px 0; }
        .promo-box { background: #f8fafc; border: 1.5px solid #cbd5e1; padding: 15px; border-radius: 8px; margin-top: 20px; }
        .btn-link { display: inline-block; background: #25D366; color: white; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 13px; margin: 4px; }
    </style>
</head>
<body>
<div class="box">
    <h2 style="color:#065f46; margin:0 0 5px;">🎉 टेस्ट यशस्वीरीत्या पूर्ण झाली!</h2>
    <p style="font-size:14px; color:#64748b; margin-bottom:15px;">राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</p>

    <div style="background:#ecfdf5; border:1px solid #86efac; border-radius:8px; padding:15px; margin-bottom:20px;">
        <p style="font-size:16px; margin:5px 0;">विद्यार्थ्याचे नाव: <b>{{ lead.student_name }}</b> (जिल्हा: {{ lead.district }})</p>
        <p style="font-size:22px; margin:5px 0; color:#059669;">प्राप्त गुण: <b>{{ lead.score }} / {{ lead.total_marks }}</b></p>
        <p style="font-size:15px; color:#b45309; font-weight:bold; margin-top:8px;">
            🏆 संपूर्ण महाराष्ट्रातील विद्यार्थ्यांमध्ये तुमचा रँक: <b>#{{ state_rank }}</b> 🌟
        </p>
    </div>

    <!-- प्रशस्तीपत्र -->
    <div class="cert-box">
        <h3 style="color:#92400e; margin:0 0 5px;">📜 सहभाग व अभिनंदन डिजिटल प्रशस्तीपत्र</h3>
        <p style="font-size:12px; color:#78350f; margin-bottom:12px;">राज्यस्तरीय ऑनलाईन सराव कक्ष</p>
        <div style="background:white; padding:15px; border-radius:6px; border:1px dashed #b45309;">
            <p style="font-size:13px; margin:4px 0;">प्रमाणित करण्यात येते की,</p>
            <h2 style="color:#065f46; margin:6px 0; font-size:22px;">{{ lead.student_name }}</h2>
            <p style="font-size:13px; margin:4px 0;">यांनी <b>{{ lead.test_name }}</b> यशस्वीरीत्या सोडवली आहे.</p>
        </div>
    </div>

    <!-- WhatsApp वर निकाल पाठवल्याचा मेसेज -->
    <div style="background:#fefce8; border:1.5px solid #facc15; padding:15px; border-radius:8px; margin:20px 0; color:#854d0e; text-align:left;">
        <h4 style="margin:0 0 6px;">📲 सविस्तर उत्तरपत्रिका व विश्लेषण WhatsApp वर पाठवले आहे:</h4>
        <p style="font-size:13px; margin:0; line-height:1.5;">
            तुमचे कोणते प्रश्न बरोबर आले, कोणते चुकले आणि त्यांचे सविस्तर स्पष्टीकरण पाहण्यासाठी तुमच्या <b>{{ lead.phone }}</b> या व्हॉट्सॲप नंबरवर थेट लिंक पाठवली आहे.
        </p>
        <div style="margin-top:10px; text-align:center;">
            <a href="https://wa.me/91{{ lead.phone }}?text={{ wa_encoded_msg }}" target="_blank" style="background:#25D366; color:white; padding:8px 16px; border-radius:5px; text-decoration:none; font-weight:bold; font-size:13px; display:inline-block;">📲 थेट WhatsApp वर उत्तरपत्रिका लिंक उघडा</a>
        </div>
    </div>

    <!-- सोशल मीडिया व यशोगाथा लिंक्स -->
    <div class="promo-box">
        <h4 style="margin:0 0 8px; color:#065f46;">🌟 अधिकृत सोशल मीडिया व यशोगाथा लिंक्स:</h4>
        {% if insta_link %}<a href="{{ insta_link }}" target="_blank" class="btn-link" style="background:#E1306C;">📸 Instagram</a>{% endif %}
        {% if yt_link %}<a href="{{ yt_link }}" target="_blank" class="btn-link" style="background:#FF0000;">▶️️ YouTube</a>{% endif %}
        {% if toppers_link %}<a href="{{ toppers_link }}" target="_blank" class="btn-link" style="background:#0284c7;">🏆 यशवंतांचे फोटो</a>{% endif %}
    </div>

    <div style="margin-top:20px;">
        <a href="/" style="background:#0b3c5d; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px;">🏠 मुख्य पानावर जा</a>
    </div>
</div>
</body>
</html>'''

# ----------------- 4. DETAILED ANSWER KEY TEMPLATE (Ordered as requested) -----------------
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
    </style>
</head>
<body>
<div class="box">
    <h2 style="color:#065f46; margin:0 0 5px; text-align:center;">📋 सविस्तर उत्तरपत्रिका व स्पष्टीकरण</h2>
    <p style="text-align:center; font-size:13px; color:#64748b; margin-bottom:20px;">विद्यार्थी: <b>{{ lead.student_name }}</b> | गुण: <b>{{ lead.score }} / {{ lead.total_marks }}</b></p>

    {% for item in evaluated_questions %}
    <div class="item {{ 'correct-box' if item.is_correct else 'wrong-box' }}">
        <!-- १. सोडवलेला प्रश्न -->
        <div style="font-weight:bold; font-size:15px; margin-bottom:8px; color:#0f172a;">
            प्र. {{ loop.index }}. {{ item.q_text }}
        </div>
        
        <div style="font-size:13px; margin-bottom:4px; padding-left:10px;">
            A) {{ item.opt_a }} &nbsp;|&nbsp; B) {{ item.opt_b }} &nbsp;|&nbsp; C) {{ item.opt_c }} &nbsp;|&nbsp; D) {{ item.opt_d }}
        </div>

        <div style="display:flex; gap:15px; font-size:13px; margin:8px 0; padding-left:10px;">
            <!-- २. विद्यार्थ्यांनी दिलेले उत्तर -->
            <div>तुमचे उत्तर: <b style="color:{{ 'green' if item.is_correct else 'red' }}; font-size:15px;">{{ item.user_ans }}</b></div>
            <!-- ३. बरोबर उत्तर -->
            <div>अचूक उत्तर: <b style="color:#16a34a; font-size:15px;">{{ item.correct_ans }}</b></div>
        </div>

        <!-- ४. प्रश्नाचे स्पष्टीकरण -->
        {% if item.explanation %}
        <div style="font-size:12px; color:#166534; background:#f0fdf4; padding:8px 12px; border-radius:6px; margin-top:6px; border:1px solid #bbf7d0;">
            💡 <b>स्पष्टीकरण:</b> {{ item.explanation }}
        </div>
        {% endif %}
    </div>
    {% endfor %}

    <div style="text-align:center; margin-top:25px;">
        <a href="/" style="background:#0284c7; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px;">🏠 मुख्य पानावर जा</a>
    </div>
</div>
</body>
</html>'''

# ----------------- 5. ADMIN LOGIN TEMPLATE -----------------
ADMIN_LOGIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ॲडमिन लॉगिन</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #0f172a; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-box { background: #1e293b; padding: 35px 30px; border-radius: 10px; width: 360px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); border-top: 5px solid #059669; text-align: center; }
        h2 { margin: 0 0 15px; color: #34d399; font-size: 22px; }
        input { width: 100%; padding: 12px; margin: 15px 0 20px; border-radius: 6px; border: 1.5px solid #475569; background: #0f172a; color: white; font-size: 14px; text-align: center; outline: none; }
        button { width: 100%; background: #059669; color: white; border: none; padding: 12px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 15px; }
        .err { color: #f87171; font-size: 13px; font-weight: bold; margin-bottom: 12px; }
    </style>
</head>
<body>
<div class="login-box">
    <h2>⚙️ ॲडमिन सुरक्षित कक्ष</h2>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    
    <form method="POST" action="/admin/login">
        <label style="font-size:13px; color:#cbd5e1;">पासवर्ड टाका:</label>
        <input type="password" name="admin_pass" placeholder="पासवर्ड टाका" required autocomplete="off">
        <button type="submit">🔐 लॉगिन करा</button>
    </form>
    <div style="margin-top:20px;"><a href="/" style="color:#38bdf8; font-size:12px; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a></div>
</div>
</body>
</html>'''

# ----------------- 6. ADMIN DASHBOARD TEMPLATE -----------------
ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ॲडमिन डॅशबोर्ड</title>
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
        <a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 Leads (चौकशी व फिल्टर्स)</a>
        <a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 Payments & QR (पेमेंट्स व QR)</a>
        <a href="/admin/dashboard?tab=questions" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions (प्रश्न व AI असिस्ट)</a>
        <a href="/admin/dashboard?tab=launch" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Test Launch (टेस्ट व्यवस्थापन)</a>
        <a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard (टॉपर लिस्ट)</a>
        <a href="/admin/dashboard?tab=notices" class="{{ 'active' if active_tab == 'notices' else '' }}">📢 Notice & Eligibility (भरती माहिती)</a>
        <a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Security & Razorpay (सेटिंग्स)</a>
    </div>

    <!-- 1. LEADS SUB-TAB (जिल्हा व टेस्ट वाईस फिल्टर) -->
    {% if active_tab == 'leads' %}
    <h3>📱 विद्यार्थ्यांची लीड्स यादी (जिल्हा व टेस्ट वाईस ऑटो-फिल्टर)</h3>
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
        <tr><th>दिनांक</th><th>विद्यार्थी नाव</th><th>जिल्हा</th><th>WhatsApp नंबर</th><th>टेस्टचे नाव</th><th>गुण</th><th>कृती</th></tr>
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
    <h3>💰 पेमेंट वैधता डेस्क, २४ तास ॲक्सेस लिंक व QR कोड</h3>
    <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <h4 style="margin:0 0 10px; color:#065f46;">💳 पेमेंट मोबाईल नंबर व नवीन QR कोड इमेज अपलोड करा:</h4>
        <form method="POST" action="/admin/update_payment_settings" enctype="multipart/form-data">
            <label style="font-weight:bold; font-size:12px;">पेमेंट मोबाईल नंबर / UPI ID:</label>
            <input type="text" name="upi_mobile" value="{{ upi_mobile }}" required>
            <label style="font-weight:bold; font-size:12px;">QR कोड इमेज फाईल अपलोड करा (JPG/PNG):</label>
            <input type="file" name="qr_file" accept="image/*" style="margin-bottom:10px;">
            <button type="submit" class="btn">💾 पेमेंट सेटिंग्ज अपडेट करा</button>
        </form>
    </div>

    <table>
        <tr><th>विद्यार्थी नाव</th><th>मोबाईल</th><th>टेस्ट</th><th>स्थिती</th><th>कृती (Approve & 24hr Link)</th></tr>
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
                <span style="color:green; font-weight:bold;">Approved (२४ तास चालू)</span>
                {% endif %}
                <a href="/admin/delete_payment/{{ p.id }}" class="btn-sm" style="background:#dc2626; color:white; margin-left:5px;" onclick="return confirm('ही पेमेंट नोंद डिलीट करायची का?');">🗑 डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 3. QUESTIONS SUB-TAB (Auto Parse & AI Assist) -->
    {% elif active_tab == 'questions' %}
    <h3>📝 प्रश्न व्यवस्थापन (Smart Auto-Parse, AI Assistant & Quick Edit)</h3>
    
    <div style="background:#ecfdf5; padding:15px; border-radius:6px; margin-bottom:20px; border:1px solid #a7f3d0;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <input type="hidden" name="tab" value="questions">
            <label style="font-weight:bold; font-size:13px; color:#065f46;">प्रश्न पाहण्यासाठी टेस्ट निवडा:</label>
            <select name="filter_test_id" onchange="this.form.submit()" style="max-width:320px; margin-bottom:0;">
                <option value="">-- सर्व टेस्ट्सचे प्रश्न --</option>
                {% for t in tests %}
                <option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                {% endfor %}
            </select>
        </form>
    </div>

    <!-- Smart Auto Parse Box -->
    <div style="background:#f8fafc; padding:18px; border-radius:8px; border:1.5px solid #cbd5e1; margin-bottom:25px;">
        <h4 style="margin-top:0; color:#065f46;">⚡ स्मार्ट ऑटोमॅटिक बल्क प्रश्न अपलोडर (एका ओळीत १ प्रश्न):</h4>
        <p style="font-size:12px; color:#64748b; margin-top:-5px;">फॉरमॅट: प्रश्न | पर्यायA | पर्यायB | पर्यायC | पर्यायD | अचूक उत्तर | स्पष्टीकरण</p>
        <form method="POST" action="/admin/bulk_questions">
            <select name="test_id" required style="max-width:320px;">
                {% for t in tests %}<option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <textarea name="bulk_questions_text" rows="6" placeholder="महाराष्ट्राची राजधानी कोणती? | पुणे | मुंबई | नागपूर | नाशिक | B | मुंबई ही प्रशासकीय राजधानी आहे.&#10;क्षेत्रफळाने सर्वात मोठा जिल्हा कोणता? | अहमदनगर | पुणे | नाशिक | सोलापूर | A | अहमदनगर सर्वात मोठा जिल्हा आहे." required></textarea>
            <button type="submit" class="btn" style="background:#0284c7;">📥 सर्व प्रश्न ऑटो-अरेंज करून सेव्ह करा</button>
        </form>
    </div>

    <h4>यादीतील प्रश्न ({{ all_questions|length }} प्रश्न उपलब्ध):</h4>
    <table>
        <tr><th>ID</th><th>प्रश्न</th><th>अचूक</th><th>स्पष्टीकरण</th><th>कृती (Edit / Delete)</th></tr>
        {% for q in all_questions %}
        <tr>
            <td>{{ q.id }}</td>
            <td><b>{{ q.question }}</b></td>
            <td style="color:green; font-weight:bold;">{{ q.correct }}</td>
            <td style="color:#475569; font-size:12px;">{{ q.explanation }}</td>
            <td>
                <a href="/admin/delete_question/{{ q.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('हा प्रश्न डिलीट करायचा आहे का?');">🗑️ डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 4. TEST LAUNCH SUB-TAB -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 नवीन टेस्ट तयार करा व लॉन्च करा</h3>
    <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <input type="text" name="test_title" placeholder="टेस्टचे नाव लिहा" required>
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
        <tr><th>ID</th><th>टेस्ट नाव</th><th>प्रकार</th><th>फी</th><th>वेळ</th><th>स्थिती</th><th>कृती</th></tr>
        {% for t in tests %}
        <tr>
            <td>{{ t.id }}</td>
            <td><b>{{ t.test_title }}</b></td>
            <td>{{ t.test_type }}</td>
            <td>₹{{ t.test_fee }}</td>
            <td>{{ t.duration_minutes }} मि.</td>
            <td><b>{{ t.status }}</b></td>
            <td>
                <a href="/admin/print_test/{{ t.id }}" target="_blank" class="btn-sm" style="background:#059669; color:white;">🖨️ प्रिंट</a>
                <a href="/admin/delete_test/{{ t.id }}" class="btn-sm" style="background:#dc2626; color:white; margin-left:4px;" onclick="return confirm('डिलीट करायची का?');">🗑️ डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 5. LEADERBOARD SUB-TAB -->
    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 टेस्ट वाईज राज्यस्तरीय लीडरबोर्ड (टॉप १०० विद्यार्थी)</h3>
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

    <!-- 6. NOTICES & ELIGIBILITY SUB-TAB (विद्यार्थ्यांसाठी फक्त वाचण्यायोग्य) -->
    {% elif active_tab == 'notices' %}
    <h3>📢 भरती माहिती व पात्रता व्यवस्थापन (केवळ ॲडमिन संपादन करू शकतो)</h3>
    <form method="POST" action="/admin/update_notices" style="background:#f8fafc; padding:20px; border-radius:8px; border:1px solid #cbd5e1;">
        <label style="font-weight:bold; font-size:13px; color:#92400e;">१. भरती अधिकृत सूचना / चालू घडामोडी (Recruitment Notice):</label>
        <textarea name="recruitment_info" rows="4" required>{{ recruitment_info }}</textarea>

        <label style="font-weight:bold; font-size:13px; color:#1e40af; margin-top:10px; display:block;">२. भरती पात्रता व मैदानी/लेखी निकष (Eligibility Criteria):</label>
        <textarea name="eligibility_info" rows="4" required>{{ eligibility_info }}</textarea>

        <button type="submit" class="btn" style="margin-top:10px;">💾 होमपेजवरील माहिती अपडेट करा</button>
    </form>

    <!-- 7. SECURITY & RAZORPAY SETTINGS -->
    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन पासवर्ड, Razorpay व सोशल मीडिया सेटिंग्स</h3>
    <div style="background:#f8fafc; padding:20px; border-radius:6px; border:1px solid #cbd5e1; max-width:650px;">
        <form method="POST" action="/admin/update_password">
            <label style="font-weight:bold; font-size:12px;">नवा ॲडमिन पासवर्ड:</label>
            <input type="password" name="new_password" placeholder="नवा पासवर्ड टाका">

            <hr style="margin:15px 0; border:0; border-top:1px solid #cbd5e1;">
            
            <h4 style="margin:0 0 10px; color:#0b3c5d;">💳 Razorpay ऑटोमॅटिक पेमेंट की (पर्यायी):</h4>
            <label style="font-weight:bold; font-size:12px;">Razorpay Key ID:</label>
            <input type="text" name="razorpay_key_id" value="{{ razorpay_key_id }}" placeholder="rzp_live_...">
            <label style="font-weight:bold; font-size:12px;">Razorpay Key Secret:</label>
            <input type="text" name="razorpay_key_secret" value="{{ razorpay_key_secret }}" placeholder="...">

            <hr style="margin:15px 0; border:0; border-top:1px solid #cbd5e1;">

            <label style="font-weight:bold; font-size:12px;">Instagram लिंक:</label>
            <input type="text" name="insta_link" value="{{ insta_link }}">
            <label style="font-weight:bold; font-size:12px;">YouTube चॅनेल लिंक:</label>
            <input type="text" name="yt_link" value="{{ yt_link }}">
            <label style="font-weight:bold; font-size:12px;">यशवंतांचे फोटो लिंक:</label>
            <input type="text" name="toppers_link" value="{{ toppers_link }}">

            <button type="submit" class="btn" style="margin-top:10px;">💾 सर्व सेटिंग्स सेव्ह करा</button>
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
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_info'")
            rec_row = cur.fetchone()
            rec_info = rec_row['setting_value'] if rec_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_info'")
            elg_row = cur.fetchone()
            elg_info = elg_row['setting_value'] if elg_row else ''
    return render_template_string(HOME_TEMPLATE, tests=tests, recruitment_info=rec_info, eligibility_info=elg_info)

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    token = request.args.get('token', '')

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

    # मोफत टेस्ट असल्यास थेट ओपन करा
    if test['test_type'] == 'Free':
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

    # सशुल्क टेस्ट असल्यास २४ तासांचे टोकन तपासा
    if token:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM mock_test_leads WHERE test_id=%s AND access_token=%s AND payment_status='Approved'", (test_id, token))
                lead = cur.fetchone()
        if lead:
            expires_at = datetime.strptime(lead['token_expires_at'], "%Y-%m-%d %H:%M:%S")
            if datetime.now() <= expires_at:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                        questions = cur.fetchall()
                return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)
            else:
                return "<h3 style='color:red; text-align:center;'>❌ या सशुल्क टेस्टची २४ तासांची मुदत संपलेली आहे!</h3>", 403

    # टोकन नसल्यास पेमेंट गेटवे पेज दाखवा
    return render_template_string(ACCESS_CHECK_TEMPLATE, test=test, qr_url=qr_url, upi_mobile=upi_mobile, error=None)

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    student_name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()

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
    pay_status = 'Approved' if test['test_type'] == 'Free' else 'Pending'

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, whatsapp_verified, payment_status, score, total_marks, test_name, answers_json)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s) RETURNING id
            """, (test_id, t_date, student_name, district, phone, pay_status, score, total, test['test_title'], ans_json_str))
            new_id = cur.fetchone()['id']
            conn.commit()

            cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s", (test_id, score))
            higher_count = cur.fetchone()['higher']
            state_rank = higher_count + 1

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            toppers_link = cur.fetchone()['setting_value']

    # WhatsApp वर पाठवण्यासाठी लिंक आणि मेसेज
    result_link = request.host_url.rstrip('/') + url_for('detailed_answers', lead_id=new_id)
    wa_message = f"नमस्कार {student_name}, राज्यस्तरीय पोलीस भरती टेस्ट '{test['test_title']}' चा निकाल प्राप्त झाला आहे. गुण: {score}/{total}. तुमचे सविस्तर स्पष्टीकरण व उत्तरपत्रिका पाहण्यासाठी लिंक: {result_link}"

    return render_template_string(RESULT_SUMMARY_TEMPLATE, lead={'student_name': student_name, 'district': district, 'phone': phone, 'score': score, 'total_marks': total, 'test_name': test['test_title']}, state_rank=state_rank, wa_encoded_msg=wa_message, insta_link=insta_link, yt_link=yt_link, toppers_link=toppers_link)

@app.route('/detailed_answers/<int:lead_id>')
def detailed_answers(lead_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE id=%s", (lead_id,))
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

# ----------------- ADMIN ROUTES -----------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('admin_pass')
        with get_db() as conn:
            with conn.cursor() as cur:
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
        with conn.cursor() as cur:
            # लीड्स क्वेरी फिल्टर्ससह
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

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='upi_mobile'")
            upi_mobile = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            toppers_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='razorpay_key_id'")
            razorpay_key_id = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='razorpay_key_secret'")
            razorpay_key_secret = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_info'")
            recruitment_info = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_info'")
            eligibility_info = cur.fetchone()['setting_value']

    top_leads = [(idx, l) for idx, l in enumerate(all_leads_sorted, start=1)]

    return render_template_string(
        ADMIN_TEMPLATE,
        active_tab=active_tab,
        leads=leads,
        tests=tests,
        all_questions=all_questions,
        payments=payments,
        top_leads=top_leads,
        all_districts=all_districts,
        lead_dist=lead_dist,
        lead_test_id=lead_test_id,
        filter_test_id=filter_test_id,
        upi_mobile=upi_mobile,
        insta_link=insta_link,
        yt_link=yt_link,
        toppers_link=toppers_link,
        razorpay_key_id=razorpay_key_id,
        razorpay_key_secret=razorpay_key_secret,
        recruitment_info=recruitment_info,
        eligibility_info=eligibility_info
    )

@app.route('/admin/bulk_questions', methods=['POST'])
def admin_bulk_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    bulk_data = request.form.get('bulk_questions_text', '').strip()

    lines = [l.strip() for l in bulk_data.split('\n') if l.strip()]
    with get_db() as conn:
        with conn.cursor() as cur:
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

@app.route('/admin/approve_payment/<int:lead_id>', methods=['POST'])
def admin_approve_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    token = secrets.token_hex(8)
    expires = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE mock_test_leads 
                SET payment_status='Approved', access_token=%s, token_expires_at=%s 
                WHERE id=%s RETURNING test_id, phone
            """, (token, expires, lead_id))
            row = cur.fetchone()
            conn.commit()

    test_link = request.host_url.rstrip('/') + f"/take_test/{row['test_id']}?token={token}"
    print(f"--- 24HR TEST LINK --- To: {row['phone']} | Link: {test_link}")
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/update_notices', methods=['POST'])
def admin_update_notices():
    if not session.get('admin_logged'): return redirect('/admin/login')
    rec = request.form.get('recruitment_info', '')
    elg = request.form.get('eligibility_info', '')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='recruitment_info'", (rec,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='eligibility_info'", (elg,))
            conn.commit()
    return redirect('/admin/dashboard?tab=notices')

@app.route('/admin/update_password', methods=['POST'])
def admin_update_password():
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_pass = request.form.get('new_password')
    rzp_id = request.form.get('razorpay_key_id', '')
    rzp_sec = request.form.get('razorpay_key_secret', '')
    insta = request.form.get('insta_link', '')
    yt = request.form.get('yt_link', '')
    top = request.form.get('toppers_link', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            if new_pass:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='razorpay_key_id'", (rzp_id,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='razorpay_key_secret'", (rzp_sec,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='insta_link'", (insta,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='yt_link'", (yt,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='toppers_link'", (top,))
            conn.commit()
    return redirect('/admin/dashboard?tab=settings')

@app.route('/admin/delete_lead/<int:lead_id>')
def admin_delete_lead(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mock_test_leads WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/delete_question/<int:q_id>')
def admin_delete_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
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
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status) VALUES (%s, %s, %s, %s, 'Active')", (title, ttype, fee, duration))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM questions WHERE test_id=%s", (test_id,))
            cur.execute("DELETE FROM test_papers WHERE id=%s", (test_id,))
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
