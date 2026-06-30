"""Слой работы с OpenAI: транскрипция, оценка звонка/чата, агрегатный анализ лида.

Структура оценки берётся из `scoring_card.py` — этот файл только строит промпт,
вызывает модель и нормализует ответ в pydantic-модель `Scoring`.
"""

import asyncio
import json
from io import BytesIO
from typing import Optional

from openai import AsyncOpenAI

from . import scoring_card as sc
from .config import settings
from .models import (
    CoachingTask,
    CriterionScore,
    Scoring,
    ScoringMeta,
    StopFactor,
)

_client: Optional[AsyncOpenAI] = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


# ═══════════════════════════════════════════════════════════════════════════
# Транскрипция
# ═══════════════════════════════════════════════════════════════════════════

TRANSCRIPTION_PROMPT = (
    "Аудио на русском или казахском языке (возможно смешанное). "
    "Аудио орыс немесе қазақ тілінде болуы мүмкін (аралас болуы мүмкін). "
    "Сделай точную транскрипцию на языке оригинала: не переводи, не сокращай, "
    "не добавляй пояснений, сохраняй имена и термины. "
    "Бастапқы тілінде дәл транскрипция жаса: аударма жасама, қысқартпа, "
    "түсініктеме қоспа, есімдер мен терминдерді сақта. "
    "Возможные имена и термины: Swiss Collection, RAAF Group, ЖК, ипотека, "
    "апартаменты, бронь, рассрочка, менеджер, клиент, договор, объект. "
    "Ықтимал сөздер: пәтер, үй, баға, бронь, ипотека, келісім, менеджер, клиент."
)


async def convert_mpeg_bytes_to_ogg(value: bytes) -> bytes:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", "pipe:0", "-f", "ogg", "-c:a", "libopus", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(input=value)
    if process.returncode != 0:
        raise RuntimeError(stderr.decode())
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
        prompt=TRANSCRIPTION_PROMPT,
    )
    if isinstance(result, str):
        return result
    return getattr(result, "text", "") or ""


# ═══════════════════════════════════════════════════════════════════════════
# Утилиты парсинга
# ═══════════════════════════════════════════════════════════════════════════

def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _str_list(value, limit: int = 10) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def _parse_scoring(data: dict, *, summary_hint: str = "") -> Scoring:
    """Нормализует JSON-ответ модели в `Scoring`.

    Гарантирует, что:
    • присутствуют ВСЕ критерии и стоп-факторы из карты (даже если LLM что-то пропустил)
    • score ∈ [0..max] и penalty неотрицательный
    • raw / normalized_score / grade пересчитаны по карте
    """
    criteria_raw = data.get("criteria_scores") or []
    stop_raw = data.get("stop_factors") or []
    tasks_raw = data.get("coaching_tasks") or []
    meta_raw = data.get("meta") or {}

    # ── криитерии ─────────────────────────────────────────────────────────
    by_id: dict[str, dict] = {}
    for c in criteria_raw:
        if isinstance(c, dict):
            cid = str(c.get("id") or c.get("criterion_id") or "").strip()
            if cid:
                by_id[cid] = c

    criteria: list[CriterionScore] = []
    for cat, c in sc.all_criteria():
        raw = by_id.get(c.id) or {}
        score = _clamp(_to_int(raw.get("score")), 0, c.max_score)
        comment = str(raw.get("comment") or
                      ("не наблюдалось" if c.id not in by_id else "")).strip()
        criteria.append(CriterionScore(
            id=c.id,
            name=c.name,
            category_id=cat.id,
            category_name=cat.name,
            score=score,
            max_score=c.max_score,
            comment=comment,
        ))

    # ── стоп-факторы ───────────────────────────────────────────────────────
    stop_by_id: dict[str, dict] = {}
    for s in stop_raw:
        if isinstance(s, dict):
            fid = str(s.get("id") or s.get("factor_id") or "").strip()
            if fid:
                stop_by_id[fid] = s

    stop_factors: list[StopFactor] = []
    for sf in sc.STOP_FACTORS:
        raw = stop_by_id.get(sf.id) or {}
        triggered = bool(raw.get("triggered"))
        stop_factors.append(StopFactor(
            id=sf.id,
            name=sf.name,
            penalty=sf.penalty,
            triggered=triggered,
            comment=str(raw.get("comment") or "").strip(),
        ))

    # ── coaching tasks ────────────────────────────────────────────────────
    tasks: list[CoachingTask] = []
    for t in tasks_raw:
        if not isinstance(t, dict):
            continue
        tasks.append(CoachingTask(
            title=str(t.get("title", "")).strip(),
            focus_area=str(t.get("focus_area", "")).strip(),
            action_item=str(t.get("action_item", "")).strip(),
        ))

    # ── итоговый балл ─────────────────────────────────────────────────────
    earned = sum(c.score for c in criteria)
    penalty = sum(sf.penalty for sf in stop_factors if sf.triggered)
    raw_score = earned - penalty
    normalized = sc.normalize_to_100(raw_score)
    grade = sc.grade_for(normalized)

    return Scoring(
        meta=ScoringMeta(
            verdict=str(meta_raw.get("verdict") or meta_raw.get("system_verdict", "")).strip(),
            raw_score=raw_score,
            max_raw_score=sc.max_raw_score(),
            normalized_score=normalized,
            grade=grade,
        ),
        strengths=_str_list(data.get("strengths"), 10),
        weaknesses=_str_list(data.get("weaknesses"), 10),
        criteria_scores=criteria,
        stop_factors=stop_factors,
        coaching_tasks=tasks[:10],
        sentiment=str(data.get("sentiment", "")).strip().lower(),
        topics=_str_list(data.get("topics"), 10),
        summary=str(data.get("summary") or summary_hint or "").strip(),
    )


