import arcpy,sys

# sys.argv[0] is reserved.
gdbs_str = sys.argv[1]

def multi_gdb_compact(gdbs_str : str) -> None:

    gdbs_str = gdbs_str.replace('\\','/')

    gdb_paths = []

    while ';' in gdbs_str:
        gdb_paths.append(gdbs_str[:gdbs_str.find(';')])
        gdbs_str = gdbs_str[gdbs_str.find(';')+1:]

    if gdbs_str != '':
        gdb_paths.append(gdbs_str)

    for gdb_path in (gdb_paths := tuple(gdb_paths)):
        try:
            arcpy.AddMessage(f'Compacting: {gdb_path}')
            arcpy.management.Compact(gdb_path)
            arcpy.AddMessage("Compacting successful.")
        except Exception:
            arcpy.AddWarning("Unable to compact geodatabase!")

    return None

multi_gdb_compact(gdbs_str)
