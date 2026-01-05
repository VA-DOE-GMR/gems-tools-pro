import arcpy
from string import punctuation,ascii_letters,digits
from array import array
from typing import Union

alphanum = set(f'{digits}{ascii_letters}')
double_puncts = tuple([punct * 2 for punct in array('u',tuple(punctuation))])

def default_env_parameters() -> None:
    """
    This sets optimal environment parameters.
    """

    # These stop ArcGIS Pro from logging everything being done as it can waste time.
    arcpy.SetLogHistory(False)
    arcpy.SetLogMetadata(False)

    # Automatic commits are not necessary.
    arcpy.env.autoCommit = 0

    arcpy.env.processorType = "CPU"
    arcpy.env.parallelProcessingFactor = "75%"
    arcpy.env.overwriteOutput = True

    return None

# Used to prevent issues with running tools with features already selected in
# ArcGIS Pro prior.
def deselectFeatures(datasets : tuple) -> None:

    for dataset in datasets:
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
            arcpy.management.SelectLayerByAttribute(f'{dataset}/{fc}','CLEAR_SELECTION')

    return None

# returning None indicates that is nothing of importance in that string.
def fixFieldItemString(entry_string : str) -> Union[str,None]:
    # No String entry should have consecutive spaces.
    while entry_string.find('  ') != -1:
        entry_string = entry_string.replace('  ',' ')
    # No String entry should be begin and/or end with a space.
    entry_string = entry_string.strip()
    # No String entry should have two or more consecutive punctuation/special
    # characters.
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


def explicit_typo_fix(item_path : str) -> None:
    '''This fixes all explicit typos present in all String/Text fields of
    feature classes and tables, excluding ones that should not be touched.
    '''

    # Annotations are highly contextual and cannot be modified via automation
    # with certainty.
    if item_path.endswith('Anno') or item_path[item_path.rfind('/')+1:].startswith('Anno'):
        return None

    excluded_fields = {'created_user','last_edited_user','GeoMaterial','Notes','Definition'}

    if len((fields := tuple([field.name for field in tuple(arcpy.ListFields(item_path,field_type='String')) if not field.name in excluded_fields and not field.name.endswith('_ID')]))):

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


