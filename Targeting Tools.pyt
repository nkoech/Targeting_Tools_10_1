"""
    Name:       Targeting Tools

    Authors:    International Center for Tropical Agriculture - CIAT
                Commonwealth Scientific and Industrial Research Organisation - CSIRO

    Notes:      Tool-1: Identify land suitable to cultivate a certain crop.
                Tool-2: Identify areas that have similar biophysical characteristics to
                        the location currently under a certain type crop.
                Tool-3: Calculate statistics from the land suitability output raster
                        and return the result in a CSV file format.

                Fully tested in ArcGIS 10.1.
                Requires Spatial Analyst extension

    Created:    May 2015
    Modified:   September 2015
"""

import os
import sys
import arcpy
import shutil
import ntpath
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
        self.canRunInBackground = False
        # List of tool classes associated with this toolbox
        self.tools = [LandSuitability, LandStatistics]


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

    def getInputFc(self, parameters):
        """ Gets the input MXD
            Args:
                parameters: Tool parameters object
            Return:
                in_fc_file: Input feature class file
                in_fc: Input feature class parameter
        """
        in_fc = parameters[1].valueAsText.replace("\\","/")
        in_fc_file = ntpath.basename(in_fc)
        return {"in_fc": in_fc, "in_fc_file": in_fc_file}


