import os, face_recognition, numpy as np
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec

class LocalSecureEnclave:
    """客户端：模拟硬件隔离区 (TEE)"""
    def __init__(self, storage_path):
        self.storage_path = storage_path

    def enroll(self, username, face_encoding):
        """录入：生成 ECC 密钥对，私钥存本地，返回公钥"""
        # 1. 存储人脸模板到本地 picture/
        np.save(os.path.join(self.storage_path, f'{username}_face.npy'), face_encoding)
        
        # 2. 生成 ECC 私钥 (P-256 曲线)
        private_key = ec.generate_private_key(ec.SECP256R1())
        
        # 3. 存储私钥到本地 picture/
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(os.path.join(self.storage_path, f'{username}_priv.pem'), 'wb') as f:
            f.write(pem)
            
        # 4. 返回公钥
        return private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def sign(self, username, current_frame, challenge):
        """认证：刷脸成功后，用私钥对挑战码签名"""
        face_path = os.path.join(self.storage_path, f'{username}_face.npy')
        priv_path = os.path.join(self.storage_path, f'{username}_priv.pem')
        
        if not os.path.exists(face_path): return None
        
        # 1. 本地人脸比对 (不出本地)
        template = np.load(face_path)
        encs = face_recognition.face_encodings(current_frame)
        
        if encs and face_recognition.compare_faces([template], encs[0], 0.4)[0]:
            # 2. 只有刷脸成功，才允许调用私钥进行数字签名
            with open(priv_path, 'rb') as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None)
            
            signature = private_key.sign(challenge.encode(), ec.ECDSA(hashes.SHA256()))
            return signature
        return None