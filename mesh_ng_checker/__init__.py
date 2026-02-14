bl_info = {
    "name": "Mesh NG Checker (Refactored+)",
    "author": "Mitsuhiko",
    "version": (0, 5, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > NG Checker",
    "description": "Check selected meshes for topology problems (N-gon / Non-manifold / Boundary / UV / Flip suspect)",
    "category": "3D View",
}

import bpy
import bmesh
from mathutils import Vector
from bpy.props import BoolProperty, FloatProperty, StringProperty


# ============================================================
# Text Editor Report
# ============================================================

REPORT_TEXT_NAME = "NG_Check_Report"


def write_report_text(text: str):
    """Text Editor用のテキストデータにレポートを書き込む"""
    txt = bpy.data.texts.get(REPORT_TEXT_NAME)
    if txt is None:
        txt = bpy.data.texts.new(REPORT_TEXT_NAME)
    txt.clear()
    txt.write(text)


# ============================================================
# Core Analysis (single source of truth)
# ============================================================

def analyze_bmesh(bm, obj):
    """BMeshから解析する（Object/Editどちらでも使える）"""
    #二重辞書　index毎の判定結果をまとめたもの
    face_flags = {}  # face.index -> {"ngon":bool,"flip":bool,"nm":bool,"bd":bool}
    edge_flags = {}  # edge.index -> {"nm":bool,"bd":bool}

    face_count = len(bm.faces)
    ngon_count = 0
    nonmanifold_edges = 0
    boundary_edges = 0
    flipped_suspect = 0

    # メッシュ全体の中心（原点の代わり）
    origin = Vector((0, 0, 0))
    if len(bm.verts) > 0:
        origin = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)

    # Edge集計 + edge_flags
    for e in bm.edges:
        lf = len(e.link_faces)
        is_nm = (lf >= 3)
        is_bd = (lf == 1)

        if is_nm:
            nonmanifold_edges += 1
        elif is_bd:
            boundary_edges += 1

        edge_flags[e.index] = {"nm": is_nm, "bd": is_bd}

    # Face集計 + face_flags
    for f in bm.faces:
        is_ngon = (len(f.verts) > 4)
        if is_ngon:
            ngon_count += 1

        # flip判定（heuristic）
        is_flip = False
        center = f.calc_center_median()
        dir_vec = center - origin
        if dir_vec.length > 1e-9:
            dir_vec.normalize()
            if f.normal.dot(dir_vec) < 0:
                is_flip = True
                flipped_suspect += 1

        # このfaceがNM/Boundaryに関係あるか（edge_flagsから）
        is_nm_face = False
        is_bd_face = False
        for e in f.edges:
            ef = edge_flags.get(e.index)
            if not ef:
                continue
            if ef["nm"]:
                is_nm_face = True
            if ef["bd"]:
                is_bd_face = True

        face_flags[f.index] = {
            "ngon": is_ngon,
            "flip": is_flip,
            "nm": is_nm_face,
            "bd": is_bd_face,
        }

    has_uv = (len(obj.data.uv_layers) > 0)

    result = {
        "name": obj.name,
        "faces": face_count,
        "ngon": ngon_count,
        "nm": nonmanifold_edges,
        "bd": boundary_edges,
        "uv": has_uv,
        "flip": flipped_suspect,
        "face_flags": face_flags,
        "edge_flags": edge_flags,
    }
    return result, None


def analyze_mesh_object(obj):
    """Objectモード用：MeshDataからBMeshを作って解析する"""
    if obj is None or obj.type != 'MESH':
        return None, "Not a mesh"

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.normal_update()
        return analyze_bmesh(bm, obj)
    finally:
        bm.free()


def get_reason(r):
    reasons = []
    if r["ngon"] > 0:
        reasons.append("N-gon detected")
    if r["nm"] > 0:
        reasons.append("Non-manifold edges")
    if r["bd"] > 0:
        reasons.append("Boundary edges")
    if not r["uv"]:
        reasons.append("UV missing")
    return ", ".join(reasons) if reasons else "No issues"


def format_block(r):
    flip_ratio = (r["flip"] / r["faces"]) if r["faces"] else 0.0
    return (
        f"Object: {r['name']}\n"
        f"Faces: {r['faces']}\n"
        f"N-gons: {r['ngon']}\n"
        f"Non-manifold edges: {r['nm']}\n"
        f"Boundary edges: {r['bd']}\n"
        f"UV: {'YES' if r['uv'] else 'NO'}\n"
        f"Flipped suspect (heuristic): {r['flip']} ({flip_ratio:.1%})\n"
    )


# ============================================================
# EditMesh helper
# ============================================================

