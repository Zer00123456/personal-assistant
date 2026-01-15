# Personal Assistant System

A personalized AI assistant with two core systems:
1. **Creative & Content Production** - Reference database for designs, articles, fonts, styles
2. **Meme Coin Trading** - Trend tracking + pump.fun graduation monitoring

## Quick Start

### 1. Setup Environment

```bash
# Clone/copy to your VPS
cd /opt
git clone <your-repo> personal-assistant
cd personal-assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy template and edit
cp env.template .env
nano .env
```

Add your Discord bot token:
```
DISCORD_BOT_TOKEN=your_actual_token_here
```

### 3. Run

**Option A: Direct (for testing)**
```bash
python -m src.main
```

**Option B: Docker (recommended for production)**
```bash
docker-compose up -d
```

**Option C: Systemd Service (recommended)**
```bash
# Create service file
sudo nano /etc/systemd/system/personal-assistant.service
```

```ini
[Unit]
Description=Personal Assistant Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/personal-assistant
Environment=PATH=/opt/personal-assistant/venv/bin
ExecStart=/opt/personal-assistant/venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable personal-assistant
sudo systemctl start personal-assistant
sudo systemctl status personal-assistant
```

## Usage

### Discord Channels

**Trends Channel** (Memecoin Tracking)
- Post keywords: `vibe coding`
- With description: `vibe coding — AI assisted development`
- TikTok/Twitter links get auto-scraped

**Creative Channel** (References)
- Post URLs: `https://example.com/article`
- With category: `https://example.com #design`
- With project: `https://example.com @myproject`
- Upload images directly

### Slash Commands

- `/trends` - List all tracked trends
- `/refs <query>` - Search references
- `/remove_trend <keyword>` - Stop tracking a trend

## MCP Integration (Claude/Cursor)

For AI assistant integration, run the MCP server:

```bash
python run_mcp.py
```

Then configure your Claude Desktop or Cursor to connect to it.

### Available MCP Tools

**References:**
- `search_references` - Semantic search
- `add_reference` - Add new reference
- `list_references` - List all
- `update_reference` - Edit existing
- `delete_reference` - Remove

**Trends:**
- `add_trend` - Track new keyword
- `list_trends` - Show all trends
- `remove_trend` - Stop tracking
- `get_recent_matches` - View matched coins

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        VPS                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Discord Bot ─────────▶ References DB (ChromaDB)        │
│      │                                                  │
│      └────────────────▶ Trends DB (JSON)                │
│                              │                          │
│  Pump.fun Monitor ◀──────────┘                          │
│      │                                                  │
│      ▼                                                  │
│  Discord Webhook ────▶ Alerts Channel                   │
│                                                         │
│  MCP Server ◀────────▶ Claude/Cursor                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Troubleshooting

**Bot not responding:**
```bash
# Check logs
sudo journalctl -u personal-assistant -f

# Restart
sudo systemctl restart personal-assistant
```

**Database issues:**
```bash
# Data stored in ./chroma_data
# To reset, delete the folder
rm -rf chroma_data/
```

## Files

```
.
├── src/
│   ├── main.py           # Entry point
│   ├── config.py         # Environment config
│   ├── bot/              # Discord bot
│   ├── database/         # ChromaDB + Trends
│   ├── scraper/          # URL content extraction
│   ├── monitor/          # Pump.fun watcher
│   ├── alerts/           # Discord webhooks
│   └── mcp/              # MCP server
├── run_mcp.py            # MCP server runner
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── env.template          # Copy to .env
```


