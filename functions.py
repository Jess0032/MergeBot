import time
from PyPDF2 import PdfFileMerger
import os
from pathlib import Path
import shutil
import multivolumefile
from py7zr import SevenZipFile, FILTER_COPY


def merge_pdf(dirpath, filename):
    merged = PdfFileMerger()
    path = Path(dirpath)
    for WindowsPath in sorted(path.iterdir()):
        file = str(WindowsPath)
        merged.append(file)
    merged.write(f"{path.parent}/{filename}")
    merged.close()
    shutil.rmtree(str(path.absolute()))


def merge_txt(dirpath, filename):
    path = Path(dirpath)
    with open(f"{path.parent}/{filename}", "w") as out:
        for WindowsPath in sorted(path.iterdir()):
            with open(str(WindowsPath), "r") as read:
                out.write(read.read())
    shutil.rmtree(str(path.absolute()))


def zip_files(path, part_size):
    dir_files = path
    partsdir = Path(f"{dir_files.parent}/parts")
    size = int(part_size) if part_size else 1945.6
    copy_filter = [{"id": FILTER_COPY}]


    try:
        os.mkdir(partsdir)
    except Exception as e:
        raise e

    files = os.listdir(dir_files)

    filename_7z = files[0] + ".7z" if len(files) < 2 else "Compress" + str(time.strftime("%H%M%S")) + ".7z"

    with multivolumefile.open(
        f"{partsdir}/{filename_7z}", "wb", size * 1024 * 1024
    ) as target_archive:
        with SevenZipFile(target_archive, "w", filters=copy_filter) as archive:
            archive.writeall(dir_files)
    shutil.rmtree(str(dir_files.absolute()))

    return partsdir
