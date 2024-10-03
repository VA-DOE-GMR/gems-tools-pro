import arcpy,os,sys
from misc_arcpy_ops import default_env_parameters,explicit_typo_fix
from misc_ops import fixFieldItemString,ref_info,to_tuple
from re import sub as re_sub
from fundamentals import hsv_into_rgb,hsl_into_rgb,lab_into_rgb,cmy_into_rgb,rgb_into_cmy,cmy_into_wpg

gdb_path = sys.argv[1]
enable_process = tuple([sys.argv[n] for n in range(2,8)])

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

    arcpy.AddMessage(arcpy.env.workspace)

    # Also determines if ArcGIS Pro can take advantage of Nvidia GPU(s).
    default_env_parameters()

    datasets = tuple(arcpy.ListDatasets())

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

    # Removing explicit typos.

    edit = GeMS_Editor()

    arcpy.AddMessage("Fixing explicit typos in feature classes and tables as well as invalid capitalization...")

    # feature classes
    map(explicit_typo_fix,tuple([f'{dataset}/{fc}' for dataset in datasets for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset))]))
    # tables
    map(explicit_typo_fix,('Glossary','DescriptionOfMapUnits'))

    edit.end_session()

    # Multi-Color/-Patterned MapUnits are skipped, excluding water and alluvium,
    # which have an explicit symbol used for them.
    if enable_process[0] == 'true':

        edit = GeMS_Editor()

        with arcpy.da.UpdateCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits',('MapUnit','Symbol','AreaFillRGB')) as cursor:
            for row in cursor:
                update_row = False
                if row[0] == 'Qal':
                    if row[1] != '180':
                        update_row = True
                        row[1] = '180'
                    if not row[2] is None:
                        update_row = True
                        row[2] = None
                elif row[0] == 'water':
                    if not row[1] is None:
                        update_row = True
                        row[1] = None
                    if not row[2] is None:
                        update_row = True
                        row[2] = None
                if update_row:
                    cursor.updateRow(row)
                del update_row

        edit.end_session()

        aprx = arcpy.mp.ArcGISProject('CURRENT')
        rgb_mapunits = dict()
        cmy_mapunits = dict()
        dups = set()
        for m in aprx.listMaps():
            for lyr in m.listLayers():
                if 'MapUnitPolys' in lyr.name:
                    sym = lyr.symbology
                    for grp in sym.renderer.groups:
                        for itm in grp.items:
                            if not (unit_name := itm.label) in (None,''):
                                try:
                                    color_space = tuple(itm.symbol.color.keys())
                                except Exception:
                                    continue
                                if len(color_space) == 1:
                                    color_space = color_space[0]
                                    if not unit_name in rgb_mapunits.keys():
                                        if color_space == 'RGB':
                                            rgb_vals = tuple(itm.symbol.color[color_space])
                                            rgb_mapunits[unit_name] = rgb_vals[:]
                                            cmy_mapunits[unit_name] = rgb_into_cmy(rgb_vals[0],rgb_vals[1],rgb_vals[2])
                                            del rgb_vals
                                        elif color_space == 'HSV':
                                            hsv_vals = tuple(itm.symbol.color[color_space])
                                            # This fixes a weird glitch related to specifically running in ArcGIS Pro. For example,
                                            # hsv_into_rgb is supposed to return a tuple of 3 integers. Instead, it returns of 3
                                            # floats and seems to ignore the round() function. This does not happen when running this
                                            # function outside ArcGIS Pro. map(round,hsv_into_rgb()) fixes this issue.
                                            rgb_mapunits[unit_name] = tuple(map(round,hsv_into_rgb(hsv_vals[0],hsv_vals[1],hsv_vals[2])))
                                            cmy_mapunits[unit_name] = rgb_into_cmy(rgb_mapunits[unit_name][0],rgb_mapunits[unit_name][1],rgb_mapunits[unit_name][2])
                                            del hsv_vals
                                        elif color_space == 'HSL':
                                            hsl_vals = tuple(itm.symbol.color[color_space])
                                            rgb_mapunits[unit_name] = tuple(map(round,hsl_into_rgb(hsl_vals[0],hsl_vals[1],hsl_vals[2])))
                                            cmy_mapunits[unit_name] = rgb_into_cmy(rgb_mapunits[unit_name][0],rgb_mapunits[unit_name][1],rgb_mapunits[unit_name][2])
                                            del hsl_vals
                                        elif color_space == 'CMYK':
                                            cmy_vals = tuple(itm.symbol.color[color_space])
                                            rgb_mapunits[unit_name] = tuple(map(round,cmy_into_rgb(cmy_vals[0],cmy_vals[1],cmy_vals[2])))
                                            cmy_mapunits[unit_name] = cmy_vals[:]
                                            del cmy_vals
                                        elif color_space == 'Grayscale':
                                            rgb_mapunits[unit_name] = ((gs_num := tuple(itm.symbol.color[color_space])[0]),gs_num,gs_num)
                                            cmy_mapunits[unit_name] = tuple(map(round,cmy_into_rgb(gs_num,gs_num,gs_num)))
                                            del gs_num
                                        else:
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

        try:
            del color_space
        except NameError:
            pass

        if len(dups):
            for item in tuple(dups):
                arcpy.AddError(f'{item} has more than one color symbol designated for the same MapUnit between two polygon feature classes.')
                rgb_mapunits.pop(item)
                cmy_mapunits.pop(item)

        del dups ; del aprx

        if len(((units := tuple(rgb_mapunits.keys())))):

            symbol_mapunits = {unit : cmy_into_wpg(cmy_mapunits[unit]) for unit in units}

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

    # Fillout Symbol and Label fields for polygon feature classes in
    # geodatabase using corresponding information from DescriptionOfMapUnits
    # table.
    if enable_process[1] == 'true':

        arcpy.AddMessage("Obtaining Label and Symbol information from DescriptionOfMapUnits table...")

        pairs = {row[0] : (row[1],row[2]) for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits',('MapUnit','Label','Symbol')) if not (row[1] is None and row[2] is None) and not row[0] is None}
        mapunits = frozenset(pairs.keys())

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
                arcpy.AddMessage(f"Filling out {fc}...")
                edit = GeMS_Editor()
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
                edit.end_session()

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                if 'MapUnitLines' in fc or 'MapUnitPoints' in fc:
                    arcpy.AddMessage(f"Filling out {fc}...")
                    edit = GeMS_Editor()
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
                    edit.end_session()

        del mapunits ; del pairs

    # Autofill MapUnit fields in point feature classes
    if enable_process[2] == 'true':

        arcpy.AddMessage("Filling out MapUnit field of point feature classes in geodatabase based upon location relative to polygons in MapUnitPolys...\n")

        # Fill MapUnit field for point feature classes in geodatabase
        # based upon relative MapUnitPolys polygon locations.

        # Points on the border between two or more polygons will have their MapUnit
        # value arbitrarily assigned.

        # Due to the contextual nature of Stations, it is excluded automatically
        # from this process.

        # GenericPoints are treated differently. Assigning the MapUnit from
        # MapUnitOverlayPolys takes priority over assigning MapUnits from
        # MapUnitPolys.

        def getMapUnits(poly_item : str) -> tuple:

            mapunits = set()
            for row in arcpy.da.SearchCursor(poly_item,'MapUnit'):
                if not row[0] is None:
                    if row[0].replace(' ','') != '':
                        mapunits.add(row[0])
            return tuple(mapunits)

        arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/GeologicMap/MapUnitPolys','temp_poly_lyr')
        mapunits = getMapUnits('temp_poly_lyr')

        hasOverlayPolys = False
        overlay_labels = set()

        if 'MapUnitOverlayPolys' in arcpy.ListFeatureClasses(feature_dataset='GeologicMap',feature_type='Polygon'):
            hasOverlayPolys = True
            arcpy.management.MakeFeatureLayer(f'{arcpy.env.workspace}/GeologicMap/MapUnitOverlayPolys','temp_overlay_lyr')
            mapoverlays = getMapUnits('temp_overlay_lyr')
            overlay_labels = frozenset({row[0] for row in arcpy.da.SearchCursor('temp_overlay_lyr','MapUnit')})

        hasCrossSection = False

        for dataset in datasets:
            if 'CrossSection' in dataset:
                hasCrossSection = True
            else:
                for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point')):
                    # Exclude Stations
                    if 'Station' in fc:
                        continue
                    elif 'GenericPoints' in fc:
                        if hasOverlayPolys:
                            feature_item = f'{arcpy.env.workspace}/{dataset}/{fc}'
                            if not 'MapUnit' in [field.name for field in tuple(arcpy.ListFields(feature_item,field_type='String'))]:
                                del feature_item
                                continue
                            arcpy.AddMessage(f'Working on: {fc} in {dataset} cross-referencing MapUnitOverlayPolys...')
                            fields = ['MapUnit']
                            for field in tuple(arcpy.ListFields(feature_item)):
                                fields.insert(0,field.name)
                                break
                            fields = tuple(fields)
                            arcpy.management.MakeFeatureLayer(feature_item,'temp_pnt_lyr')
                            matched = dict()
                            for mapunit in mapoverlays:
                                selected_polys = arcpy.management.SelectLayerByAttribute('temp_poly_lyr','NEW_SELECTION',f"MapUnit = '{mapunit}'")
                                selected_pnts,redundant,count = arcpy.management.SelectLayerByLocation('temp_pnt_lyr','INTERSECT',selected_polys,'','NEW_SELECTION')
                                del redundant
                                if int(count):
                                    for row in arcpy.da.SearchCursor(selected_pnts,fields):
                                        matched[row[0]] = mapunit
                                del count
                            if len(matched):
                                edit = GeMS_Editor()
                                oids = frozenset(matched.keys())
                                arcpy.AddMessage(f'Updating {fc} in {dataset}...')
                                with arcpy.da.UpdateCursor(feature_item,fields) as cursor:
                                    for row in cursor:
                                        if row[0] in oids:
                                            if row[1] != (new_str := matched[row[0]]):
                                                row[1] = new_str[:]
                                                cursor.updateRow(row)
                                            del new_str
                                del oids
                                edit.end_session()
                            del matched ; del fields ; del feature_item
                    edit = GeMS_Editor()
                    feature_item = f'{arcpy.env.workspace}/{dataset}/{fc}'
                    if not 'MapUnit' in [field.name for field in tuple(arcpy.ListFields(feature_item,field_type='String'))]:
                        del feature_item
                        continue
                    arcpy.AddMessage(f'Working on: {fc} in {dataset} cross-referencing MapUnitPolys...')
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
                        del count
                    if len(matched):
                        arcpy.AddMessage(f'Updating {fc} in {dataset}...')
                        oids = frozenset(matched.keys())
                        with arcpy.da.UpdateCursor(feature_item,fields) as cursor:
                            for row in cursor:
                                if row[0] in oids:
                                    if not row[1] in overlay_labels:
                                        if row[1] != (new_str := matched[row[0]]):
                                            row[1] = new_str[:]
                                            cursor.updateRow(row)
                                        del new_str
                        del oids
                    del matched ; del fields ; del feature_item
                    edit.end_session()

        del mapunits ; del mapoverlays ; del hasOverlayPolys ; del overlay_labels

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
                        arcpy.AddMessage(f'\n{dataset} is missing CS{dataset[-1]}MapUnitPolys! Skipping {dataset}.\n')
                        del found_poly
                        continue
                    del found_poly
                    mapunits = getMapUnits('temp_poly_lyr')
                    for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point')):
                        # Exclude Stations
                        if 'Stations' in fc:
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
                            del count
                        if len(matched):
                            edit = GeMS_Editor()
                            oids = frozenset(matched.keys())
                            with arcpy.da.UpdateCursor(feature_item,fields) as cursor:
                                for row in cursor:
                                    if row[0] in oids:
                                        if row[1] != (new_str := matched[row[0]]):
                                            row[1] = new_str[:]
                                            cursor.updateRow(row)
                                        del new_str
                            del oids
                            edit.end_session()
                        del matched ; del fields ; del feature_item
                    del mapunits

        del hasCrossSection


    # Alphabetize Glossary and Add missing terms
    if enable_process[3] == 'true':

        arcpy.AddMessage("Alphabetizing and adding missing terms to Glossary...")

        used_terms = set()
        valid_fields = frozenset({'Type','IdentityConfidence','ExistenceConfidence'})

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                arcpy.AddMessage(f'Checking {fc}...')
                feature_item = f'{arcpy.env.workspace}/{dataset}/{fc}'
                if len((fields := tuple([field.name for field in arcpy.ListFields(feature_item,field_type='String') if field.name in valid_fields]))):
                    field_range = range(len(fields))
                    for row in arcpy.da.SearchCursor(feature_item,fields):
                        for n in field_range:
                            used_terms.add(row[n])
                    del field_range

        del fields ; del valid_fields ; del feature_item

        if None in used_terms:
            used_terms.remove(None)

        logged_terms = []
        logged_def = []
        logged_ID = []
        blanks = Blank_Term()
        copy_count = dict()

        selected_rows,count = arcpy.management.SelectLayerByAttribute((glossary_path := f'{arcpy.env.workspace}/Glossary'),'NEW_SELECTION',"Term IS NULL And Definition IS NULL And DefinitionSourceID IS NULL")

        if count:
            arcpy.management.DeleteRows(selected_rows)

        del selected_rows ; del count

        edit = GeMS_Editor()

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

        edit.end_session()

        del update_row ; del blanks ; del copy_count

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

        edit = GeMS_Editor()

        with arcpy.da.UpdateCursor(glossary_path,('Term','Definition','DefinitionSourceID')) as cursor:
            counter = -1
            for row in cursor:
                counter += 1
                if row[0] != sorted_terms[counter]:
                    row[0] = sorted_terms[counter]
                    row[1] = terms[sorted_terms[counter]][0]
                    row[2] = terms[sorted_terms[counter]][1]
                    cursor.updateRow(row)

        edit.end_session()

        del sorted_terms ; del counter ; terms ; del glossary_path

    # Autopopulate DataSources table
    if enable_process[4] == 'true':

        arcpy.AddMessage('Filling out and populating DataSources table...')

        found_items = set()
        valid_fields = frozenset(('DataSourceID','LocationSourceID','OrientationSourceID'))

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

        if os.path.exists('Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'):
            naloe_zelmatitum = False
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
            master_dasids = frozenset(source_dict.keys())
            valid_dasids = tuple(sorted([item for item in found_dasids if item in master_dasids],key=str))

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
                edit = GeMS_Editor()
                if missing_num_rows > 0:
                    with arcpy.da.InsertCursor(datasources_path,('Source','Notes','URL','DataSources_ID')) as cursor:
                        for num_row in range(missing_num_rows):
                            cursor.insertRow((None,None,None,None))
                else:
                    with arcpy.da.UpdateCursor(datasources_path,'DataSources_ID') as cursor:
                        for row in cursor:
                            if not row[0] in valid_dasids:
                                cursor.deleteRow()
                edit.end_session()

            del missing_num_rows ; del num_rows

            counter = 0

            edit = GeMS_Editor()

            with arcpy.da.UpdateCursor(datasources_path,('Source','Notes','URL','DataSources_ID')) as cursor:
                for row in cursor:
                    if not (row[0] == source_dict[valid_dasids[counter]][0] and row[1] == source_dict[valid_dasids[counter]][1] and row[2] == source_dict[valid_dasids[counter]][2] and row[3] == valid_dasids[counter]):
                        row[0] = source_dict[valid_dasids[counter]][0]
                        row[1] = source_dict[valid_dasids[counter]][1]
                        row[2] = source_dict[valid_dasids[counter]][2]
                        row[3] = valid_dasids[counter]
                        cursor.updateRow(row)
                    counter += 1

            edit.end_session()

            del counter ; del source_dict ; del valid_dasids ; del datasources_path

        else:

            arcpy.env.workspace = code_directory[:]

            arcpy.AddMessage("Unable to connect via SDEs! Process has been ended prematurely.\n\n")

        del code_directory ; del now_num_rows

        # failsafe
        try:
            edit.end_session()
        except Exception:
            pass

        del naloe_zelmatitum

    # Autofill _ID fields
    # This should always be the last thing done if enabled and is enabled by default.
    if enable_process[5] == 'true':

        arcpy.AddMessage("Filling out _ID fields, excluding DataSources table...")

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                edit = GeMS_Editor()
                gems_id_writer(f'{arcpy.env.workspace}/{dataset}/{fc}',fc)
                edit.end_session()

        for table in ('Glossary','DescriptionOfMapUnits'):
            edit = GeMS_Editor()
            gems_id_writer(f'{arcpy.env.workspace}/{table}',table)
            edit.end_session()

    arcpy.env.workspace = current_workspace[:]


autofill_GeMS(gdb_path,enable_process)
