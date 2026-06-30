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
    StopFactor,
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


# Универсальный билингвальный prompt для Whisper.
# Whisper использует prompt как контекст: язык/стиль/частые термины подсказывают, чего ждать.
# Включаем фразы и лексику обоих языков, чтобы модель не «съезжала» в один из них и не переводила.
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


# Оставлено для обратной совместимости: поле language ещё может прилетать из старых клиентов,
# но больше не влияет на транскрипцию — Whisper определяет язык автоматически.
SUPPORTED_TRANSCRIPTION_LANGUAGES = {"ru", "kk", "auto"}


def normalize_language(value: Optional[str]) -> str:
    return "auto"


async def transcribe_audio(file_bytes: bytes, filename: str, language: Optional[str] = None) -> str:
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


_CATEGORIES = {
    "opening": "Открытие звонка",
    "qualification": "Квалификация",
    "presentation": "Презентация объекта",
    "objections": "Работа с возражениями",
    "closing": "Закрытие и следующий шаг",
}

# (criterion_id, criterion_name, category_id, max_score)
_RUBRIC: list[tuple[str, str, str, int]] = [
    ("greeting", "Приветствие и позиционирование", "opening", 5),
    ("contact", "Установление контакта", "opening", 5),
    ("call_purpose", "Цель звонка", "opening", 5),
    ("budget", "Бюджет и формат покупки", "qualification", 10),
    ("purchase_goal", "Цель покупки", "qualification", 10),
    ("decision_timeline", "Сроки принятия решения", "qualification", 10),
    ("decision_maker", "ЛПР (лицо, принимающее решение)", "qualification", 10),
    ("property_params", "Площадь и параметры объекта", "qualification", 10),
    ("qualification_summary", "Резюмирование квалификации", "qualification", 10),
    ("relevance", "Соответствие запросу клиента", "presentation", 10),
    ("premium_language", "Премиальный язык", "presentation", 10),
    ("competitive_edge", "Конкурентные преимущества", "presentation", 5),
    ("financial_argumentation", "Финансовая аргументация", "presentation", 5),
    ("objection_reaction", "Реакция на возражение", "objections", 5),
    ("objection_arguments", "Аргументация возражений", "objections", 5),
    ("objection_closure", "Закрытие возражения", "objections", 5),
    ("close_attempt", "Попытка закрытия на встречу / бронь", "closing", 10),
    ("commitment_fix", "Договорённость зафиксирована", "closing", 5),
    ("call_ending", "Завершение звонка", "closing", 5),
]

# (factor_id, name, penalty)
_STOP_FACTORS: list[tuple[str, str, int]] = [
    ("filler_words", "Слова-паразиты и непрофессионализм", 5),
    ("unauthorized_discount", "Торговля скидкой без согласования с РОПом", 10),
    ("loss_of_control", "Потеря контроля над диалогом", 5),
    ("no_next_step", "Звонок завершён без следующего шага", 15),
]

# Критические подкритерии — если score < половины max_score, добавляем задачу.
_CRITICAL_CRITERIA = {"decision_timeline", "qualification_summary", "close_attempt"}


def _grade_for(score: int) -> str:
    if score >= 90:
        return "Эталонный"
    if score >= 75:
        return "Хороший"
    if score >= 60:
        return "Удовлетворительно"
    return "Неудовлетворительно"


def _rubric_section() -> str:
    """Описание 19 критериев и 4 стоп-факторов — переиспользуется в per-call и lead-level промптах."""
    lines: list[str] = [
        "КРИТЕРИИ (по каждому начисли целое число от 0 до max баллов):",
        "",
    ]
    cur_category: Optional[str] = None
    cat_index = 0
    for cid, name, cat_id, max_score in _RUBRIC:
        if cat_id != cur_category:
            cat_index += 1
            cur_category = cat_id
            lines.append(f"{cat_index}. {_CATEGORIES[cat_id].upper()}")
        lines.append(f"   - {cid} [max {max_score}] {name}")
    lines += [
        "",
        "СТОП-ФАКТОРЫ (если триггерится — penalty вычитается из total_score; если нет — triggered=false, penalty не вычитается):",
    ]
    for fid, name, penalty in _STOP_FACTORS:
        lines.append(f"   - {fid} [-{penalty}] {name}")
    lines += [
        "",
        "ШКАЛА ОЦЕНКИ (для поля grade):",
        "   - «Эталонный» — 90–100",
        "   - «Хороший» — 75–89",
        "   - «Удовлетворительно» — 60–74",
        "   - «Неудовлетворительно» — менее 60",
        "",
        "ЛОГИКА ЗАДАЧ: для критических критериев (decision_timeline, qualification_summary, close_attempt) "
        "при оценке ниже половины max — обязательно добавь конкретную задачу в ai_coaching_tasks.",
    ]
    return "\n".join(lines)


