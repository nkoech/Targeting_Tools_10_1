installPackage <- function(pkg) {
  # Install and add a package
  # Args:
  #   pkg: A vector of packages
  # Return: None
  
  for (i in 1:length(pkg)){
    if (!is.element(pkg[i], installed.packages()[,1])) {
      print(paste("Installing package: ", pkg[i]))
      if (pkg[i] == "modEvA"){
        install.packages("modEvA", repos="http://R-Forge.R-project.org")
      } else {
        install.packages(pkg[i], dep = TRUE)
      }
    }
    print(paste("Loading package: ", pkg[i]))
    require(pkg[i], character.only = TRUE)	
  }
}

readAscii<- function(inFile) {
  # Scan through the ASCII files while reading data
  # Args:
  #   inFile: Input ASCII file
  # Return:
  #   asciiData: A list of ASCII header and grid data
  
  asciiData <- list()
  print(paste("Reading: ", inFile, sep=""))
  for (i in 0:6) {
    if (i != 6){
      headerData <- scan(file = inFile, what = 'character', skip = i, nlines = 1, quiet=T)
      asciiData[tolower(headerData[1])] <- as.numeric(headerData[2])
    } else {
      gridData <- scan(file = inFile, skip = i, quiet=T)
      gridData[gridData == asciiData$nodata_value] <- NA
      dim(gridData) <- c(asciiData$nrows * asciiData$ncols, 1)
      asciiData$gridData <- gridData
    }
  }
  return(asciiData)
}

writeAscii <- function(outFile, asciiData)  {
  # Write ASCII data to a file
  # Args:
  #   outFile:
  #   asciiData: A list of ASCII header and grid data
  # Return: None
  
  noData <- -9999
  gridData <- asciiData$gridData
  asciiFile <- file(outFile, "w")
  for (i in 1:length(asciiData)) {
    if (names(asciiData[i]) == "nodata_value") {
      writeLines(paste("NODATA_value  ", as.character(noData), sep = ""), asciiFile)
    } else if (names(asciiData[i]) == "gridData") {
      gridData[!is.finite(gridData)] <- noData  # Replace NA and INF values with -9999
    } else {
      writeLines(paste(names(asciiData[i]), "         ", as.character(asciiData[i]), sep = ""), asciiFile)
    }
  }
  print(paste("Saving: ", outFile, sep = ""))
  write(gridData, asciiFile, ncolumns = asciiData$ncols, append = TRUE)
  close(asciiFile)
}

calculateMahalanobis <- function (threshold, totalFiles, outFolder, df, asciiData){
  # Caculate mahalanobis distance 
  # Args:
  #   threshold: Corresponding covariate/raster values extracted on a point feature
  #   totalFiles: Total number of files to be processed
  #   outFolder: Output path
  #   df: Data frame with grid data as ASCII
  #   asciiData: A list of ASCII header and grid data
  # Return: None
  
  mn <- sapply(threshold[,7:(7+totalFiles-1)], mean)
  print("Calculating Mahalanobis Distance")
  asciiData$gridData <- mahalanobis(df, mn, cov(df, use = "complete.obs"))
  writeAscii(paste(outFolder, "MahalanobisDist.asc", sep = ""), asciiData)
}

calculateMESS <- function(df, totalFiles, threshold, asciiData, outFolder) {
  # Multivariate Environmental Similarity Surface (MESS)
  # Args:
  #   df: Data frame with grid data as ASCII
  #   totalFiles: Total number of files to be processed
  #   threshold: Corresponding covariate/raster values extracted on a point feature
  #   asciiData: A list of ASCII header and grid data
  #   outFolder: Output path
  # Return: None
  
  boolNa = !is.na(apply(df, 1, sum))
  outMess = MESS(threshold[,7:(7 + totalFiles - 1)], df[boolNa,])
  asciiData$gridData = rep(NA, dim(df)[1])
  asciiData$gridData[boolNa] = outMess$TOTAL
  writeAscii(paste(outFolder, "MESS.asc", sep = ""), asciiData)
}

similarityAnalysis <- function(totalFiles, workSpace) {
  # Performs similarity analysis
  # Args:
  #   totalFiles: Total number of files to be processed
  #   fileDir: Path to where files are located
  # Return: None
  
  installPackage(c("raster", "rgdal", "modEvA"))
  print('Starting similarity anlysis...')
  df <- data.frame()
  asciiData <- list()
  threshold <- read.csv(paste(workSpace, "temp.csv", sep = ""))
  for (i in 1:totalFiles){
    asciiData <- readAscii(paste(workSpace, "tempAscii_", i, ".asc", sep = ""))
    if (i != 1) {
      df <- cbind(df, asciiData$gridData)
    } else	{
      df <- asciiData$gridData
    }
  }
  calculateMahalanobis(threshold, totalFiles, workSpace, df, asciiData)
  calculateMESS(df, totalFiles, threshold, asciiData, workSpace)
}