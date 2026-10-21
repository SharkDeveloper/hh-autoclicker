"""
Утилиты безопасности: хеширование паролей, JWT, шифрование Fernet.
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Получение секретных ключей из переменных окружения
SECRET_KEY = os.environ.get("JWT_SECRET", "changeme_generate_with_openssl_rand")
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", 10080))

# Fernet ключ для шифрования паролей hh.ru
FERNET_KEY = os.environ.get("FERNET_KEY", "changeme_generate_with_fernet_keygen")
if FERNET_KEY:
    fernet = Fernet(FERNET_KEY.encode())
else:
    fernet = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверить соответствие пароля его хешу."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Получить хеш пароля."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создать JWT токен доступа.
    
    Args:
        data: данные для кодирования (обычно {"sub": user_id})
        expires_delta: время жизни токена
    
    Returns:
        Закодированный JWT токен
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Проверить JWT токен и вернуть payload.
    
    Returns:
        dict: payload токена или None при ошибке
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def encrypt_password(password: str) -> str:
    """
    Зашифровать пароль с помощью Fernet.
    
    Args:
        password: пароль в открытом виде
    
    Returns:
        Зашифрованная строка (base64)
    """
    if not fernet:
        raise ValueError("FERNET_KEY не установлен")
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    Расшифровать пароль, зашифрованный Fernet.
    
    Args:
        encrypted_password: зашифрованная строка
    
    Returns:
        Пароль в открытом виде
    """
    if not fernet:
        raise ValueError("FERNET_KEY не установлен")
    return fernet.decrypt(encrypted_password.encode()).decode()