import os
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ..auth import get_current_user
from ..database import transcriptions
from ..models import AnalysisResult, TranscriptionOut
from ..openai_service import analyze_transcript, transcribe_audio

router = APIRouter(prefix="/api/transcriptions", tags=["transcriptions"])

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB — OpenAI limit
ALLOWED_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/x-mpeg", "audio/mpeg3", "audio/mpga",
    "audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave",
    "audio/webm", "audio/ogg", "audio/vorbis",
    "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/aac",
    "audio/flac", "audio/x-flac",
    "video/mp4", "video/webm", "video/mpeg", "video/x-mpeg",
}
ALLOWED_EXTENSIONS = {
    ".mp3", ".mpeg", ".mpga", ".m4a", ".wav", ".webm",
    ".ogg", ".oga", ".flac", ".mp4", ".m4v", ".aac",
}


def _doc_to_out(doc: dict) -> TranscriptionOut:
    analysis = doc.get("analysis")
    return TranscriptionOut(
        id=str(doc["_id"]),
        filename=doc.get("filename", ""),
        duration=doc.get("duration"),
        text=doc.get("text", ""),
        analysis=AnalysisResult(**analysis) if analysis else None,
        status=doc.get("status", "done"),
        created_at=doc.get("created_at"),
        error=doc.get("error"),
    )


@router.post("", response_model=TranscriptionOut, status_code=status.HTTP_201_CREATED)
async def create_transcription(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
) -> TranscriptionOut:
    ext = os.path.splitext(file.filename or "")[1].lower()
    ctype = (file.content_type or "").lower()
    type_ok = ctype in ALLOWED_TYPES or ctype.startswith("audio/") or ctype.startswith("video/")
    ext_ok = ext in ALLOWED_EXTENSIONS
    # Accept if either the MIME type OR the extension looks valid.
    # Browsers sometimes send "application/octet-stream" or omit the type entirely.
    if not type_ok and not ext_ok:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type or ext or 'unknown'}",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 25MB)")

    doc = {
        "user_id": user["_id"],
        "filename": file.filename or "audio",
        "size": len(contents),
        "status": "processing",
        "created_at": datetime.now(timezone.utc),
    }
    result = await transcriptions.insert_one(doc)
    tid = result.inserted_id

    try:
        text = await transcribe_audio(contents, file.filename or "audio.mp3")
        analysis = await analyze_transcript(text)
        update = {
            "text": text,
            "analysis": analysis.model_dump(),
            "status": "done",
        }
    except Exception as exc:
        update = {"status": "failed", "error": str(exc)[:500]}
        await transcriptions.update_one({"_id": tid}, {"$set": update})
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}")

    await transcriptions.update_one({"_id": tid}, {"$set": update})
    fresh = await transcriptions.find_one({"_id": tid})
    return _doc_to_out(fresh)


@router.get("", response_model=List[TranscriptionOut])
async def list_transcriptions(user=Depends(get_current_user)) -> List[TranscriptionOut]:
    cursor = transcriptions.find({"user_id": user["_id"]}).sort("created_at", -1).limit(100)
    return [_doc_to_out(doc) async for doc in cursor]


@router.get("/{tid}", response_model=TranscriptionOut)
async def get_transcription(tid: str, user=Depends(get_current_user)) -> TranscriptionOut:
    try:
        oid = ObjectId(tid)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    doc = await transcriptions.find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return _doc_to_out(doc)


@router.delete("/{tid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transcription(tid: str, user=Depends(get_current_user)) -> None:
    try:
        oid = ObjectId(tid)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    result = await transcriptions.delete_one({"_id": oid, "user_id": user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
