# -*- coding: utf-8 -*-
from abaqus import *
from abaqusConstants import *
from caeModules import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import math
import json
import io
import time
import os
import traceback


class JsonTask:
    def __init__(self, filename):
        self.data = self.load_json(filename)

    @staticmethod
    def load_json(filename, encoding="utf-8"):
        """读取Json文件"""
        with io.open(filename, "r", encoding=encoding) as f:
            return json.load(f)

    @staticmethod
    def write_json(item, jsonFile="data.json", encoding="utf-8", ensure_ascii=False):
        """写入Json文件"""
        with io.open(jsonFile, "w", encoding=encoding) as f:
            f.write(json.dumps(item, ensure_ascii=ensure_ascii).decode("utf-8"))

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
                self.materials["concrete"]["strength_tensile"],
                self.materials["concrete"]["gfi"],
            ),
        )

    @property
    def steel_plasticity_model(self):
        return self.get_model("steel")

    @property
    def steelbar_plasticity_model(self):
        return self.get_model("steelbar")

    # ===几何
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

    # ===参考点
    @property
    def referpoint_bottom(self):
        rp = self.data["referpoint"]["bottom"]["shift"]
        return (self.width / 2 + rp[0], self.high / 2 + rp[1], rp[2])

    @property
    def referpoint_top(self):
        rp = self.data["referpoint"]["top"]["shift"]
        return (self.width / 2 + rp[0], self.high / 2 + rp[1], self.length + rp[2])

    # ===约束
    @property
    def displacement_bottom(self):
        value = self.data["referpoint"]["bottom"]["displacement"]
        value = tuple((UNSET if i is None else i) for i in value)
        return value

    @property
    def displacement_top(self):
        value = self.data["referpoint"]["top"]["displacement"]
        value = tuple((UNSET if i is None else i) for i in value)
        return value

    @property
    def data_pullroll(self):
        return self.data["pullroll"]

    @property
    def meta(self):
        return self.data["meta"]

    @property
    def concrete_seed(self):
        return self.geometry["concrete_seed"]

    @property
    def steel_seed(self):
        return self.geometry["steel_seed"]

    @property
    def gap(self):
        return 5

    @property
    def edge_point(self):
        return {
            "bottom_all": (
                (self.width / 2, 0, 0),
                (self.width / 2, self.high, 0),
                (0, self.high / 2, 0),
                (self.width, self.high / 2, 0),
            ),
            "top_all": (
                (self.width / 2, 0, self.length),
                (self.width / 2, self.high, self.length),
                (0, self.high / 2, self.length),
                (self.width, self.high / 2, self.length),
            ),
            "x_all": (
                (self.width / 2, 0, 0),
                (self.width / 2, self.high, 0),
                (self.width / 2, 0, self.length),
                (self.width / 2, self.high, self.length),
            ),
            "y_all": (
                (0, self.high / 2, 0),
                (self.width, self.high / 2, 0),
                (0, self.high / 2, self.length),
                (self.width, self.high / 2, self.length),
            ),
            "z_all": (
                (self.width, 0, self.length / 2),
                (self.width, self.high, self.length / 2),
                (0, self.high, self.length / 2),
                (self.width, self.high, self.length / 2),
            ),
        }


