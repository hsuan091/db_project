from flask import Flask, request, render_template, redirect, session, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import random
import time
import os

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "your-secret-key"

# Initialize SQLite
def get_db():
    conn = sqlite3.connect("models.db")
    conn.row_factory = sqlite3.Row
    return conn

# 允許的檔案類型
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Home page
@app.route("/")
def index():
    return render_template("index.html")

# Register page
@app.route("/register")
def show_register():
    return render_template("register.html")

# Register action
@app.route("/signup", methods=["POST"])
def signup():
    name = request.form["name"]
    email = request.form["email"]
    password = generate_password_hash(request.form["password"])

    conn = get_db()
    try:
        conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", 
                    (name, email, password))
        conn.commit()
        flash("註冊成功！請登入")
        return redirect("/login")
    except sqlite3.IntegrityError as e:
        error_msg = str(e)
        if "UNIQUE constraint failed" in error_msg:
            flash("Email 已被註冊")
        elif "CHECK constraint failed" in error_msg:
            flash("Email 格式不正確")
        else:
            flash("註冊失敗，請檢查輸入資料")
        return redirect("/register")
    finally:
        conn.close()

# Login page
@app.route("/login")
def show_login():
    return render_template("login.html")

# Login action
@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user["password"], password):
        session["user"] = user["name"]
        session["user_id"] = user["id"]

        conn = get_db()
        cursor = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user["id"],))
        user_profile = cursor.fetchone()
        conn.close()

        if not user_profile:
            return redirect("/info")
        else:
            return redirect("/chat")  # 登入後直接進入聊天室
    else:
        flash("登入失敗，請檢查帳密")
        return render_template("login.html")

@app.route("/match")
def match():
    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    conn = get_db()

    try:
        cursor = conn.execute("""
            SELECT up.*, GROUP_CONCAT(i.name) as interests
            FROM user_profiles up
            LEFT JOIN user_interests ui ON up.user_id = ui.user_id
            LEFT JOIN interests i ON ui.interest_id = i.id
            WHERE up.user_id = ?
            GROUP BY up.user_id
        """, (user_id,))
        user_profile = cursor.fetchone()

        if not user_profile:
            flash("請先完成個人資料設定，才能進行配對。")
            return redirect("/profile")

        profile_complete = (
            user_profile and
            user_profile["birth_date"] and
            user_profile["birth_month"] and
            user_profile["birth_year"] and
            user_profile["gender"] and
            user_profile["sex_orientation_id"] and
            user_profile["bio"] and
            user_profile["height"] and
            user_profile["interests"] and
            user_profile["mbti"]
        )

        user_mbti = user_profile["mbti"].upper()

        mbti_match_map = {
            "ENFP": ["INFJ", "INTJ"],
            "INFJ": ["ENFP", "ENTP"],
            "INFP": ["ENFJ", "ENTJ"],
            "ENFJ": ["INFP", "ISFP"],
            "ENTP": ["INFJ", "INTP"],
            "INTP": ["ENTP", "ENTJ"],
            "INTJ": ["ENFP", "ENFJ"],
            "ENTJ": ["INFP", "INTP"],
            "ISFP": ["ESFJ", "ENFJ"],
            "ESFJ": ["ISFP", "ISTP"],
            "ESTJ": ["ISTP", "ISFJ"],
            "ISTP": ["ESFJ", "ESTJ"],
            "ISFJ": ["ESFP", "ESTP"],
            "ESFP": ["ISFJ", "ISTJ"],
            "ESTP": ["ISFJ", "ISFP"],
            "ISTJ": ["ESFP", "ENFP"]
        }

        match_mbti_list = mbti_match_map.get(user_mbti, [])

        if not match_mbti_list:
            recommendations = []
        else:
            placeholders = ",".join("?" * len(match_mbti_list))
            query = f"""
                SELECT u.id, u.name, up.*, GROUP_CONCAT(i.name) as interests,
                       (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo
                FROM users u
                JOIN user_profiles up ON u.id = up.user_id
                LEFT JOIN user_interests ui ON up.user_id = ui.user_id
                LEFT JOIN interests i ON ui.interest_id = i.id
                WHERE u.id != ? 
                  AND u.id NOT IN (
                    SELECT to_user_id FROM match_requests WHERE from_user_id = ?
                    UNION
                    SELECT from_user_id FROM match_requests WHERE to_user_id = ?
                  )
                  AND up.mbti IN ({placeholders})
                GROUP BY u.id
            """
            cursor = conn.execute(query, (user_id, user_id, user_id, *match_mbti_list))
            recommendations = cursor.fetchall()

        return render_template("match.html",
                              user_profile=user_profile,
                              recommendations=recommendations)

    finally:
        conn.close()

