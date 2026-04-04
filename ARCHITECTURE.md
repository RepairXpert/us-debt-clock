# US Debt Clock - Architecture & Design

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                             │
│  dashboard.html - Dark theme, real-time debt counter, charts     │
│  WebSocket connection for live updates                           │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP/WebSocket
┌──────────────────────▼──────────────────────────────────────────┐
│              FastAPI Backend (Python 3.11+)                       │
├─────────────────────────────────────────────────────────────────┤
│  api.py - REST endpoints + WebSocket handler                     │
│  ├─ /current - Snapshot of all metrics                           │
│  ├─ /history - Historical data for charting                      │
│  ├─ /regime - Fiscal pressure classification                     │
│  ├─ /forecast - Scenario projections                             │
│  ├─ /compare - G7 comparison data                                │
│  ├─ /alerts - Active fiscal alerts                               │
│  ├─ /health - System health check                                │
│  └─ /ws/live - WebSocket live debt counter                       │
└────────┬──────────────┬──────────────┬──────────────────────────┘
         │              │              │
    ┌────▼──┐      ┌────▼──┐      ┌────▼──────┐
    │ Data  │      │Alerts │      │ Self-Heal │
    │Collect│      │ Monit │      │  Monitor  │
    └────┬──┘      └────┬──┘      └────┬──────┘
         │              │              │
   ┌─────▼──────────────▼──────────────▼──────┐
   │        SQLite Database (debt_clock.db)   │
   ├──────────────────────────────────────────┤
   │ • debt_snapshot - Current metrics        │
   │ • daily_statements - Revenue/outlays     │
   │ • historical_debt - 20+ years trends     │
   │ • fiscal_regimes - Classification log    │
   │ • health.jsonl - System events           │
   │ • patterns.jsonl - Learned patterns      │
   │ • alerts_history.jsonl - Alert log       │
   └──────────────────────────────────────────┘
         │                    │
      ┌──▼──────────┐    ┌────▼──────────┐
      │ Treasury    │    │ FRED API      │
      │ Fiscal Data │    │ (Federal Res) │
      │ API (free)  │    │ (free key)    │
      └─────────────┘    └───────────────┘
