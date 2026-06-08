"""
LinkedIn Activity Analytics — track post engagement, connection growth, messaging stats
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from backend.database import get_db_ctx

logger = logging.getLogger(__name__)


def get_linkedin_overview(days: int = 30) -> Dict[str, Any]:
    """
    Get LinkedIn activity overview for the last N days.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    
    with get_db_ctx() as conn:
        # Posts statistics
        posts_total = conn.execute(
            "SELECT COUNT(*) FROM linkedin_posts WHERE DATE(created_at) >= ?",
            (since,)
        ).fetchone()[0]
        
        posts_published = conn.execute(
            "SELECT COUNT(*) FROM linkedin_posts WHERE status = 'published' AND DATE(published_at) >= ?",
            (since,)
        ).fetchone()[0]
        
        posts_draft = conn.execute(
            "SELECT COUNT(*) FROM linkedin_posts WHERE status = 'draft' AND DATE(created_at) >= ?",
            (since,)
        ).fetchone()[0]
        
        # Engagement totals
        engagement = conn.execute(
            """SELECT 
                COALESCE(SUM(likes_count), 0) as total_likes,
                COALESCE(SUM(comments_count), 0) as total_comments,
                COALESCE(SUM(views_count), 0) as total_views
            FROM linkedin_posts 
            WHERE status = 'published' AND DATE(published_at) >= ?""",
            (since,)
        ).fetchone()
        
        # Tasks statistics
        tasks_total = conn.execute(
            "SELECT COUNT(*) FROM linkedin_tasks WHERE DATE(created_at) >= ?",
            (since,)
        ).fetchone()[0]
        
        tasks_by_type = {}
        for row in conn.execute(
            "SELECT task_type, COUNT(*) as c, COALESCE(SUM(result_count), 0) as total FROM linkedin_tasks WHERE DATE(created_at) >= ? GROUP BY task_type",
            (since,)
        ).fetchall():
            tasks_by_type[row['task_type']] = {
                "count": row['c'],
                "total_results": row['total'],
            }
        
        # Connection growth
        connections_sent = conn.execute(
            "SELECT COALESCE(SUM(result_count), 0) FROM linkedin_tasks WHERE task_type = 'connect' AND DATE(created_at) >= ?",
            (since,)
        ).fetchone()[0]
        
        messages_sent = conn.execute(
            "SELECT COALESCE(SUM(result_count), 0) FROM linkedin_tasks WHERE task_type = 'message' AND DATE(created_at) >= ?",
            (since,)
        ).fetchone()[0]
        
        # Customer pipeline impact
        new_customers = conn.execute(
            "SELECT COUNT(*) FROM customers WHERE source LIKE '%linkedin%' AND DATE(created_at) >= ?",
            (since,)
        ).fetchone()[0]
    
    return {
        "period_days": days,
        "since": since,
        "posts": {
            "total": posts_total,
            "published": posts_published,
            "draft": posts_draft,
        },
        "engagement": {
            "likes": engagement['total_likes'],
            "comments": engagement['total_comments'],
            "views": engagement['total_views'],
            "avg_likes": round(engagement['total_likes'] / max(posts_published, 1), 1),
            "avg_comments": round(engagement['total_comments'] / max(posts_published, 1), 1),
        },
        "tasks": {
            "total": tasks_total,
            "by_type": tasks_by_type,
        },
        "outreach": {
            "connections_sent": connections_sent,
            "messages_sent": messages_sent,
        },
        "pipeline": {
            "new_customers_from_linkedin": new_customers,
        },
    }


