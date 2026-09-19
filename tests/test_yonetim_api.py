# Yonetim paneli uclari: dashboard, profil/sifre/oturumlar, birim uyeleri, rol klonlama,
# denetim gunlugu.
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

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="kvkk_yonetim_"))
settings.SQLITE_PATH = _TMP / "yonetim.db"
os.environ["KVKK_ADMIN_EMAIL"] = "admin@test.local"
os.environ["KVKK_ADMIN_PASSWORD"] = "admin-sifre-123"

from kvkk_rag.api.app.Services import hashing  # noqa: E402
from kvkk_rag.api.app.Services.permission_cache import MemoryStore, cache  # noqa: E402
from kvkk_rag.api.database import connection  # noqa: E402
from kvkk_rag.inventory import store as inv_store  # noqa: E402

hashing.ITERATIONS = 1000


@unittest.skipIf(httpx is None or not hasattr(httpx, "ASGITransport"), "httpx.ASGITransport gerekli")
class TestYonetimApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kvkk_rag.api import bootstrap

        settings.SQLITE_PATH = _TMP / "yonetim.db"
        connection.reset()
        cache.store = MemoryStore()
        cls.app = bootstrap.create_app(graphql=False, static=False, seed=False)
        conn = connection.connect()
        for birim in ("İK", "İK", "Pazarlama"):
            inv_store.create(conn, {"birim": birim, "faaliyet": "İşe alım", "kisisel_veri": "Ad"}, kaynak="xlsx")
        conn.close()
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

    def test_yonetim(self):
        async def akis():
            async with self.client() as c:
                h, giris = await self.login(c, "admin@test.local", "admin-sifre-123")

                # dashboard: admin tum bloklari gorur
                d = (await c.get("/api/dashboard", headers=h)).json()
                for blok in ("envanter", "riskli_faaliyetler", "yonetim", "denetim_gunlugu"):
                    self.assertIn(blok, d)
                self.assertEqual(d["envanter"]["satir"], 3)
                self.assertGreaterEqual(d["yonetim"]["aktif_oturum"], 1)

                # profil guncelle + denetim kaydi
                r = await c.patch("/api/auth/profile", headers=h, json={"name": "Yeni Ad"})
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.json()["user"]["name"], "Yeni Ad")
                r = await c.patch("/api/auth/profile", headers=h, json={"email": "bozuk"})
                self.assertEqual(r.status_code, 422)

                # oturumlar: ikinci giris -> iki oturum; mevcut isaretli
                h2, giris2 = await self.login(c, "admin@test.local", "admin-sifre-123")
                r = await c.get("/api/auth/sessions", headers=h2)
                oturumlar = r.json()["oturumlar"]
                self.assertEqual(len(oturumlar), 2)
                self.assertEqual([o["mevcut"] for o in oturumlar].count(True), 1)
                self.assertEqual(next(o for o in oturumlar if o["mevcut"])["id"], giris2["session_id"])
                # digerlerini kapat -> ilk oturumun refresh'i gecersiz
                r = await c.post("/api/auth/sessions/revoke-others", headers=h2)
                self.assertEqual(r.json()["iptal_edilen_oturum"], 1)
                r = await c.post("/api/auth/refresh", json={"refresh_token": giris["refresh_token"]})
                self.assertEqual(r.status_code, 401)

                # sifre degistir: yanlis mevcut -> 422; dogru -> yeni sifreyle giris
                r = await c.post("/api/auth/password", headers=h2, json={
                    "current_password": "yanlis", "password": "yeni-sifre-99", "password_confirmation": "yeni-sifre-99"})
                self.assertEqual(r.status_code, 422)
                r = await c.post("/api/auth/password", headers=h2, json={
                    "current_password": "admin-sifre-123", "password": "yeni-sifre-99", "password_confirmation": "yeni-sifre-99"})
                self.assertEqual(r.status_code, 200, r.text)
                h3, _ = await self.login(c, "admin@test.local", "yeni-sifre-99")

                # birim: olustur, uye ata, detay, yeniden adlandir (envanter birimi de degisir)
                r = await c.post("/api/users", headers=h3, json={
                    "name": "Ayşe", "email": "ayse@test.local", "password": "sifre1234", "roles": ["Birim Sorumlusu"]})
                ayse = r.json()["user"]["id"]
                deps = (await c.get("/api/departments", headers=h3)).json()["departmanlar"]
                ik = next(x for x in deps if x["name"] == "İK")
                self.assertEqual(ik["envanter_sayisi"], 2)
                r = await c.patch(f"/api/departments/{ik['id']}", headers=h3,
                                  json={"name": "İnsan Kaynakları", "description": "İK birimi", "users": [ayse]})
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual([u["id"] for u in r.json()["departman"]["users"]], [ayse])
                self.assertEqual(r.json()["departman"]["envanter_sayisi"], 2)  # birim adi envanterde guncellendi
                ha, me = await self.login(c, "ayse@test.local", "sifre1234")
                self.assertEqual(me["user"]["departments"], ["İnsan Kaynakları"])
                r = await c.get("/api/inventory", headers=ha)
                self.assertEqual(r.json()["toplam"], 2)
                # uyesi olan birim silinemez
                self.assertEqual((await c.delete(f"/api/departments/{ik['id']}", headers=h3)).status_code, 422)
                # ayse kendi departman uyeligini goremez (izin yok)
                self.assertEqual((await c.get("/api/departments", headers=ha)).status_code, 200)  # departments.view var
                self.assertEqual((await c.get("/api/audit-logs", headers=ha)).status_code, 403)

                # rol klonla
                roller = (await c.get("/api/roles", headers=h3)).json()["roller"]
                denetci = next(x for x in roller if x["name"] == "Denetçi")
                r = await c.post(f"/api/roles/{denetci['id']}/clone", headers=h3, json={"name": "Denetçi (Kopya)"})
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(sorted(r.json()["rol"]["permissions"]), sorted(denetci["permissions"]))
                self.assertEqual(r.json()["rol"]["scopes"], denetci["scopes"])
                kopya = r.json()["rol"]["id"]
                # kullanicisi olan rol silinemez; kopya silinebilir
                self.assertEqual((await c.delete(f"/api/roles/{kopya}", headers=h3)).status_code, 200)

                # denetim gunlugu: eylemler kaydedildi, filtre calisir
                r = await c.get("/api/audit-logs?limit=100", headers=h3)
                self.assertEqual(r.status_code, 200)
                eylemler = {k["action"] for k in r.json()["kayitlar"]}
                for e in ("auth.login", "auth.profile_update", "auth.password_change", "users.create",
                          "departments.update", "roles.clone", "roles.delete"):
                    self.assertIn(e, eylemler)
                r = await c.get("/api/audit-logs?action=users.&limit=10", headers=h3)
                self.assertTrue(all(k["action"].startswith("users.") for k in r.json()["kayitlar"]))
                self.assertGreaterEqual(r.json()["toplam"], 1)

        asyncio.run(akis())


if __name__ == "__main__":
    unittest.main()
