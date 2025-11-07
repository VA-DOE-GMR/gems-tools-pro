import arcpy,sys,os
from misc_arcpy_ops import default_env_parameters
from misc_ops import ref_info,makeListIntArray
from os.path import exists
from array import array
from openpyxl import Workbook,load_workbook
from fundamentals import rgb_into_cmy,cmy_into_wpg

# sys.argv[0] is reserved.
gdb_path = sys.argv[1]
excel_path = sys.argv[2]

def autoreview_GeMS(gdb_path : str, excel_path : str) -> None:

    if excel_path.endswith('.xlsx') or excel_path.endswith('.xls'):
        generateExcel = True
        # This will cause the tool to fail if an excel_path is given, the Excel
        # already exists at the specified directory, AND said file is opened
        # in Microsoft Excel or any other program that can open Excel files
        # like LibreOffice.
        if exists(excel_path):
            os.remove(excel_path)
    else:
        generateExcel = False
    current_workspace = arcpy.env.workspace[:]
    current_workspace = current_workspace.replace('\\','/')
    arcpy.env.workspace = gdb_path.replace('\\','/')

    arcpy.AddMessage(arcpy.env.workspace)

    default_env_parameters()

    datasets = tuple(arcpy.ListDatasets())

    arcpy.AddMessage("\nChecking Glossary table...")

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

    try: del num_fields
    except NameError: pass
    try: del relevant_fields
    except NameError: pass
    try: del field_range
    except NameError: pass

    term_def_id = {row[0] : (row[1],row[2]) for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/Glossary',('Term','Definition','DefinitionSourceID'))}
    glossary_terms = tuple(term_def_id.keys())

    if (num_terms := len((redundant_terms := tuple(sorted([glossary_term for glossary_term in glossary_terms if not glossary_term in used_terms],key=str))))):
        arcpy.AddMessage("\nThe following terms are not needed in the Glossary:\n\n")
        for item in redundant_terms:
            arcpy.AddMessage(item)
        if generateExcel:
            arcpy.AddMessage('\nSaving to Excel file...')
            if not exists(excel_path):
                wb = Workbook()
            else:
                wb = load_workbook(excel_path,data_only=True)
                for sheet in wb.sheetnames:
                    if 'Redundant_Glossary_Terms' == sheet:
                        wb.remove(wb[sheet])
                        break
            ws = wb.create_sheet("Redundant_Glossary_Terms")
            ws['A1'] = "Glossary Term"
            for n in range(num_terms):
                ws[f'A{n+2}'] = redundant_terms[n]
            if 'Sheet' in wb.sheetnames:
                wb.remove(wb['Sheet'])
            wb.save(excel_path)
            wb.close()
            arcpy.AddMessage("Save successful!\n")

    del redundant_terms

    glossary_terms = set(glossary_terms)

    if (num_terms := len((missing_terms := tuple(sorted([used_term for used_term in tuple(used_terms) if not used_term in glossary_terms],key=str))))):
        arcpy.AddMessage("\nThe following terms are missing from the Glossary:\n\n")
        for item in missing_terms:
            arcpy.AddMessage(item)
        if generateExcel:
            arcpy.AddMessage('\nSaving to Excel file...')
            if not exists(excel_path):
                wb = Workbook()
            else:
                wb = load_workbook(excel_path,data_only=True)
                for sheet in wb.sheetnames:
                    if 'Missing_Terms' == sheet:
                        wb.remove(wb[sheet])
                        break
            ws = wb.create_sheet('Missing_Terms')
            ws['A1'] = 'Glossary Term'
            for n in range(num_terms):
                ws[f'A{n+2}'] = missing_terms[n]
            if 'Sheet' in wb.sheetnames:
                wb.remove(wb['Sheet'])
            wb.save(excel_path)
            wb.close()
            arcpy.AddMessage("Save successful!\n")

    del missing_terms ; del num_terms

    glossary_terms = tuple(glossary_terms)

    code_directory = arcpy.env.workspace[:]
    naloe_zelmatitum = False

    if os.path.exists('Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'):
        try:
            arcpy.AddMessage('\n\nConnecting to pre-existing SDE...')
            arcpy.env.workspace = 'Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'
            arcpy.AddMessage('Successfully established connection!')
            naloe_zelmatitum = True
        except Exception:
            arcpy.AddError("\n\nSomething went wrong when trying to connect via pre-existing SDE.\n\nManually check Glossary terms and corresponding definitions.")

    if naloe_zelmatitum:
        arcpy.AddMessage('\n\nChecking Glossary table against master Glossary table...')

        temp_table = arcpy.management.MakeTableView("DGMRgeo.DBO.Glossary",'temp_table')
        term_dict = {row[0] : (row[1],row[2]) for row in arcpy.da.SearchCursor('temp_table',('Term','Definition','DefinitionSourceID')) if not None in (row[0],row[1],row[2])}

        del temp_table

        master_terms = set(term_dict.keys())
        arcpy.env.workspace = code_directory[:]

        if (num_terms := len((unadded_terms := tuple(sorted([glossary_term for glossary_term in glossary_terms if not glossary_term in master_terms],key=str))))):
            arcpy.AddMessage("\nThe following terms have not been added to the Glossary in the SDE and/or are simply errors:\n\n")
            for item in unadded_terms:
                arcpy.AddMessage(item)
            if generateExcel:
                arcpy.AddMessage("\nSaving to Excel file...")
                if not exists(excel_path):
                    wb = Workbook()
                else:
                    wb = load_workbook(excel_path,data_only=True)
                    for sheet in wb.sheetnames:
                        if 'Anomoly_or_Error_Terms' == sheet:
                            wb.remove(wb[sheet])
                            break
                ws = wb.create_sheet('Anomoly_or_Error_Terms')
                ws['A1'] = 'Glossary Term'
                for n in range(num_terms):
                    ws[f'A{n+2}'] = unadded_terms[n]
                if 'Sheet' in wb.sheetnames:
                    wb.remove(wb['Sheet'])
                wb.save(excel_path)
                wb.close()
                arcpy.AddMessage("Save successful!\n")

        del unadded_terms ; del num_terms

        incomplete_defs = []

        for glossary_term in glossary_terms:
            if glossary_term in master_terms:
                if term_dict[glossary_term][0].startswith(term_def_id[glossary_term][0]) and term_def_id[glossary_term][0] != term_dict[glossary_term][0]:
                    incomplete_defs.append(glossary_term)

        if (num_terms := len((incomplete_defs := tuple(sorted(incomplete_defs,key=str))))):
            arcpy.AddMessage("\nThe following terms have truncated definitions in the Glossary:\n\n")
            for item in incomplete_defs:
                arcpy.AddMessage(item)
            if generateExcel:
                arcpy.AddMessage("\nSaving to Excel file...")
                if not exists(excel_path):
                    wb = Workbook()
                else:
                    wb = load_workbook(excel_path,data_only=True)
                    for sheet in wb.sheetnames:
                        if 'Truncated_Definitions' == sheet:
                            wb.remove(wb[sheet])
                            break
                ws = wb.create_sheet('Truncated_Definitions')
                ws['A1'] = 'Term'
                ws['B1'] = 'Truncated Definition'
                ws['C1'] = 'Full Definition'
                for n in range(num_terms):
                    ws[f'A{n+2}'] = incomplete_defs[n]
                    ws[f'B{n+2}'] = term_def_id[incomplete_defs[n]][0]
                    ws[f'C{n+2}'] = term_dict[incomplete_defs[n]][0]
                if 'Sheet' in wb.sheetnames:
                    wb.remove(wb['Sheet'])
                wb.save(excel_path)
                wb.close()
                arcpy.AddMessage("Save successful!\n")

        incomplete_defs = set(incomplete_defs)

        mismatched_defs = []

        for glossary_term in glossary_terms:
            if glossary_term in master_terms:
                if term_dict[glossary_term][0] != term_def_id[glossary_term][0] and not glossary_term in incomplete_defs:
                    mismatched_defs.append(glossary_term)

        del incomplete_defs ; del term_def_id ; del master_terms ; del glossary_terms ; del term_dict

        if (num_terms := len((mismatched_defs := tuple(sorted(mismatched_defs,key=str))))):
            arcpy.AddMessage("\nThe following terms have definitions not matching those in the master Glossary in the SDE:\n\n")
            for item in mismatched_defs:
                arcpy.AddMessage(item)
            if generateExcel:
                arcpy.AddMessage("\nSaving to Excel file...")
                if not exists(excel_path):
                    wb = Workbook()
                else:
                    wb = load_workbook(excel_path,data_only=True)
                    for sheet in wb.sheetnames:
                        if 'Term_Not_in_Master_Glossary' == sheet:
                            wb.remove(wb[sheet])
                            break
                ws = wb.create_sheet('Mismatching_Definitions')
                ws['A1'] = 'Glossary Term'
                for n in range(num_terms):
                    ws[f'A{n+2}'] = mismatched_defs
                if 'Sheet' in wb.sheetnames:
                    wb.remove(wb['Sheet'])
                wb.save(excel_path)
                wb.close()
                arcpy.AddMessage("Save successful!\n")

        del num_terms

    del naloe_zelmatitum ; del code_directory

    # Requires more testing
    arcpy.AddMessage("\nChecking DataSources table...")

    found_dasids = set()
    used_dasids = set()
    valid_fields = {'DataSourceID','LocationSourceID','OrientationSourceID'}

    for dataset in datasets:
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
            if 'DataSourceID' in tuple([field.name for field in arcpy.ListFields(f'{dataset}/{fc}')]):
                for row in arcpy.da.SearchCursor(f'{dataset}/{fc}','DataSourceID'):
                    found_dasids.add(row[0])

    for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits','DescriptionSourceID'):
        found_dasids.add(row[0])

    for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/Glossary','DefinitionSourceID'):
        found_dasids.add(row[0])

    if None in found_dasids:
        found_dasids.remove(None)

    found_dasids = list(found_dasids)

    for invalid_dasid in tuple([found_dasids[n] for n in range(len(found_dasids)) if not found_dasids[n].startswith('DAS')]):
        found_dasids.remove(invalid_dasid)

    for item in (found_dasids := tuple(found_dasids)):
        if 'DAS' in item:
            if '|' in item:
                temp_item = item[:]
                while '|' in temp_item:
                    if temp_item.startswith('DAS'):
                        used_dasids.add(temp_item[:temp_item.find('|')])
                    temp_item = temp_item[temp_item.find('|')+1:]
                if temp_item.startswith('DAS'):
                    used_dasids.add(temp_item)
                del temp_item
            else:
                used_dasids.add(item)

    del found_dasids

    dasids = {row[0] : (row[1],row[2],row[3]) for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DataSources',('DataSources_ID','Source','Notes','URL'))}
    id_dasids = tuple(dasids.keys())

    if len((redundant_dasids := tuple([id_dasid for id_dasid in id_dasids if not id_dasid in used_dasids]))):
        nums = []
        for item in redundant_dasids:
            try: nums.append(int(item[3:]))
            except TypeError: pass
        nums = makeListIntArray(sorted(nums))
        if (num_dasids := len((redundant_dasids := tuple([f'DAS{num}' for num in nums])))):
            arcpy.AddMessage("\nThe following are DASIDs that do not appear in the geodatabase:\n\n")
            for item in redundant_dasids:
                arcpy.AddMessage(item)
            if generateExcel:
                arcpy.AddMessage('\nSaving to Excel file...')
                if not exists(excel_path):
                    wb = Workbook()
                else:
                    wb = load_workbook(excel_path,data_only=True)
                    for sheet in wb.sheetnames:
                        if 'Unused_DASIDs' == sheet:
                            wb.remove(wb[sheet])
                            break
                ws = wb.create_sheet('Unused_DASIDs')
                ws['A1'] = 'DASID'
                for n in range(num_dasids):
                    ws[f'A{n+2}'] = redundant_dasids[n]
                if 'Sheet' in wb.sheetnames:
                    wb.remove(wb['Sheet'])
                wb.save(excel_path)
                wb.close()
                arcpy.AddMessage("Save successful!\n")

        del nums ; del num_dasids

    del redundant_dasids

    id_dasids = set(id_dasids)

    if len((missing_dasids := tuple([used_dasid for used_dasid in tuple(used_dasids) if not used_dasid in id_dasids]))):
        nums = []
        for item in missing_dasids:
            try: nums.append(int(item[3:]))
            except TypeError: pass
        nums = makeListIntArray(sorted(nums))
        if (num_dasids := len((missing_dasids := tuple([f'DAS{num}' for num in nums])))):
            arcpy.AddMessage("\nThe following DASIDs are missing from DataSources table:\n\n")
            for item in missing_dasids:
                arcpy.AddMessage(item)
            if generateExcel:
                arcpy.AddMessage("\nSaving to Excel file...")
                if not exists(excel_path):
                    wb = Workbook()
                else:
                    wb = load_workbook(excel_path,data_only=True)
                    for sheet in wb.sheetnames:
                        if 'Missing_DASIDs' == sheet:
                            wb.remove(wb[sheet])
                            break
                ws = wb.create_sheet('Missing_DASIDs')
                ws['A1'] = 'DASID'
                for n in range(num_dasids):
                    ws[f'A{n+2}'] = missing_dasids[n]
                if 'Sheet' in wb.sheetnames:
                    wb.remove(wb['Sheet'])
                wb.save(excel_path)
                wb.close()
                arcpy.AddMessage("Save successful!\n")

        del nums ; del num_dasids

    id_dasids = tuple(id_dasids)

    del used_dasids ; del missing_dasids

    code_directory = arcpy.env.workspace[:]
    naloe_zelmatitum = False

    if os.path.exists('Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'):
        try:
            arcpy.AddMessage('\n\nConnecting to pre-existing SDE...')
            arcpy.env.workspace = 'Z:/PROJECTS/MAPPING/GuidanceDocs/GeMS/gems-tools-pro-GMR/SDE_connection.sde'
            arcpy.AddMessage('Successfully established connection!')
            naloe_zelmatitum = True
        except Exception:
            arcpy.AddError("\n\nSomething went wrong when trying to connect via pre-existing SDE.\n\nManually check DataSources table.")

    if naloe_zelmatitum:
        arcpy.AddMessage('\n\nChecking DataSources table against master DataSources table...')

        temp_table = arcpy.management.MakeTableView("DGMRgeo.DBO.DataSources",'temp_table')
        dasid_dict = {row[0] : (row[1],row[2],row[3]) for row in arcpy.da.SearchCursor('temp_table',('DataSources_ID','Source','Notes','URL')) if not row[0] is None}

        del temp_table

        master_dasids = set(dasid_dict.keys())
        arcpy.env.workspace = code_directory[:]

        id_dasids = tuple(id_dasids)

        if (num_dasids := len((unadded_dasids := tuple([id_dasid for id_dasid in id_dasids if not id_dasid in master_dasids])))):
            nums = []
            for item in unadded_dasids:
                try: nums.append(int(item[3:]))
                except TypeError: pass
            nums = makeListIntArray(sorted(nums))
            if len((unadded_dasids := tuple([f'DAS{num}' for num in nums]))):
                arcpy.AddMessage("\nThe following DASIDs have not been added to the master DataSources table and/or have been included in the DataSources table by mistake:\n\n")
                for item in unadded_dasids:
                    arcpy.AddMessage(item)
                if generateExcel:
                    arcpy.AddMessage("\nSaving to Excel file...")
                    if not exists(excel_path):
                        wb = Workbook()
                    else:
                        wb = load_workbook(excel_path,data_only=True)
                        for sheet in wb.sheetnames:
                            if 'DASID_Not_in_Master_Glossary' == sheet:
                                wb.remove(wb[sheet])
                                break
                    ws = wb.create_sheet('DASID_Not_in_Master_Glossary')
                    ws['A1'] = 'DASID'
                    for n in range(num_dasids):
                        ws[f'A{n+2}'] = unadded_dasids[n]
                    if 'Sheet' in wb.sheetnames:
                        wb.remove(wb['Sheet'])
                    wb.save(excel_path)
                    wb.close()
                    arcpy.AddMessage("Save successful!\n")
            del nums

        del unadded_dasids ; num_dasids

        invalid_source = [] ; invalid_notes = [] ; invalid_url = []

        for id_dasid in id_dasids:
            if id_dasid in master_dasids:
                if dasids[id_dasid][0] != dasid_dict[id_dasid][0]:
                    invalid_source.append(id_dasid)
                if dasids[id_dasid][1] != dasid_dict[id_dasid][1]:
                    invalid_notes.append(id_dasid)
                if dasids[id_dasid][2] != dasid_dict[id_dasid][2]:
                    invalid_url.append(id_dasid)

        if len((invalid_source := tuple(invalid_source))):
            nums = []
            for item in invalid_source:
                try: nums.append(int(item[3:]))
                except TypeError: pass
            nums = makeListIntArray(sorted(nums))
            if (num_invalids := len((invalid_source := tuple([f'DAS{num}' for num in nums])))):
                arcpy.AddMessage("\nThe following DASIDs do not have their Source field matching the Source field for the master DataSources table:\n\n")
                for item in invalid_source:
                    arcpy.AddMessage(item)
                if generateExcel:
                    arcpy.AddMessage("\nSaving to Excel file...")
                    if exists(excel_path):
                        wb = Workbook()
                    else:
                        wb = load_workbook(excel_path,data_only=True)
                        for sheet in wb.sheetnames:
                            if 'Invalid_Sources' == sheet:
                                wb.remove(wb[sheet])
                                break
                    ws = wb.create_sheet('Invalid_Sources')
                    ws['A1'] = 'DASID'
                    for n in range(num_invalids):
                        ws[f'A{n+2}'] = invalid_source[n]
                    if 'Sheet' in wb.sheetnames:
                        wb.remove(wb['Sheet'])
                    wb.save(excel_path)
                    wb.close()
                    arcpy.AddMessage("Save successful!\n")
            del nums

        del invalid_source

        if (num_invalids := len((invalid_notes := tuple(invalid_notes)))):
            nums = []
            for item in invalid_notes:
                try: nums.append(int(item[3:]))
                except TypeError: pass
            nums = makeListIntArray(sorted(nums))
            if len((invalid_notes := tuple([f'DAS{num}' for num in nums]))):
                arcpy.AddMessage("\nThe following DASIDs do not have their Notes field matching the Notes field for the master DataSources table:\n\n")
                for item in invalid_notes:
                    arcpy.AddMessage(item)
                if generateExcel:
                    arcpy.AddMessage("\nSaving to Excel file...")
                    if not exists(excel_path):
                        wb = Workbook()
                    else:
                        wb = load_workbook(excel_path,data_only=True)
                        for sheet in wb.sheetnames:
                            if 'Invalid_Notes' == sheet:
                                wb.remove(wb[sheet])
                                break
                    ws = create_sheet('Invalid_Notes')
                    ws['A1'] = 'DASID'
                    for n in range(num_invalids):
                        ws[f'A{n+2}'] = invalid_notes[n]
                    if 'Sheet' in wb.sheetnames:
                        wb.remove(wb['Sheet'])
                    wb.save(excel_path)
                    wb.close()
                    arcpy.AddMessage("Save successful!\n")
            del nums

        del invalid_notes

        if (num_invalids := len((invalid_url := tuple(invalid_url)))):
            nums = []
            for item in invalid_url:
                try: nums.append(int(item[3:]))
                except TypeError: pass
            nums = makeListIntArray(sorted(nums))
            if len((invalid_url := tuple([f'DAS{num}' for num in nums]))):
                arcpy.AddMessage("\nThe following DASIDs do not have their URL field matching the URL field for the master DataSources table:\n\n")
                for item in invalid_url:
                    arcpy.AddMessage(item)
                if generateExcel:
                    arcpy.AddMessage("\nSaving to Excel file...")
                    if not exists(excel_path):
                        wb = Workbook()
                    else:
                        wb = load_workbook(excel_path,data_only=True)
                        for sheet in wb.sheetnames:
                            if 'Invalid_URLs' == sheet:
                                wb.remove(wb[sheet])
                                break
                    ws = wb.create_sheet('Invalid_URLs')
                    ws['A1'] = 'DASID'
                    for n in range(num_invalids):
                        ws[f'A{n+2}'] = invalid_url[n]
                    if 'Sheet' in wb.sheetnames:
                        wb.remove(wb['Sheet'])
                    wb.save(excel_path)
                    wb.close()
                    arcpy.AddMessage("Save successful!\n")
            del nums

        del invalid_url ; del master_dasids ; del dasid_dict ; del num_invalids

    del code_directory ; del naloe_zelmatitum

    arcpy.AddMessage("\nChecking DescriptionOfMapUnits table...")

    dmu_info = {int(row[0]) : (row[1],row[2],row[3],row[4],row[5],row[6],row[7],row[8],row[9],row[10],row[11],row[12],row[13]) for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/DescriptionOfMapUnits',('OID@','MapUnit','Name','FullName','Description','Age','HierarchyKey','ParagraphStyle','Label','Symbol','AreaFillRGB','GeoMaterial','GeoMaterialConfidence','AreaFillPatternDescription'))}
    oids = makeListIntArray(sorted(dmu_info.keys()))

    invalid_mapunits = {}
    invalid_names = {}
    invalid_fullnames = {}
    invalid_descriptions = {}
    invalid_ages = {}
    invalid_symbols = {}
    invalid_labels = {}
    invalid_rgbs = {}
    invalid_patternDescriptions = {}
    invalid_geoMaterials = {}
    invalid_geoMaterialConfidences = {}
    invalid_hierarchyKeys = {}

    # Since everything should be Level 3 Compliant, there is no need to check if
    # any entry in the ParagraphStyle field has no data.
    dmu_unit_oids = makeListIntArray([oid for oid in oids if dmu_info[oid][6].startswith('DMUHeading')])
    for oid in dmu_unit_oids:
        current_item = dmu_info[oid]
        if isinstance(current_item[0],str):
            invalid_mapunits[oid] = 'Unneeded MapUnit'
        if isinstance(current_item[3],str):
            invalid_descriptions[oid] = 'Unneeded Description'
        if isinstance(current_item[4],str):
            invalid_ages[oid] = 'Unneeded Age'
        if isinstance(current_item[7],str):
            invalid_labels[oid] = 'Unneeded Label'
        if isinstance(current_item[8],str):
            invalid_symbols[oid] = 'Unneeded Symbol'
        if isinstance(current_item[9],str):
            invalid_rgbs[oid] = 'Unneeded RGB Values'
        if isinstance(current_item[10],str):
            invalid_geoMaterials[oid] = 'Unneeded GeoMaterial'
        if isinstance(current_item[11],str):
            invalid_geoMaterialConfidences[oid] = 'Unneeded GeoMaterialConfidence'
        if isinstance(current_item[12],str):
            invalid_patternDescriptions[oid] = 'Unneeded AreaFillPatternDescription'

    for oid in dmu_unit_oids:
        current_item = dmu_info[oid]
        temp_str = current_item[5].strip()
        if not temp_str.replace('-','').isdigit():
            invalid_hierarchyKeys[oid] = 'No Alphanumeric Characters'
        del temp_str

    del dmu_unit_oids

    errored_symbol_oids = set()

    for oid in oids:
        if not oid in set(invalid_symbols.keys()):
            if dmu_info[oid][8] is None:
                if not dmu_info[oid][6].startswith('DMUHeading'):
                    errored_symbol_oids.add(oid)
                    invalid_symbols[oid] = 'Symbol not given for MapUnit'
            elif not dmu_info[oid][8].isdigit():
                errored_symbol_oids.add(oid)
                invalid_symbols[oid] = 'Non-numeric character is present.'

    for oid in oids:
        if not (current_item := dmu_info[oid][9]) is None:
            if not current_item.replace(',','').isdigit():
                invalid_rgbs[oid] = 'A character that is neither numeric nor a comma is present.'
            elif (num_commas := current_item.count(',')) < 2:
                invalid_rgbs[oid] = 'Missing 1 or 2 values required for RGB.'
            elif num_commas > 2:
                invalid_rgbs[oid] = 'More than 3 values given for the RGB.'
            elif len(current_item) != 11:
                invalid_rgbs[oid] = 'RGB values does not have Red, Green, and Blue values represented as 3 digits each.'
            else:
                rgb_str = current_item[:]
                rgb_values = array('H',(0,0,0))
                rgb_values[0] = int(rgb_str[:rgb_str.find(',')])
                rgb_str = rgb_str[rgb_str.find(',')+1:]
                rgb_values[1] = int(rgb_str[:rgb_str.find(',')])
                rgb_values[2] = int(rgb_str[rgb_str.find(',')+1:])
                if rgb_values[0] > 255 or rgb_values[1] > 255 or rgb_values[2] > 255:
                    invalid_rgbs[oid] = 'Red, Green, and/or Blue value in RBG is greater than 255.'
                    del rgb_str ; del rgb_values
                    continue
                del rgb_str
                if not oid in errored_symbol_oids:
                    if cmy_into_wpg(rgb_into_cmy(rgb_values[0],rgb_values[1],rgb_values[2])) != dmu_info[oid][8]:
                        invalid_symbols[oid] = 'WPG Symbol value does not correspond to RGB value.'
                        invalid_rgbs[oid] = 'RGB value does not correspond to WPG Symbol value.'
                del rgb_values

    del errored_symbol_oids

    try: del num_commas
    except NameError: pass

    hierarchy_nums = {}
    # Converting hierarchy values into numbers for easier checking and comparison.
    for oid in oids:
        if not '-' in (current_item := dmu_info[oid][5]):
            try:
                hierarchy_nums[oid] = array('H',(int(current_item),0,0,0,0,0,0,0,0,0))
            except Exception:
                invalid_hierarchyKeys[oid] = 'Invalid Entry'
        elif not current_item.replace('-','').isdigit():
            invalid_hierarchyKeys[oid] = 'Includes non-numeric characters (excluding "-")'
        else:
            temp_nums = array('H',[])
            temp_str = current_item[:]
            while '-' in temp_str:
                temp_nums.append(int(temp_str[:temp_str.find('-')]))
                temp_str = temp_str[temp_str.find('-')+1:]
            temp_nums.append(int(temp_str))
            del temp_str
            for n in range(10-len(temp_nums)):
                temp_nums.append(0)
            hierarchy_nums[oid] = temp_nums[:]
            del temp_nums

    temp_other_oids = set(invalid_geoMaterials.keys())

    geoMaterials = set(row[0] for row in arcpy.da.SearchCursor(f'{arcpy.env.workspace}/GeoMaterialDict','GeoMaterial'))

    temp_oids = makeListIntArray([oid for oid in oids if not dmu_info[oid][6].startswith('DMUHeading')])

    for oid in temp_oids:
        if not oid in temp_other_oids:
            if not dmu_info[oid][10] in geoMaterials:
                invalid_geoMaterials[oid] = 'GeoMaterial not in GeoMaterialDict table.'

    del temp_other_oids ; del geoMaterials ; del temp_oids

    # This compiles all dictionaries into a singular one.
    issues_found = {}

    for oid in oids:
        issues_found[oid] = []
        if oid in invalid_mapunits.keys(): issues_found[oid].append(invalid_mapunits[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_names.keys(): issues_found[oid].append(invalid_names[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_fullnames.keys(): issues_found[oid].append(invalid_fullnames[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_descriptions.keys(): issues_found[oid].append(invalid_descriptions[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_ages.keys(): issues_found[oid].append(invalid_ages[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_hierarchyKeys.keys(): issues_found[oid].append(invalid_hierarchyKeys[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_labels.keys(): issues_found[oid].append(invalid_labels[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_symbols.keys(): issues_found[oid].append(invalid_symbols[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_rgbs.keys(): issues_found[oid].append(invalid_rgbs[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_geoMaterials.keys(): issues_found[oid].append(invalid_geoMaterials[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_geoMaterialConfidences.keys(): issues_found[oid].append(invalid_geoMaterialConfidences[oid])
        else: issues_found[oid].append("N/A")
        if oid in invalid_patternDescriptions.keys(): issues_found[oid].append(invalid_patternDescriptions[oid])
        else: issues_found[oid].append("N/A")
        if tuple(issues_found[oid]).count("N/A") == 12: del issues_found[oid]
        else: issues_found[oid] = tuple(issues_found[oid])

    del invalid_mapunits ; del invalid_descriptions ; del invalid_ages ; del invalid_symbols ; del invalid_labels ; del invalid_rgbs ; del invalid_patternDescriptions ; del invalid_geoMaterials ; del invalid_geoMaterialConfidences

    oids = makeListIntArray(tuple(issues_found.keys()))

    if len(oids):
        arcpy.AddMessage('Potential Issues Found with DescriptionOfMapUnits:\n\nOID|MapUnit|Name|FullName|Description|Age|HierarchyKey|Label|Symbol|AreaFillRGB|GeoMaterial|GeoMaterialConfidence|AreaFillPatternDescription')
        for oid in oids:
            arcpy.AddMessage(f'{oid}|{issues_found[oid][0]}|{issues_found[oid][1]}|{issues_found[oid][2]}|{issues_found[oid][3]}|{issues_found[oid][4]}|{issues_found[oid][5]}|{issues_found[oid][6]}|{issues_found[oid][7]}|{issues_found[oid][8]}|{issues_found[oid][9]}|{issues_found[oid][10]}|{issues_found[oid][11]}')
        if generateExcel:
            arcpy.AddMessage("\nSaving to Excel file...")
            if not exists(excel_path):
                wb = Workbook()
            else:
                wb = load_workbook(excel_path,data_only=True)
                for sheet in wb.sheetnames:
                    if 'Potential_DMU_Errors' == sheet:
                        wb.remove(wb[sheet])
                        break
            ws = wb.create_sheet('Potential_DMU_Errors')
            ws['A1'] = 'OID'
            ws['B1'] = 'MapUnit'
            ws['C1'] = 'Name'
            ws['D1'] = 'FullName'
            ws['E1'] = 'Description'
            ws['F1'] = 'Age'
            ws['G1'] = 'HierarchyKey'
            ws['H1'] = 'Label'
            ws['I1'] = 'Symbol'
            ws['J1'] = 'AreaFillRGB'
            ws['K1'] = 'GeoMaterial'
            ws['L1'] = 'GeoMaterialConfidence'
            ws['M1'] = 'AreaFillPatternDescription'
            for n in range(len(oids)):
                ws[f'A{n+2}'] = str(oids[n])
                ws[f'B{n+2}'] = issues_found[oids[n]][0]
                ws[f'C{n+2}'] = issues_found[oids[n]][1]
                ws[f'D{n+2}'] = issues_found[oids[n]][2]
                ws[f'E{n+2}'] = issues_found[oids[n]][3]
                ws[f'F{n+2}'] = issues_found[oids[n]][4]
                ws[f'G{n+2}'] = issues_found[oids[n]][5]
                ws[f'H{n+2}'] = issues_found[oids[n]][6]
                ws[f'I{n+2}'] = issues_found[oids[n]][7]
                ws[f'J{n+2}'] = issues_found[oids[n]][8]
                ws[f'K{n+2}'] = issues_found[oids[n]][9]
                ws[f'L{n+2}'] = issues_found[oids[n]][10]
                ws[f'M{n+2}'] = issues_found[oids[n]][11]
            if 'Sheet' in wb.sheetnames:
                wb.remove(wb['Sheet'])
            wb.save(excel_path)
            wb.close()
            arcpy.AddMessage("Save successful!\n")

    try: del current_item
    except NameError: pass

    del oids ; del dmu_info ; del issues_found

    #arcpy.AddMessage("\nCompiling list of all symbols used in the geodatabase...")

    # Symbol Code, {Associated Types/Terms}, {Associated Feature Type}, {Associated Feature Classes}
    symbol_info = {}

    del symbol_info

    arcpy.AddMessage("\nChecking OrientationPoints feature classes...")
    for dataset in datasets:
        for fc in arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point'):
            if fc.endswith('OrientationPoints'):
                item = f'{dataset}/{fc}'
                arcpy.AddMessage(f'\n{item}')
                ori_points = {}
                for row in arcpy.da.SearchCursor(item,('OID@','Azimuth','Inclination','Label','MapUnit')):
                    ori_points[(oid := int(row[0]))] = []
                    if not row[1] is None:
                        ori_points[oid].append(float(row[1]))
                    else:
                        ori_points[oid].append(None)
                    if not row[2] is None:
                        ori_points[oid].append(float(row[2]))
                    else:
                        ori_points[oid].append(None)
                    if not row[3] is None:
                        ori_points[oid].append(float(row[3]))
                    else:
                        ori_points[oid].append(None)
                    ori_points[oid].append(row[4])
                outside_range_azimuth = {}
                outside_range_inclination = {}
                not_matching_incl_label = {}
                for oid in tuple(ori_points.keys()):
                    if not ori_points[oid][0] is None:
                        if ori_points[oid][0] < 0 or ori_points[oid][0] > 360:
                            outside_range_azimuth[oid] = ori_points[oid][0]
                    if not ori_points[oid][1] is None:
                        if ori_points[oid][1] < 0 or ori_points[oid][1] > 90:
                            outside_range_inclination[oid] = ori_points[oid][1]
                    if not None in (ori_points[oid][1],ori_points[oid][2]):
                        if ori_points[oid][1] != ori_points[oid][2]:
                            not_matching_incl_label[oid] = (ori_points[oid][1],ori_points[oid][2])
                    elif (ori_points[oid][1] is None and not ori_points[oid][2] is None) or (not ori_points[oid][1] is None and ori_points[oid][2] is None):
                        not_matching_incl_label[oid] = (ori_points[oid][1],ori_points[oid][2])
                if (num_oids := len((oids := tuple(outside_range_azimuth.keys())))):
                    arcpy.AddMessage('\nThe following points have Azimuth values outside the range 0-360:\n\nOID|Invalid Value\n')
                    for oid in oids:
                        arcpy.AddMessage(f'{oid}|{outside_range_azimuth[oid]}')
                    if generateExcel:
                        arcpy.AddMessage("\nSaving to Excel file...")
                        current_rootName = ref_info.getRootName(fc)
                        if not exists(excel_path):
                            wb = Workbook()
                        else:
                            wb = load_workbook(excel_path,data_only=True)
                            for sheet in wb.sheetnames:
                                if f'{current_rootName}_Invalid_Azimuths' == sheet:
                                    wb.remove(wb[sheet])
                                    break
                        ws = wb.create_sheet(f'{current_rootName}_Invalid_Azimuths')
                        del current_rootName
                        ws['A1'] = 'OID'
                        ws['B1'] = 'Invalid Value'
                        for n in range(num_oids):
                            ws[f'A{n+2}'] = str(oids[n])
                            ws[f'B{n+2}'] = outside_range_azimuth[oids[n]]
                        if 'Sheet' in wb.sheetnames:
                            wb.remove(wb['Sheet'])
                        wb.save(excel_path)
                        wb.close()
                        arcpy.AddMessage("Save successful!\n")
                del outside_range_azimuth
                if (num_oids := len((oids := tuple(outside_range_inclination.keys())))):
                    arcpy.AddMessage('\nThe following points have Inclination values outside the range 0-90:\n\nOID|Invalid Value\n')
                    for oid in oids:
                        arcpy.AddMessage(f'{oid}|{outside_range_inclination[oid]}')
                    if generateExcel:
                        current_rootName = ref_info.getRootName(fc)
                        arcpy.AddMessage("\nSaving to Excel file...")
                        if not exists(excel_path):
                            wb = Workbook()
                        else:
                            wb = load_workbook(excel_path,data_only=True)
                            for sheet in wb.sheetnames:
                                if f'{current_rootName}_Invalid_Inclinations' == sheet:
                                    wb.remove(wb[sheet])
                                    break
                        ws = wb.create_sheet(f'{current_rootName}_Invalid_Inclinations')
                        ws['A1'] = 'OID'
                        ws['B1'] = 'Invalid Value'
                        for n in range(num_oids):
                            ws[f'A{n+2}'] = str(oids[n])
                            ws[f'B{n+2}'] = outside_range_inclination[oids[n]]
                        if 'Sheet' in wb.sheetnames:
                            wb.remove(wb['Sheet'])
                        arcpy.AddMessage('Saving successful!\n')
                        wb.save(excel_path)
                        wb.close()
                        del current_rootName
                del outside_range_inclination
                if (num_oids := len((oids := tuple(not_matching_incl_label.keys())))):
                    arcpy.AddMessage('\nThe folowing points do not have matching Inclination and Label fields:\n\nOID|(Inclination Value,Label Value)\n')
                    for oid in oids:
                        arcpy.AddMessage(f'{oid}|({not_matching_incl_label[oid][0]},{not_matching_incl_label[oid][1]})')
                    if generateExcel:
                        current_rootName = ref_info.getRootName(fc)
                        arcpy.AddMessage('\nSaving to Excel file...')
                        if not exists(excel_path):
                            wb = Workbook()
                        else:
                            wb = load_workbook(excel_path,data_only=True)
                            for sheet in wb.sheetnames:
                                if f'{current_rootName}_Invalid_Labels' == sheet:
                                    wb.remove(wb[sheet])
                                    break
                        ws = wb.create_sheet(f'{current_rootName}_Invalid_Labels')
                        ws['A1'] = 'OID'
                        ws['B1'] = 'Inclination Value'
                        ws['C1'] = 'Label Value'
                        for n in range(num_oids):
                            ws[f'A{n+2}'] = str(oids[n])
                            ws[f'B{n+2}'] = not_matching_incl_label[oids[n]][0]
                            ws[f'C{n+2}'] = not_matching_incl_label[oids[n]][1]
                        if 'Sheet' in wb.sheetnames:
                            wb.remove(wb['Sheet'])
                        wb.save(excel_path)
                        wb.close()
                        arcpy.AddMessage("Save successful!\n")
                        del current_rootName
                del not_matching_incl_label ; del oids ; del ori_points ; del item ; del num_oids
                break

    arcpy.AddMessage("\nChecking if OrientationPoints and GenericPoints feature classes have the correct MapUnit indicated...")

    for dataset in datasets:
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point')):
            if fc.endswith('OrientationPoints') or fc.endswith('GenericPoints'):
                item = f'{dataset}/{fc}'
                mapunitpolys = None
                for fc_2 in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon')):
                    if fc_2.endswith('MapUnitPolys'):
                        mapunitpolys = fc_2[:]
                        break
                pnts_info = {row[0] : row[1] for row in arcpy.da.SearchCursor(item,('OID@','MapUnit'))}
                arcpy.management.MakeFeatureLayer((poly_item := f'{dataset}/{mapunitpolys}'),'temp_poly_lyr')
                del mapunitpolys
                mislabeled_mapunits = {}
                arcpy.management.MakeFeatureLayer(item,'temp_pnt_lyr')
                used_mapunits = {row[0] for row in arcpy.da.SearchCursor(poly_item,'MapUnit')}
                if None in used_mapunits:
                    used_mapunits.remove(None)
                del poly_item
                for used_mapunit in (used_mapunits := tuple(used_mapunits)):
                    selected_polys = arcpy.management.SelectLayerByAttribute('temp_poly_lyr','NEW_SELECTION',f"MapUnit = '{used_mapunit}'")
                    selected_pnts,redundant,count = arcpy.management.SelectLayerByLocation('temp_pnt_lyr','INTERSECT',selected_polys,'','NEW_SELECTION')
                    del redundant
                    if int(count):
                        for row_2 in arcpy.da.SearchCursor(selected_pnts,('OID@','MapUnit')):
                            if (claimed_mapunit := row_2[1]) != used_mapunit:
                                mislabeled_mapunits[row_2[0]] = (claimed_mapunit,used_mapunit)
                        del claimed_mapunit
                    del count ; del selected_pnts ; del selected_polys
                if (num_oids := len((oids := tuple(sorted(mislabeled_mapunits.keys()))))):
                    arcpy.AddMessage(f'{item}\nOID|Inputted MapUnit|Actual MapUnit\n')
                    for oid in oids:
                        arcpy.AddMessage(f'{oid}|{mislabeled_mapunits[oid][0]}|{mislabeled_mapunits[oid][1]}')
                    if generateExcel:
                        current_rootName = ref_info.getRootName(fc)
                        arcpy.AddMessage("\nSaving to Excel file...")
                        if not exists(excel_path):
                            wb = Workbook()
                        else:
                            wb = load_workbook(excel_path,data_only=True)
                            for sheet in wb.sheetnames:
                                if f'{current_rootName}_Potential_Incorrect_MUs' == sheet:
                                    wb.remove(wb[sheet])
                                    break
                        ws = wb.create_sheet(f'{current_rootName}_Potential_Incorrect_MUs')
                        del current_rootName
                        ws['A1'] = 'OID'
                        ws['B1'] = 'Inputted MapUnit'
                        ws['C1'] = 'Actual MapUnit'
                        for n in range(num_oids):
                            ws[f'A{n+2}'] = str(oids[n])
                            ws[f'B{n+2}'] = mislabeled_mapunits[oids[n]][0]
                            ws[f'C{n+2}'] = mislabeled_mapunits[oids[n]][1]
                        if 'Sheet' in wb.sheetnames:
                            wb.remove(wb['Sheet'])
                        wb.save(excel_path)
                        wb.close()
                        arcpy.AddMessage("Save successful!\n")
                del mislabeled_mapunits ; del oids ; del item ; del pnts_info ; del num_oids

    arcpy.AddMessage("\nChecking ContactsAndFaults and GeologicLines feature classes...")
    for dataset in datasets:
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polyline')):
            if fc.endswith('ContactsAndFaults') or fc.endswith('GeologicLines'):
                item = f'{dataset}/{fc}'
                feature_oids = []
                feature_labels = []
                for row in arcpy.da.SearchCursor(item,('OID@','Type','Label')):
                    if not None in (row[1],row[2]):
                        feature_oids.append(row[0])
                        feature_labels.append(row[2])
                labels_oids = {}
                used_labels = set()
                if len((feature_labels := tuple(feature_labels))):
                    for n in range(len((feature_oids := tuple(feature_oids)))):
                        if feature_labels[n] in used_labels:
                            labels_oids[feature_labels[n]].append(feature_oids[n])
                        else:
                            labels_oids[feature_labels[n]] = [feature_oids[n]]
                            used_labels.add(feature_labels[n])
                    for label in tuple(labels_oids.keys()):
                        temp_str = str(labels_oids[label][0])
                        for n in range(1,len(labels_oids[label])):
                            temp_str = f'{temp_str},{labels_oids[label][n]}'
                        labels_oids[label] = temp_str[:]
                    try: del temp_str
                    except NameError: pass
                    arcpy.AddMessage(f"\n{item}\nLabel|OIDs:")
                    for label in (labels := tuple(labels_oids.keys())):
                        arcpy.AddMessage(f'{label}|{labels_oids[label]}')
                    if generateExcel:
                        current_rootName = ref_info.getRootName(fc)
                        arcpy.AddMessage("\nSaving to Excel file...")
                        if not exists(excel_path):
                            wb = Workbook()
                        else:
                            wb = load_workbook(excel_path,data_only=True)
                            for sheet in wb.sheetnames:
                                if f'{current_rootName}_Used_Line_Labels' == sheet:
                                    wb.remove(wb[sheet])
                                    break
                        ws = wb.create_sheet(f'{current_rootName}_Used_Line_Labels')
                        del current_rootName
                        ws['A1'] = 'Label'
                        ws['B1'] = 'OIDs'
                        for n in range(len(labels)):
                            ws[f'A{n+2}'] = labels[n]
                            ws[f'B{n+2}'] = labels_oids[labels[n]]
                        if 'Sheet' in wb.sheetnames:
                            wb.remove(wb['Sheet'])
                        wb.save(excel_path)
                        wb.close()
                        arcpy.AddMessage("Save successful!\n")
                    del labels
                del used_labels ; del labels_oids ; del feature_labels ; del feature_oids ; del item

    dmu_mapunit_info = {row[0] : (row[1],row[2]) for row in arcpy.da.SearchCursor('DescriptionOfMapUnits',('MapUnit','Label','Symbol')) if not row[0] is None}
    dmu_mapunits = tuple(dmu_mapunit_info.keys())

    arcpy.AddMessage("\nChecking MapUnitPolys, MapUnitOverlayPolys, MapUnitLines, and MapUnitPoints feature classes...")
    for dataset in datasets:
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
            if fc.endswith('MapUnitPolys') or fc.endswith('MapUnitOverlayPolys') or fc.endswith('MapUnitLines') or fc.endswith('MapUnitPoints'):
                oids = []
                item = f'{dataset}/{fc}'
                for row in arcpy.da.SearchCursor(item,('OID@','MapUnit','Label','Symbol')):
                    if not row[1] is None:
                        if row[1] in dmu_mapunits:
                            if dmu_mapunit_info[row[1]][0] != row[2] and dmu_mapunit_info[row[1]][1] == row[3]:
                                oids.append(row[0])
                        else:
                            oids.append(row[0])
                if (num_oids := len((oids := tuple(oids)))):
                    arcpy.AddMessage(f"\nThe following polygons have MapUnit, Label, and/or Symbol not matching any corresponding fields in the DMU for {dataset}/{fc}:\n")
                    for oid in oids:
                        arcpy.AddMessage(str(oid))
                    if generateExcel:
                        current_rootName = ref_info.getRootName(fc)
                        arcpy.AddMessage('\nSaving to Excel file...')
                        if not exists(excel_path):
                            wb = Workbook()
                        else:
                            wb = load_workbook(excel_path,data_only=True)
                            for sheet in wb.sheetnames:
                                if f'{current_rootName}_Poly_Not_Matching_DMU' == sheet:
                                    wb.remove(wb[sheet])
                                    break
                        ws = wb.create_sheet(f'{current_rootName}_Poly_Not_Matching_DMU')
                        del current_rootName
                        ws['A1'] = 'OID'
                        for n in range(num_oids):
                            ws[f'A{n+2}'] = str(oids[n])
                        if 'Sheet' in wb.sheetnames:
                            wb.remove(wb['Sheet'])
                        wb.save(excel_path)
                        wb.close()
                        arcpy.AddMessage("Save successful!\n")
                del oids ; del item ; del num_oids

    del dmu_mapunit_info ; del dmu_mapunits

    if sys.argv[3] == 'true' and generateExcel:
        try:
            os.system(f'start excel.exe {excel_path}')
        except Exception:
            try:
                os.system(f'start EXCEL.EXE {excel_path}')
            except Exception:
                arcpy.AddError(f'\n\n\nERROR!\n\nEither Microsoft Excel was unconventionally installed on this machine, Microsoft Excel is not installed on this device, or something is preventing Python from opening {excel_path} in Microsoft Excel.')

    return None


autoreview_GeMS(gdb_path,excel_path)

