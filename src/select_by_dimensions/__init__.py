# SPDX-FileCopyrightText: 2025 todashuta
#
# SPDX-License-Identifier: GPL-3.0-or-later


import math
import operator
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


def get_evaluated_dimensions(depsgraph: Depsgraph, obj: Object) -> tuple[float, float, float] | None:
    #print(obj)
    try:
        obj_eval = obj.evaluated_get(depsgraph)
        mesh_from_eval = obj_eval.to_mesh()
        vs = np.array([obj.matrix_world @ v.co
                       for v in mesh_from_eval.vertices])
        obj_eval.to_mesh_clear()
        dimensions = np.maximum.reduce(vs) - np.minimum.reduce(vs)  # numpy便利
        return dimensions
    except RuntimeError:
        print(f"Unsupported Object: {obj.name}")
        return None


opfuncs = {
    "GT": operator.gt,
    "LT": operator.lt,
    #"EQ": math.isclose,
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
        return len(context.selectable_objects) > 0

    def execute(self, context: Context) -> OperatorResult:
        # Blender はオペレータの __init__ を複数回呼ぶことがある。__init__ で
        # キャッシュを作ると redo のたびに空に戻るので、execute の初回で作る。
        if not hasattr(self, "_dimensions_cache"):
            self._dimensions_cache: dict[str, tuple[float, float, float] | None] = {}

        if not self._dimensions_cache:
            wm: WindowManager = context.window_manager # type: ignore
            wm.progress_begin(0, len(context.selectable_objects))
            depsgraph = context.evaluated_depsgraph_get()
            for i, ob in enumerate(context.selectable_objects):
                self._dimensions_cache[ob.name] = get_evaluated_dimensions(depsgraph, ob)
                wm.progress_update(i)
            wm.progress_end()

        select = self.action == "SELECT"
        for name, dimensions in self._dimensions_cache.items():
            if dimensions is None:
                continue
            if self._matches(dimensions):
                bpy.data.objects[name].select_set(select)
        return {"FINISHED"}

    def _matches(self, dimensions: tuple[float, float, float]) -> bool:
        checked = False
        for axis, size in zip(AXES, dimensions):
            if not getattr(self, f"use_{axis}"):
                continue
            checked = True

            target = getattr(self, axis)
            if getattr(self, f"{axis}_op") == "EQ":
                if not math.isclose(size, target, abs_tol=getattr(self, f"{axis}_tol")):
                    return False
            elif not opfuncs[getattr(self, f"{axis}_op")](size, target):
                return False

        # どの軸も有効になっていなければ何も選ばない。全部選ぶより安全側に倒す。
        return checked

    def draw(self, context: Context) -> None:
        layout: UILayout = self.layout # type: ignore
        #layout.use_property_split = True

        layout.prop(self, "action")
        layout.separator()

        row = layout.row()
        row.prop(self, "use_x", text="")
        subrow = row.row()
        subrow.enabled = self.use_x
        subrow.label(text="X")
        subrow.prop(self, "x_op", text="")
        subrow.prop(self, "x", slider=False, text="")
        if self.x_op == "EQ":
            subrow.prop(self, "x_tol")

        row = layout.row()
        row.prop(self, "use_y", text="")
        subrow = row.row()
        subrow.enabled = self.use_y
        subrow.label(text="Y")
        subrow.prop(self, "y_op", text="")
        subrow.prop(self, "y", slider=False, text="")
        if self.y_op == "EQ":
            subrow.prop(self, "y_tol")

        row = layout.row()
        row.prop(self, "use_z", text="")
        subrow = row.row()
        subrow.enabled = self.use_z
        subrow.label(text="Z")
        subrow.prop(self, "z_op", text="")
        subrow.prop(self, "z", slider=False, text="")
        if self.z_op == "EQ":
            subrow.prop(self, "z_tol")


def menu_func(self, context) -> None:
    layout: UILayout = self.layout
    layout.separator()

    op = layout.operator(
            SelectByDimensions.bl_idname, text="Select by Dimensions")
    op.action = "SELECT"

    op = layout.operator(
            SelectByDimensions.bl_idname, text="Deselect by Dimensions")
    op.action = "DESELECT"


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
