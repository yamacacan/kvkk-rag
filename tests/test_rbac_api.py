# HTTP seviyesi: Bearer kimlik, permission middleware (403), kapsam filtreli listeleme
# ve kayit seviyesi 403. Uygulama GraphQL'siz kurulur (strawberry gerekmez); agir
# moduller (torch/lancedb) yalnizca ilgili uclarda tembel yuklenir.
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

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="kvkk_rbac_api_"))
settings.SQLITE_PATH = _TMP / "api.db"
os.environ["KVKK_ADMIN_EMAIL"] = "admin@test.local"
os.environ["KVKK_ADMIN_PASSWORD"] = "admin-sifre-123"

from kvkk_rag.api.app.Services import hashing  # noqa: E402
from kvkk_rag.api.app.Services.permission_cache import MemoryStore, cache  # noqa: E402
from kvkk_rag.api.database import connection  # noqa: E402
from kvkk_rag.inventory import store as inv_store  # noqa: E402

hashing.ITERATIONS = 1000


@unittest.skipIf(httpx is None or not hasattr(httpx, "ASGITransport"), "httpx.ASGITransport gerekli")
class TestRbacApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kvkk_rag.api import bootstrap

        settings.SQLITE_PATH = _TMP / "api.db"  # diger test modulleri yolu degistirmis olabilir
        connection.reset()
        cache.store = MemoryStore()
        cls.app = bootstrap.create_app(graphql=False, static=False, seed=False)
        conn = connection.connect()
        for birim in ("İK", "İK", "Pazarlama"):
            inv_store.create(conn, {"birim": birim, "faaliyet": "İşe alım", "kisisel_veri": "Ad"}, kaynak="xlsx")
        conn.close()
        bootstrap.migrate_and_seed()  # roller, izinler, kapsamlar, departmanlar (envanterden), admin

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP, ignore_errors=True)

    # ---- yardimcilar ----
    def run_async(self, coro):
        return asyncio.run(coro)

    def client(self):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")

    async def login(self, c, email, password):
        r = await c.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]

    # ---- testler ----
    def test_akis(self):
        async def akis():
            async with self.client() as c:
                # saglik herkese acik; envanter jeton ister
                self.assertEqual((await c.get("/api/health")).status_code, 200)
                self.assertEqual((await c.get("/api/inventory")).status_code, 401)
                self.assertEqual((await c.get("/api/inventory", headers={"Authorization": "Bearer 1|yanlis"})).status_code, 401)
                r = await c.post("/api/auth/login", json={"email": "admin@test.local", "password": "yanlis"})
                self.assertEqual(r.status_code, 401)

                # admin: kapsam atlanir
                h, me = await self.login(c, "admin@test.local", "admin-sifre-123")
                self.assertTrue(me["is_super"])
                self.assertEqual(me["roles"], ["Superadmin"])
                r = await c.get("/api/inventory", headers=h)
                self.assertEqual((r.json()["toplam"], r.json()["kapsam"]), (3, "all"))

                # departmanlar envanterden turedi
                deps = (await c.get("/api/departments", headers=h)).json()["departmanlar"]
                ik = next(d["id"] for d in deps if d["name"] == "İK")

                # birim sorumlusu olustur (department kapsami)
                r = await c.post("/api/users", headers=h, json={
                    "name": "Ayşe", "email": "ayse@test.local", "password": "sifre1234",
                    "roles": ["Birim Sorumlusu"], "departments": [ik]})
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.json()["user"]["scopes"]["inventory"]["view"], "department")

                h2, me2 = await self.login(c, "ayse@test.local", "sifre1234")
                self.assertEqual(me2["departments"], ["İK"])
                r = await c.get("/api/inventory", headers=h2)
                self.assertEqual(r.json()["kapsam"], "department")
                self.assertEqual([s["birim"] for s in r.json()["satirlar"]], ["İK", "İK"])
                # kayit seviyesi: baska departmanin satiri 403, kendi satiri 200
                self.assertEqual((await c.get("/api/inventory/3", headers=h2)).status_code, 403)
                self.assertEqual((await c.get("/api/inventory/1", headers=h2)).status_code, 200)
                self.assertEqual((await c.patch("/api/inventory/3", headers=h2, json={"faaliyet": "x"})).status_code, 403)
                # olusturma: yalnizca kendi departmani
                r = await c.post("/api/inventory", headers=h2, json={"birim": "Pazarlama", "faaliyet": "x"})
                self.assertEqual(r.status_code, 403)
                r = await c.post("/api/inventory", headers=h2, json={"birim": "İK", "faaliyet": "Bordro"})
                self.assertEqual(r.status_code, 200, r.text)
                yeni = r.json()["satir_no"]
                # toplu silme: kapsam disi satir "yetkisiz" listesine duser
                r = await c.post("/api/inventory/bulk-delete", headers=h2, json={"satir_no": [3, yeni]})
                self.assertEqual((r.json()["silinen"], r.json()["yetkisiz"]), ([yeni], [3]))
                # izin yok -> 403 (permission middleware)
                self.assertEqual((await c.get("/api/users", headers=h2)).status_code, 403)
                self.assertEqual((await c.post("/api/inventory/reindex", headers=h2)).status_code, 403)

                # veri giris kullanicisi (own): kendi ekledigi disinda hicbir sey gormez
                r = await c.post("/api/users", headers=h, json={
                    "name": "Veli", "email": "veli@test.local", "password": "sifre1234", "roles": ["Veri Giriş"]})
                h3, _ = await self.login(c, "veli@test.local", "sifre1234")
                r = await c.get("/api/inventory", headers=h3)
                self.assertEqual((r.json()["toplam"], r.json()["kapsam"]), (0, "own"))
                r = await c.post("/api/inventory", headers=h3, json={"birim": "Satış", "faaliyet": "CRM"})
                self.assertEqual(r.status_code, 200, r.text)
                benim = r.json()["satir_no"]
                r = await c.get("/api/inventory", headers=h3)
                self.assertEqual([s["satir_no"] for s in r.json()["satirlar"]], [benim])
                self.assertEqual((await c.delete(f"/api/inventory/{benim}", headers=h3)).status_code, 403)  # delete izni yok
                self.assertEqual((await c.get("/api/inventory/summary", headers=h3)).json()["satir"], 1)

                # rol kapsamini degistir -> onbellek surumu artar, yeni istekte gecerli
                roller = (await c.get("/api/roles", headers=h)).json()["roller"]
                veri_rol = next(r for r in roller if r["name"] == "Veri Giriş")
                r = await c.put(f"/api/roles/{veri_rol['id']}/scopes", headers=h,
                                json={"scopes": [{"module": "inventory", "action": "view", "scope": "all"}]})
                self.assertEqual(r.status_code, 200, r.text)
                r = await c.get("/api/inventory", headers=h3)
                self.assertEqual(r.json()["kapsam"], "all")
                self.assertEqual(r.json()["toplam"], 4)
                r = await c.put(f"/api/roles/{veri_rol['id']}/scopes", headers=h,
                                json={"scopes": [{"module": "inventory", "action": "view", "scope": "yanlis"}]})
                self.assertEqual(r.status_code, 422)

                # yetki yukseltme onlemi: birim sorumlusu Admin rolu veremez (users.create yok zaten -> 403)
                r = await c.post("/api/users", headers=h2, json={
                    "name": "X", "email": "x@test.local", "password": "sifre1234", "roles": ["Admin"]})
                self.assertEqual(r.status_code, 403)

                # cikis: JWT kara listeye girer, ayni jeton artik gecersiz
                self.assertTrue((await c.post("/api/auth/logout", headers=h2)).json()["cikis"])
                self.assertEqual((await c.get("/api/inventory", headers=h2)).status_code, 401)

        self.run_async(akis())

    def test_jwt_yenileme_ve_sifre_sifirlama(self):
        async def akis():
            async with self.client() as c:
                r = await c.post("/api/auth/login", json={"email": "admin@test.local", "password": "admin-sifre-123"})
                d = r.json()
                self.assertEqual(d["token_type"], "Bearer")
                self.assertEqual(d["access_token"].count("."), 2)          # JWT: header.payload.imza
                self.assertIn("|", d["refresh_token"])                    # opak, DB'de ozetli
                # refresh jetonu erisim icin kullanilamaz
                r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {d['refresh_token']}"})
                self.assertEqual(r.status_code, 401)
                # yenileme: yeni cift, eski refresh tek kullanimlik
                r = await c.post("/api/auth/refresh", json={"refresh_token": d["refresh_token"]})
                self.assertEqual(r.status_code, 200, r.text)
                yeni = r.json()
                self.assertNotEqual(yeni["refresh_token"], d["refresh_token"])
                r = await c.post("/api/auth/refresh", json={"refresh_token": d["refresh_token"]})
                self.assertEqual(r.status_code, 401)
                h = {"Authorization": f"Bearer {yeni['access_token']}"}
                self.assertEqual((await c.get("/api/auth/me", headers=h)).status_code, 200)
                # kurcalanmis imza
                bozuk = yeni["access_token"][:-3] + "abc"
                self.assertEqual((await c.get("/api/auth/me", headers={"Authorization": f"Bearer {bozuk}"})).status_code, 401)

                # dogrulama mesajlari Turkce (422)
                r = await c.post("/api/auth/login", json={"email": "a"})
                self.assertEqual(r.status_code, 422)
                self.assertIn("errors", r.json())
                self.assertIn("password", r.json()["errors"])
                self.assertEqual(r.json()["errors"]["password"], ["Bu alan zorunludur."])

                # sifremi unuttum: kayitsiz e-posta da ayni yaniti alir (sayim yok)
                r = await c.post("/api/auth/forgot-password", json={"email": "yok@test.local"})
                self.assertEqual(r.status_code, 200)
                self.assertNotIn("gelistirme", r.json())
                r = await c.post("/api/auth/forgot-password", json={"email": "admin@test.local"})
                self.assertEqual(r.status_code, 200, r.text)
                url = r.json()["gelistirme"]["reset_url"]  # APP_ENV=local + MAIL_DRIVER=log
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(url).query)
                token, email = q["token"][0], q["email"][0]
                self.assertEqual(urlparse(url).path, "/sifre-sifirla")
                # e-posta gunluge/mailer.sent'e dustu
                from kvkk_rag.api.app.Services.mail_service import mailer
                self.assertTrue(any(m.to == "admin@test.local" and token in m.text for m in mailer.sent))

                # eslesmeyen tekrar -> 422 Turkce
                r = await c.post("/api/auth/reset-password", json={
                    "email": email, "token": token, "password": "yeni-sifre-1", "password_confirmation": "farkli"})
                self.assertEqual(r.status_code, 422)
                self.assertIn("eşleşmiyor", r.json()["detail"])
                # yanlis jeton
                r = await c.post("/api/auth/reset-password", json={
                    "email": email, "token": "x" * 20, "password": "yeni-sifre-1", "password_confirmation": "yeni-sifre-1"})
                self.assertEqual(r.status_code, 422)
                # dogru jeton: sifre degisir, acik oturumlar (refresh) duser, jeton tek kullanimlik
                r = await c.post("/api/auth/reset-password", json={
                    "email": email, "token": token, "password": "yeni-sifre-1", "password_confirmation": "yeni-sifre-1"})
                self.assertEqual(r.status_code, 200, r.text)
                r = await c.post("/api/auth/refresh", json={"refresh_token": yeni["refresh_token"]})
                self.assertEqual(r.status_code, 401)
                r = await c.post("/api/auth/reset-password", json={
                    "email": email, "token": token, "password": "yeni-sifre-2", "password_confirmation": "yeni-sifre-2"})
                self.assertEqual(r.status_code, 422)
                self.assertEqual((await c.post("/api/auth/login", json={"email": email, "password": "admin-sifre-123"})).status_code, 401)
                r = await c.post("/api/auth/login", json={"email": email, "password": "yeni-sifre-1"})
                self.assertEqual(r.status_code, 200)
                # diger testler eski sifreyi kullanir; geri al
                h = {"Authorization": f"Bearer {r.json()['access_token']}"}
                r = await c.patch(f"/api/users/{r.json()['user']['id']}", headers=h, json={"password": "admin-sifre-123"})
                self.assertEqual(r.status_code, 200, r.text)

        self.run_async(akis())


if __name__ == "__main__":
    unittest.main()
