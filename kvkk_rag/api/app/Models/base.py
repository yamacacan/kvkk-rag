"""Eloquent-benzeri hafif model katmani (sqlite3 uzerinde).

QueryBuilder: WHERE kosullarini biriktirir; ScopeFilter kapsam filtrelerini buraya
SQL olarak ekler. Model: tablo eslemesi, CRUD, gozlemci (observer) olaylari.
Amac ORM yazmak degil; Laravel mimarisindeki Builder / Model / Observer
kavramlarinin sqlite3 uzerinde ayni sekilde kullanilabilmesi."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T", bound="Model")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class QueryBuilder:
    _OPS = {"=", "!=", "<>", "<", "<=", ">", ">=", "LIKE", "NOT LIKE", "IS", "IS NOT"}

    def __init__(self, conn: sqlite3.Connection, table: str,
                 model: type[Model] | None = None) -> None:
        self.conn = conn
        self.table = table
        self.model = model
        self._columns: list[str] = ["*"]
        self._wheres: list[tuple[str, str, list[Any]]] = []  # (AND/OR, sql, params)
        self._orders: list[str] = []
        self._limit: int | None = None
        self._offset: int | None = None
        self.scope_applied: str | None = None  # ScopeFilter hangi kapsami uyguladi

    # ---- secim ----
    def select(self, *columns: str) -> QueryBuilder:
        self._columns = list(columns) or ["*"]
        return self

    # ---- kosullar ----
    def where(self, column: str, operator: Any = None, value: Any = None,
              boolean: str = "AND") -> QueryBuilder:
        # Eloquent imzasi: where('a', 1) veya where('a', '>', 1)
        if value is None and operator is not None and str(operator).upper() not in self._OPS:
            operator, value = "=", operator
        operator = operator or "="
        if value is None and operator in ("=", "IS"):
            return self.where_raw(f"{column} IS NULL", (), boolean)
        return self.where_raw(f"{column} {operator} ?", (value,), boolean)

    def or_where(self, column: str, operator: Any = None, value: Any = None) -> QueryBuilder:
        return self.where(column, operator, value, boolean="OR")

    def where_in(self, column: str, values: Iterable[Any], boolean: str = "AND") -> QueryBuilder:
        values = list(values)
        if not values:
            return self.where_raw("0 = 1", (), boolean)  # bos kume: hicbir satir
        yer = ", ".join("?" * len(values))
        return self.where_raw(f"{column} IN ({yer})", values, boolean)

    def where_null(self, column: str) -> QueryBuilder:
        return self.where_raw(f"{column} IS NULL")

    def where_not_null(self, column: str) -> QueryBuilder:
        return self.where_raw(f"{column} IS NOT NULL")

    def where_raw(self, sql: str, params: Iterable[Any] = (), boolean: str = "AND") -> QueryBuilder:
        self._wheres.append((boolean.upper(), sql, list(params)))
        return self

    def where_group(self, fn: Callable[[QueryBuilder], Any], boolean: str = "AND") -> QueryBuilder:
        # where(function ($q) { ... }) karsiligi: ic kosullar parantezlenir
        alt = QueryBuilder(self.conn, self.table, self.model)
        fn(alt)
        sql, params = alt._compile_wheres()
        if sql:
            self.where_raw(f"({sql})", params, boolean)
        return self

    # ---- siralama / sayfa ----
    def order_by(self, column: str, direction: str = "ASC") -> QueryBuilder:
        self._orders.append(f"{column} {direction.upper()}")
        return self

    def limit(self, n: int | None) -> QueryBuilder:
        self._limit = n
        return self

    def offset(self, n: int | None) -> QueryBuilder:
        self._offset = n
        return self

    # ---- derleme ----
    def _compile_wheres(self) -> tuple[str, list[Any]]:
        sql, params = "", []
        for i, (boolean, parca, p) in enumerate(self._wheres):
            sql += parca if i == 0 else f" {boolean} {parca}"
            params.extend(p)
        return sql, params

    def to_sql(self, columns: str | None = None) -> tuple[str, list[Any]]:
        sql = f"SELECT {columns or ', '.join(self._columns)} FROM {self.table}"
        where, params = self._compile_wheres()
        if where:
            sql += f" WHERE {where}"
        if self._orders and columns is None:
            sql += " ORDER BY " + ", ".join(self._orders)
        if self._limit is not None and columns is None:
            sql += f" LIMIT {int(self._limit)}"
            if self._offset:
                sql += f" OFFSET {int(self._offset)}"
        return sql, params

    # ---- calistirma ----
    def _hydrate(self, r: sqlite3.Row) -> Any:
        return self.model(dict(r)) if self.model else dict(r)

    def get(self) -> list[Any]:
        sql, params = self.to_sql()
        return [self._hydrate(r) for r in self.conn.execute(sql, params)]

    def first(self) -> Any | None:
        self._limit = 1
        rows = self.get()
        return rows[0] if rows else None

    def count(self) -> int:
        sql, params = self.to_sql("COUNT(*)")
        return int(self.conn.execute(sql, params).fetchone()[0])

    def exists(self) -> bool:
        return self.count() > 0

    def pluck(self, column: str) -> list[Any]:
        sql, params = self.to_sql(column)
        return [r[0] for r in self.conn.execute(sql, params)]

    def update(self, values: dict[str, Any]) -> int:
        where, params = self._compile_wheres()
        atama = ", ".join(f"{k} = ?" for k in values)
        sql = f"UPDATE {self.table} SET {atama}"
        if where:
            sql += f" WHERE {where}"
        cur = self.conn.execute(sql, list(values.values()) + params)
        self.conn.commit()
        return cur.rowcount

    def delete(self) -> int:
        where, params = self._compile_wheres()
        sql = f"DELETE FROM {self.table}"
        if where:
            sql += f" WHERE {where}"
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur.rowcount


class Model:
    """Tablo satirini temsil eder. Alt siniflar `table`, `primary_key`, `fillable`
    tanimlar. Gozlemciler `Model.observe(obj)` ile baglanir; obj uzerinde
    created / updated / deleted / saved metotlari varsa cagrilir."""

    table: str = ""
    primary_key: str = "id"
    fillable: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    timestamps: bool = True

    def __init__(self, attributes: dict[str, Any] | None = None) -> None:
        self._attributes: dict[str, Any] = dict(attributes or {})

    # ---- attribute erisimi ----
    def __getattr__(self, name: str) -> Any:
        attrs = self.__dict__.get("_attributes", {})
        if name in attrs:
            return attrs[name]
        raise AttributeError(f"{type(self).__name__}.{name}")

    def get(self, name: str, default: Any = None) -> Any:
        return self._attributes.get(name, default)

    @property
    def key(self) -> Any:
        return self._attributes.get(self.primary_key)

    @property
    def attributes(self) -> dict[str, Any]:
        return dict(self._attributes)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self._attributes.items() if k not in self.hidden}

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.primary_key}={self.key}>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Model) and type(other) is type(self) and other.key == self.key

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.key))

    # ---- sorgu ----
    @classmethod
    def query(cls: type[T], conn: sqlite3.Connection) -> QueryBuilder:
        return QueryBuilder(conn, cls.table, cls)

    @classmethod
    def find(cls: type[T], conn: sqlite3.Connection, key: Any) -> T | None:
        return cls.query(conn).where(cls.primary_key, key).first()

    @classmethod
    def all(cls: type[T], conn: sqlite3.Connection) -> list[T]:
        return cls.query(conn).order_by(cls.primary_key).get()

    # ---- yazma ----
    @classmethod
    def _fillable(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not cls.fillable:
            return dict(values)
        return {k: v for k, v in values.items() if k in cls.fillable}

    @classmethod
    def create(cls: type[T], conn: sqlite3.Connection, **values: Any) -> T:
        veri = cls._fillable(values)
        if cls.timestamps:
            veri.setdefault("created_at", now())
            veri.setdefault("updated_at", now())
        cols = list(veri)
        yer = ", ".join("?" * len(cols))
        cur = conn.execute(
            f"INSERT INTO {cls.table} ({', '.join(cols)}) VALUES ({yer})",
            [veri[c] for c in cols])
        conn.commit()
        key = veri[cls.primary_key] if cls.primary_key in veri else cur.lastrowid
        model = cls.find(conn, key)
        cls._fire("created", model, conn)
        cls._fire("saved", model, conn)
        return model

    def update(self: T, conn: sqlite3.Connection, **values: Any) -> T:
        veri = self._fillable(values)
        if not veri:
            return self
        if self.timestamps:
            veri["updated_at"] = now()
        atama = ", ".join(f"{k} = ?" for k in veri)
        conn.execute(
            f"UPDATE {self.table} SET {atama} WHERE {self.primary_key} = ?",
            list(veri.values()) + [self.key])
        conn.commit()
        self._attributes.update(veri)
        self._fire("updated", self, conn)
        self._fire("saved", self, conn)
        return self

    def delete(self, conn: sqlite3.Connection) -> bool:
        cur = conn.execute(f"DELETE FROM {self.table} WHERE {self.primary_key} = ?", (self.key,))
        conn.commit()
        if cur.rowcount:
            self._fire("deleted", self, conn)
        return bool(cur.rowcount)

    def refresh(self: T, conn: sqlite3.Connection) -> T:
        taze = self.find(conn, self.key)
        if taze:
            self._attributes = taze._attributes
        return self

    @classmethod
    def first_or_create(cls: type[T], conn: sqlite3.Connection, where: dict[str, Any],
                        **defaults: Any) -> T:
        q = cls.query(conn)
        for k, v in where.items():
            q.where(k, v)
        mevcut = q.first()
        if mevcut:
            return mevcut
        return cls.create(conn, **where, **defaults)

    @classmethod
    def update_or_create(cls: type[T], conn: sqlite3.Connection, where: dict[str, Any],
                         **values: Any) -> T:
        q = cls.query(conn)
        for k, v in where.items():
            q.where(k, v)
        mevcut = q.first()
        if mevcut:
            return mevcut.update(conn, **values)
        return cls.create(conn, **where, **values)

    # ---- gozlemciler (Laravel Observer) ----
    _observers: dict[str, list[Any]] = {}

    @classmethod
    def observe(cls, observer: Any) -> None:
        listem = Model._observers.setdefault(cls.__name__, [])
        if not any(type(o) is type(observer) for o in listem):
            listem.append(observer)

    @classmethod
    def _fire(cls, event: str, model: Any, conn: sqlite3.Connection) -> None:
        for o in Model._observers.get(cls.__name__, ()):
            fn = getattr(o, event, None)
            if fn:
                fn(model, conn)
