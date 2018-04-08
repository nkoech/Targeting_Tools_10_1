usePackage <- function(p) {
	if (!is.element(p, installed.packages()[,1])) {
		print("Installing package")
		if (p == "modEvA"){
			install.packages("modEvA", repos="http://R-Forge.R-project.org")
		} else {
			install.packages(p, dep = TRUE)
		}
	}
	print("Loading required package")
	require(p, character.only = TRUE)	
}

similarityAnalysis <- function(cntRaster, read_script, write_script, ras_temp_path)	{
	## Install package and it's dependencies	
	usePackage("modEvA")
	## External scripts
	source(read_script)  
	source(write_script)

	print("Starting statistical similarity analysis...")

	outFolder = ras_temp_path
	dataTable = data.frame()
	for (cnt in 1:cntRaster)	{
		inAscii = readAscii(paste(outFolder, "tempAscii_", cnt, ".asc", sep = ""))
		if (cnt != 1) {
			dataTable = cbind(dataTable,inAscii$gridData)
		}
		else	{
			dataTable = inAscii$gridData
		}
	}
	pointsTable = read.csv(paste(outFolder, "temp.csv", sep = ""))
	pointsTableMean = sapply(pointsTable[,7:(7+cntRaster-1)], FUN = "mean")
	pointsTableSd = sapply(pointsTable[,7:(7+cntRaster-1)], FUN = "sd")
	dataMat = as.matrix(dataTable)
	## Mahalanobis Distance
	print("Calculating Mahalanobis Distance (D2)")
	Sx<-cov(dataTable, use = "complete.obs")
	D2 = mahalanobis(dataMat, pointsTableMean, Sx)
	inAscii$gridData = D2
	writeAscii(paste(outFolder, "MahalanobisDist.asc", sep = ""), inAscii)
	## MESS
	print("Calculating Multivariate Environmental Similarity Surface (MESS)")
	notNa = !is.na(apply(dataMat, MARGIN = 1, FUN = "sum"))
	outMess = MESS(pointsTable[,7:(7+cntRaster-1)], dataTable[notNa,])
	inAscii$gridData = rep(NA, dim(dataTable)[1])
	inAscii$gridData[notNa] = outMess$TOTAL
	writeAscii(paste(outFolder, "MESS.asc", sep = ""), inAscii)
}
