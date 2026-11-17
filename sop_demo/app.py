"""Run: python -m streamlit run sop_demo/app.py"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import uuid
import streamlit as st
import streamlit.components.v1 as ui
from sop_demo.extract import run, DEFAULT_MODEL, ROOT
from sop_demo.schema import Document,validate_document
from sop_demo.render import svg,logical_table

st.set_page_config(page_title='SOP · Document lab',layout='wide')
st.title('SOP · Document lab')
st.caption('PDF / Word → components, flowchart, logical rows → editable JSON')
with st.sidebar:
    st.header('1 · Input')
    upload=st.file_uploader('Chọn tài liệu',type=['pdf','docx','png','jpg','jpeg'])
    model=st.text_input('LiteLLM model',value=DEFAULT_MODEL)
    selection=st.text_input('Trang (trống = tất cả)',placeholder='1,2,3')
    mode=st.selectbox('Cách xử lý',['hybrid','full-vlm'])
    regions_upload=st.file_uploader('Vùng bảng/diagram theo trang (JSON, cần cho scan/ảnh)',type=['json'],key='regions')
    review=st.checkbox('VLM kiểm tra lại ảnh và JSON',value=True)
    st.caption('Hybrid: text native/OCR cục bộ; chỉ vùng cấu trúc gửi VLM. Trang text không gọi model. Scan/ảnh cần khai báo vùng; [] xác nhận trang chỉ có text.')
    if st.button('Trích xuất',disabled=upload is None,type='primary'):
        folder=ROOT/'sop_demo/runs'/uuid.uuid4().hex
        folder.mkdir(parents=True)
        path=folder/Path(upload.name).name
        path.write_bytes(upload.getvalue())
        try:
            selected=[int(n.strip()) for n in selection.split(',')] if selection.strip() else None
            with st.status('Đang xử lý...',expanded=True) as status:
                regions=json.loads(regions_upload.getvalue()) if regions_upload else None
                doc=run(path,folder,model,selected,review,progress=st.write,mode=mode,regions=regions)
                status.update(label='Đã trích xuất',state='complete')
            st.session_state.doc=doc.model_dump(); st.session_state.folder=str(folder)
        except Exception as exc:
            st.error(f'{type(exc).__name__}: xử lý thất bại. Kiểm tra cấu hình model, renderer và file phản hồi trong thư mục run.')
            st.caption(str(folder))
    st.header('2 · Open result')
    results=sorted((ROOT/'sop_demo/runs').glob('*/document.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if results:
        existing=st.selectbox('Kết quả đã lưu',results,format_func=lambda p:p.parent.name)
        if st.button('Mở kết quả'):
            st.session_state.doc=validate_document(Document.model_validate_json(existing.read_text(encoding='utf-8'))).model_dump()
            st.session_state.folder=str(existing.parent)
    incoming=st.file_uploader('Hoặc mở JSON',type=['json'])
    if incoming and st.button('Nạp JSON'):
        try:
            st.session_state.doc=validate_document(Document.model_validate_json(incoming.getvalue())).model_dump()
            st.session_state.folder=None
        except ValueError as exc: st.error(str(exc))

if 'doc' not in st.session_state:
    st.info('Chọn tài liệu để chạy model hoặc mở kết quả JSON đã lưu.'); st.stop()
doc=Document.model_validate(st.session_state.doc)
number=st.selectbox('Trang',[p.number for p in doc.pages])
page=next(p for p in doc.pages if p.number==number)
folder=st.session_state.get('folder')
for warning in page.warnings: st.warning(warning)
if not page.components:
    st.error('Kết quả rỗng: chưa trích xuất được nội dung. Không sử dụng làm output thành công.')
left,right=st.columns(2)
with left:
    st.subheader('Nguồn')
    if folder:
        root=Path(folder).resolve(); source=(root/doc.page_images[str(number)]).resolve()
        if source.is_relative_to(root) and source.exists(): st.image(str(source),use_container_width=True)
    else: st.caption('Ảnh nguồn không đi kèm JSON tải lên. Mở kết quả cục bộ để đối chiếu.')
with right:
    st.subheader('Dựng lại từ JSON')
    tab1,tab2=st.tabs(['Hàng liên kết & cell gộp','Bố cục nguồn'])
    with tab1:
        for table in page.tables: ui.html(logical_table(page,table,folder),height=1000,scrolling=True)
        if not page.tables: ui.html(svg(page),height=900,scrolling=True)
    with tab2: ui.html(svg(page),height=1000,scrolling=True)

st.subheader('Chỉnh sửa text')
choices={c.id:c for c in page.components}
if choices:
    cid=st.selectbox('Component',list(choices),format_func=lambda key:f'{key} · {choices[key].text[:85]}')
    with st.form(f'edit-{number}-{cid}'):
        value=st.text_area('Nội dung',value=choices[cid].text,height=130)
        if st.form_submit_button('Áp dụng'):
            for p in st.session_state.doc['pages']:
                if p['number']==number:
                    for c in p['components']:
                        if c['id']==cid: c['text']=value
            st.rerun()
with st.expander('Relations và cấu trúc JSON'):
    st.dataframe([r.model_dump() for r in page.relations],use_container_width=True)
    st.json(st.session_state.doc,expanded=False)
serialized=json.dumps(st.session_state.doc,ensure_ascii=False,indent=2)
st.download_button('Tải JSON đã chỉnh sửa',serialized,file_name='document.edited.json',mime='application/json')
if folder and st.button('Lưu bản chỉnh sửa cục bộ'):
    validate_document(Document.model_validate(st.session_state.doc))
    (Path(folder)/'document.edited.json').write_text(serialized,encoding='utf-8')
    st.success('Đã lưu document.edited.json')
