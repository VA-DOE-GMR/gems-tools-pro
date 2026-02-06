import arcpy,os,sys
from typing import Union
from array import array
from misc_arcpy_ops import default_env_parameters,explicit_typo_fix,textEnforcing,enforceLabels,deselectObjects
from misc_ops import ref_info,makeListIntArray
from re import sub as re_sub
from fundamentals import hsv_into_rgb,hsl_into_rgb,lab_into_rgb,cmy_into_rgb,rgb_into_cmy,cmy_into_wpg

# sys.argv[0] is reserved.
gdb_path = sys.argv[1]
enable_process = tuple([sys.argv[n] for n in range(2,11)])

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

def getOIDSelectionStr(oids : array, oid_name : str) -> Union[None,str]:
    if len(oids) >= 2:
        return f'{oid_name} IN ({",".join(oids)})'
    elif len(oids) == 1:
        return f'{oid_name} = {oids[0]}'
    else:
        return None

# This is for the scenario where an entry exists in the Glossary table where the
# Term field is <Null>.
class Blank_Term:

    def __init__(self):
        self.counter = 0

    def newUnknown(self) -> str:
        self.counter += 1
        return f'zzz_UNKNOWN_{str(self.counter).zfill(5)}'

# All processes are designed to run independently of each other.
def autofill_GeMS(gdb_path : str, enable_process : tuple):
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
    deselectObjects((datasets := tuple(arcpy.ListDatasets())))

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

    arcpy.AddMessage("Typos and invalid capitalizations have been rectified.\n\n")

    if enable_process[0] == 'true':

        null_items = {None,0}

        def getBrokenPoints(feature_item : str, oid_name : str) -> array:
            oids = []
            for row in arcpy.da.SearchCursor(feature_item,(oid_name,'SHAPE@XY')):
                if row[1] in null_items:
                    oids.append(row[0])
                elif row[1][0] == 0 and row[1][1] == 0:
                    oids.append(row[0])
            return makeListIntArray(oids)

        getBrokenPolylines = lambda feature_item, oid_name : makeListIntArray([row[0] for row in arcpy.da.SearchCursor(feature_item,(oid_name,'SHAPE@LENGTH')) if row[1] in null_items])

        getBrokenPolygons = lambda feature_item, oid_name : makeListIntArray([row[0] for row in arcpy.da.SearchCursor(feature_item,(oid_name,'SHAPE@LENGTH','SHAPE@AREA')) if row[1] in null_items and row[2] in null_items])

        arcpy.AddMessage('Checking for features with invalid geometry...')
        for dataset in datasets:
            for fc in arcpy.ListFeatureClasses(feature_dataset=dataset):
                if fc in annotation_items:
                    continue
                arcpy.AddMessage(f'Working on: {dataset}/{fc}...')
                oid_name = None
                for field in tuple(arcpy.ListFields((feature_item := f'{dataset}/{fc}'),field_type='OID')):
                    oid_name = field.name
                    break
                match arcpy.da.Describe(feature_item)['shapeType']:
                    case 'Point':
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPoints(feature_item,oid_name)),oid_name)),str):
                            del select_str
                            continue
                        arcpy.AddMessage(f"\n{feature_item} has features with potentially corrupted geometry!\nAttempting to repair geometry...")
                        arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/{feature_item}','temp_pnt_lyr')
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_pnt_lyr','NEW_SELECTION',select_str),'KEEP_NULL','ESRI')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPoints(feature_item,oid_name)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_pnt_lyr','NEW_SELECTION',select_str),'KEEP_NULL','OGC')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPoints(feature_item,oid_name)),oid_name)),str):
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
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolylines(feature_item,oid_name)),oid_name)),str):
                            continue
                        arcpy.AddMessage(f"\n{feature_item} has features with potentially corrupted geometry!\nAttempting to repair geometry...")
                        arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/{feature_item}','temp_line_lyr')
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_line_lyr','NEW_SELECTION',select_str),'KEEP_NULL','ESRI')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolylines(feature_item,oid_name)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_line_lyr','NEW_SELECTION',select_str),'KEEP_NULL','OGC')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolylines(feature_item,oid_name)),oid_name)),str):
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
                                arcpy.AddError(f"UNABLE TO DELETE NULL GEOMETRY ITEMS FROM {feature_item} FOR UNKNOWN REASONS!!!\n\n")
                                continue
                        edit.end_session()
                        arcpy.AddMessage("Problematic items have been successfully removed!\n")
                    case 'Polygon':
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolygons(feature_item,oid_name)),oid_name)),str):
                            continue
                        arcpy.AddMessage(f"\n{feature_item} has features with potentially corrupted geometry!\nAttempting to repair geometry...")
                        arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/{feature_item}','temp_polygon_lyr')
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_polygon_lyr','NEW_SELECTION',select_str),'KEEP_NULL','ESRI')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolygons(feature_item,oid_name)),oid_name)),str):
                            arcpy.AddMessage(f'Repair of {feature_item} was successful!\n')
                            continue
                        edit = GeMS_Editor()
                        arcpy.management.RepairGeometry(arcpy.management.SelectLayerByAttribute('temp_polygon_lyr','NEW_SELECTION',select_str),'KEEP_NULL','OGC')
                        edit.end_session()
                        if not isinstance((select_str := getOIDSelectionStr((broken_oids := getBrokenPolygons(feature_item,oid_name)),oid_name)),str):
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
                                arcpy.AddError(f"UNABLE TO DELETE NULL GEOMETRY ITEMS FROM {feature_item} FOR UNKNOWN REASONS!!!\n\n")
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

    # Multi-Color/-Patterned MapUnits are skipped, excluding water and alluvium,
    # which have an explicit symbol used for them.
    if enable_process[1] == 'true':

        arcpy.AddMessage("\nObtaining Symbology data from MapUnitPolys and MapUnitOverlayPolys and applying them to DescriptionOfMapUnits table...")

        # This prevents a glitch concerning Symbology of a feature class still having information on deleted symbology that can transpire. Cause is undetermined.
        valid_units = set()
        valid_labels_dict = {}
        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                if 'MapUnit' in fc and not fc in annotation_items:
                    for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/{dataset}/{fc}',('MapUnit','Label')):
                        if not row[0] is None:
                            valid_units.add(row[0])
                            if not row[1] is None and row[0] != row[1]:
                                valid_labels_dict[row[1]] = row[0]

        valid_labels = set(valid_labels_dict.keys())

        aprx = arcpy.mp.ArcGISProject('CURRENT')
        rgb_mapunits = {}
        cmy_mapunits = {}
        dups = set()

        for m in aprx.listMaps():
            for lyr in m.listLayers():
                if 'MapUnit' in lyr.name and not lyr.name in annotation_items:
                    # This prevents Symbology from feature classes and items outside from the geodatabase from being included.
                    if not isinstance((lyr_source := lyr.dataSource),str):
                        continue
                    elif not lyr_source.replace('\\','/').startswith(arcpy.env.workspace):
                        continue
                    sym = lyr.symbology
                    if getattr(sym.renderer,'groups',None) is None:
                        continue
                    for grp in sym.renderer.groups:
                        for itm in grp.items:
                            if not (unit_name := itm.label) in valid_units and not unit_name in valid_labels:
                                continue
                            try:
                                color_space = tuple(itm.symbol.color.keys())
                            except Exception:
                                continue
                            if len(color_space) == 1:
                                color_space = color_space[0]
                                if not unit_name in rgb_mapunits.keys() or unit_name in valid_labels:
                                    match color_space:
                                        case 'RGB':
                                            rgb_vals = tuple(itm.symbol.color[color_space])
                                            rgb_mapunits[unit_name] = rgb_vals[:]
                                            cmy_mapunits[unit_name] = rgb_into_cmy(rgb_vals[0],rgb_vals[1],rgb_vals[2])
                                            del rgb_vals
                                        case 'HSV':
                                            hsv_vals = tuple(itm.symbol.color[color_space])
                                            # This fixes a weird glitch related to specifically running in ArcGIS Pro. For example,
                                            # hsv_into_rgb is supposed to return a tuple of 3 integers. Instead, it returns of 3
                                            # floats and seems to ignore the round() function. This does not happen when running this
                                            # function outside ArcGIS Pro. map(round,hsv_into_rgb()) fixes this issue.
                                            rgb_mapunits[unit_name] = tuple(map(round,hsv_into_rgb(hsv_vals[0],hsv_vals[1],hsv_vals[2])))
                                            cmy_mapunits[unit_name] = rgb_into_cmy(rgb_mapunits[unit_name][0],rgb_mapunits[unit_name][1],rgb_mapunits[unit_name][2])
                                            del hsv_vals
                                        case 'HSL':
                                            hsl_vals = tuple(itm.symbol.color[color_space])
                                            rgb_mapunits[unit_name] = tuple(map(round,hsl_into_rgb(hsl_vals[0],hsl_vals[1],hsl_vals[2])))
                                            cmy_mapunits[unit_name] = rgb_into_cmy(rgb_mapunits[unit_name][0],rgb_mapunits[unit_name][1],rgb_mapunits[unit_name][2])
                                            del hsl_vals
                                        case 'CMYK':
                                            cmy_vals = tuple(itm.symbol.color[color_space])
                                            rgb_mapunits[unit_name] = tuple(map(round,cmy_into_rgb(cmy_vals[0],cmy_vals[1],cmy_vals[2])))
                                            cmy_mapunits[unit_name] = cmy_vals[:]
                                            del cmy_vals
                                        case 'Grayscale':
                                            rgb_mapunits[unit_name] = ((gs_num := tuple(itm.symbol.color[color_space])[0]),gs_num,gs_num)
                                            cmy_mapunits[unit_name] = tuple(map(round,cmy_into_rgb(gs_num,gs_num,gs_num)))
                                            del gs_num
                                        case _:
                                            lab_vals = tuple(itm.symbol.color[color_space])
                                            rgb_mapunits[unit_name] = tuple(map(round,lab_into_rgb(lab_vals[0],lab_vals[1],lab_vals[2])))
                                            cmy_mapunits[unit_name] = rgb_into_cmy(rgb_mapunits[unit_name][0],rgb_mapunits[unit_name][1],rgb_mapunits[unit_name][2])
                                            del lab_vals
                                elif color_space == 'RGB':
                                    rgb_vals = tuple(itm.symbol.color[color_space])
                                    if rgb_vals[0] != rgb_mapunits[unit_name][0] or rgb_vals[1] != rgb_mapunits[unit_name][1] or rgb_vals[2] != rgb_mapunits[unit_name][2]:
                                        dups.add(unit_name)
                                    del rgb_vals
                                elif color_space == 'CMYK':
                                    cmy_vals = tuple(itm.symbol.color[color_space])
                                    if cmy_vals[0] != cmy_mapunits[unit_name][0] or cmy_vals[1] != cmy_mapunits[unit_name][1] or cmy_vals[2] != cmy_mapunits[unit_name][2]:
                                        dups.add(unit_name)
                                    del cmy_vals
                                elif color_space == 'HSL':
                                    hsl_vals = tuple(itm.symbol.color[color_space])
                                    rgb_vals = tuple(map(round,hsl_into_rgb(hsl_vals[0],hsl_vals[1],hsl_vals[2])))
                                    if rgb_vals[0] != rgb_mapunits[unit_name][0] or rgb_vals[1] != rgb_mapunits[unit_name][1] or rgb_vals[2] != rgb_mapunits[unit_name][2]:
                                        dups.add(unit_name)
                                    del hsl_vals ; del rgb_vals
                                elif color_space == 'HSV':
                                    hsv_vals = tuple(itm.symbol.color[color_space])
                                    rgb_vals = tuple(map(round,hsv_into_rgb(hsv_vals[0],hsv_vals[1],hsv_vals[2])))
                                    if rgb_vals[0] != rgb_mapunits[unit_name][0] or rgb_vals[1] != rgb_mapunits[unit_name][1] or rgb_vals[2] != rgb_mapunits[unit_name][2]:
                                        dups.add(unit_name)
                                    del hsv_vals ; del rgb_vals
                                elif color_space == 'Grayscale':
                                    if (gs_num := tuple(itm.symbol.color[color_space])[0]) != rgb_mapunits[unit_name][0] or gs_num != rgb_mapunits[unit_name][1] or gs_num != rgb_mapunits[unit_name][2]:
                                        dups.add(unit_name)
                                    del gs_num
                                else:
                                    lab_vals = tuple(itm.symbol.color[color_space])
                                    rgb_vals = tuple(map(round,lab_into_rgb(lab_vals[0],lab_vals[1],lab_vals[2])))
                                    if rgb_vals[0] != rgb_mapunits[unit_name][0] or rgb_vals[1] != rgb_mapunits[unit_name][1] or rgb_vals[2] != rgb_mapunits[unit_name][2]:
                                        dups.add(unit_name)
                                    del lab_vals ; del rgb_vals
                            del unit_name
                    del sym

        try: del color_space
        except NameError: pass
        del valid_units

        if len(dups):
            for item in tuple(dups):
                # There should not be a case where two map units are given the same color designation/symbology.
                arcpy.AddWarning(f'{item} has more than one color symbol designated for the same MapUnit between two feature classes.')
                rgb_mapunits.pop(item)
                cmy_mapunits.pop(item)

        del dups ; del aprx

        if len(((units := tuple(rgb_mapunits.keys())))):

            # This accounts for Value and Label values in Symbology not being identical for a MapUnit.
            inconsistent_symbology = []

            for unit in units:
                if not unit.isalnum():
                    actual_mapunit = valid_labels_dict[unit]
                    if not actual_mapunit in rgb_mapunits.keys():
                        rgb_mapunits[actual_mapunit] = rgb_mapunits[unit]
                        cmy_mapunits[actual_mapunit] = cmy_mapunits[unit]
                        rgb_mapunits.pop(unit)
                        cmy_mapunits.pop(unit)
                    else:
                        rgb_mapunits.pop(actual_mapunit)
                        rgb_mapunits.pop(unit)
                        cmy_mapunits.pop(actual_mapunit)
                        cmy_mapunits.pop(unit)
                        inconsistent_symbology.append((actual_mapunit,unit))

            try: del actual_mapunit
            except NameError: pass

            if len((inconsistent_symbology := tuple(inconsistent_symbology))):
                for item in inconsistent_symbology:
                    arcpy.AddWarning(f"Inconsistent Symbology with: {item[0]}/{item[1]}")
                arcpy.AddMessage("\nPlease make sure the prior listed MapUnits have the Value and Label values in the Symbology consistent for all features.\n")

            del inconsistent_symbology

            units = tuple(rgb_mapunits.keys())

            symbol_mapunits = dict()

            for unit in units:
                symbol_mapunits[unit] = cmy_into_wpg(cmy_mapunits[unit])

            edit = GeMS_Editor()

            for unit in units:
                rgb_mapunits[unit] = f'{str(rgb_mapunits[unit][0]).zfill(3)},{str(rgb_mapunits[unit][1]).zfill(3)},{str(rgb_mapunits[unit][2]).zfill(3)}'
            with arcpy.da.UpdateCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits',('MapUnit','Symbol','AreaFillRGB')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if row[0] in units:
                            if (new_str := symbol_mapunits[row[0]]) != row[1]:
                                update_row = True
                                row[1] = new_str[:]
                            if (new_str := rgb_mapunits[row[0]]) != row[2]:
                                update_row = True
                                row[2] = new_str[:]
                            del new_str
                        if update_row:
                            cursor.updateRow(row)
                    del update_row

            del symbol_mapunits

            edit.end_session()

        del rgb_mapunits ; del cmy_mapunits

        arcpy.AddMessage("Process successfully completed.\n\n")

    # Fillout Symbol and Label fields for feature classes in geodatabase using
    # corresponding information from DescriptionOfMapUnits table.
    if enable_process[2] == 'true':

        edit = GeMS_Editor()

        arcpy.AddMessage("Obtaining Label and Symbol information from DescriptionOfMapUnits table...")

        pairs = {row[0] : (row[1],row[2]) for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits',('MapUnit','Label','Symbol')) if not (row[1] is None and row[2] is None) and not row[0] is None}
        mapunits = set(pairs.keys())

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                if fc in annotation_items:
                    continue
                if 'MapUnit' in fc:
                    with arcpy.da.UpdateCursor(f'{arcpy.env.workspace}/{dataset}/{fc}',('MapUnit','Label','Symbol')) as cursor:
                        for row in cursor:
                            update_row = False
                            if row[0] in mapunits:
                                if (new_str := pairs[row[0]][0]) != row[1]:
                                    update_row = True
                                    row[1] = new_str
                                if (new_str := pairs[row[0]][1]) != row[2]:
                                    update_row = True
                                    row[2] = new_str
                                del new_str
                                if update_row:
                                    cursor.updateRow(row)
                            del update_row

        del mapunits ; del pairs

        arcpy.AddMessage("Changes successfully applied.\n\nSaving edits...")

        edit.end_session()

        arcpy.AddMessage("Edits saved!\n\n")

    # Autofill MapUnit fields in point feature classes
    if enable_process[3] == 'true':

        arcpy.AddMessage("Filling out MapUnit field of point feature classes in geodatabase based upon location relative to polygons in MapUnitPolys...\n")

        # Fill MapUnit field for point feature classes in geodatabase
        # based upon relative MapUnitPolys polygon locations.

        # Points on the border between two or more polygons will have their MapUnit
        # value arbitrarily assigned.


        def getMapUnits(poly_item : str) -> tuple:

            mapunits = set()
            for row in arcpy.da.SearchCursor(poly_item,'MapUnit'):
                if not row[0] is None:
                    if row[0].replace(' ','') != '':
                        mapunits.add(row[0])
            return tuple(mapunits)


        edit = GeMS_Editor()

        arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/GeologicMap/MapUnitPolys','temp_poly_lyr')
        mapunits = getMapUnits('temp_poly_lyr')

        hasCrossSection = False ; num_cross_sections = 0

        for dataset in datasets:
            if not 'CrossSection' in dataset:
                for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point')):
                    if fc == 'MapUnitPoints':
                        continue
                    feature_item = f'{arcpy.env.workspace}/{dataset}/{fc}'
                    if not 'MapUnit' in [field.name for field in tuple(arcpy.ListFields(feature_item,field_type='String'))]:
                        del feature_item
                        continue
                    arcpy.AddMessage(f'Working on: {fc} in {dataset}...')
                    fields = ['MapUnit']
                    for field in tuple(arcpy.ListFields(feature_item)):
                        fields.insert(0,field.name)
                        break
                    fields = tuple(fields)
                    arcpy.management.MakeFeatureLayer(feature_item,'temp_pnt_lyr')
                    matched = dict()
                    for mapunit in mapunits:
                        selected_polys = arcpy.management.SelectLayerByAttribute('temp_poly_lyr','NEW_SELECTION',f"MapUnit = '{mapunit}'")
                        selected_pnts,redundant,count = arcpy.management.SelectLayerByLocation('temp_pnt_lyr','INTERSECT',selected_polys,'','NEW_SELECTION')
                        del redundant
                        if int(count):
                            for row in arcpy.da.SearchCursor(selected_pnts,fields):
                                matched[row[0]] = mapunit
                        del count ; del selected_polys ; del selected_pnts
                    if len(matched):
                        oids = set(matched.keys())
                        with arcpy.da.UpdateCursor(feature_item,fields) as cursor:
                            for row in cursor:
                                if row[0] in oids:
                                    if row[1] != (new_str := matched[row[0]]):
                                        row[1] = new_str[:]
                                        cursor.updateRow(row)
                                    del new_str
                        del oids
                    del matched ; del fields ; del feature_item
            else:
                num_cross_sections += 1
                hasCrossSection = True

        del mapunits

        if hasCrossSection:
            for dataset in datasets:
                if 'CrossSection' in dataset:
                    found_poly = False
                    for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
                        if 'MapUnitPolys' in fc:
                            arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/{dataset}/{fc}','temp_poly_lyr')
                            found_poly = True
                            break
                    if not found_poly:
                        # There realistically should be no more than 26 cross
                        # sections for a single GeMS geodatabase. This is just
                        # to future-proof this tool.
                        if num_cross_sections <= 26:
                            arcpy.AddMessage(f'\n{dataset} is missing CS{dataset[-1]}MapUnitPolys! Skipping {dataset}.\n')
                        elif num_cross_sections <= 702:
                            arcpy.AddMessage(f'\n{dataset} is missing CS{dataset[-2:]}MapUnitPolys! Skipping {dataset}.\n')
                        elif num_cross_sections <= 18278:
                            arcpy.AddMessage(f'\n{dataset} is missing CS{dataset[-3:]}MapUnitPolys! Skipping {dataset}.\n')
                        elif num_cross_sections <= 475254:
                            arcpy.AddMessage(f'\n{dataset} is missing CS{dataset[-3:]}MapUnitPolys! Skipping {dataset}.\n')
                        elif num_cross_sections <= 12356630:
                            arcpy.AddMessage(f'\n{dataset} is missing CS{dataset[-4:]}MapUnitPolys! Skipping {dataset}.\n')
                        del found_poly
                        continue
                    del found_poly
                    mapunits = getMapUnits('temp_poly_lyr')
                    for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point')):
                        if fc.endswith('MapUnitPoints'):
                            continue
                        feature_item = f'{arcpy.env.workspace}/{dataset}/{fc}'
                        if not 'MapUnit' in [field.name for field in tuple(arcpy.ListFields(feature_item,field_type='String'))]:
                            del feature_item
                            continue
                        arcpy.AddMessage(f'Working on: {fc} in {dataset}...')
                        fields = ['MapUnit']
                        for field in tuple(arcpy.ListFields(feature_item)):
                            fields.insert(0,field.name)
                            break
                        fields = tuple(fields)
                        arcpy.management.MakeFeatureLayer(feature_item,'temp_pnt_lyr')
                        matched = dict()
                        for mapunit in mapunits:
                            selected_polys = arcpy.management.SelectLayerByAttribute('temp_poly_lyr','NEW_SELECTION',f"MapUnit = '{mapunit}'")
                            selected_pnts,redundant,count = arcpy.management.SelectLayerByLocation('temp_pnt_lyr','INTERSECT',selected_polys,'','NEW_SELECTION')
                            del redundant
                            if int(count):
                                for row in arcpy.da.SearchCursor(selected_pnts,fields):
                                    matched[row[0]] = mapunit
                            del count ; del selected_polys ; del selected_pnts
                        if len(matched):
                            oids = set(matched.keys())
                            with arcpy.da.UpdateCursor(feature_item,fields) as cursor:
                                for row in cursor:
                                    if row[0] in oids:
                                        if row[1] != (new_str := matched[row[0]]):
                                            row[1] = new_str[:]
                                            cursor.updateRow(row)
                                        del new_str
                            del oids
                        del matched ; del fields ; del feature_item
                    del mapunits

        del hasCrossSection ; del num_cross_sections

        arcpy.AddMessage("Changes successfully applied.\n\nSaving edits...")

        edit.end_session()

        arcpy.AddMessage("Edits saved!\n\n")

    # Alphabetize Glossary and Add missing terms
    if enable_process[4] == 'true':

        arcpy.AddMessage("Alphabetizing and adding missing terms to Glossary...")

        edit = GeMS_Editor()

        used_terms = set()
        valid_fields = {'Type','IdentityConfidence','ExistenceConfidence','LocationConfidence'}

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                feature_item = f'{arcpy.env.workspace}/{dataset}/{fc}'
                if len((fields := tuple([field.name for field in arcpy.ListFields(feature_item,field_type='String') if field.name in valid_fields]))):
                    field_range = range(len(fields))
                    for row in arcpy.da.SearchCursor(feature_item,fields):
                        for n in field_range:
                            used_terms.add(row[n])
                    del field_range

        del fields ; del valid_fields ; del feature_item

        for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits',['ParagraphStyle','GeoMaterialConfidence']):
            used_terms.add(row[0])
            used_terms.add(row[1])

        if None in used_terms:
            used_terms.remove(None)
        if '' in used_terms:
            used_terms.remove('')

        logged_terms = []
        logged_def = []
        logged_ID = []
        blanks = Blank_Term()
        copy_count = dict()

        selected_rows,count = arcpy.management.SelectLayerByAttribute((glossary_path := f'{arcpy.env.workspace}/Glossary'),'NEW_SELECTION',"Term IS NULL And Definition IS NULL And DefinitionSourceID IS NULL")

        if count:
            arcpy.management.DeleteRows(selected_rows)

        del selected_rows ; del count

        with arcpy.da.UpdateCursor(glossary_path,('Term','Definition','DefinitionSourceID')) as cursor:
            for row in cursor:
                update_row = False
                if None in (tester := set((row[0],row[1],row[2]))) and len(tester) == 1 and not row[2] is None:
                    del tester
                    continue
                del tester
                if row[0] is None:
                    update_row = True
                    row[0] = (new_str := blanks.newUnknown())
                    logged_terms.append(new_str)
                    logged_def.append(row[1])
                    logged_ID.append(row[2])
                else:
                    if row[0] in logged_terms:
                        if not row[0] in copy_count.keys():
                            copy_count[row[0]] = 1
                            new_str = f'{row[0]} [Copy (00001)]'
                        else:
                            copy_count[row[0]] += 1
                            new_str = f'{row[0]} [Copy ({copy_count[row[0]].zfill(5)})]'
                        update_row = True
                        row[0] = new_str
                        logged_terms.append(new_str)
                        del new_str
                    else:
                        logged_terms.append(row[0])
                    logged_def.append(row[1])
                    logged_ID.append(row[2])
                if update_row:
                    cursor.updateRow(row)

        try: del update_row
        except NameError: pass
        try: del blanks
        except NameError: pass
        try: copy_count
        except NameError: pass

        for term in (logged_terms := tuple(logged_terms)):
            if term in used_terms:
                used_terms.remove(term)

        terms = {logged_terms[n] : (logged_def[n],logged_ID[n]) for n in range(len(logged_terms))}

        del logged_terms ; del logged_def ; del logged_ID

        if len((used_terms := tuple(used_terms))):
            for used_term in used_terms:
                terms[used_term] = (None,None)

        del used_terms

        sorted_terms = tuple(sorted(terms.keys(),key=str.lower))

        counter = 0

        for row in arcpy.da.SearchCursor(glossary_path,['Term']):
            counter += 1

        if counter > len(sorted_terms):
            while counter != len(sorted_terms):
                other_counter = 1
                with arcpy.da.UpdateCursor(glossary_path,['Term']) as cursor:
                    for row in cursor:
                        other_counter += 1
                        if other_counter == counter:
                            cursor.deleteRow()
                            counter -= 1
            del other_counter
        elif counter < len(sorted_terms):
            with arcpy.da.InsertCursor(glossary_path,('Term','Definition','DefinitionSourceID','Glossary_ID')) as cursor:
                for n in range(len(sorted_terms)-counter):
                    cursor.insertRow((None,None,None,None))

        with arcpy.da.UpdateCursor(glossary_path,('Term','Definition','DefinitionSourceID')) as cursor:
            counter = -1
            for row in cursor:
                counter += 1
                if row[0] != sorted_terms[counter]:
                    row[0] = sorted_terms[counter]
                    row[1] = terms[sorted_terms[counter]][0]
                    row[2] = terms[sorted_terms[counter]][1]
                    cursor.updateRow(row)

        del sorted_terms ; del counter ; terms ; del glossary_path

        code_directory = arcpy.env.workspace[:]

        naloe_zelmatitum = False

        if os.path.exists('Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'):
            try:
                arcpy.AddMessage('\n\nConnecting to pre-existing SDE...')
                arcpy.env.workspace = 'Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'
                arcpy.AddMessage('Successfully established connection!')
                naloe_zelmatitum = True
            except Exception:
                arcpy.AddError("\n\nSomething went wrong when trying to connect via pre-existing SDE.\n\nSkipping auto-filling Definition field in Glossary.")

        if naloe_zelmatitum:
            arcpy.AddMessage('\n\nChecking and/or updating Glossary table based upon information in master Glossary table...')

            temp_table = arcpy.management.MakeTableView("DGMRgeo.DBO.Glossary",'temp_table')
            term_dict = {row[0] : (row[1],row[2]) for row in arcpy.da.SearchCursor('temp_table',('Term','Definition','DefinitionSourceID')) if not None in (row[0],row[1],row[2])}

            del temp_table

            master_terms = set(term_dict.keys())
            arcpy.env.workspace = code_directory[:]

            del code_directory

            for field in arcpy.ListFields((glossary_path := f'{arcpy.env.workspace}/Glossary'),field_type='String'):
                if field.name == 'Definition':
                    set_max_chars = field.length
                    break

            if set_max_chars < (required_max_chars := len(max([term_dict[term][0] for term in tuple(master_terms)],key=len))):
                edit.end_session()
                arcpy.management.AlterField(glossary_path,'Definition',field_length=required_max_chars)
                edit = GeMS_Editor()

            del set_max_chars ; del required_max_chars ; del glossary_path

            with arcpy.da.UpdateCursor(f'{arcpy.env.workspace}/Glossary',('Term','Definition','DefinitionSourceID')) as cursor:
                for row in cursor:
                    update_row = False
                    if row[0] in master_terms:
                        if row[1] != term_dict[row[0]][0]:
                            update_row = True
                            row[1] = term_dict[row[0]][0]
                        if row[2] != term_dict[row[0]][1]:
                            update_row = True
                            row[2] = term_dict[row[0]][1]
                    if update_row:
                        cursor.updateRow(row)

            del update_row ; del master_terms ; del term_dict

            arcpy.AddMessage('Glossary table has been successfully checked and/or updated.')

        del naloe_zelmatitum

        arcpy.AddMessage("Process successfully completed!\n\nSaving edits...")

        edit.end_session()

        arcpy.AddMessage("Edits successfully saved!\n\n")

    # Autopopulate DataSources table
    if enable_process[5] == 'true':

        arcpy.AddMessage('Filling out and populating DataSources table...')

        edit = GeMS_Editor()

        found_items = set()
        valid_fields = {'DataSourceID','LocationSourceID','OrientationSourceID'}

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                feature_item = f'{arcpy.env.workspace}/{dataset}/{fc}'
                if len((dasid_fields := tuple([field.name for field in tuple(arcpy.ListFields(feature_item,field_type='String')) if field.name in valid_fields]))):
                    field_range = range(len(dasid_fields))
                    for row in arcpy.da.SearchCursor(feature_item,dasid_fields):
                        for n in field_range:
                            found_items.add(row[n])
                    del field_range

        del dasid_fields ; del valid_fields ; del feature_item

        for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits','DescriptionSourceID'):
            found_items.add(row[0])

        for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/Glossary','DefinitionSourceID'):
            found_items.add(row[0])

        if None in found_items:
            found_items.remove(None)

        found_dasids = set()

        for n in range(len((found_items := list(found_items)))):
            found_items[n] = found_items[n].replace(' ','')

        for item in (found_items := tuple(found_items)):
            if 'DAS' in item:
                if '|' in item:
                    temp_item = item[:]
                    while '|' in temp_item:
                        if temp_item.startswith('DAS'):
                            found_dasids.add(temp_item[:temp_item.find('|')])
                        temp_item = temp_item[temp_item.find('|')+1:]
                    if temp_item.startswith('DAS'):
                        found_dasids.add(temp_item)
                    del temp_item
                else:
                    found_dasids.add(item)

        found_dasids = tuple(found_dasids)

        now_num_rows = 0

        for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DataSources','DataSources_ID'):
            now_num_rows += 1

        code_directory = arcpy.env.workspace[:]

        naloe_zelmatitum = False

        if os.path.exists('Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'):
            try:
                arcpy.AddMessage('\n\nConnecting to pre-existing SDE...')
                arcpy.env.workspace = 'Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'
                arcpy.AddMessage('Successfully established connection!')
                naloe_zelmatitum = True
            except Exception:
                arcpy.AddError("\n\nSomething went wrong when trying to connect via pre-existing SDE.\n\nSkipping this process.")

        if naloe_zelmatitum:

            arcpy.AddMessage('\n\nChecking and/or updating DataSources table based upon information in master DataSources table...')

            temp_table = arcpy.management.MakeTableView("DGMRgeo.DBO.DataSources",'temp_table')

            source_dict = {row[3] : (row[0],row[1],row[2]) for row in arcpy.da.SearchCursor('temp_table',('Source','Notes','URL','DataSources_ID')) if not None in (row[0],row[3])}
            master_dasids = set(source_dict.keys())
            dasids_dict = {int(item[3:]) : item for item in found_dasids if item in master_dasids}
            dasids_nums = tuple(sorted(dasids_dict.keys()))
            valid_dasids = tuple([dasids_dict[num] for num in dasids_nums])

            del dasids_dict ; del dasids_nums

            arcpy.env.workspace = code_directory[:]

            for field in arcpy.ListFields((datasources_path := f'{arcpy.env.workspace}/DataSources'),field_type='String'):
                if field.name == 'Source':
                    set_max_chars = field.length
                    break

            if set_max_chars < (required_max_chars := len(max([source_dict[valid_dasid][0] for valid_dasid in valid_dasids],key=len))):
                edit.end_session()
                arcpy.management.AlterField(datasources_path,'Source',field_length=required_max_chars)
                edit = GeMS_Editor()

            del temp_table ; del master_dasids ; del found_dasids ; del set_max_chars ; del required_max_chars

            if (missing_num_rows := (num_rows := len(valid_dasids)) - now_num_rows) != 0:
                if missing_num_rows > 0:
                    with arcpy.da.InsertCursor(datasources_path,('Source','Notes','URL','DataSources_ID')) as cursor:
                        for num_row in range(missing_num_rows):
                            cursor.insertRow((None,None,None,None))
                else:
                    with arcpy.da.UpdateCursor(datasources_path,'DataSources_ID') as cursor:
                        for row in cursor:
                            if not row[0] in valid_dasids:
                                cursor.deleteRow()

            del missing_num_rows ; del num_rows

            counter = 0

            with arcpy.da.UpdateCursor(datasources_path,('Source','Notes','URL','DataSources_ID')) as cursor:
                for row in cursor:
                    if not (row[0] == source_dict[valid_dasids[counter]][0] and row[1] == source_dict[valid_dasids[counter]][1] and row[2] == source_dict[valid_dasids[counter]][2] and row[3] == valid_dasids[counter]):
                        row[0] = source_dict[valid_dasids[counter]][0]
                        row[1] = source_dict[valid_dasids[counter]][1]
                        row[2] = source_dict[valid_dasids[counter]][2]
                        row[3] = valid_dasids[counter]
                        cursor.updateRow(row)
                    counter += 1

            del counter ; del source_dict ; del valid_dasids

            #fill blanks
            with arcpy.da.UpdateCursor(datasources_path,('Notes','URL')) as cursor:
                for row in cursor:
                    row_updated = False
                    if not row[0] is None:
                        if row[0].strip() == '':
                            row[0] = None
                            row_updated = True
                    if not row[1] is None:
                        if row[1].strip() == '':
                            row[1] = None
                            row_updated = True
                    if row_updated:
                        cursor.updateRow(row)

            if 'NGMDB_ID' in [item.name for item in tuple(arcpy.ListFields(datasources_path))]:
                with arcpy.da.UpdateCursor(datasources_path,('URL','NGMDB_ID')) as cursor:
                    for row in cursor:
                        row_updated = False
                        if row[0] is None:
                            row[1] = None
                            row_updated = True
                        elif '.' in (row[0][-5],row[0][-4]):
                            try:
                                row[1] = int(row[0][row[0].rfind('_')+1:row[0].rfind('.')])
                                row_updated = True
                            except Exception:
                                try:
                                    row[1] = row[0][row[0].rfind('_')+1:row[0].rfind('.')]
                                    row_updated = True
                                except Exception:
                                    if not row[1] is None:
                                        row[1] = None
                                        row_updated = True
                        if row_updated:
                            cursor.updateRow(row)
            try: del row_updated
            except NameError: pass
            arcpy.AddMessage("DataSources table successfully processed!\n\n")

        else:

            arcpy.env.workspace = code_directory[:]

            arcpy.AddMessage("Unable to connect via SDEs! Process has been ended prematurely.\n\n")

        del code_directory ; del now_num_rows

        arcpy.AddMessage("Saving edits...")
        edit.end_session()
        arcpy.AddMessage("Edits successfully saved!\n")

        del naloe_zelmatitum

    # Enforce labels
    if enable_process[6] == 'true':

        arcpy.AddMessage("Checking and/or Correcting Label fields in all feature classes...")

        edit = GeMS_Editor()

        for dataset in datasets:
            for fc in tuple([item for item in arcpy.ListFeatureClasses(feature_dataset=dataset) if not item in annotation_items]):
                if 'Label' in (fc_fields := tuple([field.name for field in arcpy.ListFields(f'{dataset}/{fc}',field_type='String')])):
                    enforceLabels(f'{dataset}/{fc}')

        arcpy.AddMessage("Process successfully completed!\n\nSaving edits...")
        edit.end_session()
        arcpy.AddMessage("Edits successfully saved!\n\n")

    # Autofill _ID fields
    # This should always be the last or second last thing done if enabled and is enabled by default.
    if enable_process[7] == 'true':

        arcpy.AddMessage("Filling out _ID fields, excluding DataSources table...")

        edit = GeMS_Editor()

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                gems_id_writer(f'{arcpy.env.workspace}/{dataset}/{fc}',fc)

        for table in ('Glossary','DescriptionOfMapUnits'):
            gems_id_writer(f'{arcpy.env.workspace}/{table}',table)

        arcpy.AddMessage("Process successfully completed!\n\nSaving edits...")
        edit.end_session()
        arcpy.AddMessage("Edits successfully saved!\n\n")


    arcpy.env.workspace = current_workspace[:]

    if enable_process[8] == 'true':
        arcpy.AddMessage('Compacting GeMS geodatabase...')
        arcpy.management.Compact(arcpy.env.workspace)
        arcpy.AddMessage("GeMS geodatabase has been successfully compacted!")

autofill_GeMS(gdb_path,enable_process)
