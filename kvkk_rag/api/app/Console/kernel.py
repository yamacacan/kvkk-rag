"""artisan benzeri komutlar:

  python -m kvkk_rag.api.app.Console migrate
  python -m kvkk_rag.api.app.Console db:seed [--no-admin] [--sync]
  python -m kvkk_rag.api.app.Console permission:cache-reset
  python -m kvkk_rag.api.app.Console jwt:secret            # .env icin KVKK_JWT_SECRET uret
  python -m kvkk_rag.api.app.Console user:create --email a@b.c --password ... --name "Ad" --role Denetçi
  python -m kvkk_rag.api.app.Console user:password --email a@b.c --password ...
  python -m kvkk_rag.api.app.Console user:role --email a@b.c --role "Birim Sorumlusu" [--remove]
  python -m kvkk_rag.api.app.Console user:department --email a@b.c --department "İK"
  python -m kvkk_rag.api.app.Console role:list
  python -m kvkk_rag.api.app.Console envanter:import [--force]
  python -m kvkk_rag.api.app.Console queue:work [--once] [--sleep 2] [--queue documents]
  python -m kvkk_rag.api.app.Console queue:status
  python -m kvkk_rag.api.app.Console queue:retry --id 12      # basarisiz isi yeniden kuyruga al
"""
from __future__ import annotations

import argparse
import json
import sys

from ...database.connection import connect
from ...database.migrations import migrate
from ...database.seeders import DatabaseSeeder
from ...resource import RoleResource
from ..Imports.envanter_import import EnvanterImport
from ..Models.department import Department
from ..Models.role import Role
from ..Models.user import User
from ..Models.job import FAILED, Job
from ..Services import queue as queue_service
from ..Services.permission_cache import flush_cache


