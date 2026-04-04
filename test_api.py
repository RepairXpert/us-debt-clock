"""
Test suite for US Debt Clock API
"""

import asyncio
import json
from pathlib import Path
from data_collector import (
    DataCollector,
    Database,
    FiscalAnalyzer,
    TreasuryClient,
    FredClient,
)
from alerts import AlertMonitor, DebtCeilingMonitor, FiscalEventCalendar


async def test_treasury_client():
    """Test Treasury API connectivity"""
    print("\n=== Testing Treasury API ===")
    async with TreasuryClient() as client:
        debt = await client.get_national_debt()
        if debt:
            print(f"[OK] National Debt: ${debt['debt']:,.0f}")
        else:
            print("[FAIL] Failed to fetch national debt")

        stmt = await client.get_daily_statement()
        if stmt:
            print(f"[OK] Daily Revenue: ${stmt['total_revenue']:,.0f}")
            print(f"[OK] Daily Outlays: ${stmt['total_outlays']:,.0f}")
        else:
            print("[FAIL] Failed to fetch daily statement")


async def test_fred_client():
    """Test FRED API connectivity"""
    print("\n=== Testing FRED API ===")
    fred_key = "YOUR_FRED_KEY"  # Replace with actual key

    async with FredClient(fred_key) as client:
        gdp = await client.get_gdp()
        if gdp:
            print(f"[OK] GDP: ${gdp/1e12:.2f}T")
        else:
            print("[FAIL] Failed to fetch GDP")

        unemployment = await client.get_unemployment()
        if unemployment:
            print(f"[OK] Unemployment: {unemployment:.1f}%")
        else:
            print("[FAIL] Failed to fetch unemployment")


def test_fiscal_analyzer():
    """Test fiscal calculations"""
    print("\n=== Testing Fiscal Analyzer ===")

    # Test debt-to-GDP
    debt_to_gdp = FiscalAnalyzer.calculate_debt_to_gdp(33.7e12, 27.4e12)
    print(f"[OK] Debt-to-GDP: {debt_to_gdp:.1f}%")

    # Test debt per capita
    debt_per_capita = FiscalAnalyzer.calculate_debt_per_capita(33.7e12)
    print(f"[OK] Debt Per Capita: ${debt_per_capita:,.0f}")

    # Test interest calculation
    interest_pct = FiscalAnalyzer.calculate_interest_as_revenue_pct(659e9, 4100e9)
    print(f"[OK] Interest as % of Revenue: {interest_pct:.1f}%")

    # Test fiscal pressure
    pressure, factors = FiscalAnalyzer.calculate_fiscal_pressure_index(
        debt_to_gdp=123.1,
        interest_as_pct_revenue=18.2,
        deficit_to_gdp=5.5,
        unemployment=4.2,
        fed_funds_rate=5.5,
        treasury_10y_yield=4.2,
    )
    print(f"[OK] Fiscal Pressure Index: {pressure:.1f}/100")
    print(f"  Regime: {FiscalAnalyzer.classify_regime(pressure)}")


def test_database():
    """Test database operations"""
    print("\n=== Testing Database ===")

    db = Database(Path(__file__).parent / "test_debt_clock.db")

    # Save snapshot
    test_data = {
        "national_debt": 33.7e12,
        "interest_today": 1.8e9,
        "gdp": 27.4e12,
        "cpi": 315.0,
        "unemployment": 4.2,
        "fed_funds_rate": 5.5,
        "treasury_10y_yield": 4.2,
        "m2_supply": 20e12,
    }
    db.save_snapshot(test_data)
    print("[OK] Snapshot saved")

    # Retrieve latest
    snapshot = db.get_latest_snapshot()
    if snapshot:
        print(f"[OK] Retrieved snapshot: Debt=${snapshot['national_debt']:,.0f}")
    else:
        print("[FAIL] Failed to retrieve snapshot")

    # Save daily statement
    db.save_daily_statement("2026-04-04", 20e9, 25e9)
    print("[OK] Daily statement saved")

    # Save regime
    db.save_regime("elevated", 55.0, {"debt_score": 20})
    print("[OK] Regime saved")

    regime = db.get_latest_regime()
    if regime:
        print(f"[OK] Retrieved regime: {regime['regime']} ({regime['pressure_index']:.0f}/100)")

    # Cleanup
    Path("test_debt_clock.db").unlink(missing_ok=True)


async def test_alerts():
    """Test alert generation"""
    print("\n=== Testing Alerts ===")

    monitor = AlertMonitor()

    # Mock data
    current_data = {
        "fiscal_pressure_index": 75,
        "interest_today": 1.8e9,
        "revenue": 20e9,
        "unemployment": 4.2,
        "deficit": 5e9,
        "fed_funds_rate": 5.5,
        "treasury_10y_yield": 4.2,
        "debt_to_gdp": 125,
        "national_debt": 35.8e12,
    }

    alerts = await monitor.check_fiscal_events(current_data)
    print(f"[OK] Generated {len(alerts)} alerts")
    for alert in alerts:
        print(f"  - {alert['title']}: {alert['level'].upper()}")

    # Test debt ceiling
    ceiling_alert = await DebtCeilingMonitor().check_debt_ceiling(35.9e12)
    if ceiling_alert:
        print(f"[OK] Debt ceiling alert: {ceiling_alert['message']}")

    # Test events calendar
    events = FiscalEventCalendar.get_upcoming_events(days_ahead=90)
    print(f"[OK] Upcoming events: {len(events)}")
    for event in events[:3]:
        print(f"  - {event['event']} ({event['days_until']} days)")


def test_scenarios():
    """Test forecast scenarios"""
    print("\n=== Testing Forecasts ===")

    current_debt = 33.7e12
    daily_change = 50e9  # $50B per day

    # Current path
    debt_1yr = current_debt + (daily_change * 365)
    debt_5yr = current_debt + (daily_change * 365 * 5)
    print(f"[OK] Current Path (1yr): ${debt_1yr/1e12:.2f}T")
    print(f"[OK] Current Path (5yr): ${debt_5yr/1e12:.2f}T")

    # Austerity
    debt_1yr_austerity = current_debt + (daily_change * 365 * 0.7)
    print(f"[OK] Austerity (1yr): ${debt_1yr_austerity/1e12:.2f}T")

    # Stimulus
    debt_1yr_stimulus = current_debt + (daily_change * 365 * 1.3)
    print(f"[OK] Stimulus (1yr): ${debt_1yr_stimulus/1e12:.2f}T")


async def main():
    """Run all tests"""
    print("=" * 50)
    print("US Debt Clock - Test Suite")
    print("=" * 50)

    try:
        # API tests
        await test_treasury_client()
        await test_fred_client()

        # Calculation tests
        test_fiscal_analyzer()
        test_database()
        await test_alerts()
        test_scenarios()

        print("\n" + "=" * 50)
        print("[OK] All tests completed")
        print("=" * 50)

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
