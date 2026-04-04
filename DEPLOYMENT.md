# US Debt Clock - Deployment Guide

## Quick Start (5 minutes)

### 1. Get FRED API Key

```bash
# Visit: https://fred.stlouisfed.org/docs/api/api_key.html
# Enter email, verify, copy key
# Add to .env: FRED_KEY=your_key
```

### 2. Run Locally

```bash
bash startup.sh
bash run.sh
```

Visit: http://localhost:8500

### 3. Deploy to Render

```bash
# Create new Web Service
# Connect GitHub repo
# Set Environment Variables:
FRED_KEY=your_key
# Deploy!
```

---

## Detailed Deployment

### Option 1: Render.com (Recommended, Free tier available)

#### Setup

1. **Create Render Account**
   - Sign up at https://render.com
   - Connect GitHub

2. **Create Web Service**
   - New → Web Service
   - Connect to GitHub repo
   - Select `DebtClock` directory
   - Build: `pip install -r requirements.txt`
   - Start: `python api.py`
   - Instance Type: Free (or Starter for production)

3. **Environment Variables**
   - Add FRED_KEY
   - Add TELEGRAM_BOT_TOKEN (optional)
   - Add DISCORD_WEBHOOK_URL (optional)

4. **Deploy**
   - Click Deploy
   - Wait 5-10 minutes
   - URL: `https://debt-clock-xxx.onrender.com`

#### Monitoring on Render

```bash
# View logs
curl https://api.render.com/v1/services/YOUR_SERVICE_ID/logs

# Get health
curl https://debt-clock-xxx.onrender.com/health
```

#### Render Limits

- Free tier: 50 hours/month active
- Starter tier: $7/month, unlimited hours
- Database: Use free tier SQLite (stored with app)

---

### Option 2: Docker (Local or Cloud)

#### Build & Run Locally

```bash
# Build image
docker build -t debt-clock .

# Run
docker run -p 8500:8500 \
  -e FRED_KEY=your_key \
  -v $(pwd)/debt_clock.db:/app/debt_clock.db \
  debt-clock

# Access: http://localhost:8500
```

#### Docker Compose (API + Monitor)

```bash
docker-compose up -d

# View logs
docker-compose logs -f debt-clock-api

# Stop
docker-compose down
```

#### Push to Docker Hub

```bash
docker tag debt-clock your_username/debt-clock:latest
docker push your_username/debt-clock:latest
```

---

### Option 3: Railway.app

#### Setup

1. Create Railway account
2. New Project → Deploy from GitHub
3. Select this directory
4. Environment Variables:
   ```
   FRED_KEY=your_key
   ```
5. Deploy

Railway provides:
- Custom domains
- $5/month free tier
- Persistent storage
- PostgreSQL (optional)

---

### Option 4: AWS EC2 (Self-hosted)

#### Launch Instance

```bash
# t2.micro (free tier eligible)
# Ubuntu 22.04 LTS
# Security group: allow 80, 443, 8500
```

#### Install

```bash
sudo apt update
sudo apt install -y python3.11 python3-pip git nginx supervisor

# Clone repo
git clone <your-repo>
cd DebtClock

# Install dependencies
pip install -r requirements.txt

# Set env
cp .env.example .env
nano .env  # Edit with your FRED_KEY
```

#### Run with Supervisor

Create `/etc/supervisor/conf.d/debt-clock.conf`:

```ini
[program:debt-clock-api]
directory=/home/ubuntu/DebtClock
command=/usr/bin/python3 api.py
user=ubuntu
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/debt-clock-api.log

[program:debt-clock-monitor]
directory=/home/ubuntu/DebtClock
command=/usr/bin/python3 self_heal.py
user=ubuntu
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/debt-clock-monitor.log
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start debt-clock-api debt-clock-monitor
```

#### Nginx Reverse Proxy

Create `/etc/nginx/sites-available/debt-clock`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8500;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/debt-clock /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### HTTPS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

### Option 5: DigitalOcean App Platform

#### Create App

1. DigitalOcean Dashboard → Apps
2. Create App → GitHub
3. Connect repo
4. Select branch
5. Runtime: Python
6. Environment Variables: FRED_KEY

#### Build Settings

- Build command: `pip install -r requirements.txt`
- Run command: `python api.py`

#### Deploy

1. Set custom domain
2. Deploy
3. Monitor at: https://your-domain.com

---

## Scaling Considerations

### Database

Currently using SQLite. As data grows:

