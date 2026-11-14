# SPDX-FileCopyrightText: 2025 todashuta
#
# SPDX-License-Identifier: GPL-3.0-or-later


import math
import operator
from collections.abc import Callable
from typing import Literal

import bpy
import numpy as np
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
)
from bpy.types import (
    AddonPreferences,
    Context,
    Depsgraph,
    Object,
    Operator,
    UILayout,
    VIEW3D_MT_select_object,
    WindowManager,
)

OperatorResult = set[
    Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]
]

AXES = ("x", "y", "z")

ACTION_ITEMS = [
    ("SELECT", "Select", ""),
    ("DESELECT", "Deselect", ""),
]

COMPARE_ITEMS = [
    ("EQ", "Equal", ""),
    ("GT", "Greater", ""),
    ("LT", "Less", ""),
]


def get_evaluated_dimensions(depsgraph: Depsgraph, obj: Object) -> np.ndarray | None:
    """評価済みメッシュのワールド空間寸法を返す。測れないオブジェクトは None。

    ジオメトリを持たないオブジェクト (Empty, Camera, Light など) は
    to_mesh() が RuntimeError を投げるので、呼び出し側でスキップする。
    """
    obj_eval = obj.evaluated_get(depsgraph)
    try:
        mesh = obj_eval.to_mesh()
    except RuntimeError:
        return None

    # to_mesh() が成功したあとは、どの経路で抜けても to_mesh_clear() を通す。
    # 途中の例外で解放を逃すとテンポラリメッシュが残り続けるため finally に置く。
    try:
        vertex_count = len(mesh.vertices)
        if vertex_count == 0:
            # 頂点ゼロだと max() が ValueError になる。
            return None

        # 頂点ごとに Python 側で行列積を回すと遅くなるので、座標をまとめて
        # 取ってから numpy でアフィン変換する。
        coords = np.empty(vertex_count * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", coords)

        matrix = np.array(obj_eval.matrix_world)
        world = coords.reshape(vertex_count, 3) @ matrix[:3, :3].T + matrix[:3, 3]
        return world.max(axis=0) - world.min(axis=0)
    finally:
        obj_eval.to_mesh_clear()


# EQ は許容差つきで判定するので、ここには入れない。
COMPARE_FUNCS: dict[str, Callable[[float, float], bool]] = {
    "GT": operator.gt,
    "LT": operator.lt,
}


class SelectByDimensions(Operator):
    """Select/Deselect by Dimensions"""
    bl_idname = "object.select_by_dimensions"
    bl_label = "Select by Dimensions"
    # Blender はクラス属性の set を読む。ClassVar にすると ty が基底クラスの
    # インスタンス変数の上書きだと判定するので、ruff 側だけ抑制する。
    bl_options = {"REGISTER", "UNDO"}  # noqa: RUF012

    action: EnumProperty(name="Action", default="SELECT", items=ACTION_ITEMS)  # type: ignore

    use_x: BoolProperty() # type: ignore
    use_y: BoolProperty() # type: ignore
    use_z: BoolProperty(default=True) # type: ignore

    x_op: EnumProperty(name="Compare", default="GT", items=COMPARE_ITEMS)  # type: ignore
    y_op: EnumProperty(name="Compare", default="GT", items=COMPARE_ITEMS)  # type: ignore
    z_op: EnumProperty(name="Compare", default="GT", items=COMPARE_ITEMS)  # type: ignore

    x: FloatProperty(step=10, min=0) # type: ignore
    y: FloatProperty(step=10, min=0) # type: ignore
    z: FloatProperty(step=10, min=0, default=5.0) # type: ignore

    x_tol: FloatProperty(name="Tolerance", min=0.0, default=2.0) # type: ignore
    y_tol: FloatProperty(name="Tolerance", min=0.0, default=2.0) # type: ignore
    z_tol: FloatProperty(name="Tolerance", min=0.0, default=2.0) # type: ignore

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.mode == "OBJECT" and len(context.selectable_objects) > 0

    def execute(self, context: Context) -> OperatorResult:
        # Blender はオペレータの __init__ を複数回呼ぶことがある。__init__ で
        # キャッシュを作ると redo のたびに空に戻るので、execute の初回で作る。
        if not hasattr(self, "_dimensions_cache"):
            self._dimensions_cache: dict[str, np.ndarray | None] = {}

        if not self._dimensions_cache:
            self._measure(context)

        select = self.action == "SELECT"
        # キーをオブジェクト自体にすると、Blender の undo で StructRNA の
        # 参照が無効になったときにキャッシュがヒットせず、選択がすべて外れる。
        # 名前は undo でも無効にならないので、名前から引き直す。
        for name, dimensions in self._dimensions_cache.items():
            if dimensions is None:
                continue
            ob = bpy.data.objects.get(name)
            if ob is None:
                # 削除済みのオブジェクト。触ると ReferenceError になる。
                continue
            if self._matches(dimensions):
                ob.select_set(select)
        return {"FINISHED"}

    def _measure(self, context: Context) -> None:
        wm: WindowManager = context.window_manager # type: ignore
        targets = context.selectable_objects
        wm.progress_begin(0, len(targets))
        skipped = 0
        try:
            depsgraph = context.evaluated_depsgraph_get()
            for i, ob in enumerate(targets):
                dimensions = get_evaluated_dimensions(depsgraph, ob)
                self._dimensions_cache[ob.name] = dimensions
                if dimensions is None:
                    skipped += 1
                wm.progress_update(i)
        finally:
            # 途中で例外が出てもプログレスバーを閉じる。
            wm.progress_end()

        if skipped:
            # 測れないものは黙って飛ばすと理由が分からないので知らせる。
            self.report({"INFO"}, f"{skipped} object(s) skipped: no dimensions available")

    def _matches(self, dimensions: np.ndarray) -> bool:
        checked = False
        for axis, size in zip(AXES, dimensions):
            if not getattr(self, f"use_{axis}"):
                continue
            checked = True

            target = getattr(self, axis)
            if getattr(self, f"{axis}_op") == "EQ":
                if not math.isclose(size, target, abs_tol=getattr(self, f"{axis}_tol")):
                    return False
            elif not COMPARE_FUNCS[getattr(self, f"{axis}_op")](size, target):
                return False

        # どの軸も有効になっていなければ何も選ばない。全部選ぶより安全側に倒す。
        return checked

    def draw(self, context: Context) -> None:
        layout: UILayout = self.layout # type: ignore
        #layout.use_property_split = True

        layout.prop(self, "action")
        layout.separator()

        for axis in AXES:
            row = layout.row()
            row.prop(self, f"use_{axis}", text="")

            subrow = row.row()
            subrow.enabled = getattr(self, f"use_{axis}")
            subrow.label(text=axis.upper())
            subrow.prop(self, f"{axis}_op", text="")
            subrow.prop(self, f"{axis}", slider=False, text="")
            if getattr(self, f"{axis}_op") == "EQ":
                subrow.prop(self, f"{axis}_tol")


def menu_func(self, context) -> None:
    layout: UILayout = self.layout
    layout.separator()

    select_op = layout.operator(
            SelectByDimensions.bl_idname, text="Select by Dimensions")
    select_op.action = "SELECT"

    deselect_op = layout.operator(
            SelectByDimensions.bl_idname, text="Deselect by Dimensions")
    deselect_op.action = "DESELECT"


class SELECT_BY_DIMENSIONS_Preferences(AddonPreferences):
    bl_idname = __name__

    def draw(self, context: Context) -> None:
        layout = self.layout
        layout.label(text="Location: 3D Viewport > Select Menu > Select by Dimensions")


classes = (
    SelectByDimensions,
    SELECT_BY_DIMENSIONS_Preferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    VIEW3D_MT_select_object.append(menu_func)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    VIEW3D_MT_select_object.remove(menu_func)


if __name__ == "__main__":
    register()
