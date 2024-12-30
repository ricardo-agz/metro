import inspect
import os
import pkgutil
import importlib
import traceback
from typing import Type, Optional

from fastapi import Form
from starlette.responses import RedirectResponse

from pyrails.auth import AbstractUser
from pyrails.controllers import Controller, get, post, delete
from pyrails import Request
from pyrails.config import config
from pyrails.admin.templates import templates
from pyrails.admin.find_auth_class import find_auth_class
from pyrails.logger import logger


class AdminPanelAuthController(Controller):
    def __init__(self):
        super().__init__()
        self.admin_auth_class = find_auth_class()

        if config.JWT_SECRET_KEY == "PLEASE_CHANGE_ME" and config.ENV.lower() in ["prod", "production", "staging"]:
            logger.error("Config variable JWT_SECRET_KEY is still set to the default value. This is not secure. Please change it in your .env file.")
            raise Exception("Insecure JWT_SECRET_KEY. Please set this in your .env file to something secure.")

    @get(f"/auth{config.ADMIN_PANEL_ROUTE_PREFIX}/login")
    async def admin_login_page(self, request: Request):
        """Show admin login page"""
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": None}
        )

    @post(f"/auth{config.ADMIN_PANEL_ROUTE_PREFIX}/login")
    async def admin_login(
        self,
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        user = self.admin_auth_class.authenticate(username, password) if self.admin_auth_class else None
        if user:
            response = RedirectResponse(
                f"{config.ADMIN_PANEL_ROUTE_PREFIX}", status_code=302
            )
            response.set_cookie(
                "admin_token",
                user.get_auth_token(),
                httponly=True,
                secure=True,
                samesite="lax",
            )
            print(response)
            return response

        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid credentials"}
        )

    @delete(f"/auth{config.ADMIN_PANEL_ROUTE_PREFIX}/logout")
    async def admin_logout(self, request: Request):
        """Handle admin logout"""
        response = RedirectResponse(
            f"{config.ADMIN_PANEL_ROUTE_PREFIX}/login", status_code=302
        )
        response.delete_cookie("admin_token")
        return response
