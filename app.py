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

#@app.route("/info", methods=["GET", "POST"])
#def info():
#    return render_template("info.html")


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

        # 在這裡判斷是否已有個資
        conn = get_db()
        cursor = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user["id"],))
        user_profile = cursor.fetchone()
        conn.close()

        if not user_profile:
            return redirect("/info")
        else:
            return redirect("/match")

        #flash("登入成功，歡迎 " + user["name"])
        #return redirect("/match")
    else:
        flash("登入失敗，請檢查帳密")
        #return redirect("/login")
    return render_template("login.html")
    

@app.route("/match")
def match():
    if "user" not in session:
        return redirect("/login")
    
    

    user_id = session["user_id"]
    conn = get_db()

    try:
        # 取得當前用戶資料（包含 MBTI）
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
            return redirect("/profile")  # 導去你個資設定的頁面，請確認這個路徑正確
    
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
            user_profile["mbti"]  # 確保 MBTI 也已填寫
        )

        user_mbti = user_profile["mbti"].upper()

        # 固定 MBTI 配對表
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
            recommendations = []  # 若找不到對應 MBTI，則無推薦
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

'''
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
            user_profile["interests"] and 
            user_profile["mbti"]  
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
'''

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
        
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)