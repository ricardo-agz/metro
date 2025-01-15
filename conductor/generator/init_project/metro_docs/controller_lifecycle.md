## Controller Lifecycle Hooks

Lifecycle hooks like `before_request` and `after_request` can be defined directly in a controller or inherited from a parent controller. Hooks are useful for tasks such as authentication, logging, or cleanup.

### Example: AdminController and AdminUserController

**`admin_controller.py`**
```python
from metro.controllers import Controller, before_request, after_request
from metro.exceptions import UnauthorizedError
from metro import Request

class AdminController(Controller):
    @before_request
    async def check_admin(self, request: Request):
        is_admin = False  # Replace with actual logic
        print("Checking admin status... (this will be run before each request)")
        if not is_admin:
            raise UnauthorizedError(detail="Unauthorized access.")

    @after_request
    async def cleanup_stuff(self, request: Request):
        print("Cleaning up... (this will be run after each request)")
```

**`admin_user_controller.py`**
```python
from app.controllers.admin_controller import AdminController

class AdminUserController(AdminController):
    @get('/admin-user/all-users')
    async def all_users(self, request):
        return {"users": []}
```

### Key Points:
- Hooks like `check_admin` and `after_request` can be defined directly in a controller or inherited from a parent.
- In `AdminUserController`, hooks are inherited from `AdminController` and run before and after each request handler.

### Execution:
- If a `before_request` hook raises an exception (e.g., `UnauthorizedError`), the request handler is skipped, but the `after_request` hook still runs.
