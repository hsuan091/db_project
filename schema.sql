-- 修正後的資料庫架構
-- 主要修改：在 user_profiles 表中增加 name 欄位，並修正資料類型

-- 使用者基本帳戶資料
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL CHECK (email LIKE '%_@__%.__%'),
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 使用者詳細個人資料
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY,
    name TEXT,  -- 新增：從前端傳來的姓名
    birth_date INTEGER CHECK (birth_date BETWEEN 1 AND 31),
    birth_month INTEGER CHECK (birth_month BETWEEN 1 AND 12),
    birth_year INTEGER CHECK (birth_year BETWEEN 1900 AND 2024),
    gender TEXT CHECK (gender IN ('male', 'female', 'other')),
    sex_orientation_id INTEGER,
    music_genre_id INTEGER,
    mbti TEXT,
    bio TEXT,      -- 自我介紹
    height INTEGER CHECK (height > 0), -- 身高（公分）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (sex_orientation_id) REFERENCES sex_orientations(id),
    FOREIGN KEY (music_genre_id) REFERENCES music_genre(id)
);

-- 興趣分類表
CREATE TABLE IF NOT EXISTS interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT  -- 興趣分類
);

-- 使用者興趣關聯表（多對多關係）
CREATE TABLE IF NOT EXISTS user_interests (
    user_id INTEGER,
    interest_id INTEGER,
    PRIMARY KEY (user_id, interest_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (interest_id) REFERENCES interests(id)
);

-- 使用者照片
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    photo_url TEXT NOT NULL,
    is_profile_photo BOOLEAN DEFAULT 0,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 配對偏好設定
CREATE TABLE IF NOT EXISTS match_preferences (
    user_id INTEGER PRIMARY KEY,
    min_age INTEGER,
    max_age INTEGER,
    preferred_gender TEXT CHECK (preferred_gender IN ('male', 'female', 'other')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 配對請求
CREATE TABLE IF NOT EXISTS match_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    status TEXT CHECK(status IN ('pending', 'accepted', 'rejected')) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_user_id) REFERENCES users(id),
    FOREIGN KEY (to_user_id) REFERENCES users(id)
);

-- 聊天室（修正表名，與後端程式一致）
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_a_id INTEGER NOT NULL,
    user_b_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    FOREIGN KEY (user_a_id) REFERENCES users(id),
    FOREIGN KEY (user_b_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (thread_id) REFERENCES threads(id),
    FOREIGN KEY (sender_id) REFERENCES users(id)
);

-- 訊息（修正外鍵參照）
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,  -- 修正：參照 threads 表
    sender_id INTEGER NOT NULL,
    text TEXT NOT NULL,  -- 修正：欄位名稱改為 text
    is_read BOOLEAN DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 修正：欄位名稱
    FOREIGN KEY (thread_id) REFERENCES threads(id),
    FOREIGN KEY (sender_id) REFERENCES users(id)
);

-- 性向分類
CREATE TABLE IF NOT EXISTS sex_orientations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

-- 音樂類型
CREATE TABLE IF NOT EXISTS music_genre (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

-- 預設資料插入
INSERT OR IGNORE INTO sex_orientations (name, description) VALUES
    ('異性戀', '對異性有興趣'),
    ('同性戀', '對同性有興趣'),
    ('雙性戀', '對兩種性別都有興趣'),
    ('泛性戀', '對所有性別都有興趣'),
    ('無性戀', '對任何性別都沒有興趣'),
    ('其他', '其他性向');

INSERT OR IGNORE INTO music_genre (name) VALUES
    ('西洋'), ('聽團'), ('K-pop'), ('流行'), ('古典'),
    ('爵士'), ('嘻哈'), ('電子'), ('鄉村'), ('R&B');

-- 建立索引以提升查詢效能
CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id);
CREATE INDEX IF NOT EXISTS idx_photos_upload_date ON photos(upload_date);
CREATE INDEX IF NOT EXISTS idx_user_interests_user_id ON user_interests(user_id);
CREATE INDEX IF NOT EXISTS idx_user_interests_interest_id ON user_interests(interest_id);
CREATE INDEX IF NOT EXISTS idx_match_requests_from_user ON match_requests(from_user_id);
CREATE INDEX IF NOT EXISTS idx_match_requests_to_user ON match_requests(to_user_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_sex_orientation_id ON user_profiles(sex_orientation_id);
CREATE INDEX IF NOT EXISTS idx_threads_user_a_id ON threads(user_a_id);
CREATE INDEX IF NOT EXISTS idx_threads_user_b_id ON threads(user_b_id);

-- 唯一性約束
CREATE UNIQUE INDEX IF NOT EXISTS idx_threads_unique ON threads(user_a_id, user_b_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_match_requests_unique ON match_requests(from_user_id, to_user_id);