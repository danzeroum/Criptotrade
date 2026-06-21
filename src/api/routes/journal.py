"""/v1/journal — Diário Comportamental.

CRUD de registros de trading com contexto emocional + métricas de disciplina.
Tabela criada por migrations/002_journal.sql.
"""
from __future__ import annotations

from statistics import correlation, mean
from typing import Any, List, Optional

from fastapi import APIRouter, Body, Query

from src.api.schemas import (
    APIResponse,
    EmotionBand,
    JournalEntryCreate,
    JournalEntryOut,
    JournalMetricsOut,
    Meta,
)
from src.core.db import connection, is_postgres

router = APIRouter(prefix="/journal", tags=["journal"])


def _row_to_out(row: Any) -> JournalEntryOut:
    return JournalEntryOut(
        id=row["id"],
        setup=row["setup"],
        emotion_before=row["emotion_before"],
        emotion_after=row["emotion_after"],
        stop_defined=bool(row["stop_defined"]),
        plan_followed=bool(row["plan_followed"]),
        pnl_pct=row["pnl_pct"],
        note=row["note"],
        created_at=row["created_at"],
    )


@router.get(
    "",
    response_model=APIResponse[List[JournalEntryOut]],
    summary="Lista registros do diário (paginado)",
)
async def list_entries(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> APIResponse[List[JournalEntryOut]]:
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM journal_entries ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    entries = [_row_to_out(r) for r in rows]
    return APIResponse(
        data=entries,
        meta=Meta(total=total, page=(offset // limit) + 1, per_page=limit),
    )


@router.post(
    "",
    response_model=APIResponse[JournalEntryOut],
    summary="Cria novo registro no diário",
    status_code=201,
)
async def create_entry(
    payload: JournalEntryCreate = Body(...),
) -> APIResponse[JournalEntryOut]:
    with connection() as conn:
        insert_sql = """INSERT INTO journal_entries
               (setup, emotion_before, emotion_after, stop_defined, plan_followed, pnl_pct, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)"""
        params = (
            payload.setup,
            payload.emotion_before,
            payload.emotion_after,
            int(payload.stop_defined),
            int(payload.plan_followed),
            payload.pnl_pct,
            payload.note,
        )
        # Postgres has no lastrowid → use RETURNING; SQLite uses cursor.lastrowid.
        if is_postgres():  # pragma: no cover - Postgres-only (gated PG test)
            new_id = conn.execute(insert_sql + " RETURNING id", params).fetchone()[0]
        else:
            new_id = conn.execute(insert_sql, params).lastrowid
        row = conn.execute(
            "SELECT * FROM journal_entries WHERE id = ?", (new_id,)
        ).fetchone()
    return APIResponse(data=_row_to_out(row))


@router.get(
    "/metrics",
    response_model=APIResponse[JournalMetricsOut],
    summary="Métricas do diário (win-rate por emoção, correlação disciplina, win-rate real)",
)
async def get_metrics() -> APIResponse[JournalMetricsOut]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM journal_entries ORDER BY created_at").fetchall()

    entries = [dict(r) for r in rows]
    if not entries:
        return APIResponse(data=JournalMetricsOut(
            by_emotion=[],
            plan_followed_pnl=None,
            plan_deviated_pnl=None,
            discipline_correlation=None,
            real_win_rate=None,
        ))

    pnl_entries = [e for e in entries if e["pnl_pct"] is not None]

    by_emotion: List[EmotionBand] = []
    for band_start in range(1, 11, 3):
        band_end = min(band_start + 2, 10)
        band_entries = [
            e for e in pnl_entries
            if band_start <= e["emotion_before"] <= band_end
        ]
        if band_entries:
            wins = [e for e in band_entries if e["pnl_pct"] > 0]
            wr = len(wins) / len(band_entries)
            label = f"{band_start}–{band_end}"
            by_emotion.append(EmotionBand(band=label, win_rate=round(wr, 4), trades=len(band_entries)))

    plan_ok = [e["pnl_pct"] for e in pnl_entries if e["plan_followed"]]
    plan_nok = [e["pnl_pct"] for e in pnl_entries if not e["plan_followed"]]

    plan_followed_pnl = round(mean(plan_ok), 4) if plan_ok else None
    plan_deviated_pnl = round(mean(plan_nok), 4) if plan_nok else None

    discipline_correlation: Optional[float] = None
    if len(pnl_entries) >= 4:
        xs = [float(e["plan_followed"]) for e in pnl_entries]
        ys = [e["pnl_pct"] for e in pnl_entries]
        if len(set(xs)) > 1:
            try:
                discipline_correlation = round(correlation(xs, ys), 4)
            except Exception:
                pass

    real_win_rate: Optional[float] = None
    if pnl_entries:
        wins = [e for e in pnl_entries if e["pnl_pct"] > 0]
        real_win_rate = round(len(wins) / len(pnl_entries), 4)

    return APIResponse(data=JournalMetricsOut(
        by_emotion=by_emotion,
        plan_followed_pnl=plan_followed_pnl,
        plan_deviated_pnl=plan_deviated_pnl,
        discipline_correlation=discipline_correlation,
        real_win_rate=real_win_rate,
    ))
