import arcpy, os

valid_pixel_types = ["1_BIT", "2_BIT", "4_BIT", "8_BIT_UNSIGNED", "8_BIT_SIGNED", "16_BIT_UNSIGNED", "16_BIT_SIGNED", 
"32_BIT_UNSIGNED", "32_BIT_SIGNED", "32_BIT_FLOAT", "64_BIT"]

def removeIfExists(path, msg, messages):
    if arcpy.Exists(path):
        arcpy.Delete_management(path)
        messages.addMessage(msg)

def execute_copy(parameters, messages, date_folder):
    in_path = parameters[0].valueAsText
    dot_index = in_path.rfind(".")
    slash_index = in_path.rfind("\\")
    out_path_les = in_path[0:slash_index + 1] + "Analysis\\" + date_folder + in_path[slash_index:dot_index] + "_lescopy" + in_path[dot_index:]
    out_path_pole = in_path[0:slash_index + 1] + "Analysis\\" + date_folder + in_path[slash_index:dot_index] + "_polecopy" + in_path[dot_index:]

    removeIfExists(out_path_les, "old files for les removed", messages)
    arcpy.Copy_management(in_path, out_path_les)
    messages.addMessage("copied les successfully")

    removeIfExists(out_path_pole, "old files for pole removed", messages)
    arcpy.Copy_management(in_path, out_path_pole)
    messages.addMessage("copied pole successfully")
    return (in_path, out_path_les, out_path_pole)

def execute_changefield(out_path_les, out_path_pole, needs_calc, parameters, messages):
    arcpy.management.CalculateField(out_path_les, "Date_", '"{date}"'.format(date = parameters[1].valueAsText))
    arcpy.management.CalculateField(out_path_pole, "Date_", '"{date}"'.format(date = parameters[1].valueAsText))
    messages.addMessage("date fields changed successfully")

    if needs_calc:
        arcpy.management.CalculateField(out_path_les, "has_snow", "0")
        arcpy.management.CalculateField(out_path_pole, "has_snow", "0")
        messages.addMessage("has_snow fields changed successfully")

    arcpy.management.CalculateField(out_path_les, "Merge2", '!Merge!+"_"+!Date_!', expression_type="PYTHON_9.3")
    arcpy.management.CalculateField(out_path_pole, "Merge2", '!Merge!+"_"+!Date_!', expression_type="PYTHON_9.3")
    messages.addMessage("merge2 fields changed successfully")

def execute_join_calc(in_path, out_path_les, out_path_pole, date_folder, needs_calc, messages):
    in_path_converted = in_path.replace('\\', "/")
    slash_index = in_path_converted.rfind("/")
    les_temp_layer = "les_layer"
    pole_temp_layer = "pole_layer"
    les_layer = in_path_converted[0:slash_index + 1] + "Analysis/" + date_folder + "/les.lyr"
    pole_layer = in_path_converted[0:slash_index + 1] + "Analysis/" + date_folder + "/pole.lyr"

    removeIfExists(les_temp_layer, "old temp layer for les removed", messages)
    removeIfExists(les_layer, "old layer for les removed", messages)
    arcpy.MakeFeatureLayer_management(out_path_les, les_temp_layer)
    arcpy.AddJoin_management(les_temp_layer, "Merge2", in_path_converted[0:slash_index + 1] + "les_group.dbf", "MERGE")

    if needs_calc:
        arcpy.SelectLayerByAttribute_management(les_temp_layer, where_clause='"les_group.SPROC">=50')
        arcpy.management.CalculateField(les_temp_layer, "has_snow", "1")
        arcpy.SelectLayerByAttribute_management(les_temp_layer, selection_type="CLEAR_SELECTION")

    arcpy.management.SaveToLayerFile(les_temp_layer, les_layer)
    messages.addMessage("joined les succcessfully")

    removeIfExists(pole_temp_layer, "old temp layer for pole removed", messages)
    removeIfExists(pole_layer, "old layer for pole removed", messages)
    arcpy.MakeFeatureLayer_management(out_path_pole, pole_temp_layer)
    arcpy.AddJoin_management(pole_temp_layer, "Merge2", in_path_converted[0:slash_index + 1] + "pole_group.dbf", "MERGE")

    if needs_calc:
        arcpy.SelectLayerByAttribute_management(pole_temp_layer, where_clause='"pole_group.SPROC">=50')
        arcpy.management.CalculateField(pole_temp_layer, "has_snow", "1")
        arcpy.SelectLayerByAttribute_management(pole_temp_layer, selection_type="CLEAR_SELECTION")

    arcpy.management.SaveToLayerFile(pole_temp_layer, pole_layer)
    messages.addMessage("joined pole succcessfully")

    arcpy.Delete_management(pole_temp_layer)
    return (les_layer, pole_layer)

