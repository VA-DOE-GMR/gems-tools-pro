import sys
import arcpy
import pandas
import SDE_setup



def main(table):
    """
    Check database glossary against GMR glossary.
    """

    # access GMR glossary as dataframe
    config = SDE_setup.load_config()
    df_GMR = SDE_setup.table_to_dataframe(config,'Glossary_table')

    # change workspace back to input
    arcpy.env.workspace = table

    # turn the Glossary table into df
    columns = [f.name for f in arcpy.ListFields(table)]
    df_gdb = pandas.DataFrame(data=arcpy.da.SearchCursor(table,columns),columns=columns)

    # check Term
    df_gdb['exists'] = df_gdb['Term'].isin(df_GMR['Term'])

    arcpy.AddMessage(f"The following term(s) were not found in the GMR glossary:\n"
                     f"{df_gdb['Term'].loc[df_gdb['exists'] == False]}"
                    )
    
    # check Definition
    df_gdb['correct_definition'] = df_gdb['Definition'].isin(df_GMR['Definition'])

    arcpy.AddMessage(f"\nDefinition(s) for the following term(s) were not found in the GMR glossary:\n"
                     f"{df_gdb[['Term','Definition']].loc[df_gdb['correct_definition'] == False]}"
                    )
    
    # check Citation
    df_merge = df_gdb.merge(df_GMR,how='left',on='Term')
    df_citations = df_merge.query('DefinitionSourceID_x != DefinitionSourceID_y')
    df_citations = df_citations.rename(columns={'DefinitionSourceID_x':'Geodatabase','DefinitionSourceID_y':'GMR Glossary'})
    arcpy.AddMessage(f"\nData Source(s) for the following term(s) were not found in the GMR glossary:\n"
                     f"{df_citations[['Term','Geodatabase','GMR Glossary']]}"
                    )
    
if __name__ == "__main__":
    table = arcpy.GetParameterAsText(0)
    main(table)