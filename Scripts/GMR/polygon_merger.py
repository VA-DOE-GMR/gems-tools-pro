import arcpy
import gc
from misc_arcpy_ops import default_env_parameters
from misc_ops import fixFieldItemString
import sys
from array import array

gdb_path = sys.argv[1]

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

    # This is to prevent Error #160250 randomly from occurring. This also avoids
    # other arbitrary limits to modifying feature classes and/or tables.
    edit = arcpy.da.Editor(arcpy.env.workspace)
    edit.startEditing(with_undo=False,multiuser_mode=False)
    edit.startOperation()

    arcpy.AddMessage("Iterating through all polygons present in geodatabase...")

    for dataset in tuple(arcpy.ListDatasets()):
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
            arcpy.AddMessage(f"Merging polygons in {fc}...")
            # Information gathered and required to create a merged version of
            # polygons in a polygon feature class.
            polygon_mergers = []
            # This is to prevent this tool from failing if non-GeMS/FGDC feature
            # classes are encountered that may not have all these fields.
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
            # This keeps track of the maximum number of characters currently
            # allowed in the Notes field and number of maximum characters
            # required to concatenate Notes from polygon feature that shall be
            # appended to each other.
            max_notes_length = 0
            new_length = 0
            for field in tuple(arcpy.ListFields(f'{dataset}/{fc}',field_type='String')):
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
            arcpy.management.MakeFeatureLayer(f'{dataset}/{fc}','temp_lyr')
            for row in arcpy.da.SearchCursor('temp_lyr',required_fields):
                if row[0] in ignore:
                    continue
                saved_info = [row[x] for x in range(7)]
                for n in range(2,len((saved_info := [row[x] for x in range(7)]))):
                    if not saved_info[n] is None:
                        saved_info[n] = fixFieldItemString(saved_info[n])
                if saved_info[1] is None:
                    continue
                selected_polys = arcpy.management.SelectLayerByAttribute('temp_lyr','NEW_SELECTION',f'{oid_name} = {row[0]}')
                selected_polys = arcpy.management.SelectLayerByLocation(selected_polys,'BOUNDARY_TOUCHES','temp_lyr')
                selected_info = {item[0] : (item[2],item[3],item[4],item[5],item[6]) for item in arcpy.da.SearchCursor(selected_polys,required_fields) if item[1] == saved_info[1]}
                if len((selected_keys := array('i',selected_info.keys()))) > 1:
                    # Matching MapUnit was found in touching polygons.
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
                                        for n in range(4):
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
                            if not sub_iteration_complete:
                                selected_keys = array('i',selected_info.keys())
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
                        for geom in (geoms := tuple([r[0] for r in arcpy.da.SearchCursor(f'{dataset}/{fc}',('SHAPE@',oid_name),select_str)])):
                            for part in geom:
                                arr.add(part)
                        polygon_mergers.append((saved_info,select_str,arcpy.Polygon(arr,geoms[0].spatialReference)))
                        for selected_key in selected_keys:
                            ignore.add(selected_key)
                    else:
                        # No matching information found in touching polygons.
                        ignore.add(row[0])
                else:
                    # No matching MapUnit value was found in touching polygons.
                    ignore.add(row[0])
            if max_notes_length < new_length:
                # Increase the maximum number of characters allowed for Notes.
                arcpy.management.AlterField(f'{dataset}/{fc}','Notes',field_length=new_length)
            for n in range(len((polygon_mergers := tuple(polygon_mergers)))):
                counter = 0
                with arcpy.da.UpdateCursor(f'{dataset}/{fc}',('SHAPE@','IdentityConfidence','Label','Symbol','DataSourceID','Notes'),polygon_mergers[n][1]) as cursor:
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

    try:
        edit.stopOperation()
    except Exception:
        pass
    try:
        edit.stopEditing(save_changes=True)
    except Exception:
        pass

    try:
        arcpy.env.workspace = current_workspace[:]
    except Exception:
        pass
    
    try:
        arcpy.env.workspace = current_workspace[:]
    except Exception:
        pass

    gc.collect()

    arcpy.AddMessage("Process successful!")

mergeMatchingPolygons(gdb_path)
