"""
Шифрование данных AES-256-GCM и HMAC-SHA256 для поиска.

Формат хранения зашифрованного значения:
    base64url(nonce_12b || ciphertext || tag_16b)

Каждый вызов encrypt() генерирует новый nonce → разный шифртекст
для одинаковых данных. Это предотвращает атаки на основе сравнения.

Для детерминированного поиска по полю (телефон) используется
HMAC-SHA256 с отдельным ключом SEARCH_HASH_KEY.
"""

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(plaintext: str, key: bytes) -> str:
    """
    Зашифровать строку с помощью AES-256-GCM.

    Args:
        plaintext: исходная строка
        key: 32-байтный ключ шифрования

    Returns:
        base64url-строка формата: nonce(12) || ciphertext || tag(16)
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # nonce + ciphertext + tag (tag встроен в ciphertext_with_tag у cryptography)
    combined = nonce + ciphertext_with_tag
    return base64.urlsafe_b64encode(combined).decode("ascii")


def decrypt(ciphertext_b64: str, key: bytes) -> str:
    """
    Расшифровать строку зашифрованную encrypt().

    Args:
        ciphertext_b64: base64url-строка из encrypt()
        key: 32-байтный ключ шифрования

    Returns:
        оригинальная строка

    Raises:
        ValueError: если данные повреждены или ключ неверный
    """
    try:
        combined = base64.urlsafe_b64decode(ciphertext_b64.encode("ascii"))
        nonce = combined[:12]
        ciphertext_with_tag = combined[12:]
        aesgcm = AESGCM(key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return plaintext_bytes.decode("utf-8")
    except Exception as exc:
        raise ValueError("Decryption failed: invalid key or corrupted data") from exc


def compute_search_hash(value: str, key: bytes) -> str:
    """
    Вычислить детерминированный HMAC-SHA256 хеш для поиска.

    Нормализация: .lower().strip() перед хешированием.
    Один и тот же телефон всегда даёт один хеш независимо от регистра.

    Args:
        value: значение для хеширования (телефон, email, etc.)
        key: ключ HMAC (SEARCH_HASH_KEY)

    Returns:
        hex-строка HMAC-SHA256
    """
    normalized = value.lower().strip()
    mac = hmac.new(key, normalized.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()
