from pathlib import Path
from xml.etree import ElementTree
from fpdf import FPDF
import json
from PIL import Image
import os
import platform
import subprocess
from multiprocessing import Pool
import sys
import crossfiledialog
import io
import shutil

paths = {}

EXPORT_TARGET_ROOT = Path("Exported PDFs")
EXPORT_TARGET_PER_GROUP = EXPORT_TARGET_ROOT / "{groupName}"
EXPORT_TARGET_PER_NOTE = EXPORT_TARGET_ROOT / "{groupName}" / "{fileName}.pdf"

def set_up_source_path():
    global paths
    source_folder = crossfiledialog.choose_folder("Select source folder...")
    print(source_folder)
    if not source_folder:
        print("Path not selected. Exiting...")
        sys.exit(-1)
    if source_folder.startswith('mtp:/'):
        paths = {
            "NOTES_ROOT": source_folder,
            "NOTES_LABEL_PATH": f"{source_folder}/data/notes_label.xml",
            "NOTES_LIST_PATH": f"{source_folder}/data/notes.xml",
            "NOTE_PAGES": source_folder + "/{noteId}/res",
            "NOTE_PAGE": source_folder + "/{noteId}/res/pageId_{pageId}.png",
            "NOTE_CONF": source_folder + "/{noteId}/conf/note.conf",
            "EXPORT_TARGET_ROOT": Path("Exported PDFs"),
            "EXPORT_TARGET_PER_GROUP": Path("Exported PDFs") / "{groupName}",
            "EXPORT_TARGET_PER_NOTE": Path("Exported PDFs") / "{groupName}" / "{fileName}.pdf"
        }
    else:
        paths = {
            "NOTES_ROOT": Path(source_folder),
            "NOTES_LABEL_PATH": Path(source_folder) / "data" / "notes_label.xml",
            "NOTES_LIST_PATH": Path(source_folder) / "data" / "notes.xml",
            "NOTE_PAGES": Path(source_folder) / "{noteId}" / "res",
            "NOTE_PAGE": Path(source_folder) / "{noteId}" / "res" / "pageId_{pageId}.png",
            "NOTE_CONF": Path(source_folder) / "{noteId}" / "conf" / "note.conf",
            "EXPORT_TARGET_ROOT": Path("Exported PDFs"),
            "EXPORT_TARGET_PER_GROUP": Path("Exported PDFs") / "{groupName}",
            "EXPORT_TARGET_PER_NOTE": Path("Exported PDFs") / "{groupName}" / "{fileName}.pdf"
        }

def handle_open_bin_file(path: Path | str):
    print(path)
    if str(path).startswith('mtp:/'):
        proc = subprocess.run(['kioclient', 'cat', str(path)], stdout=subprocess.PIPE)
        byte_out = proc.stdout
        byte_io = io.BytesIO()
        byte_io.write(byte_out)
        byte_io.seek(0)
        
        return byte_io
    else:
        return open(path, 'rb')

def handle_open_text_file(path: Path | str):
    print(path)
    if str(path).startswith('mtp:/'):
        proc = subprocess.run(['kioclient', 'cat', str(path)], stdout=subprocess.PIPE)
        str_out = proc.stdout.decode('utf-8')
        str_io = io.StringIO()
        str_io.write(str_out)
        str_io.seek(0)
        
        return str_io
    else:
        return open(path)

def open_dir_default_tool(dir: Path):
    """
    Opens a directory in the OS's default tool
    """
    print(f"Opening directory: {dir} in default app...")
    match platform.system():
        case 'Linux':
            subprocess.run(['xdg-open', str(dir)])
        case 'Darwin':
            subprocess.run(['open', str(dir)])
        case 'Windows':
            os.startfile(str(dir))
        case _:
            print(f"Opening directory: {dir} in default app failed. OS not supported.")


