from __future__ import annotations

import sqlite3
import threading

from ttap.domain.models import Offer, Order, OrderState, PurchaseRequest

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (org_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY (org_id, id));
CREATE TABLE IF NOT EXISTS offers (org_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (org_id, id));
CREATE TABLE IF NOT EXISTS orders (org_id TEXT NOT NULL, id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
  state TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY (org_id, id), UNIQUE (org_id, idempotency_key));
"""


class SqliteStore:
    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)

    def _one(self, sql: str, params: tuple) -> tuple | None:
        with self._lock:
            return self._db.execute(sql, params).fetchone()

    def _write(self, sql: str, params: tuple) -> int:
        with self._lock:
            return self._db.execute(sql, params).rowcount

    def save_request(self, req: PurchaseRequest) -> None:
        self._write("INSERT INTO requests (org_id, id, body) VALUES (?, ?, ?)",
                    (req.org_id, req.request_id, req.model_dump_json()))

    def get_request(self, org_id: str, request_id: str) -> PurchaseRequest | None:
        row = self._one("SELECT body FROM requests WHERE org_id = ? AND id = ?", (org_id, request_id))
        return PurchaseRequest.model_validate_json(row[0]) if row else None

    def save_offer(self, offer: Offer) -> None:
        self._write("INSERT INTO offers (org_id, id, body) VALUES (?, ?, ?)",
                    (offer.org_id, offer.offer_id, offer.model_dump_json()))

    def get_offer(self, org_id: str, offer_id: str) -> Offer | None:
        row = self._one("SELECT body FROM offers WHERE org_id = ? AND id = ?", (org_id, offer_id))
        return Offer.model_validate_json(row[0]) if row else None

    def claim_offer(self, org_id: str, offer_id: str) -> bool:
        return self._write("UPDATE offers SET used = 1 WHERE org_id = ? AND id = ? AND used = 0",
                           (org_id, offer_id)) == 1

    def insert_order(self, order: Order) -> bool:
        try:
            self._write("INSERT INTO orders (org_id, id, idempotency_key, state, version, body) VALUES (?,?,?,?,?,?)",
                        (order.org_id, order.order_id, order.idempotency_key, order.state.value, order.version,
                         order.model_dump_json()))
        except sqlite3.IntegrityError:
            return False
        return True

    def get_order(self, org_id: str, order_id: str) -> Order | None:
        row = self._one("SELECT body FROM orders WHERE org_id = ? AND id = ?", (org_id, order_id))
        return Order.model_validate_json(row[0]) if row else None

    def get_order_by_idempotency_key(self, org_id: str, key: str) -> Order | None:
        row = self._one("SELECT body FROM orders WHERE org_id = ? AND idempotency_key = ?", (org_id, key))
        return Order.model_validate_json(row[0]) if row else None

    def transition(self, org_id: str, order_id: str, expected_state: OrderState, expected_version: int,
                   updated: Order) -> bool:
        if updated.version != expected_version + 1:
            raise ValueError("updated.version must be expected_version + 1")
        return self._write(
            "UPDATE orders SET state = ?, version = ?, body = ? "
            "WHERE org_id = ? AND id = ? AND state = ? AND version = ?",
            (updated.state.value, updated.version, updated.model_dump_json(), org_id, order_id,
             expected_state.value, expected_version)) == 1
