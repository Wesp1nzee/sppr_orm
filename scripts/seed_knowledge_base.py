"""
Идемпотентный скрипт загрузки базы знаний

Загружает: 24 определения КС РФ, статьи ФЗ «Об ОРД» и УПК РФ, постановление
Пленума ВС РФ № 1 от 10.02.2009.
"""

import argparse
import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User  # noqa: F401 регистрирует таблицу users (FK)
from app.db.session import async_session_factory
from app.knowledge_base.models import NormativeSourceType
from app.knowledge_base.repository import NormativeDocumentRepository

KSRF_URL = "https://www.ksrf.ru"
PRAVO_URL = "http://pravo.gov.ru"


def _todo(number: str) -> str:
    return f"[TODO: требует наполнения юристом-экспертом, {number}]"


# Номера определений КС РФ
KS_RULING_NUMBERS = [
    "86-О",
    "345-О",
    "528-О-О",
    "568-О",
    "268-О",
    "2898-О",
    "72-О",
    "326-О-О",
    "295-О-О",
    "1198-О-О",
    "1468-О",
    "445-О-О",
    "1395-О",
    "1404-О",
    "18-О",
    "636-О-О",
    "1487-О-О",
    "590-О",
    "356-О-О",
    "459-О-О",
    "4-О",
    "417-О-О",
    "924-О-О",
    "312-О-О",
]


def _ks_ruling(number: str) -> dict[str, Any]:
    placeholder = _todo(f"определение КС РФ № {number}")
    return {
        "source_type": NormativeSourceType.ks_rf_ruling,
        "code": number.replace("О", "O"),
        "title": f"Определение Конституционного Суда РФ № {number}",
        "full_text": placeholder,
        "summary": placeholder,
        "source_url": KSRF_URL,
        "extra": {"number": number},
    }


def _fz_ord(article: str, part: str = "") -> dict[str, Any]:
    code = f"fz-ord-art{article}" + (f"-ch{part}" if part else "")
    title = f"ФЗ «Об ОРД», ст. {article}" + (f", ч. {part}" if part else "")
    return {
        "source_type": NormativeSourceType.federal_law,
        "code": code,
        "title": title,
        "full_text": _todo(title),
        "summary": _FZ_ORD_SUMMARIES[code],
        "source_url": PRAVO_URL,
        "extra": {
            "law": "144-ФЗ от 12.08.1995",
            "article": article,
            "part": part or None,
        },
    }


_FZ_ORD_SUMMARIES = {
    "fz-ord-art5": (
        "Соблюдение прав и свобод человека и гражданина при осуществлении "
        "оперативно-розыскной деятельности; запрет осуществлять ОРМ в целях, "
        "не предусмотренных законом."
    ),
    "fz-ord-art5-ch4": (
        "Лицо, полагающее, что действия органов, осуществляющих ОРД, привели "
        "к нарушению его прав и свобод, вправе обжаловать эти действия и "
        "истребовать сведения о полученной о нём информации."
    ),
    "fz-ord-art6": (
        "Перечень оперативно-розыскных мероприятий; запрет проведения ОРМ, "
        "не предусмотренных законом."
    ),
    "fz-ord-art7": (
        "Основания для проведения ОРМ: возбуждённое уголовное дело, сведения "
        "о признаках преступления, поручение следователя или дознавателя и др."
    ),
    "fz-ord-art8": (
        "Проведение ОРМ, ограничивающих конституционные права граждан (тайна "
        "переписки, неприкосновенность жилища), — на основании судебного "
        "решения; в неотложных случаях — с уведомлением суда в течение 24 (48) "
        "часов."
    ),
    "fz-ord-art9": (
        "Основания и порядок судебного рассмотрения материалов об ограничении "
        "конституционных прав граждан при проведении ОРМ."
    ),
    "fz-ord-art11": (
        "Результаты ОРД могут использоваться в доказывании по уголовным делам "
        "в соответствии с уголовно-процессуальным законодательством."
    ),
    "fz-ord-art12": (
        "Защита сведений об органах, осуществляющих ОРД, и о лицах, "
        "оказывающих им содействие."
    ),
}

