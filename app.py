from flask import Flask, render_template_string

app = Flask(__name__)

# ==========================================
# HÀM THỐNG KÊ HỆ THỐNG
# ==========================================
def get_system_stats():
    return {
        "active_testers": "30+",
        "tested_players": "1.800+",
        "completed_tests": "5.200+"
    }

# ==========================================
# HTML / CSS / JS TEMPLATE (CINEMATIC ANGEL EDITION)
# ==========================================
# [EXTRACTED] HTML Template -> templates/index.html

# ==========================================
# FLASK ROUTE
# ==========================================
@app.route('/')
def home():
    stats = get_system_stats()
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=False)
