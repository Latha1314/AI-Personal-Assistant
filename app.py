from flask import Flask, request, jsonify, render_template
from datetime import datetime
from zoneinfo import ZoneInfo
import pyttsx3
import wolframalpha
import spacy
import re
from dotenv import load_dotenv
import os
import requests
import wikipedia
import threading

# --- Setup ---
app = Flask(__name__)

# --- Text-to-Speech ---
def speak_async(text):
    if os.getenv("RENDER") == "true":
        return  # Skip TTS on Render
    def run():
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    threading.Thread(target=run).start()

# --- Load environment variables ---
load_dotenv()
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# --- Initialize APIs and NLP ---
client = wolframalpha.Client(WOLFRAM_APP_ID)
nlp = spacy.load("en_core_web_sm")

# --- Helper Functions ---
def get_time():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    return f"The current time is {now.strftime('%I:%M %p')}"

def get_weather(city):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_KEY}&units=metric"
    try:
        response = requests.get(url)
        data = response.json()
        if data["cod"] == 200:
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"].capitalize()
            return f"The weather in {city} is {desc} with a temperature of {temp}°C."
        else:
            return "Sorry, I couldn't find that city."
    except:
        return "Error retrieving weather information."

def get_latest_news(topic="AI"):
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={NEWS_API_KEY}&language=en&pageSize=3"
    try:
        response = requests.get(url)
        data = response.json()
        if data["status"] == "ok" and data["articles"]:
            headlines = [article["title"] for article in data["articles"][:3]]
            return f"Here are the top {topic} news headlines: {'; '.join(headlines)}."
        else:
            return "No news found on that topic."
    except:
        return "Error fetching news."

def set_reminder(msg):
    time_match = re.search(r'(\d{1,2}(:\d{2})?\s?(am|pm)?)', msg, re.IGNORECASE)
    if time_match:
        time_str = time_match.group(1).strip()
        return f"Sure, I will remind you at {time_str}."
    else:
        return "Sure, I will remind you soon."
    
def solve_math(query):
    query_lower = query.lower()

    # Replace number words
    num_words = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10"
    }
    for word, digit in num_words.items():
        query_lower = re.sub(rf"\b{word}\b", digit, query_lower)

    # Replace math phrases
    replacements = {
        "plus": "+", "add": "+",
        "minus": "-", "subtract": "-",
        "times": "*", "multiplied by": "*", "into": "*",
        "divided by": "/", "over": "/",
        "square of": "**2", "cube of": "**3",
        "to the power of": "**",
        "power": "**"
    }
    for k, v in replacements.items():
        query_lower = query_lower.replace(k, v)

    # Remove filler words
    query_clean = re.sub(r"(calculate|solve|what is|evaluate|find|equals|the|answer|result of)", "", query_lower)
    query_clean = re.sub(r"[^0-9+\-*/(). ]", "", query_clean).strip()

    # If the query is empty, stop
    if not query_clean:
        return "Sorry, I couldn't understand the math expression."

    # Try evaluating with eval()
    try:
        result = eval(query_clean)
        return f"The answer is {result}."
    except Exception:
        # Try WolframAlpha as a backup
        try:
            res = client.query(query)
            answer = next(res.results).text
            return f"The answer is {answer}."
        except:
            return "Sorry, I couldn't calculate that."

def search_wikipedia(query):
    try:
        return wikipedia.summary(query, sentences=2)
    except:
        return "Sorry, I couldn't find information on that."

# --- NLP Command Processor with Multi-Command Handling ---

# --- NLP Command Processor with Multi-Command Handling ---
def process_command(text):
    text_lower = text.lower().strip()
    commands = re.split(r'\band\b|;|,', text_lower)  # Split multiple commands
    responses = []

    for cmd in commands:
        cmd = cmd.strip()
        # --- Greetings ---
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
        import random
        if any(re.search(rf'\b{greet}\b', cmd) for greet in greetings):
            responses.append(random.choice([
                "Hello! How can I assist you today?",
                "Hi there! What can I do for you?",
                "Good to see you! How can I help?",
            ]))
            continue

        # --- Browser Commands ---
        if "open browser" in cmd or "launch browser" in cmd:
            if os.getenv("RENDER") == "true":
                responses.append("Click here to open Google: https://www.google.com")
            else:
                import webbrowser
                webbrowser.open("https://www.google.com")
                responses.append("Opening your web browser.")
            continue

        if "open youtube" in cmd:
            if os.getenv("RENDER") == "true":
                responses.append("Click here to open YouTube: https://www.youtube.com")
            else:
                import webbrowser
                webbrowser.open("https://www.youtube.com")
                responses.append("Opening YouTube in your browser.")
            continue

        # --- Time ---
        if "time" in cmd:
            responses.append(get_time())
            continue

        # --- Weather ---
        if "weather" in cmd:
            match = re.search(r'weather in ([a-zA-Z\s]+)', cmd)
            if match:
                city = match.group(1).strip()
                responses.append(get_weather(city))
                continue

        # --- News ---
        if "news" in cmd:
            match = re.search(r'news on ([a-zA-Z\s]+)', cmd)
            topic = match.group(1).strip() if match else "AI"
            responses.append(get_latest_news(topic))
            continue

        # --- Math ---
        if any(word in cmd for word in ["calculate", "solve", "what is", "compute", "evaluate"]) or re.match(r"^[0-9+\-*/(). ]+$", cmd):
            responses.append(solve_math(cmd))
            continue

        # --- Wikipedia ---
        if any(phrase in cmd for phrase in ["who is", "what is", "tell me about"]):
            topic = cmd.replace("who is","").replace("what is","").replace("tell me about","").strip()
            if topic:
                responses.append(search_wikipedia(topic))
                continue

        # --- Reminder ---
        if "remind" in cmd:
            responses.append(set_reminder(cmd))
            continue

        # --- Fallback ---
        responses.append("Sorry, I couldn't understand that part: " + cmd)

    final_response = " ".join(responses)
    speak_async(final_response)
    return final_response


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/command', methods=['POST'])
def handle_command():
    data = request.json
    user_input = data.get("command", "")
    response = process_command(user_input)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)