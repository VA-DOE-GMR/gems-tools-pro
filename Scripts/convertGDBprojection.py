import arcpy,sys
from os import remove
from os.path import exists
from misc_arcpy_ops import default_env_parameters,deselectObjects

# sys.argv[0] is reserved
gdb_path = sys.argv[1]
neo_gdb_location = sys.argv[3]
neo_gdb_name = sys.argv[4]
neo_spatial_reference = sys.argv[5]
transformation_method = sys.argv[6]
if sys.argv[7] == 'true':
    add_vertices = True
else:
    add_vertices = False

def generateNewGDBProject(gdb_path : str, neo_gdb_location : str, neo_gdb_name : str, neo_spatial_reference, transformation_method : str, add_vertices : bool) -> None:

    default_env_parameters()

    current_workspace = arcpy.env.workspace[:]
    arcpy.env.workspace = gdb_path[:]

    # This ensures that no features are selected before running the tool.
    # Selected features will disrupt how this tool functions. It will not cause
    # any errors or abnormal behavior; however, it will cause certain things to
    # be skipped or completely ignored by the tool.
    deselectObjects((datasets := tuple([item for item in arcpy.ListDatasets() if item == 'GeologicMap' or 'CrossSection' in item])))

    tables = tuple(arcpy.ListTables())

    arcpy.AddMessage(f"Creating new geodatabase named '{neo_gdb_name}' at: {neo_gdb_location}...")
    arcpy.management.CreateFileGDB(neo_gdb_location,neo_gdb_name,'CURRENT')
    arcpy.AddMessage("Geodatabase successfully created.")

    neo_gdb_path = f'{neo_gdb_location}/{neo_gdb_name}.gdb'

    for table in tables:
        arcpy.AddMessage(f"Copying {table} non-spatial table to new geodatabase...")
        arcpy.management.Copy(f'{gdb_path}/{table}',f'{neo_gdb_path}/{table}')

    if len(tables):
        arcpy.AddMessage("Non-spatial tables successfully copied to new geodatabase.")

    del tables

    for dataset in datasets:
        arcpy.AddMessage(f"Creating {dataset} dataset with new projection...")
        arcpy.management.CreateFeatureDataset(neo_gdb_path,dataset,neo_spatial_reference)
        arcpy.AddMessage(f"{dataset} dataset generated.")
        src_dataset_path = f'{arcpy.env.workspace}/{dataset}'
        dest_dataset_path = f'{neo_gdb_path}/{dataset}'
        for fc in tuple(arcpy.ListFeatureClasses(feature_dataset=dataset)):
            arcpy.AddMessage(f"Projecting and copying {fc}...")
            arcpy.management.Project(f'{src_dataset_path}/{fc}',f'{dest_dataset_path}/{fc}',neo_spatial_reference,transform_method=transformation_method,preserve_shape=add_vertices)

    arcpy.AddMessage("Geodatabase with new projection successfully generated.")

    arcpy.env.workspace = current_workspace[:]

    if exists('temp_str_12345.txt'):
        try:
            remove('temp_str_12345.txt')
        except Exception:
            pass

    return None


generateNewGDBProject(gdb_path,neo_gdb_location,neo_gdb_name,neo_spatial_reference,transformation_method,add_vertices)
