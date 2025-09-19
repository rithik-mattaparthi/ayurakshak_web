from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_pymongo import PyMongo
from datetime import datetime, timezone
from langdetect import detect
from googletrans import Translator
import os

app = Flask(__name__)

# === Configuration ===
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/ayurakshak")
mongo = PyMongo(app)

translator = Translator()

# Supported languages
LANGUAGES = {
    "hi": "हिंदी (Hindi)",
    "en": "English",
    "te": "తెలుగు (Telugu)",
    "or": "ଓଡିଆ (Odia)"
}

# Health helpline numbers
HELPLINES = {
    "default": "104 (Govt. Health Helpline - India)"
}

DISCLAIMER = "⚠ Please consult a doctor before following this advice."

# --- Helpers ---
def detect_language(text):
    """Detect language using langdetect library."""
    try:
        return detect(text)
    except:
        return "en"

def translate_text(text, target_lang):
    """Translate text using Google Translate."""
    try:
        result = translator.translate(text, dest=target_lang)
        return result.text
    except:
        return text

def analyze_symptoms(text):
    """Simple symptom analyzer."""
    txt = text.lower()
    symptoms = []
    severity = "mild"
    if any(w in txt for w in ["fever", "बुखार"]):
        symptoms.append("fever")
    if any(w in txt for w in ["pain", "दर्द", "ache"]):
        symptoms.append("pain")
    if any(w in txt for w in ["bleeding", "unconscious", "severe", "chest pain", "difficulty breathing"]):
        severity = "severe"
    if "high" in txt or "104" in txt:
        severity = "moderate"
    return {"symptoms": symptoms, "severity": severity, "notes": ""}

# === Routes ===
@app.route("/")
def home():
    return render_template("language_select.html", languages=LANGUAGES)

@app.route("/chat/<lang_code>")
def chat(lang_code):
    lang_name = LANGUAGES.get(lang_code, "English")
    return render_template("chat.html", language=lang_name, lang_code=lang_code, helpline=HELPLINES["default"])

@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.json or {}
    user_msg = data.get("message", "")
    lang_code = data.get("lang_code", "en")

    # Save user msg
    mongo.db.messages.insert_one({
        "sender": "user",
        "lang_code": lang_code,
        "message": user_msg,
        "timestamp": datetime.now(timezone.utc)
    })

    # Detect language + translate to English for processing
    detected = detect_language(user_msg)
    user_msg_en = translate_text(user_msg, "en") if detected != "en" else user_msg

    # Core logic
    analysis = analyze_symptoms(user_msg_en)
    reply_lines = []

    if "pain" in user_msg_en.lower() or "दर्द" in user_msg:
        reply_lines.append(f"I detected pain. Please call {HELPLINES['default']}.")
        reply_lines.append("If the pain is intense or sudden, visit the nearest hospital 👉 https://www.google.com/maps/search/hospital+near+me")
    elif "fever" in user_msg_en.lower() or "बुखार" in user_msg:
        reply_lines.append("For fever: Drink fluids, rest, monitor temperature.")
    elif "garlic" in user_msg_en.lower():
        reply_lines.append("⚠ Garlic does NOT cure TB. Refer to official guidance (WHO) for treatment.")
        reply_lines.append("https://www.who.int")
    elif "sos" in user_msg_en.lower() or "😭" in user_msg:
        reply_lines.append(f"🚨 Emergency detected! Call {HELPLINES['default']} or nearest hospital immediately.")
    else:
        if analysis["symptoms"]:
            reply_lines.append(f"I detected symptoms: {', '.join(analysis['symptoms'])}.")
            if analysis["severity"] == "severe":
                reply_lines.append("Severity appears high — seek emergency care now: https://www.google.com/maps/search/hospital+near+me")
            else:
                reply_lines.append("Try home care measures (rest, fluids). Monitor and seek care if symptoms worsen.")
        else:
            reply_lines.append(f"You said: {user_msg_en}")
            reply_lines.append("Tell me more about your symptoms or type 'symptom checker' to begin.")

    # Always append disclaimer
    reply_text = "\n".join(reply_lines + [DISCLAIMER])

    # Translate reply back to the user’s language
    final_reply = translate_text(reply_text, lang_code) if lang_code != "en" else reply_text

    # Save bot reply
    mongo.db.messages.insert_one({
        "sender": "bot",
        "lang_code": lang_code,
        "message": final_reply,
        "timestamp": datetime.now(timezone.utc)
    })

    return jsonify({"reply": final_reply})

# Upload file endpoint (same as before)
@app.route("/upload_file", methods=["POST"])
def upload_file():
    f = request.files.get("file")
    lang_code = request.form.get("lang_code", "en")
    if not f:
        return jsonify({"reply": "No file received.\n" + DISCLAIMER}), 400

    filename = f.filename
    mongo.db.messages.insert_one({
        "sender": "user",
        "lang_code": lang_code,
        "message": f"Uploaded file: {filename}",
        "timestamp": datetime.now(timezone.utc)
    })

    # Simulated OCR result
    ocr_text = f"Simulated OCR of {filename}: Paracetamol 500mg twice daily for 5 days."
    explanation = (
        f"I found this in your document: {ocr_text}\n"
        "Dosage: Paracetamol 500 mg - take one tablet twice a day after food. "
        "If fever persists > 48 hours, consult your doctor."
    )
    explanation += "\n" + DISCLAIMER

    explanation = translate_text(explanation, lang_code) if lang_code != "en" else explanation

    mongo.db.messages.insert_one({
        "sender": "bot",
        "lang_code": lang_code,
        "message": explanation,
        "timestamp": datetime.now(timezone.utc)
    })

    return jsonify({"reply": explanation})

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
