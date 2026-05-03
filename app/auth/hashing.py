import bcrypt


def hash_password(plain: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False
