"""select_by_dimensions の振る舞いを確かめるテスト。

Blender の background モードで実行する:

    blender --background --factory-startup --python tests/test_select_by_dimensions.py
"""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import bpy
import numpy as np

import select_by_dimensions as m


def clear_scene() -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def add_cube(name: str, size: float, location=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    ob = bpy.context.active_object
    ob.name = name
    return ob


def selected_names() -> list[str]:
    return sorted(ob.name for ob in bpy.context.selected_objects)


class SelectByDimensionsTest(unittest.TestCase):
    """寸法による選択・解除と、寸法の測り方の仕様。"""

    @classmethod
    def setUpClass(cls) -> None:
        m.register()

    @classmethod
    def tearDownClass(cls) -> None:
        m.unregister()

    def setUp(self) -> None:
        clear_scene()
        add_cube("CubeSmall", 1.0)
        add_cube("CubeBig", 10.0, location=(20.0, 0.0, 0.0))
        bpy.ops.object.select_all(action="DESELECT")

    def select(self, **kwargs) -> None:
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.object.select_by_dimensions(action="SELECT", **kwargs)

    def test_Z寸法が5より大きい立方体だけが選ばれる(self) -> None:
        self.select(use_z=True, z_op="GT", z=5.0)
        self.assertEqual(selected_names(), ["CubeBig"])

    def test_Z寸法が5より小さい立方体だけが選ばれる(self) -> None:
        self.select(use_z=True, z_op="LT", z=5.0)
        self.assertEqual(selected_names(), ["CubeSmall"])

    def test_許容差内の等値判定で大きい立方体が選ばれる(self) -> None:
        self.select(use_x=True, x_op="EQ", x=10.0, x_tol=0.5)
        self.assertEqual(selected_names(), ["CubeBig"])

    def test_許容差外の等値判定では何も選ばれない(self) -> None:
        self.select(use_x=True, x_op="EQ", x=10.5, x_tol=0.01)
        self.assertEqual(selected_names(), [])

    def test_全軸が無効なら何も選ばれない(self) -> None:
        bpy.ops.object.select_by_dimensions(
            action="SELECT", use_x=False, use_y=False, use_z=False)
        self.assertEqual(selected_names(), [])

    def test_DESELECTは条件に合うものだけ解除する(self) -> None:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.select_by_dimensions(
            action="DESELECT", use_z=True, z_op="GT", z=5.0)
        self.assertEqual(selected_names(), ["CubeSmall"])

    def test_頂点ゼロのメッシュはスキップされる(self) -> None:
        bpy.context.scene.collection.objects.link(
            bpy.data.objects.new("EmptyMesh", bpy.data.meshes.new("empty_mesh")))
        self.select(use_z=True, z_op="GT", z=5.0)
        self.assertEqual(selected_names(), ["CubeBig"])

    def test_モディファイアの結果が寸法に反映される(self) -> None:
        ob = bpy.data.objects["CubeSmall"]
        modifier = ob.modifiers.new("Array", "ARRAY")
        modifier.count = 3
        modifier.relative_offset_displace[0] = 1.0
        depsgraph = bpy.context.evaluated_depsgraph_get()
        self.assertTrue(np.allclose(
            m.get_evaluated_dimensions(depsgraph, ob), [3.0, 1.0, 1.0]))

    def test_親の回転が寸法に反映される(self) -> None:
        bpy.ops.object.empty_add(rotation=(0.0, 0.0, math.radians(45.0)))
        parent = bpy.context.active_object
        child = add_cube("Child", 1.0)
        child.parent = parent
        depsgraph = bpy.context.evaluated_depsgraph_get()
        self.assertTrue(np.allclose(
            m.get_evaluated_dimensions(depsgraph, child),
            [math.sqrt(2.0), math.sqrt(2.0), 1.0]))

    def test_負のスケールでも寸法は正の大きさになる(self) -> None:
        ob = bpy.data.objects["CubeBig"]
        ob.scale = (-1.0, 1.0, 1.0)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        self.assertTrue(np.allclose(
            m.get_evaluated_dimensions(depsgraph, ob), [10.0, 10.0, 10.0]))

    def test_改名しても同じオブジェクトが選ばれる(self) -> None:
        bpy.data.objects["CubeBig"].name = "RenamedBig"
        self.select(use_z=True, z_op="GT", z=5.0)
        self.assertEqual(selected_names(), ["RenamedBig"])

    def test_削除されたオブジェクトがあっても落ちない(self) -> None:
        bpy.data.objects.remove(bpy.data.objects["CubeBig"], do_unlink=True)
        self.select(use_z=True, z_op="GT", z=5.0)
        self.assertEqual(selected_names(), [])


if __name__ == "__main__":
    unittest.main(argv=["test"])
