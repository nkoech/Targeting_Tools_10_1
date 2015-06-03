"""
    Name:       Targeting Tools

    Authors:    International Center for Tropical Agriculture - CIAT
                Commonwealth Scientific and Industrial Research Organisation - CSIRO

    Notes:      Tool-1: Identify land suitable to cultivate a certain crop.
                Tool-2: Identify areas that have similar biophysical characteristics to the location currently under cropping.

                Fully tested in ArcGIS 10.1.
                Requires Spatial Analyst extension

    Created:    May 2015
    Modified:   June 2015
"""

import arcpy
import ntpath
import sys

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
        self.parameters[0].columns = [['Raster Layer', 'Rasters'], ['Double', 'Min Value'], ['Double', 'Max Value'], ['Double', 'Optimal From'], ['Double', 'Optimal To']]
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
            num_rows = len(in_raster.values)  # The number of rows in the table
            ras_max_min = True
            i = 0
            # Get values from the generator function and update value table
            for opt_from_val, opt_to_val, ras_file, minVal, maxVal in self.getRowValue(in_raster, ras_max_min):
                i += 1
                if i == num_rows:
                    self.updateValueTable(in_raster, opt_from_val, opt_to_val, vtab, ras_file, minVal, maxVal)
                else:
                    self.updateValueTable(in_raster, opt_from_val, opt_to_val, vtab, ras_file, minVal, maxVal)
        return

    def updateValueTable(self, in_raster, opt_from_val, opt_to_val, vtab, ras_file, minVal, maxVal):
        # End of value table, now update update value table last row with new column data
        if opt_from_val == "#" and opt_to_val == "#":
            vtab.addRow('{0} {1} {2} {3} {4}'.format(ras_file, minVal, maxVal, "", ""))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val == "#":
            vtab.addRow('{0} {1} {2} {3} {4}'.format(ras_file, minVal, maxVal, opt_from_val, ""))
            in_raster.value = vtab.exportToString()
        elif opt_from_val == "#" and opt_to_val != "#":
            vtab.addRow('{0} {1} {2} {3} {4}'.format(ras_file, minVal, maxVal, "", opt_to_val))
            in_raster.value = vtab.exportToString()
        elif opt_from_val != "#" and opt_to_val != "#":
            vtab.addRow('{0} {1} {2} {3} {4}'.format(ras_file, minVal, maxVal, opt_from_val, opt_to_val))
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
            for opt_from_val, opt_to_val, ras_file, minVal, maxVal in self.getRowValue(in_raster, ras_max_min):
                i += 1
                if opt_from_val == "#":
                    in_raster.setErrorMessage("Crop optimal value \"from\" is missing")
                elif opt_to_val == "#":
                    in_raster.setErrorMessage("Crop optimal value \"to\" is missing")
                elif opt_to_val and opt_from_val == "#":
                    in_raster.setErrorMessage("Crop optimal value \"to\" and \"from\" are missing")
                elif float(opt_from_val) < minVal:
                    in_raster.setWarningMessage("Crop optimal value {0} is less than the minimum value {1}".format(opt_from_val, minVal))
                elif float(opt_from_val) > maxVal:
                    in_raster.setErrorMessage("Crop optimal value {0} is greater than the maximum value {1}".format(opt_from_val, maxVal))
                elif float(opt_from_val) > float(opt_to_val):
                    in_raster.setErrorMessage("Crop optimal value \"from\" is greater than crop optimal value \"to\"")
                elif float(opt_to_val) < minVal:
                    in_raster.setErrorMessage("Crop optimal value {0} is less than the minimum value {1}".format(opt_to_val, minVal))
                elif float(opt_to_val) > maxVal:
                    in_raster.setWarningMessage("Crop optimal value {0} is greater than the maximum value {1}".format(opt_to_val, maxVal))
                elif num_rows == 1:
                    in_raster.setErrorMessage("Input rasters should be more than one")
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
            in_raster = parameters[0]
            ras_max_min = False
            i = 0
            # Get values from the generator function to show update messages
            for opt_from_val, opt_to_val, ras_file in self.getRowValue(in_raster, ras_max_min):
                i += 1
                arcpy.AddMessage("Creating conditional output for {0}\n".format(ntpath.basename(ras_file)))
                arcpy.gp.Con_sa(ras_file, "1", "in_memory" + "\\" + "raster_temp_" + str(i), "0", "\"Value\" >= " + opt_from_val + " AND \"Value\" <= " + opt_to_val)

            out_ras = parameters[1].valueAsText.replace("\\","/")  # Get output file
            out_ras_temp = arcpy.Raster("in_memory\\raster_temp_1")  # Get the initial con file in memory
            num_rows = len(parameters[0].values)  # The number of rows in the table
            #  Multiply files and save output
            for j in range(1, num_rows):
                j += 1
                if j <= num_rows:
                    arcpy.AddMessage("Multiplying file{0} with input raster\n".format("raster_temp_" + str(j)))
                    out_ras_temp = out_ras_temp * arcpy.Raster("in_memory\\raster_temp_" + str(j))

            arcpy.AddMessage("Saving Output\n")
            out_ras_temp.save(out_ras)
            arcpy.management.Delete('in_memory')  # Delete files in memory
            arcpy.AddMessage("Output saved!\n")
            return
        except Exception as ex:
            arcpy.AddMessage('ERROR: {0}'.format(ex))

    def getRowValue(self, in_raster, ras_max_min):
        """ Gets row values and calculate raster maximum and minimum values.
            Args:
                in_raster: Value table parameter with rows accompanied by columns.
                ras_max_min: A parameter that determines whether minimum and maximum value should be calculated or not.
            Returns:
                Optimal From, Optimal To, raster file path, raster minimum value and maximum value
        """
        for lst in in_raster.valueAsText.split(";"):
            opt_from_val = lst.split()[-2]  # Get crop optimum value from
            opt_to_val = lst.split()[-1]  # Get crop optimum value to
            ras_file = lst.rsplit(' ', 4)[0]  # Get raster file path
            paramInRaster = arcpy.Raster(ras_file)
            if ras_max_min:
                minVal = paramInRaster.minimum  # Minimum raster value
                maxVal = paramInRaster.maximum  # Maximum raster value
                yield opt_from_val, opt_to_val, ras_file, minVal, maxVal  # Return output
            else:
                yield opt_from_val, opt_to_val, ras_file
