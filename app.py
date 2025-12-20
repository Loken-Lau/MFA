import os
import base64
import io
import pyotp
import qrcode
import face_recognition
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'super-secret-lab-key' # 建议生产环境使用随机字符串

# 模拟数据库：实际开发请连接 PostgreSQL 或 MySQL
# 结构：{ "用户名": { "password": "...", "mfa_secret": "...", "face_encoding": None, "mfa_active": False } }
users_db = {}

# 工具函数：生成二维码 Base64
def generate_qr_base64(uri):
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# 工具函数：处理前端上传的 Base64 图像
def process_base64_image(base64_str):
    header, encoded = base64_str.split(",", 1)
    data = base64.b64decode(encoded)
    with open("temp_capture.jpg", "wb") as f:
        f.write(data)
    return face_recognition.load_image_file("temp_capture.jpg")

@app.route('/')
def index():
    if not session.get('mfa_verified'):
        return redirect(url_for('login'))
    return render_template('index.html', user=session['user'])

# --- 1. 注册功能 ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in users_db:
            return "用户已存在"
        
        # 创建用户并生成随机密钥
        secret = pyotp.random_base32()
        users_db[username] = {
            "password": password,
            "mfa_secret": secret,
            "face_encoding": None,
            "mfa_active": False 
        }
        session['temp_reg_user'] = username
        return redirect(url_for('setup_mfa'))
    return render_template('register.html')

# --- 2. 绑定 Authenticator (生成并验证) ---
@app.route('/setup_mfa', methods=['GET', 'POST'])
def setup_mfa():
    username = session.get('temp_reg_user')
    if not username: return redirect(url_for('register'))
    
    user = users_db[username]
    totp = pyotp.totp.TOTP(user['mfa_secret'])
    
    if request.method == 'POST':
        code = request.form.get('code')
        if totp.verify(code):
            user['mfa_active'] = True # 正式激活 MFA
            return redirect(url_for('login'))
        return "验证码错误，请重新扫码输入"

    uri = totp.provisioning_uri(name=username, issuer_name="MFA_Secure_System")
    qr_code = generate_qr_base64(uri)
    return render_template('setup_mfa.html', qr_code=qr_code)

# --- 3. 登录与多阶段验证 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = users_db.get(username)
        
        if user and user['password'] == password:
            if not user['mfa_active']:
                session['temp_reg_user'] = username
                return redirect(url_for('setup_mfa'))
            
            session.clear() # 安全起见清除旧 session
            session['temp_user'] = username
            # 检查是否录入了人脸
            if user['face_encoding'] is None:
                return redirect(url_for('face_auth', mode='register'))
            return redirect(url_for('face_auth', mode='verify'))
        return "用户名或密码错误"
    return render_template('login.html')

# --- 4. 人脸识别路由 ---
@app.route('/face_auth/<mode>', methods=['GET', 'POST'])
def face_auth(mode):
    if 'temp_user' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        image_data = request.json.get('image')
        image = process_base64_image(image_data)
        encodings = face_recognition.face_encodings(image)
        
        if not encodings:
            return jsonify({"status": "error", "message": "未检测到人脸"})
        
        user = users_db[session['temp_user']]
        if mode == 'register':
            user['face_encoding'] = encodings[0]
            return jsonify({"status": "success", "next": url_for('login')})
        elif mode == 'verify':
            target = user['face_encoding']
            match = face_recognition.compare_faces([target], encodings[0], tolerance=0.4)
            if match[0]:
                session['face_ok'] = True
                return jsonify({"status": "success", "next": url_for('otp_verify')})
            return jsonify({"status": "error", "message": "人脸不匹配"})

    return render_template('face_auth.html', mode=mode)

# --- 5. 最终 OTP 验证 ---
@app.route('/otp_verify', methods=['GET', 'POST'])
def otp_verify():
    if not session.get('face_ok'): 
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        user = users_db[session['temp_user']]
        if pyotp.totp.TOTP(user['mfa_secret']).verify(code):
            session['user'] = session['temp_user']
            session['mfa_verified'] = True
            return redirect(url_for('index'))
        return "动态验证码错误"
        
    return render_template('otp_auth.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)