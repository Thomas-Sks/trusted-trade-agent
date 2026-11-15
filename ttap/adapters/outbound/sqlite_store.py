from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal

from ttap.domain.models import ActionToken, ApproverRef, Offer, Order, OrderState, PurchaseRequest

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (org_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY (org_id, id));
CREATE TABLE IF NOT EXISTS offers (org_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (org_id, id));
CREATE TABLE IF NOT EXISTS orders (org_id TEXT NOT NULL, id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
  state TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY (org_id, id), UNIQUE (org_id, idempotency_key));
CREATE TABLE IF NOT EXISTS reservations (order_id TEXT NOT NULL, org_id TEXT NOT NULL, product_id TEXT NOT NULL,
  delivery_date TEXT NOT NULL, qty TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY (order_id, product_id));
CREATE TABLE IF NOT EXISTS organisations (org_id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approver_links (telegram_id INTEGER PRIMARY KEY, org_id TEXT NOT NULL,
  user_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS action_tokens (id TEXT PRIMARY KEY, org_id TEXT NOT NULL, order_id TEXT NOT NULL,
  version INTEGER NOT NULL, action TEXT NOT NULL, expires_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0);
"""


class SqliteStore:
    def __init__(self, path: str = ":memory:", stock_scope: str = "global"):
        """stock_scope="global": one reservation ledger for everyone (production). "org": public-demo sandbox where
        each organisation only sees and competes with its own reservations, so visitors cannot drain each other."""
        self._per_org = stock_scope == "org"
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

    def list_orders(self, org_id: str) -> list[Order]:
        with self._lock:
            rows = self._db.execute("SELECT body FROM orders WHERE org_id = ? AND state != 'PENDING_DECISION'",
                                    (org_id,)).fetchall()
        return sorted((Order.model_validate_json(r[0]) for r in rows),
                      key=lambda o: o.decided_at.isoformat() if o.decided_at else "", reverse=True)

    def list_orders_by_state(self, state: OrderState) -> list[Order]:
        with self._lock:
            rows = self._db.execute("SELECT body FROM orders WHERE state = ?", (state.value,)).fetchall()
        return [Order.model_validate_json(r[0]) for r in rows]

    def transition(self, org_id: str, order_id: str, expected_state: OrderState, expected_version: int,
                   updated: Order) -> bool:
        if updated.version != expected_version + 1:
            raise ValueError("updated.version must be expected_version + 1")
        return self._write(
            "UPDATE orders SET state = ?, version = ?, body = ? "
            "WHERE org_id = ? AND id = ? AND state = ? AND version = ?",
            (updated.state.value, updated.version, updated.model_dump_json(), org_id, order_id,
             expected_state.value, expected_version)) == 1

    def link_approver(self, telegram_id: int, org_id: str, user_id: str) -> None:
        self._write("INSERT OR REPLACE INTO approver_links (telegram_id, org_id, user_id) VALUES (?, ?, ?)",
                    (telegram_id, org_id, user_id))

    def approver_by_telegram(self, telegram_id: int) -> ApproverRef | None:
        row = self._one("SELECT org_id, user_id FROM approver_links WHERE telegram_id = ?", (telegram_id,))
        return ApproverRef(org_id=row[0], user_id=row[1]) if row else None

    def approver_chats(self, org_id: str) -> list[int]:
        with self._lock:
            rows = self._db.execute("SELECT telegram_id FROM approver_links WHERE org_id = ?", (org_id,)).fetchall()
        return [r[0] for r in rows]

    def save_action_token(self, token: ActionToken) -> None:
        self._write("INSERT INTO action_tokens (id, org_id, order_id, version, action, expires_at) VALUES (?,?,?,?,?,?)",
                    (token.token_id, token.org_id, token.order_id, token.version, token.action,
                     token.expires_at.isoformat()))

    def get_action_token(self, token_id: str) -> ActionToken | None:
        row = self._one("SELECT id, org_id, order_id, version, action, expires_at, used FROM action_tokens "
                        "WHERE id = ?", (token_id,))
        if not row:
            return None
        return ActionToken(token_id=row[0], org_id=row[1], order_id=row[2], version=row[3], action=row[4],
                           expires_at=datetime.fromisoformat(row[5]), used=bool(row[6]))

    def consume_action_token(self, token_id: str) -> bool:
        return self._write("UPDATE action_tokens SET used = 1 WHERE id = ? AND used = 0", (token_id,)) == 1

    # --- reservations (available-to-promise ledger) -------------------------------------------------------
    def _reserved_locked(self, product_id: str, delivery: str, org_id: str | None = None) -> Decimal:
        sql = ("SELECT qty FROM reservations WHERE product_id = ? AND delivery_date = ? "
               "AND status IN ('HELD', 'FIRM')")
        args: tuple = (product_id, delivery)
        if self._per_org and org_id:
            sql, args = sql + " AND org_id = ?", (*args, org_id)
        rows = self._db.execute(sql, args).fetchall()
        return sum((Decimal(r[0]) for r in rows), Decimal("0"))

    def reserved_qty(self, product_ids: list[str], delivery: date, org_id: str | None = None) -> dict[str, Decimal]:
        with self._lock:
            return {pid: self._reserved_locked(pid, delivery.isoformat(), org_id) for pid in product_ids}

    def reserve(self, org_id: str, order_id: str,
                items: list[tuple[str, date, Decimal, Decimal]]) -> list[str]:
        """All-or-nothing: items = (product_id, delivery_date, qty, upstream_available). Returns shortages."""
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                short = [pid for pid, day, qty, upstream in items
                         if upstream - self._reserved_locked(pid, day.isoformat(), org_id) < qty]
                if short:
                    self._db.execute("ROLLBACK")
                    return short
                for pid, day, qty, _ in items:
                    self._db.execute("INSERT OR REPLACE INTO reservations VALUES (?, ?, ?, ?, ?, 'HELD')",
                                     (order_id, org_id, pid, day.isoformat(), str(qty)))
                self._db.execute("COMMIT")
                return []
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def set_reservation_status(self, order_id: str, status: str) -> None:
        self._write("UPDATE reservations SET status = ? WHERE order_id = ?", (status, order_id))

    def org_orders_since(self, org_id: str, since: datetime, states: tuple[OrderState, ...]) -> list[Order]:
        marks = ",".join("?" for _ in states)
        with self._lock:
            rows = self._db.execute(f"SELECT body FROM orders WHERE org_id = ? AND state IN ({marks})",
                                    (org_id, *[s.value for s in states])).fetchall()
        orders = [Order.model_validate_json(r[0]) for r in rows]
        return [o for o in orders if o.decided_at is not None and o.decided_at >= since]

    def reset_demo(self) -> None:
        """Demo reset: forget requests, offers, orders, reservations and tokens (approver pairings are kept)."""
        with self._lock:
            for table in ("requests", "offers", "orders", "reservations", "action_tokens"):
                self._db.execute(f"DELETE FROM {table}")

    def save_organisation(self, org_id: str, body: str) -> None:
        self._write("INSERT OR REPLACE INTO organisations (org_id, body) VALUES (?, ?)", (org_id, body))

    def list_organisations(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self._db.execute("SELECT body FROM organisations").fetchall()]

    def count_organisations(self) -> int:
        return self._one("SELECT COUNT(*) FROM organisations", ())[0]
