#!/usr/bin/env python3.10

import importlib.util
import os, shutil
import random, string
from pxr import Usd, UsdGeom, Sdf, Gf, UsdPhysics
from enum import Enum

multiverse_parser_path = os.path.dirname(
    importlib.util.find_spec("multiverse_parser").origin
)

mesh_dict = {}
geom_dict = {}
body_dict = {}
joint_dict = {}

TMP = "tmp"
TMP_DIR = "tmp/usd"

xform_cache = UsdGeom.XformCache()


def copy_and_overwrite(source_folder: str, destination_folder: str) -> None:
    os.makedirs(name=destination_folder, exist_ok=True)

    # Iterate through all files and folders in the source folder
    for item in os.listdir(source_folder):
        source_item = os.path.join(source_folder, item)
        destination_item = os.path.join(destination_folder, item)

        # If item is a folder, call the function recursively
        if os.path.isdir(source_item):
            if os.path.exists(destination_item):
                shutil.rmtree(destination_item)
            shutil.copytree(source_item, destination_item)
        # If item is a file, simply copy it
        else:
            shutil.copy2(source_item, destination_item)


class JointType(Enum):
    FIXED = 0
    REVOLUTE = 1
    CONTINUOUS = 2
    PRISMATIC = 3
    SPHERICAL = 4


class GeomType(Enum):
    PLANE = 0
    CUBE = 1
    SPHERE = 2
    CYLINDER = 3
    MESH = 4


class JointBuilder:
    def __init__(
        self,
        stage: Usd.Stage,
        name: str,
        parent_name: str,
        child_name: str,
        joint_type: JointType,
        pos: tuple = (0.0, 0.0, 0.0),
        axis: str = "Z",
    ) -> None:
        joint_dict[name] = self
        if body_dict.get(parent_name) is None or body_dict.get(child_name) is None:
            return
        self.stage = stage
        self.parent_prim = body_dict[parent_name].prim
        self.child_prim = body_dict[child_name].prim
        self.path = self.parent_prim.GetPath().AppendPath(name)
        self.type = joint_type
        self.set_prim()
        self.pos = Gf.Vec3f(pos)
        self.set_axis(axis)

        self.prim.CreateCollisionEnabledAttr(False)

        self.prim.GetBody0Rel().SetTargets([self.parent_prim.GetPath()])
        self.prim.GetBody1Rel().SetTargets([self.child_prim.GetPath()])

        body1_rot = Gf.Quatf(body_dict[parent_name].quat)

        body2_pos = Gf.Vec3f(body_dict[child_name].pos)
        body2_rot = Gf.Quatf(body_dict[child_name].quat)

        self.prim.CreateLocalPos0Attr(body2_pos + body1_rot.Transform(self.pos))
        self.prim.CreateLocalPos1Attr(Gf.Vec3f())

        self.prim.CreateLocalRot0Attr(body2_rot * self.quat)
        self.prim.CreateLocalRot1Attr(self.quat)

    def set_prim(self) -> None:
        if self.type == JointType.FIXED:
            self.prim = UsdPhysics.FixedJoint.Define(self.stage, self.path)
        elif self.type == JointType.REVOLUTE or self.type == JointType.CONTINUOUS:
            self.prim = UsdPhysics.RevoluteJoint.Define(self.stage, self.path)
        elif self.type == JointType.PRISMATIC:
            self.prim = UsdPhysics.PrismaticJoint.Define(self.stage, self.path)
        elif self.type == JointType.SPHERICAL:
            self.prim = UsdPhysics.SphericalJoint.Define(self.stage, self.path)

    def set_limit(self, lower: float = None, upper: float = None) -> None:
        if self.type == JointType.REVOLUTE or self.type == JointType.PRISMATIC:
            if lower is not None:
                self.prim.CreateLowerLimitAttr(lower)
            if upper is not None:
                self.prim.CreateUpperLimitAttr(upper)
        else:
            print(f"Joint type {str(self.type)} does not have limits.")

    def set_axis(self, axis: str) -> None:
        self.prim.CreateAxisAttr("Z")
        if axis == "X":
            self.quat = Gf.Quatf(0.7071068, 0, 0.7071068, 0)
        elif axis == "Y":
            self.quat = Gf.Quatf(0.7071068, -0.7071068, 0, 0)
        elif axis == "Z":
            self.quat = Gf.Quatf(1, 0, 0, 0)
        elif axis == "-X":
            self.quat = Gf.Quatf(0.7071068, 0, -0.7071068, 0)
        elif axis == "-Y":
            self.quat = Gf.Quatf(0.7071068, 0.7071068, 0, 0)
        elif axis == "-Z":
            self.quat = Gf.Quatf(0, 0, 1, 0)