def ensure_edit_mesh(context, obj):
    """アクティブメッシュをEditモードにし、BMeshを返す"""
    if context.mode != 'EDIT_MESH':
        bpy.ops.object.mode_set(mode='EDIT')
    return bmesh.from_edit_mesh(obj.data)


# ============================================================
# Operator: Run NG Check (multi selection, object mode)
# ============================================================

class MESHNGCHECKER_OT_run(bpy.types.Operator):
    bl_idname = "meshngchecker.run"
    bl_label = "Run NG Check"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Analyze selected mesh objects and show NG report"

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        sc = context.scene
        selected = [o for o in context.selected_objects if o.type == 'MESH']

        if not selected:
            self.report({'ERROR'}, "No mesh selected")
            return {'CANCELLED'}

        blocks = []
        summary = []
        report_lines = []
        ng_objs = []

        report_lines.append("=== Mesh NG Checker Report ===\n")

        for obj in selected:
            result, err = analyze_mesh_object(obj)

            if err:
                blocks.append(f"{obj.name} : ERROR")
                summary.append(f"ERROR | {obj.name}")
                report_lines.append(f"--- ERROR | {obj.name} ---\n")
                continue

            blocks.append(format_block(result))

            flip_ratio = (result["flip"] / result["faces"]) if result["faces"] else 0.0

            # ✅ チェックボックスのON/OFFを反映する判定
            ng = (
                (sc.ng_check_ngon and result["ngon"] > 0) or
                (sc.ng_check_nm and result["nm"] > 0) or
                (sc.ng_check_bd and result["bd"] > 0) or
                (sc.ng_check_uv and (not result["uv"])) or
                (sc.ng_check_flip and (flip_ratio > sc.ng_flip_ratio_th))
            )

            tag = "NG" if ng else "OK"

            if ng:
                ng_objs.append(obj)

            summary.append(
                f"{tag} | {result['name']} | NGon:{result['ngon']} "
                f"NM:{result['nm']} BD:{result['bd']} UV:{'Y' if result['uv'] else 'N'}"
            )

            report_lines.append(f"--- {tag} | {result['name']} ---")
            report_lines.append(f"Reason: {get_reason(result)}")
            report_lines.append(format_block(result))
            report_lines.append("")

        # UIのLast Resultに保存
        context.scene.mesh_ngchecker_last = "\n\n".join(blocks)

        # Text Editorに保存
        write_report_text("\n".join(report_lines))

        # 表示用にNGを上に並べる
        summary.sort(key=lambda s: 0 if s.startswith("NG") else 1)

        # NGオブジェクトがあればそれだけ選択し直す
        if ng_objs:
            for o in context.selected_objects:
                o.select_set(False)
            for o in ng_objs:
                o.select_set(True)
            context.view_layer.objects.active = ng_objs[0]

        self.report({'INFO'}, " || ".join(summary))
        return {'FINISHED'}


# ============================================================
# Operator: Select NG Faces (edit mode, uses analyze_bmesh)
# ============================================================

class MESHNGCHECKER_OT_select_ng_faces(bpy.types.Operator):
    bl_idname = "meshngchecker.select_ng_faces"
    bl_label = "Select NG Faces"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select faces that match enabled NG checks (Edit Mode)"

    def execute(self, context):
        sc = context.scene
        obj = context.active_object

        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        bm = ensure_edit_mesh(context, obj)

        bpy.ops.mesh.select_mode(type='FACE')

        # 全選択解除（Face）
        for f in bm.faces:
            f.select = False

        tmp_result, _ = analyze_bmesh(bm, obj)
        uv_missing = (not tmp_result["uv"])

        for f in bm.faces:
            ff = tmp_result["face_flags"].get(f.index)
            if not ff:
                continue

            # face単位のflipは 0/1 なので、しきい値比較に使う
            face_flip_ratio = 1.0 if ff["flip"] else 0.0

            is_ng = (
                (sc.ng_check_ngon and ff["ngon"]) or
                (sc.ng_check_nm and ff["nm"]) or
                (sc.ng_check_bd and ff["bd"]) or
                (sc.ng_check_uv and uv_missing) or
                (sc.ng_check_flip and (face_flip_ratio > sc.ng_flip_ratio_th))
            )

            if is_ng:
                f.select = True

        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


# ============================================================
# Operator: Select N-gon Faces (edit mode)
# ============================================================

