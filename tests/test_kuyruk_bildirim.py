# Kuyruk (jobs), olay veriyolu / dinleyiciler, bildirimler ve denetim gunlugu kapsami:
# belge uretimi arka planda (GenerateDocumentJob), hazir olunca bildirim + gunluk;
# envanter yazimlari, sayfa goruntulemeleri ve cikis gunluge duser.
import asyncio
import os
import pathlib
import shutil
import tempfile
import unittest

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

from kvkk_rag.config import settings

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="kvkk_kuyruk_"))
settings.SQLITE_PATH = _TMP / "kuyruk.db"
settings.INDEX_DIR = _TMP / "index"
os.environ["KVKK_ADMIN_EMAIL"] = "admin@test.local"
os.environ["KVKK_ADMIN_PASSWORD"] = "admin-sifre-123"

from kvkk_rag.api.app import Events  # noqa: E402
from kvkk_rag.api.app.Jobs.base import Job, ShouldQueue  # noqa: E402
from kvkk_rag.api.app.Models.audit_log import AuditLog  # noqa: E402
from kvkk_rag.api.app.Models.generated_document import GeneratedDocument  # noqa: E402
from kvkk_rag.api.app.Models.job import Job as JobRow  # noqa: E402
from kvkk_rag.api.app.Models.notification import Notification  # noqa: E402
from kvkk_rag.api.app.Services import hashing  # noqa: E402
from kvkk_rag.api.app.Services.permission_cache import MemoryStore, cache  # noqa: E402
from kvkk_rag.api.app.Services.queue import Queue, Worker  # noqa: E402
from kvkk_rag.api.database import connection  # noqa: E402

hashing.ITERATIONS = 1000
CALISAN: list[str] = []


class OrnekIs(Job, ShouldQueue):
    max_attempts = 2
    retry_after = 0

    def __init__(self, ad: str, patlat: bool = False) -> None:
        self.ad, self.patlat = ad, patlat

    def handle(self) -> None:
        if self.patlat:
            raise RuntimeError("bilerek")
        CALISAN.append(self.ad)


