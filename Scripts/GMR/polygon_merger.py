import arcpy
import gc
from misc_arcpy_ops import default_env_parameters
import sys
from array import array

gdb_path = sys.argv[1]

# Typos for MapUnits are not accounted due to too many variable scenarios to consider.
def mergeMatchingPolygons(gdb_path : str):

    '''
    This automatically merges polygons with the same MapUnit bordering each
    other that also have matching relevant fields, excluding polygons with blank
    or Null fields.
    '''

    try:
        current_workspace = arcpy.env.workspace[:]
        current_workspace = current_workspace.replace('\\','/')
    except Exception:
        pass

    arcpy.env.workspace = gdb_path.replace('\\','/')

    default_env_parameters()

    required_fields = ('MapUnit','IdentityConfidence','Label','Symbol','DataSourceID','Notes')

    arcpy.AddMessage("Iterating through all polygons present in geodatabase...")

    for dataset in tuple(arcpy.ListDatasets()):
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
            fields = tuple([field.name for field in tuple(arcpy.ListFields(f'{dataset}/{fc}'))])
            # This is to ensure that the OID/OBJECTID field name is correct as it has not been consistent at times.
            oid_name = fields[0]
            for required in required_fields:
                if not required in fields:
                    oid_name = None
                    break
            if oid_name is None:
                # Skip feature class because it is missing essential fields.
                continue
            fields = list(required_fields)
            fields.insert(0,oid_name)
            ignore = set()
            full_iteration = False
            while not full_iteration:
                # If this never changes to false, it means that no more polygons need to be merged.
                full_iteration = True
                arcpy.management.MakeFeatureLayer(f'{dataset}/{fc}','temp_lyr')
                for row in arcpy.da.SearchCursor(f'{dataset}/{fc}',fields):
                    if row[0] in ignore:
                        continue
                    elif row[1] is None:
                        # Ignore polygon with no MapUnit value.
                        ignore.add(row[0])
                        continue
                    elif row[1].replace(' ','') == '':
                        # Ignore polygon with blank MapUnit value.
                        ignore.add(row[0])
                        continue
                    # Establish initial set of field values for polygon that will be created from merging.
                    current_poly_info = [row[1],row[2],row[3],row[4],row[5],row[6]]

                    # Select current polygon only.
                    selected_polys = arcpy.management.SelectLayerByAttribute('temp_lyr','NEW_SELECTION',f'{oid_name} = {row[0]}')
                    # Select current polygon and all bordering/adjacent polygons in the same feature class.
                    selected_polys = arcpy.management.SelectLayerByLocation(selected_polys,'BOUNDARY_TOUCHES','temp_lyr')

                    # Keep information on polygons that have the same MapUnit value as indicated for current_poly_info (i.e. current polygon basing selection upon)
                    valid_polys = {item[0] : (item[2],item[3],item[4],item[5],item[6]) for item in arcpy.da.SearchCursor(selected_polys,fields) if item[1] == current_poly_info[0]}

                    # Remove MapUnit value as keeping it in memory is redundant.
                    current_poly_info.pop(0)

                    # Skip polygon if no there are no bordering/adjacent polygons that can be deduced to having the same MapUnit value.
                    if len((oids := array('i',[valid_poly for valid_poly in tuple(valid_polys.keys())]))) > 1:
                        for oid in oids:
                            update_elements = False
                            update_items = [None,None,None,None,None]
                            deleted_key = False
                            for n in range(4):
                                if not valid_polys[oid][n] is None:
                                    if valid_polys[oid][n].replace(' ','') != '':
                                        if current_poly_info[n] is None:
                                            update_elements = True
                                            update_items[n] = valid_polys[oid][n]
                                        elif current_poly_info[n].replace(' ','') == '':
                                            update_elements = True
                                            update_items[n] = valid_polys[oid][n]
                                        elif current_poly_info[n].replace(' ','') != valid_polys[oid][n].replace(' ',''):
                                            valid_polys.pop(n)
                                            deleted_key = True
                                            break
                            if update_elements and not deleted_key:
                                for n in range(4):
                                    if not update_items[n] is None:
                                        current_poly_info[n] = update_items[n]
                        # No matching values if condition is false, if any actual values were given.
                        if len((oids := array('i',[valid_poly for valid_poly in tuple(valid_polys.keys())]))) > 1:
                            # compiling Notes
                            full_iteration = False
                            notes = []
                            if not current_poly_info[4] is None:
                                while current_poly_info[4].find('  ') != -1:
                                    current_poly_info[4] = current_poly_info[4].replace('  ',' ')
                                current_poly_info[4] = current_poly_info[4].strip()
                                if current_poly_info[4] != '':
                                    notes.append(current_poly_info[4])
                            for oid in oids:
                                if not (note_item := valid_polys[oid][-1]) is None:
                                    while note_item.find('  ') != -1:
                                        note_item = note_item.replace('  ',' ')
                                    note_item = note_item.strip()
                                    if note_item != '':
                                        notes.append(note_item)
                            if len((notes := tuple(notes))):
                                current_poly_info[4] = f'{notes[0]}'
                                for x in range(1,len(notes)):
                                    current_poly_info[4] = f'{current_poly_info} | {notes[x]}'
                            else:
                                current_poly_info[4] = None
                            for oid in oids:
                                valid_polys[oid][-1]
                            select_str = f'{oid_name} IN ({oids[0]}'
                            for n in range(1,len(oids)):
                                select_str = f'{select_str},{oids[n]}'
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
                                        row[1] = current_poly_info[0]
                                        row[2] = current_poly_info[1]
                                        row[3] = current_poly_info[2]
                                        row[4] = current_poly_info[3]
                                        row[5] = current_poly_info[4]
                                        cursor.updateRow(row)
                                    else:
                                        cursor.deleteRow()
                            break
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
