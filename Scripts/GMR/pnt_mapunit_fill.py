import arcpy
import gc
from misc_arcpy_ops import default_env_parameters
import sys

gdb_path = sys.argv[1]

def fill_pnt_mapunit_field(gdb_path : str):

    try:
        current_workspace = arcpy.env.workspace[:]
        current_workspace = current_workspace.replace('\\','/')
    except Exception:
        pass

    arcpy.env.workspace = gdb_path.replace('\\','/')

    default_env_parameters()

    arcpy.AddMessage("Initializing ArcPy Editor...")

    edit = arcpy.da.Editor(arcpy.env.workspace)

    edit.startEditing(with_undo=False,multiuser_mode=False)
    edit.startOperation()

    arcpy.AddMessage("Successfully initialized ArcPy Editor.\n\nObtaining list of datasets in geodatabase...")
    datasets = tuple(arcpy.ListDatasets())
    arcpy.AddMessage("List obtained.\n")

    for dataset in datasets:
        if not len((poly_fcs := tuple([fc for fc in arcpy.ListFeatureClasses(feature_dataset=dataset) if arcpy.Describe(f'{arcpy.env.workspace}/{dataset}/{fc}').shapeType == 'Polygon']))):
            arcpy.AddMessage(f"No polygon feature class found in {dataset} dataset.\n")
            continue
        poly_nomin = None
        for poly_fc in poly_fcs:
            if 'MapUnitPolys' in poly_fc and 'MapUnit' in [field.name for field in arcpy.ListFields(f'{arcpy.env.workspace}/{dataset}/{poly_fc}')]:
                poly_nomin = poly_fc[:]
                arcpy.AddMessage(f'Obtaining unique non-empty values from MapUnit in {poly_nomin}...')
                mapunits = tuple({row[0] for row in arcpy.da.SearchCursor(f'{dataset}/{poly_nomin}',['MapUnit']) if not row[0] is None})
                arcpy.AddMessage('List of unqiue values successfully obtained.\n')
                break
        if poly_nomin is None:
            message_str = f'Skipping {dataset} dataset due to '
            if dataset == 'GeologicMap':
                message_str = f'{message_str}MapUnitPolys not found in dataset.'
            else:
                message_str = f'{message_str}CS{dataset[-1]}MapUnitPolys not found in dataset.'
            arcpy.AddMessage("%s\n" % message_str)
            del message_str
            gc.collect()
            continue
        if len((pnt_fc_names := tuple([fc for fc in arcpy.ListFeatureClasses(feature_dataset=dataset) if arcpy.Describe(f'{arcpy.env.workspace}/{dataset}/{fc}').shapeType == 'Point' and 'MapUnit' in [field.name for field in arcpy.ListFields(f'{arcpy.env.workspace}/{dataset}/{fc}',field_type='String')]]))):
            arcpy.AddMessage("Generating temporary point layer features...")
            pnt_lyrs = []
            for n in range(len(pnt_fc_names)):
                arcpy.management.MakeFeatureLayer(f'{dataset}/{pnt_fc_names[n]}',f'pnt_lyr_{n}')
                pnt_lyrs.append(f'pnt_lyr_{n}')
            pnt_lyrs = tuple(pnt_lyrs)
            arcpy.AddMessage("Layer point features generated.\n")
            pnt_oid = []
            pnt_mapunit = []
            arcpy.AddMessage(f"Generating temporary polygon layer feature of {poly_nomin}...")
            arcpy.management.MakeFeatureLayer(f'{dataset}/{poly_nomin}','mapunit_poly_lyr')
            arcpy.AddMessage("Polygon layer feature generated.\n\nFilling out MapUnit field for point feature classes...")
            for n in range(len(pnt_lyrs)):
                for field in arcpy.ListFields(pnt_lyrs[n]):
                    oid_field_name = field.name
                    break
                pnt_oid = []
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
            arcpy.AddMessage("MapUnit field for point feature classes in %s dataset have been filled.\n" % dataset)
        else:
            arcpy.AddMessage("No point feature classes with a MapUnit field were found in %s dataset.\n" % dataset)

    arcpy.AddMessage("Saving edits...")

    try:
        edit.stopOperation()
    except Exception:
        pass
    try:
        edit.stopEditing(save_changes=True)
    except Exception:
        pass

    arcpy.AddMessage("Edits saved!\n\nStarting new editing session...")

    edit = arcpy.da.Editor(arcpy.env.workspace)

    edit.startEditing(with_undo=False,multiuser_mode=False)
    edit.startOperation()

    try:
        del poly_nomin ; del pnt_fc_names
    except Exception:
        pass
    try:
        del pnt_lyrs ; del pnt_oid ; del pnt_mapunit ; del selected_polys
    except Exception:
        pass

    gc.collect()

    arcpy.AddMessage("New editing session started.\n\nAdding information to point feature classes to Symbol field based upon DescriptionOfMapUnits table...")

    mapunit_symbol = dict()

    for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits',['MapUnit','Symbol']):
        if not None in (row[0],row[1]) and not row[0] in frozenset(mapunit_symbol.keys()):
            mapunit_symbol[row[0]] = row[1]

    mapunits = frozenset(mapunit_symbol.keys())

    for dataset in datasets:
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
            if arcpy.Describe(f'{arcpy.env.workspace}/{dataset}/{fc}').shapeType == 'Point':
                fields = tuple([field.name for field in arcpy.ListFields(f'{arcpy.env.workspace}/{dataset}/{fc}',field_type='String')])
                if 'MapUnit' in fields and 'Symbol' in fields:
                    with arcpy.da.UpdateCursor(f'{arcpy.env.workspace}/{dataset}/{fc}',['MapUnit','Symbol']) as cursor:
                        for row in cursor:
                            if row[0] in mapunits:
                                row[1] = mapunit_symbol[row[0]]
                            cursor.updateRow(row)

    arcpy.AddMessage("Symbol field for point feature classes successfully filled.\n\nSaving edits...")

    try:
        edit.stopOperation()
    except Exception:
        pass
    try:
        edit.stopEditing(save_changes=True)
    except Exception:
        pass

    arcpy.AddMessage('Edits saved!')

    try:
        arcpy.env.workspace = current_workspace[:]
    except Exception:
        pass

    gc.collect()

fill_pnt_mapunit_field(gdb_path)
