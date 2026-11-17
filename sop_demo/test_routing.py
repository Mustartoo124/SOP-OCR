import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from sop_demo.routing import extract_hybrid,plan,map_page
from sop_demo.schema import Page
from sop_demo.test_schema import example

class RoutingTests(unittest.TestCase):
    def info(self,out):
        (out/'assets').mkdir(exist_ok=True)
        path=out/'assets/page-1.png'; Image.new('RGB',(1000,1000),'white').save(path)
        return dict(number=1,image=path,native_text=[],layout=dict(lines=[dict(text='Local prose',bbox=dict(x=50,y=20,w=200,h=20))],regions=[],images=[],warnings=[]))

    def test_prose_no_vlm(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder); info=self.info(out); extractor=Mock(side_effect=AssertionError('VLM called for prose'))
            p,usage,audit=extract_hybrid(info,out,'unused',True,'prompt',extractor)
            self.assertEqual(p.components[0].text,'Local prose')
            self.assertEqual(usage,[]); self.assertEqual(audit['vlm_calls'],0)
            extractor.assert_not_called()

    def test_mixed_crops_and_merges(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder); info=self.info(out)
            info['layout']['regions']=[dict(x=100,y=200,w=500,h=500)]
            model_page=Page(number=1,components=[dict(id='node',kind='flow_node',text='Process',bbox=dict(x=100,y=100,w=200,h=100))],tables=[],diagrams=[],relations=[],warnings=[])
            extractor=Mock(return_value=(model_page,[{'usage':{}}]))
            p,_,audit=extract_hybrid(info,out,'unused',True,'prompt',extractor)
            self.assertEqual(len(p.components),2)
            self.assertEqual(p.components[1].text,'Local prose')
            self.assertGreater(p.components[0].bbox.y,200)
            sent=extractor.call_args.args[0]
            self.assertNotEqual(sent['image'],info['image'])
            self.assertEqual(sent['native_text'],[])
            self.assertEqual(audit['vlm_calls'],1)

    def test_scan_requires_declaration(self):
        with tempfile.TemporaryDirectory() as folder:
            info=self.info(Path(folder)); info.pop('layout')
            with self.assertRaisesRegex(RuntimeError,'requires --regions'): plan(info)

    def test_scan_prose_uses_local_ocr(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder); info=self.info(out); lines=info.pop('layout')['lines']
            extractor=Mock(side_effect=AssertionError('VLM called'))
            with patch('sop_demo.routing.ocr_lines',return_value=lines) as ocr:
                p,_,audit=extract_hybrid(info,out,'unused',True,'prompt',extractor,{'1':[]})
                ocr.assert_called_once()
            self.assertEqual(audit['text_engine'],'tesseract')
            self.assertEqual(p.components[0].text,'Local prose'); extractor.assert_not_called()

    def test_transform_preserves_graph_and_spans(self):
        p=Page.model_validate(example()); original=p.model_dump()
        map_page(p,dict(x=100,y=200,w=500,h=400))
        self.assertEqual(p.components[0].bbox.x,100)
        self.assertEqual(p.components[0].bbox.h,40)
        self.assertEqual(p.tables[0].cells[0].rowspan,2)
        self.assertEqual(p.relations[0].model_dump(),original['relations'][0])
        self.assertEqual(p.tables[0].columns[1].x,125)

if __name__=='__main__': unittest.main()
