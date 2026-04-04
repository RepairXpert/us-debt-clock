"""
Fiscal Event Alert System
Monitors for significant fiscal events and sends notifications
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertMonitor:
    """Monitor and dispatch fiscal alerts"""

    def __init__(self, telegram_token: Optional[str] = None, discord_webhook: Optional[str] = None):
        self.telegram_token = telegram_token
        self.discord_webhook = discord_webhook
        self.alert_history = Path(__file__).parent / "alerts_history.jsonl"

    def log_alert(self, alert: Dict[str, Any]):
        """Log alert to history"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "alert": alert,
        }
        with open(self.alert_history, "a") as f:
            f.write(json.dumps(record) + "\n")

    async def check_fiscal_events(self, current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for fiscal events and generate alerts"""
        alerts = []

        # Fiscal Pressure Alert
        pressure_index = current_data.get("fiscal_pressure_index", 0)
        if pressure_index > 80:
            alert = {
                "type": "fiscal_pressure_critical",
                "level": "critical",
                "title": "Critical Fiscal Pressure",
                "message": f"Fiscal pressure index at {pressure_index:.0f}/100 - CRITICAL zone",
                "action": "Monitor policy changes and market responses",
                "timestamp": datetime.utcnow().isoformat(),
            }
            alerts.append(alert)
            self.log_alert(alert)
            await self.send_alert(alert)
        elif pressure_index > 60:
            alert = {
                "type": "fiscal_pressure_elevated",
                "level": "warning",
                "title": "Elevated Fiscal Pressure",
                "message": f"Fiscal pressure index at {pressure_index:.0f}/100 - ELEVATED zone",
                "action": "Track deficit trajectory and interest rates",
                "timestamp": datetime.utcnow().isoformat(),
            }
            alerts.append(alert)

        # Interest Burden Alert
        interest_pct = current_data.get("interest_today", 0) * 365 / max(1, current_data.get("revenue", 1)) * 100
        if interest_pct > 15:
            alert = {
                "type": "interest_burden_high",
                "level": "warning",
                "title": "High Interest Burden",
                "message": f"Interest expense at {interest_pct:.1f}% of federal revenue",
                "action": "Track rate environment and debt service impacts",
                "timestamp": datetime.utcnow().isoformat(),
            }
            alerts.append(alert)
            self.log_alert(alert)
            await self.send_alert(alert)

        # Unemployment Alert
        unemployment = current_data.get("unemployment", 0)
        if unemployment > 5:
            alert = {
                "type": "unemployment_elevated",
                "level": "info",
                "title": "Unemployment Elevated",
                "message": f"Unemployment rate at {unemployment:.1f}%",
                "action": "Monitor employment trends and labor market health",
                "timestamp": datetime.utcnow().isoformat(),
            }
            alerts.append(alert)

        # Deficit Alert
        daily_deficit = current_data.get("deficit", 0)
        if daily_deficit > 0 and daily_deficit > 5e9:  # More than $5B daily deficit
            alert = {
                "type": "deficit_expanding",
                "level": "warning",
                "title": "Large Daily Deficit",
                "message": f"Daily deficit: ${daily_deficit/1e9:.2f}B - Annualized: ${daily_deficit*365/1e9:.0f}B",
                "action": "Monitor revenue collection and spending patterns",
                "timestamp": datetime.utcnow().isoformat(),
            }
            alerts.append(alert)

        # Rate Environment Alert
        fed_funds = current_data.get("fed_funds_rate", 0)
        treasury_10y = current_data.get("treasury_10y_yield", 0)
        if fed_funds > 5 and treasury_10y > 4.5:
            alert = {
                "type": "rates_elevated",
                "level": "warning",
                "title": "Elevated Rate Environment",
                "message": f"Fed funds: {fed_funds:.2f}%, 10Y yield: {treasury_10y:.2f}% - Higher debt service costs",
                "action": "Monitor refinancing needs and debt rollover",
                "timestamp": datetime.utcnow().isoformat(),
            }
            alerts.append(alert)

        # Debt-to-GDP Alert
        debt_to_gdp = current_data.get("debt_to_gdp", 0)
        if debt_to_gdp > 120:
            alert = {
                "type": "debt_to_gdp_high",
                "level": "critical",
                "title": "Debt-to-GDP Ratio Elevated",
                "message": f"Debt-to-GDP ratio: {debt_to_gdp:.1f}% - Above sustainable levels",
                "action": "Fiscal consolidation needed to prevent spiral",
                "timestamp": datetime.utcnow().isoformat(),
            }
            alerts.append(alert)

        return alerts

    async def send_alert(self, alert: Dict[str, Any]):
        """Send alert to notification channels"""
        if self.telegram_token:
            await self._send_telegram(alert)
        if self.discord_webhook:
            await self._send_discord(alert)

    async def _send_telegram(self, alert: Dict[str, Any]):
        """Send alert via Telegram"""
        try:
            message = f"""
🚨 *{alert['title']}*

*Level:* {alert['level'].upper()}
*Message:* {alert['message']}
*Action:* {alert['action']}

`{alert['timestamp']}`
            """

            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                    json={
                        "chat_id": -1002000000000,  # Replace with channel ID
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                )
            logger.info(f"Telegram alert sent: {alert['type']}")
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")

    async def _send_discord(self, alert: Dict[str, Any]):
        """Send alert via Discord"""
        try:
            color_map = {
                "critical": 0xff0000,
                "warning": 0xffaa00,
                "info": 0x0099ff,
            }

            embed = {
                "title": alert["title"],
                "description": alert["message"],
                "color": color_map.get(alert["level"], 0x0099ff),
                "fields": [
                    {"name": "Action", "value": alert["action"], "inline": False},
                    {"name": "Timestamp", "value": alert["timestamp"], "inline": False},
                ],
            }

            async with httpx.AsyncClient() as client:
                await client.post(
                    self.discord_webhook,
                    json={"embeds": [embed]},
                )
            logger.info(f"Discord alert sent: {alert['type']}")
        except Exception as e:
            logger.error(f"Error sending Discord alert: {e}")


class DebtCeilingMonitor:
    """Monitor debt ceiling proximity"""

    # Debt ceiling milestones (updated as of 2026)
    CURRENT_CEILING = 36.2e12  # $36.2T as of 2026

    async def check_debt_ceiling(self, national_debt: float) -> Optional[Dict[str, Any]]:
        """Check proximity to debt ceiling"""
        remaining = self.CURRENT_CEILING - national_debt
        pct_of_ceiling = (national_debt / self.CURRENT_CEILING) * 100

        if pct_of_ceiling > 97:
            return {
                "type": "debt_ceiling_critical",
                "level": "critical",
                "title": "Debt Ceiling Critical",
                "message": f"At {pct_of_ceiling:.1f}% of ceiling (${remaining/1e9:.0f}B remaining)",
                "action": "Congress likely to raise ceiling soon",
                "timestamp": datetime.utcnow().isoformat(),
            }
        elif pct_of_ceiling > 95:
            return {
                "type": "debt_ceiling_warning",
                "level": "warning",
                "title": "Approaching Debt Ceiling",
                "message": f"At {pct_of_ceiling:.1f}% of ceiling (${remaining/1e9:.0f}B remaining)",
                "action": "Prepare for ceiling negotiation period",
                "timestamp": datetime.utcnow().isoformat(),
            }
        return None


class FiscalEventCalendar:
    """Track important fiscal events and milestones"""

    UPCOMING_EVENTS = [
        {"date": "2026-04-15", "event": "Tax Filing Deadline", "impact": "Large revenue spike"},
        {"date": "2026-05-15", "event": "FOMC Meeting", "impact": "Potential rate decision"},
        {"date": "2026-06-15", "event": "Treasury Auction", "impact": "Debt refinancing"},
        {
            "date": "2026-07-04",
            "event": "Q2 GDP Report",
            "impact": "Economic growth measure",
        },
    ]

    @staticmethod
    def get_upcoming_events(days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Get upcoming fiscal events"""
        today = datetime.utcnow().date()
        cutoff = today + timedelta(days=days_ahead)

        upcoming = []
        for event in FiscalEventCalendar.UPCOMING_EVENTS:
            event_date = datetime.fromisoformat(event["date"]).date()
            if today <= event_date <= cutoff:
                days_until = (event_date - today).days
                upcoming.append(
                    {
                        "date": event["date"],
                        "event": event["event"],
                        "impact": event["impact"],
                        "days_until": days_until,
                    }
                )

        return sorted(upcoming, key=lambda x: x["days_until"])


async def main():
    """Test alert system"""
    monitor = AlertMonitor()

    # Mock current data
    current_data = {
        "fiscal_pressure_index": 75,
        "interest_today": 1.5e9,
        "revenue": 3e10,
        "unemployment": 4.2,
        "deficit": 5e9,
        "fed_funds_rate": 5.5,
        "treasury_10y_yield": 4.2,
        "debt_to_gdp": 125,
        "national_debt": 35.8e12,
    }

    alerts = await monitor.check_fiscal_events(current_data)
    print(f"Generated {len(alerts)} alerts:")
    for alert in alerts:
        print(f"  - {alert['title']}: {alert['message']}")

    # Check debt ceiling
    ceiling_alert = await DebtCeilingMonitor().check_debt_ceiling(35.8e12)
    if ceiling_alert:
        print(f"\nDebt ceiling alert: {ceiling_alert['message']}")

    # Upcoming events
    events = FiscalEventCalendar.get_upcoming_events()
    print(f"\nUpcoming events: {len(events)}")
    for event in events:
        print(f"  - {event['event']} ({event['days_until']} days): {event['impact']}")


if __name__ == "__main__":
    asyncio.run(main())
