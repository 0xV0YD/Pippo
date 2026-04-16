import json
from pathlib import Path


MEETING_RECORDS_FILE = Path(__file__).resolve().parent.parent / "data" / "meeting_records.json"
MEETING_CHUNKS_FILE = Path(__file__).resolve().parent.parent / "data" / "meeting_chunks.json"


def load_meeting_records() -> list[dict]:
    return json.loads(MEETING_RECORDS_FILE.read_text(encoding="utf-8"))


def build_meeting_chunks(meeting_records: list[dict]) -> list[dict]:
    chunks = []
    for record in meeting_records:
        base_metadata = {
            "meeting_id": record["id"],
            "title": record["title"],
            "date": record["date"],
            "start_time": record["start_time"],
            "end_time": record["end_time"],
            "calendar_account": record["calendar_account"],
            "attendees": record.get("attendees", []),
            "groups_used": record.get("groups_used", []),
            "tags": record.get("tags", []),
            "source": record.get("source", ""),
        }

        overview_lines = [
            f"Meeting: {record['title']}",
            f"Date: {record['date']}",
            f"Time: {record['start_time']} to {record['end_time']}",
            f"Calendar Account: {record['calendar_account']}",
            f"Attendees: {', '.join(record.get('attendees', [])) or 'None'}",
            f"Groups Used: {', '.join(record.get('groups_used', [])) or 'None'}",
            f"Summary: {record.get('summary', '').strip() or 'No summary'}",
            f"Tags: {', '.join(record.get('tags', [])) or 'None'}",
        ]
        chunks.append(
            {
                **base_metadata,
                "chunk_id": f"{record['id']}::overview",
                "chunk_type": "overview",
                "text": "\n".join(overview_lines),
            }
        )

        if record.get("decisions"):
            decision_lines = [
                f"Meeting: {record['title']}",
                f"Date: {record['date']}",
                "Decisions:",
            ]
            decision_lines.extend(f"- {decision}" for decision in record["decisions"])
            chunks.append(
                {
                    **base_metadata,
                    "chunk_id": f"{record['id']}::decisions",
                    "chunk_type": "decisions",
                    "text": "\n".join(decision_lines),
                }
            )

        if record.get("action_items"):
            action_lines = [
                f"Meeting: {record['title']}",
                f"Date: {record['date']}",
                "Action Items:",
            ]
            for item in record["action_items"]:
                action_lines.append(
                    f"- Owner: {item['owner']} | Task: {item['task']} | Status: {item['status']}"
                )
            chunks.append(
                {
                    **base_metadata,
                    "chunk_id": f"{record['id']}::action_items",
                    "chunk_type": "action_items",
                    "text": "\n".join(action_lines),
                }
            )

        if record.get("open_questions"):
            question_lines = [
                f"Meeting: {record['title']}",
                f"Date: {record['date']}",
                "Open Questions:",
            ]
            question_lines.extend(f"- {question}" for question in record["open_questions"])
            chunks.append(
                {
                    **base_metadata,
                    "chunk_id": f"{record['id']}::open_questions",
                    "chunk_type": "open_questions",
                    "text": "\n".join(question_lines),
                }
            )

    return chunks


def save_meeting_chunks(chunks: list[dict]) -> None:
    MEETING_CHUNKS_FILE.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
