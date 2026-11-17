import json
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest
from sop_demo.schema import Document
from sop_demo.test_schema import example

class AppTests(unittest.TestCase):
    def test_edit_preserves_relations_and_spans(self):
        doc=Document(source_name='fixture',source_sha256='test',pages=[example()],page_images={'1':'unused.png'})
        app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30)
        app.session_state['doc']=doc.model_dump()
        app.session_state['folder']=None
        app.run()
        self.assertEqual(len(app.exception),0)
        app.text_area[0].set_value('Edited node')
        next(b for b in app.button if b.label=='Áp dụng').click().run()
        self.assertEqual(len(app.exception),0)
        result=app.session_state['doc']['pages'][0]
        self.assertEqual(result['components'][0]['text'],'Edited node')
        self.assertEqual(result['relations'],doc.model_dump()['pages'][0]['relations'])
        self.assertEqual(result['tables'],doc.model_dump()['pages'][0]['tables'])

if __name__=='__main__': unittest.main()
