# US Debt Clock

Real-time US national debt tracking with fiscal intelligence, regime classification, and policy forecasting.

## Features

- **Live Debt Counter**: Per-second debt increase based on actual deficit rate
- **Key Metrics**: Debt-to-GDP, debt per capita, interest expense, unemployment
- **Fiscal Pressure Index**: Composite 0-100 score indicating fiscal stress level
- **Regime Classification**: Stable → Elevated → Critical → Crisis
- **Historical Charts**: 1Y, 5Y, 10Y trend analysis
- **G7 Comparison**: US debt metrics vs other developed nations
- **Scenario Forecasting**: Current path, austerity, stimulus projections
- **Alert System**: Fiscal event monitoring and notifications
- **Self-Healing**: Auto-recovery from API failures and data staleness
- **Dark Theme Dashboard**: Professional, responsive UI

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           FastAPI Backend (port 8500)                │
├─────────────────────────────────────────────────────┤
│  api.py          - REST endpoints + WebSocket       │
│  data_collector.py - Treasury + FRED data sources   │
│  alerts.py       - Fiscal event monitoring          │
│  self_heal.py    - Health checks & auto-recovery    │
│  debt_clock.db   - SQLite cache                     │
└─────────────────────────────────────────────────────┘
          ↓                    ↓
    Treasury API         FRED API
  (daily updates)      (macro data)
```

## Data Sources

### Treasury Fiscal Data API
- **National Debt**: Real-time debt-to-penny
- **Daily Statements**: Revenue, outlays, deficit
- **Interest Expense**: Daily interest paid
- **Free, no auth required**

### FRED (Federal Reserve Economic Data)
- GDP (quarterly)
- CPI (monthly)
- Unemployment Rate
- Federal Funds Rate
- 10-Year Treasury Yield
- M2 Money Supply
- **Free API key from** https://fred.stlouisfed.org

## Setup

### 1. Get API Keys

```bash
# FRED API (free, takes 1 minute)
# Visit: https://fred.stlouisfed.org/docs/api/api_key.html
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your FRED_KEY
```

### 4. Run Locally

```bash
# Start API server
python api.py

# In another terminal: start monitor
python self_heal.py
```

Visit: http://localhost:8500

### 5. Deploy to Render

```bash
# Create new Web Service on Render.com
# Repository: point to this directory
# Build: pip install -r requirements.txt
# Start: python api.py
# Add environment variables from .env
```

## API Endpoints

### GET `/health`
Health check with last update time and data status.

### GET `/current`
Current snapshot with all metrics:
- National debt
- Debt per capita
- Debt-to-GDP ratio
- Annual deficit
- Interest expense
- Fiscal pressure index
- Regime classification

### GET `/history?metric=debt&period=1y`
Historical data for charting.

**Periods**: `1y`, `5y`, `10y`, `max`

### GET `/regime`
Current fiscal pressure regime with explanation.

### GET `/forecast`
Debt projections for 3 scenarios:
- Current path (continuation)
- Austerity (30% deficit reduction)
- Stimulus (30% deficit increase)

### GET `/compare`
G7 debt comparison (US, Japan, Italy, France, UK, Germany, Canada).

### GET `/alerts`
Current active fiscal alerts and recommended actions.

### WebSocket `/ws/live`
Real-time debt counter updates (per-second changes).

## Fiscal Pressure Index

Composite score 0-100 combining:
- **Debt-to-GDP** (0-25 pts): Higher debt = more pressure
- **Interest Burden** (0-25 pts): Interest as % of revenue
- **Deficit-to-GDP** (0-20 pts): Annual deficit relative to economy
- **Unemployment** (0-15 pts): Labor market stress
- **Rate Environment** (0-15 pts): Fed funds + 10Y yield

**Regime Thresholds**:
- 0-40: **Stable** - Sustainable path
- 40-60: **Elevated** - Monitor closely
- 60-80: **Critical** - Policy action needed
- 80-100: **Crisis** - Severe imbalance

## Alert Types

- **Fiscal Pressure Critical**: Index > 80
- **Interest Burden High**: Interest > 15% of revenue
- **Unemployment Elevated**: Rate > 5%
- **Deficit Expanding**: Daily deficit > $5B
- **Rates Elevated**: Fed funds > 5%, 10Y > 4.5%
- **Debt-to-GDP High**: Ratio > 120%
- **Debt Ceiling Critical**: At 97%+ of ceiling

## Notifications

### Telegram
Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL_ID` in .env to receive bot alerts in Telegram.