def _build_sales_prompt() -> str:
    intro = "\n".join([
        "Ты — AI-аудитор продаж для проекта Swiss Collection by RAAF Group.",
        "Проведи аудит телефонного звонка менеджера по продажам недвижимости",
        "строго по приведённой ниже карте оценки (19 критериев + 4 стоп-фактора).",
        "",
    ])
    schema = "\n".join([
        "",
        "ОГРАНИЧЕНИЯ:",
        "- Верни ТОЛЬКО валидный JSON-объект (без markdown).",
        "- Все тексты — на русском языке.",
        "- В criteria_scores верни ВСЕ 19 критериев в указанном порядке, без пропусков.",
        "- Если критерий не наблюдался в звонке — score=0 и в comment: «не наблюдалось».",
        "- В stop_factors верни ВСЕ 4 стоп-фактора. Для не сработавших — triggered=false с пустым comment.",
        "- total_score = sum(score) − sum(penalty по triggered=true стоп-факторам), затем clamp 0..100.",
        "- Структура JSON:",
        "{",
        '  "meta": {"system_verdict": str, "total_score": int, "grade": str},',
        '  "analysis": {"strengths": [str], "weaknesses": [str]},',
        '  "criteria_scores": [{"criterion_id": str, "criterion_name": str, "category_id": str, "category_name": str, "score": int, "max_score": int, "comment": str}],',
        '  "stop_factors": [{"factor_id": str, "name": str, "penalty": int, "triggered": bool, "comment": str}],',
        '  "ai_coaching_tasks": [{"title": str, "focus_area": str, "action_item": str}]',
        "}",
    ])
    return intro + _rubric_section() + schema


SALES_ANALYSIS_PROMPT = _build_sales_prompt()

