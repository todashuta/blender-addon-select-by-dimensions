# SPDX-FileCopyrightText: 2025 todashuta
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy
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
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
)
import math
import operator
import numpy as np


from typing import Literal
OperatorResult = set[
    Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]
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
    bl_options = {"REGISTER", "UNDO"}

    action: EnumProperty(name="Action", default="SELECT",
                         items=[("SELECT", "Select", ""),
                                ("DESELECT", "Deselect", "")]) # type: ignore

    use_x: BoolProperty() # type: ignore
    use_y: BoolProperty() # type: ignore
    use_z: BoolProperty(default=True) # type: ignore

    x_op: EnumProperty(name="Compare", default="GT", items=[("EQ", "Equal", ""), ("GT", "Greater", ""), ("LT", "Less", "")]) # type: ignore
    y_op: EnumProperty(name="Compare", default="GT", items=[("EQ", "Equal", ""), ("GT", "Greater", ""), ("LT", "Less", "")]) # type: ignore
    z_op: EnumProperty(name="Compare", default="GT", items=[("EQ", "Equal", ""), ("GT", "Greater", ""), ("LT", "Less", "")]) # type: ignore

    x: FloatProperty(step=10, min=0) # type: ignore
    y: FloatProperty(step=10, min=0) # type: ignore
    z: FloatProperty(step=10, min=0, default=5.0) # type: ignore

    x_tol: FloatProperty(name="Tolerance", min=0.0, default=2.0) # type: ignore
    y_tol: FloatProperty(name="Tolerance", min=0.0, default=2.0) # type: ignore
    z_tol: FloatProperty(name="Tolerance", min=0.0, default=2.0) # type: ignore

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dimensions_cache: dict[str, tuple[float, float, float] | None] = {}
        #print("[debug] SelectByDimensions __init__ called")

    @classmethod
    def poll(cls, context: Context) -> bool:
        return len(context.selectable_objects) > 0

    def execute(self, context: Context) -> OperatorResult:
        if not self._dimensions_cache:
            wm: WindowManager = context.window_manager # type: ignore
            wm.progress_begin(0, len(context.selectable_objects))
            depsgraph = context.evaluated_depsgraph_get()
            for i, ob in enumerate(context.selectable_objects):
                self._dimensions_cache[ob.name] = get_evaluated_dimensions(depsgraph, ob)
                wm.progress_update(i)
            wm.progress_end()

        for name, dimensions in self._dimensions_cache.items():
            if dimensions is None:
                continue
            dimx, dimy, dimz = dimensions
            conditions: list[bool] = []
            if self.use_x:
                if self.x_op == "EQ":
                    conditions.append(math.isclose(dimx, self.x, abs_tol=self.x_tol))
                else:
                    conditions.append(opfuncs[self.x_op](dimx, self.x))
            if self.use_y:
                if self.y_op == "EQ":
                    conditions.append(math.isclose(dimy, self.y, abs_tol=self.y_tol))
                else:
                    conditions.append(opfuncs[self.y_op](dimy, self.y))
            if self.use_z:
                if self.z_op == "EQ":
                    conditions.append(math.isclose(dimz, self.z, abs_tol=self.z_tol))
                else:
                    conditions.append(opfuncs[self.z_op](dimz, self.z))
            if conditions and all(conditions):
                if self.action == "SELECT":
                    bpy.data.objects[name].select_set(True)
                if self.action == "DESELECT":
                    bpy.data.objects[name].select_set(False)
        return {"FINISHED"}

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
