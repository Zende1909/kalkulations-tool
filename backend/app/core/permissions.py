from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.core.security import UserRole
from app.dependencies import get_current_user
from app.models.user import User


def require_roles(*roles: UserRole) -> Callable:
    allowed = {role.value for role in roles}

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unzureichende Berechtigungen",
            )
        return current_user

    return role_checker


require_viewer = require_roles(UserRole.VIEWER, UserRole.KALKULATOR, UserRole.ADMIN)
require_kalkulator = require_roles(UserRole.KALKULATOR, UserRole.ADMIN)
require_admin = require_roles(UserRole.ADMIN)
