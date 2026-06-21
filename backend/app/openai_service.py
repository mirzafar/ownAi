import asyncio
import json
from io import BytesIO
from typing import Optional

from openai import AsyncOpenAI

from .config import settings
from .models import (
    AnalysisResult,
    CoachingTask,
    CriterionScore,
    SalesAnalysis,
    SalesAnalysisBlock,
    SalesAnalysisMeta,
)

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


SALES_ANALYSIS_PROMPT = (
    "You are the core AI Intelligence Engine of \"OKO Systems\" — an advanced "
    "conversational analytics and sales quality control platform. Твоя задача — "
    "провести глубокий аудит коммуникации между менеджером и клиентом.\n\n"
    "КРИТЕРИИ ОЦЕНКИ (шкала 0–100):\n"
    "1. greeting — Приветствие и установление контакта\n"
    "2. needs_discovery — Выявление потребности клиента\n"
    "3. presentation — Презентация продукта / объекта\n"
    "4. objections — Работа с возражениями (если возражений не было — score=100, в комментарии «возражений не возникло»)\n"
    "5. whatsapp_quality — Скорость и качество ответов в WhatsApp (для звонков ставь 100 и пометь «не применимо»)\n"
    "6. next_step — Назначение следующего шага (чёткая дата/время/действие)\n"
    "7. closure — Закрытие коммуникации\n\n"
    "ЛОГИКА ЗАДАЧ: если по критическому критерию (needs_discovery, objections, next_step) "
    "оценка ниже 75 — обязательно добавь конкретную, измеримую задачу в ai_coaching_tasks.\n\n"
    "ОГРАНИЧЕНИЯ:\n"
    "- Верни ТОЛЬКО валидный JSON-объект, без markdown-обёрток.\n"
    "- Все тексты (вердикт, комментарии, задачи) — на русском языке.\n"
    "- Структура JSON:\n"
    "{\n"
    "  \"meta\": {\"system_verdict\": str, \"total_score\": int},\n"
    "  \"analysis\": {\"strengths\": [str], \"weaknesses\": [str]},\n"
    "  \"criteria_scores\": [{\"criterion_id\": str, \"criterion_name\": str, \"score\": int, \"comment\": str}],\n"
    "  \"ai_coaching_tasks\": [{\"title\": str, \"focus_area\": str, \"action_item\": str}]\n"
    "}\n"
)

_CRITERIA_NAMES = {
    "greeting": "Приветствие и установление контакта",
    "needs_discovery": "Выявление потребности клиента",
    "presentation": "Презентация продукта / объекта",
    "objections": "Работа с возражениями",
    "whatsapp_quality": "Скорость и качество ответов в WhatsApp",
    "next_step": "Назначение следующего шага",
    "closure": "Закрытие коммуникации",
}


def _clamp_score(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, n))


async def analyze_sales_call(text: str, source: str = "call") -> SalesAnalysis:
    safe_text = (text or "").strip()
    if not safe_text:
        return SalesAnalysis(
            meta=SalesAnalysisMeta(system_verdict="Транскрипт пуст.", total_score=0),
            analysis=SalesAnalysisBlock(),
            criteria_scores=[],
            ai_coaching_tasks=[],
        )

    client = get_client()
    user_block = (
        f"ИСТОЧНИК: {source}\n"
        f"ТРАНСКРИПТ КОММУНИКАЦИИ:\n---\n{safe_text[:20000]}\n---"
    )
    response = await client.chat.completions.create(
        model=settings.openai_analysis_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SALES_ANALYSIS_PROMPT},
            {"role": "user", "content": user_block},
        ],
    )
    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {}

    meta_raw = data.get("meta") or {}
    analysis_raw = data.get("analysis") or {}
    criteria_raw = data.get("criteria_scores") or []
    tasks_raw = data.get("ai_coaching_tasks") or []

    criteria: list[CriterionScore] = []
    for c in criteria_raw:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("criterion_id", "")).strip() or "unknown"
        criteria.append(
            CriterionScore(
                criterion_id=cid,
                criterion_name=str(c.get("criterion_name") or _CRITERIA_NAMES.get(cid, cid)).strip(),
                score=_clamp_score(c.get("score")),
                comment=str(c.get("comment", "")).strip(),
            )
        )

    tasks: list[CoachingTask] = []
    for t in tasks_raw:
        if not isinstance(t, dict):
            continue
        tasks.append(
            CoachingTask(
                title=str(t.get("title", "")).strip(),
                focus_area=str(t.get("focus_area", "")).strip(),
                action_item=str(t.get("action_item", "")).strip(),
            )
        )

    total = meta_raw.get("total_score")
    if not isinstance(total, (int, float)):
        applicable = [c.score for c in criteria if c.criterion_id != "whatsapp_quality" or source != "call"]
        total = round(sum(applicable) / len(applicable)) if applicable else 0

    return SalesAnalysis(
        meta=SalesAnalysisMeta(
            system_verdict=str(meta_raw.get("system_verdict", "")).strip(),
            total_score=_clamp_score(total),
        ),
        analysis=SalesAnalysisBlock(
            strengths=[str(s).strip() for s in (analysis_raw.get("strengths") or []) if str(s).strip()][:10],
            weaknesses=[str(s).strip() for s in (analysis_raw.get("weaknesses") or []) if str(s).strip()][:10],
        ),
        criteria_scores=criteria,
        ai_coaching_tasks=tasks[:10],
    )
