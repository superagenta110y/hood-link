import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from hoodlink.auth import require_api_key
from hoodlink.bridge import bridge
from hoodlink.models import OptionsOrderRequest, OrderRequest

router = APIRouter(prefix="/trading", tags=["trading"], dependencies=[Depends(require_api_key)])

RH_API = "https://api.robinhood.com"

ORDER_FORM_VERSION = 7


async def _resolve_instrument(symbol: str) -> str:
    data = await bridge.send_command("GET", f"{RH_API}/instruments/?symbol={symbol}")
    results = data.get("results", []) if isinstance(data, dict) else []
    if not results:
        raise HTTPException(status_code=404, detail=f"Instrument not found for {symbol}")
    return results[0]["url"]


async def _get_account_url() -> str:
    data = await bridge.send_command("GET", f"{RH_API}/accounts/")
    results = data.get("results", []) if isinstance(data, dict) else []
    if not results:
        raise HTTPException(status_code=502, detail="No account found")
    return results[0]["url"]


async def _get_quote(symbol: str) -> dict:
    return await bridge.send_command("GET", f"{RH_API}/quotes/{symbol}/")


@router.post("/orders")
async def place_order(order: OrderRequest):
    symbol = order.symbol.upper()
    try:
        instrument_url, account_url, quote = await _resolve_instrument(symbol), None, None
        account_url = await _get_account_url()
        quote = await _get_quote(symbol)

        body = {
            "account": account_url,
            "instrument": instrument_url,
            "symbol": symbol,
            "side": order.side,
            "quantity": str(int(order.quantity)) if order.quantity == int(order.quantity) else str(order.quantity),
            "type": order.type,
            "time_in_force": order.time_in_force,
            "trigger": "immediate",
            "market_hours": order.market_hours,
            "position_effect": order.position_effect,
            "order_form_version": ORDER_FORM_VERSION,
            "ref_id": str(uuid.uuid4()),
        }

        # Bid/ask from live quote
        if isinstance(quote, dict):
            if quote.get("ask_price"):
                body["ask_price"] = quote["ask_price"]
            if quote.get("bid_price"):
                body["bid_price"] = quote["bid_price"]
            if quote.get("updated_at"):
                body["bid_ask_timestamp"] = quote["updated_at"]

        # Price
        if order.type == "limit" and order.price is not None:
            body["price"] = f"{order.price:.2f}"
        elif order.type == "market" and isinstance(quote, dict):
            # Market orders still need a price collar — use ask for buy, bid for sell
            collar = quote.get("ask_price") if order.side == "buy" else quote.get("bid_price")
            if collar:
                body["price"] = collar

        # Stop trigger
        if order.stop_price is not None:
            body["trigger"] = "stop"
            body["stop_price"] = f"{order.stop_price:.2f}"

        # Estimated fees (RH sends this but zeros are fine for the request)
        body["estimated_fees"] = [{"name": "CAT_FEE", "rate": "0.0000000000", "amount": "0.00"}]
        body["estimated_total_fee"] = "0.00"

        data = await bridge.send_command("POST", f"{RH_API}/orders/", body=body)
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/options/orders")
async def place_options_order(order: OptionsOrderRequest):
    try:
        account_url = await _get_account_url()

        # Fetch option instrument market data for bid/ask
        option_md_url = order.option_url.replace("/options/instruments/", "/marketdata/options/")
        client_bid = "0"
        client_ask = "0"
        try:
            md = await bridge.send_command("GET", option_md_url)
            if isinstance(md, dict):
                client_bid = md.get("bid_price") or "0"
                client_ask = md.get("ask_price") or "0"
        except Exception:
            pass

        body = {
            "account": account_url,
            "direction": order.direction,
            "legs": [
                {
                    "option": order.option_url,
                    "side": order.side,
                    "position_effect": order.position_effect,
                    "ratio_quantity": 1,
                }
            ],
            "price": f"{order.price:.2f}" if order.price is not None else "0.01",
            "quantity": str(order.quantity),
            "type": order.type,
            "time_in_force": order.time_in_force,
            "trigger": "stop" if order.stop_price is not None else "immediate",
            "market_hours": None,
            "override_day_trade_checks": order.override_day_trade_checks,
            "ref_id": str(uuid.uuid4()),
            "form_source": "strategy_detail" if order.stop_price is not None else "option_chain",
            "check_overrides": ["override_no_bid_price"] if order.override_no_bid_price else [],
            "client_bid_at_submission": client_bid,
            "client_ask_at_submission": client_ask,
        }

        # Add stop_price for stop-limit orders
        if order.stop_price is not None:
            body["stop_price"] = f"{order.stop_price:.2f}"

        data = await bridge.send_command("POST", f"{RH_API}/options/orders/", body=body)
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    try:
        data = await bridge.send_command("POST", f"{RH_API}/orders/{order_id}/cancel/")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/orders")
async def list_orders(
    active_only: bool = Query(True, description="Only return active (non-filled, non-cancelled) orders"),
):
    """
    List Robinhood orders.
    Follows pagination so callers can reliably locate recent orders.
    """
    try:
        url = f"{RH_API}/orders/"
        if active_only:
            url += "?is_closed=false"

        data = await bridge.send_command("GET", url)
        if not isinstance(data, dict):
            return data

        results = list(data.get("results") or [])
        next_url = data.get("next")
        pages = 0
        max_pages = 10
        while next_url and pages < max_pages:
            page = await bridge.send_command("GET", next_url)
            if not isinstance(page, dict):
                break
            page_results = page.get("results") or []
            if isinstance(page_results, list):
                results.extend(page_results)
            next_url = page.get("next")
            pages += 1

        merged = dict(data)
        merged["results"] = results
        merged["next"] = next_url
        return merged
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/options/orders")
async def list_option_orders(
    active_only: bool = Query(True, description="Only return active (non-filled, non-cancelled) option orders"),
):
    """
    List Robinhood option orders.
    Follows pagination to surface recent orders that may not be on the first page.
    """
    try:
        url = f"{RH_API}/options/orders/"
        if active_only:
            url += "?is_closed=false"

        data = await bridge.send_command("GET", url)
        if not isinstance(data, dict):
            return data

        results = list(data.get("results") or [])
        next_url = data.get("next")
        pages = 0
        max_pages = 10
        while next_url and pages < max_pages:
            page = await bridge.send_command("GET", next_url)
            if not isinstance(page, dict):
                break
            page_results = page.get("results") or []
            if isinstance(page_results, list):
                results.extend(page_results)
            next_url = page.get("next")
            pages += 1

        merged = dict(data)
        merged["results"] = results
        merged["next"] = next_url
        return merged
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/options/orders/{order_id}")
async def get_option_order(order_id: str):
    """
    Fetch a single Robinhood options order by ID.
    This avoids pagination blind spots in /options/orders.
    """
    try:
        data = await bridge.send_command("GET", f"{RH_API}/options/orders/{order_id}/")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
