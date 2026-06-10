import arcpy,sys
from misc_arcpy_ops import default_env_parameters

gdb_path = sys.argv[1]


def metadataOverviewDescriptor(gdb_path : str) -> None:

    current_workspace = arcpy.env.workspace[:]
    current_workspace = current_workspace.replace('\\','/')
    arcpy.env.workspace = gdb_path.replace('\\','/')

    default_env_parameters()

    arcpy.AddMessage(f"{arcpy.env.workspace[arcpy.env.workspace.rfind('/')+1:]} contains the following elements:")

    for table in tuple(sorted(arcpy.ListTables())):
        counter = 0
        for row in arcpy.da.SearchCursor(table,'OID@'):
            counter += 1
        arcpy.AddMessage(f"{table}, nonspatial table, {counter} rows")

    for dataset in tuple(sorted(arcpy.ListDatasets())):
        arcpy.AddMessage(f"{dataset}, feature dataset")
        for fc in tuple(sorted(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Annotation'))):
            counter = 0
            for row in arcpy.da.SearchCursor(f'{dataset}/{fc}','OID@'):
                counter += 1
            arcpy.AddMessage(f"{fc}, annotation polygon feature class, {counter} rows")
        for fc in tuple(sorted(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Point'))):
            counter = 0
            for row in arcpy.da.SearchCursor(f'{dataset}/{fc}','OID@'):
                counter += 1
            arcpy.AddMessage(f"{fc}, simple point feature class, {counter} rows")
        for fc in tuple(sorted(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Line'))):
            counter = 0
            for row in arcpy.da.SearchCursor(f'{dataset}/{fc}','OID@'):
                counter += 1
            arcpy.AddMessage(f"{fc}, simple polyline feature class, {counter} rows")
        for fc in tuple(sorted(arcpy.ListFeatureClasses(feature_dataset=dataset,feature_type='Polygon'))):
            counter = 0
            for row in arcpy.da.SearchCursor(f'{dataset}/{fc}','OID@'):
                counter += 1
            arcpy.AddMessage(f"{fc}, simple polygon feature class, {counter} rows")

    arcpy.env.workspace = current_workspace[:]

    return None


metadataOverviewDescriptor(gdb_path)
