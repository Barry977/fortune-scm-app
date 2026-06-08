"""
CRM module – SQLite-backed persistence via backend.database.get_db_ctx.

Tables used: customers, follow_ups, quotes.
Extra columns (beyond what database.init_db creates) are added lazily
by _ensure_crm_columns() on first call.
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
import json
import sqlite3

from backend.database import get_db_ctx
from backend.crm_schemas import (
    CustomerCreate, CustomerUpdate, CustomerInDB, CustomerResponse,
    FollowUpCreate, FollowUpInDB, FollowUpResponse,
    QuoteCreate, QuoteInDB, QuoteResponse,
    CustomerFilter, CustomerStats, PipelineStage, PipelineSummary,
    CustomerStatus, CustomerSource, CustomerPriority,
)

# ---------------------------------------------------------------------------
# Lazy schema migration – adds columns that the base init_db() doesn't know
# about so the CRM can store all fields expected by the Pydantic models.
# ---------------------------------------------------------------------------

_initialized = False


def _ensure_crm_columns() -> None:
    """ALTER TABLE to add any missing CRM columns (idempotent)."""
    column_defs = {
        "customers": [
            ("country", "TEXT"),
            ("city", "TEXT"),
            ("industry", "TEXT"),
            ("priority", "TEXT DEFAULT 'medium'"),
            ("assigned_to", "INTEGER"),
            ("website", "TEXT"),
            ("last_contact_at", "TIMESTAMP"),
            ("total_quotes", "INTEGER DEFAULT 0"),
            ("total_orders", "INTEGER DEFAULT 0"),
            ("total_revenue", "REAL DEFAULT 0.0"),
        ],
        "follow_ups": [
            ("type", "TEXT"),
            ("scheduled_at", "TIMESTAMP"),
            ("completed_at", "TIMESTAMP"),
            ("outcome", "TEXT"),
            ("next_action", "TEXT"),
            ("next_action_date", "TEXT"),
        ],
        "quotes": [
            ("quote_number", "TEXT"),
            ("items", "TEXT"),  # JSON-encoded list
            ("currency", "TEXT DEFAULT 'USD'"),
            ("subtotal", "REAL DEFAULT 0"),
            ("tax_rate", "REAL DEFAULT 0"),
            ("tax_amount", "REAL DEFAULT 0"),
            ("total", "REAL DEFAULT 0"),
            ("notes", "TEXT"),
            ("valid_until", "TEXT"),
            ("updated_at", "TIMESTAMP"),
        ],
    }
    try:
        with get_db_ctx() as conn:
            for table, columns in column_defs.items():
                for col_name, col_type in columns:
                    try:
                        conn.execute(
                            f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                        )
                    except Exception:
                        pass  # column already exists
    except Exception:
        pass  # tables may not exist yet (init_db not called)


def _lazy_init() -> None:
    global _initialized
    if not _initialized:
        _ensure_crm_columns()
        _initialized = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse a timestamp string returned by SQLite into a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _row_to_customer_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "name": d["name"],
        "company": d.get("company"),
        "email": d.get("email"),
        "phone": d.get("phone"),
        "country": d.get("country"),
        "city": d.get("city"),
        "industry": d.get("industry"),
        "source": d.get("source") or "other",
        "status": d.get("status") or "lead",
        "priority": d.get("priority") or "medium",
        "tags": json.loads(d["tags"]) if d.get("tags") else [],
        "notes": d.get("notes"),
        "assigned_to": d.get("assigned_to"),
        "linkedin_url": d.get("linkedin_url"),
        "website": d.get("website"),
        "created_at": _parse_dt(d.get("created_at")),
        "updated_at": _parse_dt(d.get("updated_at")),
        "created_by": d.get("user_id"),
        "last_contact_at": _parse_dt(d.get("last_contact_at")),
        "total_quotes": d.get("total_quotes") or 0,
        "total_orders": d.get("total_orders") or 0,
        "total_revenue": d.get("total_revenue") or 0.0,
    }


def _row_to_followup_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "customer_id": d["customer_id"],
        "type": d.get("type") or "note",
        "content": d["content"],
        "scheduled_at": _parse_dt(d.get("scheduled_at")),
        "completed_at": _parse_dt(d.get("completed_at")),
        "outcome": d.get("outcome"),
        "next_action": d.get("next_action"),
        "next_action_date": _parse_date(d.get("next_action_date")),
        "created_at": _parse_dt(d.get("created_at")),
        "created_by": d.get("user_id"),
    }


def _row_to_quote_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    items_raw = d.get("items")
    if items_raw:
        try:
            items = json.loads(items_raw)
        except Exception:
            items = []
    else:
        items = []
    return {
        "id": d["id"],
        "customer_id": d["customer_id"],
        "quote_number": d.get("quote_number") or "",
        "items": items,
        "currency": d.get("currency") or "USD",
        "subtotal": d.get("subtotal") or 0.0,
        "tax_rate": d.get("tax_rate") or 0.0,
        "tax_amount": d.get("tax_amount") or 0.0,
        "total": d.get("total") or 0.0,
        "valid_until": _parse_date(d.get("valid_until")),
        "notes": d.get("notes"),
        "status": d.get("status") or "draft",
        "created_at": _parse_dt(d.get("created_at")),
        "updated_at": _parse_dt(d.get("updated_at")) or _parse_dt(d.get("created_at")),
        "created_by": d.get("user_id"),
    }


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ========== Customer management ==========

def create_customer(customer_data: CustomerCreate, created_by: int) -> dict:
    """Create a customer and return it as a dict compatible with CustomerResponse."""
    _lazy_init()
    now = _now_iso()
    with get_db_ctx() as conn:
        cur = conn.execute(
            """INSERT INTO customers
                   (user_id, name, company, email, phone, country, city, industry,
                    source, status, priority, tags, notes, assigned_to,
                    linkedin_url, website, created_at, updated_at,
                    last_contact_at, total_quotes, total_orders, total_revenue)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                created_by,
                customer_data.name,
                customer_data.company,
                customer_data.email,
                customer_data.phone,
                customer_data.country,
                customer_data.city,
                customer_data.industry,
                customer_data.source.value if hasattr(customer_data.source, "value") else customer_data.source,
                customer_data.status.value if hasattr(customer_data.status, "value") else customer_data.status,
                customer_data.priority.value if hasattr(customer_data.priority, "value") else customer_data.priority,
                json.dumps(customer_data.tags) if customer_data.tags else None,
                customer_data.notes,
                customer_data.assigned_to,
                customer_data.linkedin_url,
                customer_data.website,
                now,
                now,
                None,
                0,
                0,
                0.0,
            ),
        )
        customer_id: int = cur.lastrowid  # type: ignore[assignment]

    # Fetch and return
    return get_customer(customer_id)


