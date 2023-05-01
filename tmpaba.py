# -*- coding: mbcs -*-

from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup


def seqprint(seq):
    for i in seq:
        print(i)


odb = session.openOdb(
    name="D:/Environment/Appdata/AbaqusData/Temp/job-2023-4-30--20-38-17.odb"
)
step = odb.steps["Step-1"]

with open("tmp.txt", "w") as f:
    f.write(
        "\n".join(
            str(i)
            for i in step.frames[-1].fieldOutputs["S"].values
        )
    )

# for frame in step.frames:
#     frame_time = frame.frameValue  # 时间
#     # print(frame.fieldOutputs)
#     force_values = frame.fieldOutputs["S"].values
#     seqprint(i for i in force_values)
#     break
