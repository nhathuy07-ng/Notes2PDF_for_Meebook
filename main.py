from pathlib import Path
from xml.etree import ElementTree
from fpdf import FPDF
import json

NOTES_ROOT = Path("notes")
NOTES_LABEL_PATH = NOTES_ROOT / "data" / "notes_label.xml"
NOTES_LIST_PATH = NOTES_ROOT / "data" / "notes.xml"

NOTE_PAGES = NOTES_ROOT / "{noteId}" / "res"
NOTE_CONF = NOTES_ROOT / "{noteId}" / "conf" / "note.conf"
EXPORT_TARGET_PER_NOTE = Path("Exported PDFs") / "{datetime}" / "{groupName}"

# TODO: Implement a file opener to select folder to parse. Experimental feature: if given mtp:/ (KDE-specific), fetch file content from MTP.
# TODO: Decouple the file opener/reader to allow for reading from both MTP (kioclient) and normal files. File opener/reader shall return text string.

def pf(path: Path, **kwargs):
    """
    Formats a pathlib.Path using .format()

    Params: 
        path: a pathlib.Path
        **kwargs: parameters to pass to .format()

    Returns: 
        str: formatted string
    """

    return path.__str__().format(**kwargs)

def list_groups() -> dict[str, str]:
    group_name_by_id: dict[str | None, str] = {None: "[Not grouped]"}
    if NOTES_LABEL_PATH.exists():
        with open(NOTES_LABEL_PATH) as o:
            etree = ElementTree.fromstring(o.read())
            for x in etree.findall('string'):
                if x.get('name').startswith('labelid-'):
                    group_name_by_id[x.get('name')] = json.loads(x.text)['labelName']
                # print([(x.get('name'), json.loads(x.text)['labelName']) for x in etree.findall('string') if x.get('name').startswith('labelid-')])
    else:
        raise Exception(f"File {NOTES_LABEL_PATH.absolute()} does not exist.")

    return group_name_by_id

def list_notes(group_ids: set[str] | None = None) -> dict[str, str]:
    note_name_by_id: dict[str, str] = {}
    note_groupid_by_id: dict[str, str] = {}
    per_group_count: dict[str, str] = {}

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
                        note_name_by_id[note_metadata['noteId']] = note_metadata['noteName']

                        # increment per_group_count
                        per_group_count[note_metadata.get('labelId', None)] = per_group_count.get(note_metadata.get('labelId', None), 0) + 1

                        # assign to group
                        note_groupid_by_id[note_metadata['noteId']] = note_metadata.get('labelId', None)

            return {"note_name_by_id": note_name_by_id, "per_group_count": per_group_count, "note_groupid_by_id": note_groupid_by_id} 
    else:
        raise Exception(f'File {NOTES_LIST_PATH.absolute()} does not exist.')

print(list_groups())
print(list_notes())

def export_notes(note_name_by_id: dict[str, str], note_groupid_by_id: dict[str, str], group_name_by_id: dict[str, str]):
    for note_id, note_name in note_name_by_id.items():
        # Load page list

        # TODO: Create an empty file containing per-page hashes if file not exist. Load that file if exists.

        # TODO: Create folders by existing group names, with "Not grouped" case going into the [Not grouped] folder. Ignore if folder exists.

        # TODO: For each note, hash and compare hash of each page to the hashes file. If all pages match, skip file.

        # TODO: Generate files by getting each page's resolution, add a PDF page, set or add a white background if needed.

        # TODO: When generation is complete, open the export root folder. Write binding for each platforms.

        pass