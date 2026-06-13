"""PaperVault — real AES-256-GCM with a split decryption key.

The 32-byte key is generated on upload, then split via XOR into two halves:
  • server half  → stored in the FastAPI vault (Exam.server_key_half)
  • contract half→ held by the "smart contract" (Exam.contract_key_half), only
                    surrendered by releaseKey() once the time-lock has elapsed
                    AND the requesting device passes the GPS geofence check.

Neither half alone reveals the key. The plaintext paper is purged immediately
after encryption — only the ciphertext blob is persisted.
"""
import base64
import hashlib
import math
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def encrypt_paper(plaintext: bytes) -> dict:
    key = AESGCM.generate_key(bit_length=256)      # 32 bytes
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)

    contract_half = os.urandom(32)
    server_half = _xor(key, contract_half)         # key = server XOR contract

    return {
        "blob": base64.b64encode(ct).decode(),
        "nonce": nonce.hex(),
        "blob_hash": hashlib.sha256(ct).hexdigest(),
        "server_key_half": server_half.hex(),
        "contract_key_half": contract_half.hex(),
    }


def reassemble_key(server_half_hex: str, contract_half_hex: str) -> bytes:
    return _xor(bytes.fromhex(server_half_hex), bytes.fromhex(contract_half_hex))


def decrypt_paper(blob_b64: str, nonce_hex: str, key: bytes) -> bytes:
    ct = base64.b64decode(blob_b64)
    return AESGCM(key).decrypt(bytes.fromhex(nonce_hex), ct, None)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def within_geofence(center_lat, center_lon, radius_m, dev_lat, dev_lon) -> tuple[bool, float]:
    d = haversine_m(center_lat, center_lon, dev_lat, dev_lon)
    return d <= radius_m, d
