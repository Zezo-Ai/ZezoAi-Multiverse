#!/usr/bin/env python3.10

import os.path
from math import degrees
from typing import Optional, List, Tuple

import mujoco
import numpy

from .importer import Configuration, Importer

from ..factory import (WorldBuilder, BodyBuilder,
                       JointBuilder, JointType, JointProperty,
                       GeomBuilder, GeomType, GeomProperty,
                       MeshBuilder, MeshProperty,
                       MaterialBuilder)


def get_model_name(xml_file_path: str) -> str:
    with open(xml_file_path, "r") as xml_file:
        for line in xml_file:
            if "<mujoco model=" in line:
                return line.split('"')[1]
    return os.path.basename(xml_file_path).split(".")[0]


def get_body_name(mj_body) -> str:
    return mj_body.name if mj_body.name is not None else "Body_" + str(mj_body.id)


class MjcfImporter(Importer):
    _world_builder: WorldBuilder
    _mj_model: mujoco.MjModel

    def __init__(
            self,
            file_path: str,
            with_physics: bool,
            with_visual: bool,
            with_collision: bool
    ) -> None:
        try:
            self._mj_model = mujoco.MjModel.from_xml_path(filename=file_path)
        except ValueError as e:
            log_file = "MUJOCO_LOG.TXT"
            if os.path.exists(log_file):
                print(f"Removing log file {log_file}...")
                os.remove(log_file)
            raise FileNotFoundError(f"{e}")
        model_name = get_model_name(xml_file_path=file_path)
        super().__init__(file_path=file_path, config=Configuration(
            model_name=model_name,
            with_physics=with_physics,
            with_visual=with_visual,
            with_collision=with_collision
        ))

    def import_model(self, save_file_path: Optional[str] = None) -> str:
        self._world_builder = WorldBuilder(self.tmp_file_path)

        self._world_builder.add_body(body_name=self._config.model_name)

        for body_id in range(1, self._mj_model.nbody):
            mj_body = self._mj_model.body(body_id)
            body_builder = self.import_body(mj_body=mj_body)

            self.import_geoms(mj_body=mj_body, body_builder=body_builder)

            if self._config.with_physics:
                self.import_joints(mj_body=mj_body, body_builder=body_builder)

        self._world_builder.export()

        return self.tmp_file_path if save_file_path is None else self.save_tmp_model(file_path=save_file_path)

    def import_body(self, mj_body) -> BodyBuilder:
        body_name = mj_body.name if mj_body.name is not None else "Body_" + str(mj_body.id)

        if mj_body.id == 1:
            body_builder = self._world_builder.add_body(body_name=body_name,
                                                        parent_body_name=self._config.model_name,
                                                        body_id=mj_body.id)
        else:
            parent_mj_body = self._mj_model.body(mj_body.parentid)
            parent_body_name = get_body_name(parent_mj_body)
            if mj_body.jntnum[0] > 0 and self._config.with_physics:
                body_builder = self._world_builder.add_body(body_name=body_name,
                                                            parent_body_name=self._config.model_name,
                                                            body_id=mj_body.id)
                body_builder.enable_rigid_body()
            else:
                body_builder = self._world_builder.add_body(body_name=body_name,
                                                            parent_body_name=parent_body_name,
                                                            body_id=mj_body.id)

            relative_to_body_builder = self._world_builder.get_body_builder(body_name=parent_body_name)
            relative_to_xform = relative_to_body_builder.xform
            body_builder.set_transform(
                pos=mj_body.pos,
                quat=mj_body.quat,
                relative_to_xform=relative_to_xform,
            )

        return body_builder

    def import_joints(self, mj_body, body_builder: BodyBuilder) -> List[JointBuilder]:
        joint_builders = []
        for joint_id in range(mj_body.jntadr[0], mj_body.jntadr[0] + mj_body.jntnum[0]):
            joint_builder = self._import_joint(mj_body, body_builder, joint_id)
            if joint_builder is not None:
                joint_builders.append(joint_builder)
        return joint_builders

    def _import_joint(self, mj_body, body_builder: BodyBuilder, joint_id: int) -> Optional[JointBuilder]:
        mj_joint = self._mj_model.joint(joint_id)
        if mj_joint.type == mujoco.mjtJoint.mjJNT_FREE:
            return None

        joint_name = mj_joint.name if mj_joint.name is not None else "Joint_" + str(joint_id)
        joint_type = JointType.from_mujoco(jnt_type=mj_joint.type)

        parent_body_id = mj_body.parentid
        parent_body_name = get_body_name(self._mj_model.body(parent_body_id))
        parent_body_builder = self._world_builder.get_body_builder(body_name=parent_body_name)
        joint_property = JointProperty(
            joint_name=joint_name,
            joint_parent_prim=parent_body_builder.xform.GetPrim(),
            joint_child_prim=body_builder.xform.GetPrim(),
            joint_pos=mj_joint.pos,
            joint_axis=mj_joint.axis,
            joint_type=joint_type,
        )
        joint_builder = body_builder.add_joint(joint_property=joint_property)

        if mj_joint.type == mujoco.mjtJoint.mjJNT_HINGE:
            joint_builder.set_limit(lower=degrees(mj_joint.range[0]),
                                    upper=degrees(mj_joint.range[1]))
        elif mj_joint.type == mujoco.mjtJoint.mjJNT_SLIDE:
            joint_builder.set_limit(lower=mj_joint.range[0],
                                    upper=mj_joint.range[1])

        return joint_builder

    def import_geoms(self, mj_body, body_builder: BodyBuilder) -> List[GeomBuilder]:
        geom_builders = []
        for geom_id in range(mj_body.geomadr[0], mj_body.geomadr[0] + mj_body.geomnum[0]):
            geom_builder = self._import_geom(body_builder, geom_id)
            if geom_builder is not None:
                geom_builders.append(geom_builder)
        return geom_builders

    def _import_geom(self, body_builder: BodyBuilder, geom_id: int) -> Optional[GeomBuilder]:
        mj_geom = self._mj_model.geom(geom_id)
        geom_is_visible = (mj_geom.contype == 0) and (mj_geom.conaffinity == 0)
        geom_is_collidable = (mj_geom.contype != 0) or (mj_geom.conaffinity != 0)
        geom_builder = None
        if geom_is_visible and self._config.with_visual or geom_is_collidable and self._config.with_collision:
            geom_name = mj_geom.name if mj_geom.name != "" else "Geom_" + str(geom_id)
            geom_rgba = mj_geom.rgba

            if mj_geom.type == mujoco.mjtGeom.mjGEOM_PLANE:
                geom_property = GeomProperty(geom_name=geom_name,
                                             geom_type=GeomType.PLANE,
                                             is_visible=geom_is_visible,
                                             is_collidable=geom_is_collidable,
                                             rgba=geom_rgba)
                geom_builder = body_builder.add_geom(geom_property=geom_property)
                geom_builder.build()
                geom_builder.set_transform(pos=mj_geom.pos, quat=mj_geom.quat, scale=numpy.array([50, 50, 1]))
            elif mj_geom.type == mujoco.mjtGeom.mjGEOM_BOX:
                geom_property = GeomProperty(geom_name=geom_name,
                                             geom_type=GeomType.CUBE,
                                             is_visible=geom_is_visible,
                                             is_collidable=geom_is_collidable,
                                             rgba=geom_rgba)
                geom_builder = body_builder.add_geom(geom_property=geom_property)
                geom_builder.build()
                geom_builder.set_transform(pos=mj_geom.pos, quat=mj_geom.quat, scale=mj_geom.size)
            elif mj_geom.type in [mujoco.mjtGeom.mjGEOM_SPHERE, mujoco.mjtGeom.mjGEOM_ELLIPSOID]:
                # TODO: Fix ellipsoid
                geom_property = GeomProperty(geom_name=geom_name,
                                             geom_type=GeomType.SPHERE,
                                             is_visible=geom_is_visible,
                                             is_collidable=geom_is_collidable,
                                             rgba=geom_rgba)
                geom_builder = body_builder.add_geom(geom_property=geom_property)
                geom_builder.build()
                geom_builder.set_transform(pos=mj_geom.pos, quat=mj_geom.quat)
                geom_builder.set_attribute(radius=mj_geom.size[0])
            elif mj_geom.type in [mujoco.mjtGeom.mjGEOM_CYLINDER, mujoco.mjtGeom.mjGEOM_CAPSULE]:
                # TODO: Fix capsule
                geom_property = GeomProperty(geom_name=geom_name,
                                             geom_type=GeomType.CYLINDER,
                                             is_visible=geom_is_visible,
                                             is_collidable=geom_is_collidable,
                                             rgba=geom_rgba)
                geom_builder = body_builder.add_geom(geom_property=geom_property)
                geom_builder.build()
                geom_builder.set_transform(pos=mj_geom.pos, quat=mj_geom.quat)
                geom_builder.set_attribute(radius=mj_geom.size[0], height=mj_geom.size[1] * 2)
            elif mj_geom.type == mujoco.mjtGeom.mjGEOM_MESH:
                geom_property = GeomProperty(geom_name=geom_name,
                                             geom_type=GeomType.MESH,
                                             is_visible=geom_is_visible,
                                             is_collidable=geom_is_collidable,
                                             rgba=geom_rgba)
                geom_builder = body_builder.add_geom(geom_property=geom_property)
                mesh_id = mj_geom.dataid[0]
                mesh_name = self._mj_model.mesh(mesh_id).name
                points, normals, face_vertex_counts, face_vertex_indices = self.get_mesh_data(mesh_id=mesh_id)
                tmp_mesh_file_path = os.path.join(self._tmp_mesh_dir, "usd", f"{mesh_name}.usda")
                mesh_builder = MeshBuilder(mesh_file_path=tmp_mesh_file_path)
                mesh_property = MeshProperty(points=points,
                                             normals=normals,
                                             face_vertex_counts=face_vertex_counts,
                                             face_vertex_indices=face_vertex_indices)
                mesh_builder.create_mesh(mesh_name=mesh_name, mesh_property=mesh_property)

                mat_id = mj_geom.matid
                if mat_id != -1:
                    diffuse_color, emissive_color, specular_color = self.get_material_data(mat_id=mat_id)
                    material_builder = MaterialBuilder(file_path=tmp_mesh_file_path)
                    material_builder.apply_material(diffuse_color=diffuse_color,
                                                    emissive_color=emissive_color,
                                                    specular_color=specular_color)

                geom_builder.add_mesh(mesh_file_path=tmp_mesh_file_path)
                geom_builder.build()
                geom_builder.set_transform(pos=mj_geom.pos, quat=mj_geom.quat)
            else:
                raise NotImplementedError(f"Geom type {mj_geom.type} not supported.")

        # if self.config.with_physics:
        #     if geom_is_collidable:
        #         geom_builder.enable_rigid_body()

        return geom_builder

    def get_mesh_data(self, mesh_id: int) -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray]:
        vert_adr = self._mj_model.mesh_vertadr[mesh_id]
        vert_num = self._mj_model.mesh_vertnum[mesh_id]

        face_adr = self._mj_model.mesh_faceadr[mesh_id]
        face_num = self._mj_model.mesh_facenum[mesh_id]
        points = numpy.empty(shape=[vert_num, 3], dtype=float)

        normals = numpy.empty(shape=[self._mj_model.mesh_facenum[mesh_id], 3], dtype=float)

        face_vertex_counts = numpy.empty(shape=self._mj_model.mesh_facenum[mesh_id], dtype=float)
        face_vertex_counts.fill(3)

        face_vertex_indices = numpy.empty(shape=self._mj_model.mesh_facenum[mesh_id] * 3, dtype=float)

        for i in range(vert_num):
            vert_id = vert_adr + i
            points[i] = self._mj_model.mesh_vert[vert_id]

        normal_adr = self._mj_model.mesh_normaladr[mesh_id]
        for i in range(face_num):
            face_id = face_adr + i
            face_normals = self._mj_model.mesh_normal[normal_adr + self._mj_model.mesh_facenormal[face_id]]

            p1 = face_normals[0]
            p2 = face_normals[1]
            p3 = face_normals[2]

            v1 = p2 - p1
            v2 = p3 - p1
            normal = numpy.cross(v1, v2)
            norm = numpy.linalg.norm(normal)
            if norm != 0:
                normal = normal / norm
            normals[i] = normal

            face_vertex_indices[3 * i] = self._mj_model.mesh_face[face_id][0]
            face_vertex_indices[3 * i + 1] = self._mj_model.mesh_face[face_id][1]
            face_vertex_indices[3 * i + 2] = self._mj_model.mesh_face[face_id][2]

        return points, normals, face_vertex_counts, face_vertex_indices

    def get_material_data(self, mat_id: int) -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
        """
        Get material data from the given material id.
        :param mat_id: Material id.
        :return: diffuse_color (RGB), emissive_color (RGB), specular_color (RGB)
        """
        if mat_id == -1:
            raise ValueError(f"Material {mat_id} not found.")
        mat_rgba = self._mj_model.mat_rgba[mat_id]
        mat_rgb = mat_rgba[0][:3]
        diffuse_color = numpy.array([float(x) for x in mat_rgb])

        mat_emission = self._mj_model.mat_emission[mat_id]
        emissive_color = numpy.array([float(x * mat_emission) for x in mat_rgb])

        mat_specular = self._mj_model.mat_specular[mat_id]
        specular_color = numpy.array([float(mat_specular) for _ in range(3)])

        return diffuse_color, emissive_color, specular_color
