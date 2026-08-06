import os
import json
import time
import uuid
import threading
from flask import Flask, render_template, request, session, jsonify, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "doi-key-nay-truoc-khi-deploy-that")

# ==========================================
# CẤU HÌNH BẢO MẬT (server-side only — KHÔNG bao giờ gửi các giá trị này ra frontend)
# ==========================================
# Đáp án của từng lớp được kiểm tra ở server. Trình duyệt chỉ nhận biết
# "đúng"/"sai" cho từng bước, không bao giờ thấy được đáp án thật.
# Nên chuyển các giá trị này sang biến môi trường khi deploy thật.
LAYER_ANSWERS = {
    1: os.environ.get(
        "LAYER1_ANSWER",
        "mipbeo02082898183972992846782648678238236747848626874678274828674687248727846782648726784682746872684736782368747827842830492-4928490278040248072",
    ),
    2: os.environ.get(
        "LAYER2_ANSWER",
        "3.14159265358979323846264338327950288419716939937510"
        "58209749445923078164062862089986280348253421170679"
        "82148086513282306647093844609550582231725359408128"
        "48111745028410270193852110555964462294895493038196"
        "44288109756659334461284756482337867831652712019091"
        "45648566923460348610454326648213393607260249141273"
        "72458700660631558817488152092096282925409171536436"
        "78925903600113305305488204665213841469519415116094"
        "33057270365759591953092186117381932611793105118548"
        "07446237996274956735188575272489122793818301194912",
    ),
    # Lớp 3 chỉ yêu cầu kết quả cuối cùng của biểu thức, đề đã nói kết quả = 0
    3: os.environ.get("LAYER3_ANSWER", "0"),
    # Lớp 4: đáp án nhạy cảm nhất — LUÔN đọc từ biến môi trường khi deploy thật,
    # không nên để webhook thật nằm cứng trong mã nguồn commit lên git công khai.
    4: os.environ.get(
        "LAYER4_ANSWER",
        "https://discord.com/api/webhooks/1533666984867270696/g6UmiB6KgOZU3jgpjGuUcN-iR32G26RJfEkeNEAE-ssF-HSUzdg8gQ4qtlUkMntYhSks",
    ),
}
TOTAL_LAYERS = 4

# ==========================================
# THEO DÕI LƯỢT TRUY CẬP THEO THỜI GIAN THỰC
# ==========================================
# Lưu tạm trong RAM: {session_id: last_seen_timestamp}
_visitors_lock = threading.Lock()
_active_visitors = {}
ONLINE_WINDOW_SECONDS = 45  # coi là "đang online" nếu ping trong khoảng này

_stats_lock = threading.Lock()
_visit_counter_path = os.path.join(os.path.dirname(__file__), "data", "visit_counter.json")


def _load_total_visits():
    try:
        with open(_visit_counter_path, "r", encoding="utf-8") as f:
            return json.load(f).get("total_visits", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def _save_total_visits(value):
    with open(_visit_counter_path, "w", encoding="utf-8") as f:
        json.dump({"total_visits": value}, f)


def _touch_visitor():
    if "visitor_id" not in session:
        session["visitor_id"] = str(uuid.uuid4())
        with _stats_lock:
            total = _load_total_visits() + 1
            _save_total_visits(total)
    with _visitors_lock:
        _active_visitors[session["visitor_id"]] = time.time()


def _count_online():
    now = time.time()
    with _visitors_lock:
        stale = [vid for vid, ts in _active_visitors.items() if now - ts > ONLINE_WINDOW_SECONDS]
        for vid in stale:
            del _active_visitors[vid]
        return len(_active_visitors)


# ==========================================
# DỮ LIỆU NGƯỜI CHƠI (lưu ra file JSON -> sập server vẫn còn dữ liệu)
# ==========================================
PLAYERS_PATH = os.path.join(os.path.dirname(__file__), "data", "players.json")


def load_players():
    try:
        with open(PLAYERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_players(players):
    with open(PLAYERS_PATH, "w", encoding="utf-8") as f:
        json.dump(players, f, ensure_ascii=False, indent=2)


# ==========================================
# HÀM THỐNG KÊ HỆ THỐNG (giữ nguyên như bản gốc)
# ==========================================
def get_system_stats():
    return {
        "active_testers": "30+",
        "tested_players": "1.800+",
        "completed_tests": "5.200+",
    }


# ==========================================
# ROUTES
# ==========================================
@app.route("/")
def home():
    _touch_visitor()
    stats = get_system_stats()
    return render_template("index.html", stats=stats)


@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    """Trình duyệt gọi định kỳ để giữ trạng thái 'đang online'."""
    _touch_visitor()
    return jsonify({"online": _count_online()})


@app.route("/api/unlock/step", methods=["POST"])
def unlock_step():
    """Kiểm tra từng lớp một — chỉ trả về đúng/sai, không bao giờ trả đáp án thật."""
    data = request.get_json(silent=True) or {}
    step = data.get("step")
    answer = (data.get("answer") or "").strip()

    if step not in (1, 2, 3, 4):
        return jsonify({"ok": False, "error": "invalid_step"}), 400

    progress = session.get("unlock_progress", 0)
    # Chỉ cho phép trả lời đúng thứ tự lớp hiện tại
    if step != progress + 1:
        return jsonify({"ok": False, "error": "out_of_order"}), 400

    expected = str(LAYER_ANSWERS[step]).strip()
    correct = answer.replace(" ", "") == expected.replace(" ", "") if step in (2,) else answer == expected

    if not correct:
        return jsonify({"ok": False, "passed": False})

    session["unlock_progress"] = step
    if step == TOTAL_LAYERS:
        session["is_tech"] = True

    return jsonify({"ok": True, "passed": True, "unlocked": session.get("is_tech", False)})


@app.route("/api/unlock/reset", methods=["POST"])
def unlock_reset():
    session.pop("unlock_progress", None)
    session.pop("is_tech", None)
    return jsonify({"ok": True})


@app.route("/admin")
def admin():
    if not session.get("is_tech"):
        return redirect(url_for("home"))
    return render_template("admin.html")


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_tech", None)
    session.pop("unlock_progress", None)
    return jsonify({"ok": True})


@app.route("/api/players", methods=["GET"])
def get_players():
    return jsonify(load_players())


@app.route("/api/players", methods=["POST"])
def set_players():
    if not session.get("is_tech"):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    data = request.get_json(silent=True) or {}
    players = data.get("players")
    if not isinstance(players, list):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400
    save_players(players)
    return jsonify({"ok": True, "count": len(players)})


@app.route("/api/admin/stats")
def admin_stats():
    if not session.get("is_tech"):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    return jsonify({
        "ok": True,
        "online_now": _count_online(),
        "total_visits": _load_total_visits(),
        "players_count": len(load_players()),
    })


if __name__ == "__main__":
    os.makedirs(os.path.dirname(PLAYERS_PATH), exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
