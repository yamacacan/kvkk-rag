"""Sifre sifirlama e-postasi. SMTP'de gecikme istek suresine yansimasin diye
BackgroundTasks ile kuyruklanir; idempotenttir (ayni baglanti tekrar gonderilir,
yeni jeton uretilmez)."""
from __future__ import annotations

from ..Services.mail_service import Mail, mailer
from .base import Job


class SendPasswordResetMailJob(Job):
    def __init__(self, email: str, name: str, reset_url: str, ttl_minutes: int) -> None:
        self.email, self.name, self.reset_url, self.ttl_minutes = email, name, reset_url, ttl_minutes

    def handle(self) -> None:
        metin = (
            f"Merhaba {self.name},\n\n"
            f"Hesabınız için şifre sıfırlama talebi aldık. Yeni şifre belirlemek için bağlantıya tıklayın:\n\n"
            f"{self.reset_url}\n\n"
            f"Bağlantı {self.ttl_minutes} dakika geçerlidir. Talebi siz yapmadıysanız bu e-postayı yok sayabilirsiniz; "
            f"şifreniz değişmez.\n\nKVKK Uyum"
        )
        mailer.send(Mail(to=self.email, to_name=self.name, subject="KVKK Uyum — Şifre Sıfırlama", text=metin))
