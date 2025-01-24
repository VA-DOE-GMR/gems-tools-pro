import json
import arcpy
import sys
import pandas


def load_config():
    """
    Load configuration from a JSON file.
    """
    config_path = r"\\energyfiles\dgmr\PROJECTS\MAPPING\GuidanceDocs\GeMS\gems-tools-pro-GMR\config_alt.json"
    with open(config_path, "r") as config_file:
        config = json.load(config_file)
    return config

# def connect_to_SDE(config):
#     """
#     Validate SDE connection.
#     """
#     connection_file = config['connection_file']
#     if arcpy.Exists(connection_file):
#         return connection_file
#     else:
#         raise FileNotFoundError(f'Connection file does not exist or is inaccessible: {connection_file}')
    
def table_to_dataframe(config,table_name):
    """
    Convert SDE to pandas dataframe.
    """
    table = config['tables'][table_name]
    arcpy.env.workspace = config["connection_file"]
    
    # Make a view of the table from SDE
    try:
        table_view = "view_of_table"
        if arcpy.Exists(table_view):
            arcpy.Delete_management(table_view)
        SDE_table = arcpy.MakeTableView_management(table,table_view)
        arcpy.AddMessage("Successfully connected to SDE.")

    except Exception:
        arcpy.AddMessage("Failed to access connection string and connect to SDE. See below error.")
        e = sys.exc_info()[1]
        arcpy.AddError(e.args[0])
        exit()

    # Turn the view into a dataframe
    columns = [f.name for f in arcpy.ListFields(SDE_table)]
    df_GMR = pandas.DataFrame(data=arcpy.da.SearchCursor(SDE_table,columns),columns=columns)

    # Delete the table view
    arcpy.Delete_management(SDE_table)
    
    return df_GMR