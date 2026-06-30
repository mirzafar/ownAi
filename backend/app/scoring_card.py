"""Swiss Collection by RAAF Group · Карта оценки звонка v1.0.

Этот файл — единственный источник правды для критериев оценки. Любая правка
карты (вес критерия, добавление пункта, переименование) делается ТОЛЬКО здесь.
Промпты для LLM, парсинг ответа, нормализация баллов и отображение шкалы —
всё построено вокруг определений ниже.

Сумма весов положительных критериев = 140, шкала отображения нормирована в /100.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Criterion:
    id: str           # короткий машинный id, используется LLM и при парсинге
    name: str         # человекочитаемое название
    max_score: int    # вес критерия (макс. балл)
    description: str  # что именно проверяем (подсказка LLM)


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    criteria: tuple[Criterion, ...]


@dataclass(frozen=True)
class StopFactorDef:
    id: str
    name: str
    penalty: int
    description: str


CATEGORIES: tuple[Category, ...] = (
    Category(
        id="opening",
        name="Открытие звонка",
        criteria=(
            Criterion("greeting", "Приветствие и позиционирование", 5,
                      "Называет своё имя, проект Swiss Collection by RAAF Group, "
                      "интонация уверенная, без спешки"),
            Criterion("contact", "Установление контакта", 5,
                      "Уточняет имя клиента, использует его в диалоге минимум 2 раза, "
                      "тон тёплый, не сухой"),
            Criterion("call_purpose", "Цель звонка", 5,
                      "Чётко обозначает повод контакта в первые 30 секунд, "
                      "без заигрываний и долгих преамбул"),
        ),
    ),
    Category(
        id="qualification",
        name="Квалификация",
        criteria=(
            Criterion("budget", "Бюджет и формат покупки", 10,
                      "Выясняет диапазон бюджета, формат — ипотека / рассрочка / 100%, "
                      "не задаёт в лоб, а через выгоды"),
            Criterion("purchase_goal", "Цель покупки", 10,
                      "Уточняет: инвестиция, проживание, подарок — без этого невозможно "
                      "правильно презентовать объект"),
            Criterion("decision_timeline", "Сроки принятия решения", 10,
                      "Узнаёт горизонт: сейчас / 1–3 мес / 6+ мес — для расстановки приоритетов воронки"),
            Criterion("decision_maker", "ЛПР (лицо, принимающее решение)", 10,
                      "Выясняет, один ли клиент принимает решение, "
                      "или нужно вовлечение партнёра / семьи"),
            Criterion("property_params", "Площадь и параметры объекта", 10,
                      "Уточняет желаемую площадь, этаж, планировку, вид — для точного подбора лота"),
            Criterion("qualification_summary", "Резюмирование квалификации", 10,
                      "МОП проговаривает вслух: «Правильно ли я понял: вы ищете X кв.м., "
                      "для [цели], бюджет — Y, рассматриваете [срок]?» до перехода к презентации"),
        ),
    ),
    Category(
        id="presentation",
        name="Презентация объекта",
        criteria=(
            Criterion("relevance", "Соответствие запросу клиента", 10,
                      "Презентует только то, что релевантно выявленной потребности — не «всё подряд»"),
            Criterion("premium_language", "Премиальный язык", 10,
                      "Использует язык ценности, избегает слов «дёшево», «скидка», «акция». "
                      "Уместно: «инвестиционная привлекательность», «редкая локация»"),
            Criterion("competitive_edge", "Конкурентные преимущества", 5,
                      "Называет 2–3 чётких преимущества Swiss Collection vs рынок "
                      "(класс, застройщик, локация)"),
            Criterion("financial_argumentation", "Финансовая аргументация", 5,
                      "Умеет объяснить доходность / капитализацию / условия рассрочки "
                      "языком выгоды клиента"),
        ),
    ),
    Category(
        id="objections",
        name="Работа с возражениями",
        criteria=(
            Criterion("objection_reaction", "Реакция на возражение", 5,
                      "Не спорит, не обрывает — фиксирует, переформулирует, "
                      "уточняет суть возражения"),
            Criterion("objection_arguments", "Аргументация", 5,
                      "Отвечает фактами и цифрами, не общими фразами. "
                      "Например: «Стоимость кв.м. в этом блоке выросла на X%»"),
            Criterion("objection_closure", "Закрытие возражения", 5,
                      "После ответа проверяет, остался ли вопрос открытым: "
                      "«Я ответил на ваш вопрос?»"),
        ),
    ),
    Category(
        id="closing",
        name="Закрытие и следующий шаг",
        criteria=(
            Criterion("close_attempt", "Попытка закрытия на встречу / бронь", 10,
                      "Предлагает конкретный следующий шаг: встреча, показ, "
                      "бронирование — не «подумайте»"),
            Criterion("commitment_fix", "Договорённость зафиксирована", 5,
                      "Повторяет договорённость вслух: дата, время, формат, "
                      "действие. Вносит в CRM"),
            Criterion("call_ending", "Завершение звонка", 5,
                      "Чёткое, уважительное завершение без «ну ладно», благодарность за время клиента"),
        ),
    ),
)


STOP_FACTORS: tuple[StopFactorDef, ...] = (
    StopFactorDef("filler_words", "Слова-паразиты и непрофессионализм", 5,
                  "«Ну», «как бы», «в принципе», «вообще», частые паузы, «эмм»"),
    StopFactorDef("unauthorized_discount", "Торговля скидкой без согласования", 10,
                  "Упоминание скидки, акции или снижения цены без подтверждения от РОПа"),
    StopFactorDef("loss_of_control", "Потеря контроля над диалогом", 5,
                  "Клиент ведёт разговор, МОП отвечает на все вопросы без встречной инициативы"),
    StopFactorDef("no_next_step", "Нет следующего шага", 15,
                  "Звонок завершён без конкретной договорённости о следующем действии"),
)


# Критерии, по которым обязательно создавать coaching-задачу при низкой оценке
CRITICAL_CRITERION_IDS: frozenset[str] = frozenset(
    {"decision_timeline", "qualification_summary", "close_attempt"}
)


# ─────────────────────────────────────────────────────────────────────────────
# Производные величины
# ─────────────────────────────────────────────────────────────────────────────

def max_raw_score() -> int:
    """Сумма весов всех положительных критериев (140 для Swiss Collection v1.0)."""
    return sum(c.max_score for cat in CATEGORIES for c in cat.criteria)


def max_penalty() -> int:
    """Сумма максимально возможных штрафов (35 для Swiss Collection v1.0)."""
    return sum(s.penalty for s in STOP_FACTORS)


def all_criteria() -> tuple[tuple[Category, Criterion], ...]:
    return tuple((cat, c) for cat in CATEGORIES for c in cat.criteria)


def find_criterion(criterion_id: str) -> Optional[tuple[Category, Criterion]]:
    for cat in CATEGORIES:
        for c in cat.criteria:
            if c.id == criterion_id:
                return cat, c
    return None


def find_stop_factor(factor_id: str) -> Optional[StopFactorDef]:
    for sf in STOP_FACTORS:
        if sf.id == factor_id:
            return sf
    return None


def normalize_to_100(raw_score: int) -> int:
    """Переводит сырой балл (-max_penalty..max_raw_score) в шкалу 0..100."""
    max_raw = max_raw_score()
    if max_raw <= 0:
        return 0
    pct = round((raw_score / max_raw) * 100)
    return max(0, min(100, pct))


def grade_for(normalized_score: int) -> str:
    """Возвращает текстовую градацию по нормированному баллу (0..100)."""
    if normalized_score >= 90:
        return "Эталон"
    if normalized_score >= 75:
        return "Хороший"
    if normalized_score >= 60:
        return "Удовлетворительно"
    return "Неудовлетворительно"


# ─────────────────────────────────────────────────────────────────────────────
# Текст карты для LLM-промпта
# ─────────────────────────────────────────────────────────────────────────────

def render_rubric_for_prompt() -> str:
    """Полный текст карты для системного промпта LLM."""
    lines: list[str] = [
        "КАРТА ОЦЕНКИ ЗВОНКА — Swiss Collection by RAAF Group (v1.0)",
        f"По каждому критерию выставь целое число от 0 до max баллов. "
        f"Сумма max положительных критериев = {max_raw_score()}.",
        "",
        "КРИТЕРИИ:",
    ]
    for i, cat in enumerate(CATEGORIES, start=1):
        lines.append(f"")
        lines.append(f"{i}. {cat.name.upper()}")
        for c in cat.criteria:
            lines.append(f"   • {c.id} [max {c.max_score}] — {c.name}: {c.description}")

    lines += [
        "",
        "СТОП-ФАКТОРЫ (если сработали — penalty вычитается; иначе triggered=false):",
    ]
    for sf in STOP_FACTORS:
        lines.append(f"   • {sf.id} [-{sf.penalty}] — {sf.name}: {sf.description}")

    lines += [
        "",
        f"ИТОГ raw_score = sum(score) − sum(penalty по triggered=true). "
        f"Допустимый диапазон raw_score: −{max_penalty()}..{max_raw_score()}.",
        "Затем нормализуем в /100. ШКАЛА:",
        "  • 90–100 — Эталон",
        "  • 75–89  — Хороший",
        "  • 60–74  — Удовлетворительно",
        "  • ниже 60 — Неудовлетворительно",
        "",
        "ЛОГИКА ЗАДАЧ: для критических критериев "
        f"({', '.join(sorted(CRITICAL_CRITERION_IDS))}) "
        "при оценке ниже половины max — обязательно добавь конкретную задачу "
        "в coaching_tasks.",
    ]
    return "\n".join(lines)
