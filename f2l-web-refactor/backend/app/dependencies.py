"""
FastAPI dependency injection utilities.
Provides database sessions, authentication, and other shared dependencies.
"""
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()


# Database Dependencies
# ---------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    Yields:
        AsyncSession: Database session

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    # TODO: Implement database session management
    # from app.database.session import async_session_maker
    # async with async_session_maker() as session:
    #     try:
    #         yield session
    #         await session.commit()
    #     except Exception:
    #         await session.rollback()
    #         raise
    #     finally:
    #         await session.close()

    # Placeholder for now
    raise NotImplementedError("Database session not implemented yet")


# Authentication Dependencies
# ---------------------------

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Get current user from JWT token (optional).
    Returns None if no token or invalid token.

    Args:
        credentials: HTTP Authorization credentials

    Returns:
        User dict or None
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        # TODO: Load user from database
        return {"id": user_id, "email": payload.get("email")}

    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Get current user from JWT token (required).
    Raises 401 if no token or invalid token.

    Args:
        credentials: HTTP Authorization credentials

    Returns:
        User dict

    Raises:
        HTTPException: 401 Unauthorized
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # TODO: Load user from database
        return {"id": user_id, "email": payload.get("email")}

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current active user.
    Checks if user is active/enabled.

    Args:
        current_user: Current user from token

    Returns:
        User dict

    Raises:
        HTTPException: 400 if user is inactive
    """
    # TODO: Check if user is active in database
    is_active = current_user.get("is_active", True)

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return current_user


# Redis Dependencies
# ------------------

async def get_redis():
    """
    Dependency to get Redis connection.

    Yields:
        Redis client
    """
    # TODO: Implement Redis connection management
    # from app.core.redis import redis_client
    # yield redis_client
    raise NotImplementedError("Redis connection not implemented yet")


# Pagination Dependencies
# -----------------------

async def get_pagination_params(
    page: int = 1,
    limit: int = 50
) -> dict:
    """
    Get pagination parameters with validation.

    Args:
        page: Page number (default: 1)
        limit: Items per page (default: 50, max: 100)

    Returns:
        Dict with validated pagination params
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be >= 1"
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100"
        )

    return {
        "page": page,
        "limit": limit,
        "offset": (page - 1) * limit
    }
