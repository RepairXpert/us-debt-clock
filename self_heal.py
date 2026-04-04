"""
Self-Healing Monitor for US Debt Clock
Monitors API availability, data freshness, and system health
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import httpx
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PATTERNS_FILE = Path(__file__).parent / "patterns.jsonl"
HEALTH_LOG = Path(__file__).parent / "health.jsonl"
TREASURY_API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
FRED_API = "https://api.stlouisfed.org/fred"


class HealthMonitor:
    """Monitor system and API health"""

    def __init__(self):
        self.treasury_status = "unknown"
        self.fred_status = "unknown"
        self.last_data_update = None
        self.api_errors = []
        self.restart_count = 0

    async def check_treasury_api(self) -> bool:
        """Check if Treasury API is responding"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{TREASURY_API}/v1/accounting/od/debt_to_penny",
                    params={"page[size]": "1"},
                )
                self.treasury_status = "healthy" if response.status_code == 200 else "degraded"
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Treasury API error: {e}")
            self.treasury_status = "down"
            return False

    async def check_fred_api(self, fred_key: str) -> bool:
        """Check if FRED API is responding"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{FRED_API}/series/observations",
                    params={"series_id": "GDPA", "api_key": fred_key, "file_type": "json", "limit": 1},
                )
                self.fred_status = "healthy" if response.status_code == 200 else "degraded"
                return response.status_code == 200
        except Exception as e:
            logger.error(f"FRED API error: {e}")
            self.fred_status = "down"
            return False

    async def check_data_freshness(self) -> Dict[str, Any]:
        """Check if data is being updated regularly"""
        from data_collector import Database

        db = Database(Path(__file__).parent / "debt_clock.db")
        snapshot = db.get_latest_snapshot()

        if not snapshot:
            return {"status": "no_data", "age_hours": None}

        timestamp = datetime.fromisoformat(snapshot["timestamp"])
        age = datetime.utcnow() - timestamp
        age_hours = age.total_seconds() / 3600

        if age_hours > 24:
            return {"status": "stale", "age_hours": age_hours}
        elif age_hours > 2:
            return {"status": "degraded", "age_hours": age_hours}
        else:
            return {"status": "fresh", "age_hours": age_hours}

    def log_health(self, status: Dict[str, Any]):
        """Log health status"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
        }
        with open(HEALTH_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")

    async def run_health_check(self, fred_key: str) -> Dict[str, Any]:
        """Run complete health check"""
        treasury_ok = await self.check_treasury_api()
        fred_ok = await self.check_fred_api(fred_key)
        data_freshness = await self.check_data_freshness()

        status = {
            "treasury_api": self.treasury_status,
            "fred_api": self.fred_status,
            "data_freshness": data_freshness,
            "overall": "healthy"
            if (treasury_ok and fred_ok and data_freshness["status"] == "fresh")
            else "degraded",
        }

        self.log_health(status)
        return status


class RecoveryAgent:
    """Auto-recovery for common issues"""

    @staticmethod
    async def restart_api():
        """Restart the FastAPI server"""
        try:
            logger.info("Attempting API restart...")
            # Kill existing process
            subprocess.run(
                ["pkill", "-f", "python.*api.py"],
                capture_output=True,
            )
            await asyncio.sleep(2)

            # Start new process
            subprocess.Popen(
                ["python", str(Path(__file__).parent / "api.py")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("API restarted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to restart API: {e}")
            return False

    @staticmethod
    async def retry_data_collection():
        """Retry data collection from scratch"""
        try:
            from data_collector import DataCollector
            import os

            fred_key = os.getenv("FRED_KEY", "YOUR_FRED_KEY")
            logger.info("Retrying data collection...")
            collector = DataCollector(fred_key)
            result = await collector.collect_all()
            logger.info("Data collection retry successful")
            return True
        except Exception as e:
            logger.error(f"Data collection retry failed: {e}")
            return False


class PatternLearner:
    """Learn from health patterns for SAFLA integration"""

    @staticmethod
    def record_pattern(pattern_name: str, event: Dict[str, Any], confidence: float):
        """Record a learned pattern"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "pattern": pattern_name,
            "event": event,
            "confidence": confidence,
        }
        with open(PATTERNS_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

    @staticmethod
    def get_high_confidence_patterns(min_confidence: float = 0.85) -> List[Dict[str, Any]]:
        """Get patterns with high confidence for auto-recovery"""
        if not PATTERNS_FILE.exists():
            return []

        patterns = []
        with open(PATTERNS_FILE, "r") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record.get("confidence", 0) >= min_confidence:
                        patterns.append(record)
                except json.JSONDecodeError:
                    continue

        return patterns

    @staticmethod
    async def execute_recovery_for_pattern(pattern: Dict[str, Any]) -> bool:
        """Execute recovery based on learned pattern"""
        pattern_name = pattern.get("pattern", "")

        if pattern_name == "api_crash_recovery":
            return await RecoveryAgent.restart_api()
        elif pattern_name == "data_collection_retry":
            return await RecoveryAgent.retry_data_collection()

        return False


class MonitoringLoop:
    """Main monitoring loop"""

    def __init__(self, fred_key: str, interval_seconds: int = 300):
        self.fred_key = fred_key
        self.interval = interval_seconds
        self.monitor = HealthMonitor()
        self.learner = PatternLearner()

    async def run(self):
        """Run continuous monitoring"""
        logger.info(f"Starting health monitor (interval: {self.interval}s)")

        while True:
            try:
                status = await self.monitor.run_health_check(self.fred_key)
                logger.info(f"Health check: {status['overall']}")

                # Recovery logic
                if status["overall"] == "degraded":
                    await self._handle_degraded(status)

                # Pattern learning
                self._learn_from_status(status)

                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(self.interval)

    async def _handle_degraded(self, status: Dict[str, Any]):
        """Handle degraded status with recovery attempts"""
        logger.warning(f"Degraded status detected: {status}")

        # Try recovery based on learned patterns
        patterns = self.learner.get_high_confidence_patterns()
        for pattern in patterns:
            success = await self.learner.execute_recovery_for_pattern(pattern)
            if success:
                logger.info(f"Recovery successful using pattern: {pattern['pattern']}")
                return

        # Fallback: restart API
        if status.get("overall") == "degraded":
            await RecoveryAgent.retry_data_collection()
            await asyncio.sleep(5)
            await RecoveryAgent.restart_api()

    def _learn_from_status(self, status: Dict[str, Any]):
        """Learn patterns from health status"""
        # Pattern: data_collection_retry (if data is stale)
        if status.get("data_freshness", {}).get("status") == "stale":
            self.learner.record_pattern(
                "data_collection_retry",
                {"reason": "stale_data", "age_hours": status["data_freshness"].get("age_hours")},
                0.9,
            )

        # Pattern: api_restart (if APIs are down)
        if status.get("treasury_api") == "down" or status.get("fred_api") == "down":
            self.learner.record_pattern(
                "api_crash_recovery",
                {"treasury": status.get("treasury_api"), "fred": status.get("fred_api")},
                0.85,
            )


async def main():
    """Run monitor"""
    import os

    fred_key = os.getenv("FRED_KEY", "YOUR_FRED_KEY")
    monitor = MonitoringLoop(fred_key, interval_seconds=300)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
