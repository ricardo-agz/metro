import re
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Union, Any, Type, Pattern, ClassVar
from metro.models import (
    BaseModel,
    EmbeddedDocument,
    EmbeddedDocumentListField,
    StringField,
    ListField,
    DateTimeField,
    ReferenceField,
    DictField,
)
from metro.auth.user.mixins.typing import T


class Permission(EmbeddedDocument):
    """Represents a permission with optional resource constraints"""

    VALID_PERMISSION_PATTERN: Pattern = re.compile(r"^[a-z]+(\.[a-z]+)*(\.\*)?$")

    name = StringField(required=True)  # e.g. "posts.create"
    resource_id = StringField()  # Optional resource-specific permission
    constraints = DictField()  # Additional constraints
    granted_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField()  # Optional expiration

    @classmethod
    def validate_permission_name(cls, name: str) -> bool:
        return bool(cls.VALID_PERMISSION_PATTERN.match(name))

    def clean(self):
        super().clean()
        if not self.validate_permission_name(self.name):
            raise ValueError(
                f"Invalid permission format: {self.name}. "
                "Must be lowercase, dot-separated, optionally ending with '*'"
            )


class RoleAssignment(EmbeddedDocument):
    """Represents a role assigned to a user"""

    name = StringField(required=True)
    granted_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField()
    granted_by = ReferenceField("User")  # Who granted this role


class RolePermissionMixin:
    """Mixin for role-based permissions"""

    # Static role definitions - to be extended by developer
    ROLE_PERMISSIONS: ClassVar[dict[str, set[str]]] = {}

    # Dynamic assignments
    roles = EmbeddedDocumentListField(RoleAssignment)
    permissions = EmbeddedDocumentListField(Permission)

    meta = {
        "abstract": True,
        "indexes": [
            "roles.name",
            "roles.expires_at",
            "permissions.name",
            "permissions.resource_id",
            "permissions.expires_at",
        ],
    }

    def assign_role(
        self: T,
        role_name: str | Enum,
        granted_by: Optional["BaseModel"] = None,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """Assign a role to the user"""
        role_name = role_name.value if isinstance(role_name, Enum) else role_name

        # Verify role exists in static definitions
        if role_name not in self.ROLE_PERMISSIONS:
            raise ValueError(f"Role {role_name} does not exist")

        # Remove existing role assignment if any
        self.roles = [r for r in self.roles if r.name != role_name]

        # Add new role assignment
        self.roles.append(
            RoleAssignment(name=role_name, granted_by=granted_by, expires_at=expires_at)
        )
        self.save()
        return True

    def assign_temp_role(
        self,
        role_name: str | Enum,
        expires_in: timedelta,
        granted_by: Optional["BaseModel"] = None,
    ) -> bool:
        """Assign a temporary role that expires after a duration"""
        return self.assign_role(
            role_name, granted_by=granted_by, expires_at=datetime.utcnow() + expires_in
        )

    def remove_role(self: T, role_name: str | Enum) -> bool:
        """Remove a role from the user"""
        role_name = role_name.value if isinstance(role_name, Enum) else role_name
        initial_count = len(self.roles)
        self.roles = [r for r in self.roles if r.name != role_name]
        if len(self.roles) != initial_count:
            self.save()
            return True
        return False

    def get_active_roles(self) -> list[str]:
        """Get all active (non-expired) roles"""
        now = datetime.utcnow()
        return [r.name for r in self.roles if not r.expires_at or r.expires_at > now]

    def has_role(self, role_name: str | Enum) -> bool:
        """Check if user has a specific role"""
        role_name = role_name.value if isinstance(role_name, Enum) else role_name
        return role_name in self.get_active_roles()

    def get_permissions(self) -> set[str]:
        """Get all permissions from all active roles"""
        permissions = set()
        for role_name in self.get_active_roles():
            if role_name in self.ROLE_PERMISSIONS:
                permissions.update(self.ROLE_PERMISSIONS[role_name])
        return permissions

    @staticmethod
    def _check_wildcard_permission(permission: str, permissions: set[str]) -> bool:
        """Check if permission is covered by any wildcards"""
        if "*" in permissions:
            return True

        parts = permission.split(".")
        wildcards = [
            ".".join(parts[:-1] + ["*"]),  # e.g., "posts.*"
        ]
        return any(wp in permissions for wp in wildcards)

    def has_permission(
        self,
        permission: str | Enum,
        resource_id: Optional[str] = None,
        **constraints,
    ) -> bool:
        """
        Check if user has a specific permission

        Args:
            permission: Permission name to check
            resource_id: Optional resource-specific permission check
            **constraints: Additional permission constraints
        """
        permission = permission.value if isinstance(permission, Enum) else permission

        # Check static role-based permissions first (including wildcards)
        role_permissions = self.get_permissions()
        if self._check_wildcard_permission(permission, role_permissions):
            return True
        if permission in role_permissions:
            return True

        # Then check dynamic direct permissions
        now = datetime.utcnow()
        for p in self.permissions:
            if (
                p.name == permission
                and (not p.expires_at or p.expires_at > now)
                and (not resource_id or p.resource_id == resource_id)
                and all(p.constraints.get(k) == v for k, v in constraints.items())
            ):
                return True

        return False

    def has_all_permissions(self, permissions: list[str | Enum]) -> bool:
        """Check if user has all specified permissions"""
        return all(self.has_permission(p) for p in permissions)

    def has_any_permission(self, permissions: list[str | Enum]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(self.has_permission(p) for p in permissions)

    def grant_permission(
        self: T,
        permission: str | Enum,
        resource_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        **constraints,
    ) -> None:
        """Grant a specific permission to the user"""
        permission = permission.value if isinstance(permission, Enum) else permission
        self.permissions.append(
            Permission(
                name=permission,
                resource_id=resource_id,
                constraints=constraints,
                expires_at=expires_at,
            )
        )
        self.save()

    def revoke_permission(
        self: T, permission: str | Enum, resource_id: str | None = None
    ) -> None:
        """Revoke a specific permission from the user"""
        permission = permission.value if isinstance(permission, Enum) else permission
        self.permissions = [
            p
            for p in self.permissions
            if p.name != permission or p.resource_id != resource_id
        ]
        self.save()
