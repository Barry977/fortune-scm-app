import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


async def send_email(host: str, port: int, user: str, password: str,
                     from_addr: str, to: str, subject: str, body: str, html: bool = False) -> dict:
    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject

    if html:
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            if port != 465:
                server.starttls()
                server.ehlo()
            server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        return {"status": "sent", "to": to}
    except Exception as e:
        logger.error(f"Email error: {e}")
        return {"status": "error", "error": str(e)}
