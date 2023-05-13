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

task_path = "C:\\Users\\Tiki_\\Desktop\\abaqus_exe\\tasks.json"


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


class TaskHandler:
    def __init__(self, taskparams):
        self.taskparams = taskparams
        self.gap = 3
        self.load_params()
        self.load_material()
        self.load_geometry()
        self.load_referpoint()
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
        ) = (
            self.geometry["x_len"],
            self.geometry["y_len"],
            self.geometry["z_len"],
            self.geometry["tube_thickness"],
            self.geometry["concrete_seed"],
            self.geometry["steel_seed"],
        )

    def load_referpoint(self):
        # ===顶部
        rp = self.taskparams["referpoint"]["top"]["shift"]
        self.referpoint_top = (
            self.x_len / 2 + rp[0],
            self.y_len / 2 + rp[1],
            self.z_len + rp[2],
        )

        value = self.taskparams["referpoint"]["top"]["displacement"]
        self.displacement_top = tuple((UNSET if i is None else i) for i in value)

        # ===底部
        rp = self.taskparams["referpoint"]["bottom"]["shift"]
        self.referpoint_bottom = (self.x_len / 2 + rp[0], self.y_len / 2 + rp[1], rp[2])

        value = self.taskparams["referpoint"]["bottom"]["displacement"]
        self.displacement_bottom = tuple((UNSET if i is None else i) for i in value)

    def load_meta(self):
        self.caepath, self.jobname, self.modelname = (
            self.meta["caepath"].encode("ascii"),
            self.meta["jobname"].encode("ascii"),
            self.meta["modelname"].encode("ascii"),
        )

        self.work_stafile = (
            "D:/Environment/Appdata/AbaqusData/Temp/%s.sta" % self.jobname
        )
        self.work_odbpath = (
            ("D:/Environment/Appdata/AbaqusData/Temp/%s.odb" % self.jobname)
            .decode("utf-8")
            .encode("ascii")
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
                (self.x_len, self.y_len, self.z_len / 2),
                (0, self.y_len, self.z_len / 2),
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
        tubelar_name = (
            "tubelar"
            if (self.pullroll["x_exist"] or self.pullroll["y_exist"])
            else "union"
        )

        s = mdb.models[self.modelname].ConstrainedSketch(
            name="__profile__", sheetSize=10000.0
        )
        g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
        s.setPrimaryObject(option=STANDALONE)
        s.rectangle(point1=(0.0, 0.0), point2=(self.x_len, self.y_len))
        p = mdb.models[self.modelname].Part(
            name=tubelar_name, dimensionality=THREE_D, type=DEFORMABLE_BODY
        )
        p = mdb.models[self.modelname].parts[tubelar_name]
        p.BaseShellExtrude(sketch=s, depth=self.z_len)
        s.unsetPrimaryObject()
        p = mdb.models[self.modelname].parts[tubelar_name]
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
            table=((36.0, 0.1, 1.16, 0.63, 0.0005),)
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
            table=((34500.0, 0.2),)
        )

        # ===创建材料-拉杆
        mdb.models[self.modelname].Material(name="steel_pullroll")
        mdb.models[self.modelname].materials["steel_pullroll"].Elastic(
            table=((200000.0, 0.25),)
        )
        mdb.models[self.modelname].materials["steel_pullroll"].Plastic(
            table=self.steelbar_plasticity_model
        )

        # ===创建截面-混凝土
        mdb.models[self.modelname].HomogeneousSolidSection(
            name="concrete", material="concrete", thickness=None
        )

        # ===创建截面-钢管
        mdb.models[self.modelname].HomogeneousShellSection(
            name=tubelar_name,
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
        p = mdb.models[self.modelname].parts[tubelar_name]
        region = regionToolset.Region(faces=p.faces)
        p = mdb.models[self.modelname].parts[tubelar_name]
        p.SectionAssignment(
            region=region,
            sectionName=tubelar_name,
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
            minInc=1e-06,
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
        p = mdb.models[self.modelname].parts[tubelar_name]
        a.Instance(name="%s-1" % tubelar_name, part=p, dependent=ON)

        if not self.pullroll["ushape"]:
            # ===创建部件-拉杆X
            s = mdb.models[self.modelname].ConstrainedSketch(
                name="__profile__", sheetSize=200.0
            )
            g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
            s.setPrimaryObject(option=STANDALONE)
            s.Line(point1=(0, 0), point2=(self.x_len, 0))
            s.HorizontalConstraint(entity=g[2], addUndoState=False)
            p = mdb.models[self.modelname].Part(
                name="pullroll_x", dimensionality=THREE_D, type=DEFORMABLE_BODY
            )
            p = mdb.models[self.modelname].parts["pullroll_x"]
            p.BaseWire(sketch=s)
            s.unsetPrimaryObject()
            p = mdb.models[self.modelname].parts["pullroll_x"]
            del mdb.models[self.modelname].sketches["__profile__"]
            # ===创建部件-拉杆Y
            s1 = mdb.models[self.modelname].ConstrainedSketch(
                name="__profile__", sheetSize=200.0
            )
            g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
            s1.setPrimaryObject(option=STANDALONE)
            s1.Line(point1=(0, 0), point2=(0, self.y_len))
            s1.VerticalConstraint(entity=g[2], addUndoState=False)
            p = mdb.models[self.modelname].Part(
                name="pullroll_y", dimensionality=THREE_D, type=DEFORMABLE_BODY
            )
            p = mdb.models[self.modelname].parts["pullroll_y"]
            p.BaseWire(sketch=s1)
            s1.unsetPrimaryObject()
            p = mdb.models[self.modelname].parts["pullroll_y"]
            del mdb.models[self.modelname].sketches["__profile__"]
        else:
            # ===创建部件-拉杆x
            s1 = mdb.models[self.modelname].ConstrainedSketch(
                name="__profile__", sheetSize=200.0
            )
            g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
            s1.setPrimaryObject(option=STANDALONE)
            s1.Line(
                point1=(0, self.gap),
                point2=(self.x_len / 2, 0),
            )
            s1.Line(
                point1=(0, 0 - self.gap),
                point2=(self.x_len / 2, 0),
            )
            s1.Line(
                point1=(self.x_len, 0 + self.gap),
                point2=(self.x_len / 2, 0),
            )
            s1.Line(
                point1=(self.x_len, 0 - self.gap),
                point2=(self.x_len / 2, 0),
            )
            p = mdb.models[self.modelname].Part(
                name="pullroll_x", dimensionality=THREE_D, type=DEFORMABLE_BODY
            )
            p = mdb.models[self.modelname].parts["pullroll_x"]
            p.BaseWire(sketch=s1)
            s1.unsetPrimaryObject()
            p = mdb.models[self.modelname].parts["pullroll_x"]
            del mdb.models[self.modelname].sketches["__profile__"]

            # ===创建部件-拉杆y
            s1 = mdb.models[self.modelname].ConstrainedSketch(
                name="__profile__", sheetSize=200.0
            )
            g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
            s1.setPrimaryObject(option=STANDALONE)
            s1.Line(
                point1=(0 + self.gap, 0),
                point2=(0, self.y_len / 2),
            )
            s1.Line(
                point1=(0 - self.gap, 0),
                point2=(0, self.y_len / 2),
            )
            s1.Line(
                point1=(0 + self.gap, self.y_len),
                point2=(0, self.y_len / 2),
            )
            s1.Line(
                point1=(0 - self.gap, self.y_len),
                point2=(0, self.y_len / 2),
            )
            p = mdb.models[self.modelname].Part(
                name="pullroll_y", dimensionality=THREE_D, type=DEFORMABLE_BODY
            )
            p = mdb.models[self.modelname].parts["pullroll_y"]
            p.BaseWire(sketch=s1)
            s1.unsetPrimaryObject()
            p = mdb.models[self.modelname].parts["pullroll_y"]
            session.viewports["Viewport: 1"].setValues(displayedObject=p)
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
            name="center_roll", dimensionality=THREE_D, type=DEFORMABLE_BODY
        )
        p = mdb.models[self.modelname].parts["center_roll"]
        p.BaseWire(sketch=s)
        s.unsetPrimaryObject()
        p = mdb.models[self.modelname].parts["center_roll"]
        del mdb.models[self.modelname].sketches["__profile__"]

        # ===创建截面-拉杆X
        mdb.models[self.modelname].TrussSection(
            name="pullroll_x",
            material="steel_pullroll",
            area=self.pullroll["area"],
        )

        # ===创建截面-拉杆Y
        mdb.models[self.modelname].TrussSection(
            name="pullroll_y",
            material="steel_pullroll",
            area=self.pullroll["area"],
        )

        # ===创建截面-中心立杆
        mdb.models[self.modelname].TrussSection(
            name="center_roll",
            material="steel_pullroll",
            area=self.pullroll["area_center"],
        )

        # ===指派截面-拉杆X
        p = mdb.models[self.modelname].parts["pullroll_x"]
        region = regionToolset.Region(edges=p.edges)
        p = mdb.models[self.modelname].parts["pullroll_x"]
        p.SectionAssignment(
            region=region,
            sectionName="pullroll_x",
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )

        # ===指派截面-拉杆Y
        p = mdb.models[self.modelname].parts["pullroll_y"]
        region = regionToolset.Region(edges=p.edges)
        p = mdb.models[self.modelname].parts["pullroll_y"]
        p.SectionAssignment(
            region=region,
            sectionName="pullroll_y",
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )

        # ===指派截面-中心立杆
        p = mdb.models[self.modelname].parts["center_roll"]
        region = regionToolset.Region(edges=p.edges)
        p = mdb.models[self.modelname].parts["center_roll"]
        p.SectionAssignment(
            region=region,
            sectionName="center_roll",
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )

        steel_union = tuple()

        # ===拉杆
        for orientation in ("x", "y"):
            """拉杆方向"""
            orientation_union = tuple()
            if self.pullroll["%s_exist" % orientation]:
                # ===创建实例
                p = mdb.models[self.modelname].parts["pullroll_%s" % orientation]
                ins = a.Instance(
                    name="pullroll_%s-1" % orientation, part=p, dependent=ON
                )
                orientation_union += (ins,)
                # ===平移实例
                a1 = mdb.models[self.modelname].rootAssembly
                startvector = (
                    (
                        0.0,
                        self.pullroll["x_distance"],
                        self.pullroll["z_distance"],
                    )
                    if orientation == "x"
                    else (
                        self.pullroll["y_distance"],
                        0.0,
                        self.pullroll["z_distance"],
                    )
                )
                a1.translate(
                    instanceList=("pullroll_%s-1" % orientation,),
                    vector=startvector,
                )
                # ===线性阵列实例(z方向)
                a1 = mdb.models[self.modelname].rootAssembly
                orientation_direction = (
                    (0.0, 1.0, 0.0) if orientation == "x" else (1.0, 0.0, 0.0)
                )
                orientation_union += a1.LinearInstancePattern(
                    instanceList=("pullroll_%s-1" % orientation,),
                    direction1=(0.0, 0.0, 1.0),
                    direction2=orientation_direction,
                    number1=self.pullroll["z_number"],
                    number2=self.pullroll["%s_number" % orientation],
                    spacing1=self.pullroll["z_distance"],
                    spacing2=self.pullroll["%s_distance" % orientation],
                )

                # ===中心立杆
                if self.pullroll["ushape"]:
                    # ===创建实例-中心立杆
                    a1 = mdb.models[self.modelname].rootAssembly
                    p = mdb.models[self.modelname].parts["center_roll"]
                    a1.Instance(
                        name="center_roll-%s-1" % orientation, part=p, dependent=ON
                    )
                    # ===旋转实例-中心立杆
                    a1 = mdb.models[self.modelname].rootAssembly
                    a1.rotate(
                        instanceList=("center_roll-%s-1" % orientation,),
                        axisPoint=(0, 0, 0),
                        axisDirection=(0, 0 + 1, 0),
                        angle=-90.0,
                    )
                    orientation_union += (
                        a1.instances["center_roll-%s-1" % orientation],
                    )
                    # ===平移实例-中心立杆
                    a1 = mdb.models[self.modelname].rootAssembly
                    startvector = (
                        (
                            self.x_len / 2,
                            self.pullroll["x_distance"],
                            0,
                        )
                        if orientation == "x"
                        else (
                            self.pullroll["y_distance"],
                            self.y_len / 2,
                            0,
                        )
                    )
                    a1.translate(
                        instanceList=("center_roll-%s-1" % orientation,),
                        vector=startvector,
                    )

                    # ===线性阵列实例
                    orientation_direction = (
                        (0.0, 1.0, 0.0) if orientation == "x" else (1.0, 0.0, 0.0)
                    )
                    number = self.pullroll["%s_number" % orientation]
                    spacing = self.pullroll["%s_distance" % orientation]
                    a1 = mdb.models[self.modelname].rootAssembly
                    orientation_union += a1.LinearInstancePattern(
                        instanceList=("center_roll-%s-1" % orientation,),
                        direction1=orientation_direction,
                        direction2=(0.0, 0.0, 1.0),
                        number1=number,
                        number2=1,
                        spacing1=spacing,
                        spacing2=1.0,
                    )
            steel_union += orientation_union

        # ===合并实例-拉杆
        if steel_union:
            a1 = mdb.models[self.modelname].rootAssembly
            steel_union += (a1.instances["tubelar-1"],)

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
        e2 = a.instances["union-1"].edges
        edges2 = e2.findAt(coordinates=self.edge_point["bottom_all"])

        if self.pullroll["ushape"] and (
            self.pullroll["x_exist"] or self.pullroll["y_exist"]
        ):
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
        e2 = a.instances["union-1"].edges
        edges2 = e2.findAt(coordinates=self.edge_point["top_all"])

        if self.pullroll["ushape"] and (
            self.pullroll["x_exist"] or self.pullroll["y_exist"]
        ):
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
        s1 = a.instances["union-1"].faces
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
        # ===划分网格-union
        p = mdb.models[self.modelname].parts["union"]
        p.seedPart(size=self.steel_seed[0], deviationFactor=0.1, minSizeFactor=0.1)
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

        p = mdb.models[self.modelname].parts["union"]
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
                    self.data,
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


i = 0
while 1:
    json_path = "C:\\Users\\Tiki_\\Desktop\\abaqus_exe\\tasks\\%d.json" % i
    if not os.path.isfile(json_path):
        break
    print("task:", json_path)

    taskparams = Utils.load_json(json_path)
    TaskHandler(taskparams).run()

    i += 1