### Discord
Set `DISCORD_WEBHOOK_URL` in .env to receive rich embeds in Discord channel.

### Email (Optional)
Set `RESEND_API_KEY` for email alerts via Resend.

## Self-Healing Features

### Health Checks
- Treasury API connectivity (5min interval)
- FRED API connectivity
- Data freshness (alert if > 2 hours old)

### Auto-Recovery
- Retry data collection on API failures
- Fallback to cached data
- Auto-restart on crash
- Pattern-based recovery learning

### Pattern Learning
Logs all health events to `patterns.jsonl` for SAFLA integration:
- API crash patterns
- Data staleness patterns
- Recovery success rates
- Incident correlations

## Deployment

### Render.com (Recommended)

1. Connect GitHub repo
2. Create new Web Service
3. Set environment variables
4. Deploy

### Docker

```bash
# Build
docker build -t debt-clock .

# Run
docker run -p 8500:8500 \
  -e FRED_KEY=your_key \
  -v $(pwd)/debt_clock.db:/app/debt_clock.db \
  debt-clock

# Or with Compose
docker-compose up
```

## Premium Features (Stripe)

**Free Tier** shows:
- Current snapshot
- Basic metrics
- Historical charts (1Y only)
- Comparison table

**Premium ($9/mo consumer, $49/mo analyst)** adds:
- Advanced scenario modeling
- 10+ year trends
- Custom alerts
- API access
- Policy impact analysis

## Revenue Model

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | Snapshot, charts, comparison |
| Consumer | $9/mo | Advanced trends, 5Y+ history |
| Analyst | $49/mo | Full API, custom alerts, exports |

**Projection**:
- 100 free users → 5% conversion (5 $9/mo) = $45/mo
- Target: 50 analyst users = $2,450/mo

## Integration Points

### CryptoTradingAgent
Fiscal pressure signals feed into regime detection for crypto market correlation analysis.

### Crucix
Economic indicators available as OSINT source alongside geopolitical/market data.

### RepairXpert
Monitor economic conditions for demand forecasting (recessions drive industrial automation ROI).

## Monitoring Dashboard

### Local Metrics
- API response times
- Data collection duration
- Cache hit rates
- Alert dispatch success

### Health Log
All events logged to `health.jsonl`:
```json
{
  "timestamp": "2026-04-04T15:30:00",
  "status": {
    "treasury_api": "healthy",
    "fred_api": "healthy",
    "data_freshness": {"status": "fresh", "age_hours": 0.5},
    "overall": "healthy"
  }
}
```

### Patterns Log
All learned patterns in `patterns.jsonl` for SAFLA analysis.

## Error Handling

### API Down
- System falls back to cached data
- Alerts escalate after 2 hours stale
- Auto-retry with exponential backoff

### Data Collection Timeout
- Logs error to health.jsonl
- Triggers recovery pattern
- Notifies via alerts system

### WebSocket Disconnection
- Client auto-reconnects (5s interval)
- Browser handles gracefully

## Performance

- **API Response**: < 100ms (cached)
- **WebSocket Update**: 1/second
- **Data Collection**: ~5 minutes (hourly refresh)
- **Dashboard Load**: < 500ms

## Troubleshooting

### API not responding
```bash
# Check process
ps aux | grep api.py

# Restart
pkill -f "python.*api.py"
python api.py
```

### Data stale
```bash
# Check latest snapshot
sqlite3 debt_clock.db "SELECT timestamp FROM debt_snapshot ORDER BY id DESC LIMIT 1;"

# Force collection
python -c "import asyncio; from data_collector import *; asyncio.run(DataCollector('YOUR_KEY').collect_all())"
```

### FRED API errors
```bash
# Verify key
curl "https://api.stlouisfed.org/fred/series/GDPA?api_key=YOUR_KEY&file_type=json"

# Check rate limits (120 calls/min per key)
```

## Next Steps

1. **Deploy to Render** ($7/mo, free tier option)
2. **Collect 100 free users** (social media, HN, Twitter)
3. **Convert 5% to premium** ($45/mo MRR)
4. **Scale to 50 analyst users** ($2,450/mo)
5. **B2B corporate accounts** (policy shops, investment firms)

## License

MIT - Build on it, fork it, sell it.

## Questions?

Check health status: `curl http://localhost:8500/health`

View patterns: `tail -f patterns.jsonl`

Check alerts: `tail -f alerts_history.jsonl`
