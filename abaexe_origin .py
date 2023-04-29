# -*- coding: utf-8 -*-
from abaqus import *
from abaqusConstants import *
import json
import io


class JsonTask:
    def __init__(self, filename):
        self.data = self.load_json(filename)

    @staticmethod
    def load_json(filename, encoding="utf-8"):
        """读取Json文件"""
        with io.open(filename, "r", encoding=encoding) as f:
            return json.load(f)

    def get_model(self, model_name):
        """两个列表转为元组"""
        material = self.materials[model_name]
        return tuple((i, j) for i, j in zip(material["sigma"], material["epsilon"]))

    @property
    def materials(self):
        return self.data["materials"]

    # ===concrete
    @property
    def concrete_plasticity_model(self):
        return self.get_model("concrete")

    @property
    def concrete_gfi(self):
        return (
            (
                self.materials["concrete"]["gfi"],
                self.materials["concrete"]["strength_tensile"],
            ),
        )

    @property
    def steel_plasticity_model(self):
        return self.get_model("steel")

    @property
    def steelbar_plasticity_model(self):
        return self.get_model("steelbar")

    @property
    def geometry(self):
        """几何"""
        return self.data["geometry"]

    @property
    def width(self):
        return self.geometry["width"]

    @property
    def high(self):
        return self.geometry["high"]

    @property
    def length(self):
        return self.geometry["length"]

    @property
    def tube_thickness(self):
        return self.geometry["tube_thickness"]

    @property
    def referpoint_1(self):
        return (self.width / 2, self.high / 2, -20.0)

    @property
    def referpoint_2(self):
        return (self.width / 2, self.high / 2, self.length + 20.0)


json_task = JsonTask("C:\\Users\\Tiki_\\Desktop\\abaqus_exe\\abatmp.json")


caename = "demo6"
caepath = "D:/Casual/T_%s/%s" % (caename, caename)

# ===abaqus初始化
session.Viewport(
    name="Viewport: 1",
    origin=(0.0, 0.0),
    width=117.13020324707,
    height=100.143524169922,
)
session.viewports["Viewport: 1"].makeCurrent()
session.viewports["Viewport: 1"].maximize()
from caeModules import *
from driverUtils import executeOnCaeStartup

executeOnCaeStartup()
session.viewports["Viewport: 1"].partDisplay.geometryOptions.setValues(
    referenceRepresentation=ON
)
Mdb()
#: 新的模型数据库已创建.
#: 模型 "Model-1" 已创建.
session.viewports["Viewport: 1"].setValues(displayedObject=None)
mdb.saveAs(pathName=caepath)

# ===部件-混凝土
s1 = mdb.models["Model-1"].ConstrainedSketch(name="__profile__", sheetSize=10000.0)
g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
s1.setPrimaryObject(option=STANDALONE)
s1.rectangle(point1=(0.0, 0.0), point2=(json_task.width, json_task.high))
p = mdb.models["Model-1"].Part(
    name="concrete", dimensionality=THREE_D, type=DEFORMABLE_BODY
)
p = mdb.models["Model-1"].parts["concrete"]
p.BaseSolidExtrude(sketch=s1, depth=json_task.length)
s1.unsetPrimaryObject()
p = mdb.models["Model-1"].parts["concrete"]
del mdb.models["Model-1"].sketches["__profile__"]

# ===部件-钢管
s = mdb.models["Model-1"].ConstrainedSketch(name="__profile__", sheetSize=10000.0)
g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
s.setPrimaryObject(option=STANDALONE)
s.rectangle(point1=(0.0, 0.0), point2=(json_task.width, json_task.high))
p = mdb.models["Model-1"].Part(
    name="tubelar", dimensionality=THREE_D, type=DEFORMABLE_BODY
)
p = mdb.models["Model-1"].parts["tubelar"]
p.BaseShellExtrude(sketch=s, depth=json_task.length)
s.unsetPrimaryObject()
p = mdb.models["Model-1"].parts["tubelar"]
del mdb.models["Model-1"].sketches["__profile__"]

# ===材料-钢
mdb.models["Model-1"].Material(name="steel_tube")
mdb.models["Model-1"].materials["steel_tube"].Elastic(table=((206000.0, 0.25),))
mdb.models["Model-1"].materials["steel_tube"].Plastic(
    table=json_task.steel_plasticity_model
)