def get_post_performance(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get performance data for recent posts.
    """
    with get_db_ctx() as conn:
        rows = conn.execute(
            """SELECT id, content, image_paths, status, post_url,
                      likes_count, comments_count, views_count,
                      published_at, created_at
            FROM linkedin_posts 
            WHERE status = 'published'
            ORDER BY published_at DESC 
            LIMIT ?""",
            (limit,)
        ).fetchall()
    
    posts = []
    for row in rows:
        post = dict(row)
        # Truncate content for display
        if post['content'] and len(post['content']) > 150:
            post['content_preview'] = post['content'][:150] + '...'
        else:
            post['content_preview'] = post['content']
        
        # Calculate engagement rate
        if post['views_count'] and post['views_count'] > 0:
            post['engagement_rate'] = round(
                ((post['likes_count'] + post['comments_count']) / post['views_count']) * 100, 2
            )
        else:
            post['engagement_rate'] = 0
        
        posts.append(post)
    
    return posts


def get_daily_activity_trend(days: int = 30) -> List[Dict[str, Any]]:
    """
    Get daily activity trend for the last N days.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    
    with get_db_ctx() as conn:
        # Posts per day
        posts_by_day = {}
        for row in conn.execute(
            "SELECT DATE(published_at) as day, COUNT(*) as c FROM linkedin_posts WHERE status = 'published' AND DATE(published_at) >= ? GROUP BY day",
            (since,)
        ).fetchall():
            posts_by_day[row['day']] = row['c']
        
        # Tasks per day
        tasks_by_day = {}
        for row in conn.execute(
            "SELECT DATE(created_at) as day, task_type, COALESCE(SUM(result_count), 0) as total FROM linkedin_tasks WHERE DATE(created_at) >= ? GROUP BY day, task_type",
            (since,)
        ).fetchall():
            if row['day'] not in tasks_by_day:
                tasks_by_day[row['day']] = {}
            tasks_by_day[row['day']][row['task_type']] = row['total']
    
    # Build trend data
    trend = []
    current = date.today()
    for i in range(days):
        day = (current - timedelta(days=days - 1 - i)).isoformat()
        trend.append({
            "date": day,
            "posts": posts_by_day.get(day, 0),
            "connections": tasks_by_day.get(day, {}).get('connect', 0),
            "messages": tasks_by_day.get(day, {}).get('message', 0),
            "searches": tasks_by_day.get(day, {}).get('search', 0),
        })
    
    return trend


def get_content_topics_analysis() -> Dict[str, Any]:
    """
    Analyze post content topics and their performance.
    """
    with get_db_ctx() as conn:
        rows = conn.execute(
            """SELECT content, likes_count, comments_count, views_count
            FROM linkedin_posts 
            WHERE status = 'published' AND content IS NOT NULL
            ORDER BY published_at DESC 
            LIMIT 50"""
        ).fetchall()
    
    # Simple keyword analysis
    keywords = {
        'freight': {'count': 0, 'likes': 0, 'comments': 0},
        'shipping': {'count': 0, 'likes': 0, 'comments': 0},
        'logistics': {'count': 0, 'likes': 0, 'comments': 0},
        'supply chain': {'count': 0, 'likes': 0, 'comments': 0},
        'warehouse': {'count': 0, 'likes': 0, 'comments': 0},
        'customs': {'count': 0, 'likes': 0, 'comments': 0},
        'trade': {'count': 0, 'likes': 0, 'comments': 0},
        'import': {'count': 0, 'likes': 0, 'comments': 0},
        'export': {'count': 0, 'likes': 0, 'comments': 0},
    }
    
    for row in rows:
        content_lower = (row['content'] or '').lower()
        for keyword in keywords:
            if keyword in content_lower:
                keywords[keyword]['count'] += 1
                keywords[keyword]['likes'] += row['likes_count'] or 0
                keywords[keyword]['comments'] += row['comments_count'] or 0
    
    # Calculate average engagement per keyword
    for keyword, data in keywords.items():
        if data['count'] > 0:
            data['avg_likes'] = round(data['likes'] / data['count'], 1)
            data['avg_comments'] = round(data['comments'] / data['count'], 1)
        else:
            data['avg_likes'] = 0
            data['avg_comments'] = 0
    
    return {
        "keywords": keywords,
        "total_posts_analyzed": len(rows),
    }


def update_post_engagement(post_id: int, likes: int = 0, comments: int = 0, views: int = 0) -> bool:
    """
    Update engagement metrics for a post (manual or API sync).
    """
    try:
        with get_db_ctx() as conn:
            conn.execute(
                """UPDATE linkedin_posts 
                SET likes_count = ?, comments_count = ?, views_count = ?
                WHERE id = ?""",
                (likes, comments, views, post_id)
            )
        return True
    except Exception as e:
        logger.error("Failed to update post engagement: %s", e)
        return False


def get_top_performing_posts(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get top performing posts by engagement.
    """
    with get_db_ctx() as conn:
        rows = conn.execute(
            """SELECT id, content, likes_count, comments_count, views_count,
                      (likes_count + comments_count) as total_engagement,
                      published_at
            FROM linkedin_posts 
            WHERE status = 'published'
            ORDER BY total_engagement DESC 
            LIMIT ?""",
            (limit,)
        ).fetchall()
    
    return [dict(r) for r in rows]
