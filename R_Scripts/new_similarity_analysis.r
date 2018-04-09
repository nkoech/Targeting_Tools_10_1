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

