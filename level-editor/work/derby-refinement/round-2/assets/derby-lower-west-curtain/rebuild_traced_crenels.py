"""Rebuild complete closed walls with source-image crenel intervals."""
import sys,json,math
from pathlib import Path
workspace=Path(__file__).resolve().parent
sys.path.insert(0,str(workspace.parents[4]/'blender'))
import bpy,bmesh
from derby_asset_lower_west_curtain import _wall

# Each interval is measured on the projected outer crown edge, in original
# map pixels. The other side of the opening is derived from the wall footprint.
# Corner/turret cuts are retained from the original recipe.
RECIPES={
 'building-023':[(76,66,1,((1828,1841),(1850,1862),(1871,1882),(1904,1918.7))),
                 (66,67,1,((1918.3,1920),(1923,1936),(1940,1955),(1976,1986),(1997,2007),(2018,2028))),
                 (80,76,0,((295,310),)),(79,80,0,((265,274),)),
                 (75,74,0,((267,280),)),(74,73,0,((305,319),))],
 'building-025':[(28,27,0,((337,343),(349,356),(362,369),(375,383))),
                 (27,26,0,((334,340),(348,354),(362,368),(376,382)))],
 'building-042':[(35,36,0,((401,411),(421,431),(441,451),(461,471),(481,491),(501,511)))],
}
working=bpy.data.collections['Derby Working']
results=[]
for node,cuts in RECIPES.items():
    old=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render)
    source=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')==node and o.hide_render and 'modeled battlements' not in o.name)
    old_name=old.name
    fit=None
    if node=='building-025':
        # These four crown corners were picked in the enlarged original RGB,
        # not generated from the existing wall. Fit only a common crown height;
        # keep the plan/azimuth fixed. Other corners remain review evidence.
        observed=[(334,1563),(340,1573),(348,1584),(354,1595)]
        a=source.matrix_world@source.data.vertices[26].co
        b=source.matrix_world@source.data.vertices[27].co
        def project_y(p):return -p.y*math.sin(math.radians(35))-p.z*math.cos(math.radians(35))
        initial=[project_y(a)+(x-a.x)*(project_y(b)-project_y(a))/(b.x-a.x) for x,y in observed]
        shift=sum(y-v for (x,y),v in zip(observed,initial))/len(observed)
        fit={'observed_crown_corners':observed,'baseline_predicted_y':initial,'source_y_shift':shift,
             'height_delta':-shift/math.cos(math.radians(35)),
             'residual_y':[v+shift-y for (x,y),v in zip(observed,initial)]}
        temp=source.copy();temp.data=source.data.copy();working.objects.link(temp)
        inverse=temp.matrix_world.inverted();points=[temp.matrix_world@v.co for v in temp.data.vertices]
        top=max(p.z for p in points)
        for v,p in zip(temp.data.vertices,points):
            if p.z>top-.1:p.z+=fit['height_delta'];v.co=inverse@p
        result=_wall(temp,cuts,notch_depth=23.5)
        bpy.data.objects.remove(temp,do_unlink=True)
    else:
        result=_wall(source,cuts,notch_depth=23.5,allow_corner_cuts=node=='building-023')
    result['source_corner_height_fit']=fit
    new=bpy.data.objects[result['object']]
    new.name=old_name+' / source traced'
    new['crenel_source_intervals']=json.dumps(cuts)
    # Compare lower wall coverage to the previous closed wall: the recipe only
    # cuts top26 units, so below206 all old wall faces must remain represented.
    old_world=[old.matrix_world@v.co for v in old.data.vertices]
    new_world=[new.matrix_world@v.co for v in new.data.vertices]
    result['old_z_min']=min(p.z for p in old_world)
    result['new_z_min']=min(p.z for p in new_world)
    assert abs(result['old_z_min']-result['new_z_min'])<.01
    bm=bmesh.new();bm.from_mesh(new.data)
    result['volume']=bm.calc_volume(signed=True)
    assert result['volume']>0
    bm.free()
    bpy.data.objects.remove(old,do_unlink=True)
    new.name=old_name
    results.append(result)
output=workspace/'inspection/complete-wall-candidate-v5'
output.mkdir(parents=True,exist_ok=True)
(output/'geometry.json').write_text(json.dumps({'status':'CANDIDATE_REQUIRES_VISUAL_REVIEW','source_coordinate_uncertainty_px':2,'notch_depth_world':23.5,'recipes':RECIPES,'results':results,'note':'Counts are cutter operations, not merlons. Two overlapping cuts form one bend opening. Concealed roof-overlapped repeats extrapolate nearest visible rhythm.'},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
