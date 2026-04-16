# Project Overview

## What Pippo Is

Pippo is a Telegram-first AI assistant for operational work.

Its current responsibilities include:
- scheduling Google Calendar meetings
- creating Google Meet links automatically
- switching across multiple Google account aliases
- reading and updating Linear issues
- remembering saved members and groups
- asking for confirmation before risky actions

## Current System Shape

Pippo currently has these layers:
- Telegram bot interface
- AI parsing and intent routing
- direct Python utility functions for Calendar and Linear
- MCP tool wrappers for reuse by MCP-aware hosts

## Product Direction

The long-term direction is:
- operational assistant
- knowledge-aware assistant
- action-taking assistant

That means Pippo should eventually:
- answer questions from internal docs
- retrieve relevant project context before acting
- combine knowledge retrieval with tool execution

## Why RAG Matters Here

Right now Pippo can do things.

RAG will help Pippo know things, such as:
- what a project is about
- what terms like "lighter integration" mean
- what happened in past meeting notes
- how a team usually names issues or meetings

## Near-Term RAG Goals

The first useful knowledge abilities for Pippo are:
- answer questions from markdown docs
- find project notes and summaries
- recall previous decisions from notes
- ground meeting or Linear actions in retrieved context
