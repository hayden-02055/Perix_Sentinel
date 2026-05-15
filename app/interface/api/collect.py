from fastapi import APIRouter

router = APIRouter()


@router.post("/collect")
async def trigger_collect() -> dict:
    # TODO: wire up collect_trends use case
    return {"status": "triggered"}