def execute_raster(les_layer, pole_layer, date_folder, rasters, parameters, messages):
    date = parameters[1].valueAsText
    size = parameters[2].value
    in_path_converted = parameters[0].valueAsText.replace('\\', "/")
    slash_index = in_path_converted.rfind("/")
    table_name = in_path_converted[slash_index + 1:][:-4]
    folder = in_path_converted[0:slash_index + 1] + "Analysis/" + date_folder + "/"
    px_type = parameters[3].valueAsText

    for raster in rasters:
        if not arcpy.Exists(folder + "/{0}".format(raster)): arcpy.CreateFolder_management(folder, raster)
        les_raster = folder + "/{0}".format(raster) + "/les_" + date.replace(".", "")
        removeIfExists(les_raster, "old les raster for {0} removed".format(raster), messages)
        arcpy.conversion.PointToRaster(les_layer, (table_name + "_lescopy." if raster == "has_snow" else "les_group.")
        + raster, les_raster, "MOST_FREQUENT", "NONE", size)
        messages.addMessage("created {0} raster for les successfully".format(raster))

        pole_raster = folder + "/{0}".format(raster) + "/pole_" + date.replace(".", "")
        removeIfExists(pole_raster, "old pole raster for {0} removed".format(raster), messages)
        arcpy.conversion.PointToRaster(pole_layer, (table_name + "_polecopy." if raster == "has_snow" else "pole_group.")
        + raster, pole_raster, "MOST_FREQUENT", "NONE", size)
        messages.addMessage("created {0} raster for pole successfully".format(raster))

        final_raster = "fin_" + date.replace(".", "")
        input_rasters = [les_raster, pole_raster]
        removeIfExists(folder + "/{0}/".format(raster) + final_raster, "old final raster for {0} removed".format(raster), messages)
        arcpy.MosaicToNewRaster_management(input_rasters, folder + "/{0}".format(raster), final_raster, pixel_type = px_type, number_of_bands = 1,
        mosaic_method="SUM")
        messages.addMessage("created final raster for {0} successfully".format(raster))

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "SnowMeltVis"
        self.alias = "SnowMeltVis"

        # List of tool classes associated with this toolbox
        self.tools = [SnowMeltAnalysis]


class SnowMeltAnalysis(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "SnowMelt analysis"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
			displayName="Source file with points",
			name="srcFile",
			datatype="DEType",
			parameterType="Required",
			direction="Input"
        )
        param1 = arcpy.Parameter(
			displayName="Calculation date",
			name="calcDate",
			datatype="GPDate",
			parameterType="Required",
			direction="Input"
        )
        param2 = arcpy.Parameter(
			displayName="Cell size",
			name="cellSize",
			datatype="analysis_cell_size",
			parameterType="Required",
			direction="Input"
        )
        param3 = arcpy.Parameter(
			displayName="Pixel type",
			name="pxType",
			datatype="GPString",
			parameterType="Required",
			direction="Input",
        )
        param4 = arcpy.Parameter(
			displayName="Build raster by",
			name="buildType",
			datatype="GPString",
			parameterType="Required",
			direction="Input",
            multiValue=True
        )

        param3.filter.type = "ValueList"
        param3.filter.list = valid_pixel_types
        
        param4.filter.type = "ValueList"
        param4.filter.list = ["has_snow", "h", "ds"]

        params = [param0, param1, param2, param3, param4]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        in_path = parameters[0].valueAsText
        if in_path[-4:] != ".shp": parameters[0].setErrorMessage("Input file should have a .shp extension")
        else: parameters[0].clearMessage()

        px_type = parameters[3].valueAsText
        if px_type not in valid_pixel_types: parameters[3].setErrorMessage("Invalid pixel type")
        else: parameters[3].clearMessage()
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        path = parameters[0].valueAsText.replace("\\", "/")
        slash_index = path.rfind("/")
        folder_path = path[0:slash_index + 1] + "Analysis"
        date_folder = parameters[1].valueAsText.replace(".", "")
        if not arcpy.Exists(folder_path): arcpy.CreateFolder_management(path[0:slash_index + 1], "Analysis")
        if not arcpy.Exists(folder_path + "\\" + date_folder): arcpy.CreateFolder_management(folder_path, date_folder)
        rasters = str(parameters[4].value).split(';')

        try: in_path, out_path_les, out_path_pole = execute_copy(parameters, messages, date_folder)
        except Exception as e:
            messages.addErrorMessage("failed to copy, error message: " + str(e))
            return
            
        try: execute_changefield(out_path_les, out_path_pole, "has_snow" in rasters, parameters, messages)
        except Exception as e:
            messages.addErrorMessage("failed to change fields, error message: " + str(e))
            return

        try: les_layer, pole_layer = execute_join_calc(in_path, out_path_les, out_path_pole, date_folder, "has_snow" in rasters, messages)
        except Exception as e:
            messages.addErrorMessage("failed to join tables or calculate has_snow field, error message: " + str(e))
            return
        
        try: execute_raster(les_layer, pole_layer, date_folder, rasters, parameters, messages)
        except Exception as e:
            messages.addErrorMessage("failed to build rasters from data, error message: " + str(e))
            return
        return
