import arcpy
import gc
from misc_arcpy_ops import default_env_parameters
import sys
from array import array

gdb_path = sys.argv[1]

def fill_mapunit_pnt_field(gdb_path : str):
    """
    This autofills MapUnit field in point feature classes based upon location relative to polygons
    in MapUnitPolys.
    """

    try:
        current_workspace = arcpy.env.workspace[:]
        current_workspace = current_workspace.replace('\\','/')
    except Exception:
        pass

    arcpy.env.workspace = gdb_path.replace('\\','/')

    default_env_parameters()

    # This is to prevent Error #160250 randomly from occurring.
    edit = arcpy.da.Editor(arcpy.env.workspace)

    edit.startEditing(with_undo=False,multiuser_mode=False)
    edit.startOperation()

    for dataset in tuple(arcpy.ListDatasets()):
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
            if 'MapUnitPolys' in fc:
                poly_name = fc[:]
                break
        arcpy.management.MakeFeatureLayer(f'{dataset}/{poly_name}','temp_poly_lyr')
        mapunits = {fixFieldItemString(row[0]) for row in arcpy.da.SearchCursor(f'{dataset}/{poly_name}','MapUnit') if not row[0] is None}
        if None in mapunits:
            mapunits.remove(None)
        mapunits = tuple(mapunits)
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point')):
                if not 'MapUnit' in [field.name for field in arcpy.ListFields(f'{dataset}/{fc}',field_type='String')]:
                    continue
                arcpy.management.MakeFeatureLayer(f'{dataset}/{fc}','temp_pnt_lyr')
                fields = ["MapUnit"]
                for field in tuple(arcpy.ListFields(f'{dataset}/{fc}')):
                    fields.insert(0,field.name)
                    break
                fields = tuple(fields)
                matched = dict()
                for mapunit in mapunits:
                    selected_polys = arcpy.management.SelectLayerByAttribute('temp_poly_lyr','NEW_SELECTION',f"MapUnit = '{mapunit}'")
                    selected_pnts,redundant,count = arcpy.management.SelectLayerByLocation('temp_pnt_lyr','INTERSECT',selected_polys,'','NEW_SELECTION')
                    del redundant
                    if count:
                        for row in arcpy.da.SearchCursor(selected_pnts,fields[0]):
                            matched[row[0]] = mapunit

                if len(matched):
                    oids = array('i',matched.keys())
                    with arcpy.da.UpdateCursor(f'{dataset}/{fc}',fields) as cursor:
                        for row in cursor:
                            if row[0] in oids:
                                row[1] = matched[oids[oids.index(row[0])]]
                                cursor.updateRow(row)

    arcpy.AddMessage("Changes successfully applied.\n\nSaving edits...")

    try:
        edit.stopOperation()
    except Exception:
        pass
    try:
        edit.stopEditing(save_changes=True)
    except Exception:
        pass

    arcpy.AddMessage("Edits saved!")

    try:
        arcpy.env.workspace = current_workspace[:]
    except Exception:
        pass
    
    gc.collect()

fill_mapunit_pnt_field(gdb_path)
