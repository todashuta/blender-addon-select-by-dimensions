# SPDX-FileCopyrightText: 2025 todashuta
#
# SPDX-License-Identifier: GPL-2.0-or-later


bl_info = {
        "name": "Select By Dimensions",
        "author": "todashuta",
        "version": (0, 0, "1-dev"),
        "blender": (3, 6, 0),
        "location": "3D Viewport > Select Menu > Select By Dimensions",
        "description": "Select/Deselect By Dimensions",
        "warning": "",
        "wiki_url": "",
        "tracker_url": "",
        "category": "Object"
}


import bpy
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


class SelectByDimensions(bpy.types.Operator):
    """Select/Deselect By Dimensions"""
    bl_idname = "object.select_by_dimensions"
    bl_label = "Select By Dimensions"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(name='Action', default='SELECT',
                                   items=[('SELECT', 'Select', ''),
                                          ('DESELECT', 'Deselect', '')])

    use_x: bpy.props.BoolProperty()
    use_y: bpy.props.BoolProperty()
    use_z: bpy.props.BoolProperty(default=True)

    x_op: bpy.props.EnumProperty(default='gt', items=[('gt', 'Greater', ''), ('lt', 'Less', '')])
    y_op: bpy.props.EnumProperty(default='gt', items=[('gt', 'Greater', ''), ('lt', 'Less', '')])
    z_op: bpy.props.EnumProperty(default='gt', items=[('gt', 'Greater', ''), ('lt', 'Less', '')])

    x: bpy.props.FloatProperty(step=10, min=0)
    y: bpy.props.FloatProperty(step=10, min=0)
    z: bpy.props.FloatProperty(step=10, min=0, default=5.0)

    def __init__(self):
        self._cache = {}
        #print("SelectByDimensions __init__ called", self)

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object and active_object.mode == 'OBJECT'

    def execute(self, context):
        if not self._cache:
            wm = context.window_manager
            wm.progress_begin(0, len(context.selectable_objects))
            depsgraph = context.evaluated_depsgraph_get()
            for i, ob in enumerate(context.selectable_objects):
                self._cache[ob.name] = get_evaluated_dimensions(depsgraph, ob)
                wm.progress_update(i)
            wm.progress_end()

        for obname in self._cache:
            dimensions = self._cache[obname]
            if dimensions is None:
                continue
            dimx, dimy, dimz = dimensions
            conditions = []
            if self.use_x:
                conditions.append(getattr(operator, self.x_op)(dimx, self.x))
            if self.use_y:
                conditions.append(getattr(operator, self.y_op)(dimy, self.y))
            if self.use_z:
                conditions.append(getattr(operator, self.z_op)(dimz, self.z))
            if conditions and all(conditions):
                if self.action == 'SELECT':
                    bpy.data.objects.get(obname).select_set(True)
                if self.action == 'DESELECT':
                    bpy.data.objects.get(obname).select_set(False)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        self.use_x = False
        self.use_y = False
        self.use_z = False
        #print(self._cache)
        return wm.invoke_props_popup(self, event)

    def draw(self, context):
        layout = self.layout
        #layout.use_property_split = True

        layout.prop(self, "action")

        row = layout.row()
        row.prop(self, "use_x", text="")
        subrow = row.row()
        subrow.enabled = self.use_x
        subrow.label(text="X")
        subrow.prop(self, "x_op", text="")
        subrow.prop(self, "x", slider=False, text="")

        row = layout.row()
        row.prop(self, "use_y", text="")
        subrow = row.row()
        subrow.enabled = self.use_y
        subrow.label(text="Y")
        subrow.prop(self, "y_op", text="")
        subrow.prop(self, "y", slider=False, text="")

        row = layout.row()
        row.prop(self, "use_z", text="")
        subrow = row.row()
        subrow.enabled = self.use_z
        subrow.label(text="Z")
        subrow.prop(self, "z_op", text="")
        subrow.prop(self, "z", slider=False, text="")


def menu_func(self, context):
    layout = self.layout
    layout.separator()

    op = layout.operator(
            SelectByDimensions.bl_idname, text="Select By Dimensions")
    op.action = 'SELECT'

    op = layout.operator(
            SelectByDimensions.bl_idname, text="Deselect By Dimensions")
    op.action = 'DESELECT'


def register():
    bpy.utils.register_class(SelectByDimensions)
    bpy.types.VIEW3D_MT_select_object.append(menu_func)


def unregister():
    bpy.utils.unregister_class(SelectByDimensions)
    bpy.types.VIEW3D_MT_select_object.remove(menu_func)


if __name__ == "__main__":
    register()