def empty_scoring(reason: str) -> Scoring:
    """Заглушка: пустая карта с verdict-причиной (для случаев без текста)."""
    sc_obj = _parse_scoring({})
    sc_obj.meta.verdict = reason
    return sc_obj


# ═══════════════════════════════════════════════════════════════════════════
# Промпт для оценки одного звонка / чата
# ═══════════════════════════════════════════════════════════════════════════

def _build_unit_prompt() -> str:
    intro = (
        "Ты — AI-аудитор продаж для проекта Swiss Collection by RAAF Group.\n"
        "Проведи аудит коммуникации менеджера (звонок или чат) строго по карте оценки.\n"
        "\n"
    )
    schema = "\n".join([
        "",
        "ВЫХОД (строго JSON, без markdown):",
        "{",
        '  "meta": {"verdict": str},                       // 1–2 предложения, общее суждение',
        '  "summary": str,                                  // 2–4 предложения о звонке',
        '  "sentiment": "positive"|"neutral"|"negative"|"mixed",',
        '  "topics": [str],                                 // 3–7 кратких тем',
        '  "strengths": [str],                              // что сделано хорошо',
        '  "weaknesses": [str],                             // что упущено',
        '  "criteria_scores": [{"id": str, "score": int, "comment": str}],',
        '  "stop_factors": [{"id": str, "triggered": bool, "comment": str}],',
        '  "coaching_tasks": [{"title": str, "focus_area": str, "action_item": str}]',
        "}",
        "ВАЖНО: id критериев и стоп-факторов — строго из карты выше. "
        "Все 17 критериев и 4 стоп-фактора должны присутствовать в массивах. "
        "score в каждом критерии — целое 0..max этого критерия. "
        "Тексты — на русском.",
    ])
    return intro + sc.render_rubric_for_prompt() + schema


UNIT_PROMPT = _build_unit_prompt()


async def analyze_unit(text: str, source: str = "call") -> Scoring:
    """Оценка одной коммуникации (звонка или чата) по карте."""
    safe_text = (text or "").strip()
    if not safe_text:
        return empty_scoring("Пустой транскрипт.")

    client = get_client()
    user_block = (
        f"ИСТОЧНИК: {source}\n"
        f"ТРАНСКРИПТ:\n---\n{safe_text[:20000]}\n---"
    )
    response = await client.chat.completions.create(
        model=settings.openai_analysis_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": UNIT_PROMPT},
            {"role": "user", "content": user_block},
        ],
    )
    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {}
    return _parse_scoring(data)


