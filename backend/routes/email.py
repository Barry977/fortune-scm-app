from fastapi import APIRouter, HTTPException
from models import EmailConfigure, EmailSend
from database import get_db_ctx
from services import email_service

router = APIRouter(prefix="/api/email", tags=["Email"])


@router.post("/configure")
async def configure(body: EmailConfigure):
    with get_db_ctx() as conn:
        for k, v in {
            "smtp_host": body.smtp_host,
            "smtp_port": str(body.smtp_port),
            "smtp_user": body.smtp_user,
            "smtp_password": body.smtp_password,
            "smtp_from": body.smtp_from,
        }.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
    return {"status": "configured"}


@router.post("/send")
async def send(body: EmailSend):
    with get_db_ctx() as conn:
        settings = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings").fetchall()}

    required = ["smtp_host", "smtp_user", "smtp_password", "smtp_from"]
    for k in required:
        if not settings.get(k):
            raise HTTPException(status_code=400, detail=f"SMTP not configured: missing {k}")

    result = await email_service.send_email(
        host=settings["smtp_host"],
        port=int(settings.get("smtp_port", 587)),
        user=settings["smtp_user"],
        password=settings["smtp_password"],
        from_addr=settings["smtp_from"],
        to=body.to,
        subject=body.subject,
        body=body.body,
        html=body.html,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result
