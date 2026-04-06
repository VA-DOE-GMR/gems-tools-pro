# modules included with ArcGIS Pro
import arcpy,sys,os
from misc_ops import randstr
from os.path import exists
from openpyxl import Workbook,load_workbook
from time import sleep
# custom module
from misc_arcpy_ops import default_env_parameters,deselectObjects

gdb_path = sys.argv[1].replace('\\','/')
auto_delete_dmu_backup = sys.argv[2]

def dmu_excel_editor(gdb_path : str, auto_delete_dmu_backup : bool) -> None:

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


    current_workspace = arcpy.env.workspace[:]
    arcpy.env.workspace = gdb_path[:]

    dmu_path = f'{gdb_path}/DescriptionOfMapUnits'

    # Generate backup DMU
    edit = GeMS_Editor()

    arcpy.management.Copy(dmu_path,f'{dmu_path}_BACKUP')

    edit.end_session()

    temp_excel_dir = gdb_path[:gdb_path.rfind("/")]

    existing_excels = {item[:item.rfind('.')] for item in tuple(os.listdir(temp_excel_dir)) if item.endswith('.xlsx')}

    temp_excel_file_name = f'temp_{randstr()}'

    # failsafe
    while temp_excel_file_name in existing_excels:
        temp_excel_file_name = f'temp_{randstr()}'

    del existing_excels

    temp_excel_path = f'{temp_excel_dir}/{temp_excel_file_name}.xlsx'

    deselectObjects((datasets := tuple([item for item in arcpy.ListDatasets() if item == 'GeologicMap' or 'CrossSection' in item])))
    default_env_parameters()

    fields = ('MapUnit','Name','FullName','Description','Age','HierarchyKey','ParagraphStyle','Label','Symbol','AreaFillRGB','AreaFillPatternDescription','DescriptionSourceID','GeoMaterial','GeoMaterialConfidence')
    range_14 = range(14)

    dmu_table = [tuple([row[n] for n in range_14]) for row in arcpy.da.SearchCursor(dmu_path,fields)]
    dmu_table.insert(0,fields)
    old_num = len(dmu_table)-1

    wb = Workbook()
    ws = wb.create_sheet("DescriptionOfMapUnits")
    for n in range(len((dmu_table := tuple(dmu_table)))):
        for x in range_14:
            ws[f'{chr(65+x)}{n+1}'] = dmu_table[n][x]
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])
    wb.save(temp_excel_path)
    wb.close()

    arcpy.AddMessage("Note: An empty cell in Excel is equivalent to an item in DMU table being set to None/NULL/NoData.")

    try:
        os.system(f'start excel.exe {temp_excel_path}')
    except Exception:
        try:
            os.system(f'start EXCEL.EXE {temp_excel_path}')
        except Exception:
            arcpy.AddError(f'\n\n\nERROR!\n\nEither Microsoft Excel was unconventionally installed on this machine, Microsoft Excel is not installed on this device, or something is preventing Python from opening {temp_excel_path} in Microsoft Excel.')

    # This should give Excel enough time to open the Excel file if not this is
    # concerning.
    sleep(10)

    arcpy.AddMessage("Waiting for Excel file to be saved and Excel program to be closed...")
    # A file starting with ~$ of the same name as the Excel is created whenever
    # an Excel file is currently open.
    while f'~${temp_excel_file_name}.xlsx' in os.listdir(temp_excel_dir):
        sleep(3)

    # This double checks if the required columns still have information. This
    # is mainly to ensure that no intended changes have been made while working
    # in Excel and accidentally closing the program.
    valid_saved_file = False
    wb = load_workbook(temp_excel_path,data_only=True)
    ws = wb["DescriptionOfMapUnits"]
    if sorted([ws[f"{chr(65+x)}1"].value for x in range_14]) == sorted(fields):
        valid_saved_file = True
    wb.close()

    if not valid_saved_file:
        arcpy.AddError("\n\nInvalid changes have been made in the temporary Excel copy of the DescriptionOfMapUnits table!\n\nEdits will be discarded.")
        edit = GeMS_Editor()
        arcpy.management.Delete(f'{dmu_path}_BACKUP_{randstr()}')
        edit.end_session()
        try: remove(temp_excel_path)
        except Exception: pass

    del valid_saved_file

    dmu_table = []

    null_vars = {None,''}

    wb = load_workbook(temp_excel_path,data_only=True)
    ws = wb['DescriptionOfMapUnits']
    for n in range(1,1000):
        try:
            if ws[f'B{n+1}'].value in null_vars and ws[f'C{n+1}'].value in null_vars and ws[f'F{n+1}'].value in null_vars and ws[f'G{n+1}'].value in null_vars and ws[f'L{n+1}'].value in null_vars:
                break
        except Exception:
            break
        dmu_table.append([])
        for x in range_14:
            if (value := ws[f'{chr(65+x)}{n+1}'].value) in null_vars:
                dmu_table[-1].append(None)
            else:
                dmu_table[-1].append(value)
        dmu_table[-1] = tuple(dmu_table[-1])
    wb.close()

    try: del value
    except NameError: pass

    #check for redundant indexes
    redundant_found = True
    while redundant_found:
        for n in range(len(dmu_table)):
            redundant_found = True
            current_index = n
            for x in range_14:
                if not dmu_table[n][x] is None:
                    redundant_found = False
                    break
            if redundant_found:
                break
        if redundant_found:
            dmu_table.pop(current_index)
        else:
            break

    del redundant_found

    edit = GeMS_Editor()

    if (new_num := len((dmu_table := tuple(dmu_table)))) > old_num:
        with arcpy.da.InsertCursor(dmu_path,fields) as cursor:
            for n in range(new_num - old_num):
                cursor.insertRow([None for x in range_14])
    elif new_num < old_num:
        with arcpy.da.UpdateCursor(dmu_path,fields) as cursor:
            min_deletion = old_num - new_num
            num_deleted = 0
            for row in cursor:
                if min_deletion == num_deleted:
                    break
                cursor.deleteRow(row)
                num_deleted += 1

    try: del min_deletion
    except NameError: pass

    edit.end_session()

    edit = GeMS_Editor()

    with arcpy.da.UpdateCursor(dmu_path,fields) as cursor:
        counter = 0
        for row in cursor:
            update_row = False
            for n in range_14:
                if row[n] != dmu_table[counter][n]:
                    row[n] = dmu_table[counter][n]
                    update_row = True
            if update_row:
                cursor.updateRow(row)
            counter += 1
    edit.end_session()

    try: del counter
    except NameError: pass

    del dmu_table ; del fields

    if auto_delete_dmu_backup == 'true':
        edit = GeMS_Editor()
        arcpy.management.Delete(f'{dmu_path}_BACKUP_{randstr()}')
        edit.end_session()

    if exists(temp_excel_path):
        try: os.remove(temp_excel_path)
        except Exception: pass

    arcpy.env.workspace = current_workspace[:]

    return None


dmu_excel_editor(gdb_path,auto_delete_dmu_backup)
