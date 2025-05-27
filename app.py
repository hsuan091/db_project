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

# 添加時間格式化過濾器
@app.template_filter('datetime')
def format_datetime(timestamp):
    if not timestamp:
        return ""
    from datetime import datetime
    try:
        # 如果是字串格式，直接解析
        if isinstance(timestamp, str):
            return timestamp
        # 如果是數字格式，轉換為日期時間
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
    except:
        return str(timestamp)

# Initialize SQLite
def get_db():
    conn = sqlite3.connect("models.db")
    conn.row_factory = sqlite3.Row
    return conn

# 創建好友邀請表
def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_user_id) REFERENCES users (id),
            FOREIGN KEY (to_user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()

# 在應用啟動時初始化資料庫
with app.app_context():
    init_db()

# 允許的檔案類型
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Home page
@app.route("/")
def index():
    has_profile = False
    if "user" in session:
        conn = get_db()
        try:
            cursor = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (session["user_id"],))
            user_profile = cursor.fetchone()
            has_profile = user_profile is not None
        finally:
            conn.close()
    return render_template("index.html", has_profile=has_profile)

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
        flash(f"歡迎回來，{user['name']}！")
        return redirect("/")  # 登入成功後重定向到首頁
    else:
        flash("登入失敗，請檢查帳密")
        return redirect("/login")

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
            return redirect("/info")

        profile_complete = bool(
            user_profile and
            user_profile["name"] and
            user_profile["birth_date"] and
            user_profile["birth_month"] and
            user_profile["birth_year"] and
            user_profile["gender"] and
            user_profile["sex_orientation_id"] and
            user_profile["height"] and
            user_profile["music_genre_id"]
        )

        user_mbti = user_profile["mbti"].upper() if user_profile["mbti"] else ""

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

        # 獲取已經是好友的用戶ID列表
        cursor = conn.execute("""
            SELECT 
                CASE 
                    WHEN fr.from_user_id = ? THEN fr.to_user_id
                    ELSE fr.from_user_id 
                END as friend_id
            FROM friend_requests fr
            WHERE (fr.from_user_id = ? OR fr.to_user_id = ?)
            AND fr.status = 'accept'
        """, (user_id, user_id, user_id))
        friend_ids = [row['friend_id'] for row in cursor.fetchall()]

        # 獲取已發送但待處理的邀請的用戶ID列表
        cursor = conn.execute("""
            SELECT to_user_id
            FROM friend_requests
            WHERE from_user_id = ? AND status = 'pending'
        """, (user_id,))
        pending_request_ids = [row['to_user_id'] for row in cursor.fetchall()]

        # 基本查詢模板
        base_query = """
            SELECT u.id, u.name, up.*, 
                   (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo,
                   GROUP_CONCAT(i.name) as interests,
                   CASE 
                       WHEN u.id IN ({}) THEN 'friend'
                       WHEN u.id IN ({}) THEN 'pending'
                       ELSE 'none'
                   END as relationship_status
            FROM users u
            JOIN user_profiles up ON u.id = up.user_id
            LEFT JOIN user_interests ui ON up.user_id = ui.user_id
            LEFT JOIN interests i ON ui.interest_id = i.id
            WHERE u.id != ?
        """

        # 準備 friend_ids 和 pending_request_ids 的 SQL 片段
        friend_ids_sql = ','.join(['?' for _ in friend_ids]) or 'NULL'
        pending_ids_sql = ','.join(['?' for _ in pending_request_ids]) or 'NULL'
        
        # 獲取 MBTI 匹配的用戶
        mbti_recommendations = []
        if user_mbti and match_mbti_list:
            mbti_query = base_query.format(friend_ids_sql, pending_ids_sql) + " AND up.mbti IN ({}) GROUP BY u.id".format(
                ",".join("?" * len(match_mbti_list))
            )
            params = friend_ids + pending_request_ids + [user_id] + match_mbti_list
            cursor = conn.execute(mbti_query, params)
            mbti_recommendations = cursor.fetchall()

        # 獲取所有其他用戶（排除已經在 MBTI 匹配中的用戶）
        other_users_query = base_query.format(friend_ids_sql, pending_ids_sql)
        if mbti_recommendations:
            other_users_query += " AND u.id NOT IN ({})".format(
                ",".join(str(rec["id"]) for rec in mbti_recommendations)
            )
        other_users_query += " GROUP BY u.id"
        params = friend_ids + pending_request_ids + [user_id]
        cursor = conn.execute(other_users_query, params)
        other_recommendations = cursor.fetchall()

        return render_template("match.html",
                            user_profile=user_profile,
                            mbti_recommendations=mbti_recommendations,
                            other_recommendations=other_recommendations,
                            profile_complete=profile_complete,
                            user_mbti=user_mbti)

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

