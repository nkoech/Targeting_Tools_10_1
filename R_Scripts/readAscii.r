
############################
###
### Read Ascii
###
############################

readAscii<- function(inputPath, inAsciiIndex = NA, prismIndexTable = NA, departGridData = 0) {
    nCols <- scan(file = inputPath, what = 'character', skip = 0, nlines = 1, quiet=T)
    nRows <- scan(file = inputPath, what = 'character', skip = 1, nlines = 1, quiet=T)
    xllcorner <- scan(file = inputPath, what = 'character', skip = 2, nlines = 1, quiet=T)
    yllcorner <- scan(file = inputPath, what = 'character', skip = 3, nlines = 1, quiet=T)
    cellSize <- scan(file = inputPath, what = 'character', skip = 4, nlines = 1, quiet=T)
    noDataValue <- scan(file = inputPath, what = 'character', skip = 5, nlines = 1, quiet=T)
    gridData <- scan(file = inputPath, skip = 6, quiet=T)

    nCols <- as.numeric(nCols[2])
    nRows <- as.numeric(nRows[2])
    xllcorner <- as.numeric(xllcorner[2])
    yllcorner <- as.numeric(yllcorner[2])
    cellSize <- as.numeric(cellSize[2])
    noDataValue <- as.numeric(noDataValue[2])
    gridData[gridData == noDataValue] <- NA
    #dim(gridData) <- c(nRows,nCols)
    dim(gridData) <- c(nRows*nCols,1)
    outGridData <- gridData

    if ((!is.na(inAsciiIndex))) {

      min1 <- min(prismIndexTable[,1])
      max1 <- max(prismIndexTable[,1])
      min2 <- min(prismIndexTable[,2])
      max2 <- max(prismIndexTable[,2])
      
      nCols <- inAsciiIndex$nCols
      nRows <- inAsciiIndex$nRows
      xllcorner <- inAsciiIndex$xllcorner 
      yllcorner <- inAsciiIndex$yllcorner
      cellSize <- inAsciiIndex$cellSize
      
      outGridData <- rep(NA, nRows*nCols)     
      outGridData[!(is.na(inAsciiIndex$gridData))] <- gridData[inAsciiIndex$gridData[!(is.na(inAsciiIndex$gridData))]]  - departGridData
      dim(outGridData) <- c(nRows*nCols, 1)
      outGridData[outGridData == -9999,] <- NA
    }  
    list(nCols=nCols, nRows=nRows, xllcorner=xllcorner, yllcorner=yllcorner, cellSize=cellSize,
    	noDataValue=noDataValue,gridData=outGridData)
}
