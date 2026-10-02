from pathlib import Path
from xml.etree import ElementTree
from fpdf import FPDF
import json
from PIL import Image
import hashlib
import os
import platform
import tqdm
import subprocess

NOTES_ROOT = Path("notes")
NOTES_LABEL_PATH = NOTES_ROOT / "data" / "notes_label.xml"
NOTES_LIST_PATH = NOTES_ROOT / "data" / "notes.xml"

NOTE_PAGES = NOTES_ROOT / "{noteId}" / "res"
NOTE_PAGE = NOTES_ROOT / "{noteId}" / "res" / "pageId_{pageId}.png"
NOTE_CONF = NOTES_ROOT / "{noteId}" / "conf" / "note.conf"
EXPORT_TARGET_ROOT = Path("Exported PDFs")
EXPORT_TARGET_PER_GROUP = EXPORT_TARGET_ROOT / "{groupName}"
EXPORT_TARGET_PER_NOTE = EXPORT_TARGET_ROOT / "{groupName}" / "{fileName}.pdf"

# TODO: Implement a file opener to select folder to parse. Experimental feature: if given mtp:/ (KDE-specific), fetch file content from MTP.
# TODO: Decouple the file opener/reader to allow for reading from both MTP (kioclient) and normal files. File opener/reader shall return text string.

def open_dir_default_tool(dir: Path):
    """
    Opens a directory in the OS's default tool
    """
    match platform.system():
        case 'Linux':
            subprocess.run(['xdg-open', str(dir)])
        case 'Darwin':
            subprocess.run(['open', str(dir)])
        case 'Windows':
            os.startfile(str(dir))
        case _:
            print(f"Opening directory: {dir} in default app failed. OS not supported.")


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

    group_ids = note_groupid_by_id.values()
    for group_id in group_ids:
        if not pf(EXPORT_TARGET_PER_GROUP, groupName=group_name_by_id[group_id]).exists():
            pf(EXPORT_TARGET_PER_GROUP, groupName=group_name_by_id[group_id]).mkdir(parents=True, exist_ok=True)
    
    for note_id, note_name in note_name_by_id.items():
        # Load page list
        page_ids: list[str] = []
        with open(pf(NOTE_CONF, noteId=note_id)) as o:
            page_ids = json.load(o)["pageIds"]

        # TODO: Generate files by getting each page's resolution, add a PDF page, set or add a white background if needed.
        pdf = FPDF(unit="pt")
        for page_i, page_id in enumerate(page_ids):
            try:
                # check image size
                img_size = (0, 0)
                with Image.open(pf(NOTE_PAGE, noteId=note_id, pageId=page_id)) as im_open:
                    img_size = im_open.size
            except Exception as e:
                print(f"WARN: Document '{note_name}', page {page_id} (index {page_i}) skipped due to: {e}")
            else:
                pdf.add_page(format=img_size)
                pdf.image(pf(NOTE_PAGE, noteId=note_id, pageId=page_id), x=0, y=0)
            

        pdf.output(pf(EXPORT_TARGET_PER_NOTE, groupName=group_name_by_id[note_groupid_by_id[note_id]], fileName=note_name))

        # TODO: When generation is complete, open the export root folder. Write binding for each platforms.
    open_dir_default_tool(EXPORT_TARGET_ROOT)
        

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