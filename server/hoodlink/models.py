from pydantic import BaseModel


class Quote(BaseModel):
    symbol: str
    last_trade_price: str | None = None
    bid_price: str | None = None
    bid_size: int | None = None
    ask_price: str | None = None
    ask_size: int | None = None
    previous_close: str | None = None
    updated_at: str | None = None


class HistoryBar(BaseModel):
    begins_at: str | None = None
    open_price: str | None = None
    close_price: str | None = None
    high_price: str | None = None
    low_price: str | None = None
    volume: int | None = None


class HistoryResponse(BaseModel):
    symbol: str
    interval: str
    span: str
    historicals: list[HistoryBar] = []


class Fundamentals(BaseModel):
    symbol: str | None = None
    market_cap: str | None = None
    pe_ratio: str | None = None
    dividend_yield: str | None = None
    high: str | None = None
    low: str | None = None
    open: str | None = None
    volume: str | None = None
    description: str | None = None


class OrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    type: str = "limit"  # "market" or "limit"
    price: float | None = None
    time_in_force: str = "gfd"  # "gfd", "gtc", "ioc", "opg"
    stop_price: float | None = None
    market_hours: str = "all_day_hours"
    position_effect: str = "open"  # "open" or "close"


class OptionsLeg(BaseModel):
    option: str  # URL to option instrument
    side: str = "buy"
    position_effect: str = "open"
    ratio_quantity: int = 1


class OptionsOrderRequest(BaseModel):
    option_url: str  # URL to option instrument (used for single-leg)
    side: str = "buy"
    quantity: int = 1
    price: float | None = None
    stop_price: float | None = None  # For stop-limit orders
    type: str = "limit"
    time_in_force: str = "gfd"
    position_effect: str = "open"
    direction: str = "debit"  # "debit" or "credit"
    override_day_trade_checks: bool = False
    override_no_bid_price: bool = False


class OrderResponse(BaseModel):
    id: str | None = None
    state: str | None = None
    side: str | None = None
    quantity: str | None = None
    price: str | None = None
    symbol: str | None = None
    type: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class Position(BaseModel):
    symbol: str | None = None
    quantity: str | None = None
    average_buy_price: str | None = None
    instrument: str | None = None


class Portfolio(BaseModel):
    equity: str | None = None
    market_value: str | None = None
    total_return: str | None = None
    total_return_pct: str | None = None


class StatusResponse(BaseModel):
    status: str
    bridge_connected: bool


class OptionsOrderExecution(BaseModel):
    """Options order execution details."""
    id: str
    price: str
    quantity: str
    settlement_date: str
    timestamp: str


class OptionsOrderLegResponse(BaseModel):
    """Options order leg details in response."""
    id: str
    option: str
    position_effect: str
    ratio_quantity: int
    side: str
    executions: list[OptionsOrderExecution] = []
    expiration_date: str | None = None
    strike_price: str | None = None
    option_type: str | None = None
    long_strategy_code: str | None = None
    short_strategy_code: str | None = None


class OptionsOrderResponse(BaseModel):
    """Options order response from Robinhood API."""
    id: str
    account_number: str
    cancel_url: str | None = None
    canceled_quantity: str
    created_at: str
    updated_at: str
    direction: str
    legs: list[OptionsOrderLegResponse]
    pending_quantity: str
    premium: str
    processed_premium: str
    processed_premium_direction: str
    market_hours: str
    net_amount: str
    net_amount_direction: str
    price: str
    processed_quantity: str
    quantity: str
    ref_id: str
    regulatory_fees: str
    contract_fees: str
    gold_savings: str
    state: str
    time_in_force: str
    trigger: str
    type: str
    chain_id: str
    chain_symbol: str
    response_category: str | None = None
    opening_strategy: str | None = None
    closing_strategy: str | None = None
    stop_price: str | None = None
    form_source: str
    client_bid_at_submission: str | None = None
    client_ask_at_submission: str | None = None
    client_time_at_submission: str | None = None
    average_net_premium_paid: str
    estimated_total_net_amount: str
    estimated_total_net_amount_direction: str
    is_replaceable: bool
    strategy: str
    derived_state: str
    sales_taxes: list = []
