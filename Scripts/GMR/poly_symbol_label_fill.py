import arcpy
import gc
from misc_arcpy_ops import default_env_parameters
import sys

gdb_path = sys.argv[1]

def fill_symbol_label_poly_field(gdb_path : str):
    """
    This autofills Symbol and Label fields for polygon feature classes.
    """

    try:
        current_workspace = arcpy.env.workspace[:]
        current_workspace = current_workspace.replace('\\','/')
    except Exception:
        pass

    arcpy.env.workspace = gdb_path.replace('\\','/')

    default_env_parameters()

    # This is to prevent Error #160250 randomly from occurring.
    edit = arcpy.da.Editor()
    edit.startEditing(with_undo=False,multiuser_mode=False)
    edit.startOperation()

    symbol_mapunits = []
    label_mapunits = []
    mapunit_symbol = dict()
    mapunit_label = dict()

    arcpy.AddMessage("Obtaining Label and Symbol information from DescriptionOfMapUnits table...")

    for row in arcpy.da.SearchCursor('DescriptionOfMapUnits',['MapUnit','Label','Symbol']):
        if not None in (row[0],row[1]) and not row[0] in frozenset(mapunit_label.keys()):
            mapunit_label[row[0]] = row[1]
        if not None in (row[0],row[2]) and not row[0] in frozenset(mapunit_symbol.keys()):
            mapunit_symbol[row[0]] = row[2]

    symbol_mapunits = frozenset(mapunit_symbol.keys())
    label_mapunits = frozenset(mapunit_label.keys())

    arcpy.AddMessage("Information successfully obtained.\n\nIterating through dataset(s) in geodatabase and filling out Label and Symbol fields for polygon feature classes in geodatabase...")

    for dataset in tuple(arcpy.ListDatasets()):
        poly_fcs = []
        for fc in tuple(arcpy.ListFeatureClasses(feature_type="Polygon",feature_dataset=dataset)):
            fields = frozenset([field.name for field in arcpy.ListFields(f'{dataset}/{fc}',field_type='String')])
            if 'MapUnit' in fields and 'Label' in fields and 'Symbol' in fields:
                poly_fcs.append(fc)
        for fc in tuple(poly_fcs):
            with arcpy.da.UpdateCursor(f'{dataset}/{fc}',['MapUnit','Label','Symbol']) as cursor:
                for row in cursor:
                    if row[0] in label_mapunits:
                        row[1] = mapunit_label[row[0]]
                    if row[0] in symbol_mapunits:
                        row[2] = mapunit_symbol[row[0]]
                    cursor.updateRow(row)

    arcpy.AddMessage("Changes successfully applied.\n\nSaving edits...")

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


fill_symbol_label_poly_field(gdb_path)
