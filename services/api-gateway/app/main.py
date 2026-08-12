import httpx
from fastapi import Request, Response
from reminder_common.web import create_service_app

app = create_service_app("api-gateway")


@app.get("/api/v1", tags=["system"])
async def api_root() -> dict[str, str]:
    return {"name": "reminder-platform", "version": "v1"}


@app.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def proxy(path: str, request: Request) -> Response:
    settings = request.app.state.settings
    service_url = (
        settings.reminder_service_url
        if path.startswith(("reminders", "reminder-occurrences", "me/reminders", "reports"))
        else settings.auth_service_url
    )
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    headers["X-Request-ID"] = request.headers.get("X-Request-ID", "")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            upstream = await client.request(
                request.method,
                f"{service_url}/api/v1/{path}",
                params=request.query_params,
                content=await request.body(),
                headers=headers,
            )
        except httpx.RequestError:
            return Response(
                content='{"success":false,"error":{"code":"SERVICE_UNAVAILABLE","message":"Upstream service is unavailable."}}',
                status_code=503,
                media_type="application/json",
            )
    response_headers = {}
    if correlation_id := upstream.headers.get("X-Request-ID"):
        response_headers["X-Request-ID"] = correlation_id
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
