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
- Current account labels:
  - `Personal Yash`
  - `Pro Yash`

### Linear mode
- Lists your Linear orgs/teams
- Shows your issues
- Filters issues by team and state
- Creates issues
- Updates issue status
- Updates issue labels
- Updates issue project
- Understands follow-ups like `this issue`

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
- carry issue context for follow-up Linear actions

It is giving "executive assistant with sleeper-build anime sidekick" and honestly that is correct.

## Commands You Can Actually Try

### Calendar
- `schedule a meet at 3pm IST tomorrow with akshat@anthias.xyz named Monitoring Sync`
- `create a meeting on Pro Yash calendar with yash@anthias.xyz and vansh@anthias.xyz`
- `/start`
- `/accounts`

### Linear
- `show my linear orgs`
- `show my linear issues`
- `my in progress issues in ANT`
- `list done issues in Anthias`
- `create a linear issue in ANT titled Fix dashboard issue`
- `create an issue with heading "Fixing Dashboard issues" and assign it to me in my org ANT`
- `change ANT-147 to in progress`
- `move this issue to done`
- `add label bug to ANT-147`
- `add ANT-147 to project Monitoring`
- `show linear labels`
- `show linear projects`

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
AI_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
LINEAR_API_KEY=
```

`TELEGRAM_ALLOWED_CHAT_ID` is optional for open testing. Leave it blank if you want to talk to the bot directly without allowlisting.

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
- `get_linear_profile()`
- `list_linear_orgs()`
- `list_linear_issues(...)`
- `list_my_linear_assigned_issues(...)`
- `create_linear_issue_tool(...)`
- `update_linear_issue_state_tool(...)`
- `update_linear_issue_labels_tool(...)`
- `update_linear_issue_project_tool(...)`

## Tiny But Important Notes

- The `work` Google account needs Google Calendar API enabled in its own Google Cloud project.
- The bot can remember the last referenced Linear issue in chat for follow-ups like `this issue`.
- Linear labels currently work as a replace-style update in the backend flow unless you explicitly teach it additive/removal semantics.
- If you pasted secrets in chat while testing, rotate them later. Future you will be grateful.

## Logo Drop Zone

To make the logo render in this README, save the image in the repo root as:

`pippo-logo.png`

Right now the README is already wired to that path.

## Vibe Check

This project is:
- deeply useful
- slightly dangerous
- absurdly fun

Which is exactly where a good personal automation bot should be.

Made with love by me
