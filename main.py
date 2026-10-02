from pathlib import Path
from xml.etree import ElementTree
from fpdf import FPDF
import json

NOTES_ROOT = Path("notes")
NOTES_LABEL_PATH = NOTES_ROOT / "data" / "notes_label.xml"
NOTES_LIST_PATH = NOTES_ROOT / "data" / "notes.xml"

NOTE_PAGES = NOTES_ROOT / "{noteId}" / "res"
NOTE_CONF = NOTES_ROOT / "{noteId}" / "conf" / "note.conf"
EXPORT_TARGET_ROOT = Path("Exported PDFs")
EXPORT_TARGET_PER_NOTE = EXPORT_TARGET_ROOT / "{groupName}"
EXPORT_TARGET_HASHES = EXPORT_TARGET_ROOT / "hashes.json" 

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

    return Path(path.__str__().format(**kwargs))

def wait_for_user_select(source_list: list[any]):
    raw_in = input("Select entries (e.g 0, 1, 2-7) or skip to select all: ")

    if raw_in.strip() == '':
        return source_list # selects all

    try:
        sel = []
        for n in raw_in.split(','):
            if "-" in n:
                # parse range (inclusive)
                nstart, nend = n.split("-")
                sel.extend(source_list[int(nstart):int(nend)+1])
                continue

            # parse single num
            try:
                nnum = int(n.strip())
                sel.append(source_list[nnum])
            except:
                continue
        return sel
    except Exception as e:
        raise Exception(f"Input error: {e}")

def list_groups() -> dict[str, str]:
    group_name_by_id: dict[str | None, str] = {None: "[Not grouped]"}
    if NOTES_LABEL_PATH.exists():
        with open(NOTES_LABEL_PATH) as o:
            etree = ElementTree.fromstring(o.read())
            for x in etree.findall('string'):
                if x.get('name').startswith('labelid-'):
                    group_name_by_id[x.get('name')] = json.loads(x.text)['labelName']
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

def export_notes(note_name_by_id: dict[str, str], note_groupid_by_id: dict[str, str], group_name_by_id: dict[str, str]):
            
    if not EXPORT_TARGET_ROOT.exists():
        EXPORT_TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    page_hashes_by_noteid: dict[str, list[str]] = {}
    if EXPORT_TARGET_HASHES.exists():
        with open(EXPORT_TARGET_HASHES) as o:
            page_hashes_by_noteid = json.load(o)
    else:
        with open(EXPORT_TARGET_HASHES, "a") as w:
            json.dump(page_hashes_by_noteid, w)

    group_ids = note_groupid_by_id.values()
    for group_id in group_ids:
        if not pf(EXPORT_TARGET_PER_NOTE, groupName=group_name_by_id[group_id]).exists():
            pf(EXPORT_TARGET_PER_NOTE, groupName=group_name_by_id[group_id]).mkdir(parents=True, exist_ok=True)
    
    for note_id, note_name in note_name_by_id.items():
        # Load page list

        # TODO: Create folders by existing group names, with "Not grouped" case going into the [Not grouped] folder. Ignore if folder exists.

        # TODO: For each note, hash and compare hash of each page to the hashes file. If all pages match, skip file.

        # TODO: Generate files by getting each page's resolution, add a PDF page, set or add a white background if needed.

        # TODO: When generation is complete, open the export root folder. Write binding for each platforms.

        pass

if __name__ == '__main__':
    note_groups = list(list_groups().items())
    note_groups.sort(key=lambda x: x[1])
    for i, entry in enumerate(note_groups):
        note_id, note_label = entry
        print(f"{i}. {note_label}")

    group_id_sel = []
    while True:
        try:
            group_id_sel = wait_for_user_select([group_id for group_id, group_label in note_groups])
        except Exception as e:
            print(e)
        else:
            break

    notes = list_notes(group_id_sel)
    print(f"Exporting {sum([x[1] for x in notes['per_group_count'].items()])} notes...")
    export_notes(notes['note_name_by_id'], notes['note_groupid_by_id'], list_groups())