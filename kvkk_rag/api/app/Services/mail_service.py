"""E-posta gonderimi (Laravel Mail). Suruculer:
  log  -> mesaj uygulama gunlugune yazilir (varsayilan; gelistirme)
  smtp -> KVKK_MAIL_HOST/PORT/USERNAME/PASSWORD/ENCRYPTION ile smtplib
Gonderim istek dongusunde degil, Jobs/send_password_reset_mail_job uzerinden
arka planda yapilir."""
from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr

logger = logging.getLogger("kvkk_rag.api.mail")


@dataclass
class Mail:
    to: str
    subject: str
    text: str
    to_name: str = ""
    html: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class Mailer:
    def __init__(self) -> None:
        self.driver = os.getenv("KVKK_MAIL_DRIVER", "log").strip().lower()
        self.from_address = os.getenv("KVKK_MAIL_FROM_ADDRESS", "kvkk@localhost").strip()
        self.from_name = os.getenv("KVKK_MAIL_FROM_NAME", "KVKK Uyum").strip()
        self.sent: list[Mail] = []  # log surucusunde son gonderimler (test/gelistirme)

    def send(self, mail: Mail) -> None:
        if self.driver == "smtp":
            self._smtp(mail)
        else:
            self._log(mail)
        self.sent.append(mail)
        if len(self.sent) > 50:
            del self.sent[:-50]

    def _log(self, mail: Mail) -> None:
        logger.info("[MAIL/log] Kime: %s <%s> | Konu: %s\n%s", mail.to_name, mail.to, mail.subject, mail.text)

    def _smtp(self, mail: Mail) -> None:
        host = os.getenv("KVKK_MAIL_HOST", "localhost")
        port = int(os.getenv("KVKK_MAIL_PORT", "587"))
        kullanici = os.getenv("KVKK_MAIL_USERNAME", "")
        sifre = os.getenv("KVKK_MAIL_PASSWORD", "")
        sifreleme = os.getenv("KVKK_MAIL_ENCRYPTION", "tls").lower()  # tls | ssl | none

        msg = EmailMessage()
        msg["From"] = formataddr((self.from_name, self.from_address))
        msg["To"] = formataddr((mail.to_name, mail.to)) if mail.to_name else mail.to
        msg["Subject"] = mail.subject
        for k, v in mail.headers.items():
            msg[k] = v
        msg.set_content(mail.text)
        if mail.html:
            msg.add_alternative(mail.html, subtype="html")

        if sifreleme == "ssl":
            smtp = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            smtp = smtplib.SMTP(host, port, timeout=20)
        with smtp:
            if sifreleme == "tls":
                smtp.starttls()
            if kullanici:
                smtp.login(kullanici, sifre)
            smtp.send_message(msg)


mailer = Mailer()
