from fastapi import APIRouter, HTTPException
from models import LinkedinSearch, LinkedinConnect, LinkedinMessage
from services import linkedin_service

router = APIRouter(prefix="/api/linkedin", tags=["LinkedIn"])


@router.post("/login")
async def login():
    try:
        return await linkedin_service.open_login()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def status():
    try:
        return await linkedin_service.check_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search(body: LinkedinSearch):
    try:
        results = await linkedin_service.search_people(
            body.keywords, body.location, body.title, body.company, body.limit
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect")
async def connect(body: LinkedinConnect):
    try:
        return await linkedin_service.send_connect(body.profile_url, body.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message")
async def message(body: LinkedinMessage):
    try:
        return await linkedin_service.send_message(body.profile_url, body.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