def _yaz(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_migrate(_: argparse.Namespace) -> int:
    conn = connect()
    try:
        _yaz({"uygulanan": migrate(conn)})
    finally:
        conn.close()
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        _yaz(DatabaseSeeder.run(conn, with_admin=not args.no_admin, sync=args.sync))
    finally:
        conn.close()
    return 0


def cmd_jwt_secret(_: argparse.Namespace) -> int:
    import secrets
    print(f"KVKK_JWT_SECRET={secrets.token_urlsafe(48)}")
    print("# .env dosyasına ekleyin; değiştirmek tüm açık oturumları düşürür.", file=sys.stderr)
    return 0


def cmd_cache_reset(_: argparse.Namespace) -> int:
    _yaz({"surum": flush_cache()})
    return 0


def cmd_user_create(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        if User.find_by_email(conn, args.email):
            print("Bu e-posta zaten kayıtlı.", file=sys.stderr)
            return 1
        u = User.register(conn, args.name, args.email, args.password)
        if args.role:
            u.assign_role(conn, *args.role)
        if args.department:
            u.sync_departments(conn, [Department.find_or_create(conn, d).id for d in args.department])
        _yaz({"id": u.id, "email": u.email, "roles": u.role_names(conn),
              "departments": u.department_names(conn)})
    finally:
        conn.close()
    return 0


def cmd_user_password(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        u = User.find_by_email(conn, args.email)
        if not u:
            print("Kullanıcı bulunamadı.", file=sys.stderr)
            return 1
        u.set_password(conn, args.password)
        _yaz({"email": u.email, "sifre": "güncellendi"})
    finally:
        conn.close()
    return 0


def cmd_user_role(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        u = User.find_by_email(conn, args.email)
        if not u:
            print("Kullanıcı bulunamadı.", file=sys.stderr)
            return 1
        (u.remove_role if args.remove else u.assign_role)(conn, args.role)
        _yaz({"email": u.email, "roles": u.role_names(conn)})
    finally:
        conn.close()
    return 0


def cmd_user_department(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        u = User.find_by_email(conn, args.email)
        if not u:
            print("Kullanıcı bulunamadı.", file=sys.stderr)
            return 1
        d = Department.find_or_create(conn, args.department)
        ids = set(u.department_ids(conn))
        ids.discard(d.id) if args.remove else ids.add(d.id)
        u.sync_departments(conn, ids)
        _yaz({"email": u.email, "departments": u.department_names(conn)})
    finally:
        conn.close()
    return 0


def cmd_role_list(_: argparse.Namespace) -> int:
    conn = connect()
    try:
        _yaz(RoleResource.collection(Role.all(conn), conn=conn))
    finally:
        conn.close()
    return 0


def cmd_envanter_import(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        _yaz({"aktarilan_satir": EnvanterImport(force=args.force).run(conn)})
    finally:
        conn.close()
    return 0


def cmd_queue_work(args: argparse.Namespace) -> int:
    print("Kuyruk worker'ı çalışıyor (Ctrl+C ile durdurun)…", file=sys.stderr)
    n = queue_service.Worker.work(interval=args.sleep, once=args.once, queue=args.queue)
    _yaz({"islenen": n})
    return 0


def cmd_queue_status(_: argparse.Namespace) -> int:
    conn = connect()
    try:
        _yaz({"durum": Job.stats(conn),
              "basarisiz": [j.to_dict() for j in Job.query(conn).where("status", FAILED).order_by("id", "DESC").limit(20).get()]})
    finally:
        conn.close()
    return 0


def cmd_queue_retry(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        j = Job.find(conn, args.id)
        if not j:
            print("İş bulunamadı.", file=sys.stderr)
            return 1
        if j.status != FAILED:
            print("Yalnızca başarısız işler yeniden kuyruğa alınabilir.", file=sys.stderr)
            return 1
        _yaz({"is": j.retry(conn).to_dict()})
    finally:
        conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kvkk-console", description="KVKK-RAG API konsolu")
    alt = p.add_subparsers(dest="komut", required=True)

    alt.add_parser("migrate", help="Bekleyen göçleri uygula").set_defaults(fn=cmd_migrate)
    s = alt.add_parser("db:seed", help="Rol/izin/kapsam/departman tohumla")
    s.add_argument("--no-admin", action="store_true", help="İlk yönetici kullanıcıyı oluşturma")
    s.add_argument("--sync", action="store_true", help="Mevcut rollerin izin/kapsamlarını varsayılana eşitle")
    s.set_defaults(fn=cmd_seed)
    alt.add_parser("permission:cache-reset", help="Yetki önbellek sürümünü artır").set_defaults(fn=cmd_cache_reset)
    alt.add_parser("jwt:secret", help="KVKK_JWT_SECRET için rastgele anahtar üret").set_defaults(fn=cmd_jwt_secret)

    s = alt.add_parser("user:create", help="Kullanıcı oluştur")
    s.add_argument("--email", required=True)
    s.add_argument("--password", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--role", action="append", default=[])
    s.add_argument("--department", action="append", default=[])
    s.set_defaults(fn=cmd_user_create)

    s = alt.add_parser("user:password", help="Kullanıcı şifresini değiştir")
    s.add_argument("--email", required=True)
    s.add_argument("--password", required=True)
    s.set_defaults(fn=cmd_user_password)

    s = alt.add_parser("user:role", help="Rol ata / kaldır")
    s.add_argument("--email", required=True)
    s.add_argument("--role", required=True)
    s.add_argument("--remove", action="store_true")
    s.set_defaults(fn=cmd_user_role)

    s = alt.add_parser("user:department", help="Departman ata / kaldır")
    s.add_argument("--email", required=True)
    s.add_argument("--department", required=True)
    s.add_argument("--remove", action="store_true")
    s.set_defaults(fn=cmd_user_department)

    alt.add_parser("role:list", help="Rolleri izin ve kapsamlarıyla listele").set_defaults(fn=cmd_role_list)

    s = alt.add_parser("envanter:import", help="veri_envanteri.xlsx dosyasını SQLite'a aktar")
    s.add_argument("--force", action="store_true", help="Mevcut satırları silip yeniden aktar")
    s.set_defaults(fn=cmd_envanter_import)

    s = alt.add_parser("queue:work", help="Kuyruktaki işleri çalıştır (ayrı worker süreci)")
    s.add_argument("--once", action="store_true", help="Tek iş çalıştırıp çık")
    s.add_argument("--sleep", type=float, default=2.0, help="İş yokken bekleme (sn)")
    s.add_argument("--queue", default=None, help="Yalnızca bu kuyruk (örn. documents)")
    s.set_defaults(fn=cmd_queue_work)
    alt.add_parser("queue:status", help="Kuyruk sayaçları ve başarısız işler").set_defaults(fn=cmd_queue_status)
    s = alt.add_parser("queue:retry", help="Başarısız işi yeniden kuyruğa al")
    s.add_argument("--id", type=int, required=True)
    s.set_defaults(fn=cmd_queue_retry)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))
