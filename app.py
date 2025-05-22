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
    conn.row_factory = sqlite3.Row #會返回一個類似字典的物件
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
        # 檢查錯誤訊息來區分不同的情況
        error_msg = str(e)
        if "UNIQUE constraint failed" in error_msg:
            flash("Email 已被註冊")
        elif "CHECK constraint failed" in error_msg:
            flash("Email 格式不正確")
        else:
            flash("註冊失敗，請檢查輸入資料")
        return redirect("/register")
    finally: #不管有沒有成功 都要關閉連線
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
    cursor = conn.cursor()  # 創建一個新的游標
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))  # 執行查詢
    user = cursor.fetchone()  # 獲取一行資料
    conn.close()

    if user and check_password_hash(user["password"], password):
        session["user"] = user["name"] #將用戶名稱存入session 就是一個用來記住「誰在使用這個網站」的機制
        session["user_id"] = user["id"]
        flash("登入成功，歡迎 " + user["name"])
        return redirect("/match")
    else:
        flash("登入失敗，請檢查帳密")
        return redirect("/login")

# Match page
@app.route("/match")
def match():
    if "user" not in session: #如果沒有登入 就會被導到登入頁面
        return redirect("/login")

    user_id = session["user_id"]
    conn = get_db()
    
    try:
        # 獲取當前用戶資料
        cursor = conn.execute("""
            SELECT up.*, GROUP_CONCAT(i.name) as interests
            FROM user_profiles up
            LEFT JOIN user_interests ui ON up.user_id = ui.user_id
            LEFT JOIN interests i ON ui.interest_id = i.id
            WHERE up.user_id = ?
            GROUP BY up.user_id
        """, (user_id,)) #將所有興趣名稱合併成一個字串
        user_profile = cursor.fetchone()

        profile_complete = (
            user_profile and
            user_profile["birth_date"] and
            user_profile["birth_month"] and
            user_profile["birth_year"] and
            user_profile["gender"] and
            user_profile["sex_orientation_id"] and
            user_profile["bio"] and
            user_profile["height"] and
            user_profile["interests"]
        )

        # 獲取推薦用戶
        cursor = conn.execute("""
            SELECT u.id, u.name, up.*, GROUP_CONCAT(i.name) as interests,
                   (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo
            FROM users u
            JOIN user_profiles up ON u.id = up.user_id
            LEFT JOIN user_interests ui ON up.user_id = ui.user_id
            LEFT JOIN interests i ON ui.interest_id = i.id
            WHERE u.id != ? AND u.id NOT IN (
                SELECT to_user_id FROM match_requests WHERE from_user_id = ?
                UNION
                SELECT from_user_id FROM match_requests WHERE to_user_id = ?
            )
            GROUP BY u.id
        """, (user_id, user_id, user_id))
        
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
        
        # 確保上傳目錄存在
        upload_folder = os.path.join('static', 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        # 儲存檔案
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # 儲存到資料庫
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

    return jsonify({"error": "不支援的檔案類型"}), 400

@app.route("/get_photos")
def get_photos():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    conn = get_db()
    try:
        cursor = conn.execute("""
            SELECT photo_url, upload_date, is_profile_photo
            FROM photos
            WHERE user_id = ?
            ORDER BY upload_date DESC
        """, (session["user_id"],))
        
        photos = [{
            "url": row["photo_url"],
            "upload_date": row["upload_date"],
            "is_profile_photo": bool(row["is_profile_photo"])
        } for row in cursor.fetchall()]
        
        return jsonify({"photos": photos}), 200
    finally:
        conn.close()

@app.route("/delete_photo", methods=["POST"])
def delete_photo():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    photo_url = data.get("photo_url")
    
    if not photo_url:
        return jsonify({"error": "沒有指定照片"}), 400

    conn = get_db()
    try:
        conn.execute("""
            DELETE FROM photos
            WHERE user_id = ? AND photo_url = ?
        """, (session["user_id"], photo_url))
        conn.commit()

        # 從本地檔案系統刪除檔案
        if photo_url.startswith('/static/uploads/'):
            file_path = os.path.join('static', 'uploads', os.path.basename(photo_url))
            if os.path.exists(file_path):
                os.remove(file_path)

        return jsonify({"status": "success"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route("/set_profile_photo", methods=["POST"])
def set_profile_photo():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    photo_url = data.get("photo_url")
    
    if not photo_url:
        return jsonify({"error": "沒有指定照片"}), 400

    conn = get_db()
    try:
        # 先將所有照片設為非個人照片
        conn.execute("""
            UPDATE photos
            SET is_profile_photo = 0
            WHERE user_id = ?
        """, (session["user_id"],))
        
        # 將選定的照片設為個人照片
        conn.execute("""
            UPDATE photos
            SET is_profile_photo = 1
            WHERE user_id = ? AND photo_url = ?
        """, (session["user_id"], photo_url))
        
        conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 配對請求相關路由
@app.route("/send_match_request", methods=["POST"])
def send_match_request():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    to_user_id = data.get("to_user_id")
    
    if not to_user_id:
        return jsonify({"error": "沒有指定用戶"}), 400

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO match_requests (from_user_id, to_user_id)
            VALUES (?, ?)
        """, (session["user_id"], to_user_id))
        conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route("/respond_match_request", methods=["POST"])
def respond_match_request():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    request_id = data.get("request_id")
    status = data.get("status")
    
    if not request_id or status not in ["accepted", "rejected"]:
        return jsonify({"error": "無效的請求"}), 400

    conn = get_db()
    try:
        # 更新配對請求狀態
        conn.execute("""
            UPDATE match_requests
            SET status = ?
            WHERE id = ? AND to_user_id = ?
        """, (status, request_id, session["user_id"]))
        
        # 如果接受配對，創建聊天執行緒
        if status == "accepted":
            cursor = conn.execute("""
                SELECT from_user_id FROM match_requests WHERE id = ?
            """, (request_id,))
            from_user_id = cursor.fetchone()[0]
            
            conn.execute("""
                INSERT INTO threads (user_a_id, user_b_id)
                VALUES (?, ?)
            """, (min(session["user_id"], from_user_id), 
                  max(session["user_id"], from_user_id)))
        
        conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 訊息相關路由
@app.route("/get_threads")
def get_threads():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    conn = get_db()
    try:
        cursor = conn.execute("""
            SELECT t.*, 
                   u.name as other_user_name,
                   (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as other_user_photo,
                   (SELECT text FROM messages WHERE thread_id = t.id ORDER BY timestamp DESC LIMIT 1) as last_message,
                   (SELECT timestamp FROM messages WHERE thread_id = t.id ORDER BY timestamp DESC LIMIT 1) as last_message_time
            FROM threads t
            JOIN users u ON (u.id = CASE 
                WHEN t.user_a_id = ? THEN t.user_b_id 
                ELSE t.user_a_id 
            END)
            WHERE t.user_a_id = ? OR t.user_b_id = ?
            ORDER BY last_message_time DESC
        """, (session["user_id"], session["user_id"], session["user_id"]))
        
        threads = [{
            "id": row["id"],
            "other_user_name": row["other_user_name"],
            "other_user_photo": row["other_user_photo"],
            "last_message": row["last_message"],
            "last_message_time": row["last_message_time"]
        } for row in cursor.fetchall()]
        
        return jsonify({"threads": threads}), 200
    finally:
        conn.close()

@app.route("/get_messages/<int:thread_id>")
def get_messages(thread_id):
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    conn = get_db()
    try:
        # 確認用戶有權限訪問這個執行緒
        cursor = conn.execute("""
            SELECT 1 FROM threads
            WHERE id = ? AND (user_a_id = ? OR user_b_id = ?)
        """, (thread_id, session["user_id"], session["user_id"]))
        
        if not cursor.fetchone():
            return jsonify({"error": "無權訪問"}), 403

        cursor = conn.execute("""
            SELECT m.*, u.name as sender_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.thread_id = ?
            ORDER BY m.timestamp ASC
        """, (thread_id,))
        
        messages = [{
            "id": row["id"],
            "text": row["text"],
            "sender_id": row["sender_id"],
            "sender_name": row["sender_name"],
            "timestamp": row["timestamp"]
        } for row in cursor.fetchall()]
        
        return jsonify({"messages": messages}), 200
    finally:
        conn.close()

@app.route("/send_message", methods=["POST"])
def send_message():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    chat_room_id = data.get("chat_room_id")
    content = data.get("content")
    
    if not chat_room_id or not content:
        return jsonify({"error": "缺少必要資訊"}), 400

    conn = get_db()
    try:
        # 確認用戶有權限發送訊息
        cursor = conn.execute("""
            SELECT user_a_id, user_b_id FROM chat_rooms
            WHERE id = ?
        """, (chat_room_id,))
        chat_room = cursor.fetchone()
        
        if not chat_room:
            return jsonify({"error": "聊天室不存在"}), 404
        
        if session["user_id"] not in [chat_room["user_a_id"], chat_room["user_b_id"]]:
            return jsonify({"error": "無權發送訊息"}), 403
        
        # 更新最後訊息時間
        conn.execute("""
            UPDATE chat_rooms
            SET last_message_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (chat_room_id,))
        
        # 插入新訊息
        conn.execute("""
            INSERT INTO messages (chat_room_id, sender_id, content)
            VALUES (?, ?, ?)
        """, (chat_room_id, session["user_id"], content))
        
        conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route("/save_profile", methods=["POST"])
def save_profile():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少資料"}), 400

    conn = get_db()
    try:
        # 更新 user_profiles
        conn.execute("""
            INSERT OR REPLACE INTO user_profiles 
            (user_id, birth_date, birth_month, birth_year, gender, sex_orientation_id, bio, height, music_genre_id, mbti)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            data.get("birth_date"),
            data.get("birth_month"),
            data.get("birth_year"),
            data.get("gender"),
            data.get("sex_orientation_id"),
            data.get("bio"),
            data.get("height"),
            data.get("music_genre_id"),
            data.get("mbti")
        ))

        # 處理興趣
        if data.get("interests"):
            conn.execute("DELETE FROM user_interests WHERE user_id = ?", (session["user_id"],))
            for interest in data.get("interests"):
                conn.execute("INSERT OR IGNORE INTO interests (name) VALUES (?)", (interest,))
                cursor = conn.execute("SELECT id FROM interests WHERE name = ?", (interest,))
                interest_id = cursor.fetchone()[0]
                conn.execute("INSERT INTO user_interests (user_id, interest_id) VALUES (?, ?)", (session["user_id"], interest_id))

        # 更新姓名（users 表）
        if data.get("name"):
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (data.get("name"), session["user_id"]))

        conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)