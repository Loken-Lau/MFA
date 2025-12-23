from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec

class ServerAuthEngine:
    """服务端：只负责验证签名是否合法"""
    @staticmethod
    def verify_signature(public_key_pem, signature_bytes, challenge_str):
        try:
            # 加载公钥
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            # 验证签名 (ECC P-256)
            public_key.verify(
                signature_bytes,
                challenge_str.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception as e:
            print(f">>> 服务端验证异常: {e}")
            return False