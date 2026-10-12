"""
Enhanced AI Smart Mock Question Generator & Auto-Pilot Engine
- Subject & Topic Mapping for Maharashtra Police & Competitive Exams
- Google Gemini Integration (Flash + Vision OCR)
- Duplicate Prevention via History Tracking (MD5 Hash Matching)
- Raw Text to Quiz Parser
- Question Validator & Duplicate Gatekeeper
- Feedback Sentiment Summarizer
"""

import os
import json
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from PIL import Image
except ImportError:
    Image = None

# ============================================================================
# SUBJECT-TOPIC HIERARCHY MAPPING (MARATHI)
# ============================================================================

SUBJECT_TOPIC_MAPPING = {
    "मराठी व्याकरण": {
        "topics": [
            "वर्णविचार व संधी",
            "नाम, सर्वनाम, विशेषण व क्रियापद",
            "काळ व काळांचे प्रकार",
            "प्रयोग व समास",
            "अलंकार व वृत्त",
            "वाक्प्रचार व म्हणी",
            "समानार्थी व विरुद्धार्थी शब्द",
            "शब्दसमूहाबद्दल एक शब्द",
            "शुद्धलेखन व विरामचिन्हे"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "गणित": {
        "topics": [
            "संख्याज्ञान व कसोट्या",
            "लसावि व मसावि",
            "दशांश व व्यवहारी अपूर्णांक",
            "शेकडेवारी व नफा-तोटा",
            "सरळव्याज व चक्रवाढव्याज",
            "गुणोत्तर व प्रमाण / भागीदारी",
            "काळ, काम, वेग व अंतर",
            "सरासरी व वयवारी",
            "क्षेत्रफळ व घनफळ"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "बुद्धिमत्ता चाचणी": {
        "topics": [
            "संख्या व अक्षर मालिका",
            "सांकेतिक भाषा (Coding-Decoding)",
            "नातेसंबंध",
            "दिशा व अंतर",
            "घड्याळ व दिनदर्शिका (कॅलेंडर)",
            "तार्किक विधाने व निष्कर्ष",
            "आकृत्यांची मोजणी व सुसंगतता",
            "वेन आकृत्या"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "सामान्य ज्ञान व चालू घडामोडी": {
        "topics": [
            "महाराष्ट्राचा व भारताचा भूगोल",
            "महाराष्ट्राचा व भारताचा इतिहास",
            "भारतीय राज्यघटना व पंचायत राज",
            "पोलीस प्रशासन व गृह विभाग विशेष",
            "सामान्य विज्ञान (भौतिक, रसायन, जीवशास्त्र)",
            "अर्थशास्त्र व शासकीय योजना",
            "राष्ट्रीय व आंतरराष्ट्रीय चालू घडामोडी २०२५-२०२६",
            "पुरस्कार, क्रीडा व महत्वाच्या व्यक्ती"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    }
}

class AIQuestionGenerator:
    """Generates MCQs, performs OCR, validates questions, and prevents duplicates."""

    def __init__(self, db_connection=None):
        self.db_connection = db_connection
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        if genai and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
            except Exception as e:
                print(f"Gemini Init Warning: {e}")

    def _get_model(self, model_name: str = "gemini-2.5-flash"):
        if not genai or not self.api_key:
            return None
        try:
            return genai.GenerativeModel(model_name)
        except Exception as e:
            print(f"Error getting model {model_name}: {e}")
            return None

    def _hash_question(self, question: Dict) -> str:
        q_text = (question.get('question') or '').strip().lower()
        opt_a = (question.get('opt_a') or '').strip().lower()
        combined = f"{q_text}|{opt_a}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    def _get_existing_question_hashes(self, subject: str = None, topic: str = None, test_id: int = None) -> set:
        hashes = set()
        if not self.db_connection:
            return hashes
        try:
            with self.db_connection.cursor() as cur:
                query = "SELECT DISTINCT question_hash FROM ai_generation_history WHERE 1=1"
                params = []
                if subject:
                    query += " AND subject = %s"
                    params.append(subject)
                if topic:
                    query += " AND topic = %s"
                    params.append(topic)
                if test_id:
                    query += " AND test_id = %s"
                    params.append(test_id)
                query += " ORDER BY id DESC LIMIT 2000"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
                hashes = {r[0] for r in rows if r and r[0]}
        except Exception as e:
            print(f"Error fetching existing hashes: {e}")
        return hashes

    def _log_question_history(self, test_id: int, subject: str, topic: str, q_hash: str, question: Dict) -> None:
        if not self.db_connection:
            return
        try:
            with self.db_connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_generation_history
                    (test_id, subject, topic, question_hash, full_question_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (subject, topic, question_hash) DO NOTHING
                """, (
                    test_id,
                    subject or "सामान्य",
                    topic or "सर्वसाधारण",
                    q_hash,
                    json.dumps(question, ensure_ascii=False)
                ))
                self.db_connection.commit()
        except Exception as e:
            print(f"Error logging question history: {e}")
            try:
                self.db_connection.rollback()
            except Exception:
                pass

    def generate_questions(
        self,
        subject: str,
        topic: str,
        count: int = 5,
        difficulty: str = "मध्यम",
        test_id: int = None,
        department: str = "महाराष्ट्र पोलीस भरती"
    ) -> Tuple[List[Dict], int]:
        existing_hashes = self._get_existing_question_hashes(subject, topic, test_id)
        generated_questions = []
        model = self._get_model()

        if model:
            prompt = f"""तुम्ही महाराष्ट्र पोलीस भरती आणि स्पर्धा परीक्षांचे मुख्य पेपर सेटर आहात.
कृपया खालील विषयानुरूप {count} अत्यंत दर्जेदार, मूळ (Original), आणि अचूक मराठी बहुपर्यायी प्रश्न (MCQs) तयार करा:

विषय: {subject}
घटक/टॉपिक: {topic}
काठिण्य पातळी: {difficulty}
परीक्षा: {department}

अटी:
१. प्रश्न पूर्णपणे मराठीत असावेत.
२. प्रत्येक प्रश्नाला ४ पर्याय (A, B, C, D) द्या.
३. एकच पर्याय १००% बरोबर असावा.
४. मराठीत सोपे व सविस्तर स्पष्टीकरण द्या.
५. फक्त वैध JSON Array आउटपुट द्या:

[
  {{
    "question": "प्रश्नाचा मजकूर",
    "opt_a": "पर्याय A",
    "opt_b": "पर्याय B",
    "opt_c": "पर्याय C",
    "opt_d": "पर्याय D",
    "correct": "A",
    "explanation": "याचे अचूक स्पष्टीकरण..."
  }}
]"""
            try:
                resp = model.generate_content(prompt)
                resp_text = resp.text.strip()
                if "```json" in resp_text:
                    resp_text = resp_text.split("```json")[1].split("```")[0].strip()
                elif "```" in resp_text:
                    resp_text = resp_text.split("```")[1].split("```")[0].strip()

                parsed = json.loads(resp_text)
                if isinstance(parsed, list):
                    for q in parsed:
                        q_hash = self._hash_question(q)
                        if q_hash not in existing_hashes:
                            generated_questions.append(q)
                            existing_hashes.add(q_hash)
                            self._log_question_history(test_id, subject, topic, q_hash, q)
                            if len(generated_questions) >= count:
                                break
            except Exception as e:
                print(f"Gemini Generation Error: {e}")

        if len(generated_questions) < count:
            needed = count - len(generated_questions)
            fallback = self._generate_local_fallback(subject, topic, difficulty, needed)
            for q in fallback:
                q_hash = self._hash_question(q)
                if q_hash not in existing_hashes:
                    generated_questions.append(q)
                    existing_hashes.add(q_hash)
                    self._log_question_history(test_id, subject, topic, q_hash, q)

        return generated_questions, len(generated_questions)

    def scan_hardcopy_image(self, image_path: str, test_id: int = None) -> List[Dict]:
        model = self._get_model()
        if not model or not Image:
            return []

        try:
            img = Image.open(image_path)
            prompt = """या प्रतिमेतील (Photo/Scan) पोलीस भरती किंवा स्पर्धा परीक्षेचे सर्व प्रश्न, ४ पर्याय आणि उत्तरे वाचा.
त्यांचे रूपांतर खालीलप्रमाणे अचूक मराठी JSON Array मध्ये करा:
[
  {
    "question": "प्रश्नाचा मजकूर",
    "opt_a": "पर्याय A",
    "opt_b": "पर्याय B",
    "opt_c": "पर्याय C",
    "opt_d": "पर्याय D",
    "correct": "A",
    "explanation": "स्पष्टीकरण किंवा संदर्भ"
  }
]
फक्त JSON Array उत्तर म्हणून द्या."""

            resp = model.generate_content([prompt, img])
            resp_text = resp.text.strip()
            if "```json" in resp_text:
                resp_text = resp_text.split("```json")[1].split("```")[0].strip()
            elif "```" in resp_text:
                resp_text = resp_text.split("```")[1].split("```")[0].strip()

            data = json.loads(resp_text)
            if isinstance(data, list):
                valid_items = []
                for item in data:
                    c = str(item.get('correct', 'A')).strip().upper()
                    if c not in ['A', 'B', 'C', 'D']:
                        c = 'A'
                    item['correct'] = c
                    valid_items.append(item)
                return valid_items
        except Exception as e:
            print(f"Vision OCR Error: {e}")
        return []

    def raw_text_to_mcqs(self, raw_text: str, test_id: int = None) -> List[Dict]:
        model = self._get_model()
        if not model or not raw_text.strip():
            return []

        try:
            prompt = f"""खालील बातमी/मजकुराचा (Raw Text) अभ्यास करा आणि त्यावर आधारित महाराष्ट्र पोलीस भरती दर्जाचे बहुपर्यायी प्रश्न (MCQs) तयार करा:

मजकूर:
\"\"\"{raw_text}\"\"\"

अटी:
१. प्रत्येकाला ४ पर्याय (A, B, C, D) असावेत.
२. अचूक उत्तर आणि मराठीत स्पष्टीकरण द्या.
३. फक्त JSON Array फॉरमॅट द्या:
[
  {{
    "question": "...",
    "opt_a": "...",
    "opt_b": "...",
    "opt_c": "...",
    "opt_d": "...",
    "correct": "A",
    "explanation": "..."
  }}
]"""
            resp = model.generate_content(prompt)
            txt = resp.text.strip()
            if "```json" in txt:
                txt = txt.split("```json")[1].split("```")[0].strip()
            elif "```" in txt:
                txt = txt.split("```")[1].split("```")[0].strip()
            items = json.loads(txt)
            if isinstance(items, list):
                return items
        except Exception as e:
            print(f"Raw text conversion error: {e}")
        return []

    def validate_questions_batch(self, questions: List[Dict]) -> List[Dict]:
        warnings = []
        seen = set()

        for idx, q in enumerate(questions, start=1):
            q_text = (q.get('question') or '').strip()
            oa = (q.get('opt_a') or '').strip()
            ob = (q.get('opt_b') or '').strip()
            oc = (q.get('opt_c') or '').strip()
            od = (q.get('opt_d') or '').strip()
            corr = (q.get('correct') or '').strip().upper()

            if not q_text:
                warnings.append({"index": idx, "issue": "प्रश्नाचा मजकूर रिकामा आहे."})
                continue

            opts = [oa, ob, oc, od]
            if len(set(opts)) < 4:
                warnings.append({"index": idx, "issue": "दोन किंवा अधिक पर्याय समान आहेत."})

            if corr not in ['A', 'B', 'C', 'D']:
                warnings.append({"index": idx, "issue": f"अवैध उत्तर पर्याय ({corr}). A/B/C/D आवश्यक आहे."})

            q_hash = hashlib.md5(f"{q_text}|{oa}".encode('utf-8')).hexdigest()
            if q_hash in seen:
                warnings.append({"index": idx, "issue": "हा प्रश्न याच यादीत ड्युप्लिकेट आला आहे."})
            seen.add(q_hash)

        return warnings

    def summarize_feedbacks(self, feedbacks: List[str]) -> str:
        model = self._get_model()
        if not model or not feedbacks:
            return "सध्या पुरेसे अभिप्राय उपलब्ध नाहीत."
        try:
            combined = "\n- ".join(feedbacks[:50])
            prompt = f"""तुम्ही ऑनलाइन टेस्ट पोर्टलचे AI ॲनालिस्ट आहात.
खालील विद्यार्थ्यांचे अभिप्राय (Feedbacks) वाचून ॲडमिनसाठी फक्त एका संक्षिप्त मराठी परिच्छेदात सारांश द्या:
विद्यार्थ्यांना काय आवडले, कोणत्या विषयात अडचण वाटली आणि ॲडमिनने काय सुधारणा करावी.

विद्यार्थ्यांचे अभिप्राय:
- {combined}"""
            resp = model.generate_content(prompt)
            return resp.text.strip()
        except Exception as e:
            return f"अभिप्राय सारांश तयार करताना तांत्रिक अडचण: {e}"

    def _generate_local_fallback(self, subject: str, topic: str, difficulty: str, count: int) -> List[Dict]:
        questions = []
        for i in range(1, count + 1):
            questions.append({
                "question": f"[{subject}] {topic} घटकावर आधारित सराव प्रश्न #{i} खालीलपैकी कोणता योग्य आहे?",
                "opt_a": f"{topic} मूलभूत संकल्पना A",
                "opt_b": f"{topic} सराव पर्याय B",
                "opt_c": f"{topic} पर्याय C",
                "opt_d": f"{topic} पर्याय D",
                "correct": ["A", "B", "C", "D"][(i - 1) % 4],
                "explanation": f"हा प्रश्न {subject} विषयातील '{topic}' घटकाचा {difficulty} काठिण्य पातळीचा सराव प्रश्न आहे."
            })
        return questions

def init_ai_generation_tables(db_connection):
    try:
        with db_connection.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_generation_history (
                    id SERIAL PRIMARY KEY,
                    test_id INTEGER,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    question_hash VARCHAR(32) NOT NULL,
                    full_question_json TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(subject, topic, question_hash)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_gen_subject_topic
                ON ai_generation_history(subject, topic)
            """)
            db_connection.commit()
            print("✅ AI Generation History tables initialized successfully.")
    except Exception as e:
        print(f"❌ Error initializing AI tables: {e}")
        try:
            db_connection.rollback()
        except Exception:
            pass