# 新增獲取頭像路由
@app.route("/get_profile_photo")
def get_profile_photo():
    if "user_id" not in session:
        return jsonify({"error": "未登入", "photo_url": None}), 401

    conn = get_db()
    try:
        cursor = conn.execute("""
            SELECT photo_url 
            FROM photos 
            WHERE user_id = ? AND is_profile_photo = 1 
            LIMIT 1
        """, (session["user_id"],))
        photo = cursor.fetchone()
        return jsonify({"photo_url": photo["photo_url"] if photo else None})
    finally:
        conn.close()
@app.route("/save_profile", methods=["POST"])
def save_profile():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "無效的請求數據"}), 400

    name = data.get("name")
    birth_year = data.get("birth_year")
    birth_month = data.get("birth_month")
    birth_date = data.get("birth_date")
    gender = data.get("gender")
    sex_orientation_id = data.get("sex_orientation_id")
    height = data.get("height")
    bio = data.get("bio")
    interests = data.get("interests", [])
    music_genre_id = data.get("music_genre_id")
    mbti = data.get("mbti")
    # photo_url = data.get("photo_url")  # 目前不需要，因為 photo_url 已經在 /upload_photo 中處理

    if not all([name, birth_year, birth_month, birth_date, gender, sex_orientation_id, height, music_genre_id]):
        return jsonify({"error": "缺少必填欄位"}), 400

    conn = get_db()
    try:
        # 檢查 user_profiles 是否已存在
        cursor = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (session["user_id"],))
        user_profile = cursor.fetchone()

        if user_profile:
            # 更新現有資料
            conn.execute("""
                UPDATE user_profiles 
                SET name = ?, birth_year = ?, birth_month = ?, birth_date = ?, 
                    gender = ?, sex_orientation_id = ?, height = ?, bio = ?, 
                    interests = ?, music_genre_id = ?, mbti = ?
                WHERE user_id = ?
            """, (name, birth_year, birth_month, birth_date, gender, sex_orientation_id, height, bio, 
                  ",".join(interests) if interests else "", music_genre_id, mbti, session["user_id"]))
        else:
            # 插入新資料
            conn.execute("""
                INSERT INTO user_profiles (user_id, name, birth_year, birth_month, birth_date, 
                    gender, sex_orientation_id, height, bio, interests, music_genre_id, mbti)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session["user_id"], name, birth_year, birth_month, birth_date, gender, 
                  sex_orientation_id, height, bio, ",".join(interests) if interests else "", 
                  music_genre_id, mbti))

        conn.commit()
        return jsonify({"status": "success"})
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return jsonify({"error": f"資料庫錯誤: {str(e)}"}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"儲存失敗: {str(e)}"}), 500
    finally:
        conn.close()

# 新增獲取用戶資料路由
@app.route("/get_user_profile")
def get_user_profile():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    conn = get_db()
    try:
        cursor = conn.execute("""
            SELECT up.*, GROUP_CONCAT(i.name) as interests
            FROM user_profiles up
            LEFT JOIN user_interests ui ON up.user_id = ui.user_id
            LEFT JOIN interests i ON ui.interest_id = i.id
            WHERE up.user_id = ?
            GROUP BY up.user_id
        """, (session["user_id"],))
        profile = cursor.fetchone()
        
        if profile:
            return jsonify({
                "name": profile["name"],
                "birth_year": profile["birth_year"],
                "birth_month": profile["birth_month"],
                "birth_date": profile["birth_date"],
                "gender": profile["gender"],
                "sex_orientation_id": profile["sex_orientation_id"],
                "height": profile["height"],
                "bio": profile["bio"],
                "interests": profile["interests"].split(",") if profile["interests"] else [],
                "music_genre_id": profile["music_genre_id"],
                "mbti": profile["mbti"]
            })
        return jsonify({}), 200
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
        # 檢查用戶是否已填寫個人資料
        cursor = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        user_profile = cursor.fetchone()
        
        if not user_profile:
            flash("請先完成個人資料設定，才能使用聊天功能。")
            return redirect("/info")

        # 獲取當前用戶名稱
        cursor = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

        # 獲取好友列表（已接受的好友邀請）
        cursor = conn.execute("""
            SELECT DISTINCT 
                CASE 
                    WHEN fr.from_user_id = ? THEN fr.to_user_id
                    ELSE fr.from_user_id 
                END as friend_id,
                u.name as friend_name,
                u.email as friend_email
            FROM friend_requests fr
            JOIN users u ON u.id = CASE 
                WHEN fr.from_user_id = ? THEN fr.to_user_id
                ELSE fr.from_user_id 
            END
            WHERE (fr.from_user_id = ? OR fr.to_user_id = ?)
            AND fr.status = 'accept'
        """, (user_id, user_id, user_id, user_id))
        friends = cursor.fetchall()

        # 獲取與好友的聊天線程
        threads = []
        if friends:
            friend_ids = [friend['friend_id'] for friend in friends]
            placeholders = ','.join('?' * len(friend_ids))
            cursor = conn.execute(f"""
                SELECT t.id, t.user_a_id, t.user_b_id, t.last_message_at,
                       (SELECT name FROM users WHERE id = CASE 
                           WHEN t.user_a_id = ? THEN t.user_b_id 
                           ELSE t.user_a_id 
                       END) AS other_user_name
                FROM threads t
                WHERE (t.user_a_id = ? AND t.user_b_id IN ({placeholders}))
                   OR (t.user_b_id = ? AND t.user_a_id IN ({placeholders}))
                ORDER BY t.last_message_at DESC
            """, [user_id, user_id] + friend_ids + [user_id] + friend_ids)
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
    return render_template("chat.html", 
                         user=user["name"], 
                         friends=friends,
                         threads=threads, 
                         messages=messages, 
                         selected_thread_id=thread_id)

@app.route("/send_message", methods=["POST"])
def send_message():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    receiver_id = data.get("receiver_id")
    message = data.get("message")
    thread_id = data.get("thread_id")

    if not message:
        return jsonify({"error": "缺少訊息內容"}), 400

    conn = get_db()
    try:
        if thread_id:
            # 如果提供了 thread_id，檢查該線程是否存在
            cursor = conn.execute("""
                SELECT id, user_a_id, user_b_id 
                FROM threads 
                WHERE id = ?
            """, (thread_id,))
            thread = cursor.fetchone()

            if not thread:
                return jsonify({"error": "指定的聊天線程不存在"}), 404

            # 驗證當前用戶是否屬於該線程
            if session["user_id"] not in (thread["user_a_id"], thread["user_b_id"]):
                return jsonify({"error": "你無權在該聊天中發送訊息"}), 403

            # 更新最後訊息時間
            conn.execute("UPDATE threads SET last_message_at = ? WHERE id = ?", (time.time(), thread_id))

        else:
            # 如果沒有 thread_id，則需要 receiver_id 來創建新線程
            if not receiver_id:
                return jsonify({"error": "缺少接收者ID或聊天線程ID"}), 400

            # 檢查 receiver_id 是否為當前用戶的好友
            cursor = conn.execute("""
                SELECT * FROM friend_requests 
                WHERE ((from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?))
                AND status = 'accept'
            """, (session["user_id"], receiver_id, receiver_id, session["user_id"]))
            if not cursor.fetchone():
                return jsonify({"error": "只能與好友開始聊天"}), 403

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
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return jsonify({"error": f"資料庫錯誤: {str(e)}"}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"儲存失敗: {str(e)}"}), 500
    finally:
        conn.close()

# 發送好友邀請
@app.route("/send_friend_request", methods=["POST"])
def send_friend_request():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401
    
    data = request.get_json()
    to_user_id = data.get("to_user_id")
    
    if not to_user_id:
        return jsonify({"error": "缺少接收者ID"}), 400
        
    conn = get_db()
    try:
        # 檢查是否已經發送過邀請
        cursor = conn.execute("""
            SELECT * FROM friend_requests 
            WHERE from_user_id = ? AND to_user_id = ?
        """, (session["user_id"], to_user_id))
        existing_request = cursor.fetchone()
        
        if existing_request:
            return jsonify({"error": "已經發送過邀請了"}), 400
            
        # 檢查對方是否已經發送邀請給我
        cursor = conn.execute("""
            SELECT id FROM friend_requests 
            WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'
        """, (to_user_id, session["user_id"]))
        other_request = cursor.fetchone()
        
        if other_request:
            # 如果對方已經發送邀請，則自動接受對方的邀請
            conn.execute("""
                UPDATE friend_requests 
                SET status = 'accept' 
                WHERE id = ?
            """, (other_request["id"],))
            conn.commit()
            return jsonify({
                "status": "success", 
                "message": "已自動接受對方的好友邀請",
                "is_mutual": True
            })
            
        # 發送新邀請
        conn.execute("""
            INSERT INTO friend_requests (from_user_id, to_user_id, status, created_at)
            VALUES (?, ?, 'pending', DATETIME('now', 'localtime'))
        """, (session["user_id"], to_user_id))
        conn.commit()
        return jsonify({"status": "success", "message": "邀請已發送"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 通知頁面
@app.route("/notifications")
def notifications():
    if "user" not in session:
        return redirect("/login")
        
    conn = get_db()
    try:
        # 獲取已發送的邀請及其狀態
        cursor = conn.execute("""
            SELECT fr.id, fr.created_at, fr.status,
                   u.name as to_user_name, u.id as to_user_id,
                   up.birth_year, up.gender, up.height, up.bio, up.mbti,
                   (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo
            FROM friend_requests fr
            JOIN users u ON fr.to_user_id = u.id
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE fr.from_user_id = ?
            AND NOT EXISTS (
                -- 排除已互相接受的邀請
                SELECT 1 FROM friend_requests fr2
                WHERE fr2.from_user_id = fr.to_user_id
                AND fr2.to_user_id = fr.from_user_id
                AND fr2.status = 'accept'
                AND fr.status = 'accept'
            )
            ORDER BY 
                CASE fr.status 
                    WHEN 'pending' THEN 1 
                    WHEN 'accept' THEN 2 
                    WHEN 'reject' THEN 3 
                END,
                fr.created_at DESC
        """, (session["user_id"],))
        sent_requests = cursor.fetchall()
        
        # 獲取收到的邀請（包括待處理的）
        cursor = conn.execute("""
            SELECT fr.id, fr.created_at, fr.status,
                   u.name as from_user_name, u.id as from_user_id,
                   up.birth_year, up.gender, up.height, up.bio, up.mbti,
                   (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo
            FROM friend_requests fr
            JOIN users u ON fr.from_user_id = u.id
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE fr.to_user_id = ?
            AND (
                fr.status = 'pending'  -- 顯示所有待處理的邀請
                OR (
                    fr.status IN ('accept', 'reject')
                    AND NOT EXISTS (  -- 對於已處理的邀請，排除已互相接受的情況
                        SELECT 1 FROM friend_requests fr2
                        WHERE fr2.from_user_id = fr.to_user_id
                        AND fr2.to_user_id = fr.from_user_id
                        AND fr2.status = 'accept'
                        AND fr.status = 'accept'
                    )
                )
            )
            ORDER BY 
                CASE fr.status 
                    WHEN 'pending' THEN 1 
                    WHEN 'accept' THEN 2 
                    WHEN 'reject' THEN 3 
                END,
                fr.created_at DESC
        """, (session["user_id"],))
        received_requests = cursor.fetchall()

        # 獲取已成為好友的用戶（只顯示最新的一條記錄）
        cursor = conn.execute("""
            SELECT 
                fr.id, fr.created_at, fr.status,
                u.name as friend_name, u.id as friend_id,
                up.birth_year, up.gender, up.height, up.bio, up.mbti,
                (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo
            FROM friend_requests fr
            JOIN users u ON u.id = CASE 
                WHEN fr.from_user_id = ? THEN fr.to_user_id
                ELSE fr.from_user_id
            END
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE fr.status = 'accept'
            AND EXISTS (
                SELECT 1 FROM friend_requests fr2
                WHERE fr2.from_user_id = fr.to_user_id
                AND fr2.to_user_id = fr.from_user_id
                AND fr2.status = 'accept'
            )
            AND (fr.from_user_id = ? OR fr.to_user_id = ?)
            AND fr.created_at >= (
                SELECT created_at FROM friend_requests fr2
                WHERE ((fr2.from_user_id = fr.from_user_id AND fr2.to_user_id = fr.to_user_id)
                   OR (fr2.from_user_id = fr.to_user_id AND fr2.to_user_id = fr.from_user_id))
                AND fr2.status = 'accept'
                ORDER BY created_at DESC
                LIMIT 1
            )
            GROUP BY CASE 
                WHEN fr.from_user_id = ? THEN fr.to_user_id
                ELSE fr.from_user_id
            END
            ORDER BY fr.created_at DESC
        """, (session["user_id"], session["user_id"], session["user_id"], session["user_id"]))
        mutual_friends = cursor.fetchall()
        
        return render_template("notifications.html", 
                            sent_requests=sent_requests,
                            received_requests=received_requests,
                            mutual_friends=mutual_friends)
    finally:
        conn.close()

# 處理好友邀請（接受/拒絕）
@app.route("/handle_friend_request", methods=["POST"])
def handle_friend_request():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401
    
    data = request.get_json()
    request_id = data.get("request_id")
    action = data.get("action")  # 'accept' 或 'reject'
    
    if not request_id or not action:
        return jsonify({"error": "缺少必要參數"}), 400
        
    conn = get_db()
    try:
        # 更新邀請狀態
        conn.execute("""
            UPDATE friend_requests 
            SET status = ? 
            WHERE id = ? AND to_user_id = ?
        """, (action, request_id, session["user_id"]))
        conn.commit()
        return jsonify({
            "status": "success", 
            "message": "已處理邀請",
            "action": action
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 發送好友邀請
@app.route("/send_friend_request", methods=["POST"])
def send_friend_request():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401
    
    data = request.get_json()
    to_user_id = data.get("to_user_id")
    
    if not to_user_id:
        return jsonify({"error": "缺少接收者ID"}), 400
        
    conn = get_db()
    try:
        # 檢查是否已經發送過邀請
        cursor = conn.execute("""
            SELECT * FROM friend_requests 
            WHERE from_user_id = ? AND to_user_id = ?
        """, (session["user_id"], to_user_id))
        existing_request = cursor.fetchone()
        
        if existing_request:
            return jsonify({"error": "已經發送過邀請了"}), 400
            
        # 檢查對方是否已經發送邀請給我
        cursor = conn.execute("""
            SELECT id FROM friend_requests 
            WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'
        """, (to_user_id, session["user_id"]))
        other_request = cursor.fetchone()
        
        if other_request:
            # 如果對方已經發送邀請，則自動接受對方的邀請
            conn.execute("""
                UPDATE friend_requests 
                SET status = 'accept' 
                WHERE id = ?
            """, (other_request["id"],))
            conn.commit()
            return jsonify({
                "status": "success", 
                "message": "已自動接受對方的好友邀請",
                "is_mutual": True
            })
            
        # 發送新邀請
        conn.execute("""
            INSERT INTO friend_requests (from_user_id, to_user_id, status, created_at)
            VALUES (?, ?, 'pending', DATETIME('now', 'localtime'))
        """, (session["user_id"], to_user_id))
        conn.commit()
        return jsonify({"status": "success", "message": "邀請已發送"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 通知頁面
@app.route("/notifications")
def notifications():
    if "user" not in session:
        return redirect("/login")
        
    conn = get_db()
    try:
        # 獲取已發送的邀請及其狀態
        cursor = conn.execute("""
            SELECT fr.id, fr.created_at, fr.status,
                   u.name as to_user_name, u.id as to_user_id,
                   up.birth_year, up.gender, up.height, up.bio, up.mbti,
                   (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo
            FROM friend_requests fr
            JOIN users u ON fr.to_user_id = u.id
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE fr.from_user_id = ?
            AND NOT EXISTS (
                -- 排除已互相接受的邀請
                SELECT 1 FROM friend_requests fr2
                WHERE fr2.from_user_id = fr.to_user_id
                AND fr2.to_user_id = fr.from_user_id
                AND fr2.status = 'accept'
                AND fr.status = 'accept'
            )
            ORDER BY 
                CASE fr.status 
                    WHEN 'pending' THEN 1 
                    WHEN 'accept' THEN 2 
                    WHEN 'reject' THEN 3 
                END,
                fr.created_at DESC
        """, (session["user_id"],))
        sent_requests = cursor.fetchall()
        
        # 獲取收到的邀請（包括待處理的）
        cursor = conn.execute("""
            SELECT fr.id, fr.created_at, fr.status,
                   u.name as from_user_name, u.id as from_user_id,
                   up.birth_year, up.gender, up.height, up.bio, up.mbti,
                   (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo
            FROM friend_requests fr
            JOIN users u ON fr.from_user_id = u.id
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE fr.to_user_id = ?
            AND (
                fr.status = 'pending'  -- 顯示所有待處理的邀請
                OR (
                    fr.status IN ('accept', 'reject')
                    AND NOT EXISTS (  -- 對於已處理的邀請，排除已互相接受的情況
                        SELECT 1 FROM friend_requests fr2
                        WHERE fr2.from_user_id = fr.to_user_id
                        AND fr2.to_user_id = fr.from_user_id
                        AND fr2.status = 'accept'
                        AND fr.status = 'accept'
                    )
                )
            )
            ORDER BY 
                CASE fr.status 
                    WHEN 'pending' THEN 1 
                    WHEN 'accept' THEN 2 
                    WHEN 'reject' THEN 3 
                END,
                fr.created_at DESC
        """, (session["user_id"],))
        received_requests = cursor.fetchall()

        # 獲取已成為好友的用戶（只顯示最新的一條記錄）
        cursor = conn.execute("""
            SELECT 
                fr.id, fr.created_at, fr.status,
                u.name as friend_name, u.id as friend_id,
                up.birth_year, up.gender, up.height, up.bio, up.mbti,
                (SELECT photo_url FROM photos WHERE user_id = u.id AND is_profile_photo = 1 LIMIT 1) as profile_photo
            FROM friend_requests fr
            JOIN users u ON u.id = CASE 
                WHEN fr.from_user_id = ? THEN fr.to_user_id
                ELSE fr.from_user_id
            END
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE fr.status = 'accept'
            AND EXISTS (
                SELECT 1 FROM friend_requests fr2
                WHERE fr2.from_user_id = fr.to_user_id
                AND fr2.to_user_id = fr.from_user_id
                AND fr2.status = 'accept'
            )
            AND (fr.from_user_id = ? OR fr.to_user_id = ?)
            AND fr.created_at >= (
                SELECT created_at FROM friend_requests fr2
                WHERE ((fr2.from_user_id = fr.from_user_id AND fr2.to_user_id = fr.to_user_id)
                   OR (fr2.from_user_id = fr.to_user_id AND fr2.to_user_id = fr.from_user_id))
                AND fr2.status = 'accept'
                ORDER BY created_at DESC
                LIMIT 1
            )
            GROUP BY CASE 
                WHEN fr.from_user_id = ? THEN fr.to_user_id
                ELSE fr.from_user_id
            END
            ORDER BY fr.created_at DESC
        """, (session["user_id"], session["user_id"], session["user_id"], session["user_id"]))
        mutual_friends = cursor.fetchall()
        
        return render_template("notifications.html", 
                            sent_requests=sent_requests,
                            received_requests=received_requests,
                            mutual_friends=mutual_friends)
    finally:
        conn.close()

# 處理好友邀請（接受/拒絕）
@app.route("/handle_friend_request", methods=["POST"])
def handle_friend_request():
    if "user_id" not in session:
        return jsonify({"error": "未登入"}), 401
    
    data = request.get_json()
    request_id = data.get("request_id")
    action = data.get("action")  # 'accept' 或 'reject'
    
    if not request_id or not action:
        return jsonify({"error": "缺少必要參數"}), 400
        
    conn = get_db()
    try:
        # 更新邀請狀態
        conn.execute("""
            UPDATE friend_requests 
            SET status = ? 
            WHERE id = ? AND to_user_id = ?
        """, (action, request_id, session["user_id"]))
        conn.commit()
        return jsonify({
            "status": "success", 
            "message": "已處理邀請",
            "action": action
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 啟動伺服器
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)