def textEnforcing(entry_item : str) -> None:

    ref_name = entry_item[entry_item.find('/')+1:]

    if ref_name.isupper() or ref_name.islower():
        # Invalid Name Schema
        return None

    if ref_name.startswith('CS'):
        ref_name = ref_name[2:]
        while ref_name[0].isupper() and ref_name[1].isupper():
            ref_name = ref_name[1:]

    match ref_name:
        case 'CartographicLines':
            with arcpy.da.UpdateCursor(entry_item,('Symbol','DataSourceID')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].replace(' ','')) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].upper()) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'ContactsAndFaults' | 'GeologicLines' | 'MapUnitLines':
            with arcpy.da.UpdateCursor(entry_item,('isConcealed','ExistenceConfidence','IdentityConfidence','Symbol','DataSourceID','Notes')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].lower()) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].lower()) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if not row[2] is None:
                        if (new_str := row[2].lower()) != row[2]:
                            row[2] = new_str
                            update_row = True
                    if not row[3] is None:
                        if (new_str := row[3].replace(' ','')) != row[3]:
                            row[3] = new_str
                            update_row = True
                    if not row[4] is None:
                        if (new_str := row[4].upper()) != row[4]:
                            row[4] = new_str
                            update_row = True
                    if not row[5] is None:
                        new_str = row[5].strip()
                        while '  ' in new_str:
                            new_str = new_str.replace('  ',' ')
                        if new_str == '':
                            row[5] = None
                            update_row = True
                        elif new_str != row[5]:
                            row[5] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'DescriptionOfMapUnits':
            with arcpy.da.UpdateCursor(entry_item,('HierarchyKey','AreaFillRGB','DescriptionSourceID','GeoMaterialConfidence')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].replace(' ','')) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].replace(' ','')) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if not row[2] is None:
                        if (new_str := row[2].upper()) != row[2]:
                            row[2] = new_str
                            update_row = True
                    if not row[3] is None:
                        if (new_str := row[3].title()) != row[3]:
                            row[3] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'GenericPoints':
            with arcpy.da.UpdateCursor(entry_item,('Symbol','LocationSourceID','DataSourceID','Notes')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].replace(' ','')) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].upper()) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if not row[2] is None:
                        if (new_str := row[2].upper()) != row[2]:
                            row[2] = new_str
                            update_row = True
                    if not row[3] is None:
                        new_str = row[3].strip()
                        while '  ' in new_str:
                            new_str = new_str.replace('  ',' ')
                        if new_str == '':
                            row[3] = None
                            update_row = True
                        elif new_str != row[3]:
                            row[3] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'MapUnitPoints':
            with arcpy.da.UpdateCursor(entry_item,('ExistenceConfidence','IdentityConfidence','DataSourceID','Notes')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].lower()) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].lower()) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if not row[2] is None:
                        if (new_str := row[2].upper()) != row[2]:
                            row[2] = new_str
                            update_row = True
                    if not row[3] is None:
                        new_str = row[3].strip()
                        while '  ' in new_str:
                            new_str = new_str.replace('  ',' ')
                        if new_str == '':
                            row[3] = None
                            update_row = True
                        elif new_str != row[3]:
                            row[3] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'MapUnitOverlayPolys':
            with arcpy.da.UpdateCursor(entry_item,('IdentityConfidence','DataSourceID','Notes')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].lower()) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].upper()) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if not row[2] is None:
                        new_str = row[2].strip()
                        while '  ' in new_str:
                            new_str = new_str.replace('  ',' ')
                        if new_str == '':
                            row[2] = None
                            update_row = True
                        elif new_str != row[2]:
                            row[2] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'MapUnitPointsAnno' | 'MapUnitOverlayPolysAnno' | 'MapUnitPolysAnno' | 'OrientationPointsAnno':
            with arcpy.da.UpdateCursor(entry_item,('Angle',)) as cursor:
                for row in cursor:
                    if row[0] is None:
                        row[0] = 0
                        cursor.updateRow(row)
                    elif row[0] != 0:
                        row[0] = 0
                        cursor.updateRow(row)
        case 'MapUnitPolys' | 'OverlayPolys':
            with arcpy.da.UpdateCursor(entry_item,('IdentityConfidence','DataSourceID','Notes')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].lower()) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].upper()) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if not row[2] is None:
                        new_str = row[2].strip()
                        while '  ' in new_str:
                            new_str = new_str.replace('  ',' ')
                        if new_str == '':
                            row[2] = None
                            update_row = True
                        elif new_str != row[2]:
                            row[2] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'OrientationPoints':
            with arcpy.da.UpdateCursor(entry_item,('IdentityConfidence','LocationSourceID','OrientationSourceID','Notes')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].lower()) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].upper()) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if not row[2] is None:
                        if (new_str := row[2].upper()) != row[2]:
                            row[2] = new_str
                            update_row = True
                    if not row[3] is None:
                        new_str = row[3].strip()
                        while '  ' in new_str:
                            new_str = new_str.replace('  ',' ')
                        if new_str == '':
                            row[3] = None
                            update_row = True
                        elif new_str != row[3]:
                            row[3] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'Stations':
            with arcpy.da.UpdateCursor(entry_item,('FieldID','DataSourceID','Symbol','Notes')) as cursor:
                for row in cursor:
                    update_row = False
                    if not row[0] is None:
                        if (new_str := row[0].upper()) != row[0]:
                            row[0] = new_str
                            update_row = True
                    if not row[1] is None:
                        if (new_str := row[1].upper()) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if not row[2] is None:
                        if (new_str := row[2].replace(' ','')) != row[2]:
                            row[2] = new_str
                            update_row = True
                    if not row[3] is None:
                        new_str = row[3].strip()
                        while '  ' in new_str:
                            new_str = new_str.replace('  ',' ')
                        if new_str == '':
                            row[3] = None
                            update_row
                        elif new_str != row[3]:
                            row[3] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case _:
            pass

    return None


