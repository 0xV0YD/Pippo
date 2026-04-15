<img src="./assets/pippo-logo.png" alt="Pippo bot logo" width="2000" />

# Pippo

Your Telegram bot is no longer just a bot. It is now a mildly unhinged, hyper-productive ops goblin that can schedule meetings, juggle multiple Google calendars, and bully Linear issues into shape from chat.

Think:
- "book a sync at 3pm with the team"
- "show my in progress issues in ANT"
- "move this issue to done"
- "add label bug"
- "put this in project Monitoring"

All from Telegram. No tab chaos. No context-switch speedrun. No corporate suffering simulator.

## What This Thing Does

### Calendar mode
- Schedules Google Calendar events from Telegram
- Supports multiple Google accounts
- Lets you switch active calendar identity with buttons
- Lists today's meetings
- Finds free slots on your calendar
- Expands saved group names into attendee lists
- Creates Google Meet links automatically
- Current account labels:
  - `Personal Yash`
  - `Pro Yash`

### Linear mode
- Lists your Linear orgs/teams
- Shows your issues
- Filters issues by team and state
- Creates issues
- Updates issue status
- Assigns issues to people
- Adds and removes labels
- Updates issue project
- Understands follow-ups like `this issue`

### Memory mode
- Saves members with names, emails, and aliases
- Saves reusable groups like `infra`
- Lets you inspect members and groups from Telegram

### Safety mode
- Locks the bot so only `@OxVoyd` can use it
- Asks for `Confirm / Cancel` before risky actions run

### MCP mode
- Exposes reusable tools through your local MCP server
- Lets Codex or any MCP-aware client call the same functions
- Keeps your automation stack modular instead of becoming one giant cursed script

## Main Character Energy

This repo is basically:

`Telegram UI` + `Gemini brain` + `Google Calendar` + `Linear` + `MCP tools` + `Dockerized chaos`

Which means the bot can:
- talk like a normal assistant
- execute real actions
- remember which calendar account you selected
- remember saved members and groups
- carry issue context for follow-up Linear actions
- ask for confirmation before high-impact actions

It is giving "executive assistant with sleeper-build anime sidekick" and honestly that is correct.

## Commands You Can Actually Try

### Calendar
- `/help`
- `/start`
- `/accounts`
- `list today's meetings`
- `find free slots today`
- `find free slots on 2026-04-14 for 30 minutes`
- `schedule a meet at 3pm IST tomorrow with akshat named Monitoring Sync`
- `schedule a sync with infra tomorrow at 4pm IST named Infra Sync`

### Linear
- `show my linear orgs`
- `show my linear issues`
- `my in progress issues in ANT`
- `list done issues in Anthias`
- `create a linear issue in ANT titled Fix dashboard issue`
- `create an issue with heading "Fixing Dashboard issues" and assign it to me in my org ANT`
- `assign ANT-147 to akshat`
- `change ANT-147 to in progress`
- `move this issue to done`
- `add label bug to ANT-147`
- `remove label bug from ANT-147`
- `add ANT-147 to project Monitoring`
- `show linear labels`
- `show linear projects`

### Members and Groups
- `/members`
- `/showmember akshat`
- `/addmember Harsh harsh@anthias.xyz harsh`
- `/removemember harsh`
- `/groups`
- `/addgroup infra vasu akshat vansh`
- `/removegroup infra`

## Setup

### 1. Env

Copy:

```bash
cp .env.example .env
```

Fill in:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_ID=
TELEGRAM_ALLOWED_USERNAME=OxVoyd
AI_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
LINEAR_API_KEY=
```

Security notes:
- `TELEGRAM_ALLOWED_USERNAME` is the primary identity lock. By default Pippo only responds to `@OxVoyd`.
- `TELEGRAM_ALLOWED_CHAT_ID` is optional extra hardening if you want both username and chat ID enforcement.

AI provider notes:
- `AI_PROVIDER=openai` uses your OpenAI API key
- `AI_PROVIDER=gemini` uses your Gemini API key
- OpenAI is the default path now

### 2. Google Calendar creds

Put your OAuth desktop client files here:

- `credentials/google_oauth_client_default.json`
- `credentials/google_oauth_client_work.json`

First auth run creates:

- `credentials/google_token_default.json`
- `credentials/google_token_work.json`

Calendar account mapping:
- `default` -> `Personal Yash`
- `work` -> `Pro Yash`

### 3. Run It

Local:

```bash
uv run python telegram_bot.py
```

Docker:

```bash
make up
make logs
make down
```

## Repo Map

### Core files
- [telegram_bot.py](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/telegram_bot.py:1): Telegram chat brain and routing
- [main.py](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/main.py:1): MCP entrypoint
- [server.py](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/server.py:1): shared FastMCP instance

### Knowledge / RAG Prep
- [knowledge/README.md](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/knowledge/README.md:1)
- [docs/rag-learning-plan.md](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/docs/rag-learning-plan.md:1)

### Google Calendar
- [utils/calendar_client.py](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/utils/calendar_client.py:1)
- [tools/calendar_tools.py](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/tools/calendar_tools.py:1)

### Linear
- [utils/linear_client.py](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/utils/linear_client.py:1)
- [tools/linear_tools.py](/home/glitch/Desktop/anthias/DCS/Agents/Proj3/tools/linear_tools.py:1)

## MCP Tools

Available backend tool powerups include:

- `create_calendar_event(...)`
- `authenticate_google_account(...)`
- `list_connected_google_accounts()`
- `list_todays_meetings(...)`
- `find_free_slots(...)`
- `get_linear_profile()`
- `list_linear_orgs()`
- `list_linear_issues(...)`
- `list_my_linear_assigned_issues(...)`
- `create_linear_issue_tool(...)`
- `update_linear_issue_state_tool(...)`
- `update_linear_issue_labels_tool(...)`
- `add_linear_issue_labels_tool(...)`
- `remove_linear_issue_labels_tool(...)`
- `update_linear_issue_project_tool(...)`
- `assign_linear_issue_tool(...)`

## Tiny But Important Notes

- The `work` Google account needs Google Calendar API enabled in its own Google Cloud project.
- The bot can remember the last referenced Linear issue in chat for follow-ups like `this issue`.
- The bot now supports both label replacement and additive/remove label flows.
- Risky actions like creating meetings or mutating Linear issues now require a confirmation tap.
- If you pasted secrets in chat while testing, rotate them later. Future you will be grateful.

## Vibe Check

This project is:
- deeply useful
- slightly dangerous
- absurdly fun

Which is exactly where a good personal automation bot should be.

Made with ❤️ by me
