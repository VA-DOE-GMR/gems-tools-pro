import arcpy

def default_env_parameters():

    from subprocess import check_output as c_o

    #arcpy.SetLogHistory(False)
    #arcpy.SetLogMetadata(False)

    try:
        c_o('nvidia-smi')
        arcpy.env.processorType = "GPU"
    except Exception:
        arcpy.env.processorType = "CPU"

    arcpy.parallelProcessingFactor = "50%"
    arcpy.overwriteOutput = True