@unittest.skipIf(httpx is None or not hasattr(httpx, "ASGITransport"), "httpx.ASGITransport gerekli")
class TestKuyrukBildirim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kvkk_rag.api import bootstrap

        settings.SQLITE_PATH = _TMP / "kuyruk.db"
        settings.INDEX_DIR = _TMP / "index"
        connection.reset()
        cache.store = MemoryStore()
        cls.app = bootstrap.create_app(graphql=False, static=False, seed=False, worker=False)
        bootstrap.migrate_and_seed()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP, ignore_errors=True)

    def client(self):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")

    async def login(self, c, email, password):
        r = await c.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        return {"Authorization": f"Bearer {d['access_token']}"}, d

    # ---- kuyruk cekirdegi ----
    def test_kuyruk_calistirma_ve_tekrar(self):
        conn = connection.connect()
        try:
            # baska testlerden kalan (faaliyet belgesi vb.) isleri once bitir
            while Worker.run_once(conn):
                pass
            CALISAN.clear()
            j1 = Queue.push(OrnekIs("a"), conn=conn)
            j2 = Queue.push(OrnekIs("b", patlat=True), conn=conn)
            self.assertEqual(JobRow.find(conn, j1.id).status, "queued")
            self.assertTrue(Worker.run_once(conn))
            self.assertEqual(CALISAN, ["a"])
            self.assertEqual(JobRow.find(conn, j1.id).status, "done")
            # patlayan is: 1. deneme -> tekrar kuyruga (max_attempts=2), 2. deneme -> failed
            self.assertTrue(Worker.run_once(conn))
            self.assertEqual(JobRow.find(conn, j2.id).status, "queued")
            self.assertTrue(Worker.run_once(conn))
            j2 = JobRow.find(conn, j2.id)
            self.assertEqual(j2.status, "failed")
            self.assertIn("bilerek", j2.error)
            self.assertFalse(Worker.run_once(conn))  # kuyruk bos
            # kalici hata -> denetim gunlugu (queue.failed)
            self.assertTrue(AuditLog.query(conn).where("action", "queue.failed").where("target_id", str(j2.id)).exists())
            # yeniden kuyruga al
            j2.retry(conn)
            self.assertEqual(JobRow.find(conn, j2.id).status, "queued")
        finally:
            conn.close()

    def test_olay_veriyolu_joker_dinleyici(self):
        yakalanan = []

        class Joker:
            def handle(self, e):
                yakalanan.append(type(e).__name__)

        class Patlayan:
            def handle(self, e):
                raise RuntimeError("dinleyici hatasi")

        Events.listen(Events.Event, Joker())
        Events.listen(Events.PermissionsChanged, Patlayan())
        try:
            n = Events.dispatch(Events.PermissionsChanged(reason="test"))
            self.assertIn("PermissionsChanged", yakalanan)
            self.assertGreaterEqual(n, 1)  # patlayan dinleyici digerlerini engellemedi
        finally:
            Events._dinleyiciler[Events.Event] = [l for l in Events._dinleyiciler.get(Events.Event, []) if not isinstance(l, Joker)]
            Events._dinleyiciler[Events.PermissionsChanged] = [
                l for l in Events._dinleyiciler.get(Events.PermissionsChanged, []) if not isinstance(l, Patlayan)]

    # ---- API akisi ----
    def test_belge_kuyrugu_bildirim_ve_gunluk(self):
        async def akis():
            async with self.client() as c:
                h, giris = await self.login(c, "admin@test.local", "admin-sifre-123")
                uid = giris["user"]["id"]

                # envanter girisi -> inventory.create gunluge
                r = await c.post("/api/inventory", headers=h, json={"birim": "İK", "faaliyet": "İşe alım",
                                                                   "kisisel_veri": "Ad Soyad", "veri_kategorisi": "Kimlik"})
                self.assertEqual(r.status_code, 200, r.text)
                satir = r.json()["satir_no"]
                r = await c.patch(f"/api/inventory/{satir}", headers=h, json={"saklama_suresi": "5 yıl"})
                self.assertEqual(r.status_code, 200, r.text)

                # sayfa goruntuleme -> page.view
                r = await c.post("/api/audit-logs/page-view", headers=h,
                                 json={"path": "/belgeler", "name": "belgeler", "title": "Uyum Belgeleri"})
                self.assertEqual(r.status_code, 200, r.text)

                # belge istegi -> 202, kayit kuyrukta, is kuyrukta
                r = await c.post("/api/documents/generate", headers=h,
                                 json={"sablon": "aydinlatma", "kurum": "TEST A.Ş.", "faaliyet": "İşe alım"})
                self.assertEqual(r.status_code, 202, r.text)
                d = r.json()
                self.assertTrue(d["kuyrukta"])
                belge_id, job_id = d["belge"]["id"], d["job_id"]
                self.assertEqual(d["belge"]["durum"], "kuyrukta")

                r = await c.get("/api/documents/uretilen", headers=h)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["bekleyen"], 1)

                # hazir olmadan indirme -> 409
                r = await c.get(f"/api/documents/uretilen/{belge_id}/indir", headers=h)
                self.assertEqual(r.status_code, 409)

                # kuyruk gozlemi (audit.view)
                r = await c.get("/api/queue", headers=h)
                self.assertEqual(r.status_code, 200, r.text)
                self.assertGreaterEqual(r.json()["durum"]["queued"], 1)

                # worker'i elle calistir (testte thread yok)
                conn = connection.connect()
                try:
                    while Worker.run_once(conn):  # kuyrukta faaliyet belgesi isleri de olabilir
                        pass
                    job = JobRow.find(conn, job_id)
                    belge = GeneratedDocument.find(conn, belge_id)
                finally:
                    conn.close()
                self.assertEqual(job.status, "done", job.error)
                self.assertEqual(belge.durum, "hazir", belge.hata)
                self.assertTrue(belge.ready)

                # bildirim dustu
                r = await c.get("/api/notifications", headers=h)
                self.assertEqual(r.status_code, 200)
                hazir = [b for b in r.json()["bildirimler"]
                         if b["type"] == "documents.ready" and b["data"]["belge_id"] == belge_id]
                self.assertEqual(len(hazir), 1)
                self.assertFalse(hazir[0]["okundu"])
                okunmamis_once = r.json()["okunmamis"]
                self.assertGreaterEqual(okunmamis_once, 1)
                nid = hazir[0]["id"]

                # indir
                r = await c.get(f"/api/documents/uretilen/{belge_id}/indir", headers=h)
                self.assertEqual(r.status_code, 200, r.text)
                self.assertIn("wordprocessingml", r.headers["content-type"])
                self.assertGreater(len(r.content), 1000)

                # bildirimi oku / hepsini oku / sayac
                r = await c.post(f"/api/notifications/{nid}/read", headers=h)
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.json()["bildirim"]["okundu"])
                r = await c.get("/api/notifications/unread-count", headers=h)
                self.assertEqual(r.json()["okunmamis"], okunmamis_once - 1)
                r = await c.post("/api/notifications/read-all", headers=h)
                self.assertEqual(r.status_code, 200)
                r = await c.get("/api/notifications/unread-count", headers=h)
                self.assertEqual(r.json()["okunmamis"], 0)

                # "Tum bildirimler" sayfasi: filtre + sayfalama + geri okunmamis yap + okunmuslari temizle
                r = await c.get("/api/notifications", headers=h, params={"durum": "okunmus", "limit": 1, "offset": 0})
                d = r.json()
                self.assertEqual(r.status_code, 200)
                self.assertEqual(len(d["bildirimler"]), 1)
                self.assertGreaterEqual(d["toplam"], 1)
                self.assertIn("documents.ready", d["turler"])
                r = await c.get("/api/notifications", headers=h, params={"tur": "documents.ready", "arama": "hazır"})
                self.assertTrue(all(b["type"] == "documents.ready" for b in r.json()["bildirimler"]))
                r = await c.get("/api/notifications", headers=h, params={"durum": "okunmamis"})
                self.assertEqual(r.json()["bildirimler"], [])
                r = await c.post(f"/api/notifications/{nid}/unread", headers=h)
                self.assertEqual(r.status_code, 200)
                self.assertFalse(r.json()["bildirim"]["okundu"])
                r = await c.post("/api/notifications/clear-read", headers=h)
                self.assertEqual(r.status_code, 200)
                r = await c.get("/api/notifications", headers=h)
                self.assertEqual([b["id"] for b in r.json()["bildirimler"]], [nid])  # okunmamis olan kaldi
                await c.post(f"/api/notifications/{nid}/read", headers=h)

                # baskasinin bildirimi / belgesi erisilemez
                r = await c.post("/api/users", headers=h, json={"name": "Ayşe", "email": "ayse@test.local",
                                                                 "password": "ayse-sifre-123", "roles": ["Denetçi"]})
                self.assertEqual(r.status_code, 200, r.text)
                h2, _ = await self.login(c, "ayse@test.local", "ayse-sifre-123")
                r = await c.post(f"/api/notifications/{nid}/read", headers=h2)
                self.assertEqual(r.status_code, 403)
                r = await c.get(f"/api/documents/uretilen/{belge_id}", headers=h2)
                self.assertEqual(r.status_code, 403)

                # cikis -> auth.logout
                r = await c.post("/api/auth/logout", headers=h2)
                self.assertEqual(r.status_code, 200)

                # denetim gunlugu: tum eylemler
                r = await c.get("/api/audit-logs", headers=h, params={"limit": 200})
                self.assertEqual(r.status_code, 200)
                eylemler = {k["action"] for k in r.json()["kayitlar"]}
                for e in ("inventory.create", "inventory.update", "page.view", "documents.generate",
                          "documents.ready", "auth.logout", "users.create"):
                    self.assertIn(e, eylemler, e)
                # sayfa goruntulemeleri gizlenebilir
                r = await c.get("/api/audit-logs", headers=h, params={"sayfa_goruntuleme": "false", "limit": 200})
                self.assertNotIn("page.view", {k["action"] for k in r.json()["kayitlar"]})

                # belge sil -> dosya da gider
                yol = belge.path
                r = await c.delete(f"/api/documents/uretilen/{belge_id}", headers=h)
                self.assertEqual(r.status_code, 200)
                self.assertFalse(yol.exists())

        asyncio.run(akis())

    def test_belge_hatasi_bildirim(self):
        async def akis():
            async with self.client() as c:
                h, giris = await self.login(c, "admin@test.local", "admin-sifre-123")
                r = await c.post("/api/documents/generate", headers=h,
                                 json={"sablon": "olmayan-sablon", "kurum": "TEST A.Ş."})
                self.assertEqual(r.status_code, 404)
                # gecerli sablon ama sablon dosyasi yoksa is 'hata' ile biter ve bildirim duser
                r = await c.post("/api/documents/generate-all", headers=h,
                                 json={"sablon": "aydinlatma", "kurum": "TEST A.Ş.", "birim": "Olmayan Birim"})
                self.assertEqual(r.status_code, 202, r.text)
                belge_id = r.json()["belge"]["id"]
                conn = connection.connect()
                try:
                    while Worker.run_once(conn):
                        pass
                    belge = GeneratedDocument.find(conn, belge_id)
                    self.assertEqual(belge.durum, "hata")
                    self.assertIn("faaliyet bulunamadı", belge.hata)
                    n = Notification.query(conn).where("user_id", giris["user"]["id"]).where("type", "documents.failed").first()
                    self.assertIsNotNone(n)
                    self.assertTrue(AuditLog.query(conn).where("action", "documents.failed").exists())
                finally:
                    conn.close()

        asyncio.run(akis())


if __name__ == "__main__":
    unittest.main()
