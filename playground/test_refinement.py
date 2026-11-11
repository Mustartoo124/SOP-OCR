"""Geometry tests use generated shapes with different coordinates from the SOP fixtures."""
import unittest
import cv2
import numpy as np
from refinement import cell_grid,raster_tables,diagrams_in_tables,compose_text


class GeometryTests(unittest.TestCase):
    def test_merged_cells_recover_rowspan_and_colspan(self):
        grid=cell_grid([[10,20,40,80],[40,20,70,50],[70,20,100,50],[40,50,100,80]])
        self.assertEqual((grid['rows'],grid['cols']),(2,3))
        self.assertEqual({(c['row'],c['col'],c['rowspan'],c['colspan']) for c in grid['cells']},
                         {(0,0,2,1),(0,1,1,1),(0,2,1,1),(1,1,1,2)})

    def test_grid_with_missing_occupancy_is_not_accepted(self):
        self.assertIsNone(cell_grid([[0,0,20,20],[20,0,40,10]]))

    def test_grid_translation_does_not_change_structure(self):
        for shift in (0,47):
            image=np.full((1400,1000,3),255,np.uint8)
            for x in (100,500,900):cv2.line(image,(x,100+shift),(x,1000+shift),(40,40,40),2)
            for y in (100,400,700,1000):cv2.line(image,(100,y+shift),(900,y+shift),(40,40,40),2)
            tables,*_=raster_tables(image,1000,1400)
            self.assertEqual(len(tables),1)
            self.assertEqual((tables[0]['rows'],tables[0]['cols']),(3,2))

    def test_connected_shapes_form_diagram_and_grid_does_not(self):
        image=np.full((1400,1000,3),255,np.uint8)
        for x in (100,600,900):cv2.line(image,(x,100),(x,1000),(40,40,40),2)
        for y in (100,500,1000):cv2.line(image,(100,y),(900,y),(40,40,40),2)
        for y in (180,350):cv2.rectangle(image,(200,y),(400,y+60),(0,0,0),2)
        cv2.line(image,(300,240),(300,350),(0,0,0),2)
        tables,binary,h,v=raster_tables(image,1000,1400)
        for i,t in enumerate(tables):t['id']=f'table_{i}'
        figures,_,_=diagrams_in_tables(image,tables,[],1000,1400,binary,cv2.bitwise_or(h,v))
        self.assertEqual(len(figures),1)
        self.assertEqual(figures[0]['node_count'],2)
        self.assertLess(figures[0]['bbox'][0],200)
        self.assertGreater(figures[0]['bbox'][3],410)

    def test_text_keeps_lines_and_left_to_right_words(self):
        tokens=[dict(text='B',bbox=[30,10,40,20]),dict(text='A',bbox=[10,10,20,20]),dict(text='C',bbox=[10,40,20,50])]
        self.assertEqual(compose_text(tokens),'A B\nC')


if __name__=='__main__':unittest.main()
