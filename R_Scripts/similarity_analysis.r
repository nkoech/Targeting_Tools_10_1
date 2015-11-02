library(modEvA)

similarityAnalysis <- function(cntRaster, read_script, write_script, ras_temp_path)	{
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
