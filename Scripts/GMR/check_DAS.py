import sys
import arcpy
import pandas


def main(db,table):
    """
    Check database DAS table against master DAS
    """
    GMR_DAS = r"Z:\PROJECTS\MAPPING\Maps\StateGeoMap_2020\Deliverables_USE_THIS\VAStateGeologicMap-publication\VAStateGeologicMap-database\VAStateGeologicMap.gdb\DataSources"

    arcpy.env.workspace = db
    
    # turn Master DAS into df
    columns = [f.name for f in arcpy.ListFields(GMR_DAS)]
    df_GMR = pandas.DataFrame(data=arcpy.da.SearchCursor(GMR_DAS,columns),columns=columns)
    
    # turn gdb DAS into df
    columns = [f.name for f in arcpy.ListFields(table)]
    df_gdb = pandas.DataFrame(data=arcpy.da.SearchCursor(table,columns),columns=columns)

    # Find table records not identical to Master DAS
    df_merge = pandas.merge(df_gdb,df_GMR, on=['Source','DataSources_ID'],how='left',indicator='exists')
    df_merge['exists'] = df_merge['exists'].map(lambda x: x == 'both')
    df_filter = df_merge[df_merge['exists'] == False]

    arcpy.AddMessage(f"Source(s) not matching the GMR Master DAS table:\n"
                     f"{df_filter[['DataSources_ID','Source']]}\n"
                     f"Check these records and run again.")

if __name__ == "__main__":
    db = arcpy.GetParameterAsText(0)
    table = arcpy.GetParameterAsText(1)
    main(db,table)