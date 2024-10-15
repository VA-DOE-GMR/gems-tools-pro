import arcpy

def default_env_parameters() -> None:
    """
    This sets optimal environment parameters.
    """

    from subprocess import check_output as c_o

    #arcpy.SetLogHistory(False)
    #arcpy.SetLogMetadata(False)

    try:
        c_o('nvidia-smi')
        arcpy.env.processorType = "GPU"
    except Exception:
        arcpy.env.processorType = "CPU"
        arcpy.env.parallelProcessingFactor = "50%"
    arcpy.env.overwriteOutput = True

    return None

def explicit_typo_fix(item_path : str) -> None:
    '''This fixes all explicit typos present in all String/Text fields of
    feature classes and tables, excluding ones that should not be touched.
    '''

    excluded_fields = {'created_user','last_edited_user','GeoMaterial','Notes','Definition'}

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
