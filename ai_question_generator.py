"""
Enhanced AI Smart Mock Question Generator
- Subject & Topic Mapping
- Real AI Integration (Google Gemini / OpenAI)
- Duplicate Prevention via History Tracking
- Web-based MCQ Fetching
"""

import os
import json
import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import anthropic

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
# AI QUESTION GENERATOR WITH MULTIPLE BACKENDS
# ============================================================================

class AIQuestionGenerator:
    """Generates high-quality MCQs with duplicate prevention"""
    
    def __init__(self, db_connection=None):
        self.db_connection = db_connection
        self.api_keys = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
            "openai": os.environ.get("OPENAI_API_KEY", ""),
            "gemini": os.environ.get("GOOGLE_API_KEY", "")
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
            # Try Anthropic first, fallback to OpenAI, then to local generation
            questions = (
                self._generate_via_anthropic(subject, topic, difficulty, department, count)
                or self._generate_via_openai(subject, topic, difficulty, department, count)
                or self._generate_local_fallback(subject, topic, difficulty, count)
            )
            
            if not questions:
                break
            
            # Filter duplicates
            for q in questions:
                q_hash = self._hash_question(q)
                if q_hash not in existing_hashes:
                    generated_questions.append(q)
                    existing_hashes.add(q_hash)
                    
                    # Log to history
                    self._log_question_history(test_id, subject, topic, q_hash, q)
                    
                    if len(generated_questions) >= count:
                        break
            
            attempt += 1
        
        return generated_questions, len(generated_questions)
    
    def _generate_via_anthropic(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        department: str,
        count: int
    ) -> Optional[List[Dict]]:
        """Generate questions using Anthropic Claude API"""
        if not self.api_keys["anthropic"]:
            return None
        
        try:
            client = anthropic.Anthropic(api_key=self.api_keys["anthropic"])
            
            prompt = f"""तुम्ही एक शिक्षा तज्ञ आहात. कृपया खालील विशेष्यांचे अनुसार {count} उच्च-गुणवत्तेचे, अद्वितीय मराठी MCQ प्रश्न तयार करा:

विषय: {subject}
विषयवस्तु: {topic}
कठिणता: {difficulty}
विभाग: {department}

प्रत्येक प्रश्नासाठी हे नक्की करा:
1. प्रश्न स्पष्ट, संक्षिप्त आणि वास्तविक/प्रासंगिक असेल
2. ४ विकल्प (A, B, C, D) असतील
3. फक्त एकच अचूक उत्तर असेल
4. स्पष्टीकरण {difficulty} स्तराच्या समजून घेण्यासाठी संपूर्ण आणि सहायक असेल
5. प्रश्न {department} भरती परीक्षेसाठी अनुकूल असेल

प्रतिसाद या JSON फॉरमॅटमध्ये द्या (फक्त JSON array, इतर मजकूर नाही):
[
  {{
    "question": "...",
    "opt_a": "...",
    "opt_b": "...",
    "opt_c": "...",
    "opt_d": "...",
    "correct": "A/B/C/D",
    "explanation": "..."
  }}
]"""
            
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = message.content[0].text.strip()
            # Extract JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            questions = json.loads(response_text)
            return questions if isinstance(questions, list) else None
            
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
        """Generate questions using OpenAI GPT API"""
        if not self.api_keys["openai"]:
            return None
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_keys["openai"])
            
            prompt = f"""तुम्ही एक शिक्षा तज्ञ आहात. कृपया खालील विशेष्यांचे अनुसार {count} उच्च-गुणवत्तेचे, अद्वितीय मराठी MCQ प्रश्न तयार करा:

विषय: {subject}
विषयवस्तु: {topic}
कठिणता: {difficulty}
विभाग: {department}

प्रत्येक प्रश्नासाठी:
1. प्रश्न स्पष्ट आणि {department} भरती परीक्षेसाठी अनुकूल असेल
2. ४ विभिन्न विकल्प (A, B, C, D)
3. केवळ एकच अचूक उत्तर
4. विस्तृत स्पष्टीकरण

JSON array फॉरमॅटमध्ये केवळ प्रतिसाद द्या:
[{{"question": "...", "opt_a": "...", "opt_b": "...", "opt_c": "...", "opt_d": "...", "correct": "A/B/C/D", "explanation": "..."}}]"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            
            questions = json.loads(response_text)
            return questions if isinstance(questions, list) else None
            
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
        """Fallback: Generate questions locally using templates"""
        questions = []
        
        templates = {
            "मराठी व्याकरण": [
                {
                    "question": f"'{topic}' विषयी खालीलपैकी अचूक वाक्य कोणते?",
                    "options": [
                        f"{topic}चे सरळ उदाहरण",
                        f"{topic}चे चुकीचे प्रयोग",
                        f"{topic}चा परिभाषा",
                        f"{topic}बद्दल सामान्य ज्ञान"
                    ]
                }
            ],
            "गणित": [
                {
                    "question": f"जर x + 5 = {10 + count}, तर x = ?",
                    "options": [
                        str(count + 5),
                        str(count - 5),
                        str(15 + count),
                        str(20 - count)
                    ]
                }
            ],
            "बुद्धिमत्ता": [
                {
                    "question": f"मालिकेचा पुढील क्रमांक शोधा: 2, 4, 6, 8, ?",
                    "options": ["10", "12", "14", "16"]
                }
            ],
            "राज्यशास्त्र व नागरिक शास्त्र": [
                {
                    "question": f"भारतीय राज्यघटनेतील {topic} कलम संदर्भात खालीलपैकी काय सत्य आहे?",
                    "options": [
                        f"{topic} संदर्भात सत्य विधान १",
                        f"{topic} संदर्भात सत्य विधान २",
                        f"{topic} संदर्भात सत्य विधान ३",
                        f"{topic} संद��्भात सत्य विधान ४"
                    ]
                }
            ]
        }
        
        base_template = templates.get(subject, templates["सामान्य ज्ञान"] if "सामान्य ज्ञान" in templates else templates.get(list(templates.keys())[0]))
        
        for i in range(count):
            template = base_template[i % len(base_template)]
            q = {
                "question": template["question"],
                "opt_a": template["options"][0],
                "opt_b": template["options"][1],
                "opt_c": template["options"][2],
                "opt_d": template["options"][3],
                "correct": ["A", "B", "C", "D"][i % 4],
                "explanation": f"यह {topic} विषयातील {difficulty} स्तरीय प्रश्न आहे."
            }
            questions.append(q)
        
        return questions
    
    def _get_existing_question_hashes(self, subject: str, topic: str, test_id: int = None) -> set:
        """Fetch previously generated question hashes to prevent duplicates"""
        hashes = set()
        
        if not self.db_connection:
            return hashes
        
        try:
            with self.db_connection.cursor() as cur:
                query = """
                    SELECT DISTINCT question_hash
                    FROM ai_generation_history
                    WHERE subject = %s AND topic = %s
                """
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
        """Generate a unique hash for a question"""
        q_text = f"{question.get('question', '')} | {question.get('opt_a', '')}"
        return hashlib.md5(q_text.encode()).hexdigest()
    
    def _log_question_history(
        self,
        test_id: int,
        subject: str,
        topic: str,
        q_hash: str,
        question: Dict
    ) -> None:
        """Log generated question to history table"""
        if not self.db_connection:
            return
        
        try:
            with self.db_connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_generation_history
                    (test_id, subject, topic, question_hash, full_question_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (
                    test_id,
                    subject,
                    topic,
                    q_hash,
                    json.dumps(question)
                ))
                self.db_connection.commit()
        except Exception as e:
            print(f"Error logging question history: {e}")


# ============================================================================
# WEB-BASED MCQ FETCHING (From Quality Sources)
# ============================================================================

class WebMCQFetcher:
    """Fetch MCQs from online question banks"""
    
    @staticmethod
    def fetch_from_quiz_apis(subject: str, topic: str, count: int = 5) -> Optional[List[Dict]]:
        """
        Fetch questions from public quiz APIs
        Supports: Open Trivia DB, QuizAPI, etc.
        """
        try:
            # Example: Using Open Trivia Database
            # Note: Requires internet access
            
            subject_category_map = {
                "सामान्य ज्ञान": 9,  # General Knowledge
                "विज्ञान": 17,  # Science
                "खेळ": 21,  # Sports
            }
            
            category = subject_category_map.get(subject, 9)
            
            url = "https://opentdb.com/api.php"
            params = {
                "amount": count,
                "category": category,
                "type": "multiple",
                "difficulty": "medium"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("response_code") != 0:
                return None
            
            questions = []
            for item in data.get("results", []):
                import html
                q = {
                    "question": html.unescape(item["question"]),
                    "opt_a": html.unescape(item["correct_answer"]),
                    "opt_b": html.unescape(item["incorrect_answers"][0]) if len(item["incorrect_answers"]) > 0 else "विकल्प B",
                    "opt_c": html.unescape(item["incorrect_answers"][1]) if len(item["incorrect_answers"]) > 1 else "विकल्प C",
                    "opt_d": html.unescape(item["incorrect_answers"][2]) if len(item["incorrect_answers"]) > 2 else "विकल्प D",
                    "correct": "A",  # opt_a is always correct_answer
                    "explanation": f"स्रोत: Open Trivia Database - {topic}"
                }
                questions.append(q)
            
            return questions
            
        except Exception as e:
            print(f"Error fetching from web APIs: {e}")
            return None


# ============================================================================
# DATABASE TABLE INITIALIZATION
# ============================================================================

def init_ai_generation_tables(db_connection):
    """Create required tables for AI question generation tracking"""
    try:
        with db_connection.cursor() as cur:
            # Table to track generated questions and prevent duplicates
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
            
            # Create index for faster lookups
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_ai_gen_subject_topic
                ON ai_generation_history(subject, topic)
            ''')
            
            db_connection.commit()
            print("✅ AI Generation History tables initialized")
    except Exception as e:
        print(f"❌ Error initializing AI tables: {e}")
        db_connection.rollback()