class MESHNGCHECKER_OT_select_ngon(bpy.types.Operator):
    bl_idname = "meshngchecker.select_ngon"
    bl_label = "Select N-gon Faces"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select N-gon faces (>4 verts) in Edit Mode"

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        bm = ensure_edit_mesh(context, obj)
        bpy.ops.mesh.select_mode(type='FACE')

        for f in bm.faces:
            f.select = False

        tmp_result, _ = analyze_bmesh(bm, obj)

        for f in bm.faces:
            ff = tmp_result["face_flags"].get(f.index)
            if ff and ff["ngon"]:
                f.select = True

        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        return {'FINISHED'}


# ============================================================
# Operator: Select Non-manifold Edges (edit mode)
# ============================================================

class MESHNGCHECKER_OT_select_non_manifold(bpy.types.Operator):
    bl_idname = "meshngchecker.select_non_manifold"
    bl_label = "Select Non-manifold Edges"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select non-manifold edges (link_faces >= 3) in Edit Mode"

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        bm = ensure_edit_mesh(context, obj)
        bpy.ops.mesh.select_mode(type='EDGE')

        for e in bm.edges:
            e.select = False

        tmp_result, _ = analyze_bmesh(bm, obj)

        for e in bm.edges:
            ef = tmp_result["edge_flags"].get(e.index)
            if ef and ef["nm"]:
                e.select = True

        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        return {'FINISHED'}


# ============================================================
# Operator: Select Boundary Edges (edit mode)
# ============================================================

class MESHNGCHECKER_OT_select_boundary(bpy.types.Operator):
    bl_idname = "meshngchecker.select_boundary"
    bl_label = "Select Boundary Edges"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select boundary edges (link_faces == 1) in Edit Mode"

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        bm = ensure_edit_mesh(context, obj)
        bpy.ops.mesh.select_mode(type='EDGE')

        for e in bm.edges:
            e.select = False

        tmp_result, _ = analyze_bmesh(bm, obj)

        for e in bm.edges:
            ef = tmp_result["edge_flags"].get(e.index)
            if ef and ef["bd"]:
                e.select = True

        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        return {'FINISHED'}


# ============================================================
# UI Panel
# ============================================================

class MESHNGCHECKER_PT_panel(bpy.types.Panel):
    bl_label = "NG Checker"
    bl_idname = "MESHNGCHECKER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'NG Checker'

    def draw(self, context):
        layout = self.layout

        layout.operator("meshngchecker.run", icon='CHECKMARK')
        layout.operator("meshngchecker.select_ng_faces", icon='FACESEL')
        layout.operator("meshngchecker.select_ngon", icon='FACESEL')
        layout.operator("meshngchecker.select_non_manifold", icon='EDGESEL')
        layout.operator("meshngchecker.select_boundary", icon='EDGESEL')

        layout.separator()
        layout.label(text="Checks:")

        col = layout.column(align=True)
        col.prop(context.scene, "ng_check_ngon")
        col.prop(context.scene, "ng_check_nm")
        col.prop(context.scene, "ng_check_bd")
        col.prop(context.scene, "ng_check_uv")
        col.prop(context.scene, "ng_check_flip")

        layout.prop(context.scene, "ng_flip_ratio_th")

        layout.separator()
        layout.label(text="Last Result")
        layout.prop(context.scene, "mesh_ngchecker_last", text="")


# ============================================================
# register / unregister
# ============================================================

classes = (
    MESHNGCHECKER_OT_run,
    MESHNGCHECKER_OT_select_ng_faces,
    MESHNGCHECKER_OT_select_ngon,
    MESHNGCHECKER_OT_select_non_manifold,
    MESHNGCHECKER_OT_select_boundary,
    MESHNGCHECKER_PT_panel,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.mesh_ngchecker_last = StringProperty(default="(not run yet)")

    bpy.types.Scene.ng_check_ngon = BoolProperty(name="Check N-gon", default=True)
    bpy.types.Scene.ng_check_nm = BoolProperty(name="Check Non-manifold", default=True)
    bpy.types.Scene.ng_check_bd = BoolProperty(name="Check Boundary", default=True)
    bpy.types.Scene.ng_check_uv = BoolProperty(name="Check UV Missing", default=True)
    bpy.types.Scene.ng_check_flip = BoolProperty(name="Check Flip Suspect", default=True)

    bpy.types.Scene.ng_flip_ratio_th = FloatProperty(
        name="Flip Ratio Threshold",
        default=0.2, min=0.0, max=1.0
    )


def unregister():
    del bpy.types.Scene.mesh_ngchecker_last
    del bpy.types.Scene.ng_check_ngon
    del bpy.types.Scene.ng_check_nm
    del bpy.types.Scene.ng_check_bd
    del bpy.types.Scene.ng_check_uv
    del bpy.types.Scene.ng_check_flip
    del bpy.types.Scene.ng_flip_ratio_th

    for c in reversed(classes):
        bpy.utils.unregister_class(c)

