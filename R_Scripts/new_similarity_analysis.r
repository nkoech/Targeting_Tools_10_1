installPackage <- function(pkg) {
  for (i in 1:length(pkg)){
    if (!is.element(pkg[i], installed.packages()[,1])) {
      print(paste("Installing package:", pkg[i]))
      ifelse(pkg[i] == "modEvA", install.packages("modEvA", repos="http://R-Forge.R-project.org"), install.packages(pkg[i], dep = TRUE))
    }
    print(paste("Loading package:", pkg[i]))
    require(pkg[i], character.only = TRUE)	
  }
}