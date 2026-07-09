from django.urls import include, path
from rest_framework_nested.routers import NestedSimpleRouter, SimpleRouter
from apps.accounts.views import (
    AuthViewSet,
    MembershipViewSet,
    PermissionViewSet,
    RoleAssignmentViewSet,
    RoleViewSet,
    UserMembershipReadOnlyViewSet,
    UserRoleAssignmentReadOnlyViewSet,
    UserViewSet,
)

router = SimpleRouter()
router.register(r"auth", AuthViewSet, basename="auth")
router.register(r"accounts/users", UserViewSet, basename="accounts-users")
router.register(r"accounts/roles", RoleViewSet, basename="accounts-roles")
router.register(r"accounts/permissions", PermissionViewSet, basename="accounts-permissions")
router.register(r"accounts/memberships", MembershipViewSet, basename="accounts-memberships")
router.register(r"accounts/role-assignments", RoleAssignmentViewSet, basename="accounts-role-assignments")

users_router = NestedSimpleRouter(router, r"accounts/users", lookup="user")
users_router.register(r"memberships", UserMembershipReadOnlyViewSet, basename="accounts-user-memberships")
users_router.register(r"role-assignments", UserRoleAssignmentReadOnlyViewSet, basename="accounts-user-role-assignments")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(users_router.urls)),
]
