# MFA 多因子身份认证系统 (人脸识别 + TOTP)

本实验是一个基于 **Python Flask** 开发的安全登录系统，实现了三阶段身份验证。它将传统的密码认证、生物识别（人脸）和时间令牌（TOTP）结合在一起，体现了现代安全防御中“分层防御”的思想。

## 🌟 核心功能

- **第一因子（知识）：** 用户名与密码。
    
- **第二因子（生物）：** 基于深度学习的人脸特征比对（ResNet-128）。
    
- **第三因子（持有）：** 基于时间的一次性密码（TOTP），兼容 Google Authenticator。
    
- **动态绑定：** 用户注册时动态生成 Base32 密钥并展示二维码供手机扫码。
    

---

## 🛠️ 技术原理

### 1. 人脸识别 (Something You Are)

系统采用 `face_recognition` 库，其底层是基于 **Dlib** 的深度学习模型。

- **特征提取：** 通过预训练的残差网络（ResNet）将人脸图像映射为一个 **128 维的特征向量**（浮点数数组）。
    
- **比对机制：** 计算录入特征与当前捕获特征之间的**欧氏距离**。
    
- **安全性：** 系统仅存储 128 位特征向量，而非原始照片，实现了生物信息的脱敏存储。
    

### 2. TOTP 动态口令 (Something You Have)

系统遵循 **RFC 6238** 标准，实现基于时间的一次性密码。

- **哈希算法：** 默认使用 **HMAC-SHA1**。
    
- **时间戳同步：** 以 30 秒为一个步长（Time Step），将密钥与当前 Unix 时间戳结合，经过 HMAC 运算、动态截断和取模，生成 6 位数字。
    
- **特性：** 离线计算，无需网络通信即可完成验证。
    

---

## 📂 项目结构

Plaintext

```
MFA_Project/
├── app.py                 # 后端 Flask 核心，包含三因子验证逻辑
├── templates/             # 前端 HTML 模板（采用 Tailwind CSS 渲染）
│   ├── base.html          # 基础布局
│   ├── register.html      # 用户注册与初始密钥生成
│   ├── setup_mfa.html     # 二维码展示与扫码绑定
│   ├── login.html         # 密码登录阶段
│   ├── face_auth.html     # 人脸识别阶段
│   ├── otp_auth.html      # TOTP 动态码验证阶段
│   └── index.html         # 登录成功主页
└── requirements.txt       # 项目依赖清单
```

---

## 🚀 快速开始

### 1. 环境准备 (Ubuntu)

确保已安装必备的系统库（用于编译 Dlib）：


```bash
# 更新源
sudo apt update

# 安装 C++ 编译器、CMake 以及 Dlib 依赖的库

sudo apt install -y build-essential cmake pkg-config
sudo apt install -y libx11-dev libatlas-base-dev libgtk-3-dev libboost-python-dev

# 安装 Python 相关工具

sudo apt install -y python3-pip python3-venv python3-dev
```

### 2. 安装依赖

建议在 Python 虚拟环境中操作：

>pip安装库之前建议配环境之前建议先换源
```
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```


```bash
python3 -m venv .venv
source .venv/bin/activate
pip install face_recognition flask opencv-python pyotp qrcode
# pip install -r requirements.txt
```

### 3.最关键的一步 —— 映射摄像头

在虚拟机里，代码默认找不到你的摄像头。你需要手动把宿主机的 USB 摄像头“拨”给虚拟机：

1. VMware 用户：
	- 确保虚拟机窗口是活动状态。
	- 点击上方菜单栏：`虚拟机 (VM)` -> `可移动设备 (Removable Devices)`。
	- 找到你的 `Camera` 或 `Webcam`，选择 `连接 (Connect)`。
2. 这部分往往会遇到点障碍，可以先去宿主机的服务中重启USB服务，然后再试一下1.
```
1、重启 Windows 的 VMware USB 仲裁服务，有时候负责把 USB 设备“拨”给虚拟机的后台服务死掉了，导致点击连接也没反应。
2、在 Windows 任务栏搜索框输入 “服务” (Services.msc) 并打开。
3、找到 VMware USB Arbitration Service。
4、右键点击它，选择 “重新启动”。
5、重启该服务后，重新在 VMware 菜单里尝试连接摄像头。
```
### 4. 运行项目


```
python3 app.py
```

访问 `http://127.0.0.1:5000/register` 开始你的第一个 MFA 账号注册。

---

## 改进
1. 人脸认证安全性
2. 数据库账号密码
3. 页面友好设计
4. 生物特征和私钥对应



## 📝 实验总结

通过本实验，我们验证了多因子认证在防御撞库攻击、密码泄露以及照片伪造攻击方面的有效性。即使攻击者窃取了用户的密码，也会因为缺乏生物特征和动态硬件令牌而无法进入系统，极大地提高了身份认证的安全等级。