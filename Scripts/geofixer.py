import arcpy,sys
from typing import Union
from array import array
from misc_arcpy_ops import default_env_parameters,explicit_typo_fix,textEnforcing,deselectObjects
from misc_ops import ref_info,makeListIntArray,getOIDSelectionStr

# sys.argv[0] is reserved.
gdb_path = sys.argv[1]
enable_process = tuple([sys.argv[n] for n in range(2,4)])

# Used to fill out _ID fields.
def gems_id_writer(item_path : str, item_name : str) -> None:
    '''This function handles generating new _ID values for items in a feature
    class or table.
    '''
    id_field = None

    for field in tuple(arcpy.ListFields(item_path,field_type='String')):
        if field.name.endswith('_ID'):
            id_field = field.name
            break

    if id_field is None:
        return None

    num_rows = 0

    for row in arcpy.da.SearchCursor(item_path,id_field):
        num_rows += 1

    z_num = len(str(num_rows))
    prefix = ref_info.getRootName(item_name)
    counter = 0

    with arcpy.da.UpdateCursor(item_path,id_field) as cursor:
        for row in cursor:
            counter += 1
            if (new_str := f'{prefix}{str(counter).zfill(z_num)}') != row[0]:
                row[0] = new_str
                cursor.updateRow(row)

    return None

