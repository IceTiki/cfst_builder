# -*- coding: utf-8 -*-
# abaqus库
from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup

# 标准库
import math
import json
import io
import time
import os
import traceback
import sys
import urllib2

ORIGIN_WORKDIR = os.path.abspath(os.getcwd())


class Path:
    def __init__(self, path):
        if isinstance(path, self.__class__):
            self.__dict__.update(path.__dict__)
        elif isinstance(path, str):
            self.path = path

    def __str__(self):
        return self.path

    def __div__(self, path):
        new_path = os.path.join(self.path, str(path))
        return self.__class__(new_path)

    def __rdiv__(self, path):
        new_path = os.path.join(str(path), self.path)
        return self.__class__(new_path)

    @property
    def absolote(self):
        return self.__class__(os.path.abspath(self.path))

    @property
    def parent(self):
        return self.__class__(os.path.dirname(self.path))

    @property
    def name(self):
        """
        Returns
        ---
        name : str
            文件名
        """
        return os.path.split(self.path)[1]

    @property
    def exists(self):
        return os.path.exists(self.path)

    def traversing_generator(
        self, iter_file=True, topdown=False, path_filter=lambda x: True
    ):
        """
        遍历路径中的文件或文件夹的生成器(生成绝对路径)
        iter_file : bool
            True遍历文件|False遍历文件夹
        topdown : bool
            是否从根文件夹开始遍历
        path_filter : Callable
            Callable返回绝对路径之前, 先用该过滤器过滤
            过滤器: 接受绝对路径(Path), 传出布尔值(bool)

        Yields
        ---
        item : Path
            文件夹内的文件/文件夹的绝对路径
        """
        for root, dirs, files in os.walk(self.path, topdown=topdown):
            root = Path(root)
            if iter_file is True:
                for name in files:
                    file_dir = root / name
                    file_dir = file_dir.absolote
                    if path_filter(file_dir):
                        yield file_dir
            if iter_file is False:
                for name in dirs:
                    folder_dir = root / name
                    folder_dir = folder_dir.absolote
                    if path_filter(folder_dir):
                        yield folder_dir

    def mkdirs(self):
        if os.path.isdir(self.path):
            return True
        elif os.path.isfile(self.path):
            raise ValueError("%s is a file" % self.path)
        else:
            os.makedirs(name=self.path)
            return True


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
    def format_time(with_date=False):
        time_struct = time.localtime()
        date_str = "%d-%d-%d" % (
            time_struct.tm_year,
            time_struct.tm_mon,
            time_struct.tm_mday,
        )
        time_str = "%d-%d-%d" % (
            time_struct.tm_hour,
            time_struct.tm_min,
            time_struct.tm_sec,
        )
        if with_date:
            return "%s--%s" % (date_str, time_str)
        return time_str


class Log:
    log_path = os.path.join(ORIGIN_WORKDIR, "%s_log.txt" % Utils.format_time(True))
    log_txt_file = io.open(log_path, "a", encoding="utf-8")

    @classmethod
    def log(cla, *args, **kwargs):
        kwargs.setdefault("seq", " ")
        args = map(
            lambda x: x.encode("unicode_escape").decode("ascii")
            if isinstance(x, unicode)
            else str(x),
            args,
        )
        fm_str = kwargs["seq"].join(list(args))
        fm_str = "|||%s|||\n%s" % (Utils.format_time(True), fm_str)
        print(fm_str)

        cla.log_txt_file.write((fm_str + "\n").decode("utf-8"))
        cla.log_txt_file.flush()