# ===创建材料-混凝土(要加个(0.0001, 0))
mdb.models["Model-1"].Material(name="concrete")
mdb.models["Model-1"].materials["concrete"].ConcreteDamagedPlasticity(
    table=((36.0, 0.1, 1.16, 0.63, 0.0005),)
)
mdb.models["Model-1"].materials[
    "concrete"
].concreteDamagedPlasticity.ConcreteCompressionHardening(
    table=json_task.concrete_plasticity_model
)
mdb.models["Model-1"].materials[
    "concrete"
].concreteDamagedPlasticity.ConcreteTensionStiffening(
    table=json_task.concrete_gfi, type=GFI
)
mdb.models["Model-1"].materials["concrete"].Elastic(table=((34500.0, 0.2),))

# ===创建材料-拉杆
mdb.models["Model-1"].Material(name="steel_pullroll")
mdb.models["Model-1"].materials["steel_pullroll"].Elastic(table=((200000.0, 0.25),))
mdb.models["Model-1"].materials["steel_pullroll"].Plastic(
    table=json_task.steelbar_plasticity_model
)

# ===创建截面-混凝土
mdb.models["Model-1"].HomogeneousSolidSection(
    name="concrete", material="concrete", thickness=None
)

# ===创建截面-钢管
mdb.models["Model-1"].HomogeneousShellSection(
    name="tubelar",
    preIntegrate=OFF,
    material="steel_tube",
    thicknessType=UNIFORM,
    thickness=json_task.tube_thickness,
    thicknessField="",
    nodalThicknessField="",
    idealization=NO_IDEALIZATION,
    poissonDefinition=DEFAULT,
    thicknessModulus=None,
    temperature=GRADIENT,
    useDensity=OFF,
    integrationRule=SIMPSON,
    numIntPts=9,
)

# ===指派截面-混凝土
p = mdb.models["Model-1"].parts["concrete"]
c = p.cells
cells = c.getSequenceFromMask(
    mask=("[#1 ]",),
)
region = regionToolset.Region(cells=cells)
p = mdb.models["Model-1"].parts["concrete"]
p.SectionAssignment(
    region=region,
    sectionName="concrete",
    offset=0.0,
    offsetType=MIDDLE_SURFACE,
    offsetField="",
    thicknessAssignment=FROM_SECTION,
)

# ===指派截面-钢管
p = mdb.models["Model-1"].parts["tubelar"]
f = p.faces
faces = f.getSequenceFromMask(
    mask=("[#f ]",),
)
region = regionToolset.Region(faces=faces)
p = mdb.models["Model-1"].parts["tubelar"]
p.SectionAssignment(
    region=region,
    sectionName="tubelar",
    offset=0.0,
    offsetType=BOTTOM_SURFACE,
    offsetField="",
    thicknessAssignment=FROM_SECTION,
)

# ===分析步
mdb.models["Model-1"].StaticStep(
    name="Step-1",
    previous="Initial",
    maxNumInc=1000,
    initialInc=0.1,
    minInc=1e-07,
    nlgeom=ON,
)
session.viewports["Viewport: 1"].assemblyDisplay.setValues(step="Step-1")

# ===装配
a = mdb.models["Model-1"].rootAssembly

a.DatumCsysByDefault(CARTESIAN)
p = mdb.models["Model-1"].parts["concrete"]
a.Instance(name="concrete-1", part=p, dependent=ON)

p = mdb.models["Model-1"].parts["tubelar"]
a.Instance(name="tubelar-1", part=p, dependent=ON)

# ===创建相互作用属性-钢管-混凝土(硬接触和摩擦)
mdb.models["Model-1"].ContactProperty("tube-concrete")
mdb.models["Model-1"].interactionProperties["tube-concrete"].TangentialBehavior(
    formulation=PENALTY,
    directionality=ISOTROPIC,
    slipRateDependency=OFF,
    pressureDependency=OFF,
    temperatureDependency=OFF,
    dependencies=0,
    table=((0.6,),),
    shearStressLimit=None,
    maximumElasticSlip=FRACTION,
    fraction=0.005,
    elasticSlipStiffness=None,
)
mdb.models["Model-1"].interactionProperties["tube-concrete"].NormalBehavior(
    pressureOverclosure=HARD, allowSeparation=ON, constraintEnforcementMethod=DEFAULT
)

