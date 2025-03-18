# SPDX-FileCopyrightText: 2025 todashuta
#
# SPDX-License-Identifier: GPL-2.0-or-later


bl_info = {
    "name": "Select by Dimensions",
    "author": "todashuta",
    "version": (0, 0, "4-dev"),
    "blender": (3, 6, 0),
    "location": "3D Viewport > Select Menu > Select by Dimensions",
    "description": "Select/Deselect by Dimensions",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Object"
}


import bpy
import math
import operator
import numpy as np


def get_evaluated_dimensions(depsgraph, obj):
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
        print("Unsupported Object:", obj.name)
        return None


opfuncs = {
    "GT": operator.gt,
    "LT": operator.lt,
    "EQ": math.isclose,
}


class SelectByDimensions(bpy.types.Operator):
    """Select/Deselect by Dimensions"""
    bl_idname = "object.select_by_dimensions"
    bl_label = "Select by Dimensions"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(name='Action', default='SELECT',
                                   items=[('SELECT', 'Select', ''),
                                          ('DESELECT', 'Deselect', '')])

    use_x: bpy.props.BoolProperty()
    use_y: bpy.props.BoolProperty()
    use_z: bpy.props.BoolProperty(default=True)

    x_op: bpy.props.EnumProperty(name="Compare", default='GT', items=[('EQ', 'Equal', ''), ('GT', 'Greater', ''), ('LT', 'Less', '')])
    y_op: bpy.props.EnumProperty(name="Compare", default='GT', items=[('EQ', 'Equal', ''), ('GT', 'Greater', ''), ('LT', 'Less', '')])
    z_op: bpy.props.EnumProperty(name="Compare", default='GT', items=[('EQ', 'Equal', ''), ('GT', 'Greater', ''), ('LT', 'Less', '')])

    x: bpy.props.FloatProperty(step=10, min=0)
    y: bpy.props.FloatProperty(step=10, min=0)
    z: bpy.props.FloatProperty(step=10, min=0, default=5.0)

    x_tol: bpy.props.FloatProperty(name="Tolerance", min=0.0, default=2.0)
    y_tol: bpy.props.FloatProperty(name="Tolerance", min=0.0, default=2.0)
    z_tol: bpy.props.FloatProperty(name="Tolerance", min=0.0, default=2.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dimensions_cache = {}
        #print("[debug] SelectByDimensions __init__ called")

    @classmethod
    def poll(cls, context):
        return context.selectable_objects

    def execute(self, context):
        if not self._dimensions_cache:
            wm = context.window_manager
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
            conditions = []
            if self.use_x:
                if self.x_op == 'EQ':
                    conditions.append(opfuncs[self.x_op](dimx, self.x, abs_tol=self.x_tol))
                else:
                    conditions.append(opfuncs[self.x_op](dimx, self.x))
            if self.use_y:
                if self.y_op == 'EQ':
                    conditions.append(opfuncs[self.y_op](dimy, self.y, abs_tol=self.y_tol))
                else:
                    conditions.append(opfuncs[self.y_op](dimy, self.y))
            if self.use_z:
                if self.z_op == 'EQ':
                    conditions.append(opfuncs[self.z_op](dimz, self.z, abs_tol=self.z_tol))
                else:
                    conditions.append(opfuncs[self.z_op](dimz, self.z))
            if conditions and all(conditions):
                if self.action == 'SELECT':
                    bpy.data.objects.get(name).select_set(True)
                if self.action == 'DESELECT':
                    bpy.data.objects.get(name).select_set(False)
        return {'FINISHED'}

    #def invoke(self, context, event):
    #    wm = context.window_manager
    #    self.use_x = False
    #    self.use_y = False
    #    self.use_z = False
    #    #print(self._dimensions_cache)
    #    return wm.invoke_props_popup(self, event)
    #def invoke(self, context, event):
    #    wm = context.window_manager
    #    #print(self._dimensions_cache)
    #    return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
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
        if self.x_op == 'EQ':
            subrow.prop(self, "x_tol")

        row = layout.row()
        row.prop(self, "use_y", text="")
        subrow = row.row()
        subrow.enabled = self.use_y
        subrow.label(text="Y")
        subrow.prop(self, "y_op", text="")
        subrow.prop(self, "y", slider=False, text="")
        if self.y_op == 'EQ':
            subrow.prop(self, "y_tol")

        row = layout.row()
        row.prop(self, "use_z", text="")
        subrow = row.row()
        subrow.enabled = self.use_z
        subrow.label(text="Z")
        subrow.prop(self, "z_op", text="")
        subrow.prop(self, "z", slider=False, text="")
        if self.z_op == 'EQ':
            subrow.prop(self, "z_tol")


def menu_func(self, context):
    layout = self.layout
    layout.separator()

    op = layout.operator(
            SelectByDimensions.bl_idname, text="Select by Dimensions")
    op.action = 'SELECT'

    op = layout.operator(
            SelectByDimensions.bl_idname, text="Deselect by Dimensions")
    op.action = 'DESELECT'


def register():
    bpy.utils.register_class(SelectByDimensions)
    bpy.types.VIEW3D_MT_select_object.append(menu_func)


def unregister():
    bpy.utils.unregister_class(SelectByDimensions)
    bpy.types.VIEW3D_MT_select_object.remove(menu_func)


if __name__ == "__main__":
    register()
