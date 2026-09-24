"""Retain genuinely source-facing metal ridge pixels at a grazing angle."""
def apply():
 import bpy,math
 from mathutils import Vector
 matches=[o for o in bpy.data.objects if o.get('source_node')=='building-506'and o.get('projection_component')=='castle-hall-retained-roof']
 assert len(matches)==1
 o=matches[0];toward=Vector((0,-math.cos(math.radians(35)),math.sin(math.radians(35))));dots=[(o.matrix_world.to_3x3().inverted().transposed()@f.normal).normalized().dot(toward)for f in o.data.polygons]
 assert any(.017<d<.019 for d in dots),dots
 o['projection_min_cosine']=.01
 o['projection_grazing_review']='Source-visible metal ridge has positive normal dot0.017965; scoped threshold0.01 accepts its455 pixels while negative opposite face stays unknown.'
 wall=next(obj for obj in bpy.data.objects if obj.get('source_node')=='building-504'and not obj.get('projection_component'))
 wall_dots=[(wall.matrix_world.to_3x3().inverted().transposed()@f.normal).normalized().dot(toward)for f in wall.data.polygons]
 assert any(.029<d<.030 for d in wall_dots),wall_dots
 wall['projection_min_cosine']=.01
 wall['projection_grazing_review']='Independent source boundary shows393 visible masonry trim pixels on positive grazing face normaldot0.029488; threshold0.01 retains negative and edge-on faces as unknown.'
 return {'object':o.name,'threshold':.01,'normal_dots':dots,'wall_object':wall.name,'wall_normal_dots':wall_dots}
