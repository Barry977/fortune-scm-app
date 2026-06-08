"""
Import/Export API routes.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import io

from backend.auth import get_current_user
from backend.import_export import (
    import_customers_csv,
    export_customers_csv,
    export_follow_ups_csv,
    get_import_template,
    get_export_stats,
)

router = APIRouter(prefix="/api/data", tags=["数据导入导出"])


class ExportRequest(BaseModel):
    status: Optional[str] = Field(None, description="Filter by status")
    tags: Optional[str] = Field(None, description="Filter by tags (partial match)")


@router.get("/import-template")
async def download_template(current_user=Depends(get_current_user)):
    """Download CSV import template."""
    template = get_import_template()
    return StreamingResponse(
        io.BytesIO(template.encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customer_import_template.csv"}
    )


@router.post("/import")
async def import_customers(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    """Import customers from CSV file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    try:
        content = await file.read()
        # Try different encodings
        for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']:
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise HTTPException(status_code=400, detail="Unable to decode file. Please use UTF-8 encoding.")
        
        result = import_customers_csv(text, user_id=current_user.get("id"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_customers(req: ExportRequest, current_user=Depends(get_current_user)):
    """Export customers to CSV."""
    try:
        csv_content = export_customers_csv(
            status=req.status,
            tags=req.tags,
            user_id=current_user.get("id"),
        )
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=customers_export_{__import__('datetime').datetime.now().strftime('%Y%m%d')}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-follow-ups")
async def export_follow_ups(customer_id: Optional[int] = None, current_user=Depends(get_current_user)):
    """Export follow-up records to CSV."""
    try:
        csv_content = export_follow_ups_csv(customer_id=customer_id)
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=follow_ups_export_{__import__('datetime').datetime.now().strftime('%Y%m%d')}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def export_statistics(current_user=Depends(get_current_user)):
    """Get export statistics."""
    try:
        return get_export_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
