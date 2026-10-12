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

# क्रिप्टोग्राफिक लिंक सिग्नेचर जनरेटर व व्हेरिफायर (HMAC-SHA256)
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
            print(f"Razorpay Client Init Error: {e}")
            return None, key_id
            
    return None, ""

# =============================================================================
# TEMPLATES SECTION (पूर्णपणे AI शब्दमुक्त फ्रंट-एंड)
# =============================================================================

TERMS_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>नियम, अटी व कायदेशीर घोषणापत्र</title>
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
    <p><small>अद्यतन: ऑक्टोबर २०२६</small></p>
    
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
    <h2>पोर्टलचे तांत्रिक काम सुरू आहे!</h2>
    <p>विद्यार्थ्यांना अधिक गतिमान अनुभव देण्यासाठी नियोजित तांत्रिक सुधारणा सुरू आहेत.</p>
    <p style="color:#34d399; font-weight:bold;">लवकरच ही वेबसाईट पूर्ण क्षमतेने सुरू होईल. खाकीच्या तयारीसाठी थोडा वेळ संयम ठेवा! ⚔️</p>
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
        
        /* माहिती बॅनर */
        .tab-info-banner { background: #0f172a; border: 1.5px solid #38bdf8; border-radius: 10px; padding: 12px 16px; margin-bottom: 20px; text-align: center; color: #7dd3fc; font-size: 13.5px; font-weight: 600; display: block; }

        .tabs-wrapper { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-bottom: 20px; }
        .tab-btn { background: #334155; color: #cbd5e1; border: 1.5px solid #475569; padding: 10px 16px; border-radius: 30px; font-size: 13px; font-weight: 700; cursor: pointer; }
        .tab-btn:hover, .tab-btn.active { background: #10b981; color: #022c22; border-color: #34d399; }
        .test-grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
        .test-card { background: #0f172a; border: 1.5px solid #334155; border-radius: 12px; padding: 18px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
        .test-title { margin: 0 0 6px; color: #f1f5f9; font-size: 17px; font-weight: 700; }
        .badge-free { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #059669; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .badge-paid { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #d97706; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .badge-rapid { background: rgba(59,130,246,0.2); color: #60a5fa; border: 1px solid #2563eb; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .btn-start { background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 10px 22px; border-radius: 8px; text-decoration: none; font-weight: 800; font-size: 13.5px; border:none; cursor:pointer; }
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
        const tabInfoMap = {
            'all': '🌐 सर्व उपलब्ध पोलीस भरती सराव संच खालीलप्रमाणे उपलब्ध आहेत.',
            'live': '🔴 मिशन खाकी महासंग्राम: थेट वेळेवर सुरू होणारा विशेष सराव कक्ष.',
            'paid': '🎯 अतिसंभाव्य १०० गुण संच: सविस्तर अचूक स्पष्टीकरण व परिपूर्ण दर्जेदार प्रश्न.',
            'free': '🟢 मोफत टेस्ट्स: स्वतःची गुणवत्ता तपासण्यासाठी विशेष मोफत सराव संच.',
            'rapid': '⚡ २० गुण रॅपिड फायर: दररोज सकाळी १०:०० वाजता वेग आणि अचूकतेची कसोटी.',
            'battle': '⚔️ जिल्हा मुकाबला: महाराष्ट्रातील सर्व जिल्ह्यांमधील विद्यार्थ्यांची सरासरी तुलना.',
            'docs': '📄 अधिकृत भरती जाहिरात आणि मागील वर्षांच्या प्रश्नपत्रिका (PDF).',
            'help': '📞 कोणत्याही तांत्रिक किंवा सराव अडचणीसाठी आमचा संपर्क कक्ष.'
        };

        function filterTab(category, btn, customTitle) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const infoBanner = document.getElementById('tabInfoBanner');
            if (tabInfoMap[category]) {
                infoBanner.innerText = tabInfoMap[category];
            } else {
                infoBanner.innerText = '🎯 ' + (customTitle || 'विशेष विभाग') + ' मधील सर्व सराव प्रश्नसंच खालीलप्रमाणे:';
            }

            document.getElementById('testsContainer').style.display = 'none';
            document.getElementById('battleContainer').style.display = 'none';
            document.getElementById('docsContainer').style.display = 'none';
            document.getElementById('helpContainer').style.display = 'none';

            if (category === 'battle') {
                document.getElementById('battleContainer').style.display = 'block';
            } else if (category === 'docs') {
                document.getElementById('docsContainer').style.display = 'block';
            } else if (category === 'help') {
                document.getElementById('helpContainer').style.display = 'block';
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

        // लाईव्ह उपस्थिती हार्टबीट (दर ६० सेकंदांनी सर्व्हरला सिग्नल)
        setInterval(function() {
            fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
        }, 60000);
    </script>
</head>
<body>
<div id="loadingNoticeModal" class="loading-modal">
    <div class="modal-content">
        <h3 style="color:#34d399; margin:0 0 10px; font-size:20px;">🛡️ परीक्षा कक्ष लोड होत आहे...</h3>
        <p style="color:#cbd5e1; font-size:14px; line-height:1.6; margin:0 0 20px;">
            ⏳ <b>महाराष्ट्र पोलीस भरती टेस्ट पोर्टलवर आपले स्वागत आहे, आपली टेस्ट पेज सुरू होत आहे...</b> कृपया क्षणभर प्रतीक्षा करा!
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
    <div style="font-size:12px; color:#38bdf8; font-weight:bold;">
        👥 सध्या सराव करणारे: {{ active_students_count }} विद्यार्थी
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

    <!-- डायनॅमिक माहिती मार्गदर्शक बॉक्स -->
    <div id="tabInfoBanner" class="tab-info-banner">
        🌐 सर्व उपलब्ध पोलीस भरती सराव संच खालीलप्रमाणे उपलब्ध आहेत.
    </div>

    <!-- डायनॅमिक टॅब्स -->
    <div class="tabs-wrapper">
        {% for tab_item in parsed_home_tabs %}
            <button class="tab-btn {{ 'active' if loop.first else '' }}" onclick="filterTab('{{ tab_item.key }}', this, '{{ tab_item.label }}')">
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
                    <span class="{{ 'badge-free' if t.test_type == 'Free' else 'badge-paid' }}">
                        {{ '🟢 मोफत महासराव' if t.test_type == 'Free' else '⭐ अतिसंभाव्य संच - ₹' ~ t.test_fee }}
                    </span>
                    <span class="badge-rapid">⏱️ {{ t.duration_minutes }} मिनिटे</span>
                    {% if t.is_locked and t.category == 'rapid' %}
                    <span style="font-size:12px; color:#fbbf24;">⏳ पुढील टेस्ट दुसऱ्या दिवशी सकाळी १०:०० वाजता अनलॉक होईल</span>
                    {% endif %}
                </div>
            </div>
            {% if t.is_locked %}
                <span class="btn-locked">🔒 सकाळी १०:०० ला उघडेल</span>
            {% else %}
                <button onclick="openLoadingNotice('/take_test/{{ t.id }}')" class="btn-start">🚀 टेस्ट सोडवा</button>
            {% endif %}
        </div>
        {% endfor %}
        <div id="noTestMsg" style="display:none; text-align:center; padding:35px 20px; background:#0f172a; border-radius:12px; border:1px dashed #475569; color:#94a3b8; font-size:15px;">
            🎯 <b>लवकरच या विभागात अतिसंभाव्य व दर्जेदार प्रश्नसंच उपलब्ध होतील!</b><br>
            <span style="font-size:13px; color:#64748b;">आमचे तज्ज्ञ शिक्षक नवीन दर्जेदार प्रश्नांची रचना करत आहेत. खाकीची तयारी अखंड चालू ठेवा! ⚔️</span>
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
        <p style="font-size:14px; color:#cbd5e1; margin-bottom:15px;">टेस्ट किंवा पेमेंट संदर्भात काही अडचण असल्यास खालील क्रमांकावर संपर्क साधा:</p>
        <div style="background:#1e293b; padding:18px; border-radius:10px; border:1px solid #334155; display:inline-block; text-align:left; max-width:400px; width:100%;">
            <p style="margin:6px 0; color:#f8fafc;">📱 <b>हेल्पलाईन नंबर:</b> <a href="https://wa.me/91{{ help_phone }}" target="_blank" style="color:#34d399; font-weight:bold;">{{ help_phone }}</a></p>
            <p style="margin:6px 0; color:#f8fafc;">📍 <b>पत्ता / ऑफिस पत्ता:</b> {{ help_address }}</p>
        </div>
    </div>

    <div class="footer">
        <span>© २०२६ महाराष्ट्र पोलीस भरती सराव प्रश्नसंच ऑनलाईन व्यासपीठ | </span>
        <a href="/terms-and-conditions" target="_blank" style="color:#38bdf8;">नियम व अटी (Terms & Conditions)</a>
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
        .btn-report { background: none; border: none; color: #94a3b8; font-size: 11.5px; cursor: pointer; margin-top: 6px; text-decoration: underline; }
        .btn-report:hover { color: #f87171; }
        .bottom-submission-card { background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(15,23,42,0.9)); border: 2px solid #10b981; border-radius: 14px; padding: 22px; margin-top: 30px; }
        .bottom-submission-card input, .bottom-submission-card select { width: 100%; padding: 13px; background: #0f172a; border: 1.5px solid #334155; border-radius: 8px; margin-top: 5px; font-size: 14.5px; margin-bottom: 12px; color: white; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #10b981, #059669); color: #022c22; padding: 15px; border: none; border-radius: 8px; font-size: 17px; font-weight: 800; cursor: pointer; }
        .btn-submit:disabled { background: #334155; color: #64748b; cursor: not-allowed; }
    </style>
    <script>
        let isFormSubmitted = false;
        const testStorageKey = 'police_saved_answers_{{ test.id }}';
        const timerStorageKey = 'police_saved_timer_{{ test.id }}';

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
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">WhatsApp मोबाईल नंबर *:</label><input type="tel" name="phone" id="s_phone" placeholder="10 अंकी मोबाईल नंबर" maxlength="10" onkeyup="validateAndReady()" required></div>
            </div>
        </div>
        <button type="submit" id="submitBtn" class="btn-submit" disabled>⚠️ नाव, जिल्हा व WhatsApp नंबर भरा</button>
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
        .share-unlock-box { background: rgba(245,158,11,0.15); border: 2px dashed #f59e0b; border-radius: 12px; padding: 18px; margin: 18px 0; text-align: center; color: #fde68a; }
        .cert-card { background: linear-gradient(135deg, #1e293b, #0f172a); color: white; border: 3px double #f59e0b; padding: 22px; border-radius: 12px; margin: 20px 0; text-align: center; }
        .btn-wa { display: inline-block; background: #25D366; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 15px; margin: 8px 4px; cursor: pointer; border: none; }
        .btn-group { display: block; background: linear-gradient(135deg, #25D366, #128C7E); color: white; padding: 14px 20px; border-radius: 10px; text-decoration: none; font-weight: 800; font-size: 15px; text-align: center; margin: 20px 0; box-shadow: 0 6px 18px rgba(37,211,102,0.3); border: 1.5px solid #86efac; cursor: pointer; }
        .promo-box { background: #0f172a; border: 1.5px solid #334155; padding: 15px; border-radius: 10px; margin-top: 20px; text-align: center; }
        .btn-link { display: inline-block; color: white; padding: 10px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; margin: 4px; cursor: pointer; border: none; }
    </style>
</head>
<body>
<div class="box">
    <h2 style="color:#34d399; margin:0 0 5px; text-align:center;">🎉 टेस्ट यशस्वीरीत्या पूर्ण झाली!</h2>
    <div style="background:#0f172a; border:1px solid #334155; border-radius:12px; padding:18px; margin:15px 0; text-align:center;">
        <p style="font-size:16px; margin:4px 0; color:#cbd5e1;">परीक्षार्थी: <b>{{ lead.student_name }}</b> (जिल्हा: <b>{{ lead.district }}</b> | संवर्ग: <b style="color:#34d399;">{{ lead.caste_category }}</b>)</p>
        
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:10px; margin-top:15px;">
            <div style="background:#1e293b; padding:12px; border-radius:8px; border:1px solid #475569;">
                <span style="font-size:12px; color:#94a3b8;">🏆 महाराष्ट्र राज्य रँक:</span>
                <div style="font-size:26px; color:#fbbf24; font-weight:bold;">#{{ state_rank }}</div>
            </div>
            <div style="background:#1e293b; padding:12px; border-radius:8px; border:1px solid #475569;">
                <span style="font-size:12px; color:#94a3b8;">📍 जिल्हा रँक ({{ lead.district }}):</span>
                <div style="font-size:26px; color:#38bdf8; font-weight:bold;">#{{ district_rank }}</div>
            </div>
            <div style="background:#1e293b; padding:12px; border-radius:8px; border:1px solid #10b981;">
                <span style="font-size:12px; color:#a7f3d0;">🎯 {{ lead.caste_category }} संवर्ग रँक:</span>
                <div style="font-size:26px; color:#34d399; font-weight:bold;">#{{ category_rank }}</div>
            </div>
        </div>

        <p style="font-size:12px; color:#fbbf24; margin-top:12px;">
            ⚡ <i>हा थेट तात्पुरता रँक आहे; उर्वरित विद्यार्थ्यांचे पेपर्स संपल्यानंतर २४ तासांनी अंतिम मेरिट लिस्ट प्रसिद्ध होईल.</i>
        </p>

        <p style="font-size:20px; font-weight:bold; color:#f8fafc; margin-top:8px;">प्राप्त गुण: <span style="color:#10b981;">{{ lead.score }}</span> / {{ lead.total_marks }}</p>

        <div style="background:rgba(16,185,129,0.1); border:1px solid #059669; border-radius:8px; padding:10px; margin-top:10px; font-size:13px; color:#a7f3d0;">
            💡 <b>कट-ऑफ अंदाज:</b> मागील भरतीतील लेखी कट-ऑफनुसार आपले गुण <b>सुरक्षित क्षेत्रात (Safe Selection Zone)</b> आहेत!
        </div>
    </div>

    {% if test_category == 'free' %}
    <div class="share-unlock-box">
        <h3 style="margin:0 0 6px; font-size:18px; color:#fbbf24;">🎁 विशेष ऑफर: पहिल्या २ अतिसंभाव्य पेड टेस्ट्स मोफत अनलॉक करा!</h3>
        <p style="font-size:13.5px; line-height:1.5; margin:0 0 10px;">
            ही लिंक तुमच्या ३ मित्रांना पाठवा. त्यांनी ही मोफत टेस्ट पूर्ण सोडवून सबमिट केल्यास तुम्हाला पहिल्या २ सशुल्क टेस्ट्स मोफत अनलॉक होतील!
        </p>
        <div style="background:#0f172a; padding:6px 12px; border-radius:20px; display:inline-block; font-size:13px; font-weight:bold; color:#38bdf8;">
            📡 मित्रांनी सोडवलेल्या टेस्ट्स: {{ completed_friends_count }} / ३
        </div><br>
        {% if completed_friends_count >= 3 %}
            <p style="color:#34d399; font-weight:bold; margin-top:8px;">✅ अभिनंदन! ३ मित्रांनी टेस्ट सोडवली आहे. पहिल्या २ टेस्ट्स अनलॉक झाल्या आहेत!</p>
        {% endif %}
        <a href="https://wa.me/?text={{ ego_share_encoded }}" target="_blank" class="btn-wa">📲 ३ मित्रांना WhatsApp वर पाठवा</a>
    </div>
    {% endif %}

    {% if wa_active_link %}
    <a href="{{ wa_active_link }}" target="_blank" class="btn-group">
        📲 दररोज सकाळी १०:०० वाजता मोफत रॅपिड टेस्ट मिळवण्यासाठी अधिकृत WhatsApp ग्रुपमध्ये सामील व्हा ➔
    </a>
    {% endif %}

    <div class="cert-card">
        <h3 style="color:#fde047; margin:0 0 6px; font-size:20px;">🎖️ मिशन खाकी २०२६ — स्वाभिमान चॅलेंज</h3>
        <p style="font-size:15px; color:#a7f3d0; margin:10px 0; font-weight:bold; line-height:1.5;">
            "🔥 तुझ्यासोबत तुझा मित्रही भरती झाला पाहिजे! त्यालाही ही लिंक पाठव आणि आव्हान दे!"
        </p>
        <a href="https://wa.me/?text={{ ego_share_encoded }}" target="_blank" class="btn-wa">⚔️ मित्रांना WhatsApp वर आव्हान द्या</a>
    </div>

    <!-- सविस्तर उत्तरतालिका व स्पष्टीकरण बटण -->
    <div style="text-align:center; margin:20px 0;">
        <a href="{{ result_url }}" target="_blank" style="background:#10b981; color:#022c22; padding:12px 26px; border-radius:8px; text-decoration:none; font-weight:800; display:inline-block;">📖 सविस्तर उत्तरतालिका व तज्ज्ञ स्पष्टीकरण पहा</a>
    </div>

    <div class="promo-box">
        <h4 style="margin:0 0 10px; color:#34d399;">🌟 अधिकृत सोशल मीडिया व यशोगाथा लिंक्स:</h4>
        <a href="{{ insta_link if insta_link else '#' }}" target="_blank" class="btn-link" style="background:#E1306C;">📸 Instagram</a>
        <a href="{{ yt_link if yt_link else '#' }}" target="_blank" class="btn-link" style="background:#FF0000;">▶ YouTube</a>
        <a href="{{ toppers_link if toppers_link else '#' }}" target="_blank" class="btn-link" style="background:#0284c7;">🏆 यशवंतांचे फोटो</a>
    </div>
</div>
</body>
</html>'''

ACCESS_CHECK_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>सशुल्क टेस्ट प्रवेश द्वार - {{ test.test_title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        body { font-family:'Poppins', sans-serif; background:#0b1329; color:#f1f5f9; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }
        .box { max-width:480px; width:100%; background:#162036; border-radius:16px; padding:25px; box-shadow:0 15px 35px rgba(0,0,0,0.4); border-top:6px solid #10b981; }
        input { width:100%; padding:11px; background:#0f172a; border:1.5px solid #334155; border-radius:8px; margin-bottom:12px; font-size:14px; box-sizing:border-box; color:white; }
        .btn-rzp { width:100%; background:linear-gradient(135deg, #2563eb, #1d4ed8); color:white; padding:14px; border:none; border-radius:8px; font-weight:800; cursor:pointer; font-size:15px; margin-bottom:15px; }
        .fomo-timer { background: rgba(239,68,68,0.15); border: 1.5px solid #ef4444; color: #fca5a5; padding: 8px 12px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 13.5px; margin-bottom: 15px; }
        .fear-banner { background: #fef2f2; border-left: 4px solid #ef4444; padding: 10px 14px; margin-bottom: 15px; border-radius: 4px; font-size: 12.5px; color: #991b1b; line-height: 1.5; }
    </style>
</head>
<body>
<div class="box">
    <div class="fomo-timer">
        ⚡ विशेष सवलत संपण्यासाठी उर्वरित वेळ: <span id="fomo-countdown">14:59</span>
    </div>

    <div class="fear-banner">
        🔥 <b>गेल्या वर्षी १ मार्काने खाकी वर्दी हुकली होती का?</b><br>
        एका मार्काची किंमत १ वर्षाची मेहनत असते! आज ₹९९ वाचवून रिस्क घेऊ नका, अतिसंभाव्य १०० प्रश्न आत्ताच सोडवा.
    </div>

    <h2 style="color:#34d399; text-align:center; margin:0 0 5px;">🔒 अतिसंभाव्य १०० गुण टेस्ट प्रवेश द्वार</h2>
    <p style="text-align:center; font-size:13px; color:#94a3b8;">{{ test.test_title }} (सवलत फी: ₹{{ test.test_fee }})</p>

    <div style="background:#0f172a; border:1px solid #334155; padding:14px; border-radius:8px; margin-bottom:15px;">
        <p style="margin:0 0 8px; font-size:12.5px; font-weight:bold; color:#60a5fa;">🔄 तुम्ही ३ मित्रांना जोडून टेस्ट अनलॉक केली असल्यास:</p>
        <form method="POST" action="/verify_share_phone/{{ test.id }}">
            <input type="tel" name="verify_phone" placeholder="नोंदवलेला 10 अंकी WhatsApp नंबर" maxlength="10" required style="margin-bottom:8px;">
            <button type="submit" style="background:#2563eb; color:white; border:none; padding:8px; border-radius:6px; font-weight:bold; width:100%; font-size:12.5px; cursor:pointer;">🔓 मोफत ॲक्सेस तपासा</button>
        </form>
    </div>

    <div style="text-align:center;">
        <button id="rzp-button" class="btn-rzp">⚡ GooglePay / PhonePe द्वारे पेमेंट करा (₹{{ test.test_fee }})</button>
    </div>

    {% if upi_mobile or qr_url %}
    <div style="background:#0f172a; padding:14px; border-radius:8px; border:1px solid #f59e0b; text-align:center; margin-bottom:15px;">
        {% if upi_mobile %}
        <p style="margin:0 0 6px; font-weight:bold; color:#fbbf24; font-size:12px;">किंवा QR स्कॅन करून <b>{{ upi_mobile }}</b> वर पे करा:</p>
        {% endif %}
        {% if qr_url %}
        <img src="{{ qr_url }}" alt="QR" style="max-width:130px; max-height:130px; border-radius:6px; display:inline-block;">
        {% endif %}
    </div>
    {% endif %}

    <form method="POST" action="/request_paid_test/{{ test.id }}">
        <input type="text" name="student_name" placeholder="पूर्ण नाव" required>
        <input type="text" name="district" placeholder="जिल्हा" required>
        <input type="tel" name="phone" placeholder="10 अंकी WhatsApp नंबर" maxlength="10" required>
        <div style="font-size:11.5px; color:#cbd5e1; margin-bottom:10px;">
            <label><input type="checkbox" required checked> मी सर्व नियम, अटी व नो-रिफंड पॉलिसी मान्य करतो.</label>
        </div>
        <button type="submit" style="width:100%; background:#10b981; color:#022c22; padding:11px; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">🚀 मॅन्युअल स्क्रीनशॉट पाठवला आहे</button>
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
            "name": "महाराष्ट्र पोलीस भरती सराव व्यासपीठ",
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
        .container { max-width: 1250px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        h2 { margin: 0 0 15px; color: #065f46; text-align: center; }
        .nav-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
        .nav-tabs a { padding: 8px 14px; background: #e2e8f0; color: #334155; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; }
        .nav-tabs a.active { background: #059669; color: white; }
        .sub-nav-tabs { display: flex; gap: 8px; margin-bottom: 15px; background: #f8fafc; padding: 8px; border-radius: 8px; border: 1px solid #cbd5e1; }
        .sub-nav-tabs a { padding: 6px 14px; background: white; color: #334155; border: 1px solid #cbd5e1; border-radius: 6px; text-decoration: none; font-size: 12.5px; font-weight: 600; }
        .sub-nav-tabs a.active { background: #10b981; color: #064e3b; border-color: #059669; font-weight: bold; }
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
        function toggleSelectAll(master, className) {
            document.querySelectorAll('.' + className).forEach(cb => cb.checked = master.checked);
        }
        function switchTestView(testId, subtab) {
            window.location.href = '/admin/dashboard?tab=questions&q_subtab=' + subtab + '&filter_test_id=' + testId;
        }
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
            btn.innerText = '⏳ प्रश्न तयार होत आहेत...';
            btn.disabled = true;

            fetch('/admin/ai_generate_advanced', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({department: dept, subject_counts: subjectCounts, test_id: testId})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("✅ " + data.inserted_count + " नवीन प्रश्न सेव्ह झाले!");
                    window.location.href = '/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id=' + testId;
                } else {
                    alert("⚠️ एरर: " + (data.error || 'अज्ञात एरर'));
                }
                btn.innerText = '🤖 डिजिटल स्मार्ट प्रश्न जनरेट करा';
                btn.disabled = false;
            })
            .catch(() => {
                alert("सर्व्हर एरर आला!");
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

    {% if undo_items %}
    <div style="background:#fef3c7; border:1px solid #f59e0b; padding:10px 15px; border-radius:6px; margin-bottom:15px; display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:12.5px; color:#92400e;">⚠️ अलीकडे डिलीट केलेली नोंद: <b>{{ undo_items[0].title[:35] }}...</b></span>
        <a href="/admin/undo_delete/{{ undo_items[0].type }}/{{ undo_items[0].id }}" class="btn-sm" style="background:#d97706; color:white; font-weight:bold;">↩ पूर्ववत करा (Undo)</a>
    </div>
    {% endif %}

    <div class="nav-tabs">
        {% for tab in ordered_admin_tabs %}
            {% if tab == 'leads' %}<a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 Leads (विद्यार्थी डेटा)</a>
            {% elif tab == 'payments' %}<a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 Payments & Razorpay</a>
            {% elif tab == 'special' %}<a href="/admin/dashboard?tab=special" class="{{ 'active' if active_tab == 'special' else '' }}">👑 Special Access</a>
            {% elif tab == 'questions' %}<a href="/admin/dashboard?tab=questions&q_subtab={{ q_subtab }}{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions</a>
            {% elif tab == 'launch' %}<a href="/admin/dashboard?tab=launch&cat_tab={{ cat_tab }}" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Tests Management</a>
            {% elif tab == 'leaderboard' %}<a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard</a>
            {% elif tab == 'feedback' %}<a href="/admin/dashboard?tab=feedback" class="{{ 'active' if active_tab == 'feedback' else '' }}">💬 Feedback</a>
            {% elif tab == 'notices' %}<a href="/admin/dashboard?tab=notices" class="{{ 'active' if active_tab == 'notices' else '' }}">📢 PDF Docs</a>
            {% elif tab == 'trash' %}<a href="/admin/dashboard?tab=trash" class="{{ 'active' if active_tab == 'trash' else '' }}">🗑️ Recycle Bin</a>
            {% elif tab == 'settings' %}<a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Settings (टॅब व्यवस्थापन)</a>
            {% endif %}
        {% endfor %}
    </div>

    <!-- 1. LEADS TAB -->
    {% if active_tab == 'leads' %}
    <h3>📱 विद्यार्थ्यांची लीड्स यादी</h3>
    <div style="background:#f8fafc; padding:12px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:15px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
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
        <a href="/admin/export_leads_csv" class="btn" style="background:#10b981; text-decoration:none; font-size:12px; padding:6px 12px;">📥 सर्व लीड्स Excel/CSV डाउनलोड</a>
    </div>
    <form method="POST" action="/admin/bulk_delete_leads" onsubmit="return confirm('निवडलेले सर्व लीड्स डिलीट करायचे का?');">
        <div style="margin-bottom:10px;">
            <button type="submit" class="btn" style="background:#dc2626; padding:6px 12px; font-size:12px;">🗑️ निवडलेले लीड्स डिलीट करा</button>
        </div>
        <table>
            <tr><th style="width:30px;"><input type="checkbox" onclick="toggleSelectAll(this, 'lead-cb')"></th><th>दिनांक</th><th>नाव</th><th>जिल्हा</th><th>प्रवर्ग</th><th>WhatsApp</th><th>टेस्ट</th><th>गुण</th><th>कृती</th></tr>
            {% for l in leads %}
            <tr>
                <td><input type="checkbox" name="lead_ids" value="{{ l.id }}" class="lead-cb"></td>
                <td>{{ l.test_date }}</td>
                <td><b>{{ l.student_name }}</b></td>
                <td>{{ l.district }}</td>
                <td><span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold;">{{ l.caste_category or 'OPEN' }}</span></td>
                <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
                <td>{{ l.test_name }}</td>
                <td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
                <td><a href="/admin/delete_lead/{{ l.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('डिलीट करायची का?');">🗑️</a></td>
            </tr>
            {% endfor %}
        </table>
    </form>

    <!-- 2. PAYMENTS TAB -->
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
    <div class="sub-nav-tabs">
        <a href="/admin/dashboard?tab=questions&q_subtab=manual{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if q_subtab == 'manual' else '' }}">✍️ प्रश्न व्यवस्थापन मॅन्युअल नोंद</a>
        <a href="/admin/dashboard?tab=questions&q_subtab=ai{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if q_subtab == 'ai' else '' }}">🤖 डिजिटल स्मार्ट प्रश्न जनरेटर</a>
        <a href="/admin/dashboard?tab=questions&q_subtab=ocr{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if q_subtab == 'ocr' else '' }}">📸 हार्डकॉपी व्हिजन स्कॅनर</a>
        <a href="/admin/dashboard?tab=questions&q_subtab=csv{% if filter_test_id %}&filter_test_id={{ filter_test_id }}{% endif %}" class="{{ 'active' if q_subtab == 'csv' else '' }}">📥 १०० प्रश्नांची CSV फाईल अपलोड</a>
    </div>

    {% if q_subtab == 'manual' %}
    <div style="background:#ffffff; border:2px solid #059669; padding:20px; border-radius:8px; margin-bottom:25px; box-shadow:0 2px 10px rgba(0,0,0,0.05);">
        <h4 style="margin:0 0 12px; color:#065f46; font-size:16px;">✍️ मॅन्युअल प्रश्न, पर्याय, अचूक उत्तर व स्पष्टीकरण जोडा</h4>
        <form method="POST" action="/admin/add_manual_question">
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
        <p style="font-size:13px; color:#047857; margin-bottom:12px;">पुस्तकाचा किंवा जुन्या प्रश्नपत्रिकेचा स्पष्ट फोटो अपलोड करा; संगणक आपोआप सर्व MCQs वाचून या टेस्टमध्ये सेव्ह करेल:</p>
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
            <h4 style="margin:0; color:#0f172a;">
                📋 या टेस्टचे प्रश्न ({{ selected_test_title }}):
            </h4>
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

    <!-- 5. TEST MANAGEMENT TAB -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 टेस्ट व्यवस्थापन व शेड्युलिंग</h3>
    <div class="sub-nav-tabs">
        <a href="/admin/dashboard?tab=launch&cat_tab=all" class="{{ 'active' if cat_tab == 'all' else '' }}">🌐 सर्व टेस्ट्स</a>
        <a href="/admin/dashboard?tab=launch&cat_tab=rapid" class="{{ 'active' if cat_tab == 'rapid' else '' }}">⚡ रॅपिड फायर संच</a>
        <div class="sub-nav-tabs">
    <a href="/admin/dashboard?tab=launch&cat_tab=all" class="{{ 'active' if cat_tab == 'all' else '' }}">🌐 सर्व टेस्ट्स</a>
    <a href="/admin/dashboard?tab=launch&cat_tab=free" class="{{ 'active' if cat_tab == 'free' else '' }}">🟢 मोफत टेस्ट्स</a>
    <a href="/admin/dashboard?tab=launch&cat_tab=rapid" class="{{ 'active' if cat_tab == 'rapid' else '' }}">⚡ रॅपिड फायर संच</a>
    <a href="/admin/dashboard?tab=launch&cat_tab=paid" class="{{ 'active' if cat_tab == 'paid' else '' }}">🎯 अतिसंभाव्य १०० गुण संच</a>
    <a href="/admin/dashboard?tab=launch&cat_tab=live" class="{{ 'active' if cat_tab == 'live' else '' }}">🔴 मिशन खाकी महासंग्राम</a>
</div>
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
                <select name="category" required>
    <option value="free" {% if cat_tab=='free' %}selected{% endif %}>🟢 मोफत टेस्ट्स</option>
    <option value="paid" {% if cat_tab=='paid' %}selected{% endif %}>🎯 अतिसंभाव्य संच (₹९९)</option>
    <option value="live" {% if cat_tab=='live' %}selected{% endif %}>🔴 मिशन खाकी महासंग्राम</option>
    <option value="rapid" {% if cat_tab=='rapid' %}selected{% endif %}>⚡ २० गुण रॅपिड फायर</option>
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

    <!-- 8. RECRUITMENT PDF TAB -->
    {% elif active_tab == 'notices' %}
    <h3>📢 भरती PDF व्यवस्थापन</h3>
    <form method="POST" action="/admin/update_pdf_docs" enctype="multipart/form-data">
        <label>भरती अधिकृत माहिती PDF:</label><input type="file" name="recruitment_pdf_file" accept=".pdf">
        <label>भरती पात्रता PDF:</label><input type="file" name="eligibility_pdf_file" accept=".pdf">
        <button type="submit" class="btn">सेव्ह करा</button>
    </form>

    <!-- 9. TRASH TAB -->
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

    <!-- 10. SETTINGS TAB (नवीन टॅब निर्मितीसह) -->
    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन पासवर्ड, हेल्प डेस्क, मेंटेनन्स व सानुकूल (Custom) टॅब्स</h3>
    
    <!-- नवीन टॅब जोडण्याचा फॉर्म -->
    <div style="background:#ecfdf5; border:2px solid #10b981; padding:18px; border-radius:8px; margin-bottom:20px;">
        <h4 style="margin:0 0 10px; color:#065f46;">➕ स्वतःचा नवीन टॅब तयार करा (Add Custom Tab):</h4>
        <form method="POST" action="/admin/add_custom_tab" style="display:grid; grid-template-columns: 1fr 1fr auto; gap:10px; align-items:end;">
            <div>
                <label style="font-weight:bold; font-size:12px;">टॅबचे नाव (उदा. 🎖️ विशेष महासराव):</label>
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

        <label>नवा पासवर्ड:</label>
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
                    is_deleted INTEGER DEFAULT 0
                )''')

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

                cur.execute('''CREATE TABLE IF NOT EXISTS academy_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )''')

                # सानुकूल (Custom) टॅब्स टेबल
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
                    ('help_address', 'श्रीगुरु करिअर अकॅडमी, कोल्हापूर - कळे मेन रोड, आडूर, करवीर, कोल्हापूर'),
                    ('insta_link', 'https://instagram.com'),
                    ('yt_link', 'https://youtube.com'),
                    ('toppers_link', '/'),
                    ('wa_groups_multiline', 'https://chat.whatsapp.com/sampleGroup1'),
                    ('home_tab_order', 'all,live,paid,free,rapid,battle,docs,help'),
                    ('admin_tab_order', 'leads,payments,special,questions,launch,leaderboard,feedback,notices,trash,settings'),
                    ('recruitment_pdf', ''),
                    ('eligibility_pdf', ''),
                    ('razorpay_key_id', 'rzp_test_TmenVmrQI8nTRA'),
                    ('razorpay_key_secret', 'FfaDgcHGbqNKGd15kiI2TP7v')
                ]
                for k, v in defaults:
                    cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO NOTHING", (k, v))

                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_test_score ON mock_test_leads(test_id, score);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON mock_test_leads(phone);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_cat_score ON mock_test_leads(test_id, caste_category, score);")

                cur.execute('SELECT COUNT(*) as count FROM test_papers WHERE is_deleted=0')
                if cur.fetchone()['count'] == 0:
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active', 'free', 1)")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status, category, sequence_order) VALUES (2, '🔴 मिशन खाकी रविवार थेट महासंग्राम #१', 'Free', 0, 60, 'Active', 'live', 1)")

                conn.commit()

                if 'init_ai_generation_tables' in globals() and init_ai_generation_tables:
                    try:
                        init_ai_generation_tables(conn)
                    except Exception as e_ai:
                        print(f"AI Table Notice: {e_ai}")

    except Exception as e:
        print(f"Init DB Error: {e}")

init_master_db()

# UptimeRobot २४/७ पिंग मार्ग
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
    active_students_count = 45

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
        'all': '🌐 सर्व संच',
        'live': '🔴 मिशन खाकी महासंग्राम',
        'paid': '🎯 अतिसंभाव्य १०० गुण संच (₹९९)',
        'free': '🟢 मोफत टेस्ट्स',
        'rapid': '⚡ २० गुण रॅपिड फायर',
        'battle': '⚔️ जिल्हा मुकाबला व रँक',
        'docs': '📄 भरती PDF व PYQ',
        'help': '📞 हेल्प डेस्क'
    }

    home_tab_order = settings.get('home_tab_order', 'all,live,paid,free,rapid,battle,docs,help')
    raw_keys = [t.strip() for t in home_tab_order.split(',') if t.strip()]

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
        help_address=settings.get('help_address', 'श्रीगुरु करिअर अकॅडमी, आडूर'),
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
                if pass_row and pass_row['unlocked_paid_count'] >= 2 and test_id in [3, 4]:
                    return redirect(f"/take_test/{test_id}")
    return "<h3 style='color:red; text-align:center; padding:30px;'>⚠️ तुमच्या ३ मित्रांनी अजून टेस्ट सबमिट केलेली नाही!</h3>", 403

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    token = request.args.get('token', '')

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT setting_key, setting_value FROM academy_settings")
            st = {r['setting_key']: r['setting_value'] for r in cur.fetchall()}

    if not test or test['status'] != 'Active': return "Test not found or closed", 404

    if test.get('category') == 'rapid' and test.get('publish_at') and test['publish_at'] > datetime.now():
        return "<h3 style='color:#ef4444; text-align:center; padding:40px;'>⏳ ही टेस्ट दररोज सकाळी १०:०० वाजता अनलॉक होईल!</h3>", 403

    if test['test_type'] == 'Free':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

    user_phone = session.get('user_phone', '')
    is_share_unlocked = False
    if user_phone and test_id in [3, 4]:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT unlocked_paid_count FROM shared_free_passes WHERE phone=%s", (user_phone,))
                pass_row = cur.fetchone()
                if pass_row and pass_row['unlocked_paid_count'] >= 2:
                    is_share_unlocked = True

    if is_share_unlocked:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

    if token:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM mock_test_leads WHERE test_id=%s AND access_token=%s AND payment_status='Approved' AND is_deleted=0", (test_id, token))
                lead = cur.fetchone()
        if lead and lead['token_expires_at']:
            expires_at = datetime.strptime(lead['token_expires_at'], "%Y-%m-%d %H:%M:%S")
            if datetime.now() <= expires_at and lead.get('is_used', 0) == 0:
                with get_db() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
                        questions = cur.fetchall()
                return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

    return render_template_string(ACCESS_CHECK_TEMPLATE, test=test, qr_url=st.get('qr_code_url', ''), upi_mobile=st.get('upi_mobile', '9921111960'))

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
                fee = t_row['test_fee'] if t_row else 99.0

        amount_paise = int(fee * 100) if fee > 0 else 9900
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
    expires = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

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
    phone = request.form.get('phone', '').strip()
    t_date = date.today().strftime("%Y-%m-%d")

    if not re.match(r'^[6-9]\d{9}$', phone):
        return "<h3 style='color:red; text-align:center;'>⚠️ चुकीचा मोबाईल नंबर!</h3>", 400

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

    return "<h3 style='color:green; text-align:center; padding:40px;'>✅ मॅन्युअल पडताळणी प्रलंबित! २४ तासांत लिंक WhatsApp वर मिळेल.</h3>"

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    try:
        student_name = request.form.get('student_name', '').strip()
        district = request.form.get('district', '').strip()
        caste_category = request.form.get('caste_category', 'OPEN').strip().upper()
        phone = request.form.get('phone', '').strip()
        referred_by = session.get('referred_by', '')

        if not re.match(r'^[6-9]\d{9}$', phone):
            return "<h3 style='color:red; text-align:center; padding:30px;'>⚠️ अवैध मोबाईल नंबर! कृपया १० अंकी नंबर टाका.</h3>", 400

        session['user_phone'] = phone

        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
                test = cur.fetchone()
                if not test: return "Test not found", 404

                cur.execute("SELECT id, correct FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
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
                result_token = secrets.token_hex(10)

                cur.execute("""
                    INSERT INTO mock_test_leads (test_id, test_date, student_name, district, caste_category, phone, whatsapp_verified, payment_status, score, total_marks, test_name, answers_json, access_token, referred_by_phone, is_used)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, 'Approved', %s, %s, %s, %s, %s, %s, 1) RETURNING id
                """, (test_id, t_date, student_name, district, caste_category, phone, score, total, test['test_title'], ans_json_str, result_token, referred_by))

                completed_friends_count = 0
                if referred_by and test.get('category') == 'free':
                    cur.execute("""
                        SELECT COUNT(DISTINCT phone) as valid_friends 
                        FROM mock_test_leads
                        WHERE referred_by_phone=%s AND test_id=%s AND is_deleted=0
                    """, (referred_by, test_id))
                    f_res = cur.fetchone()
                    if f_res and f_res['valid_friends'] >= 3:
                        c_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                        cur.execute("""
                            INSERT INTO shared_free_passes (phone, unlocked_paid_count, created_at)
                            VALUES (%s, 2, %s)
                            ON CONFLICT (phone) DO UPDATE SET unlocked_paid_count=2
                        """, (referred_by, c_time))

                cur.execute("""
                    SELECT COUNT(DISTINCT phone) as my_friends
                    FROM mock_test_leads
                    WHERE referred_by_phone=%s AND test_id=%s AND is_deleted=0
                """, (phone, test_id))
                f_row = cur.fetchone()
                if f_row:
                    completed_friends_count = f_row['my_friends']

                cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s AND is_deleted=0", (test_id, score))
                rank_res = cur.fetchone()
                state_rank = (rank_res['higher'] + 1) if rank_res else 1

                cur.execute("SELECT COUNT(*) as higher_dist FROM mock_test_leads WHERE test_id=%s AND district ILIKE %s AND score > %s AND is_deleted=0", (test_id, district, score))
                dist_res = cur.fetchone()
                district_rank = (dist_res['higher_dist'] + 1) if dist_res else 1

                cur.execute("SELECT COUNT(*) as higher_cat FROM mock_test_leads WHERE test_id=%s AND caste_category = %s AND score > %s AND is_deleted=0", (test_id, caste_category, score))
                cat_res = cur.fetchone()
                category_rank = (cat_res['higher_cat'] + 1) if cat_res else 1

                cur.execute("SELECT setting_key, setting_value FROM academy_settings WHERE setting_key IN ('insta_link', 'yt_link', 'toppers_link', 'wa_groups_multiline')")
                settings_dict = {r['setting_key']: r['setting_value'] for r in cur.fetchall()}

                insta_link = settings_dict.get('insta_link', 'https://instagram.com')
                yt_link = settings_dict.get('yt_link', 'https://youtube.com')
                toppers_link = settings_dict.get('toppers_link', '/')
                wa_groups_str = settings_dict.get('wa_groups_multiline', '')

                group_list = [g.strip() for g in wa_groups_str.split('\n') if g.strip()]
                cur.execute("SELECT COUNT(*) as cnt FROM mock_test_leads WHERE is_deleted=0")
                cnt_row = cur.fetchone()
                total_students_count = cnt_row['cnt'] if cnt_row else 0

                group_index = min(total_students_count // 1000, max(0, len(group_list) - 1)) if group_list else 0
                wa_active_link = group_list[group_index] if group_list else ''

                conn.commit()

        main_portal_url = request.host_url.rstrip('/')
        result_url = main_portal_url + url_for('detailed_answers', token=result_token)
        
        ego_msg = f"महाराष्ट्र पोलीस भरती महासराव टेस्टमध्ये मला {score}/{total} गुण व {caste_category} रँक #{category_rank} मिळाला! तुझ्यामध्ये दम असेल तर हा रेकॉर्ड मोडून दाखव: {main_portal_url}"
        ego_share_encoded = urllib.parse.quote(ego_msg)

        return render_template_string(
            RESULT_SUMMARY_TEMPLATE,
            lead={'student_name': student_name, 'district': district, 'caste_category': caste_category, 'phone': phone, 'test_name': test['test_title'], 'score': score, 'total_marks': total, 'access_token': result_token},
            state_rank=state_rank,
            district_rank=district_rank,
            category_rank=category_rank,
            result_url=result_url,
            main_portal_url=main_portal_url,
            ego_share_encoded=ego_share_encoded,
            test_category=test.get('category', 'free'),
            insta_link=insta_link,
            yt_link=yt_link,
            toppers_link=toppers_link,
            wa_active_link=wa_active_link,
            completed_friends_count=completed_friends_count
        )

    except Exception as e:
        print(f"❌ Submit Test Error: {e}")
        return f"<h3 style='color:red; text-align:center; padding:30px;'>सर्व्हर त्रुटी: {str(e)}<br><br><a href='/'>मुख्य पानावर परत जा</a></h3>", 500

@app.route('/detailed_answers/<token>')
def detailed_answers(token):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE access_token=%s AND is_deleted=0", (token,))
            lead = cur.fetchone()
            if not lead: return "Result not found", 404

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
                cur.execute("SELECT student_name, phone, access_token FROM mock_test_leads WHERE id=%s AND is_deleted=0", (lead_id,))
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

@app.route('/admin/export_leads_csv')
def admin_export_leads_csv():
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT test_date, student_name, district, caste_category, phone, test_name, score, total_marks FROM mock_test_leads WHERE is_deleted=0 ORDER BY id DESC")
            leads = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Name', 'District', 'Category', 'WhatsApp', 'Test Name', 'Score', 'Total'])
    for l in leads:
        writer.writerow([l['test_date'], l['student_name'], l['district'], l.get('caste_category', 'OPEN'), l['phone'], l['test_name'], l['score'], l['total_marks']])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=police_test_leads_2026.csv"}
    )

# नवीन सानुकूल टॅब जोडणे (Custom Tab Route)
@app.route('/admin/add_custom_tab', methods=['POST'])
def admin_add_custom_tab():
    if not session.get('admin_logged'): return redirect('/admin/login')
    key = re.sub(r'[^a-zA-Z0-9_]', '', request.form.get('tab_key', '').strip().lower())
    label = request.form.get('tab_label', '').strip()
    if key and label:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO custom_tabs (tab_key, tab_label) VALUES (%s, %s) ON CONFLICT (tab_key) DO UPDATE SET tab_label = EXCLUDED.tab_label", (key, label))
                cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='home_tab_order'")
                row = cur.fetchone()
                current_order = row['setting_value'] if row else 'all,live,paid,free,rapid,battle,docs,help'
                if key not in current_order.split(','):
                    new_order = f"{current_order},{key}"
                    cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='home_tab_order'", (new_order,))
                conn.commit()
    return redirect('/admin/dashboard?tab=settings')

@app.route('/admin/clone_test/<int:test_id>')
def admin_clone_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
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
                        INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (new_t_id, q['question'], q['opt_a'], q['opt_b'], q['opt_c'], q['opt_d'], q['correct'], q['explanation']))
                conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/ai_scan_hardcopy', methods=['POST'])
def admin_ai_scan_hardcopy():
    if not session.get('admin_logged'): return redirect('/admin/login')
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
    if not session.get('admin_logged'): return redirect('/admin/login')

    active_tab = request.args.get('tab', 'leads')
    q_subtab = request.args.get('q_subtab', 'manual')
    cat_tab = request.args.get('cat_tab', 'all')
    sort_by = request.args.get('sort_by', 'seq')
    filter_test_id = request.args.get('filter_test_id', '')
    lead_dist = request.args.get('lead_dist', '')
    lead_test_id = request.args.get('lead_test_id', '')
    utr_search = request.args.get('utr_search', '').strip()

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM mock_test_leads WHERE is_deleted=0"
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

            cur.execute("SELECT DISTINCT district FROM mock_test_leads WHERE district != '' AND is_deleted=0")
            all_districts = [r['district'] for r in cur.fetchall()]

            test_order_sql = "sequence_order ASC, id ASC"
            if sort_by == 'name':
                test_order_sql = "test_title ASC"
            elif sort_by == 'id':
                test_order_sql = "id DESC"

            test_query = f"SELECT * FROM test_papers WHERE is_deleted=0"
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

            pay_query = "SELECT * FROM mock_test_leads WHERE payment_status != 'Not Required' AND is_deleted=0"
            pay_params = []
            if utr_search:
                pay_query += " AND (utr_number ILIKE %s OR phone ILIKE %s)"
                pay_params.extend([f"%{utr_search}%", f"%{utr_search}%"])
            pay_query += " ORDER BY id DESC"
            cur.execute(pay_query, tuple(pay_params))
            payments = cur.fetchall()

            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=0 ORDER BY score DESC, id ASC LIMIT 100")
            all_leads_sorted = cur.fetchall()

            cur.execute("SELECT * FROM student_feedbacks ORDER BY id DESC")
            feedbacks = cur.fetchall()
            cur.execute("SELECT * FROM special_unlimited_attempts ORDER BY id DESC")
            unlimited_list = cur.fetchall()
            cur.execute("SELECT * FROM special_free_pass ORDER BY id DESC")
            free_pass_list = cur.fetchall()

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

    top_leads = [(idx, l) for idx, l in enumerate(all_leads_sorted, start=1)]
    admin_tab_order = settings_map.get('admin_tab_order', 'leads,payments,special,questions,launch,leaderboard,feedback,notices,trash,settings')
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
        unlimited_list=unlimited_list,
        free_pass_list=free_pass_list,
        all_districts=all_districts,
        lead_dist=lead_dist,
        lead_test_id=lead_test_id,
        filter_test_id=filter_test_id,
        selected_test_title=selected_test_title,
        qr_url=settings_map.get('qr_code_url', ''),
        upi_mobile=settings_map.get('upi_mobile', '9921111960'),
        razorpay_key_id=settings_map.get('razorpay_key_id', ''),
        razorpay_key_secret=settings_map.get('razorpay_key_secret', ''),
        help_phone=settings_map.get('help_phone', '9921111960'),
        help_address=settings_map.get('help_address', 'श्रीगुरु करिअर अकॅडमी, आडूर'),
        insta_link=settings_map.get('insta_link', 'https://instagram.com'),
        yt_link=settings_map.get('yt_link', 'https://youtube.com'),
        toppers_link=settings_map.get('toppers_link', '/'),
        wa_groups_multiline=settings_map.get('wa_groups_multiline', ''),
        home_tab_order=settings_map.get('home_tab_order', 'all,live,paid,free,rapid,battle,docs,help'),
        admin_tab_order=admin_tab_order,
        ordered_admin_tabs=ordered_admin_tabs,
        site_status=settings_map.get('site_status', 'active'),
        custom_tabs_list=custom_tabs_list,
        undo_items=undo_items,
        deleted_questions_list=deleted_questions_list
    )

@app.route('/admin/add_manual_question', methods=['POST'])
def admin_add_manual_question():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    question = request.form.get('question', '').strip()
    opt_a = request.form.get('opt_a', '').strip()
    opt_b = request.form.get('opt_b', '').strip()
    opt_c = request.form.get('opt_c', '').strip()
    opt_d = request.form.get('opt_d', '').strip()
    correct = request.form.get('correct', 'A').strip().upper()
    explanation = request.form.get('explanation', '').strip()

    if question and opt_a and opt_b and opt_c and opt_d and test_id:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation))
                conn.commit()

    return redirect(f'/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id={test_id}')

@app.route('/admin/upload_csv_questions', methods=['POST'])
def admin_upload_csv_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    file = request.files.get('csv_file')
    if not file: return "No file uploaded", 400

    try:
        content = file.stream.read().decode("utf-8-sig", errors="ignore")
    except Exception:
        content = file.stream.read().decode("latin1", errors="ignore")

    stream = io.StringIO(content, newline=None)
    csv_reader = csv.reader(stream)

    questions_to_insert = []
    for row in csv_reader:
        if not row: continue
        first_cell = row[0].strip().lower()
        if any(h in first_cell for h in ['sr', 'अनुक्रमांक', 'question', 'प्रश्न']): continue

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

        if corr not in ['A', 'B', 'C', 'D']: corr = 'A'
        if q: questions_to_insert.append((test_id, q, oa, ob, oc, od, corr, exp))

    if questions_to_insert:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.executemany("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, questions_to_insert)
                conn.commit()

    return redirect(f'/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id={test_id}')

@app.route('/admin/ai_generate_advanced', methods=['POST'])
def admin_ai_generate_advanced():
    if not session.get('admin_logged'): 
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    department = data.get('department', 'पोलीस भरती')
    subject_counts = data.get('subject_counts', {})
    test_id = data.get('test_id')

    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        return jsonify({"success": False, "error": "Render Environment मध्ये GEMINI_API_KEY उपलब्ध नाही!"}), 400

    generated_list = []
    
    # थेट REST API द्वारे प्रश्न निर्मिती (लायब्ररी क्रॅश-प्रूफ)
    for subj, num in subject_counts.items():
        count = int(num)
        if count <= 0:
            continue
        
        prompt = (
            f"महाराष्ट्र {department} परीक्षेसाठी '{subj}' या विषयावर अचूक आणि नवीन {count} बहुपर्यायी प्रश्न तयार करा. "
            f"उत्तर खालीलप्रमाणे प्रत्येक ओळीत पाईप (|) फॉरमॅटमध्ये द्या:\n"
            f"प्रश्न | पर्याय A | पर्याय B | पर्याय C | पर्याय D | अचूक उत्तर (A/B/C/D) | स्पष्टीकरण"
        )
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            import requests
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
            if res.status_code == 200:
                data_resp = res.json()
                raw_text = data_resp.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                lines = raw_text.strip().split('\n')
                for line in lines:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 6:
                        q = parts[0]
                        oa, ob, oc, od = parts[1], parts[2], parts[3], parts[4]
                        corr = parts[5].upper()
                        if corr not in ['A', 'B', 'C', 'D']:
                            corr = 'A'
                        exp = parts[6] if len(parts) > 6 else 'स्पष्टीकरण उपलब्ध नाही.'
                        generated_list.append((test_id, q, oa, ob, oc, od, corr, exp))
        except Exception as err:
            print(f"Fetch Error: {err}")

    if generated_list:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.executemany("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, generated_list)
                conn.commit()
        return jsonify({"success": True, "inserted_count": len(generated_list)})

    return jsonify({"success": False, "error": "प्रश्न तयार करता आले नाहीत. कृपया API Key आणि इंटरनेट तपासा."}), 500

@app.route('/admin/undo_delete/<item_type>/<int:item_id>')
def admin_undo_delete(item_type, item_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
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
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            if item_type == 'question':
                cur.execute("UPDATE questions SET is_deleted=0 WHERE id=%s", (item_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=trash')

@app.route('/admin/bulk_restore_trash', methods=['POST'])
def admin_bulk_restore_trash():
    if not session.get('admin_logged'): return redirect('/admin/login')
    ids = request.form.getlist('question_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("UPDATE questions SET is_deleted=0 WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect('/admin/dashboard?tab=trash')

@app.route('/admin/bulk_delete_feedback', methods=['POST'])
def admin_bulk_delete_feedback():
    if not session.get('admin_logged'): return redirect('/admin/login')
    selected_ids = request.form.getlist('feedback_ids')
    if selected_ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in selected_ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("DELETE FROM student_feedbacks WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect('/admin/dashboard?tab=feedback')

@app.route('/admin/bulk_delete_trash', methods=['POST'])
def admin_bulk_delete_trash():
    if not session.get('admin_logged'): return redirect('/admin/login')
    ids = request.form.getlist('question_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("DELETE FROM questions WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect('/admin/dashboard?tab=trash')

@app.route('/admin/update_razorpay_settings', methods=['POST'])
def admin_update_razorpay_settings():
    if not session.get('admin_logged'): return redirect('/admin/login')
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
        with conn.cursor() as cur:
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='qr_code_url'", (final_qr_url,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='upi_mobile'", (new_mobile,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/bulk_delete_leads', methods=['POST'])
def admin_bulk_delete_leads():
    if not session.get('admin_logged'): return redirect('/admin/login')
    ids = request.form.getlist('lead_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                int_ids = [int(i) for i in ids if str(i).isdigit()]
                if int_ids:
                    cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id = ANY(%s)", (int_ids,))
                    conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/bulk_delete_questions', methods=['POST'])
def admin_bulk_delete_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
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

@app.route('/admin/delete_question/<int:q_id>')
def admin_delete_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT test_id FROM questions WHERE id=%s", (q_id,))
            q_row = cur.fetchone()
            t_id = q_row['test_id'] if q_row else ''
            cur.execute("UPDATE questions SET is_deleted=1 WHERE id=%s", (q_id,))
            conn.commit()
    return redirect(f'/admin/dashboard?tab=questions&q_subtab=manual&filter_test_id={t_id}')

@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE test_papers SET is_deleted=1 WHERE id=%s", (test_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    if not session.get('admin_logged'): return redirect('/admin/login')
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
    if not session.get('admin_logged'): return redirect('/admin/login')
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
        with conn.cursor() as cur:
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
        with conn.cursor() as cur:
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
    site_status = request.form.get('site_status', 'active')
    home_tab_order = request.form.get('home_tab_order', 'all,live,paid,free,rapid,battle,docs,help').strip()
    admin_tab_order = request.form.get('admin_tab_order', 'leads,payments,special,questions,launch,leaderboard,feedback,notices,trash,settings').strip()
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

@app.route('/admin/delete_lead/<int:lead_id>')
def admin_delete_lead(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/delete_payment/<int:lead_id>')
def admin_delete_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

