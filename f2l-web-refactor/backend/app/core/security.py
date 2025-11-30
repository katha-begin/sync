"""
Security utilities for F2L Web Refactor.
Handles password encryption/decryption and other security operations.
"""
import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet
from app.config import settings

logger = logging.getLogger(__name__)


class SecurityManager:
    """Handles encryption/decryption operations."""
    
    def __init__(self):
        """Initialize security manager with encryption key."""
        try:
            # Get encryption key from settings
            key_bytes = settings.ENCRYPTION_KEY.encode() if isinstance(settings.ENCRYPTION_KEY, str) else settings.ENCRYPTION_KEY
            self.fernet = Fernet(key_bytes)
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise ValueError("Invalid encryption key. Generate with: Fernet.generate_key()")

    def encrypt_password(self, password: str) -> str:
        """
        Encrypt password for storage.
        
        Args:
            password: Plain text password
            
        Returns:
            Encrypted password as base64 string
        """
        try:
            encrypted_bytes = self.fernet.encrypt(password.encode())
            return base64.b64encode(encrypted_bytes).decode()
        except Exception as e:
            logger.error(f"Password encryption failed: {e}")
            raise

    def decrypt_password(self, encrypted_password: str) -> str:
        """
        Decrypt password for use.
        
        Args:
            encrypted_password: Encrypted password as base64 string
            
        Returns:
            Decrypted plain text password
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_password.encode())
            decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Password decryption failed: {e}")
            raise


# Global security manager instance
_security_manager = None


def get_security_manager() -> SecurityManager:
    """Get global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


def encrypt_password(password: str) -> str:
    """
    Encrypt password for storage.
    
    Args:
        password: Plain text password
        
    Returns:
        Encrypted password as base64 string
    """
    return get_security_manager().encrypt_password(password)


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt password for use.
    
    Args:
        encrypted_password: Encrypted password as base64 string
        
    Returns:
        Decrypted plain text password
    """
    return get_security_manager().decrypt_password(encrypted_password)


def generate_encryption_key() -> str:
    """
    Generate new encryption key.
    
    Returns:
        Base64 encoded encryption key
    """
    key = Fernet.generate_key()
    return key.decode()


# JWT Token utilities (placeholder for future implementation)

def create_access_token(data: dict) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Token payload data
        
    Returns:
        JWT token string
    """
    # TODO: Implement JWT token creation
    raise NotImplementedError("JWT token creation not implemented yet")


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Token payload or None if invalid
    """
    # TODO: Implement JWT token verification
    raise NotImplementedError("JWT token verification not implemented yet")


# Password validation utilities

def validate_password_strength(password: str) -> dict:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        Dictionary with validation results
    """
    result = {
        'valid': True,
        'score': 0,
        'issues': []
    }
    
    if len(password) < 8:
        result['valid'] = False
        result['issues'].append('Password must be at least 8 characters long')
    else:
        result['score'] += 1
    
    if not any(c.isupper() for c in password):
        result['issues'].append('Password should contain uppercase letters')
    else:
        result['score'] += 1
    
    if not any(c.islower() for c in password):
        result['issues'].append('Password should contain lowercase letters')
    else:
        result['score'] += 1
    
    if not any(c.isdigit() for c in password):
        result['issues'].append('Password should contain numbers')
    else:
        result['score'] += 1
    
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        result['issues'].append('Password should contain special characters')
    else:
        result['score'] += 1
    
    return result


# API Key utilities (for future external API access)

def generate_api_key() -> str:
    """
    Generate API key for external access.
    
    Returns:
        Generated API key
    """
    import secrets
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage.
    
    Args:
        api_key: Plain API key
        
    Returns:
        Hashed API key
    """
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """
    Verify API key against hash.
    
    Args:
        api_key: Plain API key
        hashed_key: Stored hash
        
    Returns:
        True if valid, False otherwise
    """
    return hash_api_key(api_key) == hashed_key


# Rate limiting utilities (placeholder)

class RateLimiter:
    """Rate limiter for API endpoints."""
    
    def __init__(self, max_requests: int = 100, window_minutes: int = 1):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_minutes: Time window in minutes
        """
        self.max_requests = max_requests
        self.window_minutes = window_minutes
        self.requests = {}  # In production, use Redis
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed.
        
        Args:
            identifier: Client identifier (IP, user ID, etc.)
            
        Returns:
            True if allowed, False if rate limited
        """
        # TODO: Implement proper rate limiting with Redis
        return True
    
    def get_remaining(self, identifier: str) -> int:
        """
        Get remaining requests for identifier.
        
        Args:
            identifier: Client identifier
            
        Returns:
            Number of remaining requests
        """
        # TODO: Implement
        return self.max_requests


# Global rate limiter instance
rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_PER_MINUTE,
    window_minutes=1
)