class LandSuitability(TargetingTool):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Land Suitability"
        self.description = ""
        self.canRunInBackground = False
        self.parameters = [
            parameter("Input raster", "in_raster", "Value Table"),
            parameter("Output extent", "out_extent", "Feature Layer", parameterType='Optional'),
            parameter("Output raster", "out_raster", 'Raster Layer', direction='Output')
        ]

    def getParameterInfo(self):
        """Define parameter definitions"""
        self.parameters[0].columns = [['Raster Layer', 'Rasters'], ['Double', 'Min Value'], ['Double', 'Max Value'], ['Double', 'Optimal From'], ['Double', 'Optimal To'], ['String', 'Combine-Yes/No']]
        return self.parameters

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
        # End of value table, now update update value table last row with new column data
        if opt_from_val == "#" and opt_to_val == "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, "#", "#", "#"))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val == "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, opt_from_val, "#", "#"))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val != "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, "#", opt_to_val, "#"))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val == "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, "#", "#", ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val != "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, opt_from_val, opt_to_val, "#"))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val != "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, "#", opt_to_val, ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val == "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, opt_from_val, "#", ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val != "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine))
            in_raster.value = vtab.exportToString()
        else:
            pass

    def updateMessages(self, parameters):
        """ Modify the messages created by internal validation for each tool
            parameter.  This method is called after internal validation.
            Args:
                parameters: Parameters from the tool.
            Returns: Internal validation messages.
        """
        if parameters[0].value:
            if parameters[0].altered:
                in_raster = parameters[0]
                num_rows = len(in_raster.values)  # The number of rows in the table
                ras_max_min = True
                ras_ref = []
                i = 0
                # Get values from the generator function to show update messages
                for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                    i += 1
                    # Set raster spatial reference errors
                    if i == num_rows:
                        last_spataial_ref = arcpy.Describe(ras_file).SpatialReference   # Get spatial reference
                        for ref in ras_ref:
                            warning_msg = "Raster data not in the  spatial reference"
                            self.setSpatialError(last_spataial_ref, ref, in_raster, warning_msg)
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
                    else:
                        pass
            # Set feature class spatial reference errors
            if parameters[1].value:
                if parameters[1].altered:
                    in_fc_param = parameters[1]
                    in_fc = parameters[1].valueAsText.replace("\\","/")
                    in_fc_spataial_ref = arcpy.Describe(in_fc).SpatialReference
                    warning_msg = "Output extent data spatial reference does not match with input raster"
                    self.setSpatialError(in_fc_spataial_ref, ras_ref[-1], in_fc_param, warning_msg)
            # Set ESRI grid output file size error
            if parameters[2].value:
                if parameters[2].altered:
                    out_ras = parameters[2].valueAsText.replace("\\", "/")
                    out_ras_file, out_ras_file_ext = os.path.splitext(out_ras)
                    if out_ras_file_ext != ".tif":
                        if len(ntpath.basename(out_ras)) > 13:
                            in_raster.setErrorMessage("Output raster: The length of the grid base name in {0} is longer than 13.".format(out_ras.replace("/", "\\")))
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
                in_fc = super(LandSuitability, self).getInputFc(parameters)["in_fc"]
                #in_fc = self.getInputFc(parameters)["in_fc"]
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
                arcpy.management.Delete(ras_temp_path + "ras_min4_" + str(j))
                arcpy.management.Delete(ras_temp_path + "ras_max4_" + str(j))

            ras_temp_file = self.setCombineFile(in_raster, ras_temp_path)  # Build a list with lists of temporary raster files
            out_ras_temp = 1  # Initial temporary raster value
            n = 0
            n_ras = 0  # Number of rasters for geometric mean calculation
            # Overlay minimum rasters to create a suitability raster/map
            for item in ras_temp_file:
                if len(item) > 1:
                    n += 1
                    arcpy.AddMessage("Generating maximum values from minimum values raster files")
                    arcpy.gp.CellStatistics_sa(item, ras_temp_path + "rs_MxStat_" + str(n), "MAXIMUM", "DATA")
                else:
                    for f in item:
                        n_ras += 1
                        arcpy.AddMessage("Multiplying file {0} with input raster\n".format(ntpath.basename(f)))
                        out_ras_temp = out_ras_temp * arcpy.Raster(f)

            if arcpy.Exists(out_ras_temp):
                arcpy.AddMessage("Saving Temporary Output\n")
                out_ras_temp.save(ras_temp_path + "rs_TxTemp")
                out_ras_temp = arcpy.Raster(ras_temp_path + "rs_TxTemp")  # Initial temporary raster file for the next calculation

            if n >= 1:
                # Get times temp file and multiply with maximum value statistics output saved in a temporary directory
                for j in range(0, n):
                    n_ras += 1
                    j += 1
                    arcpy.AddMessage("Multiplying file {0} with input raster {1}\n".format(out_ras_temp, "rs_MxStat_" + str(j)))
                    out_ras_temp = out_ras_temp * arcpy.Raster(ras_temp_path + "rs_MxStat_" + str(j))

            arcpy.AddMessage("Generating suitability output\n")
            out_ras_temp = out_ras_temp ** 1 / float(n_ras)  # Calculate geometric mean
            arcpy.AddMessage("Saving suitability output\n")
            out_ras_temp.save(out_ras)
            arcpy.AddMessage("Suitability output saved!\n")
            arcpy.AddMessage("Deleting temporary folder\n")
            shutil.rmtree(ras_temp_path)
            self.loadOutput(parameters, out_ras)  # Load output to current MXD
            return
        except Exception as ex:
            arcpy.AddMessage('ERROR: {0}'.format(ex))

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
                arcpy.AddMessage("Clipping {0}\n".format(ntpath.basename(ras_file)))
                arcpy.Clip_management(ras_file, "{0} {1} {2} {3}".format(extent.XMin, extent.YMin, extent.XMax, extent.YMax), ras_temp_path + "ras_mask1_" + str(i), in_fc, "#", "ClippingGeometry")
                # Masked raster minus operation
                self.rasterMinus(ras_temp_path + "ras_mask1_" + str(i), minVal, "ras_min1_" + str(i), ras_temp_path, min_ras=True)
                self.rasterMinus(ras_temp_path + "ras_mask1_" + str(i), maxVal, "ras_max1_" + str(i), ras_temp_path, min_ras=False)
                arcpy.management.Delete(ras_temp_path + "ras_mask1_" + str(i))  # Delete temporary raster files
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
            arcpy.AddMessage("Calculating {0} - {1}\n".format(ntpath.basename(ras_file), val))
            arcpy.gp.Minus_sa(ras_file, val, ras_temp_path + ras_output)
        else:
            arcpy.AddMessage("Calculating {0} - {1}\n".format(val, ntpath.basename(ras_file)))
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
        arcpy.AddMessage("Creating conditional output for {0}\n".format(ras_input))
        arcpy.gp.Con_sa(ras_temp_path + ras_input, comp_val, ras_temp_path + ras_output, ras_temp_path + ras_input, "\"Value\" " + comp_oper + comp_val)
        arcpy.management.Delete(ras_temp_path + ras_input)  # Delete temporary raster files

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
                arcpy.AddMessage("Calculating {0} / {1}\n".format(ras_input, "1"))
                arcpy.gp.Divide_sa(ras_temp_path + ras_input, "1", ras_temp_path + ras_output)
            else:
                arcpy.AddMessage("Calculating {0} / {1} - {2}\n".format(ras_input, opt_val, m_val))
                arcpy.gp.Divide_sa(ras_temp_path + ras_input, str(float(opt_val) - float(m_val)), ras_temp_path + ras_output)
        else:
            if float(m_val) - float(opt_val) == 0:
                arcpy.AddMessage("Calculating {0} / {1}\n".format(ras_input, "1"))
                arcpy.gp.Divide_sa(ras_temp_path + ras_input, "1", ras_temp_path + ras_output)
            else:
                arcpy.AddMessage("Calculating {0} / {1} - {2}\n".format(ras_input, m_val, opt_val))
                arcpy.gp.Divide_sa(ras_temp_path + ras_input, str(float(m_val) - float(opt_val)), ras_temp_path + ras_output)
        arcpy.management.Delete(ras_temp_path + ras_input)

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
                else:
                    pass
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
            ras_combine = lst.split()[-1]  # Get combine option
            row_count = i
            if ras_max_min:
                opt_from_val = lst.split()[-3]  # Get crop optimum value from
                opt_to_val = lst.split()[-2]  # Get crop optimum value to
                ras_file = lst.rsplit(' ', 5)[0]  # Get raster file path
                ras_file = ras_file.replace("\\","/")
                if lst.split()[-5] == "#" or lst.split()[-4] == "#" or ras_combine == "#":
                    paramInRaster = arcpy.Raster(ras_file.replace("'", ""))  # Replace quote on path with null
                    minVal = paramInRaster.minimum  # Minimum raster value
                    maxVal = paramInRaster.maximum  # Maximum raster value
                    ras_combine = "No"
                    yield ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count  # Return output
                else:
                    minVal = lst.split()[-5]  # Minimum raster value
                    maxVal = lst.split()[-4]  # Maximum raster value
                    if row_count == 0:  # Set first row to "No"
                        ras_combine = "No"
                        yield ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count
                    else:
                        yield ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count
            else:
                yield ras_combine

    def loadOutput(self, parameters, out_ras):
        """ Loads output to the current MXD
            Args:
                parameters: Tool parameters object
                out_ras: Land suitability layer
            Return: None
        """
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd, "*")[0]  # Get the first data frame
        # Load raster output
        lyr = arcpy.mapping.Layer(out_ras)
        arcpy.mapping.AddLayer(df, lyr, "AUTO_ARRANGE")

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

    def setSpatialError(self, in_spatial_ref, ref, in_data, warning_msg):
        """ Sets spatial error message
            Args:
                in_spatial_ref: Input data spatial reference
                ref: Input raster spatial reference
                in_data: Input data - raster and feature class
                warnign_msg: Spatial reference warning message
            Return: None
        """
        if in_spatial_ref.Type != ref.Type:  # Check difference in spatial reference type
            in_data.setWarningMessage(warning_msg)
        elif in_spatial_ref.Type != "Geographic":
            if in_spatial_ref.PCSCode != ref.PCSCode:  # Check projection code
                in_data.setWarningMessage(warning_msg)
        else:
            pass


