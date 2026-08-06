import os
from flask import Flask, render_template

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
# FLASK ROUTE
# ==========================================
@app.route('/')
def home():
    stats = get_system_stats()
    return render_template("index.html", stats=stats)

if __name__ == '__main__':
    # Lấy cổng từ biến môi trường của Render (mặc định 5000 khi chạy local)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
