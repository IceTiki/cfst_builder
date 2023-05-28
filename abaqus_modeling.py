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
import shutil
import urllib2


TASK_FOLDER = "C:\\Users\\Tiki_\\Desktop\\abaqus_exe\\tasks"
GAP = 1  #  取一个小值, 用于几何选取函数等, 用于将选框向内缩一点


class Utils:
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

    @staticmethod
    def http_get(url):
        response = urllib2.urlopen(url)
        content = response.read()
        return content

    @staticmethod
    def mkdirs(path):
        if os.path.isdir(path):
            return True
        elif os.path.isfile(path):
            raise ValueError("%s is a file" % path)
        else:
            os.makedirs(name=path)
            return True


class TaskHandler:
    gap = GAP

    def __init__(self, taskparams):
        self.taskparams = taskparams
        self.load_params()
        self.load_material()
        self.load_geometry()
        self.load_referpoint()
        self.load_pullroll()
        self.load_meta()

    def load_params(self):
        self.materials, self.geometry, self.pullroll, self.meta = (
            self.taskparams["materials"],
            self.taskparams["geometry"],
            self.taskparams["pullroll"],
            self.taskparams["meta"],
        )

    def load_material(self):
        # ===混凝土
        materdata = self.materials["concrete"]
        self.concrete_plasticity_model = tuple(
            (i, j) for i, j in zip(materdata["sigma"], materdata["epsilon"])
        )
        self.concrete_gfi = (
            (
                self.materials["concrete"]["strength_fracture"],
                self.materials["concrete"]["gfi"],
            ),
        )
        self.concrete_elastic_modulus = self.materials["concrete"]["elastic_modulus"]
        # ===钢管
        materdata = self.materials["steel"]
        self.steel_plasticity_model = tuple(
            (i, j) for i, j in zip(materdata["sigma"], materdata["epsilon"])
        )

        # ===钢筋
        materdata = self.materials["steelbar"]
        self.steelbar_plasticity_model = tuple(
            (i, j) for i, j in zip(materdata["sigma"], materdata["epsilon"])
        )

    def load_geometry(self):
        (
            self.x_len,
            self.y_len,
            self.z_len,
            self.tube_thickness,
            self.concrete_seed,
            self.steel_seed,
            self.common_point,
        ) = (
            self.geometry["x_len"],
            self.geometry["y_len"],
            self.geometry["z_len"],
            self.geometry["tube_thickness"],
            self.geometry["concrete_grid_size"],
            self.geometry["steel_grid_size"],
            self.geometry["common_parameters"],
        )

    def load_referpoint(self):
        # ===顶部
        self.referpoint_top = self.taskparams["referpoint"]["top"]["position"]
        value = self.taskparams["referpoint"]["top"]["displacement"]
        self.displacement_top = tuple((UNSET if i is None else i) for i in value)

        # ===底部
        self.referpoint_bottom = self.taskparams["referpoint"]["bottom"]["position"]
        value = self.taskparams["referpoint"]["bottom"]["displacement"]
        self.displacement_bottom = tuple((UNSET if i is None else i) for i in value)

    def load_pullroll(self):
        self.rod_exist = bool(self.pullroll["pattern_rod"])
        self.pole_exist = bool(self.pullroll["pattern_pole"])
        self.flag_union = self.rod_exist or self.pole_exist

    def load_meta(self):
        self.caepath, self.jobname, self.modelname = (
            self.meta["caepath"].encode("ascii"),
            self.meta["jobname"].encode("ascii"),
            self.meta["modelname"].encode("ascii"),
        )

        self.work_stafile = os.getcwd() + "\\%s.sta" % self.jobname
        self.work_odbpath = (
            (os.getcwd() + "\\%s.odb" % self.jobname).decode("utf-8").encode("ascii")
        )

    @property
    def edge_point(self):
        return {
            "bottom_all": (
                (self.x_len / 2, 0, 0),
                (self.x_len / 2, self.y_len, 0),
                (0, self.y_len / 2, 0),
                (self.x_len, self.y_len / 2, 0),
            ),
            "top_all": (
                (self.x_len / 2, 0, self.z_len),
                (self.x_len / 2, self.y_len, self.z_len),
                (0, self.y_len / 2, self.z_len),
                (self.x_len, self.y_len / 2, self.z_len),
            ),
            "x_all": (
                (self.x_len / 2, 0, 0),
                (self.x_len / 2, self.y_len, 0),
                (self.x_len / 2, 0, self.z_len),
                (self.x_len / 2, self.y_len, self.z_len),
            ),
            "y_all": (
                (0, self.y_len / 2, 0),
                (self.x_len, self.y_len / 2, 0),
                (0, self.y_len / 2, self.z_len),
                (self.x_len, self.y_len / 2, self.z_len),
            ),
            "z_all": (
                (self.x_len, 0, self.z_len / 2),
                (0, self.y_len, self.z_len / 2),
                (0, 0, self.z_len / 2),
                (self.x_len, self.y_len, self.z_len / 2),
            ),
        }

    def run(self):
        # ===abaqus初始化
        print("task start at:" + self.caepath)
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
        print(self.modelname)
        mdb.Model(name=self.modelname, modelType=STANDARD_EXPLICIT)
        #: 新的模型数据库已创建.
        #: 模型 modelname 已创建.
        del mdb.models["Model-1"]

        # ===部件-混凝土
        s1 = mdb.models[self.modelname].ConstrainedSketch(
            name="__profile__", sheetSize=10000.0
        )
        g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
        s1.setPrimaryObject(option=STANDALONE)
        s1.rectangle(point1=(0.0, 0.0), point2=(self.x_len, self.y_len))
        p = mdb.models[self.modelname].Part(
            name="concrete", dimensionality=THREE_D, type=DEFORMABLE_BODY
        )
        p = mdb.models[self.modelname].parts["concrete"]
        p.BaseSolidExtrude(sketch=s1, depth=self.z_len)
        s1.unsetPrimaryObject()
        p = mdb.models[self.modelname].parts["concrete"]
        del mdb.models[self.modelname].sketches["__profile__"]

        # ===部件-钢管

        s = mdb.models[self.modelname].ConstrainedSketch(
            name="__profile__", sheetSize=10000.0
        )
        g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
        s.setPrimaryObject(option=STANDALONE)
        s.rectangle(point1=(0.0, 0.0), point2=(self.x_len, self.y_len))
        p = mdb.models[self.modelname].Part(
            name="tubelar", dimensionality=THREE_D, type=DEFORMABLE_BODY
        )
        p = mdb.models[self.modelname].parts["tubelar"]
        p.BaseShellExtrude(sketch=s, depth=self.z_len)
        s.unsetPrimaryObject()
        p = mdb.models[self.modelname].parts["tubelar"]
        del mdb.models[self.modelname].sketches["__profile__"]

        # ===材料-钢
        mdb.models[self.modelname].Material(name="steel_tube")
        mdb.models[self.modelname].materials["steel_tube"].Elastic(
            table=((206000.0, 0.25),)
        )
        mdb.models[self.modelname].materials["steel_tube"].Plastic(
            table=self.steel_plasticity_model
        )

        # ===创建材料-混凝土
        mdb.models[self.modelname].Material(name="concrete")
        mdb.models[self.modelname].materials["concrete"].ConcreteDamagedPlasticity(
            table=((40.0, 0.1, 1.16, 0.6667, 0.0005),)
        )
        mdb.models[self.modelname].materials[
            "concrete"
        ].concreteDamagedPlasticity.ConcreteCompressionHardening(
            table=self.concrete_plasticity_model
        )
        mdb.models[self.modelname].materials[
            "concrete"
        ].concreteDamagedPlasticity.ConcreteTensionStiffening(
            table=self.concrete_gfi, type=GFI
        )
        mdb.models[self.modelname].materials["concrete"].Elastic(
            table=((self.concrete_elastic_modulus, 0.2),)
        )

        # ===创建材料-拉杆
        mdb.models[self.modelname].Material(name="material_steelbar")
        mdb.models[self.modelname].materials["material_steelbar"].Elastic(
            table=((200000.0, 0.25),)
        )
        mdb.models[self.modelname].materials["material_steelbar"].Plastic(
            table=self.steelbar_plasticity_model
        )

        # ===创建截面-混凝土
        mdb.models[self.modelname].HomogeneousSolidSection(
            name="concrete", material="concrete", thickness=None
        )

        # ===创建截面-钢管
        mdb.models[self.modelname].HomogeneousShellSection(
            name="tubelar",
            preIntegrate=OFF,
            material="steel_tube",
            thicknessType=UNIFORM,
            thickness=self.tube_thickness,
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
        p = mdb.models[self.modelname].parts["concrete"]
        c = p.cells
        region = regionToolset.Region(cells=p.cells)
        p = mdb.models[self.modelname].parts["concrete"]
        p.SectionAssignment(
            region=region,
            sectionName="concrete",
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )

        # ===指派截面-钢管
        p = mdb.models[self.modelname].parts["tubelar"]
        region = regionToolset.Region(faces=p.faces)
        p = mdb.models[self.modelname].parts["tubelar"]
        p.SectionAssignment(
            region=region,
            sectionName="tubelar",
            offset=0.0,
            offsetType=BOTTOM_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )

        # ===分析步
        mdb.models[self.modelname].StaticStep(
            name="Step-1",
            previous="Initial",
            maxNumInc=10000,
            initialInc=0.01,
            minInc=1e-07,
            nlgeom=ON,
        )
        mdb.models[self.modelname].steps["Step-1"].setValues(
            stabilizationMethod=DISSIPATED_ENERGY_FRACTION,
            continueDampingFactors=True,
            adaptiveDampingRatio=0.05,
        )

        # ===装配
        a = mdb.models[self.modelname].rootAssembly

        # ===创建混凝土
        a.DatumCsysByDefault(CARTESIAN)
        p = mdb.models[self.modelname].parts["concrete"]
        a.Instance(name="concrete-1", part=p, dependent=ON)

        # ===创建钢管
        p = mdb.models[self.modelname].parts["tubelar"]
        a.Instance(name="%s-1" % "tubelar", part=p, dependent=ON)

        # ===创建拉杆
        if self.rod_exist:
            s1 = mdb.models[self.modelname].ConstrainedSketch(
                name="__profile__", sheetSize=200.0
            )
            g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
            s1.setPrimaryObject(option=STANDALONE)
            for p1, p2 in self.pullroll["pattern_rod"]:
                p1, p2 = map(tuple, (p1, p2))
                s1.Line(point1=p1, point2=p2)

            p = mdb.models[self.modelname].Part(
                name="rod_layer", dimensionality=THREE_D, type=DEFORMABLE_BODY
            )
            p = mdb.models[self.modelname].parts["rod_layer"]
            p.BaseWire(sketch=s1)
            s1.unsetPrimaryObject()
            p = mdb.models[self.modelname].parts["rod_layer"]
            del mdb.models[self.modelname].sketches["__profile__"]

        # ===创建部件-中心立杆
        s = mdb.models[self.modelname].ConstrainedSketch(
            name="__profile__", sheetSize=200.0
        )
        g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
        s.setPrimaryObject(option=STANDALONE)
        s.Line(
            point1=(0, 0),
            point2=(self.z_len, 0),
        )
        s.HorizontalConstraint(entity=g[2], addUndoState=False)
        p = mdb.models[self.modelname].Part(
            name="pole", dimensionality=THREE_D, type=DEFORMABLE_BODY
        )
        p = mdb.models[self.modelname].parts["pole"]
        p.BaseWire(sketch=s)
        s.unsetPrimaryObject()
        p = mdb.models[self.modelname].parts["pole"]
        del mdb.models[self.modelname].sketches["__profile__"]

        # ===创建截面-拉杆
        mdb.models[self.modelname].TrussSection(
            name="sec_rod_layer",
            material="material_steelbar",
            area=self.pullroll["area_rod"],
        )

        # ===创建截面-中心立杆
        mdb.models[self.modelname].TrussSection(
            name="pole",
            material="material_steelbar",
            area=self.pullroll["area_pole"],
        )

        # ===指派截面-拉杆
        if self.rod_exist:
            p = mdb.models[self.modelname].parts["rod_layer"]
            region = regionToolset.Region(edges=p.edges)
            p = mdb.models[self.modelname].parts["rod_layer"]
            p.SectionAssignment(
                region=region,
                sectionName="sec_rod_layer",
                offset=0.0,
                offsetType=MIDDLE_SURFACE,
                offsetField="",
                thicknessAssignment=FROM_SECTION,
            )

        # ===指派截面-中心立杆
        p = mdb.models[self.modelname].parts["pole"]
        region = regionToolset.Region(edges=p.edges)
        p = mdb.models[self.modelname].parts["pole"]
        p.SectionAssignment(
            region=region,
            sectionName="pole",
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )

        steel_union = tuple()

        # ===拉杆
        self.item_rod_cage = tuple()
        if self.rod_exist:
            # ===创建实例
            p = mdb.models[self.modelname].parts["rod_layer"]
            ins = a.Instance(name="rod_layer-1", part=p, dependent=ON)
            self.item_rod_cage += (ins,)
            # ===平移实例
            a1 = mdb.models[self.modelname].rootAssembly
            a1.translate(
                instanceList=("rod_layer-1",),
                vector=[0, 0, self.pullroll["layer_spacing"]],
            )
            # ===线性阵列实例(z方向)
            a1 = mdb.models[self.modelname].rootAssembly
            self.item_rod_cage += a1.LinearInstancePattern(
                instanceList=("rod_layer-1",),
                direction1=(0.0, 0.0, 1.0),
                direction2=(1.0, 0.0, 0.0),
                number1=self.pullroll["number_layers"],
                number2=1,
                spacing1=self.pullroll["layer_spacing"],
                spacing2=1.0,
            )

        # ===中心立杆
        self.item_poles = tuple()
        if self.pole_exist:
            for i, pos in enumerate(self.pullroll["pattern_pole"]):
                ins_name = "pole-%d" % (i + 1)
                pos += [0]
                # ===创建实例-中心立杆
                a1 = mdb.models[self.modelname].rootAssembly
                p = mdb.models[self.modelname].parts["pole"]
                a1.Instance(name=ins_name, part=p, dependent=ON)
                # ===旋转实例-中心立杆
                a1 = mdb.models[self.modelname].rootAssembly
                a1.rotate(
                    instanceList=(ins_name,),
                    axisPoint=(0, 0, 0),
                    axisDirection=(0, 0 + 1, 0),
                    angle=-90.0,
                )
                # ===平移实例-中心立杆
                a1 = mdb.models[self.modelname].rootAssembly
                a1.translate(
                    instanceList=(ins_name,),
                    vector=tuple(pos),
                )
                self.item_poles += (a1.instances[ins_name],)

        # ===Merge实例-拉杆
        if self.flag_union:
            a1 = mdb.models[self.modelname].rootAssembly
            steel_union = (
                (a1.instances["tubelar-1"],) + self.item_poles + self.item_rod_cage
            )

            a1.InstanceFromBooleanMerge(
                name="union",
                instances=steel_union,
                originalInstances=DELETE,
                mergeNodes=BOUNDARY_ONLY,
                nodeMergingTolerance=1e-06,
                domain=BOTH,
            )

        # ===创建参考点
        a = mdb.models[self.modelname].rootAssembly
        feature_1 = a.ReferencePoint(point=self.referpoint_bottom)
        a = mdb.models[self.modelname].rootAssembly
        feature_2 = a.ReferencePoint(point=self.referpoint_top)
        referpoint_bottom, referpoint_top = (
            a.referencePoints[feature_1.id],
            a.referencePoints[feature_2.id],
        )

        # ===创建底面刚体
        a = mdb.models[self.modelname].rootAssembly

        f1 = a.instances["concrete-1"].faces
        faces1 = f1.findAt(
            coordinates=tuple(
                [(self.x_len / 2, self.y_len / 2, 0)],
            )
        )
        if self.flag_union:
            e2 = a.instances["union-1"].edges
            edges2 = e2.findAt(coordinates=self.edge_point["bottom_all"])
        else:
            e2 = a.instances["tubelar-1"].edges
            edges2 = e2.findAt(coordinates=self.edge_point["bottom_all"])

        if self.pole_exist:
            v1 = a.instances["union-1"].vertices
            vert1 = v1.getByBoundingBox(
                0 + self.gap,
                0 + self.gap,
                0 - self.gap,
                self.x_len - self.gap,
                self.y_len - self.gap,
                0 + self.gap,
            )
            region4 = regionToolset.Region(edges=edges2, faces=faces1, vertices=vert1)
        else:
            region4 = regionToolset.Region(edges=edges2, faces=faces1)

        a = mdb.models[self.modelname].rootAssembly
        r1 = a.referencePoints

        refPoints1 = (referpoint_bottom,)
        region1 = regionToolset.Region(referencePoints=refPoints1)
        mdb.models[self.modelname].RigidBody(
            name="ct_bottom", refPointRegion=region1, tieRegion=region4
        )

        # ===创建顶面刚体
        a = mdb.models[self.modelname].rootAssembly
        f1 = a.instances["concrete-1"].faces
        faces1 = f1.findAt(
            coordinates=tuple(
                [(self.x_len / 2, self.y_len / 2, self.z_len)],
            )
        )
        if self.flag_union:
            e2 = a.instances["union-1"].edges
            edges2 = e2.findAt(coordinates=self.edge_point["top_all"])
        else:
            e2 = a.instances["tubelar-1"].edges
            edges2 = e2.findAt(coordinates=self.edge_point["top_all"])

        if self.pole_exist:
            v1 = a.instances["union-1"].vertices
            vert1 = v1.getByBoundingBox(
                0 + self.gap,
                0 + self.gap,
                self.z_len - self.gap,
                self.x_len - self.gap,
                self.y_len - self.gap,
                self.z_len + self.gap,
            )
            region4 = regionToolset.Region(edges=edges2, faces=faces1, vertices=vert1)
        else:
            region4 = regionToolset.Region(edges=edges2, faces=faces1)

        a = mdb.models[self.modelname].rootAssembly
        r1 = a.referencePoints
        refPoints1 = (referpoint_top,)
        region1 = regionToolset.Region(referencePoints=refPoints1)
        mdb.models[self.modelname].RigidBody(
            name="cp_top", refPointRegion=region1, tieRegion=region4
        )

        # ===边界条件-底部
        a = mdb.models[self.modelname].rootAssembly
        r1 = a.referencePoints
        refPoints1 = (referpoint_bottom,)
        region = regionToolset.Region(referencePoints=refPoints1)
        mdb.models[self.modelname].DisplacementBC(
            name="bound_bottom",
            createStepName="Step-1",
            region=region,
            u1=self.displacement_bottom[0],
            u2=self.displacement_bottom[1],
            u3=self.displacement_bottom[2],
            ur1=self.displacement_bottom[3],
            ur2=self.displacement_bottom[4],
            ur3=self.displacement_bottom[5],
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
        a = mdb.models[self.modelname].rootAssembly
        r1 = a.referencePoints
        refPoints1 = (referpoint_top,)
        region = regionToolset.Region(referencePoints=refPoints1)
        mdb.models[self.modelname].DisplacementBC(
            name="bound_top",
            createStepName="Step-1",
            region=region,
            u1=self.displacement_top[0],
            u2=self.displacement_top[1],
            u3=self.displacement_top[2],
            ur1=self.displacement_top[3],
            ur2=self.displacement_top[4],
            ur3=self.displacement_top[5],
            amplitude=UNSET,
            fixed=OFF,
            distributionType=UNIFORM,
            fieldName="",
            localCsys=None,
        )

        # ===创建相互作用属性-钢管-混凝土(硬接触和摩擦)
        mdb.models[self.modelname].ContactProperty("tube-concrete")
        mdb.models[self.modelname].interactionProperties[
            "tube-concrete"
        ].TangentialBehavior(
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
        mdb.models[self.modelname].interactionProperties[
            "tube-concrete"
        ].NormalBehavior(
            pressureOverclosure=HARD,
            allowSeparation=ON,
            constraintEnforcementMethod=DEFAULT,
        )

        # ===创建相互作用-钢管-混凝土
        a = mdb.models[self.modelname].rootAssembly
        if self.flag_union:
            s1 = a.instances["union-1"].faces
            side2Faces1 = s1.getSequenceFromMask(
                mask=("[#f ]",),
            )
        else:
            s1 = a.instances["tubelar-1"].faces
            side2Faces1 = s1.getSequenceFromMask(
                mask=("[#f ]",),
            )
        region1 = regionToolset.Region(side2Faces=side2Faces1)
        a = mdb.models[self.modelname].rootAssembly
        s1 = a.instances["concrete-1"].faces
        side1Faces1 = s1.getSequenceFromMask(
            mask=("[#f ]",),
        )
        region2 = regionToolset.Region(side1Faces=side1Faces1)
        mdb.models[self.modelname].SurfaceToSurfaceContactStd(
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

        # ===相互作用-钢筋-混凝土
        if self.flag_union:
            a1 = mdb.models[self.modelname].rootAssembly
            e1 = a1.instances["union-1"].edges
            edges1 = e1.getByBoundingCylinder(
                center1=(self.x_len / 2, self.y_len / 2, 0),
                center2=(self.x_len / 2, self.y_len / 2, self.z_len),
                radius=math.sqrt(self.x_len * self.x_len + self.y_len * self.y_len)
                - self.gap,
            )
            region1 = regionToolset.Region(edges=edges1)
            mdb.models[self.modelname].EmbeddedRegion(
                name="roll-concrete",
                embeddedRegion=region1,
                hostRegion=None,
                weightFactorTolerance=1e-06,
                absoluteTolerance=0.0,
                fractionalTolerance=0.05,
                toleranceMethod=BOTH,
            )

        # ===单元类型-桁架
        if self.flag_union:
            elemType1 = mesh.ElemType(elemCode=T3D2, elemLibrary=STANDARD)
            p = mdb.models[self.modelname].parts["union"]
            e = p.edges
            edges = e.getByBoundingCylinder(
                center1=(self.x_len / 2, self.y_len / 2, 0),
                center2=(self.x_len / 2, self.y_len / 2, self.z_len),
                radius=math.sqrt(self.x_len * self.x_len + self.y_len * self.y_len)
                - self.gap,
            )
            pickedRegions = (edges,)
            p.setElementType(regions=pickedRegions, elemTypes=(elemType1,))
        # ===划分网格-steel
        if self.flag_union:
            p = mdb.models[self.modelname].parts["union"]
        else:
            p = mdb.models[self.modelname].parts["tubelar"]
        p.seedPart(
            size=max(self.x_len, self.y_len), deviationFactor=0.1, minSizeFactor=0.1
        )
        e = p.edges
        for i, j in zip(["x_all", "y_all", "z_all"], [0, 1, 2]):
            pickedEdges = e.findAt(coordinates=self.edge_point[i])
            p.seedEdgeBySize(
                edges=pickedEdges,
                size=self.steel_seed[j],
                deviationFactor=0.1,
                minSizeFactor=0.1,
                constraint=FINER,
            )

        if self.flag_union:
            p = mdb.models[self.modelname].parts["union"]
        else:
            p = mdb.models[self.modelname].parts["tubelar"]
        p.generateMesh()
        # ===划分网格-concrete
        p = mdb.models[self.modelname].parts["concrete"]
        e = p.edges
        for i, j in zip(["x_all", "y_all", "z_all"], [0, 1, 2]):
            pickedEdges = e.findAt(coordinates=self.edge_point[i])
            p.seedEdgeBySize(
                edges=pickedEdges,
                size=self.concrete_seed[j],
                deviationFactor=0.1,
                minSizeFactor=0.1,
                constraint=FINER,
            )
        p = mdb.models[self.modelname].parts["concrete"]
        p.generateMesh()

        # ===创建集
        a = mdb.models[self.modelname].rootAssembly
        r1 = a.referencePoints
        refPoints1 = (referpoint_top,)
        a.Set(referencePoints=refPoints1, name="RP-TOP")

        # ===历程输出
        regionDef = mdb.models[self.modelname].rootAssembly.sets["RP-TOP"]
        mdb.models[self.modelname].HistoryOutputRequest(
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
            name=self.jobname,
            model=self.modelname,
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
            numCpus=6,
            numDomains=6,
            numGPUs=1,
        )
        # ===保存
        mdb.saveAs(pathName=self.caepath)

        # ===切换窗口
        a = mdb.models[self.modelname].rootAssembly
        a.regenerate()
        a = mdb.models[self.modelname].rootAssembly
        session.viewports["Viewport: 1"].setValues(displayedObject=a)
        session.viewports["Viewport: 1"].assemblyDisplay.setValues(
            optimizationTasks=OFF, geometricRestrictions=OFF, stopConditions=OFF
        )

        # ===提交
        if self.meta["submit"]:
            # ===作业开始
            st_time = time.time()
            try:
                mdb.jobs[self.jobname].submit()

                line = 5
                job_running = True
                stafile = self.work_stafile
                # ===输出status
                status_output = 30
                while not os.path.isfile(stafile) and status_output:
                    time.sleep(10)
                    status_output -= 1
                if status_output:
                    with io.open(stafile, "rt", encoding="gbk") as f:
                        while job_running:
                            f.seek(0, 0)
                            status = f.read().splitlines()
                            for i in range(line, len(status)):
                                line_content = status[i]
                                if "COMPLETED" in line_content:
                                    job_running = False
                                    break
                                if (
                                    self.meta["time_limit"]
                                    and time.time() - st_time > self.meta["time_limit"]
                                ):
                                    raise Exception("job time out")
                                print(line_content)
                                print("time used: ", time.time() - st_time)
                                line += 1
                            time.sleep(20)

                mdb.jobs[self.jobname].waitForCompletion()
                job_time = time.time() - st_time
                print("job running time(s):", job_time)
            except Exception:
                traceback.print_exc()
                mdb.jobs[self.jobname].kill()

            try:
                odbpath = self.work_odbpath
                odb = session.openOdb(name=odbpath)

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
                    "sigma(kN)": [-i[1] / 1000 for i in xy0],
                    "epsilon": [-i[1] / self.z_len for i in xy1],
                    "time": [i[0] for i in xy0],
                }

                data = {"top_point": top_point_data, "time_used": job_time}
                Utils.write_json(
                    data,
                    self.meta["taskfolder"] + "\\result.json",
                )
                Utils.write_json(
                    self.taskparams,
                    self.meta["taskfolder"] + "\\input.json",
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
                avipath = self.meta["taskfolder"].replace("\\", "/") + "/animation.avi"
                avipath = avipath.decode("utf-8").encode("ascii")
                session.writeImageAnimation(
                    fileName=avipath,
                    format=AVI,
                    canvasObjects=(session.viewports["Viewport: 1"],),
                )
                print("animation saved")

                # ===复制odb文件
                shutil.copy(
                    odbpath, self.meta["taskfolder"] + "\\%s.odb" % self.jobname
                )
                print("odb copied")
            except Exception:
                traceback.print_exc()


control_json_path = os.path.join(TASK_FOLDER, "control.json")
control_json = Utils.load_json(control_json_path)


i = control_json["start_at"]

while 1:
    control_json = Utils.load_json(control_json_path)
    flag = control_json["flag"]
    if flag == 0:
        pass
    elif flag == 1:
        time.sleep(60)
        print("task suspended")
        continue
    elif flag == 2:
        break

    json_path = TASK_FOLDER + "\\%d.json" % i
    if not os.path.isfile(json_path):
        break
    print("task:", json_path)

    taskparams = Utils.load_json(json_path)
    TaskHandler(taskparams).run()

    i += 1
