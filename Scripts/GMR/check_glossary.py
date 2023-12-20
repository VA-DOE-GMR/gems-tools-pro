import sys
import arcpy
import pandas

def main(db,table):
    """
    Check database glossary against GMR glossary
    """
    GMR_glossary = ".\Complete Glossary For GeMS.xlsx"

    arcpy.env.workspace = db

    df_GMR = pandas.read_excel(GMR_glossary, "CompleteGlossary")
    # tables = arcpy.ListTables('Glossary')

    # turn the Glossary table into df
    columns = [f.name for f in arcpy.ListFields(table)]

    df_gdb = pandas.DataFrame(data=arcpy.da.SearchCursor(table,columns),columns=columns)

    # check Term
    df_gdb['exists'] = df_gdb['Term'].isin(df_GMR["Term"])

    arcpy.AddMessage(f"The following term(s) were not found in the GMR glossary:\n"
                     f"{df_gdb['Term'].loc[df_gdb['exists'] == False]}"
                    )
    
    # check Definition
    df_gdb['correct_definition'] = df_gdb['Definition'].isin(df_GMR['Definition'])

    arcpy.AddMessage(f"Definition(s) for the following term(s) were not found in the GMR glossary:\n"
                     f"{df_gdb[['Term','Definition']].loc[df_gdb['correct_definition'] == False]}"
                    )
    
    # check Citation
    df_merge = df_gdb.merge(df_GMR,how='left',on='Term')
    df_citations = df_merge.query('DefinitionSourceID_x != DefinitionSourceID_y')
    arcpy.AddMessage(f"Citation(s) for the following term(s) were not found in the GMR glossary:\n"
                     f"{df_citations[['Term','DefinitionSourceID_x','DefinitionSourceID_y']]}"
                    )
    
if __name__ == "__main__":
    db = arcpy.GetParameterAsText(0)
    table = arcpy.GetParameterAsText(1)
    main(db,table)