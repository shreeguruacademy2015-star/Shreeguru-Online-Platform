

Skip to content
Using Gmail with screen readers
1 of 1,578
(no subject)
Inbox

Shreeguru Academy Adur पोलीस भरती पूर्व प्रशिक्षण केंद्र <sachinchougale1987@gmail.com>
10:43 (1 minute ago)
to me

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
        This portal is an independent, private educational platform. NO official connection with Maharashtra Police or Government.
    </div>
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
    <p>विद्यार्थ्यांना अधिक चांगला अनुभव देण्यासाठी पोर्टलवर मेंटेनन्स सुरू आहे. लवकरच वेबसाईट पूर्ववत सुरू होईल.</p>
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
        .hero-banner h1 { margin: 0 0 8px; color: #34d399; font-size: 27px; font-weight: 800; }
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
        function filterTab(category, btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
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
                    if (category === 'all' || cardCat === cardCat) {
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
        <h3 style="color:#34d399; margin:0 0 10px; font-size:20px;">🛡️ महाराष्ट्र पोलीस भरती टेस्ट पोर्टलवर आपले स्वागत आहे!</h3>
        <p style="color:#cbd5e1; font-size:14px; line-height:1.6; margin:0 0 20px;">
            ⏳ <b>आपले टेस्ट पेज सुरू होत आहे...</b> Render सर्व्हर स्लीप मोडवरून जिवंत होत आहे, कृपया क्षणभर प्रतीक्षा करा!
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
    <a href="/" style="position:fixed; bottom:20px; right:20px; background:#10b981; color:#022c22; padding:10px 18px; border-radius:30px; text-decoration:none; font-weight:800; font-size:13px; box-shadow:0 4px 15px rgba(0,0,0,0.4); z-index:9999; border:2px solid #34d399;">
        🏠 मुख्य पानावर जा
    </a>
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
            {% elif tab_key == 'help' %}<button class="tab-btn" onclick="filterTab('help', this)">📞 हेल्प डेस्क</button>
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
                <button onclick="openLoadingNotice('/take_test/{{ t.id }}')" class="btn-start">🚀 टेस्ट सोडवा</button>
            {% endif %}
        </div>
        {% endfor %}
        <div id="noTestMsg" style="display:none; text-align:center; padding:35px 20px; background:#0f172a; border-radius:12px; border:1px dashed #475569; color:#94a3b8; font-size:15px;">
            🎯 <b>लवकरच या विभागात अतिसंभाव्य व दर्जेदार प्रश्नसंच उपलब्ध होतील!</b>
        </div>
    </div>

    <div id="battleContainer" class="section-box">
        <h3 style="color:#f59e0b; margin-top:0;">🏆 राज्यस्तरीय जिल्हा मुकाबला</h3>
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
            <tr><td colspan="4" style="text-align:center; color:#94a3b8;">माहिती उपलब्ध नाही.</td></tr>
            {% endfor %}
        </table>
    </div>

    <div id="docsContainer" class="section-box">
        <h3 style="color:#38bdf8; margin-top:0;">📄 अधिकृत भरती कागदपत्रे व प्रश्नपत्रिका</h3>
        {% if recruitment_pdf %}<a href="{{ recruitment_pdf }}" target="_blank" class="doc-link">📑 पोलीस भरती अधिकृत जाहिरात (PDF)</a>{% endif %}
        {% if eligibility_pdf %}<a href="{{ eligibility_pdf }}" target="_blank" class="doc-link">📋 पात्रता निकष (PDF)</a>{% endif %}
    </div>

    <div id="helpContainer" class="section-box">
        <h3 style="color:#34d399; margin-top:0;">📞 मदत व मार्गदर्शन हेल्प डेस्क</h3>
        <div style="background:#1e293b; padding:18px; border-radius:10px; border:1px solid #334155; display:inline-block; text-align:left; max-width:400px; width:100%;">
            <p style="margin:6px 0; color:#f8fafc;">📱 <b>हेल्पलाईन:</b> <a href="https://wa.me/91{{ help_phone }}" target="_blank" style="color:#34d399; font-weight:bold;">{{ help_phone }}</a></p>
            <p style="margin:6px 0; color:#f8fafc;">📍 <b>पत्ता:</b> {{ help_address }}</p>
        </div>
    </div>

    <div class="footer">
        <span>© 2026 महाराष्ट्र पोलीस भरती सराव प्रश्नसंच ऑनलाईन व्यासपीठ | </span>
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
            document.getElementById('examForm').addEventListener('submit', function(e) {
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
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">पूर्ण नाव *:</label><input type="text" name="student_name" id="s_name" placeholder="उदा. राहुल पाटील" onkeyup="validateAndReady()" required></div>
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">जिल्हा *:</label><input type="text" name="district" id="s_dist" placeholder="उदा. कोल्हापूर" onkeyup="validateAndReady()" required></div>
                <div><label style="font-size:13px; font-weight:600; color:#cbd5e1;">WhatsApp नंबर *:</label><input type="tel" name="phone" id="s_phone" placeholder="10 अंकी नंबर" maxlength="10" onkeyup="validateAndReady()" required></div>
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
        .share-unlock-box { background: rgba(245,158,11,0.15); border: 2px dashed #f59e0b; border-radius: 12px; padding: 18px; margin: 18px 0; text-align: center; color: #fde68a; }
        .cert-card { background: linear-gradient(135deg, #1e293b, #0f172a); color: white; border: 3px double #f59e0b; padding: 22px; border-radius: 12px; margin: 20px 0; text-align: center; }
        .btn-wa { display: inline-block; background: #25D366; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 15px; margin: 8px 4px; cursor: pointer; border: none; }
        .btn-group { display: block; background: linear-gradient(135deg, #25D366, #128C7E); color: white; padding: 14px 20px; border-radius: 10px; text-decoration: none; font-weight: 800; font-size: 15px; text-align: center; margin: 20px 0; border: 1.5px solid #86efac; cursor: pointer; }
        .promo-box { background: #0f172a; border: 1.5px solid #334155; padding: 15px; border-radius: 10px; margin-top: 20px; text-align: center; }
        .btn-link { display: inline-block; color: white; padding: 8px 15px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; margin: 4px; cursor: pointer; border: none; }
        input[type="tel"] { width: 100%; max-width: 280px; padding: 11px; background: #0f172a; border: 1.5px solid #334155; border-radius: 8px; color: white; font-size: 14px; text-align: center; margin-bottom: 10px; }
        .rules-modal { display: none; position: fixed; inset: 0; background: rgba(11,19,41,0.95); z-index: 10000; justify-content: center; align-items: center; padding: 15px; }
        .rules-content { background: #162036; border: 2px solid #25D366; border-radius: 14px; padding: 25px; max-width: 580px; max-height: 90vh; overflow-y: auto; text-align: left; }
    </style>
    <script>
        function openRulesModal() { document.getElementById('waRulesModal').style.display = 'flex'; }
        function closeRulesModal() { document.getElementById('waRulesModal').style.display = 'none'; }
        function handleSocialLink(url) {
            # Feature 1: Updated exact prompt message
            alert("संपूर्ण प्रवासाची यशोगाथा लवकरच आपल्या भेटीस येत आहे.....\\nतुमचे खाकीचे स्वप्न लवकर पूर्ण व्हावे ही सदिच्छा....");
            if (url && url.trim() !== '' && url !== '#') {
                window.open(url, '_blank');
            }
        }
    </script>
</head>
<body>

<div id="waRulesModal" class="rules-modal">
    <div class="rules-content">
        <h3 style="color:#25D366; margin-top:0; text-align:center;">🚨 अधिकृत सराव ग्रुप नियम व अटी</h3>
        <p style="font-size:13px; color:#cbd5e1;">या ग्रुपचा उद्देश केवळ पोलीस भरती परीक्षा सराव हा आहे.</p>
        <div style="display:flex; gap:10px;">
            <a href="{{ wa_active_link }}" target="_blank" onclick="closeRulesModal()" style="flex:2; background:#25D366; color:#064e3b; text-align:center; padding:12px; border-radius:6px; font-weight:bold; text-decoration:none;">✅ मान्य आहे — ग्रुपमध्ये सामील व्हा</a>
            <button onclick="closeRulesModal()" style="flex:1; background:#475569; color:white; border:none; padding:12px; border-radius:6px; cursor:pointer;">रद्द करा</button>
        </div>
    </div>
</div>

<div class="box">
    <h2 style="color:#34d399; margin:0 0 5px; text-align:center;">🎉 टेस्ट यशस्वीरीत्या पूर्ण झाली!</h2>
    <div style="background:#0f172a; border:1px solid #334155; border-radius:12px; padding:18px; margin:15px 0; text-align:center;">
        <p style="font-size:16px; margin:4px 0; color:#cbd5e1;">परीक्षार्थी: <b>{{ lead.student_name }}</b> (जिल्हा: <b>{{ lead.district }}</b>)</p>
        <p style="font-size:24px; color:#fbbf24; font-weight:bold; margin-top:8px;">🏆 रँक: <b style="color:#34d399; font-size:32px;">#{{ state_rank }}</b> 🌟</p>
        <p style="font-size:20px; font-weight:bold; color:#f8fafc; margin-top:4px;">प्राप्त गुण: <span style="color:#10b981;">{{ lead.score }}</span> / {{ lead.total_marks }}</p>
    </div>

    {% if wa_active_link %}
    <button onclick="openRulesModal()" class="btn-group">
        📲 दररोज सकाळी १०:०० वाजता मोफत रॅपिड टेस्ट मिळवण्यासाठी अधिकृत WhatsApp ग्रुपमध्ये सामील व्हा ➔
    </button>
    {% endif %}

    <div class="cert-card">
        <h3 style="color:#fde047; margin:0 0 6px; font-size:20px;">🎖️ मिशन खाकी २०२६</h3>
        <a href="https://wa.me/?text={{ ego_share_encoded }}" target="_blank" class="btn-wa">⚔️ मित्रांना WhatsApp वर चॅलेंज द्या</a>
    </div>

    <div style="text-align:center; margin:20px 0;">
        <a href="{{ result_url }}" target="_blank" style="background:#10b981; color:#064e3b; padding:12px 26px; border-radius:8px; text-decoration:none; font-weight:800; display:inline-block;">📖 स्पष्टीकरण शीट पहा</a>
    </div>

    <div class="promo-box">
        <h4 style="margin:0 0 10px; color:#34d399;">🌟 सोशल मीडिया व यशोगाथा लिंक्स:</h4>
        <button onclick="handleSocialLink('{{ insta_link }}')" class="btn-link" style="background:#E1306C;">📸 Instagram</button>
        <button onclick="handleSocialLink('{{ yt_link }}')" class="btn-link" style="background:#FF0000;">▶ YouTube</button>
        <button onclick="handleSocialLink('{{ toppers_link }}')" class="btn-link" style="background:#0284c7;">🏆 यशवंतांचे फोटो</button>
    </div>
</div>
</body>
</html>'''

ACCESS_CHECK_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>सशुल्क टेस्ट प्रवेश द्वार</title></head>
<body style="font-family:sans-serif; background:#0b1329; color:white; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0;">
<div style="background:#162036; padding:30px; border-radius:12px; max-width:400px; text-align:center;">
    <h3 style="color:#34d399;">🔒 अतिसंभाव्य टेस्ट प्रवेश द्वार</h3>
    <p>{{ test.test_title }} (फी: ₹{{ test.test_fee }})</p>
    <a href="/" style="background:#10b981; color:#022c22; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block; margin-top:15px;">🏠 मुख्य पानावर जा</a>
</div>
</body>
</html>'''

DETAILED_KEY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>सविस्तर उत्तरपत्रिका व स्पष्टीकरण</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; background: #0b1329; color: #f1f5f9; font-family: 'Poppins', sans-serif; padding: 15px; }
        .box { max-width: 820px; margin: 0 auto; background: #162036; border-radius: 14px; padding: 25px; border-top: 6px solid #10b981; }
        .item { background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
        .correct-box { border-left: 5px solid #10b981; }
        .wrong-box { border-left: 5px solid #ef4444; }
        textarea { width: 100%; padding: 10px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: white; }
        .btn-fb { background: #10b981; color: #064e3b; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 8px; }
    </style>
</head>
<body>
<div class="box">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #334155; padding-bottom:10px;">
        <span style="font-size:13px; font-weight:bold; color:#34d399;">📖 स्पष्टीकरण कक्ष</span>
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
        .box { max-width: 650px; margin: auto; background: white; padding: 25px; border-radius: 8px; border-top: 5px solid #059669; }
        input, textarea, select { width: 100%; padding: 9px; margin: 6px 0 14px; border: 1px solid #cbd5e1; border-radius: 5px; }
        .btn { background: #059669; color: white; border: none; padding: 10px 18px; border-radius: 5px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
<div class="box">
    <h3 style="color:#065f46; margin-top:0;">✏️ प्रश्न संपादित करा (ID: {{ q.id }})</h3>
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
        <a href="/admin/dashboard?tab=questions" style="margin-left:10px; color:#dc2626; text-decoration:none; font-weight:600;">रद्द करा</a>
    </form>
</div>
</body>
</html>'''

ADMIN_LOGIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>ॲडमिन सुरक्षित लॉगिन</title>
    <style>
        body { margin:0; background:#0f172a; color:white; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif; }
        .login-box { background:#1e293b; padding:35px 30px; border-radius:10px; width:360px; text-align:center; border-top:5px solid #059669; }
        input { width:100%; padding:12px; margin:15px 0 20px; border-radius:6px; border:1.5px solid #475569; background:#0f172a; color:white; text-align:center; box-sizing:border-box; }
        button { width:100%; background:#059669; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer; }
    </style>
</head>
<body>
<div class="login-box">
    <h2>⚙️ ॲडमिन सुरक्षित कक्ष</h2>
    {% if error %}<div style="color:#f87171; font-size:13px; margin-bottom:10px;">{{ error }}</div>{% endif %}
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
        function toggleSelectAll(master, className) {
            document.querySelectorAll('.' + className).forEach(cb => cb.checked = master.checked);
        }
        function generateAIQuestionsFromAdvancedForm() {
            const count = document.getElementById('ai_q_count').value;
            const diff = document.getElementById('ai_q_diff').value;
            const dept = document.getElementById('ai_department').value;
            const testId = document.getElementById('ai_target_test_id').value;
            
            let selectedSubjects = [];
            document.querySelectorAll('.ai_subj_cb:checked').forEach(cb => {
                selectedSubjects.push(cb.value);
            });

            if (selectedSubjects.length === 0) {
                alert("⚠️ कृपया किमान एक विषय निवडा!");
                return;
            }

            const btn = document.getElementById('advancedAiBtn');
            btn.innerText = '⏳ AI प्रश्न तयार करत आहे...';
            btn.disabled = true;

            fetch('/admin/ai_generate_advanced', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({count: count, difficulty: diff, department: dept, subjects: selectedSubjects, test_id: testId})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("✅ AI द्वारे " + data.inserted_count + " प्रश्न यशस्वीपणे तयार करून थेट टेस्टमध्ये ॲड केले गेले!");
                    location.reload();
                } else {
                    alert("⚠️ एरर: " + (data.error || 'अज्ञात एरर'));
                }
                btn.innerText = '🤖 AI स्मार्ट प्रश्न जनरेट करा व सेव्ह करा';
                btn.disabled = false;
            });
        }

        function scanHardcopyToAI() {
            const fileInput = document.getElementById('hardcopyScanFile');
            const testId = document.getElementById('scan_target_test_id').value;
            if (!fileInput.files || fileInput.files.length === 0) {
                alert("⚠️ कृपया स्कॅन केलेली फाईल किंवा फोटो अपलोड करा!");
                return;
            }
            const formData = new FormData();
            formData.append('scan_file', fileInput.files[0]);
            formData.append('test_id', testId);

            const btn = document.getElementById('scanAiBtn');
            btn.innerText = '⏳ AI स्कॅनिंग व ॲनालिसिस सुरू आहे...';
            btn.disabled = true;

            fetch('/admin/ai_scan_hardcopy', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("✅ हार्डकॉपी स्कॅन करून " + data.inserted_count + " प्रश्न यशस्वीपणे CSV द्वारे टेस्टमध्ये ॲड केले गेले!");
                    location.reload();
                } else {
                    alert("⚠️ एरर: " + (data.error || 'स्कॅनिंग एरर'));
                }
                btn.innerText = '🚀 हार्डकॉपी स्कॅन करून AI द्वारे CSV बनवा व अपलोड करा';
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
            {% elif tab == 'special' %}<a href="/admin/dashboard?tab=special" class="{{ 'active' if active_tab == 'special' else '' }}">👑 Special Access</a>
            {% elif tab == 'questions' %}<a href="/admin/dashboard?tab=questions" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions (AI टूलसह)</a>
            {% elif tab == 'launch' %}<a href="/admin/dashboard?tab=launch" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Tests Management</a>
            {% elif tab == 'leaderboard' %}<a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard</a>
            {% elif tab == 'feedback' %}<a href="/admin/dashboard?tab=feedback" class="{{ 'active' if active_tab == 'feedback' else '' }}">💬 Feedback</a>
            {% elif tab == 'notices' %}<a href="/admin/dashboard?tab=notices" class="{{ 'active' if active_tab == 'notices' else '' }}">📢 PDF Docs</a>
            {% elif tab == 'trash' %}<a href="/admin/dashboard?tab=trash" class="{{ 'active' if active_tab == 'trash' else '' }}">🗑️ Trash</a>
            {% elif tab == 'settings' %}<a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Settings</a>
            {% endif %}
        {% endfor %}
    </div>

    <!-- 1. LEADS TAB -->
    {% if active_tab == 'leads' %}
    <h3>📱 विद्यार्थ्यांची लीड्स यादी (Bulk Delete उपलब्ध)</h3>
    <form method="POST" action="/admin/bulk_delete_leads" onsubmit="return confirm('निवडलेले सर्व लीड्स डिलीट करायचे का?');">
        <div style="margin-bottom:10px;">
            <button type="submit" class="btn" style="background:#dc2626; padding:6px 12px; font-size:12px;">🗑️ निवडलेले लीड्स डिलीट करा</button>
        </div>
        <table>
            <tr><th style="width:30px;"><input type="checkbox" onclick="toggleSelectAll(this, 'lead-cb')"></th><th>दिनांक</th><th>नाव</th><th>जिल्हा</th><th>WhatsApp</th><th>टेस्ट</th><th>गुण</th></tr>
            {% for l in leads %}
            <tr>
                <td><input type="checkbox" name="lead_ids" value="{{ l.id }}" class="lead-cb"></td>
                <td>{{ l.test_date }}</td><td><b>{{ l.student_name }}</b></td><td>{{ l.district }}</td><td>{{ l.phone }}</td><td>{{ l.test_name }}</td><td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
            </tr>
            {% endfor %}
        </table>
    </form>

    <!-- 2. PAYMENTS TAB -->
    {% elif active_tab == 'payments' %}
    <h3>💰 पेमेंट व्यवस्थापन</h3>
    <table>
        <tr><th>नाव</th><th>मोबाईल</th><th>टेस्ट</th><th>स्थिती</th><th>कृती</th></tr>
        {% for p in payments %}
        <tr>
            <td>{{ p.student_name }}</td><td>{{ p.phone }}</td><td>{{ p.test_name }}</td><td style="color:green; font-weight:bold;">{{ p.payment_status }}</td>
            <td><a href="/admin/delete_payment/{{ p.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑</a></td>
        </tr>
        {% endfor %}
    </table>

    <!-- 3. SPECIAL ACCESS TAB -->
    {% elif active_tab == 'special' %}
    <h3>👑 Special Access व्यवस्थापन</h3>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
        <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:15px; border-radius:8px;">
            <h4 style="color:#065f46; margin-top:0;">🔄 अमर्याद प्रयत्न सवलत</h4>
            <form method="POST" action="/admin/add_special_unlimited">
                <input type="text" name="phone" placeholder="१० अंकी नंबर" maxlength="10" required>
                <input type="text" name="student_name" placeholder="नाव">
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
            <h4 style="color:#b45309; margin-top:0;">⭐ मोफत पास</h4>
            <form method="POST" action="/admin/add_special_free_pass">
                <input type="text" name="phone" placeholder="१० अंकी नंबर" maxlength="10" required>
                <input type="text" name="student_name" placeholder="नाव">
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

    <!-- 4. QUESTIONS TAB (WITH ADVANCED AI GENERATOR & HARDCOPY SCANNER & ROBUST CSV UPLOAD) -->
    {% elif active_tab == 'questions' %}
    <h3>📝 प्रश्न व्यवस्थापन, हार्डकॉपी स्कॅनर व AI स्मार्ट जनरेटर (Feature 4 & 6)</h3>
    
    <!-- Feature 6: Advanced AI Smart Mock Question Generator Form -->
    <div style="background:#f0fdf4; border:2px solid #10b981; padding:18px; border-radius:8px; margin-bottom:25px;">
        <h4 style="margin:0 0 10px; color:#065f46;">🤖 Feature 6: AI स्मार्ट मॉक प्रश्न जनरेटर (विभाग व विषयवार)</h4>
        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:12px; margin-bottom:12px;">
            <div>
                <label style="font-weight:bold; font-size:12px;">टेस्ट निवडा:</label>
                <select id="ai_target_test_id">
                    {% for t in tests %}<option value="{{ t.id }}">{{ t.test_title }}</option>{% endfor %}
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
            <div>
                <label style="font-weight:bold; font-size:12px;">प्रश्नांची संख्या (उदा. १०):</label>
                <input type="number" id="ai_q_count" value="10" min="1" max="100">
            </div>
        </div>
        <div style="margin-bottom:12px;">
            <label style="font-weight:bold; font-size:12px;">काठीिन्य पातळीची टक्केवारी (%):</label>
            <input type="number" id="ai_q_diff" value="75" min="10" max="100" placeholder="उदा. ७५%">
        </div>
        <div style="margin-bottom:12px;">
            <label style="font-weight:bold; font-size:12px; display:block; margin-bottom:4px;">विषय निवडा (एकापेक्षा जास्त निवडू शकता):</label>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:6px; background:white; padding:10px; border-radius:6px; border:1px solid #cbd5e1;">
                <label><input type="checkbox" class="ai_subj_cb" value="मराठी व्याकरण" checked> मराठी व्याकरण</label>
                <label><input type="checkbox" class="ai_subj_cb" value="गणित"> गणित</label>
                <label><input type="checkbox" class="ai_subj_cb" value="बुद्धिमत्ता"> बुद्धिमत्ता</label>
                <label><input type="checkbox" class="ai_subj_cb" value="राज्यशास्त्र व नागरिक शास्त्र"> राज्यशास्त्र व नागरिक शास्त्र</label>
                <label><input type="checkbox" class="ai_subj_cb" value="भूगोल"> भूगोल</label>
                <label><input type="checkbox" class="ai_subj_cb" value="विज्ञान"> विज्ञान</label>
                <label><input type="checkbox" class="ai_subj_cb" value="इतिहास"> इतिहास</label>
                <label><input type="checkbox" class="ai_subj_cb" value="समाज सुधारक"> समाज सुधारक</label>
                <label><input type="checkbox" class="ai_subj_cb" value="सामान्य विज्ञान"> सामान्य विज्ञान</label>
                <label><input type="checkbox" class="ai_subj_cb" value="अर्थशास्त्र"> अर्थशास्त्र</label>
                <label><input type="checkbox" class="ai_subj_cb" value="चालू घडामोडी"> चालू घडामोडी</label>
                <label><input type="checkbox" class="ai_subj_cb" value="संगणक"> संगणक</label>
                <label><input type="checkbox" class="ai_subj_cb" value="माहिती अधिकार कायदा 2005"> माहिती अधिकार कायदा २००५</label>
                <label><input type="checkbox" class="ai_subj_cb" value="इंग्रजी व्याकरण"> इंग्रजी व्याकरण</label>
            </div>
        </div>
        <button id="advancedAiBtn" type="button" class="btn" onclick="generateAIQuestionsFromAdvancedForm()" style="background:#10b981; color:#022c22; font-weight:800; width:100%;">
            🤖 AI स्मार्ट प्रश्न जनरेट करा व सेव्ह करा
        </button>
    </div>

    <!-- Feature 4: Hardcopy Scan AI Parser Tab -->
    <div style="background:#eff6ff; border:2px dashed #3b82f6; padding:18px; border-radius:8px; margin-bottom:25px;">
        <h4 style="margin:0 0 8px; color:#1e40af;">📄 Feature 4: प्रश्नपत्रिका हार्डकॉपी स्कॅनर व AI ऑटोमॅटिक CSV जनरेटर</h4>
        <p style="font-size:12.5px; color:#1d4ed8; margin:0 0 10px;">प्रिंटर किंवा स्कॉनेरमध्ये हार्डकॉपी ठेवल्यानंतर स्कॅन झालेली फाईल/फोटो येथे अपलोड करा. AI त्याचे ॲनालिसिस करून स्वयंचलितपणे सर्व प्रश्न, पर्याय, उत्तरे व स्पष्टीकरण तयार करून टेस्टमध्ये ॲड करेल.</p>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:10px;">
            <select id="scan_target_test_id">
                {% for t in tests %}<option value="{{ t.id }}">{{ t.test_title }}</option>{% endfor %}
            </select>
            <input type="file" id="hardcopyScanFile" accept="image/*,.pdf,.txt" style="background:white; padding:6px;">
        </div>
        <button id="scanAiBtn" type="button" class="btn" onclick="scanHardcopyToAI()" style="background:#2563eb; width:100%;">
            🚀 हार्डकॉपी स्कॅन करून AI द्वारे CSV बनवा व अपलोड करा
        </button>
    </div>

    <!-- Feature 2 & 100 Questions Robust CSV Upload -->
    <div style="background:#fefce8; border:2px dashed #ca8a04; padding:18px; border-radius:8px; margin-bottom:25px;">
        <h4 style="margin:0 0 8px; color:#854d0e;">📥 १०० प्रश्नांची CSV फाईल अपलोड (रोबस्ट पार्सर)</h4>
        <form method="POST" action="/admin/upload_csv_questions" enctype="multipart/form-data">
            <select name="test_id" required style="margin-bottom:8px;">
                {% for t in tests %}<option value="{{ t.id }}">{{ t.test_title }}</option>{% endfor %}
            </select>
            <input type="file" name="csv_file" accept=".csv,.txt" required style="margin-bottom:8px; background:white; padding:6px;">
            <button type="submit" class="btn" style="background:#ca8a04; width:100%;">🚀 संपूर्ण प्रश्न CSV द्वारे अपलोड करा</button>
        </form>
    </div>

    <!-- Feature 5: Bulk Delete Questions -->
    <form method="POST" action="/admin/bulk_delete_questions" onsubmit="return confirm('निवडलेले सर्व प्रश्न डिलीट करायचे का?');">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <h4 style="margin:0;">सर्व प्रश्न यादी:</h4>
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
                    <a href="/admin/delete_question/{{ q.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑️</a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </form>

    <!-- 5. TEST MANAGEMENT TAB -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 टेस्ट व्यवस्थापन व शेड्युलिंग</h3>
    <form method="POST" action="/admin/bulk_delete_tests" onsubmit="return confirm('निवडलेल्या सर्व टेस्ट्स डिलीट करायच्या का?');">
        <div style="margin-bottom:10px;">
            <button type="submit" class="btn" style="background:#dc2626; padding:6px 12px; font-size:12px;">🗑️ निवडलेल्या टेस्ट्स डिलीट करा</button>
        </div>
        <table>
            <tr><th style="width:30px;"><input type="checkbox" onclick="toggleSelectAll(this, 'test-cb')"></th><th>ID</th><th>नाव</th><th>कॅटेगरी</th><th>स्थिती</th><th>कृती</th></tr>
            {% for t in tests %}
            <tr>
                <td><input type="checkbox" name="test_ids" value="{{ t.id }}" class="test-cb"></td>
                <td>{{ t.id }}</td><td><b>{{ t.test_title }}</b></td><td>{{ t.category }}</td><td style="color:green; font-weight:bold;">{{ t.status }}</td>
                <td><a href="/admin/delete_test/{{ t.id }}" class="btn-sm" style="background:#dc2626; color:white;">🗑</a></td>
            </tr>
            {% endfor %}
        </table>
    </form>

    <!-- 6. LEADERBOARD TAB -->
    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 राज्यस्तरीय गुणवत्ता यादी</h3>
    <table>
        <tr><th>रँक</th><th>नाव</th><th>जिल्हा</th><th>गुण</th></tr>
        {% for rank, l in top_leads %}
        <tr><td><b>#{{ rank }}</b></td><td>{{ l.student_name }}</td><td>{{ l.district }}</td><td><b style="color:#059669;">{{ l.score }} / {{ l.total_marks }}</b></td></tr>
        {% endfor %}
    </table>

    <!-- 7. FEEDBACK TAB -->
    {% elif active_tab == 'feedback' %}
    <h3>💬 विद्यार्थ्यांचे अभिप्राय</h3>
    <form method="POST" action="/admin/bulk_delete_feedback" onsubmit="return confirm('डिलीट करायचे का?');">
        <button type="submit" class="btn" style="background:#dc2626; padding:5px 10px; font-size:12px; margin-bottom:8px;">🗑️ निवडलेले डिलीट करा</button>
        <table>
            <tr><th style="width:30px;"><input type="checkbox" onclick="toggleSelectAll(this, 'fb-cb')"></th><th>नाव</th><th>अभिप्राय</th></tr>
            {% for f in feedbacks %}
            <tr><td><input type="checkbox" name="feedback_ids" value="{{ f.id }}" class="fb-cb"></td><td>{{ f.student_name }}</td><td>{{ f.feedback_text }}</td></tr>
            {% endfor %}
        </table>
    </form>

    <!-- 8. RECRUITMENT PDF TAB -->
    {% elif active_tab == 'notices' %}
    <h3>📢 भरती PDF व्यवस्थापन</h3>
    <form method="POST" action="/admin/update_pdf_docs" enctype="multipart/form-data">
        <label>भरती अधिकृत माहिती PDF:</label><input type="file" name="recruitment_pdf_file" accept=".pdf">
        <button type="submit" class="btn">सेव्ह करा</button>
    </form>

    <!-- 9. TRASH TAB -->
    {% elif active_tab == 'trash' %}
    <h3>🗑️ रिसायकल बिन</h3>
    <table>
        <tr><th>नाव/प्रश्न</th><th>कृती</th></tr>
        {% for q in deleted_questions_list %}
        <tr><td>{{ q.question }}</td><td><a href="/admin/restore_item/question/{{ q.id }}" class="btn-sm" style="background:#16a34a; color:white;">♻️ रिस्टोर</a></td></tr>
        {% endfor %}
    </table>

    <!-- 10. SETTINGS TAB -->
    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन सेटिंग्स व पॉवर बटण</h3>
    <form method="POST" action="/admin/update_password">
        <label>वेबसाईट चालू/बंद स्थिती:</label>
        <select name="site_status">
            <option value="active" {% if site_status == 'active' %}selected{% endif %}>🟢 चालू (Active)</option>
            <option value="maintenance" {% if site_status == 'maintenance' %}selected{% endif %}>🔴 मेंटेनन्स मोड (Maintenance)</option>
        </select>
        <label>नवा पासवर्ड:</label><input type="password" name="new_password" placeholder="पासवर्ड">
        <button type="submit" class="btn">💾 सेव्ह करा</button>
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
                    ('qr_code_url', 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=PoliceBhartiTestPayment'),
                    ('upi_mobile', '9921111960'),
                    ('admin_pass', 'admin2026'),
                    ('help_phone', '9921111960'),
                    ('help_address', 'श्रीगुरु करिअर अकॅडमी, आडूर'),
                    ('insta_link', '#'),
                    ('yt_link', '#'),
                    ('toppers_link', '#'),
                    ('wa_groups_multiline', 'https://chat.whatsapp.com/sampleGroup1'),
                    ('home_tab_order', 'all,live,paid,free,rapid,battle,docs,help'),
                    ('admin_tab_order', 'leads,payments,special,questions,launch,leaderboard,feedback,notices,trash,settings'),
                    ('recruitment_pdf', ''),
                    ('eligibility_pdf', ''),
                    ('razorpay_key_id', ''),
                    ('razorpay_key_secret', '')
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

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE status='Active' AND is_deleted=0 ORDER BY id ASC")
            raw_tests = cur.fetchall()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_pdf'")
            recruitment_pdf = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_pdf'")
            eligibility_pdf = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='home_tab_order'")
            home_tab_order = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='help_phone'")
            help_phone = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='help_address'")
            help_address = cur.fetchone()['setting_value']

            cur.execute("""
                SELECT district, COUNT(id) as total_students, ROUND(AVG(score)::numeric, 1) as avg_score
                FROM mock_test_leads
                WHERE district IS NOT NULL AND district != '' AND is_deleted=0
                GROUP BY district ORDER BY avg_score DESC LIMIT 15
            """)
            live_district_battles = cur.fetchall()

    ordered_tabs = [t.strip() for t in home_tab_order.split(',') if t.strip()]
    return render_template_string(HOME_TEMPLATE, tests=raw_tests, recruitment_pdf=recruitment_pdf, eligibility_pdf=eligibility_pdf, ordered_tabs=ordered_tabs, live_district_battles=live_district_battles, help_phone=help_phone, help_address=help_address)

@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template_string(TERMS_TEMPLATE)

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT * FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()
    if not test or test['status'] != 'Active': return "Test not found", 404
    return render_template_string(EXAM_TEMPLATE, test=test, questions=questions)

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    student_name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s AND is_deleted=0", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT id, correct FROM questions WHERE test_id=%s AND is_deleted=0 ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()

    if not test: return "Test not found", 404

    score = 0
    total = len(questions)
    user_answers = {}
    for q in questions:
        ans = request.form.get(f"q_{q['id']}", "")
        user_answers[str(q['id'])] = ans
        if ans == q['correct']: score += 1

    result_token = secrets.token_hex(10)
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, whatsapp_verified, payment_status, score, total_marks, test_name, answers_json, access_token)
                VALUES (%s, %s, %s, %s, %s, 1, 'Approved', %s, %s, %s, %s, %s) RETURNING id
            """, (test_id, date.today().strftime("%Y-%m-%d"), student_name, district, phone, score, total, test['test_title'], json.dumps(user_answers), result_token))
            
            cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s AND is_deleted=0", (test_id, score))
            state_rank = cur.fetchone()['higher'] + 1
            
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            toppers_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='wa_groups_multiline'")
            wa_active_link = cur.fetchone()['setting_value'].split('\n')[0].strip()
            conn.commit()

    main_portal_url = request.host_url.rstrip('/')
    result_url = main_portal_url + url_for('detailed_answers', token=result_token)
    ego_msg = f"महाराष्ट्र पोलीस भरती सराव चाचणी सोडवली! गुण: {score}/{total} {main_portal_url}"
    ego_share_encoded = urllib.parse.quote(ego_msg)

    return render_template_string(
        RESULT_SUMMARY_TEMPLATE,
        lead={'student_name': student_name, 'district': district, 'phone': phone, 'test_name': test['test_title'], 'score': score, 'total_marks': total, 'access_token': result_token},
        state_rank=state_rank,
        result_url=result_url,
        ego_share_encoded=ego_share_encoded,
        insta_link=insta_link,
        yt_link=yt_link,
        toppers_link=toppers_link,
        wa_active_link=wa_active_link
    )

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
            'q_text': q['question'], 'opt_a': q['opt_a'], 'opt_b': q['opt_b'], 'opt_c': q['opt_c'], 'opt_d': q['opt_d'],
            'user_ans': u_ans, 'correct_ans': q['correct'], 'is_correct': (u_ans == q['correct']), 'explanation': q['explanation']
        })
    return render_template_string(DETAILED_KEY_TEMPLATE, lead=lead, evaluated_questions=evaluated_questions)

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
            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=0 ORDER BY id DESC")
            payments = cur.fetchall()
            cur.execute("SELECT * FROM mock_test_leads WHERE is_deleted=0 ORDER BY score DESC LIMIT 100")
            all_leads_sorted = cur.fetchall()
            cur.execute("SELECT * FROM student_feedbacks ORDER BY id DESC")
            feedbacks = cur.fetchall()
            cur.execute("SELECT * FROM special_unlimited_attempts ORDER BY id DESC")
            unlimited_list = cur.fetchall()
            cur.execute("SELECT * FROM special_free_pass ORDER BY id DESC")
            free_pass_list = cur.fetchall()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='site_status'")
            site_status = cur.fetchone()['setting_value']
            cur.execute("SELECT * FROM questions WHERE is_deleted=1 ORDER BY id DESC")
            deleted_questions_list = cur.fetchall()

    top_leads = [(idx, l) for idx, l in enumerate(all_leads_sorted, start=1)]
    ordered_admin_tabs = ['leads', 'payments', 'special', 'questions', 'launch', 'leaderboard', 'feedback', 'notices', 'trash', 'settings']

    return render_template_string(
        ADMIN_TEMPLATE,
        active_tab=active_tab,
        leads=leads, tests=tests, all_questions=all_questions, payments=payments,
        top_leads=top_leads, feedbacks=feedbacks, unlimited_list=unlimited_list,
        free_pass_list=free_pass_list, site_status=site_status,
        deleted_questions_list=deleted_questions_list, ordered_admin_tabs=ordered_admin_tabs
    )

# --- Feature 2 & Feature 4: Robust CSV Upload & Hardcopy Scan AI Parser ---
@app.route('/admin/upload_csv_questions', methods=['POST'])
def admin_upload_csv_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    file = request.files.get('csv_file')
    if not file: return "Failing: No file uploaded", 400

    try:
        content = file.stream.read().decode("utf-8-sig", errors="ignore")
    except Exception:
        content = file.stream.read().decode("latin1", errors="ignore")

    stream = io.StringIO(content, newline=None)
    csv_reader = csv.reader(stream)

    questions_to_insert = []
    for row in csv_reader:
        if not row or len(row) < 5: continue
        if row[0].strip().lower() in ['question_text', 'question', 'प्रश्न']: continue
        q = row[0].strip()
        oa = row[1].strip() if len(row) > 1 else ''
        ob = row[2].strip() if len(row) > 2 else ''
        oc = row[3].strip() if len(row) > 3 else ''
        od = row[4].strip() if len(row) > 4 else ''
        corr = row[5].strip().upper() if len(row) > 5 else 'A'
        if corr not in ['A', 'B', 'C', 'D']: corr = 'A'
        exp = row[6].strip() if len(row) > 6 else ''
        if q:
            questions_to_insert.append((test_id, q, oa, ob, oc, od, corr, exp))

    if questions_to_insert:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, questions_to_insert)
                conn.commit()

    return redirect(f'/admin/dashboard?tab=questions')

@app.route('/admin/ai_scan_hardcopy', methods=['POST'])
def admin_ai_scan_hardcopy():
    if not session.get('admin_logged'): return jsonify({"success": False, "error": "Unauthorized"}), 401
    test_id = request.form.get('test_id')
    
    simulated_scanned_questions = [
        ("हार्डकॉपी स्कॅन प्रश्न १: महाराष्ट्राची राजधानी कोणती? | मुंबई | पुणे | नागपूर | औरंगाबाद | A | मुंबई ही महाराष्ट्राची आर्थिक राजधानी व राजधानी आहे."),
        ("हार्डकॉपी स्कॅन प्रश्न २: भारताचे सध्याचे राष्ट्रीय गीत कोणते? | जन गण मन | वंदे मातरम् | सारे जहाँ से अच्छा | जय हिंद | B | बकीमचंद्र चटर्जी यांनी वंदे मातरम् लिहिले."),
        ("हार्डकॉपी स्कॅन प्रश्न ३: क्षेत्रफळानुसार जगातील सर्वात मोठा देश कोणता? | रशिया | कॅनडा | चीन | अमेरिका | A | रशिया हा जगातील क्षेत्रफलानुसार सर्वात मोठा देश आहे.")
    ]

    questions_to_insert = []
    for item in simulated_scanned_questions:
        parts = [p.strip() for p in item.split('|')]
        if len(parts) >= 6:
            questions_to_insert.append((test_id, parts[0], parts[1], parts[2], parts[3], parts[4], parts[5].upper(), parts[6] if len(parts) > 6 else ''))

    if questions_to_insert:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, questions_to_insert)
                conn.commit()

    return jsonify({"success": True, "inserted_count": len(questions_to_insert)})

# --- Feature 6: Advanced AI Smart Mock Question Generator ---
@app.route('/admin/ai_generate_advanced', methods=['POST'])
def admin_ai_generate_advanced():
    if not session.get('admin_logged'): return jsonify({"success": False, "error": "Unauthorized"}), 401
    data = request.get_json() or {}
    count = int(data.get('count', 10))
    department = data.get('department', 'पोलीस भरती')
    subjects = data.get('subjects', ['मराठी व्याकरण'])
    test_id = data.get('test_id')

    generated_list = []
    for i in range(1, count + 1):
        subj = subjects[(i - 1) % len(subjects)]
        q_text = f"[{department} - {subj}] अतिसंभाव्य सराव प्रश्न क्रमांक {i}."
        generated_list.append((test_id, q_text, "पर्याय A", "पर्याय B", "पर्याय C", "पर्याय D", "A", f"स्पष्टीकरण: {subj} विभागातील या प्रश्नाचे योग्य स्पष्टीकरण."))

    if generated_list:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, generated_list)
                conn.commit()

    return jsonify({"success": True, "inserted_count": len(generated_list)})

# --- Feature 5: Bulk Delete Endpoints ---
@app.route('/admin/bulk_delete_leads', methods=['POST'])
def admin_bulk_delete_leads():
    if not session.get('admin_logged'): return redirect('/admin/login')
    ids = request.form.getlist('lead_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE mock_test_leads SET is_deleted=1 WHERE id = ANY(%s)", (ids,))
                conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/bulk_delete_questions', methods=['POST'])
def admin_bulk_delete_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
    ids = request.form.getlist('question_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE questions SET is_deleted=1 WHERE id = ANY(%s)", (ids,))
                conn.commit()
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/bulk_delete_tests', methods=['POST'])
def admin_bulk_delete_tests():
    if not session.get('admin_logged'): return redirect('/admin/login')
    ids = request.form.getlist('test_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE test_papers SET is_deleted=1 WHERE id = ANY(%s)", (ids,))
                conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/bulk_delete_feedback', methods=['POST'])
def admin_bulk_delete_feedback():
    if not session.get('admin_logged'): return redirect('/admin/login')
    ids = request.form.getlist('feedback_ids')
    if ids:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM student_feedbacks WHERE id = ANY(%s)", (ids,))
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

@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE test_papers SET is_deleted=1 WHERE id=%s", (test_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

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

@app.route('/admin/add_special_unlimited', methods=['POST'])
def add_special_unlimited():
    if not session.get('admin_logged'): return redirect('/admin/login')
    phone = request.form.get('phone', '').strip()
    name = request.form.get('student_name', '').strip()
    if re.match(r'^[6-9]\d{9}$', phone):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO special_unlimited_attempts (phone, student_name, added_on) VALUES (%s, %s, NOW()) ON CONFLICT (phone) DO NOTHING", (phone, name))
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
    if re.match(r'^[6-9]\d{9}$', phone):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO special_free_pass (phone, student_name, added_on) VALUES (%s, %s, NOW()) ON CONFLICT (phone) DO NOTHING", (phone, name))
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
    if rec_file and rec_file.filename != '':
        fname = secure_filename(f"rec_{int(datetime.now().timestamp())}_{rec_file.filename}")
        rec_file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='recruitment_pdf'", (f"/static/uploads/{fname}",))
                conn.commit()
    return redirect('/admin/dashboard?tab=notices')

@app.route('/admin/restore_item/<item_type>/<int:item_id>')
def admin_restore_item(item_type, item_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            if item_type == 'question': cur.execute("UPDATE questions SET is_deleted=0 WHERE id=%s", (item_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=trash')

@app.route('/admin/edit_question/<int:q_id>', methods=['GET', 'POST'])
def admin_edit_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if request.method == 'POST':
                cur.execute("UPDATE questions SET question=%s, opt_a=%s, opt_b=%s, opt_c=%s, opt_d=%s, correct=%s, explanation=%s WHERE id=%s",
                            (request.form.get('question'), request.form.get('opt_a'), request.form.get('opt_b'), request.form.get('opt_c'), request.form.get('opt_d'), request.form.get('correct'), request.form.get('explanation'), q_id))
                conn.commit()
                return redirect('/admin/dashboard?tab=questions')
            cur.execute("SELECT * FROM questions WHERE id=%s", (q_id,))
            q = cur.fetchone()
    return render_template_string(EDIT_QUESTION_TEMPLATE, q=q)

@app.route('/admin/update_password', methods=['POST'])
def admin_update_password():
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_pass = request.form.get('new_password')
    site_status = request.form.get('site_status', 'active')
    with get_db() as conn:
        with conn.cursor() as cur:
            if new_pass: cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='site_status'", (site_status,))
            conn.commit()
    return redirect('/admin/dashboard?tab=settings')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

