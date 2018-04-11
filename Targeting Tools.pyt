"""
    Name:       Targeting Tools

    Authors:    International Center for Tropical Agriculture - CIAT
                Commonwealth Scientific and Industrial Research Organisation - CSIRO

    Notes:      Tool-1: Identify land suitable to cultivate a certain crop.
                Tool-2: Calculate statistics from the land suitability output raster
                        and return the result in a dbf file format.
                Tool-3: Identify areas that have similar biophysical characteristics to
                        the location currently under a certain type crop.
                Fully tested in ArcGIS 10.1.
                Requires Spatial Analyst extension

    Created:    May 2015
    Modified:   November 2015
"""

import os, sys, csv, re, time, arcpy, shutil, ntpath, subprocess, traceback
from itertools import *

arcpy.env.overwriteOutput = True


def parameter(displayName, name, datatype, parameterType='Required', direction='Input', multiValue=False):
    param = arcpy.Parameter(
        displayName=displayName,
        name=name,
        datatype=datatype,
        parameterType=parameterType,
        direction=direction,
        multiValue=multiValue)
    return param


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the .pyt file)."""
        self.label = "Targeting Tools"
        self.alias = "Target Tools"
        # List of tool classes associated with this toolbox
        self.tools = [LandSuitability, LandStatistics, LandSimilarity]


class TargetingTool(object):
    def isLicensed(self):
        """Set license to execute tool."""
        spatialAnalystCheckedOut = False
        if arcpy.CheckExtension('Spatial') == 'Available':
            arcpy.CheckOutExtension('Spatial')
            spatialAnalystCheckedOut = True
        else:
            arcpy.AddMessage('ERROR: At a minimum, this script requires the Spatial Analyst Extension to run \n')
            sys.exit()
        return spatialAnalystCheckedOut

    def setRasSpatialWarning(self, ras_file, ras_ref, in_raster, prev_input):
        """ Set raster spatial warning
            Args:
                ras_file: Input raster file
                ras_ref: Input raster spatial reference
                in_raster: Input raster parameter
                prev_input: previous or preceding input raster with the true spatial reference
            Return: None
        """
        last_spataial_ref = arcpy.Describe(ras_file).SpatialReference   # Get spatial reference
        for ref in ras_ref:
            warning_msg = "{0} spatial reference is different from the input {1}"
            self.setSpatialWarning(last_spataial_ref, ref, in_raster, warning_msg, ras_file, prev_input)

    def setFcSpatialWarning(self, in_parameter, ras_ref, prev_input):
        """ Sets feature class spatial warning
            Args:
                parameter: Feature class input parameter
                ras_ref: Input raster spatial reference
                prev_input: previous or preceding input raster with the true spatial reference
            Return: None
        """
        in_fc_param = in_parameter
        in_fc = in_parameter.valueAsText.replace("\\", "/")
        in_fc_spataial_ref = arcpy.Describe(in_fc).SpatialReference
        warning_msg = "{0} spatial reference is different from the input {1}"
        self.setSpatialWarning(in_fc_spataial_ref, ras_ref, in_fc_param, warning_msg, in_fc, prev_input)

    def setSpatialWarning(self, in_ras_ref, other_ref, tool_para, warning_msg, new_in_ras, prev_in_ras):
        """ Sets spatial error message
            Args:
                in_ras_ref: Input data spatial reference
                other_ref: Other input data spatial reference
                tool_para: Tool parameter that will receive the warning
                warnign_msg: Spatial reference warning message
                new_in_ras: Other input data
                prev_in_ras: Input data itself
            Return: None
        """
        if in_ras_ref.Type != other_ref.Type:  # Check difference in spatial reference type
            tool_para.setWarningMessage(warning_msg.format(new_in_ras, prev_in_ras))
        elif in_ras_ref.Type != "Geographic":
            if in_ras_ref.PCSCode != other_ref.PCSCode:  # Check projection code
                tool_para.setWarningMessage(warning_msg.format(new_in_ras, prev_in_ras))

    def uniqueValueValidator(self, prev_val, str_val, tool_para, field_id):
        """ Check for duplicates
            Args:
                prev_val: Prev values as list
                str_val: Input string value
                tool_para: Tool parameter that will receive the warning
                field_id: Availability of field identifier
            Returns: None
        """
        for item in prev_val:
            if str_val == item:
                if field_id:
                    if str_val != "#":
                        tool_para.setErrorMessage("{0} is a duplicate of {1}. This is not allowed".format(str_val, item))
                    else:
                        tool_para.setErrorMessage("Column value is missing")
                else:
                    tool_para.setWarningMessage("{0} file is a duplicate of {1}".format(str_val, item))

    def getInputFc(self, parameter):
        """ Gets the input feature class
            Args:
                parameter: Tool parameters object
            Returns:
                in_fc_file: Input feature class file
                in_fc: Input feature class parameter
        """
        in_fc = parameter.valueAsText.replace("\\", "/")
        in_fc_file = ntpath.basename(in_fc)
        return {"in_fc": in_fc, "in_fc_file": in_fc_file}

    def getLayerDataSource(self, parameter):
        """ Gets current MXD layer data source
            Args:
                parameter: Tool parameters object
            Returns:
                in_fc_pt: Layer data source
        """
        in_fc_pt = ""
        mxd = arcpy.mapping.MapDocument("CURRENT")
        param_as_text = parameter.valueAsText.replace("\\", "/")
        if arcpy.mapping.ListLayers(mxd):  # Check if a layer exists
            for lyr in arcpy.mapping.ListLayers(mxd):
                if lyr.supports("datasetName"):
                    if lyr.datasetName == param_as_text:
                        if lyr.supports("dataSource"):
                            in_fc_pt = lyr.dataSource.replace("\\", "/")
        return in_fc_pt

    def formatValueTableData(self, lst):
        """ Clean value table data
            Args:
                lst: Value table input raw data
            Return:
                lst_val: Value table input row data as list
        """
        lst_val = re.sub(r"'[^']*'", '""', lst).split()  # Substitute quoted input string with empty quotes to create list
        if '""' in lst_val:
            counter = 0
            lst_quoted_val = []
            lst_quoted_re = re.compile("'[^']*'")  # Get quoted string input
            # Create list of quoted string input
            for item in lst_quoted_re.findall(lst):
                lst_quoted_val.append(item)
            # Replace empty quotes in list with quoted string inputs
            for j, str_val in enumerate(lst_val):
                if str_val == '""':
                    if counter < len(lst_quoted_val):
                        lst_val[j] = self.trimString(lst_quoted_val[counter])
                    counter += 1
        return lst_val

    def trimString(self, in_str):
        """ Trim leading and trailing quotation mark
            Args:
                in_str: String to be cleaned
            Return:
                out_str: Cleaned string
        """
        if in_str.startswith("'"):
            in_str = in_str.lstrip("'")
        if in_str.endswith("'"):
            in_str = in_str.rstrip("'")
        return in_str

    def setFileNameLenError(self, out_ras_param):
        """ Set ESRI GRID file name length error
            Args:
                out_ras_param: Out file parameter
            Return: None
        """
        if out_ras_param.value and out_ras_param.altered:
            out_ras = out_ras_param.valueAsText.replace("\\", "/")
            out_ras_file, out_ras_file_ext = os.path.splitext(out_ras)
            if out_ras_file_ext != ".tif":
                if len(ntpath.basename(out_ras)) > 13:
                    out_ras_param.setErrorMessage("Output raster: The length of the grid base name in {0} is longer than 13.".format(out_ras.replace("/", "\\")))

    def setDuplicateNameError(self, out_ras_1, out_ras_2):
        """ Set duplicate file name error
            Args:
                out_ras_1: Primary parameter
                out_ras_2: Secondary parameter
            Return: None
        """
        if out_ras_1.value and out_ras_1.altered:
            if out_ras_2.value:
                if out_ras_1.valueAsText == out_ras_2.valueAsText:
                    out_ras_1.setErrorMessage("Duplicate output names are not allowed")

    def deleteFile(self, ras_temp_path, *args):
        """ Delete table, feature class or raster files
            Args:
                ras_temp_path: Temporary folder
                *arg: File paths
            Returns: None
        """
        for arg in args:
            if arcpy.Exists(ras_temp_path + arg):
                arcpy.management.Delete(ras_temp_path + arg)

    def loadOutput(self, out_ras):
        """ Loads output to the current MXD
            Args:
                parameters: Tool parameters object
                out_ras: Raster dataset - string or list
            Return: None
        """
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd, "*")[0]  # Get the first data frame
        # Load raster dataset to the current mxd
        lyr = ""
        if isinstance(out_ras, list):  # Check if it is a list
            for data_obj in out_ras:
                lyr = arcpy.mapping.Layer(data_obj)
        else:
            lyr = arcpy.mapping.Layer(out_ras)
        arcpy.mapping.AddLayer(df, lyr, "AUTO_ARRANGE")

    def calculateStatistics(self, in_raster):
        """
        Gets raster maximum value
        :param in_raster: Input raster absolute path
        :return: A raster with statistics calculated
        :rtype: Integer or float
        """
        if arcpy.Exists(in_raster):
            try:
                arcpy.GetRasterProperties_management(in_raster, "STD")
            except arcpy.ExecuteError:
                arcpy.CalculateStatistics_management(in_raster, "1", "1", "", "OVERWRITE")
            return arcpy.Raster(in_raster)


class LandSuitability(TargetingTool):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Land Suitability"
        self.description = "Given a set of raster data and user optimal values, the Land Suitability tool determines the" \
                           " most suitable place to carry out an activity. In agriculture, it could be used to identify" \
                           " places with the best biophysical and socioeconomic conditions for a certain crop to do well."
        self.canRunInBackground = True
        self.parameters = [
            parameter("Input raster", "in_raster", "Value Table"),
            parameter("Output extent", "out_extent", "Feature Layer", parameterType='Optional'),
            parameter("Output raster", "out_raster", 'Raster Layer', direction='Output')
        ]

    def getParameterInfo(self):
        """Define parameter definitions"""
        self.parameters[0].columns = [['Raster Layer', 'Raster'], ['Double', 'Min Value'], ['Double', 'Optimal From'], ['Double', 'Optimal To'], ['Double', 'Max Value'], ['String', 'Combine-Yes/No']]
        return self.parameters

    def isLicensed(self):
        """ Set whether tool is licensed to execute."""
        spatialAnalystCheckedOut = super(LandSuitability, self).isLicensed()  # Check availability of Spatial Analyst
        return spatialAnalystCheckedOut

    def updateParameters(self, parameters):
        """ Modify the values and properties of parameters before internal
            validation is performed.  This method is called whenever a parameter
            has been changed.
            Args:
                parameters: Parameters from the tool.
            Returns: Parameter values.
        """
        if parameters[0].value:
            if parameters[0].altered:
                in_raster = parameters[0]  # Raster from the value table
                vtab = arcpy.ValueTable(len(in_raster.columns))  # Number of value table columns
                ras_max_min = True
                # Get values from the generator function and update value table
                for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                    if " " in ras_file:  # Check if there is space in file path
                        ras_file = "'" + ras_file + "'"
                    self.updateValueTable(in_raster, opt_from_val, opt_to_val, ras_combine, vtab, ras_file, minVal, maxVal)
        return

    def updateValueTable(self, in_raster, opt_from_val, opt_to_val, ras_combine, vtab, ras_file, minVal, maxVal):
        """ Update value parameters in the tool.
            Args:
                in_raster: Raster inputs
                opt_from_val: Optimal From value
                opt_to_val: Optimal To value
                ras_combine: Combine value
                vtab: Number of value table columns
                ras_file: Raster file path
                minVal: Minimum raster data value
                maxVal: Maximum raster data value
            Returns: Updated value table values.
        """
        # End of value table, now update value table last row with new column data
        if opt_from_val == "#" and opt_to_val == "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, "#", "#", maxVal, "#"))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val == "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, opt_from_val, "#", maxVal, "#"))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val != "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, "#", opt_to_val, maxVal, "#"))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val == "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, "#", "#", maxVal, ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val != "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, opt_from_val, opt_to_val, maxVal, "#"))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val != "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, "#", opt_to_val, maxVal, ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val == "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, opt_from_val, "#", maxVal, ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val != "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, opt_from_val, opt_to_val, maxVal, ras_combine))
            in_raster.value = vtab.exportToString()

    def updateMessages(self, parameters):
        """ Modify the messages created by internal validation for each tool
            parameter.  This method is called after internal validation.
            Args:
                parameters: Parameters from the tool.
            Returns: Internal validation messages.
        """
        if parameters[0].value:
            prev_input = ""
            ras_ref = []
            all_ras_ref = []
            in_raster = parameters[0]
            if parameters[0].altered:
                num_rows = len(in_raster.values)  # The number of rows in the table
                ras_max_min = True
                prev_ras_val = []
                i = 0
                # Get values from the generator function to show update messages
                for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                    i += 1
                    # Set input raster duplicate warning
                    if len(prev_ras_val) > 0:
                        super(LandSuitability, self).uniqueValueValidator(prev_ras_val, ras_file, in_raster, field_id=False)  # Set duplicate input warning
                        prev_ras_val.append(ras_file)
                    else:
                        prev_ras_val.append(ras_file)
                    # Get spatial reference for all input raster
                    spatial_ref = arcpy.Describe(ras_file).SpatialReference
                    all_ras_ref.append(spatial_ref)
                    # Set raster spatial reference errors
                    if i == num_rows:
                        super(LandSuitability, self).setRasSpatialWarning(ras_file, ras_ref, in_raster, prev_input)  # Set raster spatial warning
                    else:
                        spatial_ref = arcpy.Describe(ras_file).SpatialReference  # Get spatial reference of rasters in value table
                        ras_ref.append(spatial_ref)
                    # Set errors for other value table variables
                    if opt_from_val == "#":
                        in_raster.setErrorMessage("Crop \"Optimal From\" value is missing")
                    elif opt_to_val == "#":
                        in_raster.setErrorMessage("Crop \"Optimal To\" value is missing")
                    elif ras_combine == "#":
                        in_raster.setErrorMessage("Layer \"Combine\" value is missing")
                    elif opt_to_val == "#" and opt_from_val == "#" and ras_combine == "#":
                        in_raster.setErrorMessage("Crop \"Optimal From\", \"Optimal To\" and layer \"Combine\" values are missing")
                    elif float(opt_from_val) < float(minVal):
                        in_raster.setWarningMessage("Crop optimal value {0} is less than the minimum value {1}".format(opt_from_val, minVal))
                    elif float(opt_from_val) > float(maxVal):
                        in_raster.setErrorMessage("Crop optimal value {0} is greater than the maximum value {1}".format(opt_from_val, maxVal))
                    elif float(opt_from_val) > float(opt_to_val):
                        in_raster.setErrorMessage("Crop optimal value \"from\" is greater than crop optimal value \"to\"")
                    elif float(opt_to_val) < float(minVal):
                        in_raster.setErrorMessage("Crop optimal value {0} is less than the minimum value {1}".format(opt_to_val, minVal))
                    elif float(opt_to_val) > float(maxVal):
                        in_raster.setWarningMessage("Crop optimal value {0} is greater than the maximum value {1}".format(opt_to_val, maxVal))
                    elif ras_combine.lower() != "yes":
                        if ras_combine.lower() != "no":
                            in_raster.setErrorMessage("Layer \"Combine\" field expects \"Yes\" or \"No\" input value")
                    elif row_count == 0 and ras_combine.lower() != "no":
                        in_raster.setErrorMessage("The first \"Combine\" value should ONLY be \"No\"")
                    elif num_rows == 1:
                        in_raster.setWarningMessage("One raster in place. Two are recommended")
            # Set feature class spatial reference errors
            if parameters[1].value and parameters[1].altered:
                super(LandSuitability, self).setFcSpatialWarning(parameters[1], all_ras_ref[-1], prev_input)  # Set feature class spatial warning
        super(LandSuitability, self).setFileNameLenError(parameters[2])  # Set ESRI grid output file size error
        return

    def execute(self, parameters, messages):
        """ Execute functions to process input raster.
            Args:
                parameters: Parameters from the tool.
                messages: Internal validation messages
            Returns: Land suitability raster.
        """
        try:
            i = 0
            ras_max_min = True
            in_raster = parameters[0]
            num_rows = len(parameters[0].values)  # The number of rows in the table
            out_ras = parameters[2].valueAsText.replace("\\","/")  # Get output file path
            ras_temp_path = ntpath.dirname(out_ras)  # Get path without file name
            ras_temp_path += "/Temp/"

            if not os.path.exists(ras_temp_path):
                os.makedirs(ras_temp_path)  # Create new directory

            # Raster minus operation
            if parameters[1].value:
                in_fc = super(LandSuitability, self).getInputFc(parameters[1])["in_fc"]
                extent = arcpy.Describe(in_fc).extent # Get feature class extent
                self.rasterMinusInit(in_raster, ras_max_min, ras_temp_path, in_fc, extent)  # Minus init operation
            else:
                self.rasterMinusInit(in_raster, ras_max_min, ras_temp_path, in_fc=None, extent=None)

            self.rasterConditionInit(num_rows, "ras_min1_", "ras_min2_", "ras_max1_", "ras_max2_", ras_temp_path, "< ", "0")  # Initialize raster condition operation

            # Raster divide operation
            for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                i += 1
                self.rasterDivide(opt_from_val, minVal, "ras_min2_" + str(i), "ras_min3_" + str(i), ras_temp_path, min_ras=True)
                self.rasterDivide(opt_to_val, maxVal, "ras_max2_" + str(i), "ras_max3_" + str(i), ras_temp_path, min_ras=False)

            self.rasterConditionInit(num_rows, "ras_min3_", "ras_min4_", "ras_max3_", "ras_max4_", ras_temp_path, "> ", "1")  # Initialize raster condition operation

            # Calculate minimum rasters from the minimums and maximums calculation outputs
            for j in range(0, num_rows):
                j += 1
                arcpy.AddMessage("Generating minimum values for {0} and {1}\n".format("ras_min4_" + str(j), "ras_max4_" + str(j)))
                arcpy.gp.CellStatistics_sa(ras_temp_path + "ras_min4_" + str(j) + ";" + ras_temp_path + "ras_max4_" + str(j), ras_temp_path + "ras_MnMx_" + str(j), "MINIMUM", "DATA")
                super(LandSuitability, self).deleteFile(ras_temp_path, "ras_min4_" + str(j), "ras_max4_" + str(j))  # Delete file

            ras_temp_file = self.setCombineFile(in_raster, ras_temp_path)  # Build a list with lists of temporary raster files
            out_ras_temp = 1  # Initial temporary raster value
            n = 0
            n_ras = 0  # Number of rasters for geometric mean calculation
            # Overlay minimum rasters to create a suitability raster/map
            for item in ras_temp_file:
                if len(item) > 1:
                    n += 1
                    arcpy.AddMessage("Generating maximum values from minimum values raster files \n")
                    arcpy.gp.CellStatistics_sa(item, ras_temp_path + "rs_MxStat_" + str(n), "MAXIMUM", "DATA")
                else:
                    for f in item:
                        n_ras += 1
                        arcpy.AddMessage("Multiplying file {0} with input raster \n".format(ntpath.basename(f)))
                        out_ras_temp = out_ras_temp * arcpy.Raster(f)

            if arcpy.Exists(out_ras_temp):
                arcpy.AddMessage("Saving Temporary Output \n")
                out_ras_temp.save(ras_temp_path + "rs_TxTemp")
                out_ras_temp = arcpy.Raster(ras_temp_path + "rs_TxTemp")  # Initial temporary raster file for the next calculation

            if n >= 1:
                # Get times temp file and multiply with maximum value statistics output saved in a temporary directory
                for j in range(0, n):
                    n_ras += 1
                    j += 1
                    arcpy.AddMessage("Multiplying file {0} with input raster {1} \n".format(out_ras_temp, "rs_MxStat_" + str(j)))
                    out_ras_temp = out_ras_temp * arcpy.Raster(ras_temp_path + "rs_MxStat_" + str(j))

            arcpy.AddMessage("Generating suitability output \n")
            out_ras_temp = out_ras_temp ** (1 / float(n_ras))  # Calculate geometric mean
            arcpy.AddMessage("Saving suitability output\n")
            out_ras_temp.save(out_ras)
            arcpy.AddMessage("Suitability output saved! \n")
            arcpy.AddMessage("Creating data input log \n")
            self.createParametersLog(out_ras, ras_max_min, in_raster)  # create parameters log file
            arcpy.AddMessage("Deleting temporary folder \n")
            shutil.rmtree(ras_temp_path)  # Delete folder
            super(LandSuitability, self).loadOutput(out_ras)  # Load output to current MXD
            arcpy.RefreshCatalog(ntpath.dirname(out_ras))  # Refresh folder
            return
        except Exception as ex:
            arcpy.AddMessage('ERROR: {0} \n'.format(ex))

    def rasterMinusInit(self, in_raster, ras_max_min, ras_temp_path, in_fc, extent):
        """ Initializes raster minus operation
            Args:
                in_raster: Value table parameter with rows accompanied by columns.
                ras_max_min: A parameter that determines whether minimum and maximum value should be calculated or not.
                ras_temp_path: Temporary directory path.
                in_fc: Zone feature class input.
                extent: Zone feature class extent.
            Return: None
        """
        i = 0
        for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
            i += 1
            if extent is not None:
                # Raster clip operation
                arcpy.AddMessage("Clipping {0} \n".format(ntpath.basename(ras_file)))
                arcpy.Clip_management(ras_file, "{0} {1} {2} {3}".format(extent.XMin, extent.YMin, extent.XMax, extent.YMax), ras_temp_path + "ras_mask1_" + str(i), in_fc, "#", "ClippingGeometry")
                # Masked raster minus operation
                self.rasterMinus(ras_temp_path + "ras_mask1_" + str(i), minVal, "ras_min1_" + str(i), ras_temp_path, min_ras=True)
                self.rasterMinus(ras_temp_path + "ras_mask1_" + str(i), maxVal, "ras_max1_" + str(i), ras_temp_path, min_ras=False)
                super(LandSuitability, self).deleteFile(ras_temp_path, "ras_mask1_" + str(i))  # Delete temporary raster files
            else:
                # Raster minus operation
                self.rasterMinus(ras_file, minVal, "ras_min1_" + str(i), ras_temp_path, min_ras=True)
                self.rasterMinus(ras_file, maxVal, "ras_max1_" + str(i), ras_temp_path, min_ras=False)

    def rasterMinus(self, ras_file, val, ras_output, ras_temp_path, min_ras):
        """ Handles raster minus operation
            Args:
                ras_file: Input raster file
                val: Minimum and maximum value
                ras_output: Raster file output
                ras_temp_path: Temporary directory path
                min_ras: Boolean to determine if minimum value is available or not
            Return: Raster layer output
        """
        if min_ras:
            arcpy.AddMessage("Calculating {0} - {1} \n".format(ntpath.basename(ras_file), val))
            arcpy.gp.Minus_sa(ras_file, val, ras_temp_path + ras_output)
        else:
            arcpy.AddMessage("Calculating {0} - {1} \n".format(val, ntpath.basename(ras_file)))
            arcpy.gp.Minus_sa(val, ras_file, ras_temp_path + ras_output)

    def rasterConditionInit(self, num_rows, ras_min_input, ras_min_output, ras_max_input, ras_max_output, ras_temp_path, comp_oper, comp_val):
        """ Initializes raster condition operation
            Args:
                num_rows: Number of rows in the value table
                ras_min_input: Raster file input
                ras_min_output: Raster file output
                ras_max_input: Raster file input
                ras_max_output: Raster file output
                ras_temp_path: Temporary directory path
                comp_oper: Comparison operator
                comp_val: Comparison value
            Return:
                None
        """
        for j in range(0, num_rows):
            j += 1
            self.rasterCondition(ras_min_input + str(j), ras_min_output + str(j), ras_temp_path, comp_oper, comp_val)
            self.rasterCondition(ras_max_input + str(j), ras_max_output + str(j), ras_temp_path, comp_oper, comp_val)

    def rasterCondition(self, ras_input, ras_output, ras_temp_path, comp_oper, comp_val):
        """ Handles raster condition operation
            Args:
                ras_input: Raster file input
                ras_output: Raster file output
                ras_temp_path: Temporary directory path
                comp_oper: Comparison operator
                comp_val: Comparison value

            Return:
                Raster layer output
        """
        arcpy.AddMessage("Creating conditional output for {0} \n".format(ras_input))
        arcpy.gp.Con_sa(ras_temp_path + ras_input, comp_val, ras_temp_path + ras_output, ras_temp_path + ras_input, "\"Value\" " + comp_oper + comp_val)
        super(LandSuitability, self).deleteFile(ras_temp_path, ras_input)  # Delete temporary raster files

    def rasterDivide(self, opt_val, m_val, ras_input, ras_output, ras_temp_path, min_ras):
        """ Handles raster divide operation
            Args:
                opt_val: Optimal From aor Optimal To value
                m_val: Maximum or minimum value
                ras_input: Input raster file
                ras_output: Raster file output
                ras_temp_path: Temporary directory path
                min_ras: Boolean to determine if minimum value is available or not
            Return:
                Raster layer output
        """
        if min_ras:
            if float(opt_val) - float(m_val) == 0:
                arcpy.AddMessage("Calculating {0} / {1} \n".format(ras_input, "1"))
                arcpy.gp.Divide_sa(ras_temp_path + ras_input, "1", ras_temp_path + ras_output)
            else:
                arcpy.AddMessage("Calculating {0} / {1} - {2} \n".format(ras_input, opt_val, m_val))
                arcpy.gp.Divide_sa(ras_temp_path + ras_input, str(float(opt_val) - float(m_val)), ras_temp_path + ras_output)
        else:
            if float(m_val) - float(opt_val) == 0:
                arcpy.AddMessage("Calculating {0} / {1} \n".format(ras_input, "1"))
                arcpy.gp.Divide_sa(ras_temp_path + ras_input, "1", ras_temp_path + ras_output)
            else:
                arcpy.AddMessage("Calculating {0} / {1} - {2} \n".format(ras_input, m_val, opt_val))
                arcpy.gp.Divide_sa(ras_temp_path + ras_input, str(float(m_val) - float(opt_val)), ras_temp_path + ras_output)
        super(LandSuitability, self).deleteFile(ras_temp_path, ras_input)

    def setCombineFile(self, in_raster, ras_temp_path):
        """ Build a list with lists of temporary raster files
            Args:
                in_raster: Value table parameter with rows accompanied by columns.
                ras_temp_path: Temporary directory path
            Returns:
                ras_file_lists: List with lists of temporary raster
        """
        ras_file_lists = self.splitCombineValue(in_raster)  # Splits lists of combine column value "no"
        j = 0
        for i, item in enumerate(ras_file_lists):
            for k, val in enumerate(item):
                j += 1
                ras_file_lists[i][k] = ras_temp_path + "ras_MnMx_" + str(j)  # Update lists with temporary files
        return ras_file_lists

    def splitCombineValue(self, in_raster):
        """ Splits lists of combine column value "no" into individual lists.
            Args:
                in_raster: Value table parameter with rows accompanied by columns.
            Returns:
                split_combine_val: Group combine values with "no" lists split into
                individual lists
        """
        combine_val = self.getCombineValue(in_raster)  # Gets grouped combine values
        split_combine_val = []
        for item in combine_val:
            if len(item) > 1 and item[len(item)-1] == "no":
                for val in item:  # Add list elements "no" as individual list
                    split_combine_val.append([val])
            else:
                split_combine_val.append(item)
        return split_combine_val

    def getCombineValue(self, in_raster):
        """ Gets combine column values and groups them in a list of lists.
            Args:
                in_raster: Value table parameter with rows accompanied by columns.
            Returns:
                in_list: Grouped elements in list of lists
        """
        ras_max_min = False
        combine_val = []
        # Get combine column values
        for ras_combine in self.getRowValue(in_raster, ras_max_min):
            combine_val.append(ras_combine.lower())
        in_list = [list(g) for k, g in groupby(combine_val)]  # Group combine elements
        for i, item in enumerate(in_list):
            if len(in_list) > 1:
                if len(item) == 1 and item[0] == "no":
                    if i != len(in_list) - 1:  # Exclude last element
                        del in_list[i]  # Delete list
                        in_list[i].insert(0, "no")  # Insert deleted element to the next list
                elif len(item) > 1 and item[0] == "no":
                    in_list[i].pop()  # Remove the last element
                elif item[0] == "yes":
                    in_list[i].insert(0, "no")  # Insert popped element
        return in_list

    def getRowValue(self, in_raster, ras_max_min):
        """ Gets row values and calculate raster maximum and minimum values.
            Args:
                in_raster: Value table parameter with rows accompanied by columns.
                ras_max_min: A parameter that determines whether minimum and maximum value should be calculated or not.
            Returns:
                Optimal From, Optimal To, raster file path, raster minimum value and maximum value
        """
        for i, lst in enumerate(in_raster.valueAsText.split(";")):
            row_count = i
            lst_val = super(LandSuitability, self).formatValueTableData(lst)  # Clean value table data
            ras_file = lst_val[0]  # Get raster file path
            ras_file = ras_file.replace("\\","/")
            minVal = lst_val[1]  # Minimum raster value
            opt_from_val = lst_val[2]  # Get crop optimum value from
            opt_to_val = lst_val[3]  # Get crop optimum value to
            maxVal = lst_val[4]  # Maximum raster value
            ras_combine = lst_val[5]  # Get combine option
            if ras_max_min:
                if minVal == "#" or maxVal == "#" or ras_combine == "#":
                    paramInRaster = super(LandSuitability, self).calculateStatistics(ras_file.replace("'", ""))
                    minVal = paramInRaster.minimum  # Minimum raster value
                    maxVal = paramInRaster.maximum  # Maximum raster value
                    ras_combine = "No"
                    yield ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count  # Return output
                else:
                    if row_count == 0:  # Set first row to "No"
                        ras_combine = "No"
                        yield ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count
                    else:
                        yield ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count
            else:
                yield ras_combine

    def createParametersLog(self, out_ras, ras_max_min, in_raster):
        """ Loads output to the current MXD
            Args:
                out_ras: Land suitability layer file path
                ras_max_min: A parameter that determines whether minimum and maximum value should be calculated or not.
                in_raster: Value table parameter with rows accompanied by columns.
            Return: None
        """
        out_ras_path = ntpath.dirname(out_ras)  # Get path without file name
        out_log_txt = out_ras_path + "/data_log.txt"
        t = time.localtime()
        local_time = time.asctime(t)
        with open(out_log_txt, "w") as f:
            f.write(local_time + " Tool Inputs\n")
            f.write("\n")
            for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                new_line = str(row_count) + ": " + ras_file + " ; " + minVal + " ; " + opt_from_val + " ; " + maxVal + " ; " + opt_to_val + " ; " + ras_combine
                f.write(new_line + "\n")

    def createFcLayer(self, out_fc):
        """ Handles creation of feature class layer
            Args:
                parameters: Tool parameters object
                out_fc: Output feature class parameter
            Return:
                lyr: Feature class layer
        """
        if out_fc[-4:] != ".shp":
            out_fc = out_fc + ".shp"
        return arcpy.mapping.Layer(out_fc)


class LandStatistics(TargetingTool):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Land Statistics"
        self.description = ""
        self.canRunInBackground = True

        self.parameters = [
            parameter("Input raster zone data", "in_raszone", "Raster Layer"),
            parameter("Reclassify", "rec_option", "String", parameterType="Optional"),
            parameter("Number of Classes", "num_classes", "Long", parameterType='Optional'),
            parameter("Input remap table", "in_remap_table_view", "Table View", parameterType='Optional'),
            parameter("From value field", "from_val_field", "Field", parameterType='Optional'),
            parameter("To value field", "to_val_field", "Field", parameterType='Optional'),
            parameter("New value field", "new_val_field", "Field", parameterType='Optional'),
            parameter("Input value feature class", "in_val_fcls", "Feature Layer", parameterType='Optional'),
            parameter("Feature field name", "fval_field", "String", parameterType="Optional"),
            parameter("Input value raster", "in_val_ras", "Value Table"),
            parameter("Output Folder", "out_table", "Workspace", direction="input")
        ]

    def getParameterInfo(self):
        """Define parameter definitions"""
        self.parameters[1].filter.type = "ValueList"
        self.parameters[1].filter.list = ["NONE", "EQUAL INTERVAL", "RECLASS BY TABLE"]
        self.parameters[1].value = "NONE"  # Default value
        self.parameters[2].enabled = False
        self.parameters[3].enabled = False
        self.parameters[4].parameterDependencies = [self.parameters[3].name]
        self.parameters[4].enabled = False
        self.parameters[5].parameterDependencies = [self.parameters[3].name]
        self.parameters[5].enabled = False
        self.parameters[6].parameterDependencies = [self.parameters[3].name]
        self.parameters[6].enabled = False
        self.parameters[7].filter.list = ["Polygon"]  # Geometry type filter
        self.parameters[9].columns = [['Raster Layer', 'Raster'], ['String', 'Statistics Type'], ['String', 'Ignore NoData'], ['String', 'Output Table Name'], ['String', 'Field Identifier']]
        return self.parameters

    def isLicensed(self):
        """ Set whether tool is licensed to execute."""
        spatialAnalystCheckedOut = super(LandStatistics, self).isLicensed()  # Check availability of Spatial Analyst
        return spatialAnalystCheckedOut

    def updateParameters(self, parameters):
        """ Modify the values and properties of parameters before internal
            validation is performed.  This method is called whenever a parameter
            has been changed.
            Args:
                parameters: Parameters from the tool.
            Returns: Parameter values.
        """
        if parameters[1].value == "EQUAL INTERVAL":
            parameters[2].enabled = True
            if not parameters[2].value:
                parameters[2].value = 5   # Initial value
            self.disableEnableParameter(parameters, 2, 7, False, enabled_val=True)  # Disable or enable tool parameters
        elif parameters[1].value == "RECLASS BY TABLE":
            if parameters[2].enabled:
                parameters[2].enabled = False
                parameters[2].value = None  # Reset value
            self.disableEnableParameter(parameters, 2, 7, False, enabled_val=False)
            # Filter table fields data types
            parameters[4].filter.list = ["Short", "Long", "Float", "Single", "Double"]
            parameters[5].filter.list = ["Short", "Long", "Float", "Single", "Double"]
            parameters[6].filter.list = ["Short", "Long"]
        else:
            self.disableEnableParameter(parameters, 1, 7, False, enabled_val=True)
        # Set field values
        if parameters[7].value and parameters[7].altered:
            in_fc_field = [f.name for f in arcpy.ListFields(parameters[7].value, field_type="String")]  # Get string field headers
            parameters[8].filter.list = in_fc_field  # Updated filter list
            if parameters[8].value is None:
                if len(in_fc_field) > 0:
                    parameters[8].value = in_fc_field[0]  # Set initial field value
        else:
            parameters[8].filter.list = []  # Empty filter list
            parameters[8].value = ""  # Reset field value to None

        # Update value table inputs
        if parameters[9].value:
            if parameters[9].altered:
                in_val_raster = parameters[9]  # Input value raster from the value table
                vtab = arcpy.ValueTable(len(in_val_raster.columns))  # Number of value table columns
                for row_count, ras_val_file, stats_type, data_val, out_table_name, table_short_name in self.getStatisticsRasterValue(in_val_raster, table_only=False):
                    if " " in ras_val_file:  # Check if there is space in raster file path
                        ras_val_file = "'" + ras_val_file + "'"
                    if " " in out_table_name:
                        out_table_name = "'" + out_table_name + "'"
                    if " " in stats_type:
                        stats_type = "'" + stats_type + "'"
                    self.updateValueTableInput(parameters, in_val_raster, ras_val_file, stats_type, data_val, out_table_name, table_short_name, vtab)
        return

    def updateMessages(self, parameters):
        """ Modify the messages created by internal validation for each tool
            parameter.  This method is called after internal validation.
            Args:
                parameters: Parameters from the tool.
            Returns: Internal validation messages.
        """
        in_raster = ""
        in_ras_ref = ""
        if parameters[0].value and parameters[0].altered:
            in_raster = parameters[0].valueAsText.replace("\\", "/")
            in_ras_ref = arcpy.Describe(in_raster).SpatialReference  # Get spatial reference of input raster
        if parameters[1].value == "EQUAL INTERVAL" and parameters[2].enabled:
            if parameters[2].value <= 0:
                parameters[2].setErrorMessage("Class value should be greater than 0")
        if parameters[1].value == "RECLASS BY TABLE" and parameters[3].enabled:
            if parameters[3].value is None:
                parameters[3].setErrorMessage("Input remap table required")
            if parameters[4].value is None:
                parameters[4].setErrorMessage("From value field required")
            if parameters[5].value is None:
                parameters[5].setErrorMessage("To value field required")
            if parameters[6].value is None:
                parameters[6].setErrorMessage("New value field required")
            if parameters[4].value and parameters[5].value:
                warning_message = 'This field is similar to "From value field"'
                self.setFieldWarningMessage(parameters[4], parameters[5], warning_message)
            if parameters[4].value and parameters[6].value:
                warning_message = 'This field is similar to "From value field"'
                self.setFieldWarningMessage(parameters[4], parameters[6], warning_message)
            if parameters[5].value and parameters[6].value:
                warning_message = 'This field is similar to "To value field"'
                self.setFieldWarningMessage(parameters[5], parameters[6], warning_message)
        if parameters[7].value and parameters[7].altered:
            if parameters[0].value and parameters[0].altered:
                in_fc_para = parameters[7]
                in_fc = parameters[7].valueAsText.replace("\\", "/")
                in_fc_ref = arcpy.Describe(in_fc).SpatialReference  # Get spatial reference of input value raster
                warning_msg = "{0} spatial reference is different from the input {1}"
                super(LandStatistics, self).setSpatialWarning(in_ras_ref, in_fc_ref, in_fc_para, warning_msg, in_fc, in_raster)  # Set spatial reference warning
        if parameters[9].value and parameters[9].altered:
            in_val_raster = parameters[9]
            out_table_char = (" ", "_", "-")
            table_short_char = ("_")
            prev_ras_val = []
            prev_table_short_val = []
            prev_table_name_val = []
            for row_count, ras_val_file, stats_type, data_val, out_table_name, table_short_name in self.getStatisticsRasterValue(in_val_raster, table_only=False):
                # Table name validation
                for str_char in out_table_name:
                    self.charValidator(in_val_raster, str_char, out_table_char, field_id=False)  # Validated field value
                # Input raster value validation
                if len(prev_ras_val) > 0:
                    super(LandStatistics, self).uniqueValueValidator(prev_ras_val, ras_val_file, in_val_raster, field_id=False)  # Set duplicate input warning
                    prev_ras_val.append(ras_val_file)
                else:
                    prev_ras_val.append(ras_val_file)
                # Set spatial reference warning
                if parameters[0].value and parameters[0].altered:
                    ras_val_ref = arcpy.Describe(ras_val_file).SpatialReference  # Get spatial reference of input value raster
                    warning_msg = "{0} spatial reference is different from the input {1}"
                    super(LandStatistics, self).setSpatialWarning(in_ras_ref, ras_val_ref, in_val_raster, warning_msg, ras_val_file, in_raster)  # Set spatial reference warning
                self.statisticsTypeErrorMessage(in_val_raster, stats_type)  # Set error message for statistics type
                # Ignore NoData validation
                if data_val.lower() != "yes":
                    if data_val.lower() != "no":
                        in_val_raster.setErrorMessage("Ignore NoData field expects \"Yes\" or \"No\" input value")
                # Field identifier validation
                if len(in_val_raster.valueAsText.split(";")) > 1:
                    # Validated field identifier input
                    self.fielIdValidator(table_short_name, in_val_raster, table_short_char)  # Value table field identifier validator
                    if len(prev_table_short_val) > 0:
                        super(LandStatistics, self).uniqueValueValidator(prev_table_short_val, table_short_name, in_val_raster, field_id=True)
                        prev_table_short_val.append(table_short_name)
                    else:
                        prev_table_short_val.append(table_short_name)
                    # Validated output table name input
                    if len(prev_table_name_val) > 0:
                        super(LandStatistics, self).uniqueValueValidator(prev_table_name_val, out_table_name, in_val_raster, field_id=True)
                        prev_table_name_val.append(out_table_name)
                    else:
                        prev_table_name_val.append(out_table_name)
        return

    def execute(self, parameters, messages):
        """ Execute functions to process input raster.
            Args:
                parameters: Parameters from the tool.
                messages: Internal validation messages
            Returns: Land statistics table.
        """
        try:
            in_raster = parameters[0].valueAsText.replace("\\", "/")
            out_table = parameters[10].valueAsText.replace("\\", "/")  # Get output folder path
            ras_temp_path = out_table + "/Temp/"

            if not os.path.exists(ras_temp_path):
                os.makedirs(ras_temp_path)  # Create temporary directory

            # Feature class rasterization and overlay
            if parameters[7].value:
                in_fc = super(LandStatistics, self).getInputFc(parameters[7])["in_fc"]  # Get feature file path
                in_fc_file = super(LandStatistics, self).getInputFc(parameters[7])["in_fc_file"]  # Get feature file name
                in_fc_field = parameters[8].valueAsText
                arcpy.AddMessage("Converting polygon {0} to raster \n".format(in_fc_file))
                arcpy.PolygonToRaster_conversion(in_fc, in_fc_field, ras_temp_path + "ras_poly", "CELL_CENTER", "NONE", in_raster)  # Convert polygon to raster
                arcpy.gp.Times_sa(ras_temp_path + "ras_poly", "1000", ras_temp_path + "ras_multi")  # Process: Times
                in_raster = self.reclassifyRaster(parameters, ras_temp_path)  # Reclassify input raster
                self.zonalStatisticsInit(in_raster, ras_temp_path, parameters, ras_add=True)
                self.configZonalStatisticsTable(parameters, ras_temp_path, out_table, in_vector=True)
            else:
                in_raster = self.reclassifyRaster(parameters, ras_temp_path)
                self.zonalStatisticsInit(in_raster, ras_temp_path, parameters, ras_add=False)
                self.configZonalStatisticsTable(parameters, ras_temp_path, out_table, in_vector=False)
            shutil.rmtree(ras_temp_path)  # delete folder
            arcpy.RefreshCatalog(out_table)  # Refresh folder
            return
        except Exception as ex:
            #tb = sys.exc_info()[2]
            #tbinfo = traceback.format_tb(tb)[0]
            #pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])
            #msgs = "ArcPy ERRORS:\n" + arcpy.GetMessages(2) + "\n"
            #arcpy.AddError(pymsg)
            #arcpy.AddError(msgs)
            arcpy.AddMessage('ERROR: {0} \n'.format(ex))

    def disableEnableParameter(self, parameters, val_1, val_2, boolean_val, enabled_val):
        """Disable or enable tool parameters
            Args:
                parameters: Tool parameters
                val_1: First comparison value
                val_2: Second comparison value
                boolean_val: Boolean value
            Return: None
        """
        for i, item in enumerate(parameters):
            if (i > val_1) and (i < val_2):
                if enabled_val:
                    if parameters[i].enabled:
                        if not boolean_val:
                            parameters[i].value = None  # Reset values
                        parameters[i].enabled = boolean_val
                else:
                    parameters[i].enabled = True

    def updateValueTableInput(self, parameters, in_val_raster, ras_val_file, stats_type, data_val, out_table_name, table_short_name, vtab):
        """ Update value parameters in the tool.
            Args:
                parameters: Tool parameters
                in_val_raster: Input value raster parameter
                ras_val_file: Input value raster
                stats_type: Statistic type to be calculated
                data_val: Denotes whether NoData values in the Value input will influence the results or not
                out_stat_table: Output zonal statistics table
                table_short_name: Unique string to be concatenated with table field name
                vtab: Number of value table columns
            Returns: Parameter values.
        """
        if table_short_name == "#":
            vtab.addRow('{0} {1} {2} {3} {4}'.format(ras_val_file, stats_type, data_val, out_table_name, "#"))
            in_val_raster.value = vtab.exportToString()
        if table_short_name != "#":
            vtab.addRow('{0} {1} {2} {3} {4}'.format(ras_val_file, stats_type, data_val, out_table_name, table_short_name))
            in_val_raster.value = vtab.exportToString()

    def setFieldWarningMessage(self, parameter_1, parameter_2, warning_message):
        """ Set warning messages on input table fields
            Args:
                parameter_1: Input table field parameter
                parameter_2: Input table field parameter
                warning_message: Field warning message
            Return: None
        """
        if parameter_1.altered or parameter_2.altered:
            if parameter_1.valueAsText == parameter_2.valueAsText:
                parameter_2.setWarningMessage(warning_message)

    def statisticsTypeErrorMessage(self, in_val_raster, stats_type):
        """ Set error message for statistics type
            Args:
                in_val_raster: Input value raster
                stats_type: Input statistics type from the value table
            Return: None
        """
        if stats_type.upper() not in {"ALL", "MEAN", "MAJORITY", "MAX", "MAXIMUM", "MEDIAN", "MINIMUM", "MIN", "MINORITY", "RANGE",
                              "SD", "SN", "SR", "STDEV", "STANDARD DEVIATION", "STD", "SUM", "VARIETY"}:
            in_val_raster.setErrorMessage("Allowed Statistics type: {0}".format("ALL | MEAN | MAJORITY | MAX | MAXIMUM | MEDIAN | MINIMUM | MIN | MINORITY | "
                                                                                "RANGE | SUM | VARIETY | STD | SD | SN | SR | STDEV | STANDARD DEVIATION"))

    def fielIdValidator(self, table_short_name, in_val_raster, table_short_char):
        """ Value table field identifier validator
            Args:
                table_short_name: Value table field identifier column value
                in_val_raster: Input value raster
                table_short_char: esc_char: Escape characters
            Returns: None
        """
        if len(table_short_name) > 2:
            in_val_raster.setErrorMessage("Field identifier field cannot have more than two values")
        elif table_short_name[0].isdigit():
            in_val_raster.setErrorMessage("Field identifier value cannot start with a digit")
        elif table_short_name.startswith("_"):
            in_val_raster.setErrorMessage("Field identifier value cannot start with an  underscore")
        for str_char in table_short_name:
            self.charValidator(in_val_raster, str_char, table_short_char, field_id=True)  # Validated field value

    def charValidator(self, in_val_raster, str_char, esc_char, field_id):
        """ Validated string character
            Args:
                in_val_raster: Input value raster
                str_char: String character
                esc_char: Escape characters
                field_id: Check if field identifier column is to be validated or not
            Returns: None
        """
        # Check for invalid values
        if str_char.isalnum() is False and str_char not in esc_char:
            if field_id:
                if str_char == " ":
                    in_val_raster.setErrorMessage("Space is not allowed. Use an underscore instead".format(str_char))
            if str_char == "#":
                in_val_raster.setErrorMessage("Column value is missing")
            else:
                in_val_raster.setErrorMessage("{0} is not a valid character for this field".format(str_char))

    def reclassifyRaster(self, parameters, ras_temp_path):
        """ Reclassify input raster
            Args:
                parameters: Parameters from the tool.
                ras_temp_path: Temporary folder
            Return:
                reclass_raster: Reclassified input raster
        """
        reclass_raster = ""
        in_raster = parameters[0].valueAsText.replace("\\","/")
        if parameters[1].value == "EQUAL INTERVAL":
            stat_raster = super(LandStatistics, self).calculateStatistics(in_raster)
            min_val = arcpy.Raster(stat_raster).minimum  # Minimum input raster value
            max_val = arcpy.Raster(stat_raster).maximum  # Maximum input raster value
            num_cls = parameters[2].value
            cls_width = float(max_val - min_val)/num_cls  # Class width
            if cls_width.is_integer():
                cls_width = int(cls_width)  # Convert to integer
            arcpy.AddMessage("Creating reclassify range for {0} \n".format(in_raster))
            equal_interval_val = self.getEqualIntervalRemapVal(min_val, cls_width, num_cls)  # List of reclassify value lists
            self.createEqualIntervalValLog(parameters, equal_interval_val)  # Create a log of equal interval values
            arcpy.AddMessage("Reclassifying {0} \n".format(in_raster))
            reclass_raster = self.reclassifyEqualInterval(in_raster, ras_temp_path, equal_interval_val)  # Reclassify input raster layer
        elif parameters[1].value == "RECLASS BY TABLE":
            in_table = parameters[3].valueAsText
            from_val = parameters[4].valueAsText
            to_val = parameters[5].valueAsText
            new_val = parameters[6].valueAsText
            arcpy.AddMessage("Reclassifying {0} \n".format(in_raster))
            arcpy.gp.ReclassByTable_sa(in_raster, in_table, from_val, to_val, new_val, ras_temp_path + "ras_reclass", "DATA")  # Process: Reclass by Table
            reclass_raster = ras_temp_path + "ras_reclass"
        else:
            reclass_raster = in_raster
        return reclass_raster

    def getEqualIntervalRemapVal(self, min_val, cls_width, num_cls):
        """ Create list of equal interval reclassify value lists
            Args:
                parameters: Parameters from the tool.
                min_val: Minimum input raster value
                cls_width: Class width
                num_cls: Number of classes
            Return:
                equal_interval_val: A list of list with reclassify values
        """
        equal_interval_val = []
        prev_count = 0
        for i in xrange(1, num_cls + 1):
            remap_range_val = []
            for j in xrange(1):
                if i == 1:
                    remap_range_val.append(min_val)
                    remap_range_val.append(min_val + cls_width)
                    remap_range_val.append(i)
                elif i == 2:
                    remap_range_val.append(min_val + cls_width)
                    remap_range_val.append(min_val + (cls_width * i))
                    remap_range_val.append(i)
                else:
                    remap_range_val.append(min_val + (cls_width * prev_count))
                    remap_range_val.append(min_val + (cls_width * i))
                    remap_range_val.append(i)
            equal_interval_val.append(remap_range_val)
            prev_count = i
        return equal_interval_val

    def createEqualIntervalValLog(self, parameters, interval_val):
        """ Create a log of equal interval values used in reclassification of raster
            Args:
                parameters: Parameters from the tool.
                interval_val: A list of list with reclassify values.
            Return: None
        """
        out_dir = parameters[10].valueAsText.replace("\\", "/")  # Get output folder path
        interval_log_txt = out_dir + "/equal_interval_log.txt"
        t = time.localtime()
        local_time = time.asctime(t)
        with open(interval_log_txt, "w") as f:
            f.write(" " + local_time + " \n")
            f.write("\n")
            f.write(" Equal Interval Values \n")
            f.write(" ====================== \n")
            f.write("\n")
            f.write(" Number of Classes: " + str(len(interval_val)) + "\n")
            f.write("\n")
            f.write("  From Value            To Value            Output Value \n")
            f.write(" ------------          ----------          -------------- \n")
            f.write("\n")
            for item in interval_val:
                val = "  " + str(item[0]) + "                   " + str(item[1]) + "                 " + str(item[2])
                f.write(val + "\n")

    def reclassifyEqualInterval(self, in_raster, ras_temp_path, remap_val):
        """ Reclassify input raster layer
            Args:
                in_raster: Input land suitability raster
                ras_temp_path: Temporary folder
                remap_val: Input raster reclassify values
            Return: Reclassified raster temporary path
        """
        remap_val_range = arcpy.sa.RemapRange(remap_val)
        reclass_raster = arcpy.sa.Reclassify(in_raster, "Value", remap_val_range, "DATA")  # Process: Reclassify
        reclass_raster.save(ras_temp_path + "ras_reclass")
        return ras_temp_path + "ras_reclass"

    def zonalStatisticsInit(self, in_raster, ras_temp_path, parameters, ras_add):
        """ Initialize the zonal statistics calculation process
            Args:
                in_raster: Input land suitability raster.
                ras_temp_path: Temporary folder
                parameters: Tool parameters
                ras_add: Variable to hint if another process should take place or not
            Returns: None.
        """
        in_val_raster = parameters[9]
        if ras_add:
            arcpy.AddMessage("Initializing land statistics \n")
            arcpy.AddMessage("Adding {0} to {1} \n".format(ras_temp_path + "ras_multi", in_raster))
            arcpy.gp.Plus_sa(ras_temp_path + "ras_multi", in_raster, ras_temp_path + "ras_plus")  # Process: Plus
            super(LandStatistics, self).deleteFile(ras_temp_path, "ras_multi", "ras_reclass")  # Delete file
            in_raster = ras_temp_path + "ras_plus"
            ras_copy = self.convertRasterPixelType(in_raster, ras_temp_path)  # Convert float/double precision to 32 bit integer
            if ras_copy is not None:
                in_raster = ras_copy
            arcpy.AddMessage("Building raster attribute table for {0} \n".format(in_raster))
            arcpy.BuildRasterAttributeTable_management(in_raster, "Overwrite")  # Build attribute table for raster
            for row_count, ras_val_file, stats_type, data_val, out_table_name, table_short_name in self.getStatisticsRasterValue(in_val_raster, table_only=False):
                stats_type_edit = self.formatStatisticsType(stats_type)
                out_stat_table = ras_temp_path + out_table_name + ".dbf"
                self.calculateZonalStatistics(in_raster, ras_val_file, stats_type_edit, data_val, out_stat_table)
            super(LandStatistics, self).deleteFile(ras_temp_path, "ras_plus", "ras_copy")
        else:
            ras_copy = self.convertRasterPixelType(in_raster, ras_temp_path)
            if ras_copy is not None:
                in_raster = ras_copy
            arcpy.AddMessage("Building raster attribute table for {0} \n".format(in_raster))
            arcpy.BuildRasterAttributeTable_management(in_raster, "Overwrite")  # Build attribute table for raster
            for row_count, ras_val_file, stats_type, data_val, out_table_name, table_short_name in self.getStatisticsRasterValue(in_val_raster, table_only=False):
                stats_type_edit = self.formatStatisticsType(stats_type)
                out_stat_table = ras_temp_path + out_table_name + ".dbf"
                self.calculateZonalStatistics(in_raster, ras_val_file, stats_type_edit, data_val, out_stat_table)
            super(LandStatistics, self).deleteFile(ras_temp_path, "ras_reclass", "ras_copy")

    def getStatisticsRasterValue(self, in_val_raster, table_only):
        """ Get row statistics parameters from the value table
            Args:
                in_val_raster: Value table parameter with the statistics parameters
            Return:
        """
        for i, lst in enumerate(in_val_raster.valueAsText.split(";")):
            row_count = i
            lst_val = super(LandStatistics, self).formatValueTableData(lst)  # Clean value table data
            ras_val_file = lst_val[0]
            ras_val_file = ras_val_file.replace("\\","/")
            stats_type = lst_val[1]
            data_val = lst_val[2]
            out_table_name = lst_val[3].rstrip()
            table_short_name = lst_val[4]
            # Check if data is empty
            if not table_only:
                if stats_type == "#" or data_val == "#" or out_table_name == "#":
                    stats_type = "ALL"
                    data_val = "Yes"
                    out_table_name = ntpath.basename(ras_val_file)  # Get input raster file name
                    out_table_name = os.path.splitext(out_table_name)[0].rstrip()  # Get input raster file name without extension
                    yield row_count, ras_val_file, stats_type, data_val, out_table_name, table_short_name
                else:
                    yield row_count, ras_val_file, stats_type, data_val, out_table_name, table_short_name
            else:
                yield row_count, out_table_name, table_short_name

    def convertRasterPixelType(self, in_raster, ras_temp_path):
        """ Convert float/double precision raster to 32 bit signed integer pixel type
            Args:
                in_raster: Input land suitability raster.
                ras_temp_path: Temporary folder
            Returns: A 32 bit signed integer raster.
        """
        ras_desc = arcpy.Describe(in_raster)
        # Check raster pixel type and copy raster
        if ras_desc.pixelType in {"F32", "F64"}:
            in_raster_obj = super(LandStatistics, self).calculateStatistics(in_raster)
            minVal = in_raster_obj.minimum  # Minimum raster value
            minVal -= 1
            # Convert float/double precision raster to 32 bit signed integer
            arcpy.AddMessage("Converting {0} to a 32 bit signed {1} \n".format(in_raster, ras_temp_path + "ras_copy"))
            arcpy.CopyRaster_management(in_raster, ras_temp_path + "ras_copy", "", "", str(minVal), "NONE", "NONE", "32_BIT_SIGNED", "NONE", "NONE")
            return ras_temp_path + "ras_copy"

    def formatStatisticsType(self, stats_type):
        """ Format statistics type string to the right format
            Args:
                stats_type: Value table statistics type input
        """
        stats_type = stats_type.upper()
        if stats_type == "MAX":
            stats_type_edit = "MAXIMUM"
        elif stats_type == "MIN":
            stats_type_edit = "MINIMUM"
        elif stats_type in {"SD", "SN", "SR", "STDEV", "STANDARD DEVIATION"}:
            stats_type_edit = "STD"
        else:
            stats_type_edit = stats_type
        return stats_type_edit

    def calculateZonalStatistics(self, in_raster, ras_val_file, stats_type_edit, data_val, out_stat_table):
        """ Calculate statistics on a given area  of interest - zone
            Args:
                in_raster: Input land suitability raster or plus raster
                in_val_raster: Raster that contains the values on which to calculate a statistic.
                data_val: Denotes whether NoData values in the Value input will influence the results or not
                stats_type: Statistic type to be calculated
                out_stat_table: Output zonal statistics table
            Returns: Saves a dbf table to memory
        """
        if data_val.lower() == "yes":
            arcpy.AddMessage("Calculating land statistics for {0} \n".format(ras_val_file))
            arcpy.gp.ZonalStatisticsAsTable_sa(in_raster, "Value", ras_val_file, out_stat_table, "DATA", stats_type_edit)  # Process: Zonal Statistics as Table
        else:
            arcpy.AddMessage("Calculating land statistics for {0} \n".format(ras_val_file))
            arcpy.gp.ZonalStatisticsAsTable_sa(in_raster, "Value", ras_val_file, out_stat_table, "NODATA", stats_type_edit)  # Process: Zonal Statistics as Table

    def configZonalStatisticsTable(self, parameters, ras_temp_path, out_table, in_vector):
        """ Manipulate zonal statistics table
            Args:
                parameters: Value table input parameters
                ras_temp_path: Temporary folder
                out_table: Output zonal statistics directory
                in_vector: Input feature class
            Return: None
        """
        in_val_raster = parameters[9]
        first_stat_table = ""
        single_out_stat_table = ""
        single_move_stat_table = ""
        if len(in_val_raster.valueAsText.split(";")) > 1:
            for row_count, out_table_name, table_short_name in self.getStatisticsRasterValue(in_val_raster, table_only=True):
                if row_count == 0:
                    first_stat_table = ras_temp_path + out_table_name + "_view" + ".dbf"
                table_short_name = table_short_name.upper()
                self.updateZonalStatisticsTable(out_table, ras_temp_path, row_count, out_table_name, first_stat_table, table_short_name)
            self.addFieldValueZonalStatisticsTable(parameters, out_table, ras_temp_path, first_stat_table) # Add new fields and values
        else:
            for row_count, out_table_name, table_short_name in self.getStatisticsRasterValue(in_val_raster, table_only=True):
                if row_count == 0:
                    single_out_stat_table = ras_temp_path + out_table_name + ".dbf"
                    single_move_stat_table = out_table + "/" + out_table_name + ".dbf"
            if in_vector:
                self.addFieldValueZonalStatisticsTable(parameters, out_table, ras_temp_path, single_out_stat_table)
            else:
                arcpy.AddMessage("Moving file {0} to {1} \n".format(single_out_stat_table, single_move_stat_table))
                self.moveFile(single_out_stat_table, single_move_stat_table)

    def updateZonalStatisticsTable(self, out_table, ras_temp_path, row_count, out_table_name, first_stat_table, table_short_name):
        """ Edit zonal statistics output table
            Args:
                out_table: Ouput folder
                ras_temp_path: Temporary folder
                row_count: Number of rows with input in the value table
                out_table_name: Output .dbf table name
                first_stat_table: First output table name in the value table input
                table_short_name: A short name to append to table columns
            Return: None
        """
        out_stat_table = ras_temp_path + out_table_name + ".dbf"
        move_stat_table = out_table + "/" + out_table_name + ".dbf"
        arcpy.AddMessage("Renaming fields in {0} \n".format(out_table_name + ".dbf"))
        out_table_view = self.renameTableField(out_stat_table, out_table_name, table_short_name, ras_temp_path)  # Rename table fields
        arcpy.AddMessage("Moving file {0} to {1} \n".format(out_stat_table, move_stat_table))
        self.moveFile(out_stat_table, move_stat_table)  # Move original tables to output folders
        if row_count > 0:
            field_names = [f.name for f in arcpy.ListFields(out_table_view)]  # Get all field names
            del_fields = {"OID", "VALUE", "COUNT"}  # Fields to be excluded in the join
            req_fields = [i for i in field_names if i not in del_fields]  # Fields to included in the join
            arcpy.AddMessage("Joining {0} to {1} \n".format(out_table_view, first_stat_table))
            arcpy.JoinField_management(first_stat_table, "VALUE", out_table_view, "VALUE", req_fields)  # Join tables
            arcpy.management.Delete(out_table_view)

    def renameTableField(self, out_stat_table, out_table_name, table_short_name, ras_temp_path):
        """ Rename table fields
            Args:
                out_stat_table: Output table path
                out_table_name: Output table name
                table_short_name: Field keyword
                ras_temp_path: Temporary folder
            return:
                out_table_view: a table with renamed fields
        """
        fields = arcpy.ListFields(out_stat_table)  # Get fields
        fieldinfo = arcpy.FieldInfo()  # Create a fieldinfo object
        # Iterate through the fields and set them to fieldinfo
        for field in fields:
            if field.name in {"AREA", "MIN", "MAX", "RANGE", "MEAN", "STD", "SUM", "VARIETY", "MAJORITY", "MINORITY", "MEDIAN"}:
                fieldinfo.addField(field.name, table_short_name + "_" + field.name, "VISIBLE", "")
        view_table = out_table_name + "_view"
        # Create a view layer in memory with fields as set in fieldinfo object
        arcpy.MakeTableView_management(out_stat_table, view_table, "", "", fieldinfo)
        # make a copy of the view in disk
        arcpy.CopyRows_management(view_table, ras_temp_path + view_table + ".dbf")
        out_table_view = ras_temp_path + view_table + ".dbf"
        if arcpy.Exists(view_table):
            arcpy.Delete_management(view_table)  # delete view if it exists
        return out_table_view

    def moveFile(self, current_path, new_path):
        """ Move a table from the current directory to another
            Args:
                current_path: Current location of the file
                new_path: The new directory to move the file to
            Return: None
        """
        shutil.move(current_path, new_path)  # Move individual tables to output folder

    def addFieldValueZonalStatisticsTable(self, parameters, out_table, ras_temp_path, first_stat_table):
        """ Add new fields and values to the zonal statistics table
            Args:
                parameters: Tool parameters
                out_table: Ouput folder
                ras_temp_path: Temporary folder
                first_stat_table: First output table name in the value table input
        """
        # Add new fields and data
        if len(parameters[9].valueAsText.split(";")) > 1:
            combined_stat_table = out_table + "/All_Zonal_Stat.dbf"
        else:
            in_dbf_file = ntpath.basename(first_stat_table)
            combined_stat_table = out_table + "/" + in_dbf_file
        if parameters[7].value and arcpy.Exists(first_stat_table):
            in_fc_field = parameters[8].valueAsText
            ras_poly = ras_temp_path + "ras_poly"
            if not arcpy.ListFields(first_stat_table, in_fc_field):
                arcpy.AddMessage("Adding fields to {0} \n".format(first_stat_table))
                self.addTableField(first_stat_table, in_fc_field)  # Adds field to a .dbf table
            # Process: Calculate Field
            arcpy.AddMessage("Adding suitability rank values to new fields in {0} \n".format(first_stat_table))
            arcpy.CalculateField_management(first_stat_table, "POLY_VAL", "([VALUE] - Right([VALUE] , 3)) / 1000", "VB", "")
            arcpy.CalculateField_management(first_stat_table, "LAND_RANK", "Right([VALUE] , 3)", "VB", "")
            # Add values to table
            arcpy.AddMessage("Adding ID values to new fields in {0} \n".format(first_stat_table))
            self.addValuesZonalStatisticsTable(in_fc_field, ras_poly, first_stat_table)
            arcpy.AddMessage("Moving file {0} to {1} \n".format(first_stat_table, combined_stat_table))
            self.moveFile(first_stat_table, combined_stat_table)
        else:
            arcpy.AddMessage("Moving file {0} to {1} \n".format(first_stat_table, combined_stat_table))
            self.moveFile(first_stat_table, combined_stat_table)

    def addTableField(self, first_stat_table, in_fc_field):
        """ Adds field to a .dbf table
            Args:
                in_fc_field: Feature name field
                first_stat_table: First output table name in the value table input
            Return: None
        """
        arcpy.AddField_management(first_stat_table, in_fc_field, "STRING")
        arcpy.AddField_management(first_stat_table, "POLY_VAL", "LONG")
        arcpy.AddField_management(first_stat_table, "LAND_RANK", "LONG")

    def addValuesZonalStatisticsTable(self, in_fc_field, ras_poly, out_stat_table):
        """ Copy field values from one table to another
            Args:
                in_fc_field: Input feature class field name
                ras_poly: Rasterized polygon
                out_stat_table: Output zonal statistics table
        """
        with arcpy.da.SearchCursor(ras_poly, ["VALUE"]) as cursor:
            for row in cursor:
                sql_exp1 = "VALUE = " + str(row[0])  # SQL expression
                sql_exp2 = "POLY_VAL = " + str(row[0])
                with arcpy.da.SearchCursor(ras_poly, [in_fc_field], sql_exp1) as cursor2:
                    for row2 in cursor2:
                        update_val = row2[0]
                        with arcpy.da.UpdateCursor(out_stat_table, [in_fc_field], sql_exp2) as cursor3:  # Update values in the second table
                            for row3 in cursor3:
                                row3[0] = update_val
                                cursor3.updateRow(row3)

        arcpy.DeleteField_management(out_stat_table, "POLY_VAL")  # Process: Delete Field
        arcpy.management.Delete(ras_poly)  # Delete polygon


class LandSimilarity(TargetingTool):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Land Similarity"
        self.description = ""
        self.canRunInBackground = False
        self.parameters = [
            parameter("Input raster", "in_raster", "Raster Layer", multiValue=True),
            parameter("Input point layer", "in_point", "Feature Layer"),
            parameter("Output extent", "out_extent", "Feature Layer", parameterType='Optional'),
            parameter("R executable", "r_exe", "File"),
            parameter("Output Mahalanobis raster", "out_raster_mnobis", 'Raster Layer', direction='Output'),
            parameter("Output MESS raster", "out_raster_mess", 'Raster Layer', direction='Output')
        ]

    def getParameterInfo(self):
        """Define parameter definitions"""
        self.parameters[1].filter.list = ["Point"]  # Geometry type filter
        return self.parameters

    def isLicensed(self):
        """ Set whether tool is licensed to execute."""
        spatialAnalystCheckedOut = super(LandSimilarity, self).isLicensed()  # Check availability of Spatial Analyst
        return spatialAnalystCheckedOut

    def updateParameters(self, parameters):
        """ Modify the values and properties of parameters before internal
            validation is performed.  This method is called whenever a parameter
            has been changed.
            Args:
                parameters: Parameters from the tool.
            Returns: Parameter values.
        """
        if parameters[0].value:
            if not parameters[3].value:  # Set initial value
                root_dir = "C:/Program Files/R"
                if os.path.isdir(root_dir):
                    parameters[3].value = self.getRExecutable(root_dir)  # Get R executable file
        return

    def updateMessages(self, parameters):
        """ Modify the messages created by internal validation for each tool
            parameter.  This method is called after internal validation.
            Args:
                parameters: Parameters from the tool.
            Returns: Internal validation messages.
        """
        if parameters[0].value:
            prev_input = ""
            ras_ref = []
            all_ras_ref = []
            in_val_raster = parameters[0]
            if parameters[0].altered:
                num_rows = len(in_val_raster.values)  # The number of rows in the table
                prev_ras_val = []
                i = 0
                # Get values from the generator function to show update messages
                for row_count, in_ras_file in self.getRasterFile(in_val_raster):
                    i += 1
                    # Set input raster duplicate warning
                    if len(prev_ras_val) > 0:
                        super(LandSimilarity, self).uniqueValueValidator(prev_ras_val, in_ras_file, in_val_raster, field_id=False)  # Set duplicate input warning
                        prev_ras_val.append(in_ras_file)
                    else:
                        prev_ras_val.append(in_ras_file)
                    # Get spatial reference for all input raster
                    spatial_ref = arcpy.Describe(in_ras_file).SpatialReference
                    all_ras_ref.append(spatial_ref)
                    # Set raster spatial reference errors
                    if i == num_rows:
                        super(LandSimilarity, self).setRasSpatialWarning(in_ras_file, ras_ref, in_val_raster, prev_input)  # Set raster spatial warning
                    else:
                        spatial_ref = arcpy.Describe(in_ras_file).SpatialReference  # Get spatial reference of input rasters
                        ras_ref.append(spatial_ref)
            if parameters[1].value and parameters[1].altered:
                super(LandSimilarity, self).setFcSpatialWarning(parameters[1], all_ras_ref[-1], prev_input)  # Set feature class spatial warning
            if parameters[2].value and parameters[2].altered:
                super(LandSimilarity, self).setFcSpatialWarning(parameters[2], all_ras_ref[-1], prev_input)
        if parameters[1].value and parameters[1].altered:
            in_fc = parameters[1].valueAsText.replace("\\", "/")
            result = arcpy.GetCount_management(in_fc)  # Get number of features in the input feature class
            if int(result.getOutput(0)) <= 1:
                parameters[1].setWarningMessage("Input point layer has a single feature. MESS will NOT be calculated.")
        if parameters[3].value and parameters[3].altered:
            r_exe_path = parameters[3].valueAsText
            if not r_exe_path.endswith(("\\bin\\R.exe", "\\bin\\x64\\R.exe", "\\bin\\i386\\R.exe")):
                parameters[3].setErrorMessage("{0} is not a valid R executable".format(r_exe_path))
        super(LandSimilarity, self).setDuplicateNameError(parameters[4], parameters[5])  # Set duplicate file name error
        super(LandSimilarity, self).setDuplicateNameError(parameters[5], parameters[4])
        super(LandSimilarity, self).setFileNameLenError(parameters[4])  # Set ESRI grid output file size error
        super(LandSimilarity, self).setFileNameLenError(parameters[5])
        return

    def execute(self, parameters, messages):
        """ Execute functions to process input raster.
            Args:
                parameters: Parameters from the tool.
                messages: Internal validation messages
            Returns: Land suitability raster.
        """
        try:
            r_exe_path = parameters[3].valueAsText
            out_mnobis_ras = parameters[4].valueAsText.replace("\\", "/")  # Get mahalanobis output
            out_mess_ras = parameters[5].valueAsText.replace("\\", "/")  # Get mess output
            ras_temp_path = ntpath.dirname(out_mnobis_ras)  # Get path without file name
            ras_temp_path += "/Temp/"
            # Create temporary directory if it doesn't exist
            if not os.path.exists(ras_temp_path):
                os.makedirs(ras_temp_path)
            # Copy point layer to temporary directory
            in_fc_pt = parameters[1].valueAsText.replace("\\", "/")
            if os.path.isfile(in_fc_pt):
                in_fc_pt = self.copyDataset(ras_temp_path, in_fc_pt, in_fc_pt)  # Copy dataset from source to destination
            else:
                in_fc_pt = super(LandSimilarity, self).getLayerDataSource(parameters[1])  # Get point layer data source
                in_fc_pt = self.copyDataset(ras_temp_path, in_fc_pt, in_fc_pt)

            # raster sample creation
            if parameters[2].value:
                in_fc = super(LandSimilarity, self).getInputFc(parameters[2])["in_fc"]
                extent = arcpy.Describe(in_fc).extent  # Get feature class extent
                self.createValueSample(parameters, in_fc_pt, ras_temp_path, in_fc, extent)  # Create raster cell value sample
            else:
                self.createValueSample(parameters, in_fc_pt, ras_temp_path, in_fc=None, extent=None)  # Create raster cell value sample
            self.deleteTempFile(parameters, ras_temp_path)  # Delete temporary files
            arcpy.AddMessage("Joining {0} to {1} \n".format(in_fc_pt, ras_temp_path + "temp.dbf"))
            arcpy.JoinField_management(in_fc_pt, "FID", ras_temp_path + "temp.dbf", "OID", "")  # Join tables
            out_csv = ras_temp_path + "temp.csv"
            self.writeToCSV(in_fc_pt, out_csv)  # Write feature class table to CSV file
            arcpy.management.Delete(in_fc_pt)  # Delete vector
            self.createRScript(parameters, ras_temp_path)  # Create R script
            self.runCommand(r_exe_path, ras_temp_path)  # Run R command
            self.asciiToRasterConversion(parameters, ras_temp_path)  # ASCII to raster conversion
            shutil.rmtree(ras_temp_path)  # Delete directory

            # Get raster and load to the current mxd
            out_ras = ""
            if arcpy.Exists(out_mnobis_ras) and arcpy.Exists(out_mess_ras):
                out_ras = [out_mnobis_ras, out_mess_ras]
            else:
                if arcpy.Exists(out_mnobis_ras):
                    out_ras = out_mnobis_ras
                elif arcpy.Exists(out_mess_ras):
                    out_ras = out_mess_ras
            super(LandSimilarity, self).loadOutput(out_ras)  # Load output to current MXD
            arcpy.RefreshCatalog(ntpath.dirname(out_mnobis_ras))  # Refresh folder
            return
        except Exception as ex:
            #tb = sys.exc_info()[2]
            #tbinfo = traceback.format_tb(tb)[0]
            #pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])
            #msgs = "ArcPy ERRORS:\n" + arcpy.GetMessages(2) + "\n"
            #arcpy.AddError(pymsg)
            #arcpy.AddError(msgs)
            arcpy.AddMessage('ERROR: {0} \n'.format(ex))

    def copyDataset(self, ras_temp_path, source_file, new_file):
        """ Copy dataset from one source to another
            Args:
                ras_temp_path: Temporary folder
                source_file: Source file
                new_file: New file
            Returns:
                new_file: New file path
        """
        if new_file is not None:
            new_file = ntpath.basename(new_file)
        else:
            new_file = ntpath.basename(source_file)
        arcpy.Copy_management(source_file, ras_temp_path + new_file)  # Copy point layer to a temporary directory
        new_file = ras_temp_path + new_file
        return new_file

    def getRExecutable(self, root_dir):
        """ Get R executable file path
            Args:
                root_dir: Root directory
            Returns:
                r_exe_file: R executable file path
        """
        r_exe_file = ""
        if os.path.exists(root_dir):
            for root, dirs, files in os.walk("C:/Program Files/R"):
                for file_name in files:
                    if file_name == "R.exe":
                        r_exe_path = os.path.join(root, file_name).replace("/", "\\")
                        if r_exe_path.endswith("\\bin\\x64\\R.exe"):
                            r_exe_file = r_exe_path
        return r_exe_file

    def createValueSample(self, parameters, in_fc_pt, ras_temp_path, in_fc, extent):
        """ Create raster cell value sample
            Args:
                parameters: Tool parameters
                in_fc_pt: Input point layer
                ras_temp_path: Temporary folder
                in_fc: Feature class input.
                extent: Feature class extent.
            Returns: None
        """
        in_val_raster = parameters[0]
        num_rows = len(in_val_raster.values)  # The number of rows in the table
        first_in_raster = ""
        sample_in_ras = []
        for row_count, in_ras_file in self.getRasterFile(in_val_raster):
            i = row_count + 1
            if extent is not None:
                arcpy.AddMessage("Clipping {0} \n".format(ntpath.basename(in_ras_file)))
                arcpy.Clip_management(in_ras_file, "{0} {1} {2} {3}".format(extent.XMin, extent.YMin, extent.XMax, extent.YMax), ras_temp_path + "ras_mask_" + str(i), in_fc, "#", "ClippingGeometry")
                if num_rows > 1:
                    if i == 1:
                        first_in_raster = ras_temp_path + "ras_mask_" + str(i)
                in_ras_mask = ras_temp_path + "ras_mask_" + str(i)
                sample_ras = self.convertRasterToASCII(num_rows, ras_temp_path, i, first_in_raster, in_ras_mask)  # Convert raster to ASCII
                sample_in_ras.append(sample_ras)
            else:
                if num_rows > 1:
                    if i == 1:
                        first_in_raster = in_ras_file
                sample_ras = self.convertRasterToASCII(num_rows, ras_temp_path, i, first_in_raster, in_ras_file)
                sample_in_ras.append(sample_ras)
        arcpy.AddMessage("Creating sample values \n")
        arcpy.gp.Sample_sa(sample_in_ras, in_fc_pt, ras_temp_path + "temp.dbf", "NEAREST")  # Process: Sample

    def convertRasterToASCII(self, num_rows, ras_temp_path, i, first_in_raster, in_raster):
        """ Converts raster to ASCII
            Args:
                num_rows: Number of input rasters
                ras_temp_path: Temporary folder
                i: Raster counter
                first_in_raster: First input raster
                in_raster: Raster with applied environment settings
            Returns:
                sample_ras: Raster to be used in creating a cell value sample table
        """
        sample_ras = ""
        if num_rows > 1:
            if i == 1:
                sample_ras = first_in_raster
                arcpy.AddMessage("Converting {0} to ASCII file {1} \n".format(first_in_raster, ras_temp_path + "tempAscii_" + str(i) + ".asc"))
                arcpy.RasterToASCII_conversion(first_in_raster, ras_temp_path + "tempAscii_" + str(i) + ".asc")
            else:
                in_mem_raster = self.applyEnvironment(first_in_raster, in_raster)
                in_mem_raster.save(ras_temp_path + "ras_envset_" + str(i))  # Save memory raster to disk
                sample_ras = ras_temp_path + "ras_envset_" + str(i)
                arcpy.AddMessage("Converting {0} to ASCII file {1} \n".format(ras_temp_path + "ras_envset_" + str(i), ras_temp_path + "tempAscii_" + str(i) + ".asc"))
                arcpy.RasterToASCII_conversion(ras_temp_path + "ras_envset_" + str(i), ras_temp_path + "tempAscii_" + str(i) + ".asc")
        else:
            sample_ras = in_raster
            arcpy.AddMessage("Converting {0} to ASCII file {1} \n".format(in_raster, ras_temp_path + "tempAscii_" + str(i) + ".asc"))
            arcpy.RasterToASCII_conversion(in_raster, ras_temp_path + "tempAscii_" + str(i) + ".asc")
        return sample_ras

    def applyEnvironment(self, first_in_raster, in_raster):
        """ Apply environment settings
            Args:
                first_in_raster: First input raster
                in_raster: Raster with applied environment settings
            Returns: None
        """
        arcpy.env.extent = first_in_raster
        arcpy.env.cellSize = first_in_raster
        arcpy.env.outputCoordinateSystem = first_in_raster
        arcpy.env.snapRaster = first_in_raster
        arcpy.AddMessage("Applying environment settings for {0}".format(in_raster))
        in_raster = arcpy.Raster(in_raster)
        return arcpy.sa.ApplyEnvironment(in_raster)

    def deleteTempFile(self, parameters, ras_temp_path):
        """ Delete temporary files
            Args:
                parameters: Tool parameters
                ras_temp_path: Temporary folder
            Returns: None
        """
        for i in xrange(1, len(parameters[0].values)):
            if arcpy.Exists(ras_temp_path + "ras_mask_" + str(i)):
                super(LandSimilarity, self).deleteFile(ras_temp_path, "ras_mask_" + str(i))  # Delete temporary files
            if arcpy.Exists(ras_temp_path + "ras_envset_" + str(i)):
                super(LandSimilarity, self).deleteFile(ras_temp_path, "ras_envset_" + str(i))  # Delete temporary files

    def writeToCSV(self, in_fc_pt, out_csv):
        """ Write feature class table to CSV file
            Args:
                in_fc_pt: Input point layer
                out_csv: Output CSV file
            Returns: None
        """
        # Get field names
        fields = arcpy.ListFields(in_fc_pt)
        field_names = [field.name for field in fields]
        arcpy.AddMessage("Exporting {0} table to {1} \n".format(in_fc_pt, out_csv))
        with open(out_csv, 'wb') as f:
            w = csv.writer(f)
            w.writerow(field_names)  # Write field names to CSV file as headers
            # Search through rows and write values to CSV
            for row in arcpy.SearchCursor(in_fc_pt):
                field_vals = [row.getValue(field.name) for field in fields]
                w.writerow(field_vals)
            del row

    def createRScript(self, parameters, ras_temp_path):
        """ Create R script
            Args:
                parameters: Tool parameters
                ras_temp_path: Temporary folder
            Returns: None
        """
        i = 0
        in_val_raster = parameters[0]
        #  Get number of rasters
        for row_count, in_ras_file in self.getRasterFile(in_val_raster):
            row_count += 1
            i = row_count
        with open(ras_temp_path + 'out_script.r', 'w') as f:
            cwd = os.path.dirname(os.path.realpath(__file__))  # Toolbox current working directory
            cwd = self.getDirectoryPath(cwd)  # Get subdirectory path
            similar_script = self.getFilePath(cwd, "similarity_")  # Get script path
            # read_script = self.getFilePath(cwd, "readAscii")
            # write_script = self.getFilePath(cwd, "writeAscii")
            # Write out a script
            # f.write('source("' + similar_script + '"); similarityAnalysis(' + str(i) + ',"' + read_script + '","' + write_script + '","' + ras_temp_path + '") \n')
            f.write('source("' + similar_script + '"); similarityAnalysis(' + str(i) + ', "' + ras_temp_path + '") \n')

    def getDirectoryPath(self, cwd):
        """ Get subdirectory path from the toolbox directory
            Args:
                cwd: Current toolbox directory
            Returns: Script subdirectory full path
        """
        for name in os.listdir(cwd):
            if os.path.isdir(os.path.join(cwd, name)):
                if name == "R_Scripts":
                    return os.path.join(cwd, name)

    def getFilePath(self, cwd, start_char):
        """ Get file path from the toolbox directory
            Args:
                cwd: Current script directory
                start_char: File name start character
            Returns: File full path
        """
        for f in os.listdir(cwd):
            if not os.path.isdir(os.path.join(cwd, f)):
                if f.startswith(start_char) and f.endswith(".r"):
                    return os.path.join(cwd, f).replace("\\", "/")

    def runCommand(self, r_exe_path, ras_temp_path):
        """ Run R command
            Args:
                r_exe_path: Executable R file
                ras_temp_path: Temporary folder
            Returns: None
        """
        r_cmd = '"' + r_exe_path + '" --vanilla --slave --file="' + ras_temp_path + 'out_script.r"'  # r command
        arcpy.AddMessage("Running similarity analysis \n")
        subprocess.call(r_cmd, shell=False)  # Open shell and run R command

    def asciiToRasterConversion(self, parameters, ras_temp_path):
        """ ASCII to raster conversion
            Args:
                Parameters: Tool parameters
                ras_temp_path: Temporary folder
            Returns: None
        """
        r_exe_file = parameters[3].valueAsText.replace("\\", "/")  # Get R.exe file path
        out_mnobis_ras = parameters[4].valueAsText.replace("\\", "/")  # Get mahalanobis output
        out_mess_ras = parameters[5].valueAsText.replace("\\", "/")  # Get mess output
        arcpy.AddMessage("ASCII conversion of {0} to raster {1} \n".format(ras_temp_path + "MahalanobisDist.asc", out_mnobis_ras))
        arcpy.ASCIIToRaster_conversion(ras_temp_path + "MahalanobisDist.asc", out_mnobis_ras, "INTEGER")
        if os.path.isfile(ras_temp_path + "MESS.asc"):
            arcpy.AddMessage("ASCII conversion of {0} to raster {1} \n".format(ras_temp_path + "MESS.asc", out_mess_ras))
            arcpy.ASCIIToRaster_conversion(ras_temp_path + "MESS.asc", out_mess_ras, "INTEGER")  # Process ASCII to raster
        else:
            r_version = r_exe_file.rsplit("/", 3)[0]
            r_modEvA = r_version + "/library/modEvA"
            if not os.path.isdir(r_modEvA):
                arcpy.AddError('Error: {0} package missing. Connect to the internet and run the tool again. Alternatively download and install "modEvA" package. \n'.format(r_modEvA))

    def getRasterFile(self, in_val_raster):
        """ Get row statistics parameters from the value table
            Args:
                in_val_raster: Multi value input raster
            Returns:
                row_count: Input raster counter
                in_ras_file: Input raster file from the multi value parameter
        """
        for i, lst in enumerate(in_val_raster.valueAsText.split(";")):
            row_count = i
            lst_val = super(LandSimilarity, self).formatValueTableData(lst)  # Clean mutli value data
            in_ras_file = lst_val[0]
            in_ras_file = in_ras_file.replace("\\", "/")
            yield row_count, in_ras_file  # return values
