"""
US Debt Clock Data Collector
Aggregates Treasury and FRED data, calculates fiscal metrics and regime classification
"""

import json
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import sqlite3
from pathlib import Path
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TREASURY_API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
FRED_API = "https://api.stlouisfed.org/fred"
FRED_KEY = "YOUR_FRED_KEY"  # Set via env var

DB_PATH = Path(__file__).parent / "debt_clock.db"


class TreasuryClient:
    """Fetch data from Treasury Fiscal Data API"""

    def __init__(self):
        self.base_url = TREASURY_API
        self.session = None

    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30)
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()

    async def get_national_debt(self) -> Optional[Dict[str, Any]]:
        """Get current national debt and daily statement"""
        try:
            url = f"{self.base_url}/v2/accounting/od/debt_to_penny"
            params = {"sort": "-record_date", "page[size]": "1"}
            resp = await self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                record = data["data"][0]
                return {
                    "debt": float(record.get("tot_pub_debt_out_amt", 0)),
                    "intraday_debt": float(
                        record.get("tot_pub_debt_out_amt", 0)
                    ),
                    "date": record.get("record_date"),
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching national debt: {e}")
            return None

    async def get_daily_statement(self) -> Optional[Dict[str, Any]]:
        """Get treasury receipts/outlays from Monthly Treasury Statement (MTS table 4/5)"""
        try:
            # MTS table 4 = receipts summary (record_type_cd='T' for totals)
            url = f"{self.base_url}/v1/accounting/mts/mts_table_4"
            params = {
                "sort": "-record_date",
                "page[size]": "1",
                "filter": "line_code_nbr:eq:830",  # Total receipts line
            }
            resp = await self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            total_revenue = 0
            total_outlays = 0
            date = None

            if data.get("data"):
                record = data["data"][0]
                date = record.get("record_date")
                total_revenue = float(record.get("current_fytd_net_rcpt_amt") or 0)

            # MTS table 5 = outlays summary
            url2 = f"{self.base_url}/v1/accounting/mts/mts_table_5"
            params2 = {
                "sort": "-record_date",
                "page[size]": "1",
                "filter": "line_code_nbr:eq:5690",  # Total outlays line
            }
            resp2 = await self.session.get(url2, params=params2)
            resp2.raise_for_status()
            data2 = resp2.json()

            if data2.get("data"):
                record2 = data2["data"][0]
                if not date:
                    date = record2.get("record_date")
                total_outlays = float(record2.get("current_fytd_net_outly_amt") or 0)

            if date:
                return {
                    "date": date,
                    "total_revenue": total_revenue,
                    "total_outlays": total_outlays,
                    "deficit": total_outlays - total_revenue,
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching treasury statement: {e}")
            return None

    async def get_interest_expense(self) -> Optional[Dict[str, Any]]:
        """Get average interest rates from Treasury"""
        try:
            url = f"{self.base_url}/v2/accounting/od/avg_interest_rates"
            params = {"sort": "-record_date", "page[size]": "1"}
            resp = await self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                record = data["data"][0]
                return {
                    "date": record.get("record_date"),
                    "interest_today": float(record.get("interest_expense_today", 0)),
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching interest expense: {e}")
            return None

    async def get_historical_debt(self, limit: int = 365) -> List[Dict[str, Any]]:
        """Get historical debt data"""
        try:
            url = f"{self.base_url}/v2/accounting/od/debt_to_penny"
            params = {"sort": "-record_date", "page[size]": min(limit, 10000)}
            resp = await self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "date": r.get("record_date"),
                    "debt": float(r.get("tot_pub_debt_out_amt", 0)),
                }
                for r in data.get("data", [])
            ]
        except Exception as e:
            logger.error(f"Error fetching historical debt: {e}")
            return []


class FredClient:
    """Fetch data from FRED API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = FRED_API
        self.session = None

    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30)
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()

    async def get_series(self, series_id: str, limit: int = 1) -> Optional[List[Dict]]:
        """Get FRED series data"""
        try:
            url = f"{self.base_url}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            }
            resp = await self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("observations", [])
        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return None

    async def get_gdp(self) -> Optional[float]:
        """Get nominal GDP (quarterly)"""
        data = await self.get_series("GDPA", limit=1)
        if data and data[0]["value"] != ".":
            return float(data[0]["value"]) * 1e9
        return None

    async def get_cpi(self) -> Optional[float]:
        """Get CPI (monthly)"""
        data = await self.get_series("CPIAUCSL", limit=1)
        if data and data[0]["value"] != ".":
            return float(data[0]["value"])
        return None

    async def get_unemployment(self) -> Optional[float]:
        """Get unemployment rate (monthly)"""
        data = await self.get_series("UNRATE", limit=1)
        if data and data[0]["value"] != ".":
            return float(data[0]["value"])
        return None

    async def get_fed_funds_rate(self) -> Optional[float]:
        """Get federal funds rate (daily)"""
        data = await self.get_series("FEDFUNDS", limit=1)
        if data and data[0]["value"] != ".":
            return float(data[0]["value"])
        return None

    async def get_10y_treasury_yield(self) -> Optional[float]:
        """Get 10-year treasury yield (daily)"""
        data = await self.get_series("DGS10", limit=1)
        if data and data[0]["value"] != ".":
            return float(data[0]["value"])
        return None

    async def get_m2_money_supply(self) -> Optional[float]:
        """Get M2 money supply (weekly)"""
        data = await self.get_series("M2", limit=1)
        if data and data[0]["value"] != ".":
            return float(data[0]["value"]) * 1e9
        return None


class Database:
    """SQLite database for caching"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS debt_snapshot (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                national_debt REAL,
                interest_today REAL,
                gdp REAL,
                cpi REAL,
                unemployment REAL,
                fed_funds_rate REAL,
                treasury_10y_yield REAL,
                m2_supply REAL
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_statements (
                id INTEGER PRIMARY KEY,
                date TEXT UNIQUE,
                revenue REAL,
                outlays REAL,
                deficit REAL
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS historical_debt (
                id INTEGER PRIMARY KEY,
                date TEXT UNIQUE,
                debt REAL
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fiscal_regimes (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                regime TEXT,
                pressure_index REAL,
                factors TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def save_snapshot(self, data: Dict[str, Any]):
        """Save current data snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO debt_snapshot
            (timestamp, national_debt, interest_today, gdp, cpi, unemployment,
             fed_funds_rate, treasury_10y_yield, m2_supply)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.utcnow().isoformat(),
                data.get("national_debt"),
                data.get("interest_today"),
                data.get("gdp"),
                data.get("cpi"),
                data.get("unemployment"),
                data.get("fed_funds_rate"),
                data.get("treasury_10y_yield"),
                data.get("m2_supply"),
            ),
        )
        conn.commit()
        conn.close()

    def save_daily_statement(self, date: str, revenue: float, outlays: float):
        """Save daily statement"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO daily_statements (date, revenue, outlays, deficit)
                VALUES (?, ?, ?, ?)
            """,
                (date, revenue, outlays, outlays - revenue),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving daily statement: {e}")
        finally:
            conn.close()

    def save_historical_debt(self, records: List[Dict[str, Any]]):
        """Save historical debt records"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for record in records:
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO historical_debt (date, debt)
                    VALUES (?, ?)
                """,
                    (record["date"], record["debt"]),
                )
            except Exception as e:
                logger.error(f"Error saving historical record: {e}")
        conn.commit()
        conn.close()

    def save_regime(self, regime: str, pressure_index: float, factors: Dict[str, Any]):
        """Save fiscal regime classification"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO fiscal_regimes (timestamp, regime, pressure_index, factors)
            VALUES (?, ?, ?, ?)
        """,
            (
                datetime.utcnow().isoformat(),
                regime,
                pressure_index,
                json.dumps(factors),
            ),
        )
        conn.commit()
        conn.close()

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get most recent data snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM debt_snapshot ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "timestamp": row[1],
                "national_debt": row[2],
                "interest_today": row[3],
                "gdp": row[4],
                "cpi": row[5],
                "unemployment": row[6],
                "fed_funds_rate": row[7],
                "treasury_10y_yield": row[8],
                "m2_supply": row[9],
            }
        return None

    def get_historical_range(
        self, days: int = 365
    ) -> List[Dict[str, Any]]:
        """Get historical data for a range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cutoff = datetime.utcnow() - timedelta(days=days)
        cursor.execute(
            """
            SELECT date, debt FROM historical_debt
            WHERE datetime(date) >= ?
            ORDER BY date ASC
        """,
            (cutoff.isoformat(),),
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"date": r[0], "debt": r[1]} for r in rows]

    def get_latest_regime(self) -> Optional[Dict[str, Any]]:
        """Get most recent fiscal regime classification"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT regime, pressure_index, factors FROM fiscal_regimes ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "regime": row[0],
                "pressure_index": row[1],
                "factors": json.loads(row[2]),
            }
        return None


class FiscalAnalyzer:
    """Calculate derived metrics and fiscal regimes"""

    @staticmethod
    def calculate_debt_to_gdp(national_debt: float, gdp: float) -> float:
        """Calculate debt-to-GDP ratio"""
        if gdp > 0:
            return (national_debt / gdp) * 100
        return 0

    @staticmethod
    def calculate_debt_per_capita(national_debt: float, population: float = 335e6) -> float:
        """Calculate debt per person"""
        if population > 0:
            return national_debt / population
        return 0

    @staticmethod
    def calculate_interest_as_revenue_pct(
        annual_interest: float, annual_revenue: float
    ) -> float:
        """Calculate interest expense as % of revenue"""
        if annual_revenue > 0:
            return (annual_interest / annual_revenue) * 100
        return 0

    @staticmethod
    def calculate_fiscal_pressure_index(
        debt_to_gdp: float,
        interest_as_pct_revenue: float,
        deficit_to_gdp: float,
        unemployment: float,
        fed_funds_rate: float,
        treasury_10y_yield: float,
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate composite fiscal pressure index (0-100)
        100 = critical pressure
        """
        factors = {}

        # Debt-to-GDP contribution (0-25 points, 100% ratio = 25 pts)
        debt_score = min(25, (debt_to_gdp / 120) * 25)
        factors["debt_to_gdp_score"] = debt_score

        # Interest as % revenue (0-25 points, 20% = 25 pts)
        interest_score = min(25, (interest_as_pct_revenue / 20) * 25)
        factors["interest_score"] = interest_score

        # Deficit to GDP (0-20 points, 10% deficit = 20 pts)
        deficit_score = min(20, (abs(deficit_to_gdp) / 10) * 20)
        factors["deficit_score"] = deficit_score

        # Labor market (0-15 points, 6%+ unemployment = 15 pts)
        unemployment_score = min(15, (unemployment / 6) * 15)
        factors["unemployment_score"] = unemployment_score

        # Rate environment (0-15 points, high rates = pressure)
        rate_score = (fed_funds_rate + treasury_10y_yield / 2) * 1.5
        rate_score = min(15, max(0, rate_score))
        factors["rate_score"] = rate_score

        total = debt_score + interest_score + deficit_score + unemployment_score + rate_score
        factors["total_score"] = total

        return total, factors

    @staticmethod
    def classify_regime(pressure_index: float) -> str:
        """Classify fiscal regime based on pressure index"""
        if pressure_index < 40:
            return "stable"
        elif pressure_index < 60:
            return "elevated"
        elif pressure_index < 80:
            return "critical"
        else:
            return "crisis"


class DataCollector:
    """Main collector orchestration"""

    def __init__(self, fred_key: str):
        self.db = Database(DB_PATH)
        self.fred_key = fred_key

    async def collect_all(self) -> Dict[str, Any]:
        """Collect all data from APIs"""
        data = {}

        async with TreasuryClient() as treasury:
            debt = await treasury.get_national_debt()
            if debt:
                data["national_debt"] = debt["debt"]
                logger.info(f"National debt: ${debt['debt']:,.0f}")

            stmt = await treasury.get_daily_statement()
            if stmt:
                data["revenue"] = stmt["total_revenue"]
                data["outlays"] = stmt["total_outlays"]
                data["deficit"] = stmt["deficit"]
                self.db.save_daily_statement(stmt["date"], stmt["total_revenue"], stmt["total_outlays"])

            interest = await treasury.get_interest_expense()
            if interest:
                data["interest_today"] = interest["interest_today"]

            hist = await treasury.get_historical_debt(limit=5000)
            if hist:
                self.db.save_historical_debt(hist)

        async with FredClient(self.fred_key) as fred:
            data["gdp"] = await fred.get_gdp()
            data["cpi"] = await fred.get_cpi()
            data["unemployment"] = await fred.get_unemployment()
            data["fed_funds_rate"] = await fred.get_fed_funds_rate()
            data["treasury_10y_yield"] = await fred.get_10y_treasury_yield()
            data["m2_supply"] = await fred.get_m2_money_supply()

        # Calculate derived metrics
        if data.get("national_debt") and data.get("gdp"):
            data["debt_to_gdp"] = FiscalAnalyzer.calculate_debt_to_gdp(
                data["national_debt"], data["gdp"]
            )
            data["debt_per_capita"] = FiscalAnalyzer.calculate_debt_per_capita(
                data["national_debt"]
            )

        # Save snapshot
        self.db.save_snapshot(data)

        # Calculate regime
        if all(
            k in data
            for k in [
                "debt_to_gdp",
                "interest_today",
                "revenue",
                "unemployment",
                "fed_funds_rate",
                "treasury_10y_yield",
            ]
        ):
            # Annualize interest (rough estimate)
            annual_interest = data["interest_today"] * 365
            deficit_to_gdp = (data.get("deficit", 0) * 365 / data.get("gdp", 1)) * 100

            pressure, factors = FiscalAnalyzer.calculate_fiscal_pressure_index(
                data["debt_to_gdp"],
                FiscalAnalyzer.calculate_interest_as_revenue_pct(annual_interest, data["revenue"]),
                deficit_to_gdp,
                data["unemployment"],
                data["fed_funds_rate"],
                data["treasury_10y_yield"],
            )
            regime = FiscalAnalyzer.classify_regime(pressure)
            data["fiscal_pressure_index"] = pressure
            data["fiscal_regime"] = regime
            data["pressure_factors"] = factors

            self.db.save_regime(regime, pressure, factors)

        return data


async def main():
    """Run collector once"""
    fred_key = "YOUR_FRED_KEY"  # Set via env
    collector = DataCollector(fred_key)
    result = await collector.collect_all()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
