import json
from pathlib import Path


CONTACTS_FILE = Path(__file__).resolve().parent.parent / "data" / "contacts.json"
GROUPS_FILE = Path(__file__).resolve().parent.parent / "data" / "groups.json"


DEFAULT_CONTACTS = [
    {"name": "Vasu", "email": "vasu@anthias.xyz", "aliases": ["vasu"]},
    {"name": "Akshat", "email": "akshat@anthias.xyz", "aliases": ["akshat"]},
    {"name": "Vansh", "email": "vansh@anthias.xyz", "aliases": ["vansh"]},
    {"name": "Vaishnavi", "email": "vaishnavi@anthias.xyz", "aliases": ["vaishnavi"]},
    {"name": "Noah", "email": "noah@anthias.xyz", "aliases": ["noah"]},
    {"name": "Sy", "email": "sy@anthias.xyz", "aliases": ["sy"]},
    {"name": "Aaron", "email": "aaron@anthias.xyz", "aliases": ["aaron"]},
    {"name": "Charlie", "email": "charlie@anthias.xyz", "aliases": ["charlie"]},
]


def ensure_contacts_file() -> None:
    if CONTACTS_FILE.exists():
        return
    CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTACTS_FILE.write_text(json.dumps(DEFAULT_CONTACTS, indent=2), encoding="utf-8")


def load_contacts() -> list[dict]:
    ensure_contacts_file()
    return json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))


def save_contacts(contacts: list[dict]) -> None:
    CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTACTS_FILE.write_text(json.dumps(contacts, indent=2), encoding="utf-8")


def add_contact(name: str, email: str, aliases: list[str] | None = None) -> dict:
    contacts = load_contacts()
    normalized_email = email.strip().lower()
    for contact in contacts:
        if contact["email"].strip().lower() == normalized_email:
            raise ValueError(f"Contact with email '{email}' already exists")

    alias_values = aliases or [name.strip().lower()]
    contact = {
        "name": name.strip(),
        "email": normalized_email,
        "aliases": [alias.strip().lower() for alias in alias_values if alias.strip()],
    }
    contacts.append(contact)
    save_contacts(contacts)
    return contact


def remove_contact(email_or_alias: str) -> dict:
    contacts = load_contacts()
    needle = email_or_alias.strip().lower()
    for index, contact in enumerate(contacts):
        aliases = [alias.strip().lower() for alias in contact.get("aliases", [])]
        if contact["email"].strip().lower() == needle or needle in aliases:
            removed = contacts.pop(index)
            save_contacts(contacts)
            return removed
    raise ValueError(f"Contact '{email_or_alias}' not found")


def find_contact(token: str) -> dict | None:
    needle = token.strip().lower()
    for contact in load_contacts():
        aliases = [alias.strip().lower() for alias in contact.get("aliases", [])]
        if contact["email"].strip().lower() == needle or needle in aliases or contact["name"].strip().lower() == needle:
            return contact
    return None


def ensure_groups_file() -> None:
    if GROUPS_FILE.exists():
        return
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    GROUPS_FILE.write_text(json.dumps([], indent=2), encoding="utf-8")


def load_groups() -> list[dict]:
    ensure_groups_file()
    return json.loads(GROUPS_FILE.read_text(encoding="utf-8"))


def save_groups(groups: list[dict]) -> None:
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    GROUPS_FILE.write_text(json.dumps(groups, indent=2), encoding="utf-8")


def add_group(name: str, members: list[str]) -> dict:
    groups = load_groups()
    normalized_name = name.strip().lower()
    for group in groups:
        if group["name"].strip().lower() == normalized_name:
            raise ValueError(f"Group '{name}' already exists")

    resolved_members = []
    for member in members:
        contact = find_contact(member)
        if not contact:
            raise ValueError(f"Member '{member}' not found in contacts")
        resolved_members.append(contact["email"])

    group = {"name": name.strip(), "members": resolved_members}
    groups.append(group)
    save_groups(groups)
    return group


def contacts_prompt_block() -> str:
    contacts = load_contacts()
    if not contacts:
        return "Known contacts: none"
    lines = ["Known contacts:"]
    for contact in contacts:
        aliases = ", ".join(contact.get("aliases", []))
        lines.append(f"- {contact['name']} <{contact['email']}> aliases: {aliases}")
    return "\n".join(lines)


def groups_prompt_block() -> str:
    groups = load_groups()
    if not groups:
        return "Known groups: none"
    lines = ["Known groups:"]
    for group in groups:
        members = ", ".join(group.get("members", []))
        lines.append(f"- {group['name']}: {members}")
    return "\n".join(lines)
