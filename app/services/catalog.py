"""Google Sheets catalogue synchronisation and local search."""

from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from typing import cast

import gspread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Product
from app.services.loyalty import money


class CatalogSyncError(RuntimeError):
    """Raised when the configured Google Sheets catalogue cannot be read."""


def parse_price(value: object) -> Decimal | None:
    """Convert Sheets price cells into BYN values without leaking float arithmetic."""
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).replace(" ", "").replace(",", ".")
    try:
        return money(Decimal(normalized))
    except InvalidOperation as exc:
        raise CatalogSyncError(f"Cannot parse product price: {value!r}") from exc


class CatalogService:
    """Maintain a local catalogue snapshot for bot product links and sale search."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def sync(self, session: AsyncSession) -> int:
        """Pull Google Sheets rows and atomically update the local product catalogue."""
        if not self._settings.google_sheets_credentials_file:
            raise CatalogSyncError("GOOGLE_SHEETS_CREDENTIALS_FILE is not configured")

        records = await asyncio.to_thread(self._read_records)
        existing_products = {
            product.external_id: product
            for product in (await session.scalars(select(Product).with_for_update())).all()
        }
        seen_ids: set[str] = set()

        try:
            for row in records:
                external_id = str(row.get("Tilda UID", "")).strip()
                title = str(row.get("Title", "")).strip()
                if not external_id or not title:
                    continue
                seen_ids.add(external_id)
                product = existing_products.get(external_id)
                if product is None:
                    product = Product(external_id=external_id, title=title)
                    session.add(product)
                product.title = title
                product.current_price = parse_price(row.get("Price"))
                product.url = str(row.get("Url", "")).strip() or None
                product.photo_url = str(row.get("Photo", "")).strip() or None
                product.is_active = True

            for external_id, product in existing_products.items():
                if external_id not in seen_ids:
                    product.is_active = False
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        return len(seen_ids)

    async def search(self, session: AsyncSession, query: str, *, limit: int = 10) -> list[Product]:
        """Find active products by title or external Tilda identifier."""
        escaped_query = query.strip()
        if not escaped_query:
            return []
        statement = (
            select(Product)
            .where(
                Product.is_active.is_(True),
                (Product.title.ilike(f"%{escaped_query}%"))
                | (Product.external_id.ilike(f"%{escaped_query}%")),
            )
            .order_by(Product.title)
            .limit(limit)
        )
        return list((await session.scalars(statement)).all())

    def _read_records(self) -> list[dict[str, object]]:
        credentials_file = self._settings.google_sheets_credentials_file
        if credentials_file is None:
            raise CatalogSyncError("GOOGLE_SHEETS_CREDENTIALS_FILE is not configured")
        client = gspread.service_account(filename=credentials_file)
        worksheet = client.open(self._settings.google_sheet_name).sheet1
        return cast(list[dict[str, object]], worksheet.get_all_records())