# Information page
@app.route("/info")
def info():
    if "user" not in session:
        return redirect("/login")
    return render_template("info.html")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("已成功登出")
    return redirect("/")

# 照片相關的路由
@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    if "photo" not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files["photo"]
    if file.filename == "":
        return jsonify({"error": "沒有選擇檔案"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{session['user_id']}_{int(time.time())}_{filename}"
        
        upload_folder = os.path.join('static', 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        photo_url = f"/static/uploads/{unique_filename}"
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO photos (user_id, photo_url, is_profile_photo)
                VALUES (?, ?, ?)
            """, (session["user_id"], photo_url, request.form.get("is_profile_photo", 0)))
            conn.commit()
            
            return jsonify({
                "status": "success",
                "photo_url": photo_url
            }), 200
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

# Chat room routes
@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect("/login")
    user_id = session["user_id"]
    conn = get_db()
    try:
        # 獲取當前用戶名稱
        cursor = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

        # 獲取其他用戶（用於選擇聊天對象）
        cursor = conn.execute("SELECT id, name FROM users WHERE id != ?", (user_id,))
        other_users = cursor.fetchall()

        # 獲取用戶的聊天線程
        cursor = conn.execute("""
            SELECT t.id, t.user_a_id, t.user_b_id, t.last_message_at,
                   (SELECT name FROM users WHERE id = CASE 
                       WHEN t.user_a_id = ? THEN t.user_b_id 
                       ELSE t.user_a_id 
                   END) AS other_user_name
            FROM threads t
            WHERE t.user_a_id = ? OR t.user_b_id = ?
            ORDER BY t.last_message_at DESC
        """, (user_id, user_id, user_id))
        threads = cursor.fetchall()

        # 如果選擇了特定線程，顯示該線程的訊息
        thread_id = request.args.get("thread_id")
        messages = []
        if thread_id:
            cursor = conn.execute("""
                SELECT cm.*, u.name AS sender_name
                FROM chat_messages cm
                JOIN users u ON cm.sender_id = u.id
                WHERE cm.thread_id = ?
                ORDER BY cm.timestamp ASC
            """, (thread_id,))
            messages = cursor.fetchall()

    finally:
        conn.close()
    return render_template("chat.html", user=user["name"], other_users=other_users, threads=threads, messages=messages, selected_thread_id=thread_id)

@app.route("/send_message", methods=["POST"])
def send_message():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401
    data = request.get_json()
    receiver_id = data.get("receiver_id")
    message = data.get("message")

    if not receiver_id or not message:
        return jsonify({"error": "缺少接收者或訊息"}), 400

    conn = get_db()
    try:
        # 檢查是否已存在線程
        cursor = conn.execute("""
            SELECT id FROM threads 
            WHERE (user_a_id = ? AND user_b_id = ?) OR (user_a_id = ? AND user_b_id = ?)
        """, (session["user_id"], receiver_id, receiver_id, session["user_id"]))
        thread = cursor.fetchone()

        if not thread:
            # 創建新線程
            cursor = conn.execute("""
                INSERT INTO threads (user_a_id, user_b_id, last_message_at) 
                VALUES (?, ?, ?)
            """, (session["user_id"], receiver_id, time.time()))
            thread_id = cursor.lastrowid
        else:
            thread_id = thread["id"]
            # 更新最後訊息時間
            conn.execute("UPDATE threads SET last_message_at = ? WHERE id = ?", (time.time(), thread_id))

        # 儲存訊息
        conn.execute("""
            INSERT INTO chat_messages (thread_id, sender_id, message, timestamp)
            VALUES (?, ?, ?, ?)
        """, (thread_id, session["user_id"], message, time.time()))

        conn.commit()
        return jsonify({"status": "success", "thread_id": thread_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 啟動伺服器
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)