def enforceLabels(feature_item : str) -> None:

    ref_name = feature_item[feature_item.find('/')+1:]

    if ref_name.isupper() or ref_name.islower():
        # Invalid Name Schema
        return None

    if ref_name.startswith('CS'):
        ref_name = ref_name[2:]
        while ref_name[0].isupper() and ref_name[1].isupper():
            ref_name = ref_name[1:]

    match ref_name:
        case 'MapUnitLines':
            mapunit_dict = {}
            label_dict = {}
            with arcpy.da.SearchCursor('DescriptionOfMapUnits',('MapUnit','Label')) as cursor:
                for row in cursor:
                    if not row[0] is None and not row[1] is None:
                        mapunit_dict[row[0]] = row[1]
                        label_dict[row[1]] = row[0]
            mapunit_keys = set(mapunit_dict.keys())
            label_keys = set(label_dict.keys())
            with arcpy.da.UpdateCursor(feature_item,('MapUnit','Label')) as cursor:
                for row in cursor:
                    update_row = False
                    if row[0] in mapunit_keys:
                        if (new_str := mapunit_dict[row[0]]) != row[1]:
                            row[1] = new_str
                            update_row = True
                    elif row[1] in label_keys:
                        row[0] = label_dict[row[1]]
                        update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'MapUnitOverlayPolys' | 'MapUnitPolys':
            mapunit_dict = {}
            label_dict = {}
            symbol_dict = {}
            with arcpy.da.SearchCursor('DescriptionOfMapUnits',('MapUnit','Label','Symbol')) as cursor:
                for row in cursor:
                    if not row[0] is None and not row[1] is None and not row[2] is None:
                        mapunit_dict[row[0]] = (row[1],row[2])
                        label_dict[row[1]] = (row[0],row[2])
                        symbol_dict[row[2]] = (row[0],row[1])
            mapunit_keys = set(mapunit_dict.keys())
            label_keys = set(label_dict.keys())
            symbol_keys = set(symbol_dict.keys())
            with arcpy.da.UpdateCursor(feature_item,('MapUnit','Label','Symbol')) as cursor:
                for row in cursor:
                    update_row = False
                    if row[0] in mapunit_keys:
                        if (new_str := mapunit_dict[row[0]][0]) != row[1]:
                            row[1] = new_str
                            update_row = True
                        if (new_str := mapunit_dict[row[0]][1]) != row[2]:
                            row[2] = new_str
                            update_row = True
                    elif row[1] in label_keys:
                        if (new_str := label_dict[row[1]][0]) != row[0]:
                            row[0] = new_str
                            update_row = True
                        if (new_str := label_dict[row[1]][1]) != row[2]:
                            row[2] = new_str
                            update_row = True
                    elif row[2] in symbol_keys:
                        if (new_str := symbol_dict[row[2]][0]) != row[0]:
                            row[0] = new_str
                            update_row = True
                        if (new_str := symbol_dict[row[2]][1]) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)
        case 'MapUnitPoints':
            mapunit_dict = {}
            label_dict = {}
            symbol_dict = {}
            with arcpy.da.SearchCursor('DescriptionOfMapUnits',('MapUnit','Label','Symbol')) as cursor:
                for row in cursor:
                    if not row[0] is None and not row[1] is None and row[2] is None:
                        mapunit_dict[row[0]] = (row[1],row[2])
                        label_dict[row[1]] = (row[0],row[2])
                        symbol_dict[row[2]] = (row[0],row[1])
            mapunit_keys = set(mapunit_dict.keys())
            label_keys = set(label_dict.keys())
            symbol_keys = set(symbol_dict.keys())
            with arcpy.da.UpdateCursor(feature_item,('MapUnit','Label','Symbol')) as cursor:
                for row in cursor:
                    update_row = False
                    if row[0] in mapunit_keys:
                        if (new_str := mapunit_dict[row[0]][0]) != row[1]:
                            row[1] = new_str
                            update_row = True
                        if (new_str := mapunit_dict[row[0]][1]) != row[2]:
                            row[2] = new_str
                            update_row = True
                    elif row[1] in label_keys:
                        if (new_str := label_dict[row[1]][0]) != row[0]:
                            row[0] = new_str
                            update_row = True
                        if (new_str := label_dict[row[1]][1]) != row[2]:
                            row[2] = new_str
                            update_row = True
                    elif row[2] in symbol_keys:
                        if (new_str := symbol_dict[row[2]][0]) != row[0]:
                            row[0] = new_str
                            update_row = True
                        if (new_str := symbol_dict[row[2]][1]) != row[1]:
                            row[1] = new_str
                            update_row = True
                    if update_row:
                        cursor.updateRow(row)

        case 'OrientationPoints':
            with arcpy.da.UpdateCursor(feature_item,('Inclination','Symbol','Label','Type')) as cursor:
                for row in cursor:
                    update_row = False
                    if row[1] == 'hidden':
                        if not row[2] is None:
                            row[2] = None
                            update_row = True
                    elif not row[3] is None:
                        if row[3].startswith('horizontal'):
                            if not row[2] is None:
                                row[2] = None:
                                update_row = True
                            if row[0] != 0:
                                row[0] = 0:
                                update_row = True
                        elif row[3].startswith('vertical'):
                            if not row[2] is None:
                                row[2] = None
                                update_row = True
                            if row[0] != 90:
                                row[0] = 90
                                update_row = True
                        elif not row[0] is None:
                            try:
                                if (new_str := str(int(row[0]))) != row[2]:
                                    row[2] = new_str
                                    update_row = True
                            except ValueError:
                                pass
                        elif not row[2] is None:
                            try:
                                row[0] = int(row[2])
                                update_row = True
                            except ValueError:
                                pass
                    elif not row[0] is None:
                        if int(row[0]) >= 0:
                            try:
                                if (new_str := str(int(row[0]))) != row[2]:
                                    row[2] = new_str
                                    update_row = True
                            except ValueError:
                                pass
                        elif not row[2] is None:
                            row[2] = None
                            update_row = True
                    elif not row[2] is None:
                        try:
                            row[0] = int(row[0])
                            update_row = True
                        except ValueError:
                            pass
                    if update_row:
                        cursor.updateRow(row)
        case _:
            pass

    return None
