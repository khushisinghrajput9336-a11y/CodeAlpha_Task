from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import os

app = Flask(__name__)

USERNAME_FILE = "username.txt"

# ---------------- SAVE USERNAME ----------------
def save_username(name):
    with open(USERNAME_FILE, "w", encoding="utf-8") as f:
        f.write(name)

def get_username():
    if os.path.exists(USERNAME_FILE):
        with open(USERNAME_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

# ---------------- CHATBOT LOGIC ----------------
def chatbot_reply(msg):
    msg = msg.lower()
    user = get_username()

    # ---------------- GREETINGS ----------------
    if msg in ["hi", "hello", "hey", "hii", "hey bot"]:
        return f"Hello {user}! 😊" if user else "Hello! 😊 What is your name?"

    elif msg in ["good morning"]:
        return "Good Morning 🌅 Have a great day!"

    elif msg in ["good afternoon"]:
        return "Good Afternoon ☀️"

    elif msg in ["good evening"]:
        return "Good Evening 🌇"

    elif msg in ["good night"]:
        return "Good Night 🌙 Sweet dreams!"

    # ---------------- NAME ----------------
    elif "my name is" in msg:
        name = msg.replace("my name is", "").strip()
        save_username(name)
        return f"Nice to meet you, {name}! 😄 I will remember you."

    elif "what is my name" in msg:
        return f"Your name is {user} 😊" if user else "I don't know your name yet."

    # ---------------- EMOTIONS ----------------
    elif msg in ["i am happy", "happy", "feeling good"]:
        return "That's awesome 😄 Keep smiling!"

    elif msg in ["i am sad", "sad", "depressed", "upset"]:
        return "I'm sorry to hear that 😔 Everything will be okay ❤️"

    elif msg in ["angry", "i am angry"]:
        return "Take a deep breath 😌 Things will get better."

    elif msg in ["bored"]:
        return "Let's talk! 😊 Or I can tell you a joke."

    # ---------------- JOKES ----------------
    elif msg in ["joke", "tell me a joke"]:
        return "Why do programmers prefer dark mode? 😂 Because light attracts bugs!"

    # ---------------- WEATHER (DUMMY) ----------------
    elif "weather" in msg:
        return "🌤️ Weather today is sunny with mild wind (dummy data)."

    # ---------------- TIME & DATE ----------------
    elif "time" in msg:
        return datetime.now().strftime("⏰ Current time: %H:%M:%S")

    elif "date" in msg:
        return datetime.now().strftime("📅 Today's date: %d-%m-%Y")

    # ---------------- CALCULATOR ----------------
    elif msg.startswith("calc"):
        try:
            exp = msg.replace("calc", "").strip()
            result = eval(exp)
            return f"🧮 Result: {result}"
        except:
            return "Invalid calculation ❌ Example: calc 10+5"

    # ---------------- STUDY / TECH ----------------
    elif "python" in msg:
        return "Python 🐍 is a high-level, easy & powerful programming language."

    elif "flask" in msg:
        return "Flask 🌐 is a lightweight Python web framework."

    elif "html" in msg:
        return "HTML is used to create webpage structure."

    elif "css" in msg:
        return "CSS is used to style webpages 🎨"

    elif "javascript" in msg:
        return "JavaScript adds interactivity to websites ⚡"

    # ---------------- MOTIVATION ----------------
    elif msg in ["motivate me", "motivation"]:
        return "Believe in yourself 💪 You are capable of amazing things!"

    elif msg in ["i am tired"]:
        return "Take some rest 😴 You deserve it."

    # ---------------- THANKS ----------------
    elif msg in ["thanks", "thank you", "thx"]:
        return "You're welcome 😊 Happy to help!"

    # ---------------- HELP ----------------
    elif msg in ["help", "commands", "what can you do"]:
        return (
            "🤖 I can:\n"
            "• Chat with you\n"
            "• Remember your name\n"
            "• Weather info\n"
            "• Calculator (calc 5+5)\n"
            "• Jokes\n"
            "• Motivation\n"
            "• Voice chat"
        )

    # ---------------- BYE ----------------
    elif msg in ["bye", "exit", "quit", "goodbye"]:
        return f"Goodbye {user}! 👋" if user else "Goodbye! 👋"

    # ---------------- DEFAULT ----------------
    else:
        return "Sorry 😕 I didn't understand that. Try something else!"



# ---------------- SAVE CHAT ----------------
def save_chat(user, bot):
    with open("chat_history.txt", "a", encoding="utf-8") as f:
        time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        f.write(f"[{time}] You: {user}\n")
        f.write(f"[{time}] Bot: {bot}\n\n")

# ---------------- UI ----------------
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>AI Advanced Chatbot</title>
<style>
body{
    background:#0f2027;
    display:flex;
    justify-content:center;
    align-items:center;
    height:100vh;
    font-family:Arial;
}
.chat{
    width:380px;
    background:#111;
    color:#0ff;
    padding:20px;
    border-radius:15px;
    box-shadow:0 0 30px cyan;
}
.msgs{height:280px;overflow:auto;}
.user{color:#0f0;}
.bot{color:#ff0;}
input{width:70%;padding:8px;}
button{padding:8px;background:cyan;border:none;}
.voice{margin-top:5px;}
</style>
</head>

<body>
<div class="chat">
<h3>🤖 AI Advanced Chatbot</h3>
<div class="msgs" id="box"></div>
<input id="msg" placeholder="Type message">
<button onclick="send()">Send</button>
<button class="voice" onclick="voice()">🎤</button>
</div>

<script>
const box = document.getElementById("box");

// AI typing animation
function typeText(text){
    let i=0;
    let p=document.createElement("p");
    p.className="bot";
    box.appendChild(p);
    let t=setInterval(()=>{
        p.innerHTML += text.charAt(i);
        i++;
        box.scrollTop=box.scrollHeight;
        if(i>=text.length) clearInterval(t);
    },30);
}

// Send message
function send(){
    let m=msg.value;
    if(m=="") return;
    box.innerHTML += `<p class='user'>You: ${m}</p>`;
    fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({message:m})})
    .then(r=>r.json())
    .then(d=>{
        typeText("Bot: "+d.reply);
        speak(d.reply);
    });
    msg.value="";
}

// Voice input
function voice(){
    let rec = new webkitSpeechRecognition();
    rec.lang="en-US";
    rec.start();
    rec.onresult = e=>{
        msg.value = e.results[0][0].transcript;
        send();
    }
}

// Voice output
function speak(text){
    let s = new SpeechSynthesisUtterance(text);
    speechSynthesis.speak(s);
}
</script>
</body>
</html>
""")

# ---------------- CHAT API ----------------
@app.route("/chat", methods=["POST"])
def chat():
    user = request.json["message"]
    bot = chatbot_reply(user)
    save_chat(user, bot)
    return jsonify({"reply": bot})

if __name__ == "__main__":
    app.run(debug=True)

