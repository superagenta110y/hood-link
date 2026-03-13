from fastapi import APIRouter, Depends, HTTPException, Query

from hoodlink.auth import require_api_key
from hoodlink.bridge import bridge

router = APIRouter(prefix="/account", tags=["account"], dependencies=[Depends(require_api_key)])

RH_API = "https://api.robinhood.com"


@router.get("/accounts")
async def get_accounts():
    try:
        data = await bridge.send_command("GET", f"{RH_API}/accounts/")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/positions")
async def get_positions():
    try:
        data = await bridge.send_command("GET", f"{RH_API}/positions/?nonzero=true")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/portfolio")
async def get_portfolio():
    try:
        accounts = await bridge.send_command("GET", f"{RH_API}/accounts/")
        results = accounts.get("results", []) if isinstance(accounts, dict) else []
        if not results:
            raise HTTPException(status_code=502, detail="No account found")
        account_number = results[0]["account_number"]
        data = await bridge.send_command(
            "GET", f"{RH_API}/portfolios/{account_number}/"
        )
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/portfolios/{account_id}")
async def get_portfolio_by_id(account_id: str):
    try:
        data = await bridge.send_command("GET", f"{RH_API}/portfolios/{account_id}/")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/options/positions")
async def get_options_positions(nonzero: bool = Query(True, description="Only non-zero positions")):
    url = f"{RH_API}/options/aggregate_positions/"
    if nonzero:
        url += "?nonzero=True"
    try:
        data = await bridge.send_command("GET", url)
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/futures/session/{contract_id}/{date}")
async def get_futures_session(contract_id: str, date: str):
    try:
        data = await bridge.send_command(
            "GET", f"{RH_API}/arsenal/v1/futures/trading_sessions/{contract_id}/{date}"
        )
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/futures/orders/{account_id}")
async def get_futures_orders(account_id: str):
    try:
        data = await bridge.send_command(
            "GET", f"{RH_API}/ceres/v1/accounts/{account_id}/orders"
        )
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/futures/pnl/{account_id}")
async def get_futures_pnl(
    account_id: str,
    contract_id: str = Query(..., description="Futures contract ID"),
):
    try:
        data = await bridge.send_command(
            "GET",
            f"{RH_API}/ceres/v1/accounts/{account_id}/pnl_cost_basis?contractId={contract_id}",
        )
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/watchlists")
async def get_watchlists():
    try:
        data = await bridge.send_command("GET", f"{RH_API}/watchlists/")
        return data
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
