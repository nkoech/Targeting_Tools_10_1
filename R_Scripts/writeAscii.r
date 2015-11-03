
############################
###
### Write Ascii
###
############################

writeAscii <- function(outputPath, asciiList = NA, nCols = NA, nRows = NA, xllcorner = NA, yllcorner = NA, cellSize = NA, noDataValue = NA, gridData = NA)  {
    if (length(names(asciiList)) == 7){
      nCols <- asciiList$nCols
      nRows <- asciiList$nRows
      xllcorner <- asciiList$xllcorner
      yllcorner <- asciiList$yllcorner
      cellSize <- asciiList$cellSize
      noDataValue <- -9999
      gridData <- asciiList$gridData
    }

    gridData[is.na(gridData)] <- noDataValue
    outFile <- file(outputPath, "w")
    writeLines(paste("ncols         ", as.character(nCols), sep = ""), outFile)
    writeLines(paste("nrows         ", as.character(nRows), sep = ""), outFile)
    writeLines(paste("xllcorner     ", as.character(xllcorner), sep = ""), outFile)
    writeLines(paste("yllcorner     ", as.character(yllcorner), sep = ""), outFile)
    writeLines(paste("cellsize      ", as.character(cellSize), sep = ""), outFile)
    writeLines(paste("NODATA_value  ", as.character(noDataValue), sep = ""), outFile)
    write(gridData, outFile, ncolumns = nCols, append = TRUE)
    close(outFile)
}
