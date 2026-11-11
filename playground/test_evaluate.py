"""Diagnostic controls only. These synthetic predictions are never model results."""
import copy
import unittest

from common import FIXTURES,read_json,box
from evaluate import score_page,match_regions
from adapters import CellHTMLParser


def control_prediction(page):
    out=dict(blocks=[],tables=[],texts=[])
    for item in page["components"]:
        if item["type"]=="table":
            cells=[copy.deepcopy(c) for c in page["components"] if c["type"]=="table_cell" and c["parent_id"]==item["id"]]
            for c in cells: c["text"]=""
            out["tables"].append(dict(id=item["id"],bbox=item["bbox"],rows=item["rows"],cols=item["cols"],cells=cells))
            out["blocks"].append(dict(id=item["id"],type="table",label="table",bbox=item["bbox"]))
        elif item["type"] in ("image","diagram"):
            out["blocks"].append(dict(id=item["id"],type="figure",label="picture",bbox=item["bbox"],parent_ref=None))
    return out


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages=read_json(FIXTURES/"sop_digital.ground_truth.json")["pages"]

    def test_bottom_left_conversion(self):
        self.assertEqual(box(dict(l=10,t=180,r=30,b=160,coord_origin="BOTTOMLEFT"),100,200),[10,20,30,40])

    def test_equal_shape_does_not_hide_wrong_merge(self):
        gt=self.pages[1]; pred=control_prediction(gt)
        merged=next(c for c in pred["tables"][0]["cells"] if c["rowspan"]>1)
        merged["rowspan"]=1
        row=score_page(gt,pred)
        self.assertTrue(row["table_matches"][0]["shape_exact"])
        self.assertFalse(row["table_matches"][0]["span_grid_exact"])

    def test_partial_layout_grid_not_scored_as_canonical_grid(self):
        gt=self.pages[2]; pred=control_prediction(gt)
        pred["tables"][0]["rows"]=99
        match=score_page(gt,pred)["table_matches"][0]
        self.assertNotIn("span_grid_exact",match)

    def test_one_predicted_figure_cannot_match_two_targets(self):
        targets=[dict(bbox=[0,0,10,10]),dict(bbox=[0,0,10,10])]
        self.assertEqual(len(match_regions(targets,[dict(bbox=[0,0,10,10])])),1)

    def test_geometry_inside_cell_does_not_prove_ownership(self):
        gt=self.pages[3]; row=score_page(gt,control_prediction(gt))
        self.assertIn("nested_figure_parent_unresolved",[i["type"] for i in row["issues"]])

    def test_table_ancestor_through_group_is_preserved(self):
        gt=self.pages[3]; pred=control_prediction(gt)
        figure=next(b for b in pred["blocks"] if b["type"]=="figure" and b["bbox"][1]>200)
        figure["parent_ref"]="group_1"
        pred["containers"]=[dict(id="group_1",type="container",parent_ref=pred["tables"][0]["id"])]
        check=next(f for f in score_page(gt,pred)["figure_matches"] if f["prediction_id"]==figure["id"])
        self.assertTrue(check["nested_explicit"])

    def test_cell_parent_is_checked_separately_from_table(self):
        gt=self.pages[3]; pred=control_prediction(gt)
        target=next(i for i in gt['components'] if i['type']=='image' and i.get('parent_id'))
        owner=next(i for i in gt['components'] if i['id']==target['parent_id'])
        figure=next(b for b in pred['blocks'] if b['id']==target['id'])
        figure['parent_ref']='predicted_cell'
        pred['containers']=[dict(id='predicted_cell',type='table_cell',parent_ref=pred['tables'][0]['id'],
            **{k:owner[k] for k in ('row','col','rowspan','colspan')})]
        check=next(f for f in score_page(gt,pred)['figure_matches'] if f['gt_id']==target['id'])
        self.assertTrue(check['nested_explicit']);self.assertTrue(check['cell_ownership_verified'])
        pred['containers'][0]['col']+=1
        check=next(f for f in score_page(gt,pred)['figure_matches'] if f['gt_id']==target['id'])
        self.assertTrue(check['nested_explicit']);self.assertFalse(check['cell_ownership_verified'])

    def test_partial_figure_crop_is_flagged_even_if_iou_passes(self):
        gt=self.pages[3]; pred=control_prediction(gt)
        figure=next(b for b in pred["blocks"] if b["type"]=="figure" and b["bbox"][1]>200)
        a,b,c,d=figure["bbox"]; figure["bbox"]=[a,b,a+(c-a)*.7,d]
        row=score_page(gt,pred)
        self.assertIn("figure_crop_may_be_incomplete",[i["type"] for i in row["issues"]])

    def test_html_rowspan_occupancy(self):
        p=CellHTMLParser()
        p.feed('<table><tr><td rowspan="2">A</td><td>B</td></tr><tr><td>C</td></tr></table>')
        self.assertEqual([(c["row"],c["col"],c["rowspan"]) for c in p.cells],[(0,0,2),(0,1,1),(1,1,1)])


if __name__=="__main__": unittest.main()