# All processes are designed to run independently of each other.
def geofixer_GeMS(gdb_path : str, enable_process : tuple) -> None:
    """
    This autofills Attribute Table data based upon expected pre-existing data.
    Missing/Unfinished data will be skipped and left untouched.
    """

    current_workspace = arcpy.env.workspace[:]
    current_workspace = current_workspace.replace('\\','/')
    arcpy.env.workspace = gdb_path.replace('\\','/')

    arcpy.AddMessage(f'Path to GeMS geodatabase currently being processed: {arcpy.env.workspace}\n\n')

    default_env_parameters()

    # This ensures that no features are selected before running the tool.
    # Selected features will disrupt how this tool functions. It will not cause
    # any errors or abnormal behavior; however, it will cause certain things to
    # be skipped or completely ignored by the tool.
    deselectObjects((datasets := tuple([item for item in arcpy.ListDatasets() if item == 'GeologicMap' or 'CrossSection' in item])))

    # For simplification purposes.
    class GeMS_Editor:

        def __init__(self):

            self.edit = arcpy.da.Editor(arcpy.env.workspace)
            self.edit.startEditing(with_undo=False,multiuser_mode=False)
            self.edit.startOperation()

        def end_session(self):
            try:
                self.edit.stopOperation()
            except Exception:
                pass
            try:
                self.edit.stopEditing(save_changes=True)
            except Exception:
                pass

    # The following done as they are required to be fixed for the best output as
    # well as applying fixes and changes that will be required to be done
    # regardless.

    annotation_items = {fc for dataset in datasets for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Annotation'))}

    edit = GeMS_Editor()

    arcpy.AddMessage("Fixing explicit typos in feature classes and tables as well as invalid capitalizations...")

    # feature classes
    for item in (feature_items := tuple([f'{dataset}/{fc}' for dataset in datasets for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)) if not fc in annotation_items])):
        explicit_typo_fix(item)
    # tables
    for item in ('Glossary','DescriptionOfMapUnits'):
        explicit_typo_fix(item)

    # Enforce text consistency
    # feature classes
    for item in feature_items:
        textEnforcing(item)
    # tables
    textEnforcing('/DescriptionOfMapUnits')

    del feature_items

    edit.end_session()

    if enable_process[0] == 'true':

        null_items = {None,0}

        def getBrokenPoints(feature_item : str) -> array:
            oids = []
            for row in arcpy.da.SearchCursor(feature_item,('OID@','SHAPE@XY')):
                if row[1] in null_items:
                    oids.append(str(row[0]))
                elif row[1][0] == 0 and row[1][1] == 0:
                    oids.append(str(row[0]))
            return tuple(oids)

        getBrokenPolylines = lambda feature_item : tuple([str(row[0]) for row in arcpy.da.SearchCursor(feature_item,('OID@','SHAPE@LENGTH')) if row[1] in null_items])

        getBrokenPolygons = lambda feature_item : tuple([str(row[0]) for row in arcpy.da.SearchCursor(feature_item,('OID@','SHAPE@LENGTH','SHAPE@AREA')) if row[1] in null_items and row[2] in null_items])

        arcpy.AddMessage('Checking for features with invalid geometry...')
        for dataset in datasets:
            for fc in arcpy.ListFeatureClasses(feature_dataset=dataset):
                if fc in annotation_items:
                    continue
                arcpy.AddMessage(f'Checking: {dataset}/{fc}...')
                oid_name = None
                for field in tuple(arcpy.ListFields((feature_item := f'{dataset}/{fc}'),field_type='OID')):
                    oid_name = field.name
                    break
                match arcpy.da.Describe(feature_item)['shapeType']:
                    case 'Point':
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPoints(feature_item)),oid_name)),str):
                            del select_str
                            continue
                        arcpy.AddMessage(f"\n{feature_item} has features with potentially corrupted geometry!\nAttempting to repair geometry...")
                        arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/{feature_item}','temp_pnt_lyr')
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_pnt_lyr','NEW_SELECTION',select_str),'KEEP_NULL','ESRI')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPoints(feature_item)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_pnt_lyr','NEW_SELECTION',select_str),'KEEP_NULL','OGC')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPoints(feature_item)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        arcpy.AddMessage(f'Unable to repair the geometry corrupted items!\nDeleting problematic items from {feature_item}...')
                        edit = GeMS_Editor()
                        try:
                            arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_pnt_lyr','NEW_SELECTION',select_str),'DELETE_NULL','ESRI')
                        except Exception:
                            try:
                                arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_pnt_lyr','NEW_SELECTION',select_str),'DELETE_NULL','OGC')
                            except Exception:
                                edit.end_session()
                                arcpy.AddError(f"UNABLE TO DELETE NULL GEOMETRY ITEMS FROM {feature_item} FOR UNKNOWN REASONS!!!\n\n")
                                continue
                        edit.end_session()
                        arcpy.AddMessage("Problematic items have been successfully removed!\n")
                    case 'Polyline':
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolylines(feature_item)),oid_name)),str):
                            continue
                        arcpy.AddMessage(f"\n{feature_item} has features with potentially corrupted geometry!\nAttempting to repair geometry...")
                        arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/{feature_item}','temp_line_lyr')
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_line_lyr','NEW_SELECTION',select_str),'KEEP_NULL','ESRI')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolylines(feature_item)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_line_lyr','NEW_SELECTION',select_str),'KEEP_NULL','OGC')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolylines(feature_item)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        arcpy.AddMessage(f'Unable to repair the geometry corrupted items!\nDeleting problematic items from {feature_item}...')
                        edit = GeMS_Editor()
                        try:
                            arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_line_lyr','NEW_SELECTION',select_str),'DELETE_NULL','ESRI')
                        except Exception:
                            try:
                                arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_line_lyr','NEW_SELECTION',select_str),'DELETE_NULL','OGC')
                            except Exception:
                                edit.end_session()
                                arcpy.AddWarning(f"UNABLE TO DELETE NULL GEOMETRY ITEMS FROM {feature_item} FOR UNKNOWN REASONS!!!\n\n")
                                continue
                        edit.end_session()
                        arcpy.AddMessage("Problematic items have been successfully removed!\n")
                    case 'Polygon':
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolygons(feature_item)),oid_name)),str):
                            continue
                        arcpy.AddMessage(f"\n{feature_item} has features with potentially corrupted geometry!\nAttempting to repair geometry...")
                        arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/{feature_item}','temp_polygon_lyr')
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_polygon_lyr','NEW_SELECTION',select_str),'KEEP_NULL','ESRI')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolygons(feature_item)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_polygon_lyr','NEW_SELECTION',select_str),'KEEP_NULL','OGC')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolygons(feature_item)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        arcpy.AddMessage(f'Unable to repair the geometry corrupted items!\nDeleting problematic items from {feature_item}...')
                        edit = GeMS_Editor()
                        try:
                            arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_polygon_lyr','NEW_SELECTION',select_str),'DELETE_NULL','ESRI')
                        except Exception:
                            try:
                                arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_polygon_lyr','NEW_SELECTION',select_str),'DELETE_NULL','OGC')
                            except Exception:
                                edit.end_session()
                                # This should never happen.
                                arcpy.AddWarning(f"UNABLE TO DELETE NULL GEOMETRY ITEMS FROM {feature_item} FOR UNKNOWN REASONS!!!\n\n")
                                continue
                        edit.end_session()
                        arcpy.AddMessage("Problematic items have been successfully removed!\n")
                    case _:
                        pass
                try: del broken_oids
                except NameError: pass
                del oid_name ; del feature_item
        del null_items
        try: del select_str
        except NameError: pass
        arcpy.AddMessage("Process successfully completed!\n\n")

        del getBrokenPolylines ; del getBrokenPolygons

    arcpy.AddMessage("Typos and invalid capitalizations have been rectified.\n\n")

    if enable_process[1] == 'true':

        arcpy.AddMessage("Rectifying Multipart Features...")

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon') + arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polyline')):
                arcpy.AddMessage(f"Processing {fc}...")
                multipart_oids = []
                oid_name = None
                for field in arcpy.ListFields(f'{dataset}/{fc}',field_type='OID'):
                    oid_name = field.name[:]
                    break
                if oid_name is None:
                    continue
                for row in arcpy.da.SearchCursor(f'{dataset}/{fc}',('OID@','SHAPE@')):
                    partnum = 0
                    for part in row[1]:
                        if partnum == 1:
                            multipart_oids.append(row[0])
                            break
                        partnum += 1
                if len((multipart_oids := tuple(multipart_oids))):
                    temp_lyr = arcpy.management.MakeFeatureLayer(f'{dataset}/{fc}',r'memory\temp_lyr')
                    selected_features,count = arcpy.management.SelectLayerByAttribute(temp_lyr,'NEW_SELECTION',getOIDSelectionStr(multipart_oids,oid_name))
                    singlepart_features = arcpy.management.MultipartToSinglepart(selected_features,r'memory\singlepart_features')
                    counter = 0
                    for row in arcpy.da.SearchCursor(singlepart_features,'OID@'):
                        counter += 1
                    # If equal, no new parts were actually generated.
                    if int(count) != counter:
                        edit = GeMS_Editor()
                        arcpy.management.Append(singlepart_features,f'{dataset}/{fc}',schema_type='NO_TEST')
                        edit.end_session()
                        arcpy.management.Delete(selected_features)
                        edit = GeMS_Editor()
                        gems_id_writer(f'{dataset}/{fc}',fc)
                        edit.end_session()

        try: del count ; del counter
        except NameError: pass
        try: del multipart_oids ; del oid_name
        except NameError: pass
        try: del partnum
        except NameError: pass
        try: del temp_lyr ; del selected_features ; del singlepart_features
        except NameError: pass

        arcpy.AddMessage("Process completed!\n\n")

    arcpy.env.workspace = current_workspace[:]

    return None

geofixer_GeMS(gdb_path,enable_process)