```

## Components

### 1. Frontend (dashboard.html)

**Purpose**: Consumer-facing real-time debt tracking interface

**Features**:
- Live counter with per-second deficit calculation
- 6 metric cards (debt per capita, debt-to-GDP, deficit, etc.)
- Fiscal Pressure Gauge (0-100, color-coded)
- Historical charts (Chart.js)
- G7 comparison table
- Scenario forecasts
- Fiscal alerts
- Dark theme, mobile responsive
- Premium CTA banner

**Technology**:
- Vanilla HTML/CSS/JavaScript (no build step)
- Chart.js for visualizations
- WebSocket for live updates
- Local API calls

**Performance**:
- < 500ms page load
- < 100ms API responses (cached)
- 1/second WebSocket updates
- ~2MB dashboard + Chart.js library

---

### 2. Backend - data_collector.py

**Purpose**: Fetch and aggregate fiscal data from Treasury and FRED APIs

**Classes**:

#### TreasuryClient
Connects to Treasury Fiscal Data API (free, no auth):
- `get_national_debt()` - Real-time debt-to-penny
- `get_daily_statement()` - Revenue, outlays, deficit
- `get_interest_expense()` - Daily interest paid
- `get_historical_debt()` - 20+ year trend data

#### FredClient
Connects to Federal Reserve Economic Data API (free key):
- `get_gdp()` - Quarterly nominal GDP
- `get_cpi()` - Monthly inflation
- `get_unemployment()` - Monthly jobless rate
- `get_fed_funds_rate()` - Current short rate
- `get_10y_treasury_yield()` - Long-term rates
- `get_m2_money_supply()` - Monetary aggregate

#### Database
SQLite wrapper for caching:
- `save_snapshot()` - Current metrics
- `save_daily_statement()` - Revenue/outlays tracking
- `save_historical_debt()` - Long-term trends
- `save_regime()` - Fiscal classification log
- `get_latest_snapshot()` - Most recent data
- `get_historical_range()` - Period queries

#### FiscalAnalyzer
Calculations for derived metrics:
- `calculate_debt_to_gdp()` - Sustainability metric
- `calculate_debt_per_capita()` - Per-person burden
- `calculate_interest_as_revenue_pct()` - Interest burden
- `calculate_fiscal_pressure_index()` - Composite 0-100 score
- `classify_regime()` - Stable/Elevated/Critical/Crisis

#### DataCollector
Orchestration:
- `collect_all()` - Async fetch from both APIs
- Calculates all metrics in one pass
- Saves to database
- Classifies regime

**Update Cycle**:
- Runs at startup + every hour
- Debt data refreshed hourly
- Macro data refreshed daily (daily statements, FRED weekly)
- Graceful degradation on API failures

---

### 3. Backend - api.py

**Purpose**: REST API + WebSocket server for frontend consumption

**Endpoints**:

| Method | Endpoint | Response |
|--------|----------|----------|
| GET | `/health` | API + data status |
| GET | `/current` | All current metrics |
| GET | `/history?metric=debt&period=1y` | Historical time series |
| GET | `/regime` | Fiscal regime + classification |
| GET | `/forecast` | 3 scenarios (1yr + 5yr projections) |
| GET | `/compare` | G7 debt comparison |
| GET | `/alerts` | Active fiscal alerts |
| WS | `/ws/live` | Real-time debt counter |
| GET | `/` | Dashboard HTML |

**Key Functions**:

- `startup()` - Initialize data, start background collection
- `update_data()` - Background task, refresh hourly
- `get_current()` - Combine database + real-time calculations
- `get_forecast()` - Linear projection + scenarios
- `websocket_live()` - 1Hz debt counter stream

**Architecture**:
- CORS enabled for cross-origin requests
- Startup event loads initial data or uses cache
- Background task updates every hour
- WebSocket spawns new connection per client
- Graceful fallback if data unavailable

---

### 4. Backend - alerts.py

**Purpose**: Monitor fiscal events and dispatch notifications

**Classes**:

#### AlertMonitor
- `check_fiscal_events()` - Generate alerts from metrics
- `send_alert()` - Route to Telegram/Discord/Email
- `log_alert()` - Archive to alerts_history.jsonl

**Alert Types**:
1. Fiscal Pressure Critical (> 80/100)
2. Interest Burden High (> 15% of revenue)
3. Unemployment Elevated (> 5%)
4. Large Daily Deficit (> $5B)
5. Elevated Rate Environment (Fed > 5%, 10Y > 4.5%)
6. Debt-to-GDP High (> 120%)

#### DebtCeilingMonitor
- Tracks current ceiling ($36.2T as of 2026)
- Alerts at 95% and 97% of ceiling

#### FiscalEventCalendar
- Upcoming events (tax filing, Fed meetings, auctions, GDP reports)
- Returns events within N days

**Notification Channels**:
- Telegram via bot API (to channel)
- Discord via webhook (rich embeds)
- Email via Resend API (optional)

**Logging**:
- All alerts archived to `alerts_history.jsonl`
- JSON format for easy querying
- Used by SAFLA for pattern learning

---

### 5. Backend - self_heal.py

**Purpose**: Monitor system health and auto-recover from failures

**Classes**:

#### HealthMonitor
- `check_treasury_api()` - Treasury connectivity
- `check_fred_api()` - FRED connectivity
- `check_data_freshness()` - Age of cached data
- `run_health_check()` - Complete audit
- `log_health()` - Record to health.jsonl

**Recovery Agent**:
- `restart_api()` - Kill and restart FastAPI
- `retry_data_collection()` - Fetch from scratch

**Pattern Learner**:
- Learns from repeated failure patterns
- High-confidence patterns auto-trigger recovery
- Integrates with SAFLA for nightly learning cycles

**Monitoring Loop**:
- Runs every 5 minutes
- Checks both APIs + data freshness
- Records health to patterns.jsonl
- Executes recovery if degraded

---

## Data Flow

### Initialization (Startup)

```
1. api.py starts
2. @startup event triggers
3. DataCollector.collect_all() runs
   - TreasuryClient fetches debt, statements, interest
   - FredClient fetches GDP, CPI, rates, unemployment
4. Data saved to debt_clock.db
5. Fiscal metrics calculated
6. Regime classified
7. Response served to frontend
```

### Continuous Operation

```
Every 1 hour:
1. Background task in api.py wakes up
2. DataCollector.collect_all() refreshes
3. Database updated
4. New data available to /current endpoint

Every 5 minutes:
1. HealthMonitor wakes up in self_heal.py
2. Checks API connectivity
3. Checks data freshness
4. Logs to health.jsonl
5. If degraded, triggers recovery

Every second:
1. Client requests /ws/live
2. Per-second deficit calculated
3. Update sent over WebSocket
4. Dashboard counter increments

