"""Create explicitly manual, partial schema example; never label it a VLM output."""
import hashlib
import shutil
from pathlib import Path
from .schema import Document,Page,validate_document

def main():
    root=Path(__file__).resolve().parents[1]
    out=root/'sop_demo/runs/manual-schema-example'; (out/'assets').mkdir(parents=True,exist_ok=True)
    source=root/'document/border.png'; shutil.copyfile(source,out/'assets/page-1.png')
    def box(x,y,w,h): return dict(x=x,y=y,w=w,h=h)
    specs=[
        ('ttc','flow_node','HCN Giao tại TTC: WV-PTNL-06-F1',box(298,82,171,59),'document'),
        ('nm','flow_node','HCN Giao tại NM: WV-PTNL-06-F2',box(298,147,171,42),'document'),
        ('supply','flow_node','Cung cấp hồ sơ thu mua STNL',box(143,151,115,52),'rectangle'),
        ('daily','text','Hằng ngày',box(477,82,65,228),'none'),
        ('people','text','- Đại diện Trạm/KCS\n- Nhân viên tiếp nhận/Nhân viên Kho',box(554,82,94,107),'none'),
        ('desc1','text','Bảng theo dõi quá trình giao - nhận sữa nông hộ tại NM: gửi bảng có đủ chữ ký cho Ban PTNL/QA vào cuối 2 buổi nhận sữa để Ban PTNL/QA kiểm tra hồ sơ và gửi KTO',box(658,82,326,58),'none'),
        ('desc2','text','Bảng theo dõi quá trình giao - nhận sữa nông hộ tại NM: Gửi bảng có đủ chữ ký cho Ban KTO vào cuối 2 buổi nhận sữa',box(658,147,326,42),'none')]
    components=[dict(id=i,kind=k,text=t,bbox=b,shape=s,confidence=1) for i,k,t,b,s in specs]
    table=dict(id='table',bbox=box(61,75,930,130),columns=[
        dict(id='flowcol',title='Lưu đồ',role='flowchart',x=61,width=411),
        dict(id='timecol',title='Thời gian',role='timing',x=472,width=78),
        dict(id='peoplecol',title='Trách nhiệm',role='responsibility',x=550,width=102),
        dict(id='desccol',title='Mô tả',role='description',x=652,width=339)],
        rows=[dict(id=f'row{i}',y=y,height=h,source_band='step1',anchor_ids=[anchor]) for i,y,h,anchor in [(1,82,65,'ttc'),(2,147,58,'nm')]],cells=[])
    for ident,r,c,span,ids,did,b in [
        ('flowcell',0,0,2,[],'flow',box(61,75,411,130)),
        ('timecell',0,1,2,['daily'],None,box(477,82,65,228)),
        ('peoplecell',0,2,2,['people'],None,box(554,82,94,107)),
        ('desc1cell',0,3,1,['desc1'],None,box(658,82,326,58)),
        ('desc2cell',1,3,1,['desc2'],None,box(658,147,326,42))]:
        table['cells'].append(dict(id=ident,row=r,column=c,rowspan=span,component_ids=ids,diagram_id=did,source_bbox=b))
    relations=[]
    for node,description in [('ttc','desc1'),('nm','desc2')]:
        for target,kind in [(description,'describes'),('daily','timing_for'),('people','responsible_for')]:
            relations.append(dict(id=f'{node}_{target}',source=node,target=target,kind=kind,basis='both',confidence=1,rationale='Manual illustrative mapping from user-provided example'))
    page=Page(number=1,components=components,tables=[table],diagrams=[dict(id='flow',bbox=box(130,75,345,135),node_ids=['ttc','nm','supply'],edges=[
        dict(id='input_ttc',source='ttc',target='supply',kind='input',points=[dict(x=298,y=111),dict(x=277,y=111),dict(x=277,y=177),dict(x=258,y=177)]),
        dict(id='input_nm',source='nm',target='supply',kind='input',points=[dict(x=298,y=168),dict(x=277,y=168),dict(x=277,y=177),dict(x=258,y=177)])])],relations=relations,
        warnings=['VÍ DỤ SCHEMA VIẾT TAY, CHỈ MỘT PHẦN của border.png. Không phải output VLM hay bản trích xuất đầy đủ. Hằng ngày trong bản gốc còn liên quan các hàng khác ngoài phạm vi ví dụ.'])
    doc=Document(source_name=source.name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),pages=[page],page_images={'1':'assets/page-1.png'},provenance={'origin':'manual_partial_example','not_a_model_result':True})
    validate_document(doc)
    (out/'document.json').write_text(doc.model_dump_json(indent=2),encoding='utf-8')
    print(out)

if __name__=='__main__': main()
