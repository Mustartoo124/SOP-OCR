"""Download a pinned Windows Poppler build for independent visual QA, into tmp/."""
from pathlib import Path
import hashlib
import urllib.request
import zipfile

root=Path(__file__).resolve().parents[1]/"tmp"/"poppler"
root.mkdir(parents=True,exist_ok=True)
archive=root/"Release-26.09.0-0.zip"
url="https://github.com/oschwartz10612/poppler-windows/releases/download/v26.09.0-0/Release-26.09.0-0.zip"
if not archive.exists():
    urllib.request.urlretrieve(url,archive)
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
if checksum!="7a6f256a0ddf7536182246a5733331bf4677cbcc34f4663774947ad34556c8d0":
    raise RuntimeError("Poppler archive checksum does not match the pinned build")
with zipfile.ZipFile(archive) as z:
    for member in z.infolist():
        target=(root/member.filename).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError("Unsafe archive path")
    z.extractall(root)
print("Archive SHA256:",checksum)
print("pdftoppm:",next(root.rglob("pdftoppm.exe")))