On demand:
1. /history endpoint queries database
2. Historical data returned for charting
3. /regime returns latest classification
4. /forecast runs linear projection
5. AlertMonitor checks thresholds
```

### Error Handling

```
If Treasury API fails:
  → Log error
  → Use cached data if available
  → After 2 hours: generate alert

If FRED API fails:
  → Use last known values
  → Alerts escalate if data > 24 hours old
  → Self_heal triggers retry

If database corrupted:
  → Falls back to in-memory cache
  → self_heal.py can reset DB
  → Backups stored

If API crashes:
  → self_heal.py detects (health check fails)
  → Logs to patterns.jsonl
  → Auto-restarts after learning pattern
```

---

## Data Model

### debt_snapshot (Current)
```json
{
  "timestamp": "2026-04-04T15:30:00",
  "national_debt": 33700000000000,
  "gdp": 27400000000000,
  "cpi": 315.2,
  "unemployment": 4.2,
  "fed_funds_rate": 5.5,
  "treasury_10y_yield": 4.2,
  "m2_supply": 20000000000000,
  "interest_today": 1800000000
}
```

### daily_statements (Revenue/Outlay Tracking)
```json
{
  "date": "2026-04-03",
  "revenue": 20000000000,
  "outlays": 25000000000,
  "deficit": 5000000000
}
```

### historical_debt (20+ Years)
```json
{
  "date": "2026-04-03",
  "debt": 33695000000000
}
```

### fiscal_regimes (Classification Log)
```json
{
  "timestamp": "2026-04-04T15:30:00",
  "regime": "elevated",
  "pressure_index": 58.3,
  "factors": {
    "debt_to_gdp_score": 22.5,
    "interest_score": 18.2,
    "deficit_score": 12.1,
    "unemployment_score": 8.4,
    "rate_score": 4.5,
    "total_score": 58.3
  }
}
```

### Fiscal Pressure Index Calculation

```
Total Score (0-100):
├─ Debt-to-GDP (0-25 pts)
│  └─ 100% ratio = 25 points
├─ Interest Burden (0-25 pts)
│  └─ 20% of revenue = 25 points
├─ Deficit-to-GDP (0-20 pts)
│  └─ 10% deficit = 20 points
├─ Unemployment (0-15 pts)
│  └─ 6% unemployment = 15 points
└─ Rate Environment (0-15 pts)
   └─ (Fed + 10Y/2) * 1.5 = points

Regime Thresholds:
├─ 0-40: Stable
├─ 40-60: Elevated
├─ 60-80: Critical
└─ 80-100: Crisis
```

---

## Integration Points

### CryptoTradingAgent
- Fiscal pressure signals feed crypto regime detection
- High pressure = risk-off correlations
- Interest rates affect BTC correlation to macro

### Crucix OSINT Dashboard
- Fiscal pressure as economic indicator
- Alerts surface as market-moving events
- Historical comparison with geopolitical data

### RepairXpert Industrial
- Economic conditions → industrial capex demand
- Recessions drive automation ROI
- Debt forecasts shape customer budgets

---

## Performance Characteristics

| Operation | Duration | Frequency |
|-----------|----------|-----------|
| Full data collection | ~5 min | Hourly |
| Fiscal metric calc | ~100ms | Per request |
| GET /current | 50ms | On demand |
| GET /history | 200ms | On demand |
| WebSocket update | 10ms | Per second |
| Health check | 2 sec | Every 5 min |
| Pattern learning | 50ms | Per health check |

---

## Scaling Path

### Phase 1: Current (Single Instance)
- SQLite database
- Python scheduler for updates
- WebSocket single-threaded

### Phase 2: Moderate Scale (100K+ users)
- Add Redis cache layer
- Move to PostgreSQL
- Horizontal API scaling behind load balancer

### Phase 3: Enterprise (1M+ users)
- TimescaleDB for time-series
- Kafka for events
- Distributed monitoring
- CDN for dashboard
- API rate limiting + tiers

---

## Security

### API
- No authentication required (free product)
- Optional Stripe auth for premium tier
- Rate limiting on sensitive endpoints
- CORS restricted in production

### Data
- No sensitive PII stored
- All data is public (Treasury + FRED)
- Database backups recommended
- Health logs for audit trail

### Deployment
- Environment variables for secrets
- HTTPS only in production
- Health checks for availability
- Graceful degradation on failures

---

## Testing

Run comprehensive test suite:
```bash
python test_api.py
```

Tests cover:
- Treasury API connectivity
- FRED API connectivity
- Fiscal calculations
- Database operations
- Alert generation
- Forecast scenarios