- **Up to 1M records**: SQLite fine (~500MB)
- **Scaling**: Migrate to PostgreSQL
  ```python
  # In data_collector.py, swap Database for PostgreSQL
  from sqlalchemy import create_engine
  engine = create_engine("postgresql://user:pass@host/debt_clock")
  ```

### Caching

Add Redis for faster API responses:

```python
import redis
cache = redis.Redis(host='localhost', port=6379)

# Cache current snapshot
cache.set('current_snapshot', json.dumps(data), ex=300)
```

### Monitoring

Add APM for production:

```python
# Option 1: Sentry
import sentry_sdk
sentry_sdk.init("YOUR_DSN")

# Option 2: New Relic
import newrelic.agent
newrelic.agent.initialize('newrelic.ini')
```

---

## Customization

### Add Custom Metrics

Edit `data_collector.py` to add metrics:

```python
async def get_custom_metric(self):
    """Add your metric here"""
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.example.com/metric")
        return resp.json()
```

### Change Refresh Intervals

In `api.py`:

```python
# Hourly refresh (default)
await asyncio.sleep(3600)

# Change to 30 minutes
await asyncio.sleep(1800)
```

### Custom Alerts

Edit `alerts.py` to add new alert types:

```python
if some_metric > threshold:
    alert = {
        "type": "custom_alert",
        "level": "warning",
        "title": "My Alert",
        "message": "Alert message",
    }
    alerts.append(alert)
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Is API running?
curl https://your-domain.com/health

# Check data freshness
sqlite3 debt_clock.db "SELECT timestamp FROM debt_snapshot ORDER BY id DESC LIMIT 1;"

# View alerts
tail -f alerts_history.jsonl

# View patterns
tail -f patterns.jsonl
```

### Logs

**Local**:
```bash
tail -f health.jsonl
tail -f alerts_history.jsonl
tail -f patterns.jsonl
```

**Render**:
```bash
# View logs in dashboard or:
curl https://api.render.com/v1/services/YOUR_SERVICE_ID/logs
```

**AWS**:
```bash
tail -f /var/log/debt-clock-api.log
tail -f /var/log/debt-clock-monitor.log
```

### Performance Tuning

**Slower than 200ms response?**

1. Check data freshness
2. Add caching layer (Redis)
3. Profile with: `python -m cProfile api.py`

**High memory usage?**

1. Reduce historical data retention
2. Add pagination to history endpoint
3. Clear old patterns: `> patterns.jsonl`

---

## Troubleshooting

### API won't start

```bash
# Check Python version
python3 --version  # Should be 3.9+

# Check dependencies
pip install -r requirements.txt

# Check port
lsof -i :8500
```

### No data showing

```bash
# Verify FRED_KEY
python3 -c "from data_collector import FredClient; import asyncio; asyncio.run(FredClient('YOUR_KEY').get_gdp())"

# Check Treasury API
curl "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/debt_to_penny?page[size]=1"
```

### Database locked

```bash
# Check connections
sqlite3 debt_clock.db ".open debt_clock.db"

# Backup and reset
cp debt_clock.db debt_clock.db.bak
rm debt_clock.db
python3 -c "from data_collector import Database; Database('debt_clock.db')"
```

---

## Going Live Checklist

- [ ] FRED_KEY configured
- [ ] Domain name registered
- [ ] HTTPS certificate active (Let's Encrypt)
- [ ] Daily monitoring enabled
- [ ] Alerts configured (Telegram/Discord)
- [ ] Error logging to Sentry or similar
- [ ] Backup strategy (daily exports)
- [ ] Load testing (simulate 100+ concurrent users)
- [ ] Documentation updated with your domain
- [ ] Stripe keys added for premium tier
- [ ] Analytics configured (Mixpanel, Amplitude)

---

## Revenue Integration

### Stripe Integration

```python
# In api.py
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@app.post("/create-checkout")
async def create_checkout(tier: str):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"Debt Clock {tier.title()}"},
                    "unit_amount": 900 if tier == "consumer" else 4900,
                },
                "quantity": 1,
            }
        ],
        mode="subscription",
        success_url="https://your-domain.com?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://your-domain.com",
    )
    return {"url": session.url}
```

### Analytics

Add to dashboard.html:

```html
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_ID');
</script>
```

---

## Support & Questions

- Check README.md for features
- Test with: `python test_api.py`
- View health: `curl http://localhost:8500/health`
- Debug: Enable logging in startup.sh