class MeshBuilder:
    def __init__(self, name: str, usd_file_path: str) -> None:
        mesh_dict[name] = self
        self.stage = Usd.Stage.CreateNew(usd_file_path)
        UsdGeom.SetStageUpAxis(self.stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(self.stage, UsdGeom.LinearUnits.meters)
        self.prim = UsdGeom.Mesh.Define(self.stage, "/Mesh_" + name)
        self.stage.SetDefaultPrim(self.prim.GetPrim())

    def build(self, points, normals, face_vertex_counts, face_vertex_indices):
        self.prim.CreatePointsAttr(points)
        self.prim.CreateNormalsAttr(normals)
        self.prim.CreateFaceVertexCountsAttr(face_vertex_counts)
        self.prim.CreateFaceVertexIndicesAttr(face_vertex_indices)

    def save(self):
        self.stage.Save()


class GeomBuilder:
    def __init__(
        self, stage: Usd.Stage, name: str, body_path: Sdf.Path, geom_type: GeomType
    ) -> None:
        geom_dict[name] = self
        self.stage = stage
        self.usd_file_dir = os.path.dirname(self.stage.GetRootLayer().realPath)
        self.path = body_path.AppendPath(name)
        self.type = geom_type
        self.set_prim()
        self.pos = Gf.Vec3d(0.0, 0.0, 0.0)
        self.quat = Gf.Quatd(1.0, 0.0, 0.0, 0.0)
        self.scale = Gf.Vec3d(1.0, 1.0, 1.0)

    def set_prim(self) -> None:
        if self.type == GeomType.PLANE:
            self.prim = UsdGeom.Mesh.Define(self.stage, self.path)
            self.prim.CreatePointsAttr(
                [(-0.5, -0.5, 0), (0.5, -0.5, 0), (-0.5, 0.5, 0), (0.5, 0.5, 0)]
            )
            self.prim.CreateNormalsAttr([(0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1)])
            self.prim.CreateFaceVertexCountsAttr([4])
            self.prim.CreateFaceVertexIndicesAttr([0, 1, 3, 2])
        elif self.type == GeomType.CUBE:
            self.prim = UsdGeom.Cube.Define(self.stage, self.path)
        elif self.type == GeomType.SPHERE:
            self.prim = UsdGeom.Sphere.Define(self.stage, self.path)
        elif self.type == GeomType.CYLINDER:
            self.prim = UsdGeom.Cylinder.Define(self.stage, self.path)
        elif self.type == GeomType.MESH:
            self.prim = UsdGeom.Mesh.Define(self.stage, self.path)

    def set_transform(
        self,
        pos: tuple = (0.0, 0.0, 0.0),
        quat: tuple = (1.0, 0.0, 0.0, 0.0),
        scale: tuple = (1.0, 1.0, 1.0),
    ):
        self.pos = Gf.Vec3d(pos)
        self.quat = Gf.Quatd(quat[0], Gf.Vec3d(quat[1], quat[2], quat[3]))
        self.scale = Gf.Vec3d(scale)

        mat = Gf.Matrix4d()
        mat.SetTranslateOnly(self.pos)
        mat.SetRotateOnly(self.quat)
        mat_scale = Gf.Matrix4d()
        mat_scale.SetScale(self.scale)
        mat = mat_scale * mat
        self.prim.AddTransformOp().Set(mat)

    def set_attribute(self, prefix: str = None, **kwargs) -> None:
        for key, value in kwargs.items():
            attr = prefix + ":" + key if prefix is not None else key
            if self.prim.GetPrim().HasAttribute(attr):
                self.prim.GetPrim().GetAttribute(attr).Set(value)

    def compute_extent(self) -> None:
        if self.type == GeomType.PLANE:
            self.prim.CreateExtentAttr([(-0.5, -0.5, 0), (0.5, 0.5, 0)])
        elif self.type == GeomType.CUBE:
            self.prim.CreateExtentAttr(((-1, -1, -1), (1, 1, 1)))
        elif self.type == GeomType.SPHERE:
            radius = self.prim.GetRadiusAttr().Get()
            self.prim.CreateExtentAttr(
                ((-radius, -radius, -radius), (radius, radius, radius))
            )
        elif self.type == GeomType.CYLINDER:
            radius = self.prim.GetRadiusAttr().Get()
            height = self.prim.GetHeightAttr().Get()
            self.prim.CreateExtentAttr(
                ((-radius, -radius, -height / 2), (radius, radius, height / 2))
            )
        elif self.type == GeomType.MESH:
            self.prim.CreateExtentAttr(((-1, -1, -1), (1, 1, 1)))

    def add_mesh(self, mesh_name: str) -> MeshBuilder:
        mesh_dir = os.path.join(TMP_DIR, mesh_name + ".usda")
        mesh_ref = "./" + mesh_dir
        if mesh_name in mesh_dict:
            mesh = mesh_dict[mesh_name]
        else:
            mesh = MeshBuilder(
                mesh_name, os.path.join(self.usd_file_dir, TMP_DIR, mesh_name + ".usda")
            )
        self.prim.GetPrim().GetReferences().AddReference(mesh_ref)
        return mesh

    def enable_collision(self) -> None:
        physics_collision_api = UsdPhysics.CollisionAPI(self.prim)
        physics_collision_api.CreateCollisionEnabledAttr(True)
        physics_collision_api.Apply(self.prim.GetPrim())

        if self.type == GeomType.MESH:
            physics_mesh_collision_api = UsdPhysics.MeshCollisionAPI(self.prim)
            physics_mesh_collision_api.CreateApproximationAttr("convexHull")
            physics_mesh_collision_api.Apply(self.prim.GetPrim())


class BodyBuilder:
    def __init__(self, stage: Usd.Stage, name: str, parent_name: str = None) -> None:
        body_dict[name] = self
        if parent_name is not None:
            parent_prim = body_dict.get(parent_name).prim
            if parent_prim is not None:
                self.path = parent_prim.GetPath().AppendPath(name)
            else:
                print(f"Parent prim with name {parent_name} not found.")
                return
        else:
            self.path = Sdf.Path("/").AppendPath(name)
        self.stage = stage
        self.usd_file_dir = os.path.dirname(self.stage.GetRootLayer().realPath)
        self.prim = UsdGeom.Xform.Define(self.stage, self.path)
        self.pos = Gf.Vec3d(0.0, 0.0, 0.0)
        self.quat = Gf.Quatd(1.0, 0.0, 0.0, 0.0)
        self.scale = Gf.Vec3d(1.0, 1.0, 1.0)
        self.geoms = set()
        self.joints = set()

    def set_transform(
        self,
        pos: tuple = (0.0, 0.0, 0.0),
        quat: tuple = (1.0, 0.0, 0.0, 0.0),
        scale: tuple = (1.0, 1.0, 1.0),
        relative_to: str = None,
    ):
        self.pos = Gf.Vec3d(pos)
        self.quat = Gf.Quatd(quat[0], Gf.Vec3d(quat[1], quat[2], quat[3]))
        self.scale = Gf.Vec3d(scale)

        mat = Gf.Matrix4d()
        mat.SetTranslateOnly(self.pos)
        mat.SetRotateOnly(self.quat)
        mat_scale = Gf.Matrix4d()
        mat_scale.SetScale(Gf.Vec3d(self.scale))
        mat = mat_scale * mat

        if relative_to is not None:
            relative_prim = body_dict[relative_to].prim.GetPrim()
            if relative_prim:
                parent_prim = self.prim.GetPrim().GetParent()
                if parent_prim and parent_prim != relative_prim:
                    parent_to_relative_mat, _ = xform_cache.ComputeRelativeTransform(
                        relative_prim, parent_prim
                    )
                    mat = mat * parent_to_relative_mat
            else:
                print(f"Prim at path {relative_to} not found.")

        self.prim.AddTransformOp().Set(mat)

    def add_geom(self, geom_name: str, geom_type: GeomType) -> GeomBuilder:
        if geom_name in geom_dict:
            print(f"Geom {geom_name} already exists.")
            geom = geom_dict[geom_name]
        else:
            geom = GeomBuilder(self.stage, geom_name, self.path, geom_type)
            self.geoms.add(geom)
        return geom

    def add_joint(
        self,
        joint_name: str,
        parent_name: str,
        child_name: str,
        joint_type: JointType,
        joint_pos: tuple = (0.0, 0.0, 0.0),
        joint_axis: str = "Z",
    ) -> JointBuilder:
        if joint_name in joint_dict:
            print(f"Joint {joint_name} already exists.")
            joint = joint_dict[joint_name]
        else:
            joint = JointBuilder(
                self.stage,
                joint_name,
                parent_name,
                child_name,
                joint_type,
                joint_pos,
                joint_axis,
            )
            self.joints.add(joint)
        return joint

    def enable_collision(self) -> None:
        physics_rigid_body_api = UsdPhysics.RigidBodyAPI(self.prim)
        physics_rigid_body_api.CreateRigidBodyEnabledAttr(True)
        physics_rigid_body_api.Apply(self.prim.GetPrim())

        for geom in self.geoms:
            geom.enable_collision()

    def set_inertial(
        self,
        mass: float = 1e-9,
        com: tuple = (0.0, 0.0, 0.0),
        diagonal_inertia: tuple = (0.0, 0.0, 0.0),
    ) -> None:
        physics_mass_api = UsdPhysics.MassAPI(self.prim)
        physics_mass_api.CreateMassAttr(mass)
        physics_mass_api.CreateCenterOfMassAttr(Gf.Vec3f(com))
        physics_mass_api.CreateDiagonalInertiaAttr(Gf.Vec3f(diagonal_inertia))
        physics_mass_api.Apply(self.prim.GetPrim())


class WorldBuilder:
    def __init__(self) -> None:
        random_string = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        self.usd_file_path = os.path.join(
            multiverse_parser_path, ".cache", random_string, TMP + ".usda"
        )
        print(f"Create {self.usd_file_path}")
        os.makedirs(os.path.dirname(self.usd_file_path))
        self.stage = Usd.Stage.CreateNew(self.usd_file_path)
        UsdGeom.SetStageUpAxis(self.stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(self.stage, UsdGeom.LinearUnits.meters)

    def add_body(self, body_name: str, parent_body_name: str = None) -> BodyBuilder:
        if body_name in body_dict:
            print(f"Body {body_name} already exists.")
            return body_dict[body_name]

        if parent_body_name is None:
            self.root_body = BodyBuilder(self.stage, body_name)
            self.stage.SetDefaultPrim(self.root_body.prim.GetPrim())
            return self.root_body
        else:
            return BodyBuilder(self.stage, body_name, parent_body_name)

    def export(self, usd_file_path: str = None) -> None:
        self.stage.Save()

        if usd_file_path is not None:
            usd_file_dir = os.path.dirname(usd_file_path)
            usd_file_name = os.path.splitext(os.path.basename(usd_file_path))[0]

            copy_and_overwrite(os.path.dirname(self.usd_file_path), usd_file_dir)

            tmp_usd_file_path = os.path.join(
                usd_file_dir, os.path.basename(self.usd_file_path)
            )
            os.rename(tmp_usd_file_path, usd_file_path)

            tmp_mesh_dir = os.path.join(usd_file_dir, TMP)
            new_mesh_dir = os.path.join(usd_file_dir, usd_file_name)
            if os.path.exists(new_mesh_dir):
                shutil.rmtree(new_mesh_dir)
            os.rename(tmp_mesh_dir, new_mesh_dir)

            with open(usd_file_path, "r", encoding="utf-8") as file:
                file_contents = file.read()

            tmp_path = "prepend references = @./" + TMP + "/usd/"
            new_path = "prepend references = @./" + usd_file_name + "/usd/"
            file_contents = file_contents.replace(tmp_path, new_path)

            with open(usd_file_path, "w", encoding="utf-8") as file:
                file.write(file_contents)

    def clean_up(self) -> None:
        print(f"Remove {os.path.dirname(self.usd_file_path)}")
        shutil.rmtree(os.path.dirname(self.usd_file_path))
        body_dict.clear()
        geom_dict.clear()
        mesh_dict.clear()
        xform_cache.Clear()