class LandStatistics(TargetingTool):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Land Statistics"
        self.description = ""
        self.canRunInBackground = False
        self.parameters = [
            parameter("Input raster zone data", "in_raszone", "Raster Layer"),
            parameter("Input feature zone data", "in_fczone", "Feature Layer", parameterType='Optional'),
            #parameter("Feature name field", "fval_field", "Field", parameterType="Optional"),
            parameter("Feature name field", "fval_field", "String", parameterType="Optional"),
            parameter("Input value raster", "in_val_ras", "Raster Layer"),
            parameter("Output table", "out_table", "Table", direction="Output"),
            parameter("Ignore NoData in calculations", "nodata_calc", "Boolean", parameterType='Optional'),
            parameter("Statistics type", "stat_type", "String", parameterType="Optional")
        ]

    def getParameterInfo(self):
        """Define parameter definitions"""
        self.parameters[1].filter.list = ["Polygon"]  # Geometry type filter
        #self.parameters[2].filter.list = ["Short", "Long", "Float", "Single", "Double", "Text", "Date", "OID"]
        #self.parameters[2].parameterDependencies = [self.parameters[1].name]
        self.parameters[5].value = True  # Default value
        self.parameters[6].filter.type = "ValueList"
        self.parameters[6].filter.list = ["ALL", "MEAN", "MAJORITY", "MAXIMUM", "MEDIAN", "MINIMUM", "MINORITY", "RANGE", "STD", "SUM", "VARIETY", "MIN_MAX", "MEAN_STD", "MIN_MAX_MEAN"]
        self.parameters[6].value = "ALL"  # Default value
        return self.parameters

    def updateParameters(self, parameters):
        """ Modify the values and properties of parameters before internal
            validation is performed.  This method is called whenever a parameter
            has been changed.
            Args:
                parameters: Parameters from the tool.
            Returns: Parameter values.
        """
        if parameters[1].value and parameters[1].altered:
            in_fc_field = [f.name for f in arcpy.ListFields(parameters[1].value, field_type="String")]  # Get string field headers
            parameters[2].filter.list = in_fc_field  # Updated filter list
            if parameters[2].value is None:
                parameters[2].value = in_fc_field[0]  # Set initial field value
        else:
            parameters[2].filter.list = []  # Empty filter list
            parameters[2].value = ""  # Reset field value to None
        return

    def updateMessages(self, parameters):
        """ Modify the messages created by internal validation for each tool
            parameter.  This method is called after internal validation.
            Args:
                parameters: Parameters from the tool.
            Returns: Internal validation messages.
        """
        return

    def execute(self, parameters, messages):
        """ Execute functions to process input raster.
            Args:
                parameters: Parameters from the tool.
                messages: Internal validation messages
            Returns: Land statistics table.
        """
        try:
            in_raster = parameters[0].valueAsText.replace("\\","/")
            out_stat_table = parameters[4].valueAsText.replace("\\","/")  # Get output file path
            ras_temp_path = ntpath.dirname(out_stat_table)  # Get path without file name
            ras_temp_path += "/Temp/"

            if not os.path.exists(ras_temp_path):
                os.makedirs(ras_temp_path)  # Create new directory

            # Feature class rasterization and overlay
            if parameters[1].value:
                in_fc = super(LandStatistics, self).getInputFc(parameters)["in_fc"]  # Get feature file path
                in_fc_file = super(LandStatistics, self).getInputFc(parameters)["in_fc_file"]  # Get feature file name
                in_fc_field = parameters[2].valueAsText
                arcpy.AddMessage("Converting polygon {0} to raster\n".format(in_fc_file))
                arcpy.PolygonToRaster_conversion(in_fc, in_fc_field, ras_temp_path + "ras_poly", "CELL_CENTER", "NONE", in_raster)  # Convert polygon to raster
                arcpy.gp.Times_sa(ras_temp_path + "ras_poly", "1000", ras_temp_path + "ras_multi")  # Process: Times
                self.zonalStatisticsInit(in_raster, ras_temp_path, out_stat_table, parameters, ras_add=True)
                self.updateZonalStatisticsTable(in_fc_field, ras_temp_path, out_stat_table)
            else:
                self.zonalStatisticsInit(in_raster, ras_temp_path, out_stat_table, parameters, ras_add=False)
            shutil.rmtree(ras_temp_path)
            return
        except Exception as ex:
            arcpy.AddMessage('ERROR: {0}'.format(ex))

    def zonalStatisticsInit(self, in_raster, ras_temp_path, out_stat_table, parameters, ras_add):
        """ Initialize the zonal statistics calculation process
            Args:
                in_raster: Input land suitability raster.
                ras_temp_path: Temporary folder
                out_stat_table: Output zonal statistics table
                parameters: Tool parameters
                ras_add: Variable to hint if another process should take place or not
            Returns: None.
        """
        in_val_raster = parameters[3].valueAsText.replace("\\","/")
        data_val = parameters[5].value
        stats_type = parameters[6].valueAsText
        if ras_add:
            arcpy.AddMessage("Initializing land statistics")
            arcpy.gp.Plus_sa(ras_temp_path + "ras_multi", in_raster, ras_temp_path + "ras_plus")  # Process: Plus
            arcpy.management.Delete(ras_temp_path + "ras_multi")
            in_raster = ras_temp_path + "ras_plus"
            self.calculateZonalStatistics(in_raster, in_val_raster, data_val, stats_type, out_stat_table)
            arcpy.management.Delete(ras_temp_path + "ras_plus")
        else:
            self.calculateZonalStatistics(in_raster, in_val_raster, data_val, stats_type, out_stat_table)

    def calculateZonalStatistics(self, in_raster, in_val_raster, data_val, stats_type, out_stat_table):
        """ Calculate statistics on a given area  of interest - zone
            Args:
                in_raster: Input land suitability raster or plus raster
                in_val_raster: Raster that contains the values on which to calculate a statistic.
                data_val: Denotes whether NoData values in the Value input will influence the results or not
                stats_type: Statistic type to be calculated
                out_stat_table: Output zonal statistics table
            Returns: Saves a dbf table to memory
        """

        if data_val:
            arcpy.AddMessage("Calculating land statistics")
            arcpy.gp.ZonalStatisticsAsTable_sa(in_raster, "Value", in_val_raster, out_stat_table, "DATA", stats_type)  # Process: Zonal Statistics as Table
        else:
            arcpy.AddMessage("Calculating land statistics")
            arcpy.gp.ZonalStatisticsAsTable_sa(in_raster, "Value", in_val_raster, out_stat_table, "NODATA", stats_type)  # Process: Zonal Statistics as Table

    def updateZonalStatisticsTable(self, in_fc_field, ras_temp_path, out_stat_table):
        """ Edit zonal statistics output table
            Args:
                in_fc_field: Feature name field
                ras_temp_path: Temporary folder
                out_stat_table: Output zonal statistics table
        """
        ras_poly = ras_temp_path + "ras_poly"
        # Add fields to table
        if not arcpy.ListFields(out_stat_table, in_fc_field):
            arcpy.AddField_management(out_stat_table, in_fc_field, "STRING")
            arcpy.AddField_management(out_stat_table, "POLY_VAL", "LONG")
            arcpy.AddField_management(out_stat_table, "LAND_RANK", "LONG")

        # Process: Calculate Field
        arcpy.CalculateField_management(out_stat_table, "POLY_VAL", "([VALUE] - Right([VALUE] , 3)) / 1000", "VB", "")
        arcpy.CalculateField_management(out_stat_table, "LAND_RANK", "Right([VALUE] , 3)", "VB", "")
        self.addValuesZonalStatisticsTable(ras_poly, out_stat_table)  # Add values to table

    def addValuesZonalStatisticsTable(self, ras_poly, out_stat_table):
        """ Copy field values from one table to another
            Args:
                ras_poly: Rasterized polygon
                ras_temp_path: Temporary folder
                out_stat_table: Output zonal statistics table
        """

        with arcpy.da.SearchCursor(ras_poly, ["VALUE"]) as cursor:
            for row in cursor:
                sql_exp1 = "VALUE = " + str(row[0])  # SQL expression
                sql_exp2 = "POLY_VAL = " + str(row[0])
                cursor2 = arcpy.da.SearchCursor(ras_poly, ["ADM2_NAME"], sql_exp1)
                for row2 in cursor2:
                    update_val = row2[0]
                    with arcpy.da.UpdateCursor(out_stat_table, ["ADM2_NAME"], sql_exp2) as cursor3:  # Update values in the second table
                        for row3 in cursor3:
                            row3[0] = update_val
                            cursor3.updateRow(row3)

        arcpy.DeleteField_management(out_stat_table, "POLY_VAL")  # Process: Delete Field
        arcpy.management.Delete(ras_poly)  # Delete polygon