"""
    Name:       Targeting Tools

    Authors:    International Center for Tropical Agriculture - CIAT
                Commonwealth Scientific and Industrial Research Organisation - CSIRO

    Notes:      Tool-1: Identify land suitable to cultivate a certain crop.
                Tool-2: Identify areas that have similar biophysical characteristics to
                        the location currently under a certain type crop.
                Tool-3: Calculate statistics of a raster and return the result in a CSV
                        file format.

                Fully tested in ArcGIS 10.1.
                Requires Spatial Analyst extension

    Created:    May 2015
    Modified:   June 2015
"""

import arcpy
import ntpath
import sys
from itertools import *
import shutil
import os

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
        self.tools = [GetSuitableLand]


class GetSuitableLand(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Land Suitability"
        self.description = ""
        self.canRunInBackground = False
        self.parameters = [
            parameter("Input Rasters", "in_raster", "Value Table"),
            parameter("Output Raster", "out_raster", 'Raster Layer', direction='Output')
        ]

    def getParameterInfo(self):
        """Define parameter definitions"""
        self.parameters[0].columns = [['Raster Layer', 'Rasters'], ['Double', 'Min Value'], ['Double', 'Max Value'], ['Double', 'Optimal From'], ['Double', 'Optimal To'], ['String', 'Combine']]
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        spatialAnalystCheckedOut = False
        if arcpy.CheckExtension('Spatial') == 'Available':
            arcpy.CheckOutExtension('Spatial')
            spatialAnalystCheckedOut = True
        else:
            arcpy.AddMessage('ERROR: At a minimum, this script requires the Spatial Analyst Extension to run \n')
            sys.exit()
        return spatialAnalystCheckedOut

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        if parameters[0].value:
            in_raster = parameters[0]
            vtab = arcpy.ValueTable(len(in_raster.columns))  # Number of value table columns
            ras_max_min = True
            # Get values from the generator function and update value table
            for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                self.updateValueTable(in_raster, opt_from_val, opt_to_val, ras_combine, vtab, ras_file, minVal, maxVal)
        return

    def updateValueTable(self, in_raster, opt_from_val, opt_to_val, ras_combine, vtab, ras_file, minVal, maxVal):
        # End of value table, now update update value table last row with new column data
        if opt_from_val == "#" and opt_to_val == "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, "", "", ""))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val == "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, opt_from_val, "", ""))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val != "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, "", opt_to_val, ""))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val == "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, "", "", ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val != "#" and ras_combine == "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, opt_from_val, opt_to_val, ""))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val != "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, "", opt_to_val, ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val == "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, opt_from_val, "", ras_combine))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val != "#" and ras_combine != "#":
            vtab.addRow('{0} {1} {2} {3} {4} {5}'.format(ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine))
            in_raster.value = vtab.exportToString()
        else:
            pass

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        if parameters[0].value:
            in_raster = parameters[0]
            num_rows = len(in_raster.values)  # The number of rows in the table
            ras_max_min = True
            ras_ref = []
            i = 0
            # Get values from the generator function to show update messages
            for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                i += 1
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
                # Get spatial reference system errors
                if i == num_rows:
                    last_spataial_ref = arcpy.Describe(ras_file).SpatialReference   # Get spatial reference
                    for ref in ras_ref:
                        if last_spataial_ref.Type != ref.Type:  # Check difference in spatial reference type
                            in_raster.setWarningMessage("All raster data must be in the same spatial reference")
                        elif last_spataial_ref.Type != "Geographic":
                            if last_spataial_ref.PCSCode != ref.PCSCode:  # Check projection code
                                in_raster.setWarningMessage("All raster data must be in the same projection system")
                        else:
                            pass
                else:
                    spatial_ref = arcpy.Describe(ras_file).SpatialReference  # Get spatial reference of rasters in value table
                    ras_ref.append(spatial_ref)
        return

    def execute(self, parameters, messages):
        """Geoprocessing logic."""

        try:
            i = 0
            ras_max_min = True
            in_raster = parameters[0]
            num_rows = len(parameters[0].values)  # The number of rows in the table
            out_ras = parameters[1].valueAsText.replace("\\","/")  # Get output file path
            ras_temp_path = ntpath.dirname(out_ras)
            ras_temp_path += "/Temp/"

            if not os.path.exists(ras_temp_path):  # Create new directory
                os.makedirs(ras_temp_path)

            # Raster minus operation
            for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                i += 1
                self.rasterMinus(ras_file, minVal, "ras_min1_" + str(i), ras_temp_path, min_ras=True)
                self.rasterMinus(ras_file, maxVal, "ras_max1_" + str(i), ras_temp_path, min_ras=False)
            i = 0

            # Initialize raster condition operation
            self.rasterConditionInit(num_rows, "ras_min1_", "ras_min2_", "ras_max1_", "ras_max2_", ras_temp_path, "< ", "0")

            # Raster divide operation
            for ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count in self.getRowValue(in_raster, ras_max_min):
                i += 1
                self.rasterDivide(opt_from_val, minVal, "ras_min2_" + str(i), "ras_min3_" + str(i), ras_temp_path, min_ras=True)
                self.rasterDivide(opt_to_val, maxVal, "ras_max2_" + str(i), "ras_max3_" + str(i), ras_temp_path, min_ras=False)

            # Initialize raster condition operation
            self.rasterConditionInit(num_rows, "ras_min3_", "ras_min4_", "ras_max3_", "ras_max4_", ras_temp_path, "> ", "1")

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
            # Overlay minimum rasters to create a suitability raster/map
            for item in ras_temp_file:
                if len(item) > 1:
                    n += 1
                    self.maxRasterValueCalc(item, ras_temp_path, n)  # Extract maximum
                else:
                    for f in item:
                        arcpy.AddMessage("Multiplying file {0} with input raster\n".format(ntpath.basename(f)))
                        out_ras_temp = out_ras_temp * arcpy.Raster(f)

            if arcpy.Exists(out_ras_temp):
                arcpy.AddMessage("Saving Temporary Output\n")
                out_ras_temp.save(ras_temp_path + "rs_TxTemp")
                out_ras_temp = arcpy.Raster(ras_temp_path + "rs_TxTemp")   # Initial temporary raster file for the next calculation

            if n >= 1:
                # Get times temp file and multiply with maximum value statistics output saved in a temporary directory
                for j in range(0, n):
                    j += 1
                    arcpy.AddMessage("Multiplying file {0} with input raster {1}\n".format(out_ras_temp, "rs_MxStat_" + str(j)))
                    out_ras_temp = out_ras_temp * arcpy.Raster(ras_temp_path + "rs_MxStat_" + str(j))

            arcpy.AddMessage("Saving Output\n")
            out_ras_temp.save(out_ras)
            arcpy.AddMessage("Deleting temporary folder\n")
            shutil.rmtree(ras_temp_path)
            arcpy.AddMessage("Output saved!\n")
            return
        except Exception as ex:
            arcpy.AddMessage('ERROR: {0}'.format(ex))

    def rasterMinus(self, ras_file, val, ras_output, ras_temp_path, min_ras):
        """ Handles raster minus operation
            Args:
                ras_file: Input raster file
                val: Minimum and maximum value
                ras_output: Raster file output
                min: Boolean to determine if minimum value is available or not
            Return:
                Raster layer
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
                Raster layer
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
                min: Boolean to determine if minimum value is available or not
            Return:
                Raster layer
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

    def maxRasterValueCalc(self, item, ras_temp_path, n):
        """ Extract maximum values from minimum temporary rasters
            Args:
                item: Temporary raster files
            Returns: Saves maximum value raster in a temporary directory
        """
        max_stat_files = ""
        for ras_file in item:
            if max_stat_files:
                max_stat_files += ";" + ras_file
            else:
                max_stat_files += ras_file
        arcpy.AddMessage("Generating maximum values from minimum values raster files")
        arcpy.gp.CellStatistics_sa(max_stat_files, ras_temp_path + "rs_MxStat_" + str(n), "MAXIMUM", "DATA")

    def getRowValue(self, in_raster, ras_max_min):
        """ Gets row values and calculate raster maximum and minimum values.
            Args:
                in_raster: Value table parameter with rows accompanied by columns.
                ras_max_min: A parameter that determines whether minimum and maximum value should be calculated or not.
            Returns:
                Optimal From, Optimal To, raster file path, raster minimum value and maximum value
        """
        for i, lst in enumerate(in_raster.valueAsText.split(";")):
            ras_file = lst.rsplit(' ', 5)[0]  # Get raster file path
            paramInRaster = arcpy.Raster(ras_file.replace("'", ""))
            opt_from_val = lst.split()[-3]  # Get crop optimum value from
            opt_to_val = lst.split()[-2]  # Get crop optimum value to
            ras_combine = lst.split()[-1]  # Get combine option
            row_count = i
            if ras_max_min:
                if lst.split()[-5] == "#" or lst.split()[-4] == "#":
                    minVal = paramInRaster.minimum  # Minimum raster value
                    maxVal = paramInRaster.maximum  # Maximum raster value
                    yield ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count  # Return output
                else:
                    minVal = lst.split()[-5]  # Minimum raster value
                    maxVal = lst.split()[-4]  # Maximum raster value
                    yield ras_file, minVal, maxVal, opt_from_val, opt_to_val, ras_combine, row_count
            else:
                yield ras_combine