_RUBRIC_INDEX = {cid: (name, cat_id, max_score) for cid, name, cat_id, max_score in _RUBRIC}
_STOP_INDEX = {fid: (name, penalty) for fid, name, penalty in _STOP_FACTORS}


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _parse_sales_analysis(data: dict) -> SalesAnalysis:
    """Нормализует JSON-ответ модели в SalesAnalysis с заполненными 19 критериями и 4 стоп-факторами."""
    meta_raw = data.get("meta") or {}
    analysis_raw = data.get("analysis") or {}
    criteria_raw = data.get("criteria_scores") or []
    stop_raw = data.get("stop_factors") or []
    tasks_raw = data.get("ai_coaching_tasks") or []

    by_id: dict[str, dict] = {}
    for c in criteria_raw:
        if isinstance(c, dict):
            cid = str(c.get("criterion_id", "")).strip()
            if cid:
                by_id[cid] = c

    criteria: list[CriterionScore] = []
    for cid, name, cat_id, max_score in _RUBRIC:
        raw = by_id.get(cid) or {}
        score = _clamp(_to_int(raw.get("score")), 0, max_score)
        comment = str(raw.get("comment") or ("не наблюдалось" if cid not in by_id else "")).strip()
        criteria.append(
            CriterionScore(
                criterion_id=cid,
                criterion_name=str(raw.get("criterion_name") or name).strip(),
                category_id=cat_id,
                category_name=_CATEGORIES.get(cat_id, ""),
                score=score,
                max_score=max_score,
                comment=comment,
            )
        )

    stop_by_id: dict[str, dict] = {}
    for s in stop_raw:
        if isinstance(s, dict):
            fid = str(s.get("factor_id", "")).strip()
            if fid:
                stop_by_id[fid] = s

    stop_factors: list[StopFactor] = []
    for fid, name, penalty in _STOP_FACTORS:
        raw = stop_by_id.get(fid) or {}
        triggered = bool(raw.get("triggered"))
        stop_factors.append(
            StopFactor(
                factor_id=fid,
                name=str(raw.get("name") or name).strip(),
                penalty=penalty,
                triggered=triggered,
                comment=str(raw.get("comment") or "").strip(),
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

    earned = sum(c.score for c in criteria)
    penalty = sum(sf.penalty for sf in stop_factors if sf.triggered)
    total_score = _clamp(earned - penalty, 0, 100)
    grade = _grade_for(total_score)

    return SalesAnalysis(
        meta=SalesAnalysisMeta(
            system_verdict=str(meta_raw.get("system_verdict", "")).strip(),
            total_score=total_score,
            grade=grade,
        ),
        analysis=SalesAnalysisBlock(
            strengths=[str(s).strip() for s in (analysis_raw.get("strengths") or []) if str(s).strip()][:10],
            weaknesses=[str(s).strip() for s in (analysis_raw.get("weaknesses") or []) if str(s).strip()][:10],
        ),
        criteria_scores=criteria,
        stop_factors=stop_factors,
        ai_coaching_tasks=tasks[:10],
    )


def _empty_sales_analysis(verdict: str) -> SalesAnalysis:
    return _parse_sales_analysis({"meta": {"system_verdict": verdict}})


async def analyze_sales_call(text: str, source: str = "call") -> SalesAnalysis:
    safe_text = (text or "").strip()
    if not safe_text:
        return _empty_sales_analysis("Транскрипт пуст.")

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

    return _parse_sales_analysis(data)


# ============================================================================
# Lead-level аналитика (reduce-фаза map-reduce)
# ============================================================================

def _build_lead_overall_prompt() -> str:
    intro = "\n".join([
        "Ты — старший AI-аудитор отдела продаж недвижимости (Swiss Collection by RAAF Group).",
        "Тебе дают сводку по одному ЛИДУ: метаданные сделки, краткие выжимки и оценки по каждому звонку",
        "(результат предыдущего аудита) и комментарии менеджеров из таймлайна CRM.",
        "",
        "Твоя задача — провести АУДИТ РАБОТЫ МЕНЕДЖЕРА С ЛИДОМ В ЦЕЛОМ по той же карте оценки,",
        "что применяется к отдельному звонку (19 критериев + 4 стоп-фактора), агрегируя поведение",
        "менеджера по всем звонкам и комментариям. Дополнительно дай качественную сводку по лиду.",
        "",
        "Оценивай так, будто перед тобой один длинный 'мета-звонок' — серия касаний с клиентом.",
        "Если какой-то критерий не наблюдался НИ В ОДНОМ звонке/комментарии — score=0 и comment=«не наблюдалось».",
        "Если критерий проявился хотя бы раз — оценивай по лучшему/худшему проявлению с учётом контекста (см. comment).",
        "",
    ])
    schema = "\n".join([
        "",
        "ОГРАНИЧЕНИЯ И СТРУКТУРА ОТВЕТА:",
        "- Верни ТОЛЬКО валидный JSON-объект (без markdown). Все тексты — на русском.",
        "- В criteria_scores верни ВСЕ 19 критериев в указанном порядке.",
        "- В stop_factors верни ВСЕ 4 стоп-фактора. Triggered=true только при явном подтверждении из выжимок звонков.",
        "- total_score = sum(score) − sum(penalty по triggered=true), затем clamp 0..100.",
        "- В next_step — конкретное действие (кому позвонить, что отправить, до какой даты).",
        "- risk=high при долгом молчании / без следующего шага / явных негативных сигналах;",
        "  medium при возражениях без блокировки; low при тёплом контакте и понятной траектории.",
        "- Не дублируй пункты в objections / manager_pros / manager_cons.",
        "",
        "Структура JSON:",
        "{",
        '  "summary": str,                  // 3–6 предложений: история лида, текущее положение',
        '  "client_request": str,           // что хочет клиент (объект, бюджет, сроки, мотивация)',
        '  "objections": [str],             // ключевые возражения/блокеры (3–7 пунктов)',
        '  "manager_pros": [str],           // что менеджер делает хорошо по совокупности касаний',
        '  "manager_cons": [str],           // что менеджер упускает / делает плохо',
        '  "risk": "low" | "medium" | "high",',
        '  "risk_reason": str,              // 1–2 предложения',
        '  "next_step": str,                // конкретный следующий шаг для менеджера',
        '  "meta": {"system_verdict": str, "total_score": int, "grade": str},',
        '  "analysis": {"strengths": [str], "weaknesses": [str]},',
        '  "criteria_scores": [{"criterion_id": str, "criterion_name": str, "category_id": str, "category_name": str, "score": int, "max_score": int, "comment": str}],',
        '  "stop_factors": [{"factor_id": str, "name": str, "penalty": int, "triggered": bool, "comment": str}],',
        '  "ai_coaching_tasks": [{"title": str, "focus_area": str, "action_item": str}]',
        "}",
    ])
    return intro + _rubric_section() + schema


LEAD_OVERALL_PROMPT = _build_lead_overall_prompt()


def _str_list(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def _empty_lead_overall(reason: str) -> dict:
    sa = _empty_sales_analysis(reason)
    return {
        "summary": reason,
        "client_request": "",
        "objections": [],
        "manager_pros": [],
        "manager_cons": [],
        "risk": "low",
        "risk_reason": "Недостаточно данных.",
        "next_step": "Связаться с клиентом и собрать первичную информацию.",
        "sales_analysis": sa.model_dump(),
    }


async def analyze_lead_overall(reduce_input: str) -> dict:
    """Reduce-фаза: на вход — текст со сводкой по лиду (мета + per-call summary + комменты).
    Возвращает dict с качественной сводкой + полной rubric-картой (через _parse_sales_analysis).
    """
    safe_text = (reduce_input or "").strip()
    if not safe_text:
        return _empty_lead_overall("По лиду нет данных для анализа.")

    client = get_client()
    response = await client.chat.completions.create(
        model=settings.openai_analysis_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": LEAD_OVERALL_PROMPT},
            {"role": "user", "content": safe_text[:30000]},
        ],
    )
    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {}

    risk_raw = str(data.get("risk", "low")).strip().lower()
    risk = risk_raw if risk_raw in ("low", "medium", "high") else "low"

    sales = _parse_sales_analysis(data)

    return {
        "summary": str(data.get("summary", "")).strip(),
        "client_request": str(data.get("client_request", "")).strip(),
        "objections": _str_list(data.get("objections"), 10),
        "manager_pros": _str_list(data.get("manager_pros"), 10),
        "manager_cons": _str_list(data.get("manager_cons"), 10),
        "risk": risk,
        "risk_reason": str(data.get("risk_reason", "")).strip(),
        "next_step": str(data.get("next_step", "")).strip(),
        "sales_analysis": sales.model_dump(),
    }
