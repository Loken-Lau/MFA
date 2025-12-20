import face_recognition
import cv2
import pyotp
import numpy as np

# --- 配置区 ---
# 1. 模拟数据库：存储用户名及其对应的 TOTP 密钥和人脸特征
# 实际开发中，这些应该从数据库读取
USER_DATA = {
    "admin": {
        "mfa_secret": "JBSWY3DPEHPK3PXP", # 这是之前生成的 Base32 密钥
        "face_encoding": None              # 待注册
    }
}

def get_face_encoding():
    """捕获摄像头画面并提取人脸特征"""
    video_capture = cv2.VideoCapture(0)
    print("正在启动摄像头，请正对屏幕...")
    
    encoding = None
    while True:
        ret, frame = video_capture.read()
        if not ret: break
        
        # 为了提速，缩小画面处理
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # 查找人脸
        face_locations = face_recognition.face_locations(rgb_small_frame)
        
        # 画个框提示用户
        for (top, right, bottom, left) in face_locations:
            cv2.rectangle(frame, (left*4, top*4), (right*4, bottom*4), (0, 255, 0), 2)
            cv2.putText(frame, "Face Detected", (left*4, top*4-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)
        
        cv2.imshow('MFA Face Auth', frame)
        
        # 只要检测到人脸就尝试提取特征
        if face_locations:
            encoding = face_recognition.face_encodings(rgb_small_frame, face_locations)[0]
            print("成功提取人脸特征！")
            break

        if cv2.waitKey(1) & 0xFF == ord('q'): break

    video_capture.release()
    cv2.destroyAllWindows()
    return encoding

def main():
    username = "admin"
    print(f"--- 欢迎登录安全系统 ({username}) ---")

    # --- 第一因子：人脸识别 ---
    print("\n[因子 1] 请进行人脸验证...")
    # 模拟：第一次运行先注册人脸，第二次运行进行比对
    if USER_DATA[username]["face_encoding"] is None:
        print("首次登录，正在录入您的生物信息...")
        USER_DATA[username]["face_encoding"] = get_face_encoding()
        print("人脸录入成功！请重新运行程序进行验证。")
        return

    current_face = get_face_encoding()
    match = face_recognition.compare_faces([USER_DATA[username]["face_encoding"]], current_face, tolerance=0.4)

    if not match[0]:
        print("❌ 人脸校验失败！拒绝访问。")
        return
    print("✅ 人脸校验通过！")

    # --- 第二因子：TOTP 验证码 ---
    print("\n[因子 2] 请输入手机 App 上的 6 位验证码...")
    totp = pyotp.totp.TOTP(USER_DATA[username]["mfa_secret"])
    user_code = input("验证码: ")

    if totp.verify(user_code):
        print("\n🎉【登录成功】欢迎回来，管理员！")
    else:
        print("\n❌ 验证码错误！安全系统已锁定。")

if __name__ == "__main__":
    main()