# ═══════════════════════════════════════════════════════════════════════════
# Промпт для агрегатной оценки лида
# ═══════════════════════════════════════════════════════════════════════════

def _build_lead_prompt() -> str:
    intro = (
        "Ты — старший AI-аудитор отдела продаж недвижимости (Swiss Collection by RAAF Group).\n"
        "Тебе дают сводку по одному ЛИДУ: метаданные сделки, оценки и выжимки\n"
        "по каждому звонку, и комментарии менеджеров из таймлайна CRM.\n"
        "\n"
        "Задача — оценить работу менеджера с лидом ЦЕЛИКОМ по той же карте,\n"
        "что применяется к отдельному звонку. Оценивай так, словно это один длинный\n"
        "мета-звонок — серия касаний с клиентом.\n"
        "Если критерий не наблюдался ни в одном звонке/комментарии — score=0,\n"
        "comment=«не наблюдалось». Если был — оценивай по лучшему/худшему проявлению.\n"
        "\n"
    )
    schema = "\n".join([
        "",
        "ВЫХОД (строго JSON, без markdown):",
        "{",
        '  "meta":     {"verdict": str},',
        '  "summary":  str,                  // 3–6 предложений: история лида',
        '  "client_request": str,            // что хочет клиент',
        '  "objections":     [str],',
        '  "strengths":      [str],          // плюсы менеджера по совокупности',
        '  "weaknesses":     [str],          // минусы менеджера',
        '  "risk":           "low"|"medium"|"high",',
        '  "risk_reason":    str,',
        '  "next_step":      str,            // конкретное действие',
        '  "sentiment":      "positive"|"neutral"|"negative"|"mixed",',
        '  "topics":         [str],',
        '  "criteria_scores": [{"id": str, "score": int, "comment": str}],',
        '  "stop_factors":    [{"id": str, "triggered": bool, "comment": str}],',
        '  "coaching_tasks":  [{"title": str, "focus_area": str, "action_item": str}]',
        "}",
        "ВАЖНО: все 17 критериев и 4 стоп-фактора обязательны в массивах. "
        "id — строго из карты. Тексты — на русском.",
    ])
    return intro + sc.render_rubric_for_prompt() + schema


LEAD_PROMPT = _build_lead_prompt()


async def analyze_lead_aggregate(reduce_input: str) -> tuple[Scoring, dict]:
    """Reduce-фаза по лиду. Возвращает (scoring, lead_qualitative),
    где lead_qualitative содержит client_request / objections / risk / next_step.
    """
    safe = (reduce_input or "").strip()
    if not safe:
        sc_empty = empty_scoring("По лиду нет данных для анализа.")
        return sc_empty, {
            "client_request": "",
            "objections": [],
            "risk": "low",
            "risk_reason": "Недостаточно данных.",
            "next_step": "Связаться с клиентом и собрать первичную информацию.",
            "summary": "По лиду нет данных для анализа.",
        }

    client = get_client()
    response = await client.chat.completions.create(
        model=settings.openai_analysis_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": LEAD_PROMPT},
            {"role": "user", "content": safe[:30000]},
        ],
    )
    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {}

    scoring = _parse_scoring(data)

    risk_raw = str(data.get("risk", "low")).strip().lower()
    risk = risk_raw if risk_raw in ("low", "medium", "high") else "low"

    qualitative = {
        "client_request": str(data.get("client_request", "")).strip(),
        "objections": _str_list(data.get("objections"), 10),
        "risk": risk,
        "risk_reason": str(data.get("risk_reason", "")).strip(),
        "next_step": str(data.get("next_step", "")).strip(),
        "summary": str(data.get("summary", "")).strip(),
    }
    return scoring, qualitative
