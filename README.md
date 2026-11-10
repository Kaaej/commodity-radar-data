# Commodity Radar, daily data

Market news, economic calendar, policy rates and the daily market brief shown on [Commodity Radar](https://commodity-radar.netlify.app), updated each weekday morning by a market watch agent.

- `live/events.json`: market events pinned on the map (date, commodity, place, title, price move, source and link).
- `live/calendar.json`: central bank meetings, macro releases and energy reports (Paris time).
- `live/rates.json`: latest policy rate decisions logged by the market watch.
- `live/editions.json`: the daily market brief, written in English from sourced news.
- `add_live.py`: merges a new batch, never deletes or overwrites existing items, commits, pushes and checks the result online.

Each item links to its original source. © 2026 Arthur DE CLAIRVAL ([LinkedIn](https://www.linkedin.com/in/arthur-de-clairval/)); the underlying facts belong to their sources.
