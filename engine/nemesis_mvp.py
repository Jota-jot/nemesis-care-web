#!/usr/bin/env python3
"""Némesis MVP: auditable task, evidence, forecast and cash-control core.

Python 3.11+, standard library only. No network calls and no automatic purchases.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path("data/nemesis.db")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      objective TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','blocked','done','cancelled')),
      priority INTEGER NOT NULL DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS evidence (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      task_id INTEGER REFERENCES tasks(id),
      claim TEXT NOT NULL,
      source_url TEXT NOT NULL DEFAULT '',
      source_title TEXT NOT NULL DEFAULT '',
      evidence_type TEXT NOT NULL CHECK(evidence_type IN ('fact','inference','hypothesis','contradiction')),
      confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
      observed_at TEXT NOT NULL,
      notes TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS forecasts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      question TEXT NOT NULL,
      created_at TEXT NOT NULL,
      horizon_at TEXT NOT NULL,
      p_yes REAL NOT NULL CHECK(p_yes > 0 AND p_yes < 1),
      rationale TEXT NOT NULL,
      resolution_rule TEXT NOT NULL,
      resolution_source TEXT NOT NULL DEFAULT '',
      resolved_at TEXT,
      outcome_yes INTEGER CHECK(outcome_yes IN (0,1)),
      brier REAL,
      log_loss REAL,
      calibration_note TEXT
    );
    CREATE TRIGGER IF NOT EXISTS forecast_core_immutable
    BEFORE UPDATE OF question, created_at, horizon_at, p_yes, rationale, resolution_rule
    ON forecasts
    BEGIN
      SELECT RAISE(ABORT, 'Forecast core is immutable; only resolution fields may change');
    END;
    CREATE TABLE IF NOT EXISTS ledger (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      recorded_at TEXT NOT NULL,
      direction TEXT NOT NULL CHECK(direction IN ('income','expense')),
      status TEXT NOT NULL CHECK(status IN ('collected','paid','contracted_unpaid','projected','committed')),
      amount REAL NOT NULL CHECK(amount >= 0),
      currency TEXT NOT NULL DEFAULT 'EUR',
      category TEXT NOT NULL,
      description TEXT NOT NULL,
      reference TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
    INSERT OR IGNORE INTO settings(key,value) VALUES ('reserve_eur','0');
    INSERT OR IGNORE INTO settings(key,value) VALUES ('monthly_budget_eur','0');
    """)
    db.commit()


def add_task(db, title, objective="", priority=3):
    ts = now()
    cur = db.execute("INSERT INTO tasks(title,objective,priority,created_at,updated_at) VALUES(?,?,?,?,?)",
                     (title, objective, priority, ts, ts))
    db.commit()
    return cur.lastrowid


def add_evidence(db, claim, evidence_type, confidence, source_url="", source_title="", task_id=None, notes=""):
    cur = db.execute("""INSERT INTO evidence(task_id,claim,source_url,source_title,evidence_type,confidence,observed_at,notes)
                        VALUES(?,?,?,?,?,?,?,?)""",
                     (task_id, claim, source_url, source_title, evidence_type, confidence, now(), notes))
    db.commit()
    return cur.lastrowid


def add_forecast(db, question, horizon_at, p_yes, rationale, resolution_rule):
    if not 0 < p_yes < 1:
        raise ValueError("p_yes debe estar estrictamente entre 0 y 1.")
    cur = db.execute("""INSERT INTO forecasts(question,created_at,horizon_at,p_yes,rationale,resolution_rule)
                        VALUES(?,?,?,?,?,?)""",
                     (question, now(), horizon_at, p_yes, rationale, resolution_rule))
    db.commit()
    return cur.lastrowid


def resolve_forecast(db, forecast_id, outcome_yes, source="", note=""):
    row = db.execute("SELECT * FROM forecasts WHERE id=?", (forecast_id,)).fetchone()
    if row is None:
        raise ValueError(f"No existe el pronóstico {forecast_id}.")
    if row["resolved_at"] is not None:
        raise ValueError("El pronóstico ya está resuelto; no se permite sobrescribir el resultado.")
    y, p = int(outcome_yes), float(row["p_yes"])
    brier = (p - y) ** 2
    clipped = min(max(p, 1e-15), 1 - 1e-15)
    log_loss = -(y * math.log(clipped) + (1-y) * math.log(1-clipped))
    db.execute("""UPDATE forecasts SET resolution_source=?,resolved_at=?,outcome_yes=?,brier=?,log_loss=?,calibration_note=?
                  WHERE id=?""", (source, now(), y, brier, log_loss, note, forecast_id))
    db.commit()
    return {"id": forecast_id, "brier": brier, "log_loss": log_loss}


def set_setting(db, key, value):
    if key not in {"reserve_eur", "monthly_budget_eur"}:
        raise ValueError("Ajuste no permitido.")
    amount = float(value)
    if amount < 0:
        raise ValueError("El importe no puede ser negativo.")
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, str(amount)))
    db.commit()


def record_ledger(db, direction, status, amount, category, description, currency="EUR", reference=""):
    allowed = {"income": {"collected", "contracted_unpaid", "projected"},
               "expense": {"paid", "committed", "projected"}}
    if direction not in allowed or status not in allowed[direction]:
        raise ValueError("Estado incompatible: ingreso=collected/contracted_unpaid/projected; gasto=paid/committed/projected.")
    if amount <= 0:
        raise ValueError("El importe debe ser mayor que cero.")
    if currency != "EUR":
        raise ValueError("El MVP solo calcula saldos en EUR; no mezcles divisas.")
    cur = db.execute("""INSERT INTO ledger(recorded_at,direction,status,amount,currency,category,description,reference)
                        VALUES(?,?,?,?,?,?,?,?)""",
                     (now(), direction, status, amount, currency, category, description, reference))
    db.commit()
    return cur.lastrowid