def get_customer(customer_id: int) -> Optional[dict]:
    """Return a single customer dict, or None."""
    _lazy_init()
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_customer_dict(row)


def update_customer(customer_id: int, customer_data: CustomerUpdate) -> Optional[dict]:
    """Update a customer. Returns the updated dict or None."""
    _lazy_init()
    # Build SET clause dynamically from fields that were actually provided
    fields = customer_data.model_dump(exclude_unset=True)
    if not fields:
        return get_customer(customer_id)

    # Convert enums to their string values
    set_parts = []
    values: list = []
    for key, value in fields.items():
        if hasattr(value, "value"):
            value = value.value
        if key == "tags":
            value = json.dumps(value) if value is not None else None
        set_parts.append(f"{key} = ?")
        values.append(value)

    set_parts.append("updated_at = ?")
    values.append(_now_iso())
    values.append(customer_id)

    with get_db_ctx() as conn:
        result = conn.execute(
            f"UPDATE customers SET {', '.join(set_parts)} WHERE id = ?",
            values,
        )
        if result.rowcount == 0:
            return None

    return get_customer(customer_id)


def delete_customer(customer_id: int) -> bool:
    """Delete a customer and its related follow-ups / quotes."""
    _lazy_init()
    with get_db_ctx() as conn:
        # Delete related records first
        conn.execute("DELETE FROM follow_ups WHERE customer_id = ?", (customer_id,))
        conn.execute("DELETE FROM quotes WHERE customer_id = ?", (customer_id,))
        result = conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        return result.rowcount > 0


