import arcpy,os,geo_cal,gc,sys
from misc_arcpy_ops import default_env_parameters,explicit_typo_fix
from misc_ops import fixFieldItemString,ref_info,to_tuple
from array import array
from geo_cal import Coord_Pnt,doIntersect

gdb_path = sys.argv[1]
# Example: range(2,3) means there is 1 toggable process and range(2,5) means that there are 3 togglable processes.
enable_process = tuple([sys.argv[n] for n in range(2,3)])

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


# All processes are designed to run independently of each other.
def geofill_GeMS(gdb_path : str, enable_process : tuple) -> None:
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

    datasets = tuple(arcpy.ListDatasets())

    if enable_process[0] == 'true':

        arcpy.AddMessage('Merging matching polygons...')

        edit = GeMS_Editor()

        # Explicit and constant range objects.
        range_4 = range(4)
        range_7 = range(7)

        for dataset in datasets:
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

    placeholder = False

    # Correct self-intersecting polylines
    if placeholder == 'true':

        excluded_fields = frozenset(('created_user','created_date','last_edited_user','last_edited_date','Shape','Shape_Length'))

        for dataset in datasets:
            for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polyline')):
                feature_item = f'{dataset}/{fc}'
                fields = [field.name for field in tuple(arcpy.ListFields(feature_item)) if field.name in excluded_fields]
                fields.remove('Notes')
                fields.append('SHAPE@')
                fields.append('Notes')
                fields = tuple(fields)
                # check for multipart polylines
                multipart_oids = array('i',[])
                for row in arcpy.da.SearchCursor(feature_item,(fields[0],fields[-2])):
                    num_parts = 0
                    for part in row[1]:
                        num_parts += 1
                        if num_parts > 1:
                            break
                    if num_parts > 1:
                        multipart_oids.append(row[0])

                del num_parts

                if len(multipart_oids):
                    # NOT IMPLEMENTED
                    pass

                del multipart_oids

                geo_num = (num_fields := len(fields)) - 2
                info_range = range(1,num_fields-3)
                polylines = dict()

                for row in arcpy.da.SearchCursor(feature_item,fields):
                    polylines[row[0]] = []
                    coords = tuple([Coord_Pnt(vertex.X,vertex.Y) for polyline in row[geo_num] for vertex in polyline])
                    polylines[row[0]].append(tuple([(coords[n],coords[n+1]) for n in range(len(coords)-1)]))
                    del coords
                    polylines[row[0]].append(tuple(row[n] for n in info_range))
                    polylines[row[0]].append(row[num_fields-1])
                    polylines[row[0]] = tuple(polylines[row[0]])

                for oid in tuple(polylines.keys()):
                    for n in range(len(current_coords := polylines[oid][0])-2):
                        coord = current_coords[n]
                        for x in range(n+2,len(current_coords)):
                            pass

        del excluded_fields

    return


geofill_GeMS(gdb_path,enable_process)
