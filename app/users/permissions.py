from rest_framework.permissions import BasePermission
from .app_choices import UserType


class IsUser(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.auth.user == obj


class IsShopOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in {'GET', 'POST'}:
            return True
        return request.auth.user == obj.owner


class IsPartner(BasePermission):
    def has_permission(self, request, view):
        return request.auth.user.type == UserType.seller


class IsBuyer(BasePermission):
    def has_permission(self, request, view):
        return request.auth.user.type == UserType.buyer
