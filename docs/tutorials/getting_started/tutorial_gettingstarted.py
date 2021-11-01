from pathlib import Path

import pandas as pd

from hydrolib.core.io.dimr.models import DIMR, FMComponent
from hydrolib.core.io.mdu.models import FMModel
from hydrolib.core.io.structure.models import *

# Specify path and filenames
root = Path.cwd()
inputdir = root / "data"
modeldir = inputdir / "model"
mdufile = "moergestels_broek.mdu"
structurefile = "structure_temp.ini"

# Read MDU file
fm = FMModel(modeldir / mdufile)

# Read structure file: (A) from mdu model and (B) get based on structure file name directly
struc_A = fm.geometry.structurefile[0]
struc_B = StructureModel(modeldir / structurefile)

# Dict to df
df_struc_A = pd.DataFrame([f.__dict__ for f in struc_A.structure])
df_struc_B = pd.DataFrame([f.__dict__ for f in struc_B.structure])

# Change crestlevel and crestwidth of weir "Weir_RS373-st1" to respectively 10.1 m AD and 0.69
df_struc_A.loc[df_struc_A["id"] == "Weir_RS373-st1", "crestlevel"] = 10.1
df_struc_A.loc[df_struc_A["id"] == "Weir_RS373-st1", "crestwidth"] = 0.69

df_struc_B.loc[df_struc_B["id"] == "Weir_RS373-st1", "crestlevel"] = 10.1
df_struc_B.loc[df_struc_B["id"] == "Weir_RS373-st1", "crestwidth"] = 0.69

# Convert back to object
struc_A = StructureModel(structure=df_struc_A.to_dict("records"))
struc_B = StructureModel(structure=df_struc_B.to_dict("records"))

fm.geometry.structurefile[0] = struc_A

# Create output directory
outputdir = root / "output"
outputdir_files = root / "output_files"
outputdir.mkdir(parents=True, exist_ok=True)
outputdir_files.mkdir(parents=True, exist_ok=True)

# Change timerange
fm.time.tstop = 2 * 86400.0

# Save model
fm.save(outputdir)

# Save as seperate file
struc_B.save(outputdir_files)

# Add a dimr file
outputdimr = root.joinpath("output_dimr")
outputdimr.mkdir(parents=True, exist_ok=True)

dimr = DIMR()
dimr.component.append(
    FMComponent(name="MGB", workingDir=".", inputfile=fm.filepath, model=fm)
)
dimr.save(outputdimr)

# Run model from script
# TODO: run model
# with open("run_simulation.txt", "w") as f:
#    with open("error_run_simulation.txt", "w") as ferr:
#        o = subprocess.run("execute_dimr.bat", shell=False, stdout=f, stderr=ferr, check=False)

#
# TODO: nu nieuwe data genereren
# TODO: Read shapefile peilgebiedenb from data folder

# TODO: check out initial conditions

# TODO: Add IWL to peilgebieden to initial conditions

# TODO: Merge initial conditions back to object

# TODO: change boundary

print("hello world")
