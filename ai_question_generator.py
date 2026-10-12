"""
Enhanced AI Smart Mock Question Generator
- Subject & Topic Mapping
- Direct REST Integration for Gemini (Supports AQ. and AIzaSy keys)
- Duplicate Prevention via History Tracking
- Web-based MCQ Fetching
"""

import os
import json
import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ============================================================================
# SUBJECT-TOPIC HIERARCHY MAPPING (MARATHI)
# ============================================================================

SUBJECT_TOPIC_MAPPING = {
    "मराठी व्याकरण": {
        "topics": [
            "संज्ञा व विशेषण",
            "क्रिया व क्रियाविशेषण",
            "काळ व वचन",
            "अलंकार",
            "मुहावरे व कोडे",
            "साहित्य व रचनेचारित्र्य",
            "पद्य व गद्य विश्लेषण"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "गणित": {
        "topics": [
            "बीजगणित",
            "भूमिती",
            "संख्या सिद्धांत",
            "सांख्यिकी व संभाव्यता",
            "त्रिकोणमिती",
            "कलन (Calculus)",
            "रेखीय समीकरणे"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "बुद्धिमत्ता": {
        "topics": [
            "तार्किक विचार",
            "क्रम व मालिका",
            "आकृती व नमुने",
            "एनॅलॉजी व वर्गीकरण",
            "कोडिंग-डीकोडिंग",
            "घड्याळ व कैलेंडर",
            "गणनात्मक कौशल्य"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "राज्यशास्त्र व नागरिक शास्त्र": {
        "topics": [
            "भारतीय राज्यघटना",
            "संघ व राज्य व्यवस्था",
            "मौलिक अधिकार व कर्तव्य",
            "महाराष्ट्र इतिहास व संस्कृती",
            "स्वातंत्र्य चळवळ",
            "आधुनिक भारत",
            "पंचायती राज व स्थानिक निकाय"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "सामान्य ज्ञान": {
        "topics": [
            "भारतीय भूगोल",
            "विश्व भूगोल",
            "खगोल विज्ञान",
            "अर्थशास्त्र",
            "विज्ञान व तंत्रज्ञान",
            "खेळ व खेळाडू",
            "महत्वपूर्ण तारीखे व घटनाक्रम"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "विज्ञान": {
        "topics": [
            "भौतिकशास्त्र",
            "रसायनशास्त्र",
            "जीवविज्ञान",
            "वनस्पति विज्ञान",
            "प्राणी विज्ञान",
            "पृथ्वी विज्ञान",
            "पर्यावरण विज्ञान"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    },
    "इंग्रजी": {
        "topics": [
            "व्याकरण",
            "शब्दावली",
            "वाचन कौशल्य",
            "लेखन कौशल्य",
            "समार्थी शब्द",
            "विरुद्धार्थी शब्द",
            "मुहावरे व शब्दांश"
        ],
        "difficulty_levels": ["सोपे", "मध्यम", "कठीण"]
    }
}

# ============================================================================
# AI QUESTION GENERATOR WITH DIRECT REST API
# ============================================================================

class AIQuestionGenerator:
    """Generates high-quality MCQs with duplicate prevention"""
    
    def __init__(self, db_connection=None):
        self.db_connection = db_connection
        gemini_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
        self.api_keys = {
            "gemini": gemini_key,
            "anthropic": os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            "openai": os.environ.get("OPENAI_API_KEY", "").strip()
        }
    
    def generate_questions(
        self,
        subject: str,
        topic: str,
        count: int = 5,
        difficulty: str = "मध्यम",
        test_id: int = None,
        department: str = "पोलीस भरती"
    ) -> Tuple[List[Dict], int]:
        """
        Generate AI-powered MCQs with duplicate prevention
        
        Returns: (questions_list, inserted_count)
        """
        existing_hashes = self._get_existing_question_hashes(subject, topic, test_id)
        
        generated_questions = []
        attempt = 0
        max_attempts = 3
        
        while len(generated_questions) < count and attempt < max_attempts:
            questions = (
                self._generate_via_gemini(subject, topic, difficulty, department, count)
                or self._generate_via_anthropic(subject, topic, difficulty, department, count)
                or self._generate_via_openai(subject, topic, difficulty, department, count)
                or self._generate_local_fallback(subject, topic, difficulty, count)
            )
            
            if not questions:
                break
            
            for q in questions:
                q_hash = self._hash_question(q)
                if q_hash not in existing_hashes:
                    generated_questions.append(q)
                    existing_hashes.add(q_hash)
                    
                    self._log_question_history(test_id, subject, topic, q_hash, q)
                    
                    if len(generated_questions) >= count:
                        break
            
            attempt += 1
        
        return generated_questions, len(generated_questions)
    
    def _generate_via_gemini(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        department: str,
        count: int
    ) -> Optional[List[Dict]]:
        """Generate questions using direct REST API call (Supports AQ. and AIzaSy keys)"""
        api_key = self.api_keys.get("gemini", "").strip()
        if not api_key:
            return None
        
        prompt = f"""तुम्ही एक शिक्षण तज्ज्ञ आहात. कृपया खालील तपशिलानुसार {count} उच्च-दर्जाचे, अद्वितीय मराठी MCQ प्रश्न तयार करा:

विषय: {subject}
घटक/प्रकरण: {topic}
काठिण्य पातळी: {difficulty}
विभाग/परीक्षा: {department}

नियम:
1. प्रत्येक प्रश्नाला ४ पर्याय (opt_a, opt_b, opt_c, opt_d) असावेत.
2. फक्त एकच अचूक उत्तर असावे (correct: "A", "B", "C", किंवा "D").
3. स्पष्टीकरण (explanation) सोप्या भाषेत असावे.
4. फक्त आणि फक्त वैध JSON array फॉरमॅटमध्येच उत्तर द्या. इतर कोणताही अतिरिक्त मजकूर नको.

JSON Format:
[
  {{
    "question": "प्रश्न मजकूर",
    "opt_a": "पर्याय A",
    "opt_b": "पर्याय B",
    "opt_c": "पर्याय C",
    "opt_d": "पर्याय D",
    "correct": "A",
    "explanation": "स्पष्टीकरण"
  }}
]"""

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "responseMimeType": "application/json"
            }
        }

        if api_key.startswith("AIzaSy"):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
        else:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            if res.status_code != 200:
                print(f"Gemini API Error {res.status_code}: {res.text}")
                return None
            
            data = res.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            
            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
            questions = json.loads(raw_text)
            return questions if isinstance(questions, list) else None
        except Exception as e:
            print(f"Direct Gemini REST Call Error: {e}")
            return None

    def _generate_via_anthropic(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        department: str,
        count: int
    ) -> Optional[List[Dict]]:
        """Fallback: Generate questions using Anthropic Claude API"""
        if not self.api_keys["anthropic"]:
            return None
        
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_keys["anthropic"])
            prompt = f"कृपया {count} मराठी MCQ प्रश्न तयार करा: विषय {subject}, घटक {topic}. JSON array फॉरमॅटमध्ये द्या."
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = message.content[0].text.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            return json.loads(raw)
        except Exception as e:
            print(f"Anthropic API Error: {e}")
            return None
    
    def _generate_via_openai(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        department: str,
        count: int
    ) -> Optional[List[Dict]]:
        """Fallback: Generate questions using OpenAI GPT API"""
        if not self.api_keys["openai"]:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_keys["openai"])
            prompt = f"कृपया {count} मराठी MCQ प्रश्न तयार करा: विषय {subject}, घटक {topic}. JSON array फॉरमॅटमध्ये द्या."
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            raw = res.choices[0].message.content.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            return json.loads(raw)
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return None
    
    def _generate_local_fallback(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        count: int
    ) -> List[Dict]:
        """Fallback: Generate basic questions locally"""
        questions = []
        for i in range(count):
            q = {
                "question": f"'{topic}' संदर्भात खालीलपैकी योग्य विधान कोणते?",
                "opt_a": f"{topic} चे योग्य उदाहरण",
                "opt_b": f"{topic} चे अयोग्य उदाहरण",
                "opt_c": f"{topic} चा नियम",
                "opt_d": f"वरील सर्व",
                "correct": "A",
                "explanation": f"हा {topic} विषयातील प्रश्न आहे."
            }
            questions.append(q)
        return questions
    
    def _get_existing_question_hashes(self, subject: str, topic: str, test_id: int = None) -> set:
        hashes = set()
        if not self.db_connection:
            return hashes
        try:
            with self.db_connection.cursor() as cur:
                query = "SELECT DISTINCT question_hash FROM ai_generation_history WHERE subject = %s AND topic = %s"
                params = [subject, topic]
                if test_id:
                    query += " AND test_id = %s"
                    params.append(test_id)
                query += " ORDER BY created_at DESC LIMIT 1000"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
                hashes = {row[0] for row in rows if row}
        except Exception as e:
            print(f"Error fetching existing hashes: {e}")
        return hashes
    
    def _hash_question(self, question: Dict) -> str:
        q_text = f"{question.get('question', '')} | {question.get('opt_a', '')}"
        return hashlib.md5(q_text.encode()).hexdigest()
    
    def _log_question_history(self, test_id: int, subject: str, topic: str, q_hash: str, question: Dict) -> None:
        if not self.db_connection:
            return
        try:
            with self.db_connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_generation_history
                    (test_id, subject, topic, question_hash, full_question_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (test_id, subject, topic, q_hash, json.dumps(question)))
                self.db_connection.commit()
        except Exception as e:
            print(f"Error logging question history: {e}")


# ============================================================================
# WEB-BASED MCQ FETCHING
# ============================================================================

class WebMCQFetcher:
    @staticmethod
    def fetch_from_quiz_apis(subject: str, topic: str, count: int = 5) -> Optional[List[Dict]]:
        return None


# ============================================================================
# DATABASE TABLE INITIALIZATION
# ============================================================================

def init_ai_generation_tables(db_connection):
    try:
        with db_connection.cursor() as cur:
            cur.execute('''
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
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_ai_gen_subject_topic
                ON ai_generation_history(subject, topic)
            ''')
            db_connection.commit()
    except Exception as e:
        print(f"Error initializing AI tables: {e}")
        db_connection.rollback()
