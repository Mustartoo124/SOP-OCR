"""Small vision capability probe before spending on full extraction."""
import json
from pathlib import Path
from .extract import client,image_data,ROOT

def main():
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('model'); args=ap.parse_args()
    r=client().chat.completions.create(model=args.model,max_tokens=800,messages=[{'role':'user','content':[
        {'type':'text','text':'Read this image. Return the exact Vietnamese title and first three flowchart node texts. Do not describe a generic document. If you cannot see the image, say so.'},
        {'type':'image_url','image_url':{'url':image_data(ROOT/'document/border.png')}}]}])
    print(json.dumps({'model':args.model,'text':r.choices[0].message.content,'usage':r.usage.model_dump() if r.usage else None},ensure_ascii=True))
if __name__=='__main__': main()
