from flask import Flask, render_template_string, request, session
import random

app = Flask(__name__)
app.secret_key = "neon_hangman_secret"

WORDS = ["python", "coding", "alpha", "hangman", "program"]
MAX_WRONG = 6

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Neon Hangman Game</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        body {
            margin: 0;
            font-family: 'Segoe UI', sans-serif;
            background: radial-gradient(circle at top, #0f2027, #203a43, #2c5364);
            color: #fff;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }

        .card {
            background: rgba(0,0,0,0.6);
            width: 90%;
            max-width: 420px;
            padding: 25px;
            border-radius: 20px;
            box-shadow: 0 0 25px #00ffe1;
            text-align: center;
        }

        h1 {
            color: #00ffe1;
            text-shadow: 0 0 15px #00ffe1;
        }

        .word {
            font-size: 32px;
            letter-spacing: 10px;
            margin: 20px 0;
        }

        input {
            padding: 10px;
            width: 60px;
            text-align: center;
            font-size: 20px;
            border-radius: 10px;
            border: none;
            outline: none;
        }

        button {
            padding: 10px 18px;
            margin-top: 10px;
            font-size: 16px;
            border-radius: 12px;
            border: none;
            cursor: pointer;
            background: #00ffe1;
            box-shadow: 0 0 15px #00ffe1;
        }

        button:hover {
            transform: scale(1.05);
        }

        .info {
            margin-top: 15px;
            font-size: 14px;
        }

        @media (max-width: 480px) {
            .word {
                font-size: 26px;
                letter-spacing: 6px;
            }
        }
    </style>
</head>
<body>

<div class="card">
    <h1>🎮 Hangman</h1>

    <div class="word">{{ display_word }}</div>

    <div class="info">
        ❌ Wrong Attempts: {{ wrong }}/6 <br>
        ⭐ Score: {{ score }}
    </div>

    {% if message %}
        <p>{{ message }}</p>
    {% endif %}

    {% if not game_over %}
    <form method="post" onsubmit="playClick()">
        <input type="text" name="letter" maxlength="1" required>
        <br>
        <button type="submit">Guess</button>
    </form>
    {% else %}
        <button onclick="playEnd(); location.href='/'">Restart</button>
    {% endif %}
</div>

<!-- Sound Effects -->
<audio id="click" src="https://www.soundjay.com/buttons/sounds/button-16.mp3"></audio>
<audio id="win" src="https://www.soundjay.com/misc/sounds/bell-ringing-05.mp3"></audio>
<audio id="lose" src="https://www.soundjay.com/misc/sounds/fail-buzzer-02.mp3"></audio>

<script>
function playClick() {
    document.getElementById("click").play();
}
function playEnd() {
    {% if win %}
        document.getElementById("win").play();
    {% else %}
        document.getElementById("lose").play();
    {% endif %}
}
</script>

</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def game():
    if "word" not in session:
        session["word"] = random.choice(WORDS)
        session["guessed"] = []
        session["wrong"] = 0
        session["score"] = 0

    word = session["word"]
    guessed = session["guessed"]
    wrong = session["wrong"]
    score = session["score"]

    message = ""
    game_over = False
    win = False

    if request.method == "POST":
        letter = request.form["letter"].lower()

        if letter in guessed:
            message = "⚠️ Letter already guessed"
        elif letter in word:
            guessed.append(letter)
            session["score"] += 10
            message = "✅ Correct!"
        else:
            guessed.append(letter)
            session["wrong"] += 1
            session["score"] -= 5
            message = "❌ Wrong!"

    display_word = " ".join([c if c in guessed else "_" for c in word])

    if "_" not in display_word:
        message = "🎉 YOU WON! Word: " + word
        game_over = True
        win = True
        session.clear()

    if session.get("wrong", 0) >= MAX_WRONG:
        message = "💀 GAME OVER! Word: " + word
        game_over = True
        win = False
        session.clear()

    return render_template_string(
        HTML,
        display_word=display_word,
        wrong=wrong,
        score=score,
        message=message,
        game_over=game_over,
        win=win
    )

if __name__ == "__main__":
    app.run(debug=True)


