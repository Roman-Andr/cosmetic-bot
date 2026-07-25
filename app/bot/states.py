"""Redis-backed conversational state declarations."""

from aiogram.fsm.state import State, StatesGroup


class SaleStates(StatesGroup):
    """Steps for a sales administrator recording an immutable purchase."""

    buyer_code = State()
    total_amount = State()
    products = State()
    confirmation = State()


class OwnerStates(StatesGroup):
    """Small owner-only conversational workflows."""

    sales_admin_id = State()
    tier_rules = State()