def pf(path: Path | str, **kwargs):
    """
    Formats a pathlib.Path using .format()

    Params: 
        path: a pathlib.Path
        **kwargs: parameters to pass to .format()

    Returns: 
        str: formatted string
    """
    if isinstance(path, Path):
        return Path(path.__str__().format(**kwargs))
    else:
        return path.format(**kwargs)

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
    with handle_open_text_file(paths["NOTES_LABEL_PATH"]) as o:
        etree = ElementTree.fromstring(o.read())
        for x in etree.findall('string'):
            if x.get('name').startswith('labelid-'):
                group_name_by_id[x.get('name')] = json.loads(x.text)['labelName']


    return group_name_by_id
  
def list_notes(group_ids: set[str] | None = None) -> dict[str, str]:
    note_name_by_id: dict[str, str] = {}
    note_groupid_by_id: dict[str, str] = {}
    per_group_count: dict[str, str] = {}

    print(group_ids)
    if type(paths["NOTES_LIST_PATH"]) == str or paths["NOTES_LIST_PATH"].exists():
        with handle_open_text_file(paths["NOTES_LIST_PATH"]) as o:

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
        raise Exception(f'File {paths["NOTES_LIST_PATH"].absolute()} does not exist.')

def note_export_worker(worker_input):
    note_id, note_name, group_name_by_id, note_groupid_by_id, paths = worker_input
    # Load page list
    page_ids: list[str] = []
    with handle_open_text_file(pf(paths["NOTE_CONF"], noteId=note_id)) as o:
        page_ids = json.load(o)["pageIds"]

    pdf = FPDF(unit="pt")
    img_size = None

    for page_i, page_id in enumerate(page_ids):
        try:
            # check image size for first page only
            with handle_open_bin_file(pf(paths["NOTE_PAGE"], noteId=note_id, pageId=page_id)) as ob:
                with Image.open(ob) as im_open:
                    if img_size == None:
                        img_size = im_open.size
                ob.seek(0)
                pdf.add_page(format=img_size)
                pdf.image(ob, x=0, y=0)

        except Exception as e:
            print(f" [WARN] Document '{note_name}', page {page_id} (index {page_i}) skipped due to: {e}")
        
    pdf.output(pf(EXPORT_TARGET_PER_NOTE, groupName=group_name_by_id[note_groupid_by_id[note_id]], fileName=note_name)) 
    print(note_name + " done!")

def export_notes(note_name_by_id: dict[str, str], note_groupid_by_id: dict[str, str], group_name_by_id: dict[str, str], threads: int=8):
    
    if not EXPORT_TARGET_ROOT.exists():
        EXPORT_TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    group_ids = note_groupid_by_id.values()
    for group_id in group_ids:
        if not pf(EXPORT_TARGET_PER_GROUP, groupName=group_name_by_id[group_id]).exists():
            pf(EXPORT_TARGET_PER_GROUP, groupName=group_name_by_id[group_id]).mkdir(parents=True, exist_ok=True)

    # TODO: Multithread this
    with Pool(threads) as p:
        p.map(note_export_worker, [(note_id, note_name, group_name_by_id, note_groupid_by_id, paths) for note_id, note_name in note_name_by_id.items()])           
        
if __name__ == '__main__':

    # Interactively set up source path
    set_up_source_path()

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

    override_mode = input(f"Delete existing directory '{paths['EXPORT_TARGET_ROOT'].absolute()}' (if exists?) [y/n]")
    if override_mode.lower() == 'y' and paths['EXPORT_TARGET_ROOT'].exists():
        shutil.rmtree(paths['EXPORT_TARGET_ROOT'])

    notes = list_notes(group_id_sel)
    print(f"Exporting {sum([x[1] for x in notes['per_group_count'].items()])} notes...")

    export_notes(notes['note_name_by_id'], notes['note_groupid_by_id'], list_groups(), threads=1)
    open_dir_default_tool(EXPORT_TARGET_ROOT)