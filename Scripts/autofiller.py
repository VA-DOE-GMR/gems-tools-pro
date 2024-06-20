import arcpy,gc,os,sys
from misc_arcpy_ops import default_env_parameters,explicit_typo_fix
from misc_ops import fixFieldItemString,ref_info,to_tuple
from array import array
from re import sub as re_sub
from fundamentals import hsv_into_rgb,hsl_into_rgb,lab_into_rgb,cmy_into_rgb,rgb_into_cmy,cmy_into_wpg

gdb_path = sys.argv[1]
enable_process = tuple([sys.argv[n] for n in range(2,8)])

# used to make specific fields uppercase.
def upperFields(item_path : str, fields) -> None:

    field_range = range(len(fields))

    with arcpy.da.UpdateCursor(item_path,fields) as cursor:
        for row in cursor:
            update_row = False
            for n in field_range:
                if not row[n] is None:
                    if (new_str := row[n].upper()) != row[n]:
                        row[n] = new_str
                        update_row = True
            if update_row:
                cursor.updateRow(row)

    return None

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

    edit = GeMS_Editor()

    # The following done as they are required to be fixed for the best output as
    # well as applying fixes and changes that will be required to be done
    # regardless.

    # Removing explicit typos.

    arcpy.AddMessage("Fixing explicit typos in feature classes and tables as well as invalid capitalization...")

    # feature classes
    map(explicit_typo_fix,tuple([f'{dataset}/{fc}' for dataset in datasets for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset))]))
    # tables
    map(explicit_typo_fix,('Glossary','DescriptionOfMapUnits'))
    gc.collect()

    # change these to uppercase
    # DataSourceID,DescriptionSourceID,DefinitionSourceID,LocationSourceID,OrientationSourceID

    valid_fields = frozenset(('DataSourceID','LocationSourceID','OrientationSourceID'))

    for dataset in datasets:
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
            feature_item = f'{dataset}/{fc}'
            if len((id_fields := tuple([field.name for field in tuple(arcpy.ListFields(feature_item,field_type='String')) if field.name in valid_fields or field.name.endswith('_ID')]))):
                upperFields(feature_item,id_fields)

    del id_fields ; del feature_item
    gc.collect()

    upperFields('Glossary',('DefinitionSourceID','Glossary_ID'))
    upperFields('DescriptionOfMapUnits',('DescriptionSourceID','DescriptionOfMapUnits_ID'))
    upperFields('DataSources',('DataSources_ID',))

    # change these to lowercase:
    # IsConcealed,IdentityConfidence,ExistenceConfidence

    valid_fields = frozenset(('IsConcealed','IdentityConfidence','ExistenceConfidence'))

    for dataset in datasets:
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
            feature_item = f'{dataset}/{fc}'
            if len((fields := tuple([field.name for field in tuple(arcpy.ListFields(feature_item,field_type='String')) if field.name in valid_fields]))):
                field_range = range(len(fields))
                with arcpy.da.UpdateCursor(feature_item,fields) as cursor:
                    for row in cursor:
                        update_row = False
                        for n in field_range:
                            if not row[n] is None:
                                if (new_str := row[n].lower()) != row[n]:
                                    row[n] = new_str
                                    update_row = True
                                del new_str
                        if update_row:
                            cursor.updateRow(row)
                        del update_row
                del field_range

    del fields ; del valid_fields ; del feature_item
    gc.collect()

    edit.end_session()

    # Multi-Color/-Patterned MapUnits are skipped, excluding water and alluvium,
    # which have an explicit symbol used for them.
    if enable_process[0] == 'true':

        aprx = arcpy.mp.ArcGISProject('CURRENT')
        rgb_mapunits = dict()
        cmy_mapunits = dict()
        complex_mapunits = dict()
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
                                        gc.collect()
                                    elif color_space == 'HSV':
                                        hsv_vals = tuple(itm.symbol.color[color_space])
                                        rgb_vals = tuple(map(round,hsv_into_rgb(hsv_vals[0],hsv_vals[1],hsv_vals[2])))
                                        if rgb_vals[0] != rgb_mapunits[unit_name][0] or rgb_vals[1] != rgb_mapunits[unit_name][1] or rgb_vals[2] != rgb_mapunits[unit_name][2]:
                                            dups.add(unit_name)
                                        del hsv_vals ; del rgb_vals
                                        gc.collect()
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
                                        gc.collect()
                            del unit_name
                    del sym
                elif 'MapUnitOverlayPolys' in lyr.name:
                    sym = lyr.symbology
                    for grp in sym.renderer.groups:
                        if itm in grp.items:
                            if (unit_name := itm.label) == 'Qal':
                                complex_mapunits[unit_name] = 'al'
                            elif unit_name == 'water':
                                complex_mapunits[unit_name] = 'w'

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

            symbol_mapunits = dict()

            other_units = tuple(complex_mapunits.keys())

            for unit in units:
                symbol_mapunits[unit] = cmy_into_wpg(cmy_mapunits[unit])

            edit = GeMS_Editor()

            for unit in units:
                rgb_mapunits[unit] = f'{str(rgb_mapunits[unit][0]).zfill(3)},{str(rgb_mapunits[unit][1]).zfill(3)},{str(rgb_mapunits[unit][2]).zfill(3)}'
            with arcpy.da.UpdateCursor('DescriptionOfMapUnits',('MapUnit','Symbol','AreaFillRGB')) as cursor:
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
                        if row[0] in other_units:
                            if row[1] != complex_mapunits[row[0]]:
                                update_row = True
                                row[1] = complex_mapunits[row[0]]
                            if row[2] != None:
                                update_row = True
                                row[2] = None
                        if update_row:
                            cursor.updateRow(row)
                    del update_row

            del symbol_mapunits ; del other_units

            edit.end_session()

        del rgb_mapunits ; del cmy_mapunits ; del complex_mapunits
        gc.collect()

    # Fillout Symbol and Label fields for polygon feature classes in
    # geodatabase using corresponding information from DescriptionOfMapUnits
    # table.
    if enable_process[1] == 'true':

        edit = GeMS_Editor()

        arcpy.AddMessage("Obtaining Label and Symbol information from DescriptionOfMapUnits table...")

        pairs = {row[0] : (row[1],row[2]) for row in arcpy.da.SearchCursor('DescriptionOfMapUnits',('MapUnit','Label','Symbol')) if not (row[1] is None and row[2] is None) and not row[0] is None}
        mapunits = frozenset(pairs.keys())

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
                with arcpy.da.UpdateCursor(f'{dataset}/{fc}',('MapUnit','Label','Symbol')) as cursor:
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
        gc.collect()

        arcpy.AddMessage("Changes successfully applied.\n\nSaving edits...")

        edit.end_session()

        arcpy.AddMessage("Edits saved!\n\n")

    # Autofill MapUnit fields in point feature classes
    if enable_process[2] == 'true':

        arcpy.AddMessage("Filling out MapUnit field of point feature classes in geodatabase based upon location relative to polygons in MapUnitPolys...\n")

        # Fill MapUnit field for point feature classes in geodatabase
        # based upon relative MapUnitPolys polygon locations.

        # Points on the border between two or more polygons will have their MapUnit
        # value arbitrarily assigned.

        edit = GeMS_Editor()

        for dataset in datasets:
            poly_name = None
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
                if 'MapUnitPolys' in fc:
                    poly_name = fc[:]
                    break
            if poly_name is None:
                del poly_name
                continue
            arcpy.management.MakeFeatureLayer((polygon_feature := f'{dataset}/{poly_name}'),'temp_poly_lyr')
            # Polygons with <Null> as the MapUnit value will be ignored.
            mapunits = {row[0] for row in arcpy.da.SearchCursor(polygon_feature,'MapUnit') if not row[0] is None}
            del polygon_feature
            if None in mapunits:
                mapunits.remove(None)
            mapunits = tuple(mapunits)
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point')):
                feature_item = f'{dataset}/{fc}'
                if not 'MapUnit' in [field.name for field in arcpy.ListFields(feature_item,field_type='String')]:
                    continue
                arcpy.AddMessage(f'Working on: {fc}\n')
                arcpy.management.MakeFeatureLayer(feature_item,'temp_pnt_lyr')
                fields = ["MapUnit"]
                for field in tuple(arcpy.ListFields(feature_item)):
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
                    del count
                if len(matched):
                    oids = array('i',matched.keys())
                    with arcpy.da.UpdateCursor(feature_item,fields) as cursor:
                        for row in cursor:
                            if row[0] in oids:
                                if row[1] != (new_str := matched[oids[oids.index(row[0])]]):
                                    row[1] = new_str
                                    cursor.updateRow(row)
                                del new_str
                    del oids
                del matched ; del selected_polys ; del selected_pnts
                gc.collect()

        arcpy.AddMessage("Changes successfully applied.\n\nSaving edits...")

        edit.end_session()

        arcpy.AddMessage("Edits saved!\n\n")

    # Alphabetize Glossary and Add missing terms
    if enable_process[3] == 'true':

        arcpy.AddMessage("Alphabetizing and adding missing terms to Glossary...")

        edit = GeMS_Editor()

        used_terms = set()
        valid_fields = frozenset({'Type','IdentityConfidence','ExistenceConfidence'})

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                feature_item = f'{dataset}/{fc}'
                if len((fields := tuple([field.name for field in arcpy.ListFields(feature_item,field_type='String') if field.name in valid_fields]))):
                    field_range = range(len(fields))
                    for row in arcpy.da.SearchCursor(feature_item,fields):
                        for n in field_range:
                            used_terms.add(row[n])
                    del field_range

        del fields ; del valid_fields ; del feature_item
        gc.collect()

        if None in used_terms:
            used_terms.remove(None)

        logged_terms = []
        logged_def = []
        logged_ID = []
        blanks = Blank_Term()
        copy_count = dict()
        selected_rows,count = arcpy.management.SelectLayerByAttribute('Glossary','NEW_SELECTION',"Term IS NULL And Definition IS NULL And DefinitionSourceID IS NULL")

        if count:
            arcpy.management.DeleteRows(selected_rows)

        del selected_rows ; del count
        gc.collect()

        with arcpy.da.UpdateCursor('Glossary',('Term','Definition','DefinitionSourceID')) as cursor:
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

        del update_row ; del blanks ; del copy_count
        gc.collect()

        for term in (logged_terms := tuple(logged_terms)):
            if term in used_terms:
                used_terms.remove(term)

        terms = {logged_terms[n] : (logged_def[n],logged_ID[n]) for n in range(len(logged_terms))}

        del logged_terms ; del logged_def ; del logged_ID
        gc.collect()

        if len((used_terms := tuple(used_terms))):
            for used_term in used_terms:
                terms[used_term] = (None,None)

        del used_terms

        sorted_terms = tuple(sorted(terms.keys(),key=str.lower))

        with arcpy.da.UpdateCursor('Glossary',('Term','Definition','DefinitionSourceID')) as cursor:
            counter = -1
            for row in cursor:
                counter += 1
                if row[0] != sorted_terms[counter]:
                    row[0] = sorted_terms[counter]
                    row[1] = terms[sorted_terms[counter]][0]
                    row[2] = terms[sorted_terms[counter]][1]
                    cursor.updateRow(row)

        del sorted_terms ; del counter ; terms
        gc.collect()

        arcpy.AddMessage("Process successfully completed!\n\nSaving edits...")

        edit.end_session()

        arcpy.AddMessage("Edits successfully saved!\n\n")

    # Autopopulate DataSources table
    if enable_process[4] == 'true':

        arcpy.AddMessage('Filling out and populating DataSources table...')

        edit = GeMS_Editor()

        found_items = set()
        valid_fields = frozenset(('DataSourceID','LocationSourceID','OrientationSourceID'))

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                feature_item = f'{dataset}/{fc}'
                if len((dasid_fields := tuple([field.name for field in tuple(arcpy.ListFields(feature_item,field_type='String')) if field.name in valid_fields]))):
                    field_range = range(len(dasid_fields))
                    for row in arcpy.da.SearchCursor(feature_item,dasid_fields):
                        for n in field_range:
                            found_items.add(row[n])
                    del field_range

        del dasid_fields ; del valid_fields ; del feature_item
        gc.collect()

        for row in arcpy.da.SearchCursor('DescriptionOfMapUnits','DescriptionSourceID'):
            found_items.add(row[0])

        for row in arcpy.da.SearchCursor('Glossary','DefinitionSourceID'):
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

        for row in arcpy.da.SearchCursor('DataSources','DataSources_ID'):
            now_num_rows += 1

        if os.path.exists(f'{arcpy.env.workspace[:arcpy.env.workspace.rfind("/")]}/naloe_zelmatitum.sde'):
            os.remove(f'{arcpy.env.workspace[:arcpy.env.workspace.rfind("/")]}/naloe_zelmatitum.sde')

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

            source_dict = {row[3] : (row[0],row[1],row[2]) for row in arcpy.da.SearchCursor(temp_table,('Source','Notes','URL','DataSources_ID')) if not None in (row[0],row[3])}
            master_dasids = frozenset(source_dict.keys())
            valid_dasids = tuple(sorted([item for item in found_dasids if item in master_dasids],key=str))

            del temp_table ; del master_dasids ; del found_dasids
            gc.collect()

            arcpy.env.workspace = code_directory[:]

            if (missing_num_rows := (num_rows := len(valid_dasids)) - now_num_rows) != 0:
                if missing_num_rows > 0:
                    with arcpy.da.InsertCursor('DataSources',('Source','Notes','URL','DataSources_ID')) as cursor:
                        for num_row in range(missing_num_rows):
                            cursor.insertRow((None,None,None,None))
                else:
                    with arcpy.da.UpdateCursor('DataSources','DataSources_ID') as cursor:
                        for row in cursor:
                            if not row[0] in valid_dasids:
                                cursor.deleteRow()

            del missing_num_rows ; del num_rows
            gc.collect()

            counter = 0

            with arcpy.da.UpdateCursor('DataSources',('Source','Notes','URL','DataSources_ID')) as cursor:
                for row in cursor:
                    if not (row[0] == source_dict[valid_dasids[counter]][0] and row[1] == source_dict[valid_dasids[counter]][1] and row[2] == source_dict[valid_dasids[counter]][2] and row[3] == valid_dasids[counter]):
                        row[0] = source_dict[valid_dasids[counter]][0]
                        row[1] = source_dict[valid_dasids[counter]][1]
                        row[2] = source_dict[valid_dasids[counter]][2]
                        row[3] = valid_dasids[counter]
                        cursor.updateRow(row)
                    counter += 1

            del counter ; del source_dict ; del valid_dasids
            gc.collect()

        else:

            arcpy.env.workspace = code_directory[:]

            arcpy.AddMesssage("Unable to connect via SDEs! Process has been ended prematurely.\n\n")

        del code_directory ; del now_num_rows
        gc.collect()

        edit.end_session()

        del naloe_zelmatitum

        gc.collect()

    # Autofill _ID fields
    # This should always be the last thing done if enabled and is enabled by default.
    if enable_process[5] == 'true':

        arcpy.AddMessage("Filling out _ID fields, excluding DataSources table...")

        edit = GeMS_Editor()

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
                gems_id_writer(f'{dataset}/{fc}',fc)

        for table in ('Glossary','DescriptionOfMapUnits'):
            gems_id_writer(table,table)

        arcpy.AddMessage("Process successfully completed!\n\nSaving edits...")

        edit.end_session()

        arcpy.AddMessage("Edits successfully saved!\n\n")


    arcpy.env.workspace = current_workspace[:]

    gc.collect()


autofill_GeMS(gdb_path,enable_process)