import arcpy
import gc
from misc_arcpy_ops import default_env_parameters
from misc_ops import fixFieldItemString,ref_info,to_tuple
import sys
from array import array
from re import sub as re_sub
import os

gdb_path = sys.argv[1]
enable_process = tuple([sys.argv[n] for n in range(2,7)])

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

# Attempts to create a temporary SDE file, which will be deleted after necessary data is obtained.
def temp_SDE() -> bool:
    '''This only executes when the expected SDE file's location cannot be found.
    Therefore, a temporary SDE needs to be created in order to get DASID
    information.
    '''
    try:
        arcpy.management.CreateDatabaseConnection((sde_directory := arcpy.env.workspace[:arcpy.env.workspace.rfind('/')]),"naloe_zelmatitum","SQL_SERVER",instance="WSQ06627, 50000",account_authentication="OPERATING_SYSTEM_AUTH",database="DGMRgeo")
        arcpy.env.workspace = f'{sde_directory}/naloe_zelmatitum.sde'
        return True
    except Exception:
        arcpy.AddError("An error has transpired while attempting to establish and generate temporary SDE.")
        import pyodbc
        ms_odbc_driver = None
        for driver in tuple(pyodbc.drivers()):
            if driver.startswith('ODBC Driver'):
                ms_odbc_driver = driver[:]
                break
        if ms_odbc_driver is None:
            arcpy.AddMessage("\n\nNo ODBC Driver for SQL Server was found on your machine.")
        else:
            arcpy.AddMessage("\n\nYou have an unsupported/outdated version of Microsoft ODBC Driver for SQL Server installed on your machine.")
        return False

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

