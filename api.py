"""
US Debt Clock FastAPI Backend
Real-time debt tracking with fiscal intelligence
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import os
import logging

from fastapi import FastAPI, WebSocket, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from data_collector import (
    DataCollector,
    Database,
    FiscalAnalyzer,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="US Debt Clock", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
DB = Database(Path(__file__).parent / "debt_clock.db")
FRED_KEY = os.getenv("FRED_KEY", "YOUR_FRED_KEY")
COLLECTOR = DataCollector(FRED_KEY)

# Global state
CURRENT_DATA = {}
LAST_UPDATE = None


# Static G7 comparison data (updated monthly)
G7_DEBT_DATA = {
    "US": {
        "debt": 33.7e12,
        "gdp": 27.4e12,
        "population": 335e6,
        "debt_to_gdp": 123.1,
        "interest_as_pct_revenue": 18.2,
    },
    "Japan": {
        "debt": 9.1e12,
        "gdp": 4.2e12,
        "population": 125e6,
        "debt_to_gdp": 216.7,
        "interest_as_pct_revenue": 8.1,
    },
    "Italy": {
        "debt": 2.8e12,
        "gdp": 2.0e12,
        "population": 58e6,
        "debt_to_gdp": 140,
        "interest_as_pct_revenue": 12.5,
    },
    "France": {
        "debt": 2.7e12,
        "gdp": 2.8e12,
        "population": 67e6,
        "debt_to_gdp": 96.4,
        "interest_as_pct_revenue": 6.8,
    },
    "UK": {
        "debt": 2.4e12,
        "gdp": 3.1e12,
        "population": 67e6,
        "debt_to_gdp": 77.4,
        "interest_as_pct_revenue": 5.2,
    },
    "Germany": {
        "debt": 1.8e12,
        "gdp": 4.4e12,
        "population": 83e6,
        "debt_to_gdp": 40.9,
        "interest_as_pct_revenue": 1.8,
    },
    "Canada": {
        "debt": 1.3e12,
        "gdp": 2.1e12,
        "population": 39e6,
        "debt_to_gdp": 61.9,
        "interest_as_pct_revenue": 7.5,
    },
}


async def update_data():
    """Background task to update data periodically"""
    global CURRENT_DATA, LAST_UPDATE
    while True:
        try:
            logger.info("Collecting data...")
            CURRENT_DATA = await COLLECTOR.collect_all()
            LAST_UPDATE = datetime.utcnow()
            logger.info(f"Data updated at {LAST_UPDATE}")
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            # Fallback to cached data
            snapshot = DB.get_latest_snapshot()
            if snapshot:
                CURRENT_DATA = snapshot
        await asyncio.sleep(3600)  # Update every hour


@app.on_event("startup")
async def startup():
    """Start background tasks"""
    asyncio.create_task(update_data())
    # Initial collection
    try:
        global CURRENT_DATA, LAST_UPDATE
        CURRENT_DATA = await COLLECTOR.collect_all()
        LAST_UPDATE = datetime.utcnow()
    except Exception as e:
        logger.error(f"Initial data collection failed: {e}")
        snapshot = DB.get_latest_snapshot()
        if snapshot:
            CURRENT_DATA = snapshot
            LAST_UPDATE = datetime.fromisoformat(snapshot.get("timestamp", datetime.utcnow().isoformat()))


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "last_update": LAST_UPDATE,
        "data_available": bool(CURRENT_DATA),
    }


@app.get("/current")
async def get_current():
    """Get current debt snapshot with all metrics"""
    if not CURRENT_DATA:
        raise HTTPException(status_code=503, detail="Data not yet loaded")

    debt = CURRENT_DATA.get("national_debt", 0)
    population = 335e6

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "national_debt": debt,
        "national_debt_formatted": f"${debt:,.0f}",
        "debt_per_capita": debt / population,
        "debt_per_capita_formatted": f"${debt/population:,.2f}",
        "debt_to_gdp": CURRENT_DATA.get("debt_to_gdp", 0),
        "annual_deficit": CURRENT_DATA.get("deficit", 0) * 365,
        "annual_deficit_formatted": f"${CURRENT_DATA.get('deficit', 0) * 365:,.0f}",
        "interest_expense_today": CURRENT_DATA.get("interest_today", 0),
        "interest_expense_today_formatted": f"${CURRENT_DATA.get('interest_today', 0):,.0f}",
        "annual_interest": CURRENT_DATA.get("interest_today", 0) * 365,
        "interest_as_pct_revenue": FiscalAnalyzer.calculate_interest_as_revenue_pct(
            CURRENT_DATA.get("interest_today", 0) * 365,
            CURRENT_DATA.get("revenue", 1),
        ),
        "gdp": CURRENT_DATA.get("gdp", 0),
        "cpi": CURRENT_DATA.get("cpi", 0),
        "unemployment": CURRENT_DATA.get("unemployment", 0),
        "fed_funds_rate": CURRENT_DATA.get("fed_funds_rate", 0),
        "treasury_10y_yield": CURRENT_DATA.get("treasury_10y_yield", 0),
        "m2_supply": CURRENT_DATA.get("m2_supply", 0),
        "fiscal_pressure_index": CURRENT_DATA.get("fiscal_pressure_index", 0),
        "fiscal_regime": CURRENT_DATA.get("fiscal_regime", "unknown"),
        "pressure_factors": CURRENT_DATA.get("pressure_factors", {}),
    }


@app.get("/history")
async def get_history(
    metric: str = Query("debt", description="Metric: debt, debt_to_gdp, deficit, interest"),
    period: str = Query("1y", description="Period: 1y, 5y, 10y, max"),
):
    """Get historical data for a metric"""
    days_map = {"1y": 365, "5y": 1825, "10y": 3650, "max": 36500}
    days = days_map.get(period, 365)

    if metric == "debt":
        data = DB.get_historical_range(days)
        return {
            "metric": metric,
            "period": period,
            "data": data,
        }
    else:
        # Add more metrics as needed
        return {"metric": metric, "period": period, "data": []}


@app.get("/regime")
async def get_regime():
    """Get current fiscal pressure regime"""
    regime = DB.get_latest_regime()
    if regime:
        return {
            "regime": regime["regime"],
            "pressure_index": regime["pressure_index"],
            "description": get_regime_description(regime["regime"]),
            "factors": regime["factors"],
        }
    return {"regime": "unknown", "pressure_index": 0, "factors": {}}


@app.get("/forecast")
async def get_forecast():
    """Simple linear projection and scenario analysis"""
    history = DB.get_historical_range(365)
    if len(history) < 2:
        raise HTTPException(status_code=400, detail="Insufficient historical data")

    # Extract debt values
    debts = [float(d["debt"]) for d in history]
    daily_change = (debts[0] - debts[-1]) / len(debts) if len(debts) > 1 else 0

    current_debt = CURRENT_DATA.get("national_debt", debts[0])

    # Scenarios
    scenarios = {
        "current_path": {
            "description": "Continuation of current deficit trajectory",
            "multiplier": 1.0,
            "debt_in_1yr": current_debt + (daily_change * 365),
            "debt_in_5yr": current_debt + (daily_change * 365 * 5),
        },
        "austerity": {
            "description": "30% reduction in deficit growth",
            "multiplier": 0.7,
            "debt_in_1yr": current_debt + (daily_change * 365 * 0.7),
            "debt_in_5yr": current_debt + (daily_change * 365 * 5 * 0.7),
        },
        "stimulus": {
            "description": "30% increase in deficit spending",
            "multiplier": 1.3,
            "debt_in_1yr": current_debt + (daily_change * 365 * 1.3),
            "debt_in_5yr": current_debt + (daily_change * 365 * 5 * 1.3),
        },
    }

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "current_debt": current_debt,
        "daily_change": daily_change,
        "annual_change": daily_change * 365,
        "scenarios": scenarios,
    }


@app.get("/compare")
async def get_comparison():
    """US vs G7 debt comparison"""
    comparison = []
    for country, data in G7_DEBT_DATA.items():
        comparison.append(
            {
                "country": country,
                "total_debt": data["debt"],
                "debt_formatted": f"${data['debt']/1e12:.2f}T",
                "gdp": data["gdp"],
                "gdp_formatted": f"${data['gdp']/1e12:.2f}T",
                "population": data["population"],
                "debt_to_gdp": data["debt_to_gdp"],
                "debt_per_capita": data["debt"] / data["population"],
                "interest_as_pct_revenue": data["interest_as_pct_revenue"],
            }
        )

    return {"timestamp": datetime.utcnow().isoformat(), "countries": comparison}


@app.get("/alerts")
async def get_alerts():
    """Fiscal event alerts"""
    alerts = []

    pressure_index = CURRENT_DATA.get("fiscal_pressure_index", 0)
    if pressure_index > 80:
        alerts.append(
            {
                "level": "critical",
                "message": "Fiscal pressure index in critical zone",
                "action": "Monitor policy changes",
            }
        )

    interest_pct = CURRENT_DATA.get("interest_today", 0) * 365 / CURRENT_DATA.get("revenue", 1) * 100
    if interest_pct > 15:
        alerts.append(
            {
                "level": "warning",
                "message": f"Interest expense at {interest_pct:.1f}% of revenue",
                "action": "Track rate environment",
            }
        )

    unemployment = CURRENT_DATA.get("unemployment", 0)
    if unemployment > 5:
        alerts.append(
            {
                "level": "info",
                "message": f"Unemployment at {unemployment:.1f}%",
                "action": "Monitor employment data",
            }
        )

    return {"timestamp": datetime.utcnow().isoformat(), "alerts": alerts}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket for real-time debt counter"""
    await websocket.accept()
    try:
        while True:
            if not CURRENT_DATA:
                await asyncio.sleep(1)
                continue

            # Calculate per-second deficit rate
            daily_deficit = CURRENT_DATA.get("deficit", 0)
            per_second_deficit = daily_deficit / 86400

            current_debt = CURRENT_DATA.get("national_debt", 0)

            message = {
                "timestamp": datetime.utcnow().isoformat(),
                "debt": current_debt,
                "debt_formatted": f"${current_debt:,.0f}",
                "per_second_increase": per_second_deficit,
            }

            await websocket.send_json(message)
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


def get_regime_description(regime: str) -> str:
    """Get human-readable regime description"""
    descriptions = {
        "stable": "Fiscal metrics are within sustainable ranges. Interest burden manageable.",
        "elevated": "Growing fiscal pressures. Monitor deficit trajectory and interest rates.",
        "critical": "Significant fiscal stress. Policy action needed to stabilize metrics.",
        "crisis": "Severe fiscal imbalance. Immediate intervention required.",
    }
    return descriptions.get(regime, "Unknown regime")


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the dashboard"""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        return dashboard_path.read_text()
    return "<h1>Dashboard not found</h1>"


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8500)
