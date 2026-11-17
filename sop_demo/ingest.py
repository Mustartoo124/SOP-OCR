"""Render first; retain native text as evidence, never as layout truth."""
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import fitz
from PIL import Image
from .routing import native_layout

def prepare(source: Path, out: Path, selected: list[int] | None = None):
    out.mkdir(parents=True, exist_ok=True)
    assets = out/'assets'
    assets.mkdir(exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    original = source
    if source.suffix.lower() == '.docx':
        # Configure a headless runtime explicitly; no lossy paragraph-only conversion.
        executable = os.getenv('SOP_SOFFICE') or shutil.which('soffice')
        if not executable and os.name == 'nt':
            destination=out/(source.stem+'.pdf')
            subprocess.run(['powershell.exe','-NoProfile','-File',str(Path(__file__).with_name('word_to_pdf.ps1')),
                            '-Source',str(source.resolve()),'-Destination',str(destination.resolve())],
                           check=True,capture_output=True,timeout=180)
        elif not executable:
            raise RuntimeError('DOCX requires LibreOffice headless. Set SOP_SOFFICE to its soffice executable, or export Word to PDF first.')
        else:
            with tempfile.TemporaryDirectory(prefix='sop-lo-') as profile:
                subprocess.run([executable, f'-env:UserInstallation={Path(profile).as_uri()}',
                            '--headless','--convert-to','pdf','--outdir',str(out.resolve()),str(source.resolve())],
                           check=True, capture_output=True, timeout=180)
        source = out/(source.stem+'.pdf')
        if not source.exists(): raise RuntimeError('DOCX conversion produced no PDF')
    pages = []
    if source.suffix.lower() in {'.png','.jpg','.jpeg'}:
        image = Image.open(source).convert('RGB')
        image.save(assets/'page-1.png')
        pages.append(dict(number=1,image=assets/'page-1.png',native_text='',width=image.width,height=image.height))
    elif source.suffix.lower() == '.pdf':
        with fitz.open(source) as pdf:
            chosen = selected or list(range(1,len(pdf)+1))
            if any(n<1 or n>len(pdf) for n in chosen): raise ValueError('Page selection outside document')
            for n in chosen:
                page = pdf[n-1]
                pix = page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
                dest = assets/f'page-{n}.png'
                pix.save(dest)
                words = page.get_text('words')
                evidence = [{'text':w[4],'bbox':[round(w[0]/page.rect.width*1000,1),round(w[1]/page.rect.height*1000,1),round(w[2]/page.rect.width*1000,1),round(w[3]/page.rect.height*1000,1)]} for w in words]
                pages.append(dict(number=n,image=dest,native_text=evidence,width=pix.width,height=pix.height,layout=native_layout(page)))
    else:
        raise ValueError('Supported: PDF, DOCX, PNG, JPEG. Legacy DOC/XLSX not implemented.')
    return dict(source_name=original.name,source_sha256=digest), pages

def save_image_crops(page, image_path, out):
    image = Image.open(image_path)
    for index,c in enumerate(page.components):
        if c.kind != 'image': continue
        b=c.bbox
        crop=image.crop((int(b.x/1000*image.width),int(b.y/1000*image.height),int((b.x+b.w)/1000*image.width),int((b.y+b.h)/1000*image.height)))
        ref=f'assets/page-{page.number}-image-{index}.png'
        crop.save(out/ref)
        c.asset_ref=ref
