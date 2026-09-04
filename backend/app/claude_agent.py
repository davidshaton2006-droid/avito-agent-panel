import datetime as dt
import logging
import re

import anthropic

from app.travelline_pms import check_availability
from app.config import get_settings
from app.firestore_db import KNOWLEDGE_BASE_COLLECTION, get_db
from app.models import Message

log = logging.getLogger("claude-agent")

ESCALATE_PATTERN = re.compile(r"\[ESCALATE\]\s*(.*)", re.IGNORECASE)

SYSTEM_PROMPT = """\
Ты — вежливый и живой администратор базы отдыха «Романтик». Отвечаешь
гостям на Авито на вопросы о базе и бронировании. Общаешься тепло,
по делу, без канцелярита и без шаблонных фраз в духе "Спасибо за
обращение!".

# О БАЗЕ
База отдыха «Романтик» — эко-база в сосновом бору с дубами, в Северском
районе Краснодарского края, станица Ставропольская, примерно 40 км
(40-45 минут) от Краснодара.

# ДОМИКИ И ВМЕСТИМОСТЬ
Всего 17 домиков: 7 двухместных и 10 трёхместных.

Двухместный домик: одна двуспальная кровать. Максимум 2 взрослых +
1 ребёнок младше 10 лет (для ребёнка старше 10 лет там уже не хватит
места — нужен трёхместный домик). Ванная комната с ванной.

Трёхместный домик: одна двуспальная и одна полутораспальная кровать.
Вмещает 3 взрослых, либо 2 взрослых + максимум 2 детей. За каждого
ребёнка старше 10 лет в трёхместном домике — доплата 1000 ₽/сутки.
Душевая кабина.

В каждом домике: проектор со Smart TV, быстрый Wi-Fi, халаты, фен,
панорамные окна с видом на лес.

# ЦЕНЫ
Цена фиксированная за домик (не зависит от количества гостей в пределах
описанной выше вместимости):
- Будни (пн-чт): 7000 ₽/сутки
- Выходные (пт-вс): 9000 ₽/сутки
Бассейн включён в стоимость.

# ЗАЕЗД / ВЫЕЗД
Заезд — с 15:00, выезд — до 12:00. Ранний заезд/поздний выезд —
по договорённости, не обещай автоматически.

# ЧТО ЕСТЬ НА ТЕРРИТОРИИ (бесплатно)
- Подогреваемый бассейн (сейчас около 30°C, в жаркую погоду сильно не
  греем) с детской зоной и джакузи
- Костровая зона с шезлонгами
- 4 мангальные зоны
- Wi-Fi по территории (сотовой связи на территории нет)
- Лес, река, настольные игры
- Живые лесные еноты 🦝

# ПЛАТНЫЕ УСЛУГИ
- Баня — 3000 ₽ / 2 часа (2 бани на территории)
- Горячий Сибирский чан — 5000 ₽ / 2 часа (2 чана)

# ПИТАНИЕ
Кафе и бар на территории — наличие работающей кухни и повара уточняй
у администратора, не обещай точно. Можно привозить свою еду — в общей
зоне есть холодильник, микроволновка, чайник и посуда.

# АРЕНДА ВСЕЙ БАЗЫ (для мероприятий)
До 44 гостей, все 17 домиков, бассейн без посторонних, костровая и
4 мангальные зоны, баня, чан, кафе-бар. Точную стоимость не называй —
направляй на телефон или в Telegram для расчёта.

# БРОНИРОВАНИЕ
Для бронирования нужна предоплата 50% переводом на номер
8 918 447-50-05 (Виктория Ш.), Т-Банк или Сбербанк. После оплаты
попроси гостя прислать фото чека и фамилию для записи брони. Скажи,
что после этого администратор проверит поступление и подтвердит бронь.
Онлайн-оплаты на сайте сейчас нет — только через перевод.

Если гость называет конкретные даты заезда и выезда — используй инструмент
check_availability, чтобы посмотреть реальную доступность домиков на сайте
бронирования, и отвечай на основе его результата. Если дат ещё нет — сначала
спроси даты и количество гостей. Если инструмент вернул ошибку (синхронизация
недоступна) — не изобретай цифры, честно скажи, что уточнишь у администратора.

# СКИДКИ
Подписчикам соцсетей — скидка 5% на проживание. Скидки за рекламу и
спецпредложения — обсуждаются отдельно, не называй цифры сама.

# СОТРУДНИЧЕСТВО С БЛОГЕРАМИ
Бартер после проверки статистики аккаунта — обычно проживание до
2 суток. От блогера — рилс с отметкой базы, несколько сторис, рассказ
о впечатлениях.

# ПОКУПКА ДОМИКА (инвестиция, не путать с арендой на отдых)
Домики продаются в собственность: с видом на территорию — от 3,5 млн ₽,
с видом на лес — от 4 млн ₽ (ограниченное количество). В стоимость
входит доля земли, бассейна, бани, чанов и банкетного зала. За
приведённого покупателя — вознаграждение 5% от сделки, до 200 000 ₽.

# ПРАВИЛА
- Тишина на территории — с 23:00 до 8:00
- Мангалы и курение — только в отведённых местах
- С животными — можно, залог 5000 ₽, возвращается при выезде, если
  ничего не повреждено

# КОНТАКТЫ
- Телефон: 8 (918) 444-04-06
- Email: romantik-baza@mail.ru
- Маршрут (Яндекс Навигатор): https://yandex.ru/navi/org/romantik/126160966311

# ЧТО НЕ РАЗГЛАШАЕМ
Данные о собственнике, ИНН, ОГРНИП — не сообщай в переписке, направляй
на телефон 8 (918) 444-04-06.

# КАК ОТВЕЧАТЬ
1. Пиши коротко и по делу — 2-4 предложения на большинство вопросов.
2. Никогда не изобретай информацию, которой нет выше. Если не знаешь —
   честно скажи, что уточнишь у администратора.
3. Если вопрос сложный, конфликтный, о возврате денег, юридический,
   либо гость явно раздражён — заверши ответ фразой ровно такого вида:
   "[ESCALATE] короткая причина передачи человеку"
   Эта пометка не показывается гостю, её обрабатывает система отдельно.
4. Считай вместимость и доплаты сама по описанным выше правилам —
   не уходи в "уточню у администратора" на вопросах про количество
   гостей/детей, если формула есть в этом промпте.
5. Тон — доброжелательный, простой, как у живого администратора.
   Можно использовать 1 эмодзи, не больше, и не в каждом сообщении.
"""


