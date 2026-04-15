# Team Glossary

## Anthias

Anthias is the working context around Pippo's automation workflows.

## Pippo

Pippo is the Telegram bot and assistant layer.

It is designed to:
- schedule meetings
- manage Linear tasks
- store small operational memory
- eventually use retrieval over internal knowledge

## MCP

MCP stands for Model Context Protocol.

In this project, MCP is the standardized capability layer that exposes tools such as:
- creating calendar events
- listing meetings
- reading and updating Linear issues

MCP is more about capabilities than memory.

## RAG

RAG stands for Retrieval-Augmented Generation.

In this project, RAG will be the knowledge layer that lets Pippo answer using:
- specs
- notes
- playbooks
- internal docs

## Personal Yash

`Personal Yash` is the friendly display label for the default Google account alias.

## Pro Yash

`Pro Yash` is the friendly display label for the work Google account alias.

## Infra

`infra` is an example reusable attendee group. Group names should eventually be resolvable both in scheduling and in knowledge queries.

## Lighter Integration

This is an example project phrase that would benefit from RAG because it sounds like domain-specific context that the assistant should be able to retrieve from specs or notes rather than guess from general model knowledge.
