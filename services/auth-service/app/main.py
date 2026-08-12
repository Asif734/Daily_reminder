from reminder_common.web import create_service_app

from app.api.auth import router as auth_router
from app.api.users import device_router
from app.api.users import router as users_router

app = create_service_app("auth-service")
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(device_router)
