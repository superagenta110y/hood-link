from fastapi import APIRouter, Depends, HTTPException, Query

from hoodlink.auth import require_api_key
from hoodlink.bridge import bridge

router = APIRouter(prefix="/market", tags=["market"], dependencies=[Depends(require_api_key)])

RH_API = "https://api.robinhood.com"
RH_BONFIRE = "https://bonfire.robinhood.com"


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    symbol = symbol.upper()
    try:
        data = await bridge.send_command("GET", f"{RH_API}/quotes/{symbol}/")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/quotes")
async def get_quotes(symbols: str = Query(..., description="Comma-separated symbols")):
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    try:
        data = await bridge.send_command(
            "GET", f"{RH_API}/quotes/?symbols={','.join(symbol_list)}"
        )
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/history/{symbol}")
async def get_history(
    symbol: str,
    interval: str = Query("day", description="Interval: 5minute, 10minute, hour, day, week"),
    span: str = Query("year", description="Span: day, week, month, 3month, year, 5year"),
):
    symbol = symbol.upper()
    try:
        data = await bridge.send_command(
            "GET",
            f"{RH_API}/marketdata/historicals/{symbol}/?interval={interval}&span={span}",
        )
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/fundamentals/{symbol}")
async def get_fundamentals(symbol: str):
    symbol = symbol.upper()
    try:
        data = await bridge.send_command("GET", f"{RH_API}/fundamentals/{symbol}/")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/instruments")
async def get_instruments(
    symbol: str | None = Query(None, description="Exact ticker symbol"),
    query: str | None = Query(None, description="Search by name or symbol"),
):
    try:
        url = f"{RH_API}/instruments/"
        params = []
        if symbol:
            params.append(f"symbol={symbol.upper()}")
        if query:
            params.append(f"query={query}")
        if params:
            url += "?" + "&".join(params)
        data = await bridge.send_command("GET", url)
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/options/marketdata")
async def get_options_marketdata(
    instruments: str = Query(..., description="Comma-separated option instrument IDs"),
):
    try:
        data = await bridge.send_command(
            "GET", f"{RH_API}/marketdata/options/?instruments={instruments}"
        )
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/futures/products")
async def get_futures_products():
    try:
        data = await bridge.send_command("GET", f"{RH_API}/arsenal/v1/futures/products/")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/futures/contracts")
async def get_futures_contracts(
    product_ids: str | None = Query(None, description="Comma-separated product IDs"),
    contract_ids: str | None = Query(None, description="Comma-separated contract IDs"),
):
    url = f"{RH_API}/arsenal/v1/futures/contracts/"
    params = []
    if product_ids:
        params.append(f"product_ids={product_ids}")
    if contract_ids:
        params.append(f"contract_ids={contract_ids}")
    if params:
        url += "?" + "&".join(params)
    try:
        data = await bridge.send_command("GET", url)
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


async def _resolve_chain(symbol: str) -> dict:
    """Resolve a symbol to its options chain metadata. Returns the raw chain object."""
    symbol = symbol.upper()
    data = await bridge.send_command(
        "GET", f"{RH_API}/options/chains/?underlying_symbol={symbol}"
    )
    if isinstance(data, dict):
        results = data.get("results", [])
        if not results and data.get("id"):
            results = [data]
        if results and results[0].get("id"):
            return results[0]
    return {}


@router.get("/options/expirations/{symbol}")
async def get_options_expirations(symbol: str):
    """Get available expiration dates for a symbol's options chain."""
    symbol = symbol.upper()
    try:
        chain = await _resolve_chain(symbol)
        if not chain:
            return {"symbol": symbol, "chain_id": None, "expiration_dates": []}

        chain_id = chain.get("id")
        expiration_dates = chain.get("expiration_dates", [])

        # If the chain object didn't include expiration_dates, try fetching a
        # small page of instruments to discover them
        if not expiration_dates and chain_id:
            page = await bridge.send_command(
                "GET",
                f"{RH_API}/options/instruments/?chain_id={chain_id}&state=active",
            )
            if isinstance(page, dict):
                seen = set()
                for inst in page.get("results", []):
                    exp = inst.get("expiration_date")
                    if exp:
                        seen.add(exp)
                expiration_dates = sorted(seen)

        return {
            "symbol": symbol,
            "chain_id": chain_id,
            "expiration_dates": sorted(expiration_dates) if expiration_dates else [],
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/options/{symbol}")
async def get_options(
    symbol: str,
    expiration_dates: str | None = Query(None, description="Comma-separated dates YYYY-MM-DD"),
    type: str | None = Query(None, description="call or put"),
):
    symbol = symbol.upper()
    try:
        chain = await _resolve_chain(symbol)
        chain_id = chain.get("id") if chain else None

        if not chain_id:
            return {"chain_id": None, "expiration_dates": [], "results": []}

        if not expiration_dates and not type:
            return {
                "chain_id": chain_id,
                "expiration_dates": chain.get("expiration_dates", []),
                "results": [],
            }

        instruments_url = f"{RH_API}/options/instruments/?chain_id={chain_id}&state=active"
        if expiration_dates:
            instruments_url += f"&expiration_dates={expiration_dates}"
        if type:
            instruments_url += f"&type={type}"

        # Follow pagination to collect all instruments
        all_instruments = []
        page_url = instruments_url
        while page_url:
            page_data = await bridge.send_command("GET", page_url)
            if isinstance(page_data, dict):
                all_instruments.extend(page_data.get("results", []))
                page_url = page_data.get("next")
            else:
                break

        # Fetch market data and stitch into instruments
        if all_instruments:
            # Extract instrument IDs from URLs
            ids = []
            for inst in all_instruments:
                inst_id = inst.get("id")
                if not inst_id and inst.get("url"):
                    # Extract ID from URL like .../options/instruments/{id}/
                    parts = inst["url"].rstrip("/").split("/")
                    inst_id = parts[-1] if parts else None
                if inst_id:
                    ids.append(inst_id)

            # Batch fetch market data (20 per request to stay within URL limits)
            md_map: dict[str, dict] = {}
            batch_size = 20
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i : i + batch_size]
                ids_param = "%2C".join(batch_ids)
                try:
                    md_data = await bridge.send_command(
                        "GET",
                        f"{RH_API}/marketdata/options/?ids={ids_param}&include_all_sessions=false",
                    )
                    if isinstance(md_data, dict):
                        for md in md_data.get("results", []):
                            # Key by instrument ID extracted from the instrument URL
                            md_inst = md.get("instrument")
                            if md_inst:
                                md_id = md_inst.rstrip("/").split("/")[-1]
                                md_map[md_id] = md
                except Exception:
                    pass  # Don't fail the whole request if market data fails

            # Merge market data into each instrument
            md_fields = [
                "bid_price", "ask_price", "bid_size", "ask_size",
                "last_trade_price", "last_trade_size",
                "high_price", "low_price", "volume",
                "open_interest", "implied_volatility",
                "delta", "gamma", "theta", "vega", "rho",
                "chance_of_profit_long", "chance_of_profit_short",
                "mark_price", "previous_close_price",
                "break_even_price",
            ]
            for inst in all_instruments:
                inst_id = inst.get("id")
                if not inst_id and inst.get("url"):
                    inst_id = inst["url"].rstrip("/").split("/")[-1]
                md = md_map.get(inst_id)
                if md:
                    for field in md_fields:
                        if field in md:
                            inst[field] = md[field]

        return {"results": all_instruments}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