def list_customers(
    filter_params: Optional[CustomerFilter] = None,
    user_id: Optional[int] = None,
) -> List[dict]:
    """List customers with optional filtering."""
    _lazy_init()
    clauses: List[str] = []
    params: list = []

    # Non-admin users see only their own or assigned customers
    if user_id is not None:
        clauses.append("(assigned_to = ? OR user_id = ?)")
        params.extend([user_id, user_id])

    if filter_params:
        if filter_params.status:
            clauses.append("status = ?")
            params.append(filter_params.status.value)
        if filter_params.source:
            clauses.append("source = ?")
            params.append(filter_params.source.value)
        if filter_params.priority:
            clauses.append("priority = ?")
            params.append(filter_params.priority.value)
        if filter_params.industry:
            clauses.append("industry = ?")
            params.append(filter_params.industry)
        if filter_params.country:
            clauses.append("country = ?")
            params.append(filter_params.country)
        if filter_params.assigned_to:
            clauses.append("assigned_to = ?")
            params.append(filter_params.assigned_to)
        if filter_params.tags:
            # Match any of the provided tags (JSON array stored as text)
            tag_clauses = []
            for tag in filter_params.tags:
                tag_clauses.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
            clauses.append(f"({' OR '.join(tag_clauses)})")
        if filter_params.created_after:
            clauses.append("created_at >= ?")
            params.append(str(filter_params.created_after))
        if filter_params.created_before:
            clauses.append("created_at <= ?")
            params.append(str(filter_params.created_before) + " 23:59:59")
        if filter_params.search:
            search = f"%{filter_params.search}%"
            clauses.append("(name LIKE ? OR company LIKE ? OR email LIKE ?)")
            params.extend([search, search, search])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_db_ctx() as conn:
        rows = conn.execute(
            f"SELECT * FROM customers {where} ORDER BY updated_at DESC",
            params,
        ).fetchall()

    customers = [_row_to_customer_dict(r) for r in rows]

    # Sort by priority then updated_at (descending)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    customers.sort(
        key=lambda c: (priority_order.get(c["priority"], 1), c["updated_at"] or datetime.min),
        reverse=True,
    )
    # Fix sort: high priority first, then newest
    customers.sort(
        key=lambda c: (priority_order.get(c["priority"], 1), -(c["updated_at"] or datetime.min).timestamp()),
    )

    return customers


# ========== Follow-up records ==========

