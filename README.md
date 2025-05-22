5/22 廖靖綾 17:20

## 專案進度紀錄

### 1. 配對功能
- **接下來重點會是配對功能**
  目前主力開發方向。
---
### 2. 錯誤訊息與 flash 機制
- 為了方便 debug，暫時在所有頁面加上 flash 訊息顯示區塊：
  ```jinja2
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <ul class="flashes">
        {% for message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
      </ul>
    {% endif %}
  {% endwith %}
  ```
- 之後會再優化錯誤訊息的顯示方式，目前屬於次要事項。

---

### 3. 資料庫管理
- 有時候後端出現問題，可能是因為資料庫結構已經更動，但 `models.db` 還是舊的。
- **解決方式**：刪除舊資料庫並重建
  ```bash
  rm models.db
  sqlite3 models.db < schema.sql
  ```

---

### 4. 架構調整
- 已經**完全移除 Firebase 相關程式碼**。
- `info.html` 已經改用 React 開發。

---

### 5. 之後的開發規劃
- 主要配對邏輯會用 MBTI（尚未實作，預計後續補上）。
- 測試時建議每次都刪除 `models.db` 再重建，避免舊資料影響測試結果。
- 有發現一些細微功能可以優化，例如個人資料欄位、興趣欄位（目前逗號分隔的字串處理還需加強）。

---

### 6. 目前功能狀態
- **個人資料填寫**：資料可正確儲存，路徑也正確。
- **配對頁**：可以看到推薦對象，但配對按鈕尚未實作。
- **配對頁上方提示**：即使已填寫個人資料，仍顯示「尚未完成」的提示，需再確認判斷邏輯。
- **照片功能**：尚未測試與整合到前端顯示，但後端框架已經寫好，且已改為本地 static/ 儲存（已移除 Google Storage）。

==
#### !! 建議先下載好軟體 之後會commit push才會比較方便
## 下載套件
```
pip install -r requirement.txt
```
## 編譯執行
### crtl+c quit
- 結束執行
### crtl+按網址
- 開啟網頁

   

### 架構

```
project/
├── app.py                   ← 主程式（Flask）
├── models.db                ← SQLite 本地資料庫（使用者資料、配對、聊天）
├── schema.sql               ← SQL 資料表定義檔（老師需要）
├── firebase_init.py         ← Firestore 初始化（額外擴充用）
├── serviceAccountKey.json   ← Firebase 憑證（不要上傳 GitHub）
├── requirements.txt         ← 所需套件（sqlite3, firebase-admin, flask）
│
├── templates/               ← 前端 HTML
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── match.html
│   └── profile.html
│
├── static/                  ← CSS / 圖片 / JS
│   └── style.css
│
└── README.md                ← 專案說明
```
mac 虛擬環境

python3 -m venv venv          # 建立虛擬環境
source venv/bin/activate      # 啟動虛擬環境（Mac/Linux）
# 如果你是 Windows： venv\Scripts\activate
pip install -r requirements.txt

退出虛擬環境 deactivate