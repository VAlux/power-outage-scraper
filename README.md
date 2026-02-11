# Power Outage Scraper -> Apple Calendar

Python scraper that polls `https://poweron.loe.lviv.ua/` on a configurable interval, parses outage schedule text, filters by configured outage queue, and updates a specific Apple Calendar (via CalDAV/iCloud).

## What it does

- Scrapes the schedule page.
- Parses:
  - applicable schedule date,
  - update datetime,
  - time ranges for each outage queue.
- Processes only schedules for today or tomorrow.
- Uses a txt state file (`/data/state.txt`) to detect changes.
- Replaces events for the target day/queue in the selected Apple Calendar.

## Configuration

Set environment variables:

- `SCRAPE_INTERVAL_SECONDS` (default: `30`)
- `SOURCE_URL` (default: `https://poweron.loe.lviv.ua/`)
- `OUTAGE_QUEUE` (default: `1`)
- `STATE_FILE` (default: `/data/state.txt`)
- `TZ` (default: `Europe/Kyiv`)
- `CHROMIUM_EXECUTABLE` (default: `/usr/bin/chromium`)
- `CHROMIUM_LAUNCH_TIMEOUT_MS` (default: `180000`)
- `LOG_EXTRACTED_EVENTS` (default: `false`, enables debug logging of parsed schedule events)
- `CALDAV_URL` (default: `https://caldav.icloud.com/`)
- `CALDAV_USER` (required, usually Apple ID email)
- `CALDAV_PASSWORD` (required, iCloud app-specific password)
- `CALENDAR_NAME` (default: `Power Outage`)
- `EVENT_PREFIX` (default: `Power outage`)

## Run with Docker

Build image:

```bash
docker build -t poweroutage-scraper .
```

Run container:

```bash
docker run -d \
  --name poweroutage-scraper \
  -e SCRAPE_INTERVAL_SECONDS=30 \
  -e OUTAGE_QUEUE=1.1 \
  -e TZ=Europe/Kyiv \
  -e CALDAV_USER="your-apple-id@example.com" \
  -e CALDAV_PASSWORD="app-specific-password" \
  -e CALENDAR_NAME="Power Outage" \
  -v poweroutage-data:/data \
  poweroutage-scraper
```

Check logs:

```bash
docker logs -f poweroutage-scraper
```

## Notes

- State file keeps fingerprints for only today and tomorrow.
- Scraping is Chromium/Playwright-based (rendered HTML).
- Schedule parsing is DOM-based: the parser reads `.power-off__text` blocks and extracts each day from those blocks.
- If the page contains multiple schedule blocks (for example today and tomorrow), each day is parsed and synced independently.