def create_followup(followup_data: FollowUpCreate, created_by: int) -> Optional[dict]:
    """Create a follow-up record. Returns dict or None if customer doesn't exist."""
    _lazy_init()
    # Verify customer exists
    with get_db_ctx() as conn:
        cust = conn.execute(
            "SELECT id FROM customers WHERE id = ?", (followup_data.customer_id,)
        ).fetchone()
    if cust is None:
        return None

    now = _now_iso()
    with get_db_ctx() as conn:
        cur = conn.execute(
            """INSERT INTO follow_ups
                   (user_id, customer_id, type, content, scheduled_at,
                    completed_at, outcome, next_action, next_action_date,
                    follow_up_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                created_by,
                followup_data.customer_id,
                followup_data.type.value if hasattr(followup_data.type, "value") else followup_data.type,
                followup_data.content,
                followup_data.scheduled_at.strftime("%Y-%m-%d %H:%M:%S") if followup_data.scheduled_at else None,
                followup_data.completed_at.strftime("%Y-%m-%d %H:%M:%S") if followup_data.completed_at else None,
                followup_data.outcome,
                followup_data.next_action,
                str(followup_data.next_action_date) if followup_data.next_action_date else None,
                str(followup_data.scheduled_at.date()) if followup_data.scheduled_at else None,
                "completed" if followup_data.completed_at else "pending",
                now,
            ),
        )
        followup_id: int = cur.lastrowid  # type: ignore[assignment]

        # Update customer's last_contact_at
        conn.execute(
            "UPDATE customers SET last_contact_at = ?, updated_at = ? WHERE id = ?",
            (now, now, followup_data.customer_id),
        )

    return _get_followup(followup_id)


def _get_followup(followup_id: int) -> Optional[dict]:
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM follow_ups WHERE id = ?", (followup_id,)
        ).fetchone()
    return _row_to_followup_dict(row) if row else None


def get_customer_followups(customer_id: int) -> List[dict]:
    """Return follow-ups for a customer, newest first."""
    _lazy_init()
    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM follow_ups WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()
    return [_row_to_followup_dict(r) for r in rows]


def get_pending_followups(user_id: Optional[int] = None) -> List[dict]:
    """Return pending follow-ups (scheduled in the future or action-date reached)."""
    _lazy_init()
    today = date.today().isoformat()
    now = _now_iso()

    clauses = [
        "(completed_at IS NULL OR completed_at = '')",
        f"((scheduled_at IS NOT NULL AND scheduled_at >= ?) OR "
        f"(next_action_date IS NOT NULL AND next_action_date <= ?))",
    ]
    params: list = [now, today]

    if user_id is not None:
        clauses.append(
            "customer_id IN (SELECT id FROM customers WHERE assigned_to = ? OR user_id = ?)"
        )
        params.extend([user_id, user_id])

    where = " AND ".join(clauses)
    with get_db_ctx() as conn:
        rows = conn.execute(
            f"SELECT * FROM follow_ups WHERE {where} ORDER BY COALESCE(scheduled_at, next_action_date)",
            params,
        ).fetchall()

    return [_row_to_followup_dict(r) for r in rows]


def complete_followup(followup_id: int, outcome: Optional[str] = None) -> Optional[dict]:
    """Mark a follow-up as completed."""
    _lazy_init()
    now = _now_iso()
    with get_db_ctx() as conn:
        result = conn.execute(
            "UPDATE follow_ups SET completed_at = ?, status = 'completed', outcome = COALESCE(?, outcome) WHERE id = ?",
            (now, outcome, followup_id),
        )
        if result.rowcount == 0:
            return None
    return _get_followup(followup_id)


# ========== Quotes ==========

def create_quote(quote_data: QuoteCreate, created_by: int) -> Optional[dict]:
    """Create a quote. Returns dict or None if customer doesn't exist."""
    _lazy_init()
    # Verify customer exists
    with get_db_ctx() as conn:
        cust = conn.execute(
            "SELECT id FROM customers WHERE id = ?", (quote_data.customer_id,)
        ).fetchone()
    if cust is None:
        return None

    now = _now_iso()

    # Calculate totals
    items_list = []
    subtotal = 0.0
    for item in quote_data.items:
        line_total = item.quantity * item.unit_price
        subtotal += line_total
        items_list.append({
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total": line_total,
        })

    tax_rate = quote_data.tax_rate or 0.0
    tax_amount = subtotal * (tax_rate / 100)
    total = subtotal + tax_amount

    with get_db_ctx() as conn:
        cur = conn.execute(
            """INSERT INTO quotes
                   (user_id, customer_id, quote_number, items, currency,
                    subtotal, tax_rate, tax_amount, total, valid_until,
                    notes, status, content, amount, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                created_by,
                quote_data.customer_id,
                quote_data.quote_number,
                json.dumps(items_list),
                quote_data.currency or "USD",
                round(subtotal, 2),
                tax_rate,
                round(tax_amount, 2),
                round(total, 2),
                str(quote_data.valid_until) if quote_data.valid_until else None,
                quote_data.notes,
                quote_data.status or "draft",
                quote_data.quote_number,  # content fallback
                round(total, 2),          # amount fallback
                now,
                now,
            ),
        )
        quote_id: int = cur.lastrowid  # type: ignore[assignment]

        # Update customer stats
        conn.execute(
            "UPDATE customers SET total_quotes = total_quotes + 1, updated_at = ? WHERE id = ?",
            (now, quote_data.customer_id),
        )

    return _get_quote(quote_id)


def _get_quote(quote_id: int) -> Optional[dict]:
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM quotes WHERE id = ?", (quote_id,)
        ).fetchone()
    return _row_to_quote_dict(row) if row else None


def get_customer_quotes(customer_id: int) -> List[dict]:
    """Return quotes for a customer, newest first."""
    _lazy_init()
    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM quotes WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()
    return [_row_to_quote_dict(r) for r in rows]


# ========== Statistics ==========

def get_customer_stats() -> CustomerStats:
    """Aggregate CRM statistics."""
    _lazy_init()
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM customers").fetchall()

    customers = [_row_to_customer_dict(r) for r in rows]

    by_status: Dict[str, int] = defaultdict(int)
    by_source: Dict[str, int] = defaultdict(int)
    by_priority: Dict[str, int] = defaultdict(int)
    by_country: Dict[str, int] = defaultdict(int)

    new_this_month = 0
    new_this_week = 0
    total_revenue = 0.0
    total_quotes = 0
    total_orders = 0

    for c in customers:
        by_status[c["status"]] += 1
        by_source[c["source"]] += 1
        by_priority[c["priority"]] += 1
        if c["country"]:
            by_country[c["country"]] += 1

        ca = c["created_at"]
        if ca and ca >= this_month_start:
            new_this_month += 1
        if ca and ca >= this_week_start:
            new_this_week += 1

        total_revenue += c.get("total_revenue", 0)
        total_quotes += c.get("total_quotes", 0)
        total_orders += c.get("total_orders", 0)

    total_leads = len(customers)
    won = by_status.get("won", 0)
    conversion_rate = (won / total_leads * 100) if total_leads > 0 else 0

    return CustomerStats(
        total_customers=total_leads,
        by_status=dict(by_status),
        by_source=dict(by_source),
        by_priority=dict(by_priority),
        by_country=dict(by_country),
        new_this_month=new_this_month,
        new_this_week=new_this_week,
        conversion_rate=round(conversion_rate, 2),
        total_revenue=round(total_revenue, 2),
        total_quotes=total_quotes,
        total_orders=total_orders,
    )


def get_pipeline_summary() -> PipelineSummary:
    """Build the sales pipeline funnel."""
    _lazy_init()
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM customers").fetchall()

    customers = [_row_to_customer_dict(r) for r in rows]

    stages_def = [
        ("lead", "潜在客户"),
        ("contacted", "已联系"),
        ("quoted", "已报价"),
        ("negotiating", "谈判中"),
        ("won", "成交"),
        ("lost", "流失"),
    ]

    pipeline_stages: List[PipelineStage] = []
    total_value = 0.0

    for idx, (stage_key, stage_label) in enumerate(stages_def):
        stage_customers = [c for c in customers if c["status"] == stage_key]
        count = len(stage_customers)
        value = sum(c.get("total_revenue", 0) for c in stage_customers)

        # Conversion relative to previous stage
        if idx > 0:
            prev_key = stages_def[idx - 1][0]
            prev_count = sum(1 for c in customers if c["status"] == prev_key)
            conversion = (count / prev_count * 100) if prev_count > 0 else 0
        else:
            conversion = 100.0

        # Average days in stage (simplified: days since creation)
        avg_days = 0.0
        if stage_customers:
            days = [
                (datetime.utcnow() - c["created_at"]).days
                for c in stage_customers
                if c["created_at"]
            ]
            avg_days = (sum(days) / len(days)) if days else 0.0

        pipeline_stages.append(
            PipelineStage(
                stage=stage_label,
                count=count,
                value=round(value, 2),
                conversion_rate=round(conversion, 2),
                avg_days=round(avg_days, 1),
            )
        )
        total_value += value

    total_leads = len(customers)
    won = sum(1 for c in customers if c["status"] == "won")
    overall_conversion = (won / total_leads * 100) if total_leads > 0 else 0

    won_customers = [c for c in customers if c["status"] == "won"]
    avg_deal_size = (total_value / len(won_customers)) if won_customers else 0

    sales_cycles = []
    for c in won_customers:
        if c["created_at"]:
            sales_cycles.append((datetime.utcnow() - c["created_at"]).days)
    avg_sales_cycle = (sum(sales_cycles) / len(sales_cycles)) if sales_cycles else 0

    return PipelineSummary(
        stages=pipeline_stages,
        total_leads=total_leads,
        total_value=round(total_value, 2),
        overall_conversion=round(overall_conversion, 2),
        avg_deal_size=round(avg_deal_size, 2),
        avg_sales_cycle=round(avg_sales_cycle, 1),
    )


def get_recent_activities(limit: int = 20) -> List[Dict]:
    """Unified activity feed from customers, follow-ups, and quotes."""
    _lazy_init()
    activities: List[Dict] = []

    with get_db_ctx() as conn:
        # Customer creations
        for c in conn.execute("SELECT * FROM customers ORDER BY created_at DESC").fetchall():
            cd = dict(c)
            activities.append({
                "type": "customer_created",
                "description": f"创建客户: {cd['name']}",
                "timestamp": _parse_dt(cd.get("created_at")),
                "customer_id": cd["id"],
                "user_id": cd.get("user_id"),
            })

        # Follow-ups
        for f in conn.execute("SELECT * FROM follow_ups ORDER BY created_at DESC").fetchall():
            fd = dict(f)
            activities.append({
                "type": "followup",
                "description": f"跟进: {fd.get('type', 'note')}",
                "timestamp": _parse_dt(fd.get("created_at")),
                "customer_id": fd["customer_id"],
                "user_id": fd.get("user_id"),
            })

        # Quotes
        for q in conn.execute("SELECT * FROM quotes ORDER BY created_at DESC").fetchall():
            qd = dict(q)
            activities.append({
                "type": "quote_created",
                "description": f"创建报价: {qd.get('quote_number', '')}",
                "timestamp": _parse_dt(qd.get("created_at")),
                "customer_id": qd["customer_id"],
                "user_id": qd.get("user_id"),
            })

    activities.sort(key=lambda a: a["timestamp"] or datetime.min, reverse=True)
    return activities[:limit]