def financial_summary(db):
    def total(direction, status):
        row = db.execute("SELECT COALESCE(SUM(amount),0) n FROM ledger WHERE direction=? AND status=?",
                         (direction, status)).fetchone()
        return float(row["n"])
    cash_in = total("income", "collected")
    cash_out = total("expense", "paid")
    committed = total("expense", "committed")
    contracted = total("income", "contracted_unpaid")
    projected_in = total("income", "projected")
    projected_out = total("expense", "projected")
    reserve = float(db.execute("SELECT value FROM settings WHERE key='reserve_eur'").fetchone()[0])
    budget = float(db.execute("SELECT value FROM settings WHERE key='monthly_budget_eur'").fetchone()[0])
    available = cash_in - cash_out - committed - reserve
    return {
        "income_collected_eur": round(cash_in, 2),
        "expenses_paid_eur": round(cash_out, 2),
        "expenses_committed_eur": round(committed, 2),
        "income_contracted_unpaid_eur": round(contracted, 2),
        "income_projected_eur_not_cash": round(projected_in, 2),
        "expenses_projected_eur_not_cash": round(projected_out, 2),
        "reserve_eur": round(reserve, 2),
        "monthly_budget_eur": round(budget, 2),
        "available_after_paid_committed_and_reserve_eur": round(available, 2),
        "spending_authorized_automatically": False,
        "warning": "Proyecciones y facturas pendientes no son caja disponible."
    }


def report(db):
    tasks = [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY priority DESC, id")]
    forecasts = [dict(r) for r in db.execute("SELECT * FROM forecasts ORDER BY id DESC LIMIT 20")]
    resolved = db.execute("SELECT COUNT(*) n, AVG(brier) brier, AVG(log_loss) ll FROM forecasts WHERE resolved_at IS NOT NULL").fetchone()
    evidence_count = db.execute("SELECT COUNT(*) n FROM evidence").fetchone()["n"]
    return {
        "generated_at": now(),
        "tasks": tasks,
        "recent_forecasts": forecasts,
        "forecast_performance": {"resolved_count": resolved["n"], "mean_brier": resolved["brier"], "mean_log_loss": resolved["ll"],
                                 "interpretation": "Comparar con una referencia/base y con muestras suficientes; una media aislada no demuestra superioridad."},
        "evidence_records": evidence_count,
        "finance": financial_summary(db)
    }


def main():
    p = argparse.ArgumentParser(description="Némesis MVP — núcleo auditable local")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta SQLite (por defecto data/nemesis.db)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    t = sub.add_parser("task-add"); t.add_argument("title"); t.add_argument("--objective", default=""); t.add_argument("--priority", type=int, default=3)
    e = sub.add_parser("evidence-add"); e.add_argument("claim"); e.add_argument("--type", choices=["fact","inference","hypothesis","contradiction"], required=True); e.add_argument("--confidence", type=float, required=True); e.add_argument("--url", default=""); e.add_argument("--source-title", default=""); e.add_argument("--task-id", type=int); e.add_argument("--notes", default="")
    f = sub.add_parser("forecast-add"); f.add_argument("question"); f.add_argument("--horizon", required=True); f.add_argument("--p-yes", type=float, required=True); f.add_argument("--rationale", required=True); f.add_argument("--resolution-rule", required=True)
    r = sub.add_parser("forecast-resolve"); r.add_argument("id", type=int); r.add_argument("--outcome", choices=["yes","no"], required=True); r.add_argument("--source", required=True); r.add_argument("--note", default="")
    l = sub.add_parser("ledger-add"); l.add_argument("direction", choices=["income","expense"]); l.add_argument("status"); l.add_argument("amount", type=float); l.add_argument("--category", required=True); l.add_argument("--description", required=True); l.add_argument("--currency", default="EUR"); l.add_argument("--reference", default="")
    s = sub.add_parser("setting"); s.add_argument("key", choices=["reserve_eur","monthly_budget_eur"]); s.add_argument("value", type=float)
    sub.add_parser("report")
    a = p.parse_args()
    db = connect(a.db); init_db(db)
    try:
        if a.cmd == "init": result = {"initialized": True, "db": a.db}
        elif a.cmd == "task-add": result = {"task_id": add_task(db, a.title, a.objective, a.priority)}
        elif a.cmd == "evidence-add": result = {"evidence_id": add_evidence(db, a.claim, a.type, a.confidence, a.url, a.source_title, a.task_id, a.notes)}
        elif a.cmd == "forecast-add": result = {"forecast_id": add_forecast(db, a.question, a.horizon, a.p_yes, a.rationale, a.resolution_rule)}
        elif a.cmd == "forecast-resolve": result = resolve_forecast(db, a.id, a.outcome == "yes", a.source, a.note)
        elif a.cmd == "ledger-add": result = {"ledger_id": record_ledger(db, a.direction, a.status, a.amount, a.category, a.description, a.currency, a.reference)}
        elif a.cmd == "setting": set_setting(db, a.key, a.value); result = {"updated": a.key}
        else: result = report(db)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    except (ValueError, sqlite3.Error) as exc:
        p.error(str(exc))
    finally:
        db.close()


if __name__ == "__main__":
    main()
