--這個是使用者的帳戶資料
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL CHECK (email LIKE '%_@__%.__%'),
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY,
    birth_date INTEGER CHECK (birth_date BETWEEN 1 AND 31),
    birth_month INTEGER CHECK (birth_month BETWEEN 1 AND 12),
    birth_year INTEGER CHECK (birth_year BETWEEN 1900 AND 2024),
    gender TEXT CHECK (gender IN ('male', 'female', 'other')),
    sex_orientation_id INTEGER,
    music_genre_id INTEGER,
    mbti TEXT, -- 新增 mbti 欄位
    -- location TEXT, --之後可以做這個 跟那個最大距離有關
    bio TEXT,      -- 自我介紹
    height INTEGER CHECK (height > 0), -- 身高（公分）
    -- occupation TEXT, --之後可以做這個
    -- education TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (sex_orientation_id) REFERENCES sex_orientations(id),
    FOREIGN KEY (music_genre_id) REFERENCES music_genre(id)
);

CREATE TABLE IF NOT EXISTS interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT  -- 興趣分類
);

-- 這個是使用者興趣 是直接跟users 多對多 透過user_profiles會很麻煩
CREATE TABLE IF NOT EXISTS user_interests (
    user_id INTEGER,
    interest_id INTEGER,
    PRIMARY KEY (user_id, interest_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (interest_id) REFERENCES interests(id)
);

CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    photo_url TEXT NOT NULL,
    is_profile_photo BOOLEAN DEFAULT 0,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS match_preferences (
    user_id INTEGER PRIMARY KEY,
    min_age INTEGER,
    max_age INTEGER,
    preferred_gender TEXT CHECK (preferred_gender IN ('male', 'female', 'other')),
    -- max_distance INTEGER,  -- 最大距離（公里）
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS match_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    status TEXT CHECK(status IN ('pending', 'accepted', 'rejected')) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_user_id) REFERENCES users(id),
    FOREIGN KEY (to_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS chat_rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_a_id INTEGER NOT NULL,
    user_b_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    FOREIGN KEY (user_a_id) REFERENCES users(id),
    FOREIGN KEY (user_b_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_room_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT 0,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_room_id) REFERENCES chat_rooms(id),
    FOREIGN KEY (sender_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sex_orientations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,  -- 性向名稱
    description TEXT           -- 性向描述（可選）
);

CREATE TABLE IF NOT EXISTS music_genre (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

INSERT OR IGNORE INTO sex_orientations (name, description) VALUES
    ('異性戀', '對異性有興趣'),
    ('同性戀', '對同性有興趣'),
    ('雙性戀', '對兩種性別都有興趣'),
    ('泛性戀', '對所有性別都有興趣'),
    ('無性戀', '對任何性別都沒有興趣'),
    ('其他', '其他性向');

-- 這個是索引 可以加快查詢速度
CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id);
CREATE INDEX IF NOT EXISTS idx_photos_upload_date ON photos(upload_date);
CREATE INDEX IF NOT EXISTS idx_user_interests_user_id ON user_interests(user_id);
CREATE INDEX IF NOT EXISTS idx_user_interests_interest_id ON user_interests(interest_id);
CREATE INDEX IF NOT EXISTS idx_match_requests_from_user ON match_requests(from_user_id);
CREATE INDEX IF NOT EXISTS idx_match_requests_to_user ON match_requests(to_user_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_room_id ON messages(chat_room_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);

-- 需要確保所有外鍵都有對應的索引
-- 建議為以下外鍵添加索引：
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_sex_orientation_id ON user_profiles(sex_orientation_id);
CREATE INDEX IF NOT EXISTS idx_chat_rooms_user_a_id ON chat_rooms(user_a_id);
CREATE INDEX IF NOT EXISTS idx_chat_rooms_user_b_id ON chat_rooms(user_b_id);

-- 建議為以下組合添加唯一性約束
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_rooms_unique ON chat_rooms(user_a_id, user_b_id);  -- 避免重複的聊天室
CREATE UNIQUE INDEX IF NOT EXISTS idx_match_requests_unique ON match_requests(from_user_id, to_user_id);  -- 避免重複的配對請求
