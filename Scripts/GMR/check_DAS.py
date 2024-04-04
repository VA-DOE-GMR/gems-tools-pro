import json
import arcpy
import pandas
import sys
import os

def main(db_table):
    """
    Check database DAS table against master DAS
    """

    config_path = r"Z:\PROJECTS\MAPPING\GuidanceDocs\GeMS\gems-tools-pro-GMR"
    config_name = "config.json"
    with open(os.path.join(config_path,config_name), "r") as config_file:
        config = json.load(config_file)

    try:      
        arcpy.env.workspace = os.path.join(config_path,'SDE_connection.sde')
        GMR_DAS = config['table']
        GMR_DAS = arcpy.MakeTableView_management(GMR_DAS, "view_of_table")
        arcpy.AddMessage("Successfully connected to Master Data Sources table")

    except Exception:
        arcpy.AddMessage("Failed to access connection string and connect to SDE. See below error")
        e = sys.exc_info()[1]
        arcpy.AddError(e.args[0])
        exit()

    # turn Master DAS into df
    columns = [f.name for f in arcpy.ListFields(GMR_DAS)]
    df_GMR = pandas.DataFrame(data=arcpy.da.SearchCursor(GMR_DAS,columns),columns=columns)
    
    arcpy.env.workspace = db_table
    # turn gdb DAS into df
    columns = [f.name for f in arcpy.ListFields(db_table)]
    df_gdb = pandas.DataFrame(data=arcpy.da.SearchCursor(db_table,columns),columns=columns)

    # Find table records not identical to Master DAS
    df_merge = pandas.merge(df_gdb,df_GMR, on=['Source','DataSources_ID'],how='left',indicator='exists')
    df_merge['exists'] = df_merge['exists'].map(lambda x: x == 'both')
    df_filter = df_merge[df_merge['exists'] == False]

    arcpy.AddMessage(f"Source(s) not matching the GMR Master DAS table:\n"
                     f"{df_filter[['DataSources_ID','Source']]}\n"
                     f"Check these records and run again.")

if __name__ == "__main__":
    db_table = arcpy.GetParameterAsText(0)
    main(db_table)