from fastapi import Form
from starlette.responses import RedirectResponse

from pyrails.controllers import Controller, get, post, delete
from pyrails import Request
from pyrails.config import config
from pyrails.admin.templates import templates


class AdminPanelAuthController(Controller):
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
        """Handle admin login"""
        if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            response = RedirectResponse(
                f"{config.ADMIN_PANEL_ROUTE_PREFIX}", status_code=302
            )
            response.set_cookie(
                "admin_token",
                config.ADMIN_SECRET,
                httponly=True,
                secure=True,
                samesite="lax",
            )
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
