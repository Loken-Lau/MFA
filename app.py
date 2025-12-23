import os
import base64
import io
import sqlite3
import json
import pyotp
import qrcode
import face_recognition
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'mfa-secure-lab-key-2025' # 安全密钥
DB_PATH = 'mfa_system.db'

# --- 数据库初始化 ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            mfa_secret TEXT NOT NULL,
            face_encoding TEXT,
            mfa_active INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 数据库辅助函数 ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- 图像处理工具 ---
def process_base64_image(base64_str):
    header, encoded = base64_str.split(",", 1)
    data = base64.b64decode(encoded)
    with open("temp_capture.jpg", "wb") as f:
        f.write(data)
    return face_recognition.load_image_file("temp_capture.jpg")

# --- 路由逻辑 ---

@app.route('/')
def index():
    if not session.get('mfa_verified'):
        return redirect(url_for('login'))
    return render_template('index.html', user=session['user'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password)
        secret = pyotp.random_base32()
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, mfa_secret) VALUES (?, ?, ?)',
                         (username, hashed_pw, secret))
            conn.commit()
            session['temp_reg_user'] = username
            return redirect(url_for('setup_mfa'))
        except sqlite3.IntegrityError:
            return "用户名已存在"
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/setup_mfa', methods=['GET', 'POST'])
def setup_mfa():
    username = session.get('temp_reg_user')
    if not username: return redirect(url_for('register'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    totp = pyotp.totp.TOTP(user['mfa_secret'])
    
    if request.method == 'POST':
        code = request.form.get('code')
        if totp.verify(code):
            conn = get_db_connection()
            conn.execute('UPDATE users SET mfa_active = 1 WHERE username = ?', (username,))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        return "动态码校验失败，请重试"

    uri = totp.provisioning_uri(name=username, issuer_name="MFA_Secure_Lab")
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_code = base64.b64encode(buf.getvalue()).decode()
    return render_template('setup_mfa.html', qr_code=qr_code)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            if not user['mfa_active']:
                session['temp_reg_user'] = username
                return redirect(url_for('setup_mfa'))
            
            session.clear()
            session['temp_user'] = username
            if user['face_encoding'] is None:
                return redirect(url_for('face_auth', mode='register'))
            return redirect(url_for('face_auth', mode='verify'))
        return "身份验证失败"
    return render_template('login.html')

@app.route('/face_auth/<mode>', methods=['GET', 'POST'])
def face_auth(mode):
    if 'temp_user' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        image_data = request.json.get('image')
        image = process_base64_image(image_data)
        encodings = face_recognition.face_encodings(image)
        
        if not encodings:
            return jsonify({"status": "error", "message": "未检测到人脸"})
        
        if mode == 'register':
            encoding_json = json.dumps(encodings[0].tolist())
            conn = get_db_connection()
            conn.execute('UPDATE users SET face_encoding = ? WHERE username = ?', 
                         (encoding_json, session['temp_user']))
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "next": url_for('login')})
            
        elif mode == 'verify':
            conn = get_db_connection()
            user = conn.execute('SELECT face_encoding FROM users WHERE username = ?', 
                                (session['temp_user'],)).fetchone()
            conn.close()
            
            target_encoding = np.array(json.loads(user['face_encoding']))
            match = face_recognition.compare_faces([target_encoding], encodings[0], tolerance=0.4)
            
            if match[0]:
                session['face_ok'] = True
                return jsonify({"status": "success", "next": url_for('otp_verify')})
            return jsonify({"status": "error", "message": "人脸不匹配"})

    return render_template('face_auth.html', mode=mode)

@app.route('/otp_verify', methods=['GET', 'POST'])
def otp_verify():
    if not session.get('face_ok'): return redirect(url_for('login'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        conn = get_db_connection()
        user = conn.execute('SELECT mfa_secret FROM users WHERE username = ?', 
                            (session['temp_user'],)).fetchone()
        conn.close()
        
        if pyotp.totp.TOTP(user['mfa_secret']).verify(code):
            session['user'] = session['temp_user']
            session['mfa_verified'] = True
            return redirect(url_for('index'))
        return "动态码错误"
        
    return render_template('otp_auth.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)