"""Versiyonlu yetki/kapsam onbellegi (Laravel Cache facade karsiligi).

Anahtar bicimi : scope_v{version}_{roleIds}__{module}__{action}
Gecersizleme   : flush_cache() anahtarlari tek tek silmez; sadece
                 `permission_scope_cache_version` sayacini artirir. Eski surumlu
                 anahtarlar bir daha uretilmedigi icin O(1) maliyetle duser,
                 TTL dolunca depodan kendiliginden temizlenir.
Depo           : varsayilan bellek (surec ici). KVKK_REDIS_URL verilirse Redis;
                 coklu uvicorn worker'da surum sayaci ancak boyle paylasilir."""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, Iterable, Protocol

VERSION_KEY = "permission_scope_cache_version"
DEFAULT_TTL = int(os.getenv("KVKK_PERMISSION_CACHE_TTL", "3600"))


class CacheStore(Protocol):
    def get(self, key: str) -> Any | None: ...
    def put(self, key: str, value: Any, ttl: int) -> None: ...
    def forget(self, key: str) -> None: ...
    def increment(self, key: str) -> int: ...
    def flush(self) -> None: ...


class MemoryStore:
    """Surec ici depo. Buyumeyi sinirlamak icin belirli sayida yazimda bir
    suresi dolmus kayitlar suprulur."""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._veri: dict[str, tuple[float, Any]] = {}
        self._kilit = threading.Lock()
        self._max = max_entries
        self._yazim = 0

    def get(self, key: str) -> Any | None:
        with self._kilit:
            kayit = self._veri.get(key)
            if not kayit:
                return None
            son, deger = kayit
            if son and son < time.time():
                self._veri.pop(key, None)
                return None
            return deger

    def put(self, key: str, value: Any, ttl: int) -> None:
        with self._kilit:
            self._veri[key] = (time.time() + ttl if ttl else 0.0, value)
            self._yazim += 1
            if self._yazim % 500 == 0 or len(self._veri) > self._max:
                self._supur()

    def _supur(self) -> None:
        simdi = time.time()
        for k in [k for k, (son, _) in self._veri.items() if son and son < simdi]:
            self._veri.pop(k, None)
        if len(self._veri) > self._max:  # hala buyukse en eskileri at
            for k in list(self._veri)[: len(self._veri) - self._max]:
                self._veri.pop(k, None)

    def forget(self, key: str) -> None:
        with self._kilit:
            self._veri.pop(key, None)

    def increment(self, key: str) -> int:
        with self._kilit:
            _, mevcut = self._veri.get(key, (0.0, 0))
            yeni = int(mevcut or 0) + 1
            self._veri[key] = (0.0, yeni)  # surum sayacinin suresi dolmaz
            return yeni

    def flush(self) -> None:
        with self._kilit:
            self._veri.clear()

    def __len__(self) -> int:
        return len(self._veri)


class RedisStore:
    """Redis depo; `redis` paketi ve KVKK_REDIS_URL gerekir. Degerler JSON."""

    def __init__(self, url: str, prefix: str = "kvkk:perm:") -> None:
        import json
        import redis  # noqa: F401 - istege bagli bagimlilik

        self._r = redis.Redis.from_url(url, decode_responses=True)
        self._p = prefix
        self._json = json

    def get(self, key: str) -> Any | None:
        v = self._r.get(self._p + key)
        return None if v is None else self._json.loads(v)

    def put(self, key: str, value: Any, ttl: int) -> None:
        self._r.set(self._p + key, self._json.dumps(value), ex=ttl or None)

    def forget(self, key: str) -> None:
        self._r.delete(self._p + key)

    def increment(self, key: str) -> int:
        return int(self._r.incr(self._p + key))

    def flush(self) -> None:
        for k in self._r.scan_iter(self._p + "*"):
            self._r.delete(k)


def _default_store() -> CacheStore:
    url = os.getenv("KVKK_REDIS_URL", "").strip()
    if url:
        try:
            return RedisStore(url)
        except Exception as e:  # noqa: BLE001 - Redis yoksa bellege dus
            import logging
            logging.getLogger(__name__).warning("Redis onbellegi kullanilamadi (%s); bellek deposu", e)
    return MemoryStore()


class PermissionCache:
    def __init__(self, store: CacheStore | None = None, ttl: int = DEFAULT_TTL) -> None:
        self.store: CacheStore = store or _default_store()
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

    # ---- surum ----
    def version(self) -> int:
        v = self.store.get(VERSION_KEY)
        return int(v) if v else 1

    def flush(self) -> int:
        # O(1) gecersizleme: yalnizca surum artar
        return self.store.increment(VERSION_KEY)

    # ---- anahtarlar ----
    def scope_key(self, role_ids: Iterable[int], module: str, action: str) -> str:
        roller = ",".join(str(r) for r in sorted(set(role_ids)))
        return f"scope_v{self.version()}_{roller}__{module}__{action}"

    def permissions_key(self, role_ids: Iterable[int]) -> str:
        roller = ",".join(str(r) for r in sorted(set(role_ids)))
        return f"perm_v{self.version()}_{roller}"

    # ---- erisim ----
    def get(self, key: str) -> Any | None:
        return self.store.get(key)

    def put(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.store.put(key, value, self.ttl if ttl is None else ttl)

    def forget(self, key: str) -> None:
        self.store.forget(key)

    def remember(self, key: str, callback: Callable[[], Any], ttl: int | None = None) -> Any:
        deger = self.store.get(key)
        if deger is not None:
            self.hits += 1
            return deger
        self.misses += 1
        deger = callback()
        self.put(key, deger, ttl)
        return deger


cache = PermissionCache()


def flush_cache() -> int:
    """Rol izinleri veya kapsamlar degistiginde cagrilir (gozlemciler yapar)."""
    return cache.flush()


def use_store(store: CacheStore) -> None:
    # Testler veya farkli depo secimi icin
    cache.store = store
