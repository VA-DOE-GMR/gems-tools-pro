import arcpy
import gc
from misc_arcpy_ops import default_env_parameters
import sys
from array import array
from string import punctuation,digits,ascii_letters

gdb_path = sys.argv[1]

double_puncts = tuple([punct * 2 for punct in array('u',list(punctuation))])
alphanum = frozenset(list(f'{digits}{ascii_letters}'))

# returning None indicates that is nothing of importance in that string.
def fixFieldItemString(entry_string : str):

    # No String entry should have consecutive spaces.
    while entry_string.find('  ') != -1:
        entry_string = entry_string.replace('  ',' ')
    # No String entry should be begin and/or end with a space.
    entry_string = entry_string.strip()
    # No String entry should have two or more consecutive punctuation characters.
    if entry_string == '':
        return None
    for double_punct in double_puncts:
        if double_punct in entry_string:
            while double_punct in entry_string:
                entry_string = entry_string.replace(double_punct,double_punct[0])
    for item in entry_string:
        if item in alphanum:
            return entry_string

    return None


# Typos for MapUnit field are not accounted due to too many variable scenarios to consider it practical.
def mergeMatchingPolygons(gdb_path : str):

    '''
    This automatically merges polygons with the same MapUnit bordering each
    other that also have matching relevant fields, excluding Notes field.
    Redundant spaces will be automatically corrected and explicit typos will be
    automatically corrected as well (e.g., two or more consecutive
    punctionations and/or nonalphanumeric characters).
    '''

    try:
        current_workspace = arcpy.env.workspace[:]
        current_workspace = current_workspace.replace('\\','/')
    except Exception:
        pass

    arcpy.env.workspace = gdb_path.replace('\\','/')

    default_env_parameters()

    arcpy.AddMessage("Iterating through all polygons present in geodatabase...")

    for dataset in tuple(arcpy.ListDatasets()):
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
            arcpy.AddMessage(f"Merging polygons in {fc}...")
            required_fields = ['MapUnit','IdentityConfidence','Label','Symbol','DataSourceID','Notes']
            fields = tuple([field.name for field in tuple(arcpy.ListFields(f'{dataset}/{fc}'))])
            oid_name = fields[0]
            for required_field in required_fields:
                if not required_field in fields:
                    oid_name = None
                    break
            if oid_name is None:
                continue
            required_fields.insert(0,oid_name)
            max_notes_length = 0
            for field in tuple(arcpy.ListFields(f'{dataset}/{fc}',field_type='String')):
                if field.name == 'Notes':
                    max_notes_length = field.length
                    break
            full_iteration = False
            ignore = set()
            while not full_iteration:
                full_iteration = True
                arcpy.management.MakeFeatureLayer(f'{dataset}/{fc}','temp_lyr')
                for row in arcpy.da.SearchCursor('temp_lyr',required_fields):
                    if row[0] in ignore:
                        continue
                    elif row[1] in (None,''):
                        ignore.add(row[0])
                        continue
                    saved_info = [row[x] for x in range(7)]
                    for n in range(2,len((saved_info := [row[x] for x in range(7)]))):
                        if not saved_info[n] is None:
                            saved_info[n] = fixFieldItemString(saved_info[n])
                    selected_polys = arcpy.management.SelectLayerByAttribute('temp_lyr','NEW_SELECTION',f'{oid_name} = {row[0]}')
                    selected_polys = arcpy.management.SelectLayerByLocation(selected_polys,'BOUNDARY_TOUCHES','temp_lyr')
                    selected_info = {item[0] : (item[2],item[3],item[4],item[5],item[6]) for item in arcpy.da.SearchCursor(selected_polys,required_fields) if item[1] == saved_info[1]}
                    if len((selected_keys := array('i',list(selected_info.keys())))) > 1:
                        for selected_key in selected_keys:
                            for n in range(4):
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
                                    if fixFieldItemString(saved_info[n+2]) != fixFieldItemString(selected_info[selected_key][n]):
                                        selected_info.pop(selected_key)
                                        break
                        if len((selected_keys := array('i',list(selected_info.keys())))) > 1:
                            full_iteration = False
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
                                if max_notes_length < len(saved_info[6]):
                                    arcpy.management.AlterField(f'{dataset}/{fc}','Notes',field_length=len(saved_info[6]))
                            else:
                                saved_info[6] = None
                            select_str = f'{oid_name} IN ({selected_keys[0]}'
                            for n in range(1,len(selected_keys)):
                                select_str = f'{select_str},{selected_keys[n]}'
                            select_str = f'{select_str})'
                            arr = arcpy.Array()
                            for geom in (geoms := tuple([r[0] for r in arcpy.da.SearchCursor(f'{dataset}/{fc}',('SHAPE@',oid_name),select_str)])):
                                for part in geom:
                                    arr.add(part)
                            diss_geom = arcpy.Polygon(arr,geoms[0].spatialReference)
                            counter = 0
                            with arcpy.da.UpdateCursor(f'{dataset}/{fc}',('SHAPE@','IdentityConfidence','Label','Symbol','DataSourceID','Notes'),select_str) as cursor:
                                for row in cursor:
                                    counter += 1
                                    if counter == 1:
                                        row[0] = diss_geom
                                        row[1] = saved_info[2]
                                        row[2] = saved_info[3]
                                        row[3] = saved_info[4]
                                        row[4] = saved_info[5]
                                        row[5] = saved_info[6]
                                        cursor.updateRow(row)
                                    else:
                                        cursor.deleteRow()
                        else:
                            ignore.add(row[0])
                    else:
                        ignore.add(row[0])

    try:
        arcpy.env.workspace = current_workspace[:]
    except Exception:
        pass

    gc.collect()

    arcpy.AddMessage("Process successful!")

mergeMatchingPolygons(gdb_path)
