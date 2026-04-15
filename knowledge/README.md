# Knowledge Base

This folder is the future RAG corpus for Pippo.

Right now this is Phase 0:
- define what kinds of knowledge Pippo should know
- keep a small, human-readable corpus
- start with a few well-structured markdown files

Why this exists:
- later phases will chunk these docs
- generate embeddings for those chunks
- index them in a retriever
- let Pippo answer grounded questions from them

Recommended document types:
- specs
- meeting notes
- glossary / team language
- playbooks
- onboarding notes

Current starter docs:
- [project_overview.md](./project_overview.md)
- [team_glossary.md](./team_glossary.md)
- [meeting_notes_sample.md](./meeting_notes_sample.md)
- [operations_playbook.md](./operations_playbook.md)

Design rules for docs in this folder:
- use clear headings
- keep sections focused
- prefer markdown over random text dumps
- include dates where useful
- avoid giant mixed-topic files

Later RAG phases will work much better if the source documents are clean.
