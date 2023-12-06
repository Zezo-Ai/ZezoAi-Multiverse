import math
import unittest

import os
import tracemalloc

import numpy
from pxr import Usd
from multiverse_parser import (WorldBuilder,
                               JointBuilder, JointType, JointProperty,
                               GeomType, GeomProperty)


class FactoryTestCase(unittest.TestCase):
    resource_path: str

    @classmethod
    def setUpClass(cls):
        tracemalloc.start()
        cls.resource_path = os.path.join(os.path.dirname(__file__), "..", "resources")

    def test_world_builder(self):
        file_path = os.path.join(self.resource_path, "output", "test_world_builder", "test.usda")
        world_builder = WorldBuilder(file_path=file_path)
        self.assertIsInstance(world_builder._stage, Usd.Stage)

        body_builder_0 = world_builder.add_body(body_name="body_0")
        self.assertEqual(body_builder_0.xform.GetPath(), "/body_0")

        body_builder_1 = world_builder.add_body(body_name="body_1", parent_body_name="body_0")
        self.assertEqual(body_builder_1.xform.GetPath(), "/body_0/body_1")

        body_builder_2 = world_builder.add_body(body_name="body_2", parent_body_name="body_0")
        self.assertEqual(body_builder_2.xform.GetPath(), "/body_0/body_2")

        body_builder_3 = world_builder.add_body(body_name="body_3", parent_body_name="body_2")
        self.assertEqual(body_builder_3.xform.GetPath(), "/body_0/body_2/body_3")

        body_builder_4 = world_builder.add_body(body_name="body_1", parent_body_name="body_2")
        self.assertEqual(body_builder_4, body_builder_1)

        with self.assertRaises(ValueError):
            world_builder.add_body(body_name="body_4", parent_body_name="body_abcxyz")

        body_builder_1.set_transform(pos=numpy.array([1.0, 0.0, 0.0]),
                                     quat=numpy.array([math.sqrt(2) / 2, 0.0, 0.0, math.sqrt(2) / 2]),
                                     scale=numpy.array([1.0, 1.0, 1.0]))
        body_1_xform = body_builder_1.xform
        body_1_local_transform = body_1_xform.GetLocalTransformation()
        body_1_local_pos = body_1_local_transform.ExtractTranslation()
        self.assertEqual(body_1_local_pos, (1.0, 0.0, 0.0))

        body_builder_3.set_transform(pos=numpy.array([1.0, 0.0, 0.0]),
                                     quat=numpy.array([math.sqrt(2) / 2, 0.0, 0.0, math.sqrt(2) / 2]),
                                     scale=numpy.array([1.0, 1.0, 1.0]),
                                     relative_to_xform=body_1_xform)

        geom_property = GeomProperty(geom_name="geom_1", geom_type=GeomType.CUBE)
        geom_builder_1 = body_builder_1.add_geom(geom_property=geom_property)
        geom_1_xform = geom_builder_1.xform
        self.assertEqual(geom_1_xform.GetPath(), "/body_0/body_1/geom_1")

        geom_builder_1.set_transform(pos=numpy.array([0.1, 0.2, 3.0]),
                                     quat=numpy.array([math.sqrt(2) / 2, 0.0, 0.0, math.sqrt(2) / 2]),
                                     scale=numpy.array([1.0, 1.0, 1.0]))
        geom_1_local_transform = geom_1_xform.GetLocalTransformation()
        geom_1_local_pos = geom_1_local_transform.ExtractTranslation()
        self.assertEqual(geom_1_local_pos, (0.1, 0.2, 3.0))

        geom_builder_1.set_attribute(prefix="primvars", displayColor=[(0, 0, 0)])
        geom_builder_1.set_attribute(prefix="primvars", displayOpacity=[1])

        joint_property = JointProperty(joint_name="joint_0",
                                       joint_parent_prim=body_builder_1.xform.GetPrim(),
                                       joint_child_prim=body_builder_3.xform.GetPrim(),
                                       joint_type=JointType.FIXED)
        joint_builder = JointBuilder(joint_property=joint_property)
        self.assertEqual(joint_builder.path, "/body_0/body_1/joint_0")
        self.assertEqual(joint_builder.type, JointType.FIXED)

        mesh_builder, _ = geom_builder_1.add_mesh(mesh_file_path=os.path.join(self.resource_path, "input", "milk_box",
                                                                              "meshes", "usd", "obj", "milk_box.usda"))
        self.assertEqual(mesh_builder.xform.GetPath(), "/milk_box")
        self.assertTrue(geom_builder_1.stage.GetPrimAtPath("/body_0/body_1/geom_1/SM_MilkBox").IsValid())

        world_builder.export()
        self.assertTrue(os.path.exists(file_path))

    @classmethod
    def tearDownClass(cls):
        tracemalloc.stop()


if __name__ == '__main__':
    unittest.main()
