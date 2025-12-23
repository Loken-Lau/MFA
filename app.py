import os, base64, io, sqlite3, pyotp, qrcode, face_recognition
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# 导入自定义逻辑模块
from client_logic.secure_enclave import LocalSecureEnclave
from server_logic.auth_engine import ServerAuthEngine

# 1. 初始化 Flask 并支持实例文件夹
app = Flask(__name__, instance_relative_config=True)
app.secret_key = 'ecc-mfa-final-safe-2025'

# 确保必要的目录存在
if not os.path.exists(app.instance_path): os.makedirs(app.instance_path)
if not os.path.exists('picture'): os.makedirs('picture')

# 定义数据库路径
DB_PATH = os.path.join(app.instance_path, 'mfa_system.db')

# 初始化逻辑对象
client_enclave = LocalSecureEnclave('picture')
server_engine = ServerAuthEngine()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, 
                  public_key TEXT, mfa_secret TEXT, mfa_active INTEGER DEFAULT 0)''')
    conn.close()

init_db()

# --- 路由开始 ---

# 1. 首页
@app.route('/')
def index():
    if not session.get('mfa_verified'): return redirect(url_for('login'))
    return render_template('index.html', user=session['user'])

# 2. 注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        session['reg_uname'] = request.form['username']
        session['reg_pwd'] = generate_password_hash(request.form['password'])
        return redirect(url_for('face_auth', mode='register'))
    return render_template('register.html')

# 3. 登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname, pwd = request.form['username'], request.form['password']
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT * FROM users WHERE username = ?', (uname,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], pwd):
            session.clear()
            session['temp_user'] = uname
            if not user['mfa_active']: return redirect(url_for('setup_mfa'))
            return redirect(url_for('face_auth', mode='verify'))
        return "用户名或密码错误"
    return render_template('login.html')

# 4. 人脸认证（核心：ECC 签名）
@app.route('/face_auth/<mode>', methods=['GET', 'POST'])
def face_auth(mode):
    if request.method == 'POST':
        img_data = base64.b64decode(request.json['image'].split(',')[1])
        frame = face_recognition.load_image_file(io.BytesIO(img_data))
        
        if mode == 'register':
            encs = face_recognition.face_encodings(frame)
            if not encs: return jsonify({"status": "error", "message": "未检测到人脸"})
            pub_key = client_enclave.enroll(session['reg_uname'], encs[0])
            mfa_secret = pyotp.random_base32()
            conn = sqlite3.connect(DB_PATH)
            conn.execute('INSERT INTO users (username, password, public_key, mfa_secret) VALUES (?,?,?,?)',
                         (session['reg_uname'], session['reg_pwd'], pub_key, mfa_secret))
            conn.commit(); conn.close()
            session['temp_reg_user'] = session['reg_uname']
            return jsonify({"status": "success", "next": url_for('setup_mfa')})

        elif mode == 'verify':
            challenge = session.get('challenge')
            signature = client_enclave.sign(session['temp_user'], frame, challenge)
            if signature:
                conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
                user = conn.execute('SELECT public_key FROM users WHERE username = ?', (session['temp_user'],)).fetchone(); conn.close()
                if server_engine.verify_signature(user['public_key'], signature, challenge):
                    session['face_ok'] = True
                    return jsonify({"status": "success", "next": url_for('otp_verify')})
            return jsonify({"status": "error", "message": "人脸认证或 ECC 签名失败"})

    if mode == 'verify': session['challenge'] = os.urandom(16).hex()
    return render_template('face_auth.html', mode=mode)

# 5. 绑定 TOTP (解决之前的 BuildError)
@app.route('/setup_mfa', methods=['GET', 'POST'])
def setup_mfa():
    username = session.get('temp_reg_user')
    if not username: return redirect(url_for('register'))
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    user = conn.execute('SELECT mfa_secret FROM users WHERE username = ?', (username,)).fetchone(); conn.close()
    
    totp = pyotp.totp.TOTP(user['mfa_secret'])
    if request.method == 'POST':
        if totp.verify(request.form.get('code')):
            conn = sqlite3.connect(DB_PATH)
            conn.execute('UPDATE users SET mfa_active = 1 WHERE username = ?', (username,))
            conn.commit(); conn.close()
            return redirect(url_for('login'))
        return "动态码错误"

    uri = totp.provisioning_uri(name=username, issuer_name="ECC_MFA_Project")
    img = qrcode.make(uri); buf = io.BytesIO(); img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return render_template('setup_mfa.html', qr_code=qr_b64)

# 6. OTP 校验
@app.route('/otp_verify', methods=['GET', 'POST'])
def otp_verify():
    if not session.get('face_ok'): return redirect(url_for('login'))
    if request.method == 'POST':
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT mfa_secret FROM users WHERE username = ?', (session['temp_user'],)).fetchone(); conn.close()
        if pyotp.totp.TOTP(user['mfa_secret']).verify(request.form.get('code')):
            session['user'] = session['temp_user']
            session['mfa_verified'] = True
            return redirect(url_for('index'))
        return "OTP 码错误"
    return render_template('otp_auth.html')

# 7. 退出
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)