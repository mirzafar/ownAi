import os
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from ..auth import get_current_user
from ..database import audio_bucket, transcriptions
from ..models import AnalysisResult, SalesAnalysis, TranscriptionOut
from ..openai_service import analyze_sales_call, analyze_transcript, transcribe_audio

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
    sales = doc.get("sales_analysis")
    return TranscriptionOut(
        id=str(doc["_id"]),
        filename=doc.get("filename", ""),
        duration=doc.get("duration"),
        text=doc.get("text", ""),
        analysis=AnalysisResult(**analysis) if analysis else None,
        sales_analysis=SalesAnalysis(**sales) if sales else None,
        source=doc.get("source"),
        bitrix_call_id=doc.get("bitrix_call_id"),
        bitrix_chat_id=doc.get("bitrix_chat_id"),
        bitrix_manager=doc.get("bitrix_manager", "") or "",
        bitrix_manager_id=doc.get("bitrix_manager_id", "") or "",
        bitrix_phone=doc.get("bitrix_phone", "") or "",
        bitrix_direction=doc.get("bitrix_direction", "") or "",
        bitrix_channel=doc.get("bitrix_channel", "") or "",
        bitrix_client=doc.get("bitrix_client", "") or "",
        bitrix_call_date=doc.get("bitrix_call_date"),
        messages_count=int(doc.get("messages_count") or 0),
        has_audio=bool(doc.get("audio_file_id")),
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
    doc = await transcriptions.find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if doc.get("audio_file_id"):
        try:
            await audio_bucket.delete(doc["audio_file_id"])
        except Exception:
            pass
    await transcriptions.delete_one({"_id": oid, "user_id": user["_id"]})


async def _load_audio_bytes(file_id) -> bytes:
    stream = await audio_bucket.open_download_stream(file_id)
    try:
        chunks: list[bytes] = []
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        close = getattr(stream, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result


async def _run_analysis(text: str, source: Optional[str]) -> dict:
    """Запускает подходящий анализ и возвращает поля для $set."""
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст для анализа пуст")
    if source == "bitrix_call":
        sales = await analyze_sales_call(text, source="call")
        return {"sales_analysis": sales.model_dump(), "analysis": None}
    if source == "bitrix_chat":
        sales = await analyze_sales_call(text, source="chat")
        return {"sales_analysis": sales.model_dump(), "analysis": None}
    analysis = await analyze_transcript(text)
    return {"analysis": analysis.model_dump(), "sales_analysis": None}


@router.post("/{tid}/reanalyze", response_model=TranscriptionOut)
async def reanalyze(tid: str, user=Depends(get_current_user)) -> TranscriptionOut:
    try:
        oid = ObjectId(tid)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    doc = await transcriptions.find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if not (doc.get("text") or "").strip():
        raise HTTPException(status_code=400, detail="Нет текста — сначала транскрибируйте")

    await transcriptions.update_one({"_id": oid}, {"$set": {"status": "processing", "error": None}})
    try:
        update = await _run_analysis(doc.get("text", ""), doc.get("source"))
        update["status"] = "done"
        update["error"] = None
    except HTTPException:
        await transcriptions.update_one({"_id": oid}, {"$set": {"status": "failed"}})
        raise
    except Exception as exc:
        await transcriptions.update_one(
            {"_id": oid}, {"$set": {"status": "failed", "error": str(exc)[:500]}}
        )
        raise HTTPException(status_code=502, detail=f"Анализ не выполнен: {exc}")

    await transcriptions.update_one({"_id": oid}, {"$set": update})
    fresh = await transcriptions.find_one({"_id": oid})
    return _doc_to_out(fresh)


@router.post("/{tid}/retranscribe", response_model=TranscriptionOut)
async def retranscribe(tid: str, user=Depends(get_current_user)) -> TranscriptionOut:
    try:
        oid = ObjectId(tid)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    doc = await transcriptions.find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if not doc.get("audio_file_id"):
        raise HTTPException(status_code=400, detail="Аудио не сохранено — повторная транскрипция невозможна")

    await transcriptions.update_one({"_id": oid}, {"$set": {"status": "processing", "error": None}})
    try:
        audio_bytes = await _load_audio_bytes(doc["audio_file_id"])
        text = await transcribe_audio(audio_bytes, doc.get("filename") or "audio.mp3")
        update = await _run_analysis(text, doc.get("source"))
        update["text"] = text
        update["status"] = "done"
        update["error"] = None
    except HTTPException:
        await transcriptions.update_one({"_id": oid}, {"$set": {"status": "failed"}})
        raise
    except Exception as exc:
        await transcriptions.update_one(
            {"_id": oid}, {"$set": {"status": "failed", "error": str(exc)[:500]}}
        )
        raise HTTPException(status_code=502, detail=f"Транскрипция не выполнена: {exc}")

    await transcriptions.update_one({"_id": oid}, {"$set": update})
    fresh = await transcriptions.find_one({"_id": oid})
    return _doc_to_out(fresh)


@router.get("/{tid}/audio")
async def stream_audio(tid: str, user=Depends(get_current_user)):
    try:
        oid = ObjectId(tid)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    doc = await transcriptions.find_one(
        {"_id": oid, "user_id": user["_id"]},
        {"audio_file_id": 1, "audio_content_type": 1, "filename": 1},
    )
    if not doc or not doc.get("audio_file_id"):
        raise HTTPException(status_code=404, detail="Аудио не сохранено")

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
        headers={"Content-Disposition": f'inline; filename="{doc.get("filename", "audio.mp3")}"'},
    )