# ===创建相互作用-钢管-混凝土
i1 = mdb.models["Model-1"].rootAssembly.allInstances["concrete-1"]
leaf = dgm.LeafFromInstance(instances=(i1,))

i1 = mdb.models["Model-1"].rootAssembly.allInstances["tubelar-1"]
leaf = dgm.LeafFromInstance(instances=(i1,))

a = mdb.models["Model-1"].rootAssembly
s1 = a.instances["tubelar-1"].faces
side2Faces1 = s1.getSequenceFromMask(
    mask=("[#f ]",),
)
region1 = regionToolset.Region(side2Faces=side2Faces1)
a = mdb.models["Model-1"].rootAssembly
s1 = a.instances["concrete-1"].faces
side1Faces1 = s1.getSequenceFromMask(
    mask=("[#f ]",),
)
region2 = regionToolset.Region(side1Faces=side1Faces1)
mdb.models["Model-1"].SurfaceToSurfaceContactStd(
    name="tube-core",
    createStepName="Step-1",
    master=region1,
    slave=region2,
    sliding=FINITE,
    thickness=OFF,
    interactionProperty="tube-concrete",
    adjustMethod=NONE,
    initialClearance=OMIT,
    datumAxis=None,
    clearanceRegion=None,
)

# ===创建参考点
a = mdb.models["Model-1"].rootAssembly
a.ReferencePoint(point=json_task.referpoint_1)
a = mdb.models["Model-1"].rootAssembly
a.ReferencePoint(point=json_task.referpoint_2)

# ===创建底面刚体
a = mdb.models["Model-1"].rootAssembly
e1 = a.instances["tubelar-1"].edges
edges1 = e1.getSequenceFromMask(
    mask=("[#a44 ]",),
)
f2 = a.instances["concrete-1"].faces
faces2 = f2.getSequenceFromMask(
    mask=("[#20 ]",),
)
region4 = a.Set(edges=edges1, faces=faces2, name="ct_bottom")
a = mdb.models["Model-1"].rootAssembly
r1 = a.referencePoints
refPoints1 = (r1[8],)
region1 = regionToolset.Region(referencePoints=refPoints1)
mdb.models["Model-1"].RigidBody(
    name="C-RP-1", refPointRegion=region1, tieRegion=region4
)

# ===创建顶面刚体
a = mdb.models["Model-1"].rootAssembly
e1 = a.instances["tubelar-1"].edges
edges1 = e1.getSequenceFromMask(
    mask=("[#491 ]",),
)
f2 = a.instances["concrete-1"].faces
faces2 = f2.getSequenceFromMask(
    mask=("[#10 ]",),
)
region4 = a.Set(edges=edges1, faces=faces2, name="ct_top")
a = mdb.models["Model-1"].rootAssembly
r1 = a.referencePoints
refPoints1 = (r1[9],)
region1 = regionToolset.Region(referencePoints=refPoints1)
mdb.models["Model-1"].RigidBody(
    name="C-RP-2", refPointRegion=region1, tieRegion=region4
)

# ===边界条件-底部
a = mdb.models["Model-1"].rootAssembly
r1 = a.referencePoints
refPoints1 = (r1[8],)
region = regionToolset.Region(referencePoints=refPoints1)
# PinnedBC 铰接
# EncastreBC 固接
mdb.models["Model-1"].PinnedBC(
    name="bound_bottom", createStepName="Step-1", region=region, localCsys=None
)

# ===边界条件-顶部
a = mdb.models["Model-1"].rootAssembly
r1 = a.referencePoints
refPoints1 = (r1[9],)
region = regionToolset.Region(referencePoints=refPoints1)
mdb.models["Model-1"].DisplacementBC(
    name="bound_top",
    createStepName="Step-1",
    region=region,
    u1=UNSET,
    u2=0.0,
    u3=-200.0,
    ur1=0.0,
    ur2=0.0,
    ur3=0.0,
    amplitude=UNSET,
    fixed=OFF,
    distributionType=UNIFORM,
    fieldName="",
    localCsys=None,
)

