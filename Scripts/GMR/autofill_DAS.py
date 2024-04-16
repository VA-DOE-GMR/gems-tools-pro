import arcpy
import gc
from misc_arcpy_ops import default_env_parameters
import os
import sys
from regex import sub as regex_sub

gdb_path = sys.argv[1]
delete_unused = sys.argv[2]

def autofill_DAS(gdb_path,delete_unused):

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

    arcpy.AddMessage("Successfully initialized ArcPy Editor.\n\nGathering list of DASIDs used in geodatabase...")

    # Gather list of all DASIDs used.

    def odbcError() -> None:

        import pyodbc
        db_server_drivers = tuple(pyodbc.drivers())
        ms_odbc_driver = None
        for driver in tuple(pyodbc.drivers()):
            if driver.startswith('ODBC Driver'):
                ms_odbc_driver = driver[:]
                break
        if ms_odbc_driver is None:
            arcpy.AddMessage("\n\nNo ODBC Driver for SQL Server was found on your machine.")
        else:
            arcpy.AddMessage("\n\nYou have an unsupported/outdated version of Microsoft ODBC Driver for SQL Server installed on your machine.")

        return None

    relevant_fields = frozenset(('DataSourceID','DataSources_ID','LocationSourceID','OrientationSourceID','DefinitionSourceID'))

    found_dasids = set()

    def getDASID(relative_path : str):
        dasid_field = None
        for field in tuple(arcpy.ListFields(relative_path,field_type='String')):
            if field.name in relevant_fields:
                dasid_field = field.name
                break
        if dasid_field != None:
            for row in arcpy.da.SearchCursor(relative_path,dasid_field):
                found_dasids.add(row[0])

    for dataset in tuple(arcpy.ListDatasets()):
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
            getDASID(f'{dataset}/{fc}')

    for table in ('Glossary','DescriptionOfMapUnits'):
        getDASID(table)

    del relevant_fields
    gc.collect()

    found_dasids = list(found_dasids)
    while None in found_dasids:
        found_dasids.pop(found_dasids.index(None))

    used_dasids = set()

    for dasid in (found_dasids := tuple(found_dasids)):
        if not '|' in (current_dasid := regex_sub('[^A-Za-z0-9|]+','',dasid)):
            used_dasids.add(current_dasid.upper())
        else:
            current_dasid = current_dasid.upper()
            while current_dasid.find('|') != -1:
                used_dasids.add(current_dasid[:current_dasid.find('|')])
                current_dasid = current_dasid[current_dasid.find('|')+1:]
            if len(current_dasid):
                used_dasids.add(current_dasid)

    del current_dasid ; del found_dasids
    gc.collect()

    used_dasids = tuple(used_dasids)

    # It is safe to assume that no one will have a SDE file called naloe_zelmatitum and would only already exist if it was failed to be deleted when this tool was last being ran.
    if os.path.exists(f"{arcpy.env.workspace[:arcpy.env.workspace.rfind('/')]}/naloe_zelmatitum.sde"):
        os.remove(f"{arcpy.env.workspace[:arcpy.env.workspace.rfind('/')]}/naloe_zelmatitum.sde")

    arcpy.AddMessage("List of DASIDs compiled.\n\nConnecting to Master DAS table in SDE...")

    if not os.path.exists("Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde"):
        arcpy.AddError("Path to pre-existing SDE cannot be found/reached.\n\nAttempting to generate temporary SDE...")
        try:
            arcpy.management.CreateDatabaseConnection((sde_directory := arcpy.env.workspace[:arcpy.env.workspace.rfind('/')]),"naloe_zelmatitum","SQL_SERVER",instance="WSQ06627, 50000",account_authentication="OPERATING_SYSTEM_AUTH",database="DGMRgeo")
            arcpy.env.workspace = f'{sde_directory}/naloe_zelmatitum.sde'
        except Exception:
            arcpy.AddError("An error has transpired while attempting to establish and generate temporary SDE.")
            odbcError()
            return
    else:
        try:
            arcpy.env.workspace = "Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde"
        except Exception:
            arcpy.AddError("An error has transpired when attempting to connecting to SDE.\n\nAttempting to generate temporary SDE...")
            try:
                arcpy.management.CreateDatabaseConnection((sde_directory := arcpy.env.workspace[:arcpy.env.workspace.rfind('/')]),"naloe_zelmatitum","SQL_SERVER",instance="WSQ06627, 50000",account_authentication="OPERATING_SYSTEM_AUTH",database="DGMRgeo")
                arcpy.env.workspace = f'{sde_directory}/naloe_zelmatitum.sde'
            except Exception:
                arcpy.AddError("An error has transpired while attempting to establish and generate SDE.")
                odbcError()
                return

    temp_table = arcpy.management.MakeTableView("DGMRgeo.DBO.DataSources",'temp_table')
    source_dict = {row[3] : (row[0],row[1],row[2]) for row in arcpy.da.SearchCursor(temp_table,['Source','Notes','URL','DataSources_ID']) if not None in (row[0],row[3])}
    master_dasids = frozenset(source_dict.keys())
    valid_dasids = tuple(sorted([item for item in used_dasids if item in master_dasids],key=str))

    del temp_table ; del master_dasids ; del used_dasids
    gc.collect()

    try:
        os.remove(f'{sde_directory}/naloe_zelmatitum.sde')
    except Exception:
        pass

    gc.collect()

    arcpy.AddMessage("Master list of DASID information successfully compiled.\n\nUpdating DataSources table from Master DAS table...")

    num_existing_rows = 0
    arcpy.env.workspace = gdb_path.replace('\\','/')

    old_data = dict()

    for row in arcpy.da.SearchCursor("DataSources",['Source','Notes','URL','DataSources_ID']):
        num_existing_rows += 1
        if not row[3] is None:
            old_data[row[3]] = (row[0],row[1],row[2])

    def addItemsToTable():
        counter = 0
        with arcpy.da.UpdateCursor('DataSources',['Source','Notes','URL','DataSources_ID']) as cursor:
            for row in cursor:
                row[0] = source_dict[valid_dasids[counter]][0]
                row[1] = source_dict[valid_dasids[counter]][1]
                row[2] = source_dict[valid_dasids[counter]][2]
                row[3] = valid_dasids[counter]
                cursor.updateRow(row)
                counter += 1

    if num_existing_rows == len(valid_dasids):
        addItemsToTable()
    elif num_existing_rows < len(valid_dasids):
        with arcpy.da.InsertCursor('DataSources',['Source','Notes','URL','DataSources_ID']) as cursor:
            for n in range(len(valid_dasids) - num_existing_rows):
                cursor.insertRow((None,None,None,None))
        addItemsToTable()
    else:
        num_removed = 0
        num_removal = num_existing_rows - len(valid_dasids)
        with arcpy.da.UpdateCursor('DataSources',['Source','Notes','URL','DataSources_ID']) as cursor:
            for n in cursor:
                cursor.deleteRow()
                num_removed += 1
                if num_removed == num_removal:
                    break
        addItemsToTable()

    if delete_unused == 'true':
        new_data = {row[3] : (row[0],row[1],row[2]) for row in arcpy.da.SearchCursor('DataSources',['Source','Notes','URL','DataSources_ID'])}
        new_data_keys = frozenset(new_data.keys())
        with arcpy.da.InsertCursor('DataSources',['Source','Notes','URL','DataSources_ID']) as cursor:
            for dasid in tuple(old_data.keys()):
                if dasid in new_data_keys:
                    if old_data[dasid] != new_data[dasid]:
                        cursor.insertRow(old_data[dasid])
                else:
                    cursor.insertRow(old_data[dasid])

    arcpy.AddMessage("DataSources successfully updated.\n\nSaving edits...")

    try:
        edit.stopOperation()
    except Exception:
        pass
    try:
        edit.stopEditing(save_changes=True)
    except Exception:
        pass

    arcpy.AddMessage("Edits saved!")

    try:
        arcpy.env.workspace = current_workspace[:]
    except Exception:
        pass

    gc.collect()

autofill_DAS(gdb_path,delete_unused)