def explicit_typo_fix(item_path : str) -> None:
    '''This fixes all explicit typos present in all String/Text fields of
    feature classes and tables, excluding ones that should not be touched.
    '''

    excluded_fields = frozenset(('created_user','last_edited_user','GeoMaterial'))

    if len((fields := tuple([field.name for field in tuple(arcpy.ListFields(item_path,field_type='String')) if not field.name in excluded_fields]))):

        field_range = range(len(fields))

        with arcpy.da.UpdateCursor(item_path,fields) as cursor:
            for row in cursor:
                update_row = False
                for n in field_range:
                    if not row[n] is None:
                        if (new_str := fixFieldItemString(row[n])) != row[n]:
                            row[n] = new_str
                            update_row = True
                if update_row:
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

    # Autofill Label and Symbol fields of polygon feature classes
    if enable_process[0] == 'true':

        # Fillout Symbol and Label fields for polygon feature classes in
        # geodatabase using corresponding information from DescriptionOfMapUnits
        # table.

        # This is to prevent Error #160250 randomly from occurring.
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
    if enable_process[1] == 'true':

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
    if enable_process[2] == 'true':

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
    if enable_process[3] == 'true':

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
                arcpy.AddError("\n\nSomething went wrong when trying to connect via pre-existing SDE.\n\nGenerating temporary SDE...")
                naloe_zelmatitum = temp_SDE()
        else:
            naloe_zelmatitum = temp_SDE()

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

        if os.path.exists((temp_sde := f'{arcpy.env.workspace[:arcpy.env.workspace.rfind("/")]}/naloe_zelmatitum.sde')):
            os.remove(temp_sde)

        del temp_sde

        if naloe_zelmatitum:
            arcpy.AddMessage("\n\nProcess completed!\n\nSaving edits...")

        edit.end_session()

        if naloe_zelmatitum:
            arcpy.AddMessage('Edits successfully saved!\n\n')

        del naloe_zelmatitum

        gc.collect()


    if enable_process[4] == 'true':

        arcpy.AddMessage('Merging matching polygons...')

        edit = GeMS_Editor()

        # Explicit and constant range objects.
        range_4 = range(4)
        range_7 = range(7)

        for dataset in tuple(arcpy.ListDatasets()):
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
                arcpy.AddMessage(f"Merging polygons in {fc}...")
                # Information gathered and required to create a merged version of
                # polygons in a polygon feature class.
                polygon_mergers = []
                # This is to prevent this tool from failing if non-GeMS/FGDC feature
                # classes are encountered that may not have all these fields.
                required_fields = ['MapUnit','IdentityConfidence','Label','Symbol','DataSourceID','Notes']
                feature_item = f'{dataset}/{fc}'
                fields = tuple([field.name for field in tuple(arcpy.ListFields(feature_item))])
                oid_name = fields[0]
                # Fast means of getting OID field name.
                for required_field in required_fields:
                    if not required_field in fields:
                        oid_name = None
                        break
                if oid_name is None:
                    continue
                required_fields.insert(0,oid_name)
                # This keeps track of the maximum number of characters currently
                # allowed in the Notes field and number of maximum characters
                # required to concatenate Notes from polygon feature that shall be
                # appended to each other.
                max_notes_length = 0
                new_length = 0
                for field in tuple(arcpy.ListFields(feature_item,field_type='String')):
                    if field.name == 'Notes':
                        max_notes_length = field.length
                        new_length = field.length
                        break
                # This keeps track of which features have already been checked and
                # will be skipped if already present in set.
                ignore = set()
                # Create Feature Layer to prevent odd slowdown and memory behavior
                # of SelectLayerByLocation and SelectLayerByAttribute
                # Management tools.
                arcpy.management.MakeFeatureLayer(feature_item,'temp_lyr')
                for row in arcpy.da.SearchCursor('temp_lyr',required_fields):
                    if row[0] in ignore:
                        continue
                    saved_info = [row[x] for x in range_7]
                    for n in range(2,len((saved_info := [row[x] for x in range_7]))):
                        if not saved_info[n] is None:
                            saved_info[n] = fixFieldItemString(saved_info[n])
                    if saved_info[1] is None:
                        continue
                    selected_polys = arcpy.management.SelectLayerByLocation(arcpy.management.SelectLayerByAttribute('temp_lyr','NEW_SELECTION',f'{oid_name} = {row[0]}'),'BOUNDARY_TOUCHES','temp_lyr')
                    selected_info = {item[0] : (item[2],item[3],item[4],item[5],item[6]) for item in arcpy.da.SearchCursor(selected_polys,required_fields) if item[1] == saved_info[1]}
                    if len((selected_keys := array('i',selected_info.keys()))) > 1:
                        # Matching MapUnit was found in touching polygons.
                        for selected_key in selected_keys:
                            for n in range_4:
                                if saved_info[n+2] is None:
                                    if not selected_info[selected_key][n] is None:
                                        if not fixFieldItemString(selected_info[selected_key][n]) is None:
                                            selected_info.pop(selected_key)
                                            break
                                elif saved_info[n+2].replace(' ','') == '':
                                    if not selected_info[selected_key][n] is None:
                                        if not fixFieldItemString(selected_info[selected_key][n]) is None:
                                            selected_info.pop(selected_key)
                                            break
                                elif not selected_info[selected_key][n] is None:
                                    if saved_info[n+2] != fixFieldItemString(selected_info[selected_key][n]):
                                        selected_info.pop(selected_key)
                                        break
                        if len((selected_keys := array('i',selected_info.keys()))) > 1:
                            # Identical information found in touching polygons.
                            checked = {row[0]}
                            sub_iteration_complete = False
                            # This iterates through all matching touching polygons
                            # and checks if they also touch matching polygons
                            # that can be grouped together.
                            while not sub_iteration_complete:
                                sub_iteration_complete = True
                                for selected_key in selected_keys:
                                    if selected_key in checked:
                                        continue
                                    selected_polys = arcpy.management.SelectLayerByAttribute('temp_lyr','NEW_SELECTION',f'{oid_name} = {selected_key}')
                                    selected_polys = arcpy.management.SelectLayerByLocation(selected_polys,'BOUNDARY_TOUCHES','temp_lyr')
                                    checked.add(selected_key)
                                    if len((new_info := {item[0] : (item[2],item[3],item[4],item[5],item[6]) for item in arcpy.da.SearchCursor(selected_polys,required_fields) if item[1] == saved_info[1] and not item[0] in selected_keys and not item[0] in checked})):
                                        # Notes is the only field that does not need to be identical.
                                        # IdentityConfidence, Label, Symbol, and DataSourceID all must match.
                                        for new_key in array('i',new_info.keys()):
                                            for n in range_4:
                                                if saved_info[n+2] is None:
                                                    if not new_info[new_key][n] is None:
                                                        if not fixFieldItemString(new_info[new_key][n]) is None:
                                                            new_info.pop(new_key)
                                                            break
                                                elif saved_info[n+2].replace(' ','') == '':
                                                    if not new_info[new_key][n] is None:
                                                        if not fixFieldItemString(new_info[new_key][n]) is None:
                                                            new_info.pop(new_key)
                                                            break
                                                elif not new_info[new_key][n] is None:
                                                    if saved_info[n+2] != fixFieldItemString(new_info[new_key][n]):
                                                        new_info.pop(new_key)
                                                        break
                                        if len(new_info):
                                            sub_iteration_complete = False
                                            for new_key in array('i',new_info.keys()):
                                                selected_info[new_key] = new_info[new_key]
                                    del selected_polys
                                if not sub_iteration_complete:
                                    selected_keys = array('i',selected_info.keys())
                            del checked ; del sub_iteration_complete
                            gc.collect()
                            # Create a concatenated string of differing Notes or
                            # value to None if they are all blank.
                            notes_items = set()
                            if not saved_info[6] is None:
                                notes_items.add(saved_info[6])
                            for selected_key in selected_keys:
                                if not selected_info[selected_key][4] is None:
                                    temp_str = fixFieldItemString(selected_info[selected_key][4])
                                    if not (temp_str := fixFieldItemString(selected_info[selected_key][4])) is None:
                                        notes_items.add(temp_str)
                            if len((notes_items := tuple(sorted(notes_items,key=str)))):
                                saved_info[6] = notes_items[0]
                                for n in range(1,len(notes_items)):
                                    saved_info[6] = f'{saved_info[6]} | {notes_items[n]}'
                                if new_length < len(saved_info[6]):
                                    new_length = len(saved_info[6])
                            else:
                                saved_info[6] = None
                            select_str = f'{oid_name} IN ({selected_keys[0]}'
                            for n in range(1,len(selected_keys)):
                                select_str = f'{select_str},{selected_keys[n]}'
                            select_str = f'{select_str})'
                            arr = arcpy.Array()
                            for geom in (geoms := tuple([r[0] for r in arcpy.da.SearchCursor(feature_item,('SHAPE@',oid_name),select_str)])):
                                for part in geom:
                                    arr.add(part)
                            polygon_mergers.append((saved_info,select_str,arcpy.Polygon(arr,geoms[0].spatialReference)))
                            for selected_key in selected_keys:
                                ignore.add(selected_key)
                        else:
                            # No matching information found in touching polygons.
                            ignore.add(row[0])
                        del selected_keys
                    else:
                        # No matching MapUnit value was found in touching polygons.
                        ignore.add(row[0])
                if max_notes_length < new_length:
                    # Increase the maximum number of characters allowed for Notes.
                    edit.end_session()
                    arcpy.management.AlterField(feature_item,'Notes',field_length=new_length)
                    edit = GeMS_Editor()
                for n in range(len((polygon_mergers := tuple(polygon_mergers)))):
                    counter = 0
                    with arcpy.da.UpdateCursor(feature_item,('SHAPE@','IdentityConfidence','Label','Symbol','DataSourceID','Notes'),polygon_mergers[n][1]) as cursor:
                        for row in cursor:
                            counter += 1
                            if counter == 1:
                                # Overwrite one of the matching polygons shape and
                                # Attribute Table values.
                                row[0] = polygon_mergers[n][2]
                                row[1] = polygon_mergers[n][0][2]
                                row[2] = polygon_mergers[n][0][3]
                                row[3] = polygon_mergers[n][0][4]
                                row[4] = polygon_mergers[n][0][5]
                                row[5] = polygon_mergers[n][0][6]
                                cursor.updateRow(row)
                            else:
                                # Delete the rest of the matching polygons.
                                cursor.deleteRow()
                del oid_name ; del new_length ; del max_notes_length ; del fields ; del required_fields ; del feature_item ; del ignore
                gc.collect()
        edit.end_session()

    # Autofill _ID fields
    if enable_process[4] == 'true':

        # This should always be the last thing done if enabled and is enabled by default.

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