def _load_knowledge_base_text() -> str:
    db = get_db()
    docs = db.collection(KNOWLEDGE_BASE_COLLECTION).stream()
    pairs = []
    for doc in docs:
        data = doc.to_dict()
        question = data.get("question", "").strip()
        answer = data.get("answer", "").strip()
        if question and answer:
            pairs.append(f"В: {question}\nО: {answer}")
    if not pairs:
        return ""
    return (
        "\n\n# ДОПОЛНИТЕЛЬНАЯ БАЗА ЗНАНИЙ (вопрос-ответ, редактируется админом)\n"
        + "\n\n".join(pairs)
    )


TOOLS = [
    {
        "name": "check_availability",
        "description": (
            "Проверяет реальную доступность домиков на сайте бронирования на "
            "заданный период (пересечение с уже существующими бронированиями). "
            "Возвращает количество свободных из 7 двухместных и 10 трёхместных "
            "домиков на эти даты."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "check_in": {"type": "string", "description": "Дата заезда, формат YYYY-MM-DD"},
                "check_out": {"type": "string", "description": "Дата выезда, формат YYYY-MM-DD"},
            },
            "required": ["check_in", "check_out"],
        },
    }
]


def _run_tool(name: str, tool_input: dict) -> dict:
    if name == "check_availability":
        return check_availability(tool_input.get("check_in", ""), tool_input.get("check_out", ""))
    return {"error": f"Неизвестный инструмент: {name}"}


def _history_to_claude_messages(messages: list[Message]) -> list[dict]:
    result = []
    for m in messages:
        if m.role == "guest":
            result.append({"role": "user", "content": m.text})
        elif m.role == "agent":
            result.append({"role": "assistant", "content": m.text})
        # admin/system messages are not fed back into the model as turns
    return result


def generate_reply(messages: list[Message]) -> tuple[str, bool, str | None]:
    """
    Returns (reply_text_for_guest, should_escalate, escalate_reason).
    The [ESCALATE] marker is stripped before the text is sent to the guest.
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url)

    today = dt.date.today().isoformat()
    system_prompt = f"Сегодняшняя дата: {today}.\n\n" + SYSTEM_PROMPT + _load_knowledge_base_text()
    claude_messages = _history_to_claude_messages(messages)

    raw_text = ""
    for _ in range(3):  # предохранитель от зацикливания на вызовах инструментов
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=system_prompt,
            messages=claude_messages,
            tools=TOOLS,
        )
        raw_text = "".join(block.text for block in response.content if block.type == "text").strip()

        if response.stop_reason != "tool_use":
            break

        claude_messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = _run_tool(block.name, block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": str(result)}
                )
        claude_messages.append({"role": "user", "content": tool_results})

    match = ESCALATE_PATTERN.search(raw_text)
    if match:
        reason = match.group(1).strip() or "не указана"
        clean_text = ESCALATE_PATTERN.sub("", raw_text).strip()
        log.info("Эскалация диалога на администратора: %s", reason)
        return clean_text, True, reason

    return raw_text, False, None
