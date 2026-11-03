import base64
import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import hashlib

data_b64 = "1MOh25yFeAUlFjXnWygAb9THSB2XOU9FHZs8ZRBEcO6o6HNIVCF/+dtWrLNpbyKQc948a9GE10WPJNHUEEfyyYJxPTblVeYgAVVJOsN4FfY="
ciphertext = base64.b64decode(data_b64)

zpw_sek = "pt54.466784528.a0.pEx5gaxrrp7DW59S_160HwOpvIp_Aw9mwqFuBOaXytFlTBKFhLh94wn7pogwBBrbe1yw2exCZH2z42mfD7k0Hm"

# Các cách tạo key thông dụng trong Zalo
candidates = [
    zpw_sek.encode()[:16],
    zpw_sek.encode()[:32],
    hashlib.md5(zpw_sek.encode()).digest(),
    hashlib.sha256(zpw_sek.encode()).digest()[:16],
    hashlib.sha256(zpw_sek.encode()).digest(),
]

parts = zpw_sek.split(".")
if len(parts) >= 4:
    candidates.append(parts[3].encode()[:16])
    candidates.append(hashlib.md5(parts[3].encode()).digest())

iv_zero = bytes([0]*16)

for i, k in enumerate(candidates):
    # Thử CBC
    try:
        cipher = AES.new(k, AES.MODE_CBC, iv_zero)
        dec = unpad(cipher.decrypt(ciphertext), 16)
        print(f"Success candidate {i} CBC:", dec.decode('utf-8', errors='ignore'))
    except Exception:
        pass
    # Thử ECB
    try:
        cipher = AES.new(k, AES.MODE_ECB)
        dec = unpad(cipher.decrypt(ciphertext), 16)
        print(f"Success candidate {i} ECB:", dec.decode('utf-8', errors='ignore'))
    except Exception:
        pass
