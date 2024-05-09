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
    edit = arcpy.da.Editor()
    edit.startEditing(with_undo=False,multiuser_mode=False)
    edit.startOperation()

    arcpy.AddMessage("Iterating through dataset(s) in geodatabase...")

    for dataset in tuple(arcpy.ListDatasets()):
        if not len((poly_fcs := tuple([fc for fc in arcpy.ListFeatureClasses(feature_type='Polygon',feature_dataset=dataset)]))):
            arcpy.AddMessage(f"No polygon feature class found in {dataset} dataset.\n\n")
            continue
        poly_nomin = None
        for poly_fc in poly_fcs:
            if 'MapUnitPolys' in poly_fc and 'MapUnit' in [field.name for field in arcpy.ListFields(f'{arcpy.env.workspace}/{dataset}/{poly_fc}')]:
                poly_nomin = poly_fc[:]
                arcpy.AddMessage(f'Obtaining unique non-empty values from MapUnit in {poly_nomin}...')
                mapunits = tuple({row[0] for row in arcpy.da.SearchCursor(f'{dataset}/{poly_nomin}',['MapUnit']) if not row[0] is None})
                arcpy.AddMessage('List of unqiue values successfully obtained.\n\n')
                break
        if poly_nomin is None:
            message_str = f'Skipping {dataset} dataset due to '
            if dataset == 'GeologicMap':
                message_str = f'{message_str}MapUnitPolys not found in dataset.'
            else:
                message_str = f'{message_str}CS{dataset[-1]}MapUnitPolys not found in dataset.'
            arcpy.AddMessage(f"{message_str}\n\n")
            del message_str
            gc.collect()
            continue
        if len((pnt_fc_names := tuple([fc for fc in arcpy.ListFeatureClasses(feature_type='Point',feature_dataset=dataset) if 'MapUnit' in [field.name for field in arcpy.ListFields(f'{arcpy.env.workspace}/{dataset}/{fc}',field_type='String')]]))):
            arcpy.AddMessage("Generating temporary point layer features...")
            pnt_lyrs = []
            for n in range(len(pnt_fc_names)):
                arcpy.management.MakeFeatureLayer(f'{dataset}/{pnt_fc_names[n]}',f'pnt_lyr_{n}')
                pnt_lyrs.append(f'pnt_lyr_{n}')
            pnt_lyrs = tuple(pnt_lyrs)
            arcpy.AddMessage("Layer point features generated.\n\n")
            arcpy.AddMessage(f"Generating temporary polygon layer feature of {poly_nomin}...")
            arcpy.management.MakeFeatureLayer(f'{dataset}/{poly_nomin}','mapunit_poly_lyr')
            arcpy.AddMessage("Polygon layer feature generated.\n\nFilling out MapUnit field for point feature classes...")
            for n in range(len(pnt_lyrs)):
                for field in arcpy.ListFields(pnt_lyrs[n]):
                    oid_field_name = field.name
                    break
                pnt_oid = array('i',[])
                pnt_mapunit = []
                for mapunit in mapunits:
                    selected_polys,count = arcpy.management.SelectLayerByAttribute('mapunit_poly_lyr','NEW_SELECTION',f"MapUnit = '{mapunit}'",'NON_INVERT')
                    del count
                    for row in arcpy.da.SearchCursor(selected_polys,[oid_field_name]):
                        pnt_oid.append(row[0])
                        pnt_mapunit.append(mapunit)
                with arcpy.da.UpdateCursor(f'{dataset}/{pnt_fc_names[n]}',[oid_field_name,'MapUnit']) as cursor:
                    for row in cursor:
                        if row[0] in pnt_oid:
                            row[1] = pnt_mapunit[pnt_oid.index(row[0])]
                        cursor.updateRow(row)
            arcpy.AddMessage("MapUnit field for point feature classes in %s dataset have been filled.\n\n" % dataset)
        else:
            arcpy.AddMessage("No point feature classes with a MapUnit field were found in %s dataset.\n\n" % dataset)

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
