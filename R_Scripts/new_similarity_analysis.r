installPackage <- function(pkg) {
  # Install and add a package
  # Args:
  #   pkg: A vector of packages
  # Return: None
  
  for (i in 1:length(pkg)){
    if (!is.element(pkg[i], installed.packages()[,1])) {
      print(paste("Installing package:", pkg[i]))
      if (pkg[i] == "modEvA"){
        install.packages("modEvA", repos="http://R-Forge.R-project.org")
      } else {
        install.packages(pkg[i], dep = TRUE)
      }
    }
    print(paste("Loading package:", pkg[i]))
    require(pkg[i], character.only = TRUE)	
  }
}

readAscii<- function(inFile) {
  # Scan through the ASCII files while reading data
  # Args:
  #   inFile: Input ASCII file
  # Return:
  #   asciiData: A list of ascii header and grid data
  
  asciiData <- list()
  for (i in 0:6) {
    if (i != 6){
      headerData <- scan(file = inFile, what = 'character', skip = i, nlines = 1, quiet=T)
      asciiData[headerData[1]] <- as.numeric(headerData[2])
    } else {
      gridData <- scan(file = inFile, skip = i, quiet=T)
      gridData[gridData == asciiData$NODATA_value] <- NA
      dim(gridData) <- c(asciiData$NROWS * asciiData$NCOLS, 1)
      asciiData$gridData <- gridData
    }
  }
  return(asciiData)
}

similarityAnalysis <- function(numFiles, dirPath) {
  # Performs similarity analysis
  # Args:
  #   numFiles: Number of files to be processed
  #   fileDir: Path to where files are located
  # Return: None
  
  installPackage(c("raster", "rgdal", "modEvA")) # Install/add packages
  print('Starting similarity anlysi...')
  
  dataTable <- data.frame() # Create empty data frame
  for (i in 1:numFiles){
    readAscii(paste(dirPath, "tempAscii_", i, ".asc", sep = ""))
  }
  
  
  # for (cnt in 1:cntRaster)	{
  #   inAscii = readAscii(paste(outFolder, "tempAscii_", cnt, ".asc", sep = ""))
  #   if (cnt != 1) {
  #     dataTable = cbind(dataTable,inAscii$gridData)
  #   }
  #   else	{
  #     dataTable = inAscii$gridData
  #   }
  # }
  
  
}