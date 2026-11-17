import copy
import unittest
from sop_demo.schema import Page,validate_page
from sop_demo.render import logical_table,svg

BOX={'x':0,'y':0,'w':100,'h':100}

def example():
    return {'number':1,'components':[
        {'id':'node1','kind':'flow_node','text':'HCN TTC','bbox':BOX},
        {'id':'node2','kind':'flow_node','text':'HCN NM','bbox':BOX},
        {'id':'daily','kind':'text','text':'Hằng ngày','bbox':BOX}],
        'diagrams':[{'id':'flow','bbox':BOX,'node_ids':['node1','node2'],'edges':[]}],
        'tables':[{'id':'table','bbox':BOX,'columns':[
            {'id':'col_flow','title':'Lưu đồ','role':'flowchart','x':0,'width':50},
            {'id':'col_time','title':'Thời gian','role':'timing','x':50,'width':50}],
            'rows':[{'id':'r1','y':0,'height':50,'source_band':'band1','anchor_ids':['node1']},
                    {'id':'r2','y':50,'height':50,'source_band':'band1','anchor_ids':['node2']}],
            'cells':[{'id':'fc','row':0,'column':0,'rowspan':2,'component_ids':[],'diagram_id':'flow','source_bbox':BOX},
                     {'id':'tc','row':0,'column':1,'rowspan':2,'component_ids':['daily'],'source_bbox':BOX}]}],
        'relations':[{'id':f'rel{i}','source':n,'target':'daily','kind':'timing_for','basis':'both','confidence':.9,'rationale':'shared'} for i,n in enumerate(['node1','node2'])],
        'warnings':[]}

class IntegrityTests(unittest.TestCase):
    def test_shared_cell_and_whole_diagram(self):
        p=validate_page(Page.model_validate(example()))
        rendered=logical_table(p,p.tables[0])
        self.assertEqual(rendered.count('rowspan="2"'),2)
        self.assertEqual(rendered.count('Hằng ngày'),1)
        self.assertEqual(len(p.relations),2)

    def test_dangling_edge(self):
        data=example(); data['diagrams'][0]['edges']=[{'id':'bad','source':'node1','target':'missing','points':[{'x':0,'y':0},{'x':1,'y':1}]}]
        with self.assertRaises(ValueError): validate_page(Page.model_validate(data))

    def test_overlap(self):
        data=example(); c=copy.deepcopy(data['tables'][0]['cells'][1]); c['id']='overlap'; data['tables'][0]['cells'].append(c)
        with self.assertRaises(ValueError): validate_page(Page.model_validate(data))

    def test_out_of_bounds_span(self):
        data=example(); data['tables'][0]['cells'][1]['rowspan']=3
        with self.assertRaises(ValueError): validate_page(Page.model_validate(data))

    def test_escape_untrusted_text(self):
        data=example(); data['components'][0]['text']='<script>alert(1)</script>'
        p=Page.model_validate(data)
        self.assertNotIn('<script>',svg(p))
        self.assertIn('&lt;script&gt;',svg(p))

    def test_duplicate_ids(self):
        data=example(); data['components'][1]['id']='node1'
        with self.assertRaises(ValueError): validate_page(Page.model_validate(data))

if __name__=='__main__': unittest.main()
