# US Debt Clock — OpenClaw Agent Memory

## Service Status
- **URL**: https://us-debt-clock.onrender.com
- **Hosting**: Render free tier (sleeps after 15min idle, cold start ~30s)
- **Stack**: FastAPI, WebSocket, Treasury API + FRED API
- **Embed API**: $9/mo on Stripe (prod_UKHBbmRC8eGs1S)

## Competitive Landscape
- **usdebtclock.org**: Dominant player, static page with calculated estimates
- **us-debt-clock.com**: Strong SEO, added DOGE tracker + debt-by-president features
- **Our advantage**: Real-time WebSocket data from actual Treasury + FRED APIs, not calculated estimates
- **Our weakness**: Render free tier = cold starts, no DOGE tracker yet

## Distribution Targets
- **PGPF** (pgpf.org): Peter G. Peterson Foundation cites debt tools — get listed on their resources page
- **Financial tool directories**: FindTheBest, AlternativeTo, Product Hunt
- **Economics educators**: Looking for embeddable classroom tools
- **Finance bloggers**: Need real-time debt widgets for their sites
- **Reddit**: r/economics, r/fiscalconservative, r/dataisbeautiful

## Task Queue
1. [ ] Search "embed debt clock website" — find sites wanting widgets
2. [ ] Search "US national debt tracker 2026" — find who discusses debt tools
3. [ ] Find finance subreddits discussing debt ceiling
4. [ ] Find sites linking to usdebtclock.org — offer real-time alternative
5. [ ] Check if listed on any financial tool directories
6. [ ] Get listed on PGPF resources page
7. [ ] Generate tweet content about national debt trends

## Embed Pitch Template
> Add a real-time US national debt clock to your site. Unlike calculated estimates,
> our widget streams live data from the US Treasury and Federal Reserve (FRED) APIs
> via WebSocket. $9/mo. Preview: us-debt-clock.onrender.com

## Run Log
<!-- Agent appends findings below -->
