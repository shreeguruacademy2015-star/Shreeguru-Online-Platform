import json
import os
from datetime import date
from flask import Flask, redirect, render_template_string, request, session, url_for
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_master_test_platform_2026_secure"

# --- NEON CLOUD DATABASE CONNECTION ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_master_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            # १. टेस्ट पेपर्स टेबल
            cur.execute('''CREATE TABLE IF NOT EXISTS test_papers (
                id SERIAL PRIMARY KEY,
                test_title TEXT NOT NULL,
                test_type TEXT DEFAULT 'Free',
                test_fee REAL DEFAULT 0,
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

            # ३. विद्यार्थी लीड्स व निकाल टेबल (WhatsApp Verification & Payment सोबत)
            cur.execute('''CREATE TABLE IF NOT EXISTS mock_test_leads (
                id SERIAL PRIMARY KEY,
                test_id INTEGER DEFAULT 1,
                test_date TEXT NOT NULL,
                student_name TEXT NOT NULL,
                district TEXT NOT NULL,
                phone TEXT NOT NULL,
                whatsapp_verified INTEGER DEFAULT 0,
                payment_status TEXT DEFAULT 'Not Required',
                utr_number TEXT DEFAULT '',
                score INTEGER NOT NULL,
                total_marks INTEGER NOT NULL,
                test_name TEXT NOT NULL,
                answers_json TEXT DEFAULT ''
            )''')

            # डीफॉल्ट टेस्ट्स नसल्यास ऍड करणे
            cur.execute('SELECT COUNT(*) as count FROM test_papers')
            if cur.fetchone()['count'] == 0:
                cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0)")
                cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee) VALUES (2, 'आर्मी भरती बौद्धिक व गणित टेस्ट #२', 'Free', 0)")
                conn.commit()

            # डीफॉल्ट प्रश्न नसल्यास ऍड करणे
            cur.execute('SELECT COUNT(*) as count FROM questions')
            if cur.fetchone()['count'] == 0:
                default_qs = [
                    (1, "महाराष्ट्राची आर्थिक व व्यापारी राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B", "मुंबई ही महाराष्ट्राची आर्थिक व व्यापारी राजधानी आहे."),
                    (1, "क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A", "अहमदनगर हा क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा आहे."),
                    (1, "स्वराज्य स्थापना कोणी केली?", "छत्रपती संभाजी महाराज", "छत्रपती शिवाजी महाराज", "महात्मा ज्योतिराव फुले", "संत ज्ञानेश्वर", "B", "छत्रपती शिवाजी महाराजांनी स्वराज्याची स्थापना केली."),
                    (2, "भारताचे राष्ट्रीय गीत कोणते?", "जन गण मन", "वंदे मातरम्", "सारा जहाँ से अच्छा", "जय हिंद", "B", "वंदे मातरम् हे बंकिमचंद्र चटोपाध्याय यांनी रचलेले भारताचे राष्ट्रीय गीत आहे.")
                ]
                cur.executemany('INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', default_qs)
                conn.commit()

init_master_db()

# ----------------- 1. HOME: ATTRACTIVE STUDENT TEST LIST -----------------
HOME_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>श्रीगुरु करिअर अकॅडमी - ऑनलाईन टेस्ट पोर्टल</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: linear-gradient(135deg, #f0fdf4, #e6fffa); color: #1e293b; padding: 15px; }
        .box { max-width: 750px; margin: 25px auto; background: white; border-radius: 14px; padding: 30px; box-shadow: 0 12px 30px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 26px; }
        .sub { text-align: center; color: #475569; font-size: 13px; margin-bottom: 20px; line-height: 1.5; }
        .quote-box { background: #ecfdf5; border-left: 4px solid #059669; padding: 12px 15px; border-radius: 6px; font-size: 14px; color: #065f46; font-weight: bold; text-align: center; margin-bottom: 25px; }
        .test-card { background: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 10px; padding: 18px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; transition: 0.2s; }
        .test-card:hover { border-color: #059669; box-shadow: 0 4px 12px rgba(5,150,105,0.1); }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; box-shadow: 0 3px 8px rgba(5,150,105,0.3); }
        .badge-free { background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-paid { background: #fef9c3; color: #854d0e; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .admin-link { text-align: center; margin-top: 25px; font-size: 12px; }
        .admin-link a { color: #64748b; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
<div class="box">
    <h2>⚔️ श्रीगुरु करिअर अकॅडमी, आडूर</h2>
    <div class="sub">पोलीस व सैन्य भरती पूर्व प्रशिक्षण केंद्र (ता. करवीर, जि. कोल्हापूर)</div>

    <div class="quote-box">
        🔥 "वर्षाचे ३६५ दिवस, घाम गाळायचा एकच निश्चय - खाकी वर्दी आपलीच! आजच आपली तयारी तपासा आणि महाराष्ट्रात स्वतःचे स्थान निर्माण करा." 🌟
    </div>

    <p style="font-size:15px; font-weight:bold; color:#0b3c5d; margin-bottom:15px; border-bottom:2px solid #e2e8f0; padding-bottom:8px;">📝 खालीलपैकी कोणती टेस्ट तुम्हाला सोडवायची आहे?</p>

    {% for t in tests %}
    <div class="test-card">
        <div>
            <h4 style="margin:0 0 6px; color:#0f172a; font-size:16px;">{{ t.test_title }}</h4>
            <span class="{{ 'badge-free' if t.test_type == 'Free' else 'badge-paid' }}">
                {{ '🟢 मोफत महासराव टेस्ट' if t.test_type == 'Free' else '⭐ सशुल्क (Paid) टेस्ट - ₹' ~ t.test_fee }}
            </span>
        </div>
        <a href="/take_test/{{ t.id }}" class="btn-start">✨ टेस्ट सोडवा</a>
    </div>
    {% endfor %}

    <div class="admin-link">
        <a href="/admin/dashboard" target="_blank">⚙️ ॲडमिन डॅशबोर्ड (ऑफिस वापर)</a>
    </div>
</div>
</body>
</html>'''

# ----------------- 2. EXAM PAGE TEMPLATE -----------------
EXAM_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ test.test_title }} - श्रीगुरु अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; }
        .box { max-width: 750px; margin: 20px auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 22px; }
        .sub { text-align: center; color: #475569; font-size: 13px; margin-bottom: 25px; }
        .q-item { margin-bottom: 22px; padding-bottom: 15px; border-bottom: 1px solid #e2e8f0; }
        .q-text { font-weight: bold; margin-bottom: 10px; font-size: 15px; color: #0f172a; }
        .opt-label { display: block; margin-bottom: 8px; font-size: 14px; cursor: pointer; background: #f8fafc; padding: 8px 12px; border-radius: 6px; border: 1px solid #e2e8f0; }
        .opt-label:hover { background: #f1f5f9; }
        input[type="text"], input[type="tel"] { width: 100%; padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #059669, #047857); color: white; padding: 14px; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 12px rgba(5,150,105,0.3); }
    </style>
</head>
<body>
<div class="box">
    <h2>⚔️ {{ test.test_title }}</h2>
    <div class="sub">श्रीगुरु करिअर अकॅडमी, आडूर (जि. कोल्हापूर)</div>

    <form method="POST" action="/submit_test/{{ test.id }}">
        <div style="background:#f8fafc; padding:18px; border-radius:8px; margin-bottom:20px; border:1px solid #cbd5e1;">
            <h4 style="margin:0 0 12px; color:#0b3c5d;">👤 तुमची माहिती भरा:</h4>
            <label style="font-weight:bold; font-size:13px;">पूर्ण नाव *:</label>
            <input type="text" name="student_name" placeholder="उदा. राहुल तानाजी पाटील" required>
            
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                <div>
                    <label style="font-weight:bold; font-size:13px;">जिल्हा *:</label>
                    <input type="text" name="district" placeholder="उदा. कोल्हापूर" required>
                </div>
                <div>
                    <label style="font-weight:bold; font-size:13px;">व्हॉट्सॲप मोबाईल नंबर *:</label>
                    <input type="tel" name="phone" placeholder="१० अंकी नंबर" pattern="[0-9]{10}" required>
                </div>
            </div>
            
            {% if test.test_type == 'Paid' %}
            <div style="margin-top:10px; background:#fffbeb; padding:10px; border-radius:6px; border:1px solid #fcd34d;">
                <label style="font-weight:bold; font-size:12px; color:#92400e;">यमुना / UPI UTR / Transaction No (Payment Fee ₹{{ test.test_fee }} भरून नंबर टाка):</label>
                <input type="text" name="utr_number" placeholder="उदा. UPI Ref No / UTR Number" required style="margin-top:5px; margin-bottom:0;">
            </div>
            {% endif %}
        </div>

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

# ----------------- 3. RESULT & WHATSAPP LOCK TEMPLATE -----------------
RESULT_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>टेस्ट निकाल - श्रीगुरु अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; }
        .box { max-width: 750px; margin: 20px auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 24px; }
        .sub { text-align: center; color: #475569; font-size: 13px; margin-bottom: 25px; }
        .lock-box { background: #fffbeb; border: 2px dashed #f59e0b; padding: 25px; border-radius: 8px; text-align: center; margin-top: 20px; }
        input[type="tel"] { width: 250px; padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px; font-size: 14px; text-align: center; margin-right: 8px; }
        .btn-verify { background: #d97706; color: white; padding: 10px 20px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
<div class="box">
    <h2>⚔️ श्रीगुरु करिअर अकॅडमी, आडूर</h2>
    <div class="sub">परीक्षेचा निकाल व मूल्यमापन डॅशबोर्ड</div>

    <div style="background:#f0fdf4; border:2px solid #86efac; border-radius:8px; padding:20px; text-align:center; margin-bottom:20px;">
        <h3 style="margin:0 0 5px; color:#166534;">टेस्ट यशस्वीरीत्या सबमिट झाली आहे! 🎉</h3>
        <p style="font-size:16px; margin:8px 0;">विद्यार्थ्याचे नाव: <b>{{ lead.student_name }}</b> (जिल्हा: {{ lead.district }})</p>
        <p style="font-size:20px; margin:8px 0;">प्राप्त गुण: <b style="color:#059669; font-size:26px;">{{ lead.score }} / {{ lead.total_marks }}</b></p>
        <p style="font-size:16px; color:#b45309; font-weight:bold; margin-top:10px;">
            🏆 अभिनंदन! तुम्ही संपूर्ण महाराष्ट्रातील विद्यार्थ्यांमध्ये <b style="font-size:20px; color:#92400e;">क्र. #{{ state_rank }}</b> क्रमांकाने पास झाला आहात! 🌟
        </p>
    </div>

    {% if not verified %}
    <!-- LOCK SECTION: WHATSAPP VERIFICATION REQUIRED -->
    <div class="lock-box">
        <h3 style="color:#92400e; margin-top:0;">🔒 उत्तरपत्रिका (Answer Key) व सविस्तर स्पष्टीकरण लॉक आहे!</h3>
        <p style="font-size:13px; color:#78350f; line-height:1.5;">
            कोणते प्रश्न बरोबर आणि कोणते चुकले हे पाहण्यासाठी आणि सविस्तर स्पष्टीकरण वाचण्यासाठी कृपया तुमचा नोंदणीकृत <b>व्हॉट्सॲप नंबर</b> टाकून मोबाईल नंबर व्हेरिफाय करा.
        </p>
        {% if error_msg %}
        <div style="color:red; font-weight:bold; font-size:12px; margin-bottom:10px;">{{ error_msg }}</div>
        {% endif %}
        <form method="POST" action="/verify_whatsapp/{{ lead.id }}">
            <input type="tel" name="verify_phone" placeholder="१० अंकी मोबाईल नंबर" required>
            <button type="submit" class="btn-verify">📲 व्हॉट्सॲप व्हेरिफाय करा</button>
        </form>
    </div>
    {% else %}
    <!-- UNLOCKED SECTION: DETAILED ANSWER KEY & EXPLANATIONS -->
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
            <a href="/" style="background:#0284c7; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold;">🏠 मुख्य टेस्ट यादीकडे जा</a>
        </div>
    </div>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- 4. ADMIN PANEL TEMPLATE (5 TABS IN 1) -----------------
ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ॲडमिन डॅशबोर्ड - श्रीगुरु अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f1f5f9; color: #1e293b; padding: 15px; }
        .container { max-width: 1000px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        h2 { margin: 0 0 15px; color: #065f46; text-align: center; }
        .nav-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
        .nav-tabs a { padding: 8px 14px; background: #e2e8f0; color: #334155; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; }
        .nav-tabs a.active { background: #059669; color: white; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }
        th { background: #f8fafc; color: #0f172a; }
        input[type="text"], input[type="number"], select { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; margin-bottom: 8px; font-size: 13px; }
        .btn { background: #059669; color: white; padding: 8px 14px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
        .btn-sm { padding: 4px 8px; font-size: 11px; text-decoration: none; border-radius: 3px; display: inline-block; }
    </style>
</head>
<body>
<div class="container">
    <h2>⚙️ श्रीगुरु करिअर अकॅडमी - ॲडमिन मॅनेजमेंट डॅशबोर्ड</h2>
    <div style="text-align:right; margin-bottom:10px;"><a href="/" style="font-weight:bold; color:#0284c7; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a></div>

    <!-- TABS NAVIGATION -->
    <div class="nav-tabs">
        <a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 चौकशी व टेस्ट डेस्क (Leads)</a>
        <a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 पेमेंट व वैधता डेस्क (Payments)</a>
        <a href="/admin/dashboard?tab=questions" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 प्रश्न व्यवस्थापन (Questions)</a>
        <a href="/admin/dashboard?tab=launch" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 टेस्ट लॉन्च व स्टेटस (Launch)</a>
        <a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 राज्यस्तरीय लीडरबोर्ड (Leaderboard)</a>
    </div>

    <!-- TAB 1: LEADS / INQUIRIES -->
    {% if active_tab == 'leads' %}
    <h3>📱 सर्व विद्यार्थ्यांची टेस्ट माहिती व मोबाईल क्रमांक (Inquiries & Leads)</h3>
    <table>
        <tr>
            <th>दिनांक</th>
            <th>विद्यार्थ्याचे नाव</th>
            <th>जिल्हा</th>
            <th>मोबाईल नंबर (WhatsApp)</th>
            <th>टेस्टचे नाव</th>
            <th>गुण</th>
        </tr>
        {% for l in leads %}
        <tr>
            <td>{{ l.test_date }}</td>
            <td><b>{{ l.student_name }}</b></td>
            <td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td>
            <td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
        </tr>
        {% endfor %}
    </table>

    <!-- TAB 2: PAYMENTS -->
    {% elif active_tab == 'payments' %}
    <h3>💰 पेड टेस्ट पेमेंट व वैधता तपासणी (Payment & Validity Desktop)</h3>
    <table>
        <tr>
            <th>विद्यार्थी नाव</th>
            <th>मोबाईल</th>
            <th>टेस्ट</th>
            <th>UTR / Ref Number</th>
            <th>स्थिती (Status)</th>
            <th>कृती (Action)</th>
        </tr>
        {% for p in payments %}
        <tr>
            <td>{{ p.student_name }}</td>
            <td>{{ p.phone }}</td>
            <td>{{ p.test_name }}</td>
            <td><b>{{ p.utr_number if p.utr_number else 'N/A' }}</b></td>
            <td><span style="color:{{ 'green' if p.payment_status == 'Approved' else 'orange' }}; font-weight:bold;">{{ p.payment_status }}</span></td>
            <td>
                {% if p.payment_status != 'Approved' %}
                <a href="/admin/approve_payment/{{ p.id }}" class="btn-sm" style="background:#16a34a; color:white;">✅ Approve करा</a>
                {% else %}
                <span style="color:gray;">Completed</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- TAB 3: QUESTIONS -->
    {% elif active_tab == 'questions' %}
    <h3>📝 नवीन प्रश्न ॲड करणे (Question Management)</h3>
    <form method="POST" action="/admin/add_question" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
        <label style="font-weight:bold; font-size:12px;">टेस्ट निवडा:</label>
        <select name="test_id">
            {% for t in tests %}
            <option value="{{ t.id }}">{{ t.test_title }}</option>
            {% endfor %}
        </select>
        <label style="font-weight:bold; font-size:12px;">प्रश्न:</label>
        <input type="text" name="question" placeholder="प्रश्नाची महिती लिहा" required>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
            <input type="text" name="opt_a" placeholder="पर्याय A" required>
            <input type="text" name="opt_b" placeholder="पर्याय B" required>
            <input type="text" name="opt_c" placeholder="पर्याय C" required>
            <input type="text" name="opt_d" placeholder="पर्याय D" required>
        </div>
        <label style="font-weight:bold; font-size:12px;">अचूक उत्तर (A, B, C किंवा D):</label>
        <input type="text" name="correct" placeholder="उदा. B" maxlength="1" required style="width:100px;">
        <label style="font-weight:bold; font-size:12px;">सविस्तर स्पष्टीकरण (Explanation):</label>
        <input type="text" name="explanation" placeholder="प्रश्नाचे स्पष्टीकरण लिहा">
        <button type="submit" class="btn" style="margin-top:5px;">➕ प्रश्न सेव्ह करा</button>
    </form>

    <!-- TAB 4: LAUNCH & STATUS -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 टेस्ट लॉन्च व नवीन टेस्ट तयार करणे (Test Launch & Status)</h3>
    <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <label style="font-weight:bold; font-size:12px;">नवीन टेस्टचे नाव:</label>
        <input type="text" name="test_title" placeholder="उदा. पोलीस भरती विशेष टेस्ट #३" required>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
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
        </div>
        <button type="submit" class="btn" style="margin-top:5px;">🚀 नवीन टेस्ट लॉन्च करा</button>
    </form>

    <h4>सध्याच्या लाईव्ह टेस्ट्स:</h4>
    <table>
        <tr><th>ID</th><th>टेस्ट नाव</th><th>प्रकार</th><th>फी</th><th>स्थिती</th></tr>
        {% for t in tests %}
        <tr><td>{{ t.id }}</td><td>{{ t.test_title }}</td><td>{{ t.test_type }}</td><td>₹{{ t.test_fee }}</td><td>{{ t.status }}</td></tr>
        {% endfor %}
    </table>

    <!-- TAB 5: LEADERBOARD -->
    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 राज्यस्तरीय लीडरबोर्ड / टॉपर डेस्क (State Leaderboard)</h3>
    <table>
        <tr>
            <th>रँक (Rank)</th>
            <th>विद्यार्थ्याचे नाव</th>
            <th>जिल्हा</th>
            <th>टेस्टचे नाव</th>
            <th>गुण</th>
        </tr>
        {% for rank, l in top_leads %}
        <tr>
            <td><b>#{{ rank }}</b></td>
            <td>{{ l.student_name }}</td>
            <td>{{ l.district }}</td>
            <td>{{ l.test_name }}</td>
            <td><b style="color:#059669;">{{ l.score }} / {{ l.total_marks }}</b></td>
        </tr>
        {% endfor %}
    </table>
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
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()
    if not test: return "Test not found", 404
    return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    name = request.form.get('student_name')
    district = request.form.get('district')
    phone = request.form.get('phone')
    utr_number = request.form.get('utr_number', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()

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
    pay_status = 'Pending' if test['test_type'] == 'Paid' else 'Not Required'

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, whatsapp_verified, payment_status, utr_number, score, total_marks, test_name, answers_json)
                VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (test_id, t_date, name, district, phone, pay_status, utr_number, score, total, test['test_title'], ans_json_str))
            new_id = cur.fetchone()['id']
            conn.commit()

    return redirect(f'/result_view/{new_id}')

@app.route('/result_view/<int:lead_id>')
def result_view(lead_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead: return "Result not found", 404

            # राज्यस्तरीय रँक काढणे
            cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s", (lead['test_id'], lead['score']))
            higher_count = cur.fetchone()['higher']
            state_rank = higher_count + 1

    verified = (lead['whatsapp_verified'] == 1)
    evaluated_questions = []

    if verified:
        user_ans_dict = json.loads(lead['answers_json'] or '{}')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (lead['test_id'],))
                questions = cur.fetchall()

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

    return render_template_string(RESULT_TEMPLATE, lead=lead, state_rank=state_rank, verified=verified, evaluated_questions=evaluated_questions, error_msg=None)

@app.route('/verify_whatsapp/<int:lead_id>', methods=['POST'])
def verify_whatsapp(lead_id):
    entered_phone = request.form.get('verify_phone', '').strip()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()

    if not lead: return "Lead not found", 404

    if entered_phone == lead['phone']:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE mock_test_leads SET whatsapp_verified=1 WHERE id=%s", (lead_id,))
                conn.commit()
        return redirect(f'/result_view/{lead_id}')
    else:
        user_ans_dict = json.loads(lead['answers_json'] or '{}')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s", (lead['test_id'], lead['score']))
                state_rank = cur.fetchone()['higher'] + 1
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (lead['test_id'],))
                questions = cur.fetchall()

        evaluated_questions = []
        for q in questions:
            u_ans = user_ans_dict.get(str(q['id']), 'सोडवले नाही')
            evaluated_questions.append({
                'q_text': q['question'], 'user_ans': u_ans, 'correct_ans': q['correct'],
                'is_correct': (u_ans == q['correct']), 'explanation': q['explanation']
            })

        return render_template_string(RESULT_TEMPLATE, lead=lead, state_rank=state_rank, verified=False, evaluated_questions=evaluated_questions, error_msg="❌ चुकीचा मोबाईल नंबर! कृपया तुम्ही फॉर्म भरताना दिलेला १० अंकी व्हॉट्सॲप नंबरच टाका.")

# ----------------- ADMIN DASHBOARD ROUTES -----------------
@app.route('/admin/dashboard')
def admin_dashboard():
    active_tab = request.args.get('tab', 'leads')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads ORDER BY id DESC")
            leads = cur.fetchall()
            cur.execute("SELECT * FROM test_papers ORDER BY id ASC")
            tests = cur.fetchall()
            cur.execute("SELECT * FROM mock_test_leads WHERE payment_status != 'Not Required' ORDER BY id DESC")
            payments = cur.fetchall()
            cur.execute("SELECT * FROM mock_test_leads ORDER BY score DESC, id ASC LIMIT 50")
            all_leads_sorted = cur.fetchall()

    top_leads = []
    for idx, l in enumerate(all_leads_sorted, start=1):
        top_leads.append((idx, l))

    return render_template_string(ADMIN_TEMPLATE, active_tab=active_tab, leads=leads, tests=tests, payments=payments, top_leads=top_leads)

@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    title = request.form.get('test_title')
    ttype = request.form.get('test_type')
    fee = float(request.form.get('test_fee', 0))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_papers (test_title, test_type, test_fee, status) VALUES (%s, %s, %s, 'Active')", (title, ttype, fee))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/add_question', methods=['POST'])
def admin_add_question():
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

@app.route('/admin/approve_payment/<int:lead_id>')
def admin_approve_payment(lead_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET payment_status='Approved' WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