def task_execute(jtask):
    caepath = jtask.meta["caepath"].encode("ascii")
    jobname = jtask.meta["jobname"].encode("ascii")
    modelname = jtask.meta["modelname"].encode("ascii")

    # ===abaqus初始化
    print("task start at:" + caepath)
    session.Viewport(
        name="Viewport: 1",
        origin=(0.0, 0.0),
        width=117.13020324707,
        height=100.143524169922,
    )
    session.viewports["Viewport: 1"].makeCurrent()
    session.viewports["Viewport: 1"].maximize()

    executeOnCaeStartup()
    session.viewports["Viewport: 1"].partDisplay.geometryOptions.setValues(
        referenceRepresentation=ON
    )
    Mdb()
    print(modelname)
    mdb.Model(name=modelname, modelType=STANDARD_EXPLICIT)
    #: 新的模型数据库已创建.
    #: 模型 modelname 已创建.
    session.viewports["Viewport: 1"].setValues(displayedObject=None)

    # ===部件-混凝土
    s1 = mdb.models[modelname].ConstrainedSketch(name="__profile__", sheetSize=10000.0)
    g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
    s1.setPrimaryObject(option=STANDALONE)
    s1.rectangle(point1=(0.0, 0.0), point2=(jtask.width, jtask.high))
    p = mdb.models[modelname].Part(
        name="concrete", dimensionality=THREE_D, type=DEFORMABLE_BODY
    )
    p = mdb.models[modelname].parts["concrete"]
    p.BaseSolidExtrude(sketch=s1, depth=jtask.length)
    s1.unsetPrimaryObject()
    p = mdb.models[modelname].parts["concrete"]
    del mdb.models[modelname].sketches["__profile__"]

    # ===部件-钢管
    s = mdb.models[modelname].ConstrainedSketch(name="__profile__", sheetSize=10000.0)
    g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
    s.setPrimaryObject(option=STANDALONE)
    s.rectangle(point1=(0.0, 0.0), point2=(jtask.width, jtask.high))
    p = mdb.models[modelname].Part(
        name="tubelar", dimensionality=THREE_D, type=DEFORMABLE_BODY
    )
    p = mdb.models[modelname].parts["tubelar"]
    p.BaseShellExtrude(sketch=s, depth=jtask.length)
    s.unsetPrimaryObject()
    p = mdb.models[modelname].parts["tubelar"]
    del mdb.models[modelname].sketches["__profile__"]

    # ===材料-钢
    mdb.models[modelname].Material(name="steel_tube")
    mdb.models[modelname].materials["steel_tube"].Elastic(table=((206000.0, 0.25),))
    mdb.models[modelname].materials["steel_tube"].Plastic(
        table=jtask.steel_plasticity_model
    )

    # ===创建材料-混凝土(要加个(0.0001, 0))
    mdb.models[modelname].Material(name="concrete")
    mdb.models[modelname].materials["concrete"].ConcreteDamagedPlasticity(
        table=((36.0, 0.1, 1.16, 0.63, 0.0005),)
    )
    mdb.models[modelname].materials[
        "concrete"
    ].concreteDamagedPlasticity.ConcreteCompressionHardening(
        table=jtask.concrete_plasticity_model
    )
    mdb.models[modelname].materials[
        "concrete"
    ].concreteDamagedPlasticity.ConcreteTensionStiffening(
        table=jtask.concrete_gfi, type=GFI
    )
    mdb.models[modelname].materials["concrete"].Elastic(table=((34500.0, 0.2),))

    # ===创建材料-拉杆
    mdb.models[modelname].Material(name="steel_pullroll")
    mdb.models[modelname].materials["steel_pullroll"].Elastic(table=((200000.0, 0.25),))
    mdb.models[modelname].materials["steel_pullroll"].Plastic(
        table=jtask.steelbar_plasticity_model
    )

    # ===创建截面-混凝土
    mdb.models[modelname].HomogeneousSolidSection(
        name="concrete", material="concrete", thickness=None
    )

    # ===创建截面-钢管
    mdb.models[modelname].HomogeneousShellSection(
        name="tubelar",
        preIntegrate=OFF,
        material="steel_tube",
        thicknessType=UNIFORM,
        thickness=jtask.tube_thickness,
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
    p = mdb.models[modelname].parts["concrete"]
    c = p.cells
    region = regionToolset.Region(cells=p.cells)
    p = mdb.models[modelname].parts["concrete"]
    p.SectionAssignment(
        region=region,
        sectionName="concrete",
        offset=0.0,
        offsetType=MIDDLE_SURFACE,
        offsetField="",
        thicknessAssignment=FROM_SECTION,
    )

    # ===指派截面-钢管
    p = mdb.models[modelname].parts["tubelar"]
    region = regionToolset.Region(faces=p.faces)
    p = mdb.models[modelname].parts["tubelar"]
    p.SectionAssignment(
        region=region,
        sectionName="tubelar",
        offset=0.0,
        offsetType=BOTTOM_SURFACE,
        offsetField="",
        thicknessAssignment=FROM_SECTION,
    )

    # ===分析步
    mdb.models[modelname].StaticStep(
        name="Step-1",
        previous="Initial",
        maxNumInc=1000,
        initialInc=0.01,
        minInc=1e-07,
        nlgeom=ON,
    )
    session.viewports["Viewport: 1"].assemblyDisplay.setValues(step="Step-1")

    # ===装配
    a = mdb.models[modelname].rootAssembly

    a.DatumCsysByDefault(CARTESIAN)
    p = mdb.models[modelname].parts["concrete"]
    a.Instance(name="concrete-1", part=p, dependent=ON)

    p = mdb.models[modelname].parts["tubelar"]
    a.Instance(name="tubelar-1", part=p, dependent=ON)

    # ===创建部件-拉杆X
    s = mdb.models[modelname].ConstrainedSketch(name="__profile__", sheetSize=200.0)
    g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
    s.setPrimaryObject(option=STANDALONE)
    s.Line(point1=(0, jtask.high / 2), point2=(jtask.width, jtask.high / 2))
    s.HorizontalConstraint(entity=g[2], addUndoState=False)
    p = mdb.models[modelname].Part(
        name="pullroll_x", dimensionality=THREE_D, type=DEFORMABLE_BODY
    )
    p = mdb.models[modelname].parts["pullroll_x"]
    p.BaseWire(sketch=s)
    s.unsetPrimaryObject()
    p = mdb.models[modelname].parts["pullroll_x"]
    del mdb.models[modelname].sketches["__profile__"]
    # ===创建部件-拉杆Y
    s1 = mdb.models[modelname].ConstrainedSketch(name="__profile__", sheetSize=200.0)
    g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
    s1.setPrimaryObject(option=STANDALONE)
    s1.Line(point1=(jtask.width / 2, 0), point2=(jtask.width / 2, jtask.high))
    s1.VerticalConstraint(entity=g[2], addUndoState=False)
    p = mdb.models[modelname].Part(
        name="pullroll_y", dimensionality=THREE_D, type=DEFORMABLE_BODY
    )
    p = mdb.models[modelname].parts["pullroll_y"]
    p.BaseWire(sketch=s1)
    s1.unsetPrimaryObject()
    p = mdb.models[modelname].parts["pullroll_y"]
    del mdb.models[modelname].sketches["__profile__"]

    # ===创建截面-拉杆X
    mdb.models[modelname].TrussSection(
        name="pullroll_x",
        material="steel_pullroll",
        area=jtask.data_pullroll["area"],
    )

    # ===创建截面-拉杆Y
    mdb.models[modelname].TrussSection(
        name="pullroll_y",
        material="steel_pullroll",
        area=1 if jtask.data_pullroll["only_x"] else jtask.data_pullroll["area"],
    )

    # ===指派截面-拉杆X
    p = mdb.models[modelname].parts["pullroll_x"]
    region = regionToolset.Region(edges=p.edges)
    p = mdb.models[modelname].parts["pullroll_x"]
    p.SectionAssignment(
        region=region,
        sectionName="pullroll_x",
        offset=0.0,
        offsetType=MIDDLE_SURFACE,
        offsetField="",
        thicknessAssignment=FROM_SECTION,
    )

    # ===指派截面-拉杆Y
    p = mdb.models[modelname].parts["pullroll_y"]
    region = regionToolset.Region(edges=p.edges)
    p = mdb.models[modelname].parts["pullroll_y"]
    p.SectionAssignment(
        region=region,
        sectionName="pullroll_y",
        offset=0.0,
        offsetType=MIDDLE_SURFACE,
        offsetField="",
        thicknessAssignment=FROM_SECTION,
    )
    # ===创建实例-拉杆
    p = mdb.models[modelname].parts["pullroll_x"]
    a.Instance(name="pullroll_x-1", part=p, dependent=ON)
    p = mdb.models[modelname].parts["pullroll_y"]
    a.Instance(name="pullroll_y-1", part=p, dependent=ON)
    # ===平移实例-拉杆
    a1 = mdb.models[modelname].rootAssembly
    a1.translate(
        instanceList=("pullroll_x-1", "pullroll_y-1"),
        vector=(0.0, 0.0, jtask.data_pullroll["start_shift"]),
    )
    # ===线性阵列实例-拉杆
    a1 = mdb.models[modelname].rootAssembly
    pullroll_all = a1.LinearInstancePattern(
        instanceList=("pullroll_x-1",),
        direction1=(0.0, 0.0, 1.0),
        direction2=(0.0, 1.0, 0.0),
        number1=jtask.data_pullroll["number_z"],
        number2=1,
        spacing1=jtask.data_pullroll["distance"],
        spacing2=300.0,
    )
    pullroll_all += (a1.instances["pullroll_x-1"],)
    pullroll_all += a1.LinearInstancePattern(
        instanceList=("pullroll_y-1",),
        direction1=(0.0, 0.0, 1.0),
        direction2=(0.0, 1.0, 0.0),
        number1=jtask.data_pullroll["number_z"],
        number2=1,
        spacing1=jtask.data_pullroll["distance"],
        spacing2=300.0,
    )
    pullroll_all += (a1.instances["pullroll_y-1"],)
    # ===合并实例-拉杆
    a1 = mdb.models[modelname].rootAssembly
    a1.InstanceFromBooleanMerge(
        name="union",
        instances=pullroll_all + (a1.instances["tubelar-1"],),
        originalInstances=DELETE,
        mergeNodes=BOUNDARY_ONLY,
        nodeMergingTolerance=1e-06,
        domain=BOTH,
    )

    # ===创建参考点
    a = mdb.models[modelname].rootAssembly
    feature_1 = a.ReferencePoint(point=jtask.referpoint_bottom)
    a = mdb.models[modelname].rootAssembly
    feature_2 = a.ReferencePoint(point=jtask.referpoint_top)
    referpoint_bottom, referpoint_top = (
        a.referencePoints[feature_1.id],
        a.referencePoints[feature_2.id],
    )

    # ===创建底面刚体
    a = mdb.models[modelname].rootAssembly

    f1 = a.instances["concrete-1"].faces
    faces1 = f1.findAt(
        coordinates=tuple(
            [(jtask.width / 2, jtask.high / 2, 0)],
        )
    )
    e2 = a.instances["union-1"].edges
    edges2 = e2.findAt(coordinates=jtask.edge_point["bottom_all"])

    region4 = regionToolset.Region(edges=edges2, faces=faces1)
    a = mdb.models[modelname].rootAssembly
    r1 = a.referencePoints

    refPoints1 = (referpoint_bottom,)
    region1 = regionToolset.Region(referencePoints=refPoints1)
    mdb.models[modelname].RigidBody(
        name="ct_bottom", refPointRegion=region1, tieRegion=region4
    )

    # ===创建顶面刚体
    a = mdb.models[modelname].rootAssembly
    f1 = a.instances["concrete-1"].faces
    faces1 = f1.findAt(
        coordinates=tuple(
            [(jtask.width / 2, jtask.high / 2, jtask.length)],
        )
    )
    e2 = a.instances["union-1"].edges
    edges2 = e2.findAt(coordinates=jtask.edge_point["top_all"])

    region4 = regionToolset.Region(edges=edges2, faces=faces1)
    a = mdb.models[modelname].rootAssembly
    r1 = a.referencePoints
    refPoints1 = (referpoint_top,)
    region1 = regionToolset.Region(referencePoints=refPoints1)
    mdb.models[modelname].RigidBody(
        name="cp_top", refPointRegion=region1, tieRegion=region4
    )

    # ===边界条件-底部
    a = mdb.models[modelname].rootAssembly
    r1 = a.referencePoints
    refPoints1 = (referpoint_bottom,)
    region = regionToolset.Region(referencePoints=refPoints1)
    mdb.models[modelname].DisplacementBC(
        name="bound_bottom",
        createStepName="Step-1",
        region=region,
        u1=jtask.displacement_bottom[0],
        u2=jtask.displacement_bottom[1],
        u3=jtask.displacement_bottom[2],
        ur1=jtask.displacement_bottom[3],
        ur2=jtask.displacement_bottom[4],
        ur3=jtask.displacement_bottom[5],
        amplitude=UNSET,
        fixed=OFF,
        distributionType=UNIFORM,
        fieldName="",
        localCsys=None,
    )
    # PinnedBC 铰接
    # EncastreBC 固接
    # mdb.models[modelname].PinnedBC(
    #     name="bound_bottom", createStepName="Step-1", region=region, localCsys=None
    # )

    # ===边界条件-顶部
    a = mdb.models[modelname].rootAssembly
    r1 = a.referencePoints
    refPoints1 = (referpoint_top,)
    region = regionToolset.Region(referencePoints=refPoints1)
    mdb.models[modelname].DisplacementBC(
        name="bound_top",
        createStepName="Step-1",
        region=region,
        u1=jtask.displacement_top[0],
        u2=jtask.displacement_top[1],
        u3=jtask.displacement_top[2],
        ur1=jtask.displacement_top[3],
        ur2=jtask.displacement_top[4],
        ur3=jtask.displacement_top[5],
        amplitude=UNSET,
        fixed=OFF,
        distributionType=UNIFORM,
        fieldName="",
        localCsys=None,
    )

    # ===创建相互作用属性-钢管-混凝土(硬接触和摩擦)
    mdb.models[modelname].ContactProperty("tube-concrete")
    mdb.models[modelname].interactionProperties["tube-concrete"].TangentialBehavior(
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
    mdb.models[modelname].interactionProperties["tube-concrete"].NormalBehavior(
        pressureOverclosure=HARD,
        allowSeparation=ON,
        constraintEnforcementMethod=DEFAULT,
    )

    # ===创建相互作用-钢管-混凝土
    a = mdb.models[modelname].rootAssembly
    s1 = a.instances["union-1"].faces
    side2Faces1 = s1.getSequenceFromMask(
        mask=("[#f ]",),
    )
    region1 = regionToolset.Region(side2Faces=side2Faces1)
    a = mdb.models[modelname].rootAssembly
    s1 = a.instances["concrete-1"].faces
    side1Faces1 = s1.getSequenceFromMask(
        mask=("[#f ]",),
    )
    region2 = regionToolset.Region(side1Faces=side1Faces1)
    mdb.models[modelname].SurfaceToSurfaceContactStd(
        name="steel-concrete",
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

    # ===单元类型-桁架
    elemType1 = mesh.ElemType(elemCode=T3D2, elemLibrary=STANDARD)
    p = mdb.models[modelname].parts["union"]
    e = p.edges
    edges = e.getByBoundingCylinder(
        center1=(jtask.width / 2, jtask.high / 2, 0),
        center2=(jtask.width / 2, jtask.high / 2, jtask.length),
        radius=math.sqrt(jtask.width * jtask.width + jtask.high * jtask.high)
        - jtask.gap,
    )
    pickedRegions = (edges,)
    p.setElementType(regions=pickedRegions, elemTypes=(elemType1,))
    # ===划分网格-union
    p = mdb.models[modelname].parts["union"]
    p.seedPart(size=jtask.steel_seed[0], deviationFactor=0.1, minSizeFactor=0.1)
    e = p.edges
    for i, j in zip(["x_all", "y_all", "z_all"], [0, 1, 2]):
        pickedEdges = e.findAt(coordinates=jtask.edge_point[i])
        p.seedEdgeBySize(
            edges=pickedEdges,
            size=jtask.steel_seed[j],
            deviationFactor=0.1,
            minSizeFactor=0.1,
            constraint=FINER,
        )

    p = mdb.models[modelname].parts["union"]
    p.generateMesh()
    # ===划分网格-concrete
    p = mdb.models[modelname].parts["concrete"]
    e = p.edges
    for i, j in zip(["x_all", "y_all", "z_all"], [0, 1, 2]):
        pickedEdges = e.findAt(coordinates=jtask.edge_point[i])
        p.seedEdgeBySize(
            edges=pickedEdges,
            size=jtask.concrete_seed[j],
            deviationFactor=0.1,
            minSizeFactor=0.1,
            constraint=FINER,
        )
    p = mdb.models[modelname].parts["concrete"]
    p.generateMesh()

    # ===创建集
    a = mdb.models[modelname].rootAssembly
    r1 = a.referencePoints
    refPoints1 = (referpoint_top,)
    a.Set(referencePoints=refPoints1, name="RP-TOP")

    # ===历程输出
    regionDef = mdb.models[modelname].rootAssembly.sets["RP-TOP"]
    mdb.models[modelname].HistoryOutputRequest(
        name="TOP-OUTPUT",
        createStepName="Step-1",
        variables=(
            "U1",
            "U2",
            "U3",
            "UR1",
            "UR2",
            "UR3",
            "RF1",
            "RF2",
            "RF3",
            "RM1",
            "RM2",
            "RM3",
        ),
        region=regionDef,
        sectionPoints=DEFAULT,
        rebar=EXCLUDE,
    )

    # ===生成作业
    mdb.Job(
        name=jobname,
        model=modelname,
        description="",
        type=ANALYSIS,
        atTime=None,
        waitMinutes=0,
        waitHours=0,
        queue=None,
        memory=90,
        memoryUnits=PERCENTAGE,
        getMemoryFromAnalysis=True,
        explicitPrecision=SINGLE,
        nodalOutputPrecision=SINGLE,
        echoPrint=OFF,
        modelPrint=OFF,
        contactPrint=OFF,
        historyPrint=OFF,
        userSubroutine="",
        scratch="",
        resultsFormat=ODB,
        multiprocessingMode=DEFAULT,
        numCpus=7,
        numDomains=7,
        numGPUs=1,
    )
    # ===保存
    mdb.saveAs(pathName=caepath)

    # ===切换窗口
    a = mdb.models[modelname].rootAssembly
    a.regenerate()
    a = mdb.models[modelname].rootAssembly
    session.viewports["Viewport: 1"].setValues(displayedObject=a)
    session.viewports["Viewport: 1"].assemblyDisplay.setValues(
        optimizationTasks=OFF, geometricRestrictions=OFF, stopConditions=OFF
    )

    # ===提交
    if jtask.meta["submit"]:
        # ===作业开始
        st_time = time.time()
        try:
            mdb.jobs[jobname].submit()

            line = 5
            job_running = True
            stafile = "D:/Environment/Appdata/AbaqusData/Temp/%s.sta" % jobname
            # ===输出status
            while not os.path.isfile(stafile):
                time.sleep(10)
            with io.open(stafile, "rt", encoding="gbk") as f:
                while job_running:
                    f.seek(0, 0)
                    status = f.read().splitlines()
                    for i in range(line, len(status)):
                        line_content = status[i]
                        if "COMPLETED" in line_content:
                            job_running = False
                            break
                        if time.time() - st_time > jtask.meta["time_limit"]:
                            raise Exception("job time out")
                        print(line_content)
                        line += 1
                    time.sleep(10)

            mdb.jobs[jobname].waitForCompletion()
            print("job running time(s):", time.time() - st_time)
        except Exception:
            traceback.print_exc()
            mdb.jobs[jobname].kill()

        try:
            odb = session.openOdb(
                name=("D:/Environment/Appdata/AbaqusData/Temp/%s.odb" % jobname)
                .decode("utf-8")
                .encode("ascii")
            )

            # ===保存应力应变曲线
            xy0 = xyPlot.XYDataFromHistory(
                odb=odb,
                outputVariableName="Reaction force: RF3 PI: rootAssembly Node 2 in NSET RP-TOP",
                steps=("Step-1",),
                suppressQuery=True,
                __linkedVpName__="Viewport: 1",
            )
            xy1 = xyPlot.XYDataFromHistory(
                odb=odb,
                outputVariableName="Spatial displacement: U3 PI: rootAssembly Node 2 in NSET RP-TOP",
                steps=("Step-1",),
                suppressQuery=True,
                __linkedVpName__="Viewport: 1",
            )

            top_point_data = {
                "sigma": [-i[1] for i in xy0],
                "epsilon": [-i[1] / jtask.length for i in xy1],
                "time": [i[0] for i in xy0],
            }

            data = {"top_point": top_point_data}
            JsonTask.write_json(
                data,
                jtask.meta["taskfolder"] + "\\top_point_data.json",
            )
            JsonTask.write_json(
                jtask.data,
                jtask.meta["taskfolder"] + "\\task_data.json",
            )
            print("json saved")

            # ===保存动画
            session.viewports["Viewport: 1"].odbDisplay.basicOptions.setValues(
                renderShellThickness=ON
            )
            session.viewports["Viewport: 1"].setValues(displayedObject=odb)
            session.viewports["Viewport: 1"].makeCurrent()
            session.viewports["Viewport: 1"].odbDisplay.display.setValues(
                plotState=(CONTOURS_ON_DEF,)
            )
            session.viewports["Viewport: 1"].animationController.setValues(
                animationType=TIME_HISTORY
            )
            session.viewports["Viewport: 1"].animationController.play(
                duration=UNLIMITED
            )

            session.imageAnimationOptions.setValues(
                vpDecorations=ON, vpBackground=OFF, compass=OFF
            )
            avipath = jtask.meta["taskfolder"].replace("\\", "/") + "/animation.avi"
            avipath = avipath.decode("utf-8").encode("ascii")
            session.writeImageAnimation(
                fileName=avipath,
                format=AVI,
                canvasObjects=(session.viewports["Viewport: 1"],),
            )
            print("animation saved")
        except Exception:
            traceback.print_exc()


json_task = JsonTask("C:\\Users\\Tiki_\\Desktop\\abaqus_exe\\abatmp.json")
task_execute(json_task)
