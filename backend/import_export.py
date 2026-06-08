"""
Customer Import/Export — CSV/Excel support
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.database import get_db_ctx

logger = logging.getLogger(__name__)


def import_customers_csv(file_content: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Import customers from CSV content.
    
    Expected columns (flexible matching):
    - name / 姓名 / contact_name
    - company / 公司 / company_name
    - title / 职位 / job_title
    - email / 邮箱
    - phone / 电话
    - linkedin_url / LinkedIn
    - tags / 标签
    - notes / 备注
    - source / 来源
    """
    # Column mapping
    column_map = {
        'name': 'name',
        '姓名': 'name',
        'contact_name': 'name',
        'company': 'company',
        '公司': 'company',
        'company_name': 'company',
        'title': 'title',
        '职位': 'title',
        'job_title': 'title',
        'email': 'email',
        '邮箱': 'email',
        'phone': 'phone',
        '电话': 'phone',
        'linkedin_url': 'linkedin_url',
        'linkedin': 'linkedin_url',
        'tags': 'tags',
        '标签': 'tags',
        'notes': 'notes',
        '备注': 'notes',
        'source': 'source',
        '来源': 'source',
    }
    
    reader = csv.DictReader(io.StringIO(file_content))
    
    imported = 0
    skipped = 0
    errors = []
    
    with get_db_ctx() as conn:
        for row_num, row in enumerate(reader, start=2):
            try:
                # Map columns
                customer = {}
                for csv_col, value in row.items():
                    if csv_col and csv_col.lower().strip() in column_map:
                        db_col = column_map[csv_col.lower().strip()]
                        customer[db_col] = value.strip() if value else ''
                
                # Validate required fields
                if not customer.get('name'):
                    errors.append(f"Row {row_num}: Missing name")
                    skipped += 1
                    continue
                
                # Check for duplicates (by email or linkedin_url)
                if customer.get('email'):
                    existing = conn.execute(
                        "SELECT id FROM customers WHERE email = ?",
                        (customer['email'],)
                    ).fetchone()
                    if existing:
                        errors.append(f"Row {row_num}: Duplicate email {customer['email']}")
                        skipped += 1
                        continue
                
                if customer.get('linkedin_url'):
                    existing = conn.execute(
                        "SELECT id FROM customers WHERE linkedin_url = ?",
                        (customer['linkedin_url'],)
                    ).fetchone()
                    if existing:
                        errors.append(f"Row {row_num}: Duplicate LinkedIn URL")
                        skipped += 1
                        continue
                
                # Insert
                conn.execute(
                    """INSERT INTO customers 
                       (user_id, name, company, title, email, phone, linkedin_url, tags, notes, source, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')""",
                    (
                        user_id,
                        customer.get('name', ''),
                        customer.get('company', ''),
                        customer.get('title', ''),
                        customer.get('email', ''),
                        customer.get('phone', ''),
                        customer.get('linkedin_url', ''),
                        customer.get('tags', ''),
                        customer.get('notes', ''),
                        customer.get('source', 'csv_import'),
                    )
                )
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                skipped += 1
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:20],  # Limit error messages
    }


def export_customers_csv(
    status: Optional[str] = None,
    tags: Optional[str] = None,
    user_id: Optional[int] = None,
) -> str:
    """
    Export customers to CSV content.
    """
    query = "SELECT * FROM customers WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if tags:
        query += " AND tags LIKE ?"
        params.append(f"%{tags}%")
    
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    
    query += " ORDER BY created_at DESC"
    
    with get_db_ctx() as conn:
        rows = conn.execute(query, params).fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Name', 'Company', 'Title', 'Email', 'Phone', 
        'LinkedIn URL', 'Status', 'Tags', 'Notes', 'Source',
        'Created At', 'Updated At'
    ])
    
    # Data
    for row in rows:
        writer.writerow([
            row['name'],
            row['company'],
            row['title'],
            row['email'],
            row['phone'],
            row['linkedin_url'],
            row['status'],
            row['tags'],
            row['notes'],
            row['source'],
            row['created_at'],
            row['updated_at'],
        ])
    
    return output.getvalue()


def export_follow_ups_csv(customer_id: Optional[int] = None) -> str:
    """
    Export follow-up records to CSV.
    """
    query = """
        SELECT f.*, c.name as customer_name, c.company 
        FROM follow_ups f
        LEFT JOIN customers c ON f.customer_id = c.id
        WHERE 1=1
    """
    params = []
    
    if customer_id:
        query += " AND f.customer_id = ?"
        params.append(customer_id)
    
    query += " ORDER BY f.created_at DESC"
    
    with get_db_ctx() as conn:
        rows = conn.execute(query, params).fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Customer', 'Company', 'Content', 'Follow Date', 'Status', 'Created At'])
    
    for row in rows:
        writer.writerow([
            row['customer_name'],
            row['company'],
            row['content'],
            row['follow_up_date'],
            row['status'],
            row['created_at'],
        ])
    
    return output.getvalue()


def get_import_template() -> str:
    """
    Generate a CSV template for import.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['name', 'company', 'title', 'email', 'phone', 'linkedin_url', 'tags', 'notes', 'source'])
    writer.writerow(['John Smith', 'Amazon', 'Supply Chain Manager', 'john@amazon.com', '+1-555-0123', 'https://linkedin.com/in/johnsmith', 'US,enterprise', 'Met at conference', 'manual'])
    writer.writerow(['Marie Dupont', 'Carrefour', 'Logistics Director', 'marie@carrefour.fr', '+33-1-2345', 'https://linkedin.com/in/mariedupont', 'EU,retail', '', 'linkedin_search'])
    
    return output.getvalue()


def get_export_stats() -> Dict[str, Any]:
    """
    Get statistics about exportable data.
    """
    with get_db_ctx() as conn:
        total = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        
        by_status = {}
        for row in conn.execute("SELECT status, COUNT(*) as c FROM customers GROUP BY status"):
            by_status[row['status']] = row['c']
        
        with_email = conn.execute("SELECT COUNT(*) FROM customers WHERE email IS NOT NULL AND email != ''").fetchone()[0]
        with_linkedin = conn.execute("SELECT COUNT(*) FROM customers WHERE linkedin_url IS NOT NULL AND linkedin_url != ''").fetchone()[0]
        
        follow_ups = conn.execute("SELECT COUNT(*) FROM follow_ups").fetchone()[0]
    
    return {
        "total_customers": total,
        "by_status": by_status,
        "with_email": with_email,
        "with_linkedin": with_linkedin,
        "total_follow_ups": follow_ups,
    }