FZ_ORD_ARTICLES = [
    _fz_ord("5"),
    _fz_ord("5", "4"),
    _fz_ord("6"),
    _fz_ord("7"),
    _fz_ord("8"),
    _fz_ord("9"),
    _fz_ord("11"),
    _fz_ord("12"),
]


def _upk(code: str, article: str, summary: str) -> dict[str, Any]:
    return {
        "source_type": NormativeSourceType.federal_law,
        "code": code,
        "title": f"УПК РФ, ст. {article}",
        "full_text": _todo(f"ст. {article} УПК РФ"),
        "summary": summary,
        "source_url": PRAVO_URL,
        "extra": {"law": "УПК РФ от 18.12.2001 № 174-ФЗ", "article": article},
    }


SEED_DOCUMENTS: list[dict[str, Any]] = [
    *(_ks_ruling(n) for n in KS_RULING_NUMBERS),
    *FZ_ORD_ARTICLES,
    _upk(
        "upk-art89",
        "89",
        "В процессе доказывания запрещается использование результатов "
        "оперативно-розыскной деятельности, если они не отвечают требованиям, "
        "предъявляемым к доказательствам УПК РФ.",
    ),
    _upk(
        "upk-art81-1",
        "81.1",
        _todo("ст. 81.1 УПК РФ"),
    ),
    {
        "source_type": NormativeSourceType.federal_law,
        "code": "upk",
        "title": "Уголовно-процессуальный кодекс РФ",
        "full_text": _todo("УПК РФ"),
        "summary": (
            "Уголовно-процессуальный кодекс РФ — порядок уголовного "
            "судопроизводства, включая участие защитника и порядок задержания."
        ),
        "source_url": PRAVO_URL,
        "extra": {"law": "УПК РФ от 18.12.2001 № 174-ФЗ"},
    },
    {
        "source_type": NormativeSourceType.federal_law,
        "code": "koap",
        "title": "Кодекс Российской Федерации об административных правонарушениях",
        "full_text": _todo("КоАП РФ"),
        "summary": (
            "КоАП РФ — порядок административного задержания и составления "
            "протокола об административном правонарушении."
        ),
        "source_url": PRAVO_URL,
        "extra": {"law": "КоАП РФ от 30.12.2001 № 195-ФЗ"},
    },
    {
        "source_type": NormativeSourceType.plenum_resolution,
        "code": "plenum-vs-2009-1",
        "title": "Постановление Пленума ВС РФ от 10.02.2009 № 1",
        "full_text": _todo("Постановление Пленума ВС РФ от 10.02.2009 № 1"),
        "summary": (
            "О практике рассмотрения судами жалоб в порядке статьи 125 "
            "Уголовно-процессуального кодекса Российской Федерации."
        ),
        "source_url": "https://vsrf.ru",
        "extra": {"number": "1", "date": "10.02.2009"},
    },
]


async def seed_knowledge_base(session: AsyncSession) -> int:
    """Загружает документы; пропускает существующие коды. Возвращает число созданных."""
    repo = NormativeDocumentRepository(session)
    created = 0
    for entry in SEED_DOCUMENTS:
        if await repo.get_current_by_code(entry["code"]) is not None:
            continue
        fields = {k: v for k, v in entry.items() if k != "code"}
        await repo.create_new_version(code=entry["code"], admin_id=None, **fields)
        created += 1
    await session.commit()
    return created


async def _run() -> int:
    async with async_session_factory() as session:
        return await seed_knowledge_base(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Загрузить базу знаний")
    parser.parse_args()
    created = asyncio.run(_run())
    print(f"Создано документов базы знаний: {created}")


if __name__ == "__main__":
    main()
