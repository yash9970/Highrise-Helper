# Workspace

## Overview

pnpm workspace monorepo using TypeScript + a Highrise bot written in Python.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)
- **Python**: 3.11 (for Highrise bot)
- **Bot SDK**: highrise-bot-sdk 24.1.0

## Structure

```text
artifacts-monorepo/
├── artifacts/              # Deployable applications
│   └── api-server/         # Express API server
├── bot/                    # Highrise bot (Python)
│   ├── main.py             # Bot entry point
│   ├── bot.py              # Bot logic (HigrhiseBot class)
│   ├── keep_alive.py       # Flask keep-alive server for UptimeRobot
│   └── vip_users.json      # Persistent VIP users list
├── lib/                    # Shared libraries
│   ├── api-spec/           # OpenAPI spec + Orval codegen config
│   ├── api-client-react/   # Generated React Query hooks
│   ├── api-zod/            # Generated Zod schemas from OpenAPI
│   └── db/                 # Drizzle ORM schema + DB connection
├── scripts/                # Utility scripts
├── pnpm-workspace.yaml
├── tsconfig.base.json
├── tsconfig.json
└── package.json
```

## Highrise Bot Features

### Automatic Behaviors
- Greets **Zen1thos** as Master with a bow (bot bows, not master)
- Greets all other players with a random friendly welcome
- Bot stays at `x=18.0, y=0.0, z=13.5` by default
- Farewell message when players leave

### Commands (Everyone)
- `!hi` — Random friendly greeting from the bot
- `!emote <name>` — Bot performs an emote (e.g. `!emote wave`)
- `!help` — Lists all available commands
- `!song` — Shows the current song playing
- `!nextsong` — Skips to the next song
- `!playlist` — Shows song playlist
- `!dance` — Bot does a random dance
- `!8ball <question>` — Magic 8-ball answer
- `!flip` — Coin flip
- `!joke` — Random joke

### Commands (VIP only)
- `!vip` — Teleport to VIP floor
- `!f0` — Teleport to ground floor (`x=13.0, y=0.1, z=5.0`)

### Commands (Zen1thos / Master only)
- `!pos` — Shows Master's current coordinates
- `!tele` — Bot teleports to Master's location
- `!home` — Bot returns to default position
- `!addvip <username>` — Grant VIP status
- `!removevip <username>` — Remove VIP status
- `!viplist` — List all VIPs

### Keep-Alive (UptimeRobot)
The bot runs a Flask web server on port 8000.
- UptimeRobot URL: `https://712bfd14-bf93-4a90-9b16-b8a64ea68641-00-1o7z2saksmzfd.kirk.replit.dev/ping`
- Endpoints: `/`, `/health`, `/ping`

## Secrets Required
- `HIGHRISE_TOKEN` — Bot API token from Highrise developer portal
- `HIGHRISE_ROOM_ID` — Room ID where bot operates

## Running the Bot
The bot runs via the "ZenBot - Highrise Bot" workflow.
Command: `cd bot && python3 main.py`
