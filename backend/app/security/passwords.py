"""
Хеширование и верификация паролей с bcrypt.
Rounds=12 — баланс между безопасностью и производительностью.
"""

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """
    Захешировать пароль с bcrypt.

    Args:
        password: пароль в открытом виде

    Returns:
        bcrypt хеш для хранения в БД
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверить пароль против хеша.

    Args:
        plain_password: пароль в открытом виде
        hashed_password: bcrypt хеш из БД

    Returns:
        True если пароль совпадает
    """
    return _pwd_context.verify(plain_password, hashed_password)
