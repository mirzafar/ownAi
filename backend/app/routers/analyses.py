"""Универсальный CRUD для коллекции `analyses` — звонки, чаты, лиды в одном месте."""

import os
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from ..auth import get_current_user
from ..database import analyses, audio_bucket
from ..models import AnalysisOut
from ..openai_service import analyze_unit, transcribe_audio
from ..services import analysis_service as svc

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB — лимит OpenAI
ALLOWED_EXTENSIONS = {
    ".mp3", ".mpeg", ".mpga", ".m4a", ".wav", ".webm",
    ".ogg", ".oga", ".flac", ".mp4", ".m4v", ".aac",
}


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Bad date: {value}")


# ─── Список и деталка ────────────────────────────────────────────────────────

@router.get("", response_model=List[AnalysisOut])
async def list_items(
    kind: Optional[str] = Query(None, description="all | call | lead | chat"),
    status_q: Optional[str] = Query(None, alias="status"),
    manager_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    user=Depends(get_current_user),
) -> List[AnalysisOut]:
    return await svc.list_analyses(
        user["_id"],
        kind=kind,
        status=status_q,
        manager_id=manager_id,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
        limit=limit,
        skip=skip,
    )


@router.get("/{analysis_id}", response_model=AnalysisOut)
async def get_item(analysis_id: str, user=Depends(get_current_user)) -> AnalysisOut:
    doc = await svc.find_by_id(user["_id"], analysis_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return svc.doc_to_out(doc)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(analysis_id: str, user=Depends(get_current_user)) -> None:
    if not await svc.delete(user["_id"], analysis_id):
        raise HTTPException(status_code=404, detail="Not found")


# ─── Аудио (для звонков) ─────────────────────────────────────────────────────

@router.get("/{analysis_id}/audio")
async def stream_audio(analysis_id: str, user=Depends(get_current_user)):
    doc = await svc.find_by_id(user["_id"], analysis_id)
    if not doc or not doc.get("audio_file_id"):
        raise HTTPException(status_code=404, detail="Аудио недоступно")
    stream = await audio_bucket.open_download_stream(doc["audio_file_id"])

    async def iterator():
        try:
            while True:
                chunk = await stream.readchunk()
                if not chunk:
                    break
                yield chunk
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result

    return StreamingResponse(
        iterator(),
        media_type=doc.get("audio_content_type") or "audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="{doc.get("title", "audio.mp3")}"'},
    )


# ─── Прямой upload аудио (без Bitrix) ────────────────────────────────────────

@router.post("/upload", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def upload_audio(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
) -> AnalysisOut:
    ext = os.path.splitext(file.filename or "")[1].lower()
    ctype = (file.content_type or "").lower()
    if not (ctype.startswith("audio/") or ctype.startswith("video/") or ext in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type or ext or 'unknown'}",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 25MB)")

    now = datetime.now(timezone.utc)
    title = file.filename or "audio"

    # Создаём запись со статусом processing и сразу льём аудио в GridFS
    placeholder = {
        "user_id": user["_id"],
        "kind": "call",
        "status": "processing",
        "title": title,
        "date": now,
        "duration": 0,
        "manager": "",
        "manager_id": "",
        "source_text": "",
        "scoring": None,
        "call": {
            "bitrix_call_id": "",
            "phone": "",
            "direction": "",
            "record_url": "",
            "has_audio": True,
            "language": "",
        },
        "created_at": now,
        "updated_at": now,
        "error": "",
    }
    result = await analyses.insert_one(placeholder)
    aid = result.inserted_id

    audio_file_id = await audio_bucket.upload_from_stream(
        title, contents,
        metadata={"user_id": user["_id"], "analysis_id": aid, "content_type": file.content_type or "audio/mpeg"},
    )
    await analyses.update_one(
        {"_id": aid},
        {"$set": {"audio_file_id": audio_file_id, "audio_content_type": file.content_type or "audio/mpeg"}},
    )

    try:
        text = await transcribe_audio(contents, title)
        scoring = await analyze_unit(text, source="call")
        await analyses.update_one(
            {"_id": aid},
            {"$set": {
                "source_text": text,
                "scoring": scoring.model_dump(),
                "status": "done",
                "error": "",
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    except Exception as exc:
        await analyses.update_one(
            {"_id": aid},
            {"$set": {"status": "failed", "error": str(exc)[:500],
                      "updated_at": datetime.now(timezone.utc)}},
        )
        raise HTTPException(status_code=502, detail=f"Анализ не выполнен: {exc}")

    fresh = await analyses.find_one({"_id": aid})
    return svc.doc_to_out(fresh)


# ─── Пересчёт анализа ────────────────────────────────────────────────────────

@router.post("/{analysis_id}/reanalyze", response_model=AnalysisOut)
async def reanalyze(analysis_id: str, user=Depends(get_current_user)) -> AnalysisOut:
    doc = await svc.find_by_id(user["_id"], analysis_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if doc.get("kind") == "lead":
        raise HTTPException(
            status_code=400,
            detail="Перезапуск анализа лида — через POST /api/bitrix/leads/{id}/analyze?force=true",
        )

    text = (doc.get("source_text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Нет исходного текста — сначала транскрипция")

    await svc.set_status(user["_id"], analysis_id, "processing")
    try:
        scoring = await analyze_unit(text, source=doc.get("kind") or "call")
        await analyses.update_one(
            {"_id": ObjectId(analysis_id), "user_id": user["_id"]},
            {"$set": {
                "scoring": scoring.model_dump(),
                "status": "done",
                "error": "",
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    except Exception as exc:
        await svc.set_status(user["_id"], analysis_id, "failed", error=str(exc)[:500])
        raise HTTPException(status_code=502, detail=f"Анализ не выполнен: {exc}")

    fresh = await svc.find_by_id(user["_id"], analysis_id)
    return svc.doc_to_out(fresh)


# ─── Пересмотр транскрипции по сохранённому аудио ────────────────────────────

@router.post("/{analysis_id}/retranscribe", response_model=AnalysisOut)
async def retranscribe(analysis_id: str, user=Depends(get_current_user)) -> AnalysisOut:
    doc = await svc.find_by_id(user["_id"], analysis_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if not doc.get("audio_file_id"):
        raise HTTPException(status_code=400, detail="Аудио не сохранено")

    await svc.set_status(user["_id"], analysis_id, "processing")
    try:
        stream = await audio_bucket.open_download_stream(doc["audio_file_id"])
        chunks: list[bytes] = []
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            chunks.append(chunk)
        audio_bytes = b"".join(chunks)
        text = await transcribe_audio(audio_bytes, doc.get("title") or "audio.mp3")
        scoring = await analyze_unit(text, source=doc.get("kind") or "call")
        await analyses.update_one(
            {"_id": ObjectId(analysis_id), "user_id": user["_id"]},
            {"$set": {
                "source_text": text,
                "scoring": scoring.model_dump(),
                "status": "done",
                "error": "",
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    except Exception as exc:
        await svc.set_status(user["_id"], analysis_id, "failed", error=str(exc)[:500])
        raise HTTPException(status_code=502, detail=f"Транскрипция не выполнена: {exc}")

    fresh = await svc.find_by_id(user["_id"], analysis_id)
    return svc.doc_to_out(fresh)
