import asyncio
import json
from io import BytesIO
from typing import Optional

from openai import AsyncOpenAI

from .config import settings
from .models import AnalysisResult

_client: Optional[AsyncOpenAI] = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def convert_mpeg_bytes_to_ogg(value: bytes) -> bytes:
    process = await asyncio.create_subprocess_exec(
        'ffmpeg',
        '-i', 'pipe:0',
        '-f', 'ogg',
        '-c:a', 'libopus',
        'pipe:1',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate(input=value)

    if process.returncode != 0:
        raise Exception(stderr.decode())

    return stdout


async def transcribe_audio(file_bytes: bytes, filename: str) -> str:
    client = get_client()
    ogg_bytes = await convert_mpeg_bytes_to_ogg(file_bytes)
    buf = BytesIO(ogg_bytes)
    buf.name = "audio.ogg"
    result = await client.audio.transcriptions.create(
        model=settings.openai_transcribe_model,
        file=buf,
        response_format="text",
    )
    if isinstance(result, str):
        return result
    return getattr(result, "text", "") or ""


ANALYSIS_PROMPT = (
    "You are an assistant that analyzes audio transcripts. "
    "Given a transcript, produce a strict JSON object with the keys: "
    "summary (2-4 sentence overview), "
    "topics (array of 3-7 short topic strings), "
    "sentiment (one of: positive, neutral, negative, mixed), "
    "action_items (array of concrete action items, empty if none), "
    "language (ISO 639-1 code of the transcript). "
    "Reply ONLY with JSON, no markdown."
)


async def analyze_transcript(text: str) -> AnalysisResult:
    if not text.strip():
        return AnalysisResult(summary="", topics=[], sentiment="neutral", action_items=[], language="")

    client = get_client()
    response = await client.chat.completions.create(
        model=settings.openai_analysis_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": ANALYSIS_PROMPT},
            {"role": "user", "content": text[:15000]},
        ],
    )
    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {}

    return AnalysisResult(
        summary=str(data.get("summary", "")).strip(),
        topics=[str(t) for t in (data.get("topics") or [])][:10],
        sentiment=str(data.get("sentiment", "neutral")).strip().lower(),
        action_items=[str(a) for a in (data.get("action_items") or [])][:20],
        language=str(data.get("language", "")).strip().lower(),
    )