class TaskExecutor:
    def __init__(self, taskparams, workdir="./"):
        self.taskparams = taskparams
        self.workdir = workdir

        params = self.taskparams
        # ===一级释放
        (
            self.materials,
            self.geometry,
            self.referpoint,
            self.rod_pattern,
            self.meta,
            self.misc,
            self.comment,
        ) = (
            params["materials"],
            params["geometry"],
            params["referpoint"],
            params["rod_pattern"],
            params["meta"],
            params["misc"],
            params["comment"],
        )

        materials = self.materials

        def load_steel(params):
            return {
                "plastic_model": tuple(
                    (i, j) for i, j in zip(params["sigma"], params["epsilon"])
                ),
                "elastic_modulus": params["elastic_modulus"],
                "poissons_ratio": params["poissons_ratio"],
            }

        # ===材料-混凝土
        mtl_concrete_params = materials["concrete"]
        self.mtl_concrete = {
            "plastic_model": tuple(
                (i, j)
                for i, j in zip(
                    mtl_concrete_params["sigma"], mtl_concrete_params["epsilon"]
                )
            ),
            "gfi_table": (
                mtl_concrete_params["strength_fracture"],
                mtl_concrete_params["gfi"],
            ),
            "elastic_modulus": mtl_concrete_params["elastic_modulus"],
            "poissons_ratio": mtl_concrete_params["poissons_ratio"],
            "cdp_params": mtl_concrete_params["cdp_params"],
        }

        # ===材料-钢管
        mtl_tubelar_params = self.materials["tubelar"]
        self.mtl_tubelar = load_steel(mtl_tubelar_params)

        # ===材料-约束拉杆
        mtl_rod_params = self.materials["rod"]
        self.mtl_rod = load_steel(mtl_rod_params)

        # ===材料-中心立杆
        mtl_pole_params = self.materials["pole"]
        self.mtl_pole = load_steel(mtl_pole_params)

        # ===几何
        (
            self.x_len,
            self.y_len,
            self.z_len,
            self.tubelar_thickness,
            self.concrete_seed,
            self.steel_seed,
            self.grid_minsize,
        ) = (
            self.geometry["x_len"],
            self.geometry["y_len"],
            self.geometry["z_len"],
            self.geometry["tubelar_thickness"],
            self.geometry["concrete_grid_size"],
            self.geometry["steel_grid_size"],
            self.geometry["grid_minsize"],
        )

        # ===参考点
        referpoint = self.referpoint
        self.referpoint_top = {
            "position": referpoint["top"]["position"],
            "displacement": tuple(
                (UNSET if i is None else i) for i in referpoint["top"]["displacement"]
            ),
        }
        self.referpoint_bottom = {
            "position": referpoint["bottom"]["position"],
            "displacement": tuple(
                (UNSET if i is None else i)
                for i in referpoint["bottom"]["displacement"]
            ),
        }

        # ===约束拉杆样式
        self.rod_exist = bool(self.rod_pattern["pattern_rod"])
        self.pole_exist = bool(self.rod_pattern["pattern_pole"])
        self.union_exist = self.rod_exist or self.pole_exist

        # ===元参数
        meta_info = self.meta
        (
            self.jobname,
            self.caepath,
            self.taskfolder,
            self.modelname,
        ) = map(
            str,
            (
                meta_info["jobname"],
                meta_info["caepath"],
                meta_info["taskfolder"],
                meta_info["modelname"],
            ),
        )

        self.workdir_statusfile = os.path.join(self.workdir, "%s.sta" % self.jobname)
        self.workdir_odb = os.path.join(self.workdir, "\%s.odb" % self.jobname)
        self.gap = meta_info["gap"]

        # 杂项参数
        self.misc["friction_factor_between_concrete_tubelar"] = self.misc.pop(
            "friction_factor_between_concrete_tubelar"
        )
        self.misc["tubelar_num_int_pts"] = self.misc.pop("tubelar_num_int_pts")
        performance_params = self.misc["performance"]
        self.performance = {
            "memory": performance_params["memory"],
            "num_cpus": performance_params["num_cpus"],
            "num_gpus": performance_params["num_gpus"],
        }
        static_step_params = self.misc["static_step"]
        self.static_step = {
            "max_num_inc": static_step_params["max_num_inc"],
            "initial_inc": static_step_params["initial_inc"],
            "min_inc": static_step_params["min_inc"],
            "nlgeom": SymbolicConstant(
                str(static_step_params["nlgeom"])
            ),  # SymbolicConstant可能仅支持str不支持unicode
            "stabilization_method": SymbolicConstant(
                str(static_step_params["stabilization_method"])
            ),
            "continue_damping_factors": static_step_params["continue_damping_factors"],
            "adaptive_damping_ratio": static_step_params["adaptive_damping_ratio"],
        }

    @property
    def edge_point(self):
        x_len, y_len, z_len = self.x_len, self.y_len, self.z_len
        return {
            "bottom_all": (
                (x_len / 2.0, 0, 0),
                (x_len / 2.0, y_len, 0),
                (0, y_len / 2.0, 0),
                (x_len, y_len / 2.0, 0),
            ),
            "top_all": (
                (x_len / 2.0, 0, z_len),
                (x_len / 2.0, y_len, z_len),
                (0, y_len / 2.0, z_len),
                (x_len, y_len / 2.0, z_len),
            ),
            "x_all": (
                (x_len / 2.0, 0, 0),
                (x_len / 2.0, y_len, 0),
                (x_len / 2.0, 0, z_len),
                (x_len / 2.0, y_len, z_len),
            ),
            "y_all": (
                (0, y_len / 2.0, 0),
                (x_len, y_len / 2.0, 0),
                (0, y_len / 2.0, z_len),
                (x_len, y_len / 2.0, z_len),
            ),
            "z_all": (
                (x_len, 0, z_len / 2.0),
                (0, y_len, z_len / 2.0),
                (0, 0, z_len / 2.0),
                (x_len, y_len, z_len / 2.0),
            ),
        }

    def run(self):
        # ===abaqus初始化
        print("SCIIPT> task running at: ", self.caepath)
        print("SCIIPT> model name is: ", self.modelname)
        # ===初始化常用变量
        Mdb()
        task_model = mdb.Model(name=self.modelname, modelType=STANDARD_EXPLICIT)
        del mdb.models["Model-1"]
        x_len, y_len, z_len = self.x_len, self.y_len, self.z_len
        gap = self.gap

        # ======创建部件======
        # ===混凝土
        s1 = task_model.ConstrainedSketch(name="__profile__", sheetSize=10000.0)
        g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
        s1.setPrimaryObject(option=STANDALONE)
        s1.rectangle(point1=(0.0, 0.0), point2=(x_len, y_len))
        part_concrete = task_model.Part(
            name="part_concrete", dimensionality=THREE_D, type=DEFORMABLE_BODY
        )
        part_concrete.BaseSolidExtrude(sketch=s1, depth=z_len)
        s1.unsetPrimaryObject()
        # ===钢管
        s = task_model.ConstrainedSketch(name="__profile__", sheetSize=10000.0)
        g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
        s.setPrimaryObject(option=STANDALONE)
        s.rectangle(point1=(0.0, 0.0), point2=(x_len, y_len))
        part_tubelar = task_model.Part(
            name="part_tubelar", dimensionality=THREE_D, type=DEFORMABLE_BODY
        )
        part_tubelar.BaseShellExtrude(sketch=s, depth=z_len)
        s.unsetPrimaryObject()
        del task_model.sketches["__profile__"]
        # ===约束拉杆
        if self.rod_exist:
            s1 = task_model.ConstrainedSketch(name="__profile__", sheetSize=200.0)
            g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
            s1.setPrimaryObject(option=STANDALONE)
            for p1, p2 in self.rod_pattern["pattern_rod"]:
                p1, p2 = map(tuple, (p1, p2))
                s1.Line(point1=p1, point2=p2)

            part_rod_layer = task_model.Part(
                name="part_rod_layer", dimensionality=THREE_D, type=DEFORMABLE_BODY
            )
            part_rod_layer.BaseWire(sketch=s1)
            s1.unsetPrimaryObject()
            del task_model.sketches["__profile__"]
        # ===中心立杆
        if self.pole_exist:
            s = task_model.ConstrainedSketch(name="__profile__", sheetSize=200.0)
            g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
            s.setPrimaryObject(option=STANDALONE)
            s.Line(
                point1=(0, 0),
                point2=(z_len, 0),
            )
            s.HorizontalConstraint(entity=g[2], addUndoState=False)
            part_pole = task_model.Part(
                name="part_pole", dimensionality=THREE_D, type=DEFORMABLE_BODY
            )
            part_pole.BaseWire(sketch=s)
            s.unsetPrimaryObject()
            del task_model.sketches["__profile__"]

        # ======创建材料======
        # ===材料-钢管
        mtl_tubelar = task_model.Material(name="mtl_tubelar")
        mtl_tubelar.Elastic(
            table=(
                (
                    self.mtl_tubelar["elastic_modulus"],
                    self.mtl_tubelar["poissons_ratio"],
                ),
            )
        )
        mtl_tubelar.Plastic(table=self.mtl_tubelar["plastic_model"])
        # ===材料-混凝土
        mtl_concrete = task_model.Material(name="mtl_concrete")
        mtl_concrete.ConcreteDamagedPlasticity(table=(self.mtl_concrete["cdp_params"],))
        mtl_concrete.concreteDamagedPlasticity.ConcreteCompressionHardening(
            table=self.mtl_concrete["plastic_model"]
        )
        mtl_concrete.concreteDamagedPlasticity.ConcreteTensionStiffening(
            table=(self.mtl_concrete["gfi_table"],), type=GFI
        )
        mtl_concrete.Elastic(
            table=(
                (
                    self.mtl_concrete["elastic_modulus"],
                    self.mtl_concrete["poissons_ratio"],
                ),
            )
        )
        # ===材料-约束拉杆
        mtl_rod = task_model.Material(name="mtl_rod")
        mtl_rod.Elastic(
            table=((self.mtl_rod["elastic_modulus"], self.mtl_rod["poissons_ratio"]),)
        )
        mtl_rod.Plastic(table=self.mtl_rod["plastic_model"])
        # ===材料-中心立杆
        mtl_pole = task_model.Material(name="mtl_pole")
        mtl_pole.Elastic(
            table=((self.mtl_pole["elastic_modulus"], self.mtl_pole["poissons_ratio"]),)
        )
        mtl_pole.Plastic(table=self.mtl_pole["plastic_model"])

        # ======创建截面======
        # ===混凝土
        sec_concrete = task_model.HomogeneousSolidSection(
            name="sec_concrete", material="mtl_concrete", thickness=None
        )
        # ===钢管
        sec_tubelar = task_model.HomogeneousShellSection(
            name="sec_tubelar",
            preIntegrate=OFF,
            material="mtl_tubelar",
            thicknessType=UNIFORM,
            thickness=self.tubelar_thickness,
            thicknessField="",
            nodalThicknessField="",
            idealization=NO_IDEALIZATION,
            poissonDefinition=DEFAULT,
            thicknessModulus=None,
            temperature=GRADIENT,
            useDensity=OFF,
            integrationRule=SIMPSON,
            numIntPts=self.misc["tubelar_num_int_pts"],
        )
        # ===创建截面-拉杆
        sec_rod_layer = task_model.TrussSection(
            name="sec_rod_layer",
            material="mtl_rod",
            area=self.rod_pattern["area_rod"],
        )

        # ===创建截面-中心立杆
        sec_pole = task_model.TrussSection(
            name="sec_pole",
            material="mtl_pole",
            area=self.rod_pattern["area_pole"],
        )

        # ======指派截面======
        # ===混凝土
        region = regionToolset.Region(cells=part_concrete.cells)
        part_concrete.SectionAssignment(
            region=region,
            sectionName="sec_concrete",
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )
        # ===钢管
        region = regionToolset.Region(faces=part_tubelar.faces)
        part_tubelar.SectionAssignment(
            region=region,
            sectionName="sec_tubelar",
            offset=0.0,
            offsetType=BOTTOM_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )
        # ===拉杆
        if self.rod_exist:
            p = task_model.parts["part_rod_layer"]
            region = regionToolset.Region(edges=p.edges)
            p = task_model.parts["part_rod_layer"]
            p.SectionAssignment(
                region=region,
                sectionName="sec_rod_layer",
                offset=0.0,
                offsetType=MIDDLE_SURFACE,
                offsetField="",
                thicknessAssignment=FROM_SECTION,
            )
        # ===中心立杆
        if self.pole_exist:
            region = regionToolset.Region(edges=part_pole.edges)
            part_pole.SectionAssignment(
                region=region,
                sectionName="sec_pole",
                offset=0.0,
                offsetType=MIDDLE_SURFACE,
                offsetField="",
                thicknessAssignment=FROM_SECTION,
            )

        # ======装配=======
        a = task_model.rootAssembly
        # ===混凝土
        a.DatumCsysByDefault(CARTESIAN)
        ins_concrete = a.Instance(name="ins_concrete", part=part_concrete, dependent=ON)
        # ===钢管
        ins_tubelar = a.Instance(name="ins_tubelar", part=part_tubelar, dependent=ON)
        steel_union = tuple()
        # ===拉杆
        self.insset_rod_layer = tuple()
        if self.rod_exist:
            # ===创建实例
            self.insset_rod_layer += (
                a.Instance(name="ins_rod_layer_1", part=part_rod_layer, dependent=ON),
            )
            # ===平移实例
            a1 = task_model.rootAssembly
            a1.translate(
                instanceList=("ins_rod_layer_1",),
                vector=[0, 0, self.rod_pattern["layer_spacing"]],
            )
            # ===线性阵列实例(z方向)
            a1 = task_model.rootAssembly
            self.insset_rod_layer += a1.LinearInstancePattern(
                instanceList=("ins_rod_layer_1",),
                direction1=(0.0, 0.0, 1.0),
                direction2=(1.0, 0.0, 0.0),
                number1=self.rod_pattern["number_layers"],
                number2=1,
                spacing1=self.rod_pattern["layer_spacing"],
                spacing2=1.0,
            )
        # ===中心立杆
        self.insset_poles = tuple()
        if self.pole_exist:
            for i, pos in enumerate(self.rod_pattern["pattern_pole"]):
                ins_name = "pole-%d" % (i + 1)
                pos += [0]
                # ===创建实例-中心立杆
                a1 = task_model.rootAssembly
                a1.Instance(name=ins_name, part=part_pole, dependent=ON)
                # ===旋转实例-中心立杆
                a1 = task_model.rootAssembly
                a1.rotate(
                    instanceList=(ins_name,),
                    axisPoint=(0, 0, 0),
                    axisDirection=(0, 0 + 1, 0),
                    angle=-90.0,
                )
                # ===平移实例-中心立杆
                a1 = task_model.rootAssembly
                a1.translate(
                    instanceList=(ins_name,),
                    vector=tuple(pos),
                )
                self.insset_poles += (a1.instances[ins_name],)
        # ===Merge实例(钢管, 约束拉杆, 中心立杆)
        if self.union_exist:
            a1 = task_model.rootAssembly
            steel_union = (ins_tubelar,) + self.insset_poles + self.insset_rod_layer

            a1.InstanceFromBooleanMerge(
                name="merge_union",
                instances=steel_union,
                originalInstances=DELETE,
                mergeNodes=BOUNDARY_ONLY,
                nodeMergingTolerance=1e-06,
                domain=BOTH,
            )  # 这一步会同时在part里面创建merge_union, 在instances中创建merge_union-1

        # ======创建分析步======
        task_model.StaticStep(
            name="Step-1",
            previous="Initial",
            maxNumInc=self.static_step["max_num_inc"],
            initialInc=self.static_step["initial_inc"],
            minInc=self.static_step["min_inc"],
            nlgeom=self.static_step["nlgeom"],
            stabilizationMethod=self.static_step["stabilization_method"],
            continueDampingFactors=self.static_step["continue_damping_factors"],
            adaptiveDampingRatio=self.static_step["adaptive_damping_ratio"],
        )

        # ======相互作用======
        # ===设置参考点
        a = task_model.rootAssembly
        feature_1 = a.ReferencePoint(self.referpoint_bottom["position"])
        a = task_model.rootAssembly
        feature_2 = a.ReferencePoint(self.referpoint_top["position"])
        referpoint_bottom, referpoint_top = (
            a.referencePoints[feature_1.id],
            a.referencePoints[feature_2.id],
        )
        # ===设置刚体约束: 底面
        a = task_model.rootAssembly

        f1 = ins_concrete.faces
        faces1 = f1.findAt(
            coordinates=tuple(
                [(x_len / 2.0, y_len / 2.0, 0)],
            )
        )
        if self.union_exist:
            e2 = a.instances["merge_union-1"].edges
            edges2 = e2.findAt(coordinates=self.edge_point["bottom_all"])
        else:
            e2 = ins_tubelar.edges
            edges2 = e2.findAt(coordinates=self.edge_point["bottom_all"])

        if self.pole_exist:
            v1 = a.instances["merge_union-1"].vertices
            vert1 = v1.getByBoundingBox(
                0 + gap,
                0 + gap,
                0 - gap,
                x_len - gap,
                y_len - gap,
                0 + gap,
            )
            region4 = regionToolset.Region(edges=edges2, faces=faces1, vertices=vert1)
        else:
            region4 = regionToolset.Region(edges=edges2, faces=faces1)

        a = task_model.rootAssembly
        r1 = a.referencePoints

        refPoints1 = (referpoint_bottom,)
        region1 = regionToolset.Region(referencePoints=refPoints1)
        task_model.RigidBody(
            name="ct_bottom", refPointRegion=region1, tieRegion=region4
        )
        # ===设置刚体约束: 顶面
        a = task_model.rootAssembly
        f1 = ins_concrete.faces
        faces1 = f1.findAt(
            coordinates=tuple(
                [(x_len / 2.0, y_len / 2.0, z_len)],
            )
        )
        if self.union_exist:
            e2 = a.instances["merge_union-1"].edges
            edges2 = e2.findAt(coordinates=self.edge_point["top_all"])
        else:
            e2 = ins_tubelar.edges
            edges2 = e2.findAt(coordinates=self.edge_point["top_all"])

        if self.pole_exist:
            v1 = a.instances["merge_union-1"].vertices
            vert1 = v1.getByBoundingBox(
                0 + gap,
                0 + gap,
                z_len - gap,
                x_len - gap,
                y_len - gap,
                z_len + gap,
            )
            region4 = regionToolset.Region(edges=edges2, faces=faces1, vertices=vert1)
        else:
            region4 = regionToolset.Region(edges=edges2, faces=faces1)

        a = task_model.rootAssembly
        r1 = a.referencePoints
        refPoints1 = (referpoint_top,)
        region1 = regionToolset.Region(referencePoints=refPoints1)
        task_model.RigidBody(name="cp_top", refPointRegion=region1, tieRegion=region4)
        # ===设置边界条件: 底部
        a = task_model.rootAssembly
        r1 = a.referencePoints
        refPoints1 = (referpoint_bottom,)
        region = regionToolset.Region(referencePoints=refPoints1)
        displacement_bottom = self.referpoint_bottom["displacement"]
        task_model.DisplacementBC(
            name="bound_bottom",
            createStepName="Step-1",
            region=region,
            u1=displacement_bottom[0],
            u2=displacement_bottom[1],
            u3=displacement_bottom[2],
            ur1=displacement_bottom[3],
            ur2=displacement_bottom[4],
            ur3=displacement_bottom[5],
            amplitude=UNSET,
            fixed=OFF,
            distributionType=UNIFORM,
            fieldName="",
            localCsys=None,
        )
        # ===设置边界条件: 顶部
        a = task_model.rootAssembly
        r1 = a.referencePoints
        refPoints1 = (referpoint_top,)
        region = regionToolset.Region(referencePoints=refPoints1)
        displacement_top = self.referpoint_top["displacement"]
        task_model.DisplacementBC(
            name="bound_top",
            createStepName="Step-1",
            region=region,
            u1=displacement_top[0],
            u2=displacement_top[1],
            u3=displacement_top[2],
            ur1=displacement_top[3],
            ur2=displacement_top[4],
            ur3=displacement_top[5],
            amplitude=UNSET,
            fixed=OFF,
            distributionType=UNIFORM,
            fieldName="",
            localCsys=None,
        )
        # ===定义相互作用: 钢管-混凝土(硬接触和摩擦)相互作用
        inacttype_tubelar_concrete = task_model.ContactProperty(
            "inacttype_tubelar_concrete"
        )
        inacttype_tubelar_concrete.TangentialBehavior(
            formulation=PENALTY,
            directionality=ISOTROPIC,
            slipRateDependency=OFF,
            pressureDependency=OFF,
            temperatureDependency=OFF,
            dependencies=0,
            table=((self.misc["friction_factor_between_concrete_tubelar"],),),
            shearStressLimit=None,
            maximumElasticSlip=FRACTION,
            fraction=0.005,
            elasticSlipStiffness=None,
        )
        inacttype_tubelar_concrete.NormalBehavior(
            pressureOverclosure=HARD,
            allowSeparation=ON,
            constraintEnforcementMethod=DEFAULT,
        )
        # ===设置相互作用: 钢管-混凝土(硬接触和摩擦)相互作用
        a = task_model.rootAssembly
        if self.union_exist:
            s1 = a.instances["merge_union-1"].faces
            side2Faces1 = s1.getSequenceFromMask(
                mask=("[#f ]",),
            )
        else:
            s1 = ins_tubelar.faces
            side2Faces1 = s1.getSequenceFromMask(
                mask=("[#f ]",),
            )
        region1 = regionToolset.Region(side2Faces=side2Faces1)
        a = task_model.rootAssembly
        s1 = ins_concrete.faces
        side1Faces1 = s1.getSequenceFromMask(
            mask=("[#f ]",),
        )
        region2 = regionToolset.Region(side1Faces=side1Faces1)
        task_model.SurfaceToSurfaceContactStd(
            name="inact_tubelar_concrete",
            createStepName="Step-1",
            master=region1,
            slave=region2,
            sliding=FINITE,
            thickness=OFF,
            interactionProperty="inacttype_tubelar_concrete",
            adjustMethod=NONE,
            initialClearance=OMIT,
            datumAxis=None,
            clearanceRegion=None,
        )
        # ===设置内置区域约束: 钢筋, 混凝土
        if self.union_exist:
            a1 = task_model.rootAssembly
            e1 = a.instances["merge_union-1"].edges
            edges1 = e1.getByBoundingCylinder(
                center1=(x_len / 2.0, y_len / 2.0, 0),
                center2=(x_len / 2.0, y_len / 2.0, z_len),
                radius=math.sqrt(x_len * x_len + y_len * y_len) - gap,
            )
            region1 = regionToolset.Region(edges=edges1)
            task_model.EmbeddedRegion(
                name="inact_rod_concrete",
                embeddedRegion=region1,
                hostRegion=None,
                weightFactorTolerance=1e-06,
                absoluteTolerance=0.0,
                fractionalTolerance=0.05,
                toleranceMethod=BOTH,
            )

        # ======网格======
        # ===设置单元类型-桁架
        if self.union_exist:
            elemType1 = mesh.ElemType(elemCode=T3D2, elemLibrary=STANDARD)
            p = task_model.parts["merge_union"]
            e = p.edges
            edges = e.getByBoundingCylinder(
                center1=(x_len / 2.0, y_len / 2.0, 0),
                center2=(x_len / 2.0, y_len / 2.0, z_len),
                radius=math.sqrt(x_len * x_len + y_len * y_len) - gap,
            )
            pickedRegions = (edges,)
            p.setElementType(regions=pickedRegions, elemTypes=(elemType1,))
        # ===划分网格: 钢材
        if self.union_exist:
            p = task_model.parts["merge_union"]
        else:
            p = part_tubelar
        p.seedPart(
            size=max(x_len, y_len),
            deviationFactor=self.grid_minsize,
            minSizeFactor=self.grid_minsize,
        )
        e = p.edges
        for i, j in zip(["x_all", "y_all", "z_all"], [0, 1, 2]):
            pickedEdges = e.findAt(coordinates=self.edge_point[i])
            p.seedEdgeBySize(
                edges=pickedEdges,
                size=self.steel_seed[j],
                deviationFactor=self.grid_minsize,
                minSizeFactor=self.grid_minsize,
                constraint=FINER,
            )

        if self.union_exist:
            p = task_model.parts["merge_union"]
        else:
            p = part_tubelar
        p.generateMesh()
        # ===划分网格-concrete
        e = part_concrete.edges
        for i, j in zip(["x_all", "y_all", "z_all"], [0, 1, 2]):
            pickedEdges = e.findAt(coordinates=self.edge_point[i])
            part_concrete.seedEdgeBySize(
                edges=pickedEdges,
                size=self.concrete_seed[j],
                deviationFactor=self.grid_minsize,
                minSizeFactor=self.grid_minsize,
                constraint=FINER,
            )
        part_concrete.generateMesh()

        # ======历程输出======
        # ===创建集
        a = task_model.rootAssembly
        r1 = a.referencePoints
        refPoints1 = (referpoint_top,)
        a.Set(referencePoints=refPoints1, name="RP-TOP")
        # ===历程输出
        regionDef = task_model.rootAssembly.sets["RP-TOP"]
        task_model.HistoryOutputRequest(
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

        # ======生成作业======
        mdb.Job(
            name=self.taskname,
            model=self.taskname,
            description="",
            type=ANALYSIS,
            atTime=None,
            waitMinutes=0,
            waitHours=0,
            queue=None,
            memory=self.performance["memory"],
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
            numCpus=self.performance["num_cpus"],
            numDomains=self.performance["num_cpus"],
            numGPUs=self.performance["num_gpus"],
        )
        # ======保存======
        mdb.saveAs(pathName=self.caepath)

        # ======提交======
        if self.meta["submit"]:
            # ===作业开始
            st_time = time.time()
            try:
                mdb.jobs[self.jobname].submit()

                line = 5
                job_running = True
                stafile = self.workdir_statusfile
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
                odbpath = self.workdir_odb
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
                    "load": [-i[1] for i in xy0],
                    "load_k": [-i[1] / 1000.0 for i in xy0],
                    "displacement": xy1,
                    "epsilon": [-i[1] / float(z_len) for i in xy1],
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


taskparams = Utils.load_json("C:\\Users\\Tiki_\\Desktop\\tmp.json")["task_params"]
TaskExecutor(taskparams).run()
# control_json_path = os.path.join(TASK_FOLDER, "control.json")
# control_json = Utils.load_json(control_json_path)


# i = control_json["start_at"]

# while 1:
#     control_json = Utils.load_json(control_json_path)
#     flag = control_json["flag"]
#     if flag == 0:
#         pass
#     elif flag == 1:
#         time.sleep(60)
#         print("task suspended")
#         continue
#     elif flag == 2:
#         break

#     json_path = TASK_FOLDER + "\\%d.json" % i
#     if not os.path.isfile(json_path):
#         break
#     print("task:", json_path)

#     taskparams = Utils.load_json(json_path)["task_params"]
#     TaskExecutor(taskparams).run()

#     i += 1
