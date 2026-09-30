from pathlib import Path
from xml.etree import ElementTree
import json

NOTES_ROOT = Path("notes")
NOTES_LABEL_PATH = NOTES_ROOT / "data" / "notes_label.xml"
NOTES_LIST_PATH = NOTES_ROOT / "data" / "notes.xml"

def list_groups() -> dict[str, str]:
    group_ids: dict[str | None, str] = {None: "[Not grouped]"}
    if NOTES_LABEL_PATH.exists():
        with open(NOTES_LABEL_PATH) as o:
            etree = ElementTree.fromstring(o.read())
            for x in etree.findall('string'):
                if x.get('name').startswith('labelid-'):
                    group_ids[x.get('name')] = json.loads(x.text)['labelName']
                # print([(x.get('name'), json.loads(x.text)['labelName']) for x in etree.findall('string') if x.get('name').startswith('labelid-')])
    else:
        raise Exception(f"File {NOTES_LABEL_PATH.absolute()} does not exist.")

    return group_ids

def list_notes(group_ids: set[str] | None = None) -> dict[str, str]:
    note_ids: dict[str, str] = {}
    print(group_ids)
    if NOTES_LIST_PATH.exists():
        with open(NOTES_LIST_PATH) as o:

            etree = ElementTree.fromstring(o.read())

            # enforce category = 0 to limit export to standalone notes for now
            for x in etree.findall('string'):
                if x.get('name').startswith('noteid-'):
                    note_metadata = json.loads(x.text)

                    # membership & note type check
                    is_in_groups = (group_ids is None) or (note_metadata.get('labelId', None) in group_ids)
                    is_standalone = note_metadata['category'] == 0

                    if is_standalone and is_in_groups:
                        note_ids[note_metadata['noteId']] = note_metadata['noteName']

            return note_ids
    else:
        raise Exception(f'File {NOTES_LIST_PATH.absolute()} does not exist.')

def export_notes(note_ids: set[str] | None = None):
    pass
