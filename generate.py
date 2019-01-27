import os
import sys
import bpy
import numpy as np
import random
import bisect
from collections import Counter

blend_dir = os.path.basename(bpy.data.filepath)
if blend_dir not in sys.path:
       sys.path.append(blend_dir)
sys.path.append("./")

import argparse
import nurbs


class Generator():
    def __init__(self):
        self.scene = bpy.context.scene
        self.render = self.scene.render
        self.material_count = 0

    def cleanup_scene(self):
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_by_type(type='CAMERA', extend=True)
        bpy.ops.object.select_by_type(type='LAMP', extend=True)
        bpy.ops.object.select_all(action='INVERT')
        bpy.ops.object.delete()

    def setup_lamp(self, shadowMethod="NOSHADOW"):
        self.lamp = bpy.data.lamps['Lamp']
        self.lamp.type = "SUN"
        self.lamp.color = (1.0, 1.0, 1.0)
        self.lamp.energy = 1.0
        self.lamp.shadow_method = shadowMethod

    def setup_camera(self, loc=(0,-17.5,30), angle=(30,0,0)):
        self.camera = self.scene.camera
        # Set camera rotation in euler angles
        self.camera.rotation_mode = 'XYZ'
        self.camera.rotation_euler = list(np.multiply(angle, (np.pi/180.0)))

        # Set camera translation
        self.camera.location = loc

    def new_random_material(self):
        material_name = "Material_" + str(self.material_count)
        bpy.data.materials.new(name = material_name)
        material = bpy.data.materials[material_name]
        material.diffuse_color = np.random.random((3,))
        material.specular_intensity = 0
        self.material_count += 1
        return material

    def get_random_points(self, count, dim):
        #origin = np.array([0,0,0])
        points = [np.append(2*(np.random.random((dim,)) - 0.5), max(0, 3-dim)*[0]) * i for i in range(count)]
        #return np.concatenate([[origin], points])
        return points

    def get_random_primitive_factory(self):
        return random.choice([bpy.ops.mesh.primitive_cube_add, bpy.ops.mesh.primitive_cylinder_add, bpy.ops.mesh.primitive_uv_sphere_add])

    def get_path_center(self, curve_data, nu):
        resolution = (curve_data.render_resolution_u if curve_data.render_resolution_u else curve_data.resolution_u)
        coord_array = nurbs.nurb_make_curve(nu, resolution, 3)
        verts = [coord_array[i: i + 3] for i in range(0, len(coord_array), 3)]
        return verts[len(verts) // 2]

    def add_path(self):
        curve_data = bpy.data.curves.new("curve_data", type = "CURVE")
        curve_data.dimensions = '3D'

        num_points = 4
        curve_scale = 10
        coords = np.multiply(curve_scale, self.get_random_points(num_points, 2))
        nu = curve_data.splines.new('NURBS')
        nu.points.add(len(coords) - 1)
        for i, coord in enumerate(coords):
            x, y, z = coord
            nu.points[i].co = (x, y, z, 1)

        path = bpy.data.objects.new("mover_path", curve_data)
        curve_data.bevel_depth = 0.01

        self.scene.objects.link(path)
        self.scene.objects.active = path
        path.hide_render = True

        #Get occlusion point
        occPoint = self.get_path_center(curve_data, nu)

        return path, occPoint

    def get_vec_to_camera(self, point):
        vec = np.subtract(list(self.camera.location), point)
        return vec/np.linalg.norm(vec)

    def add_occlusion(self, occPoint, occDist=3):
        occPoint += occDist * self.get_vec_to_camera(occPoint)
        factory = self.get_random_primitive_factory()
        factory(location=tuple(occPoint))
        self.occlusion = bpy.context.scene.objects.active
        self.occlusion.scale = (2, 2, 1)
        material = self.new_random_material()
        if self.occlusion.data.materials:
            self.occlusion.data.materials[0] = material
        else:
            self.occlusion.data.materials.append(material)



    def add_mover(self, loc=(0,0,0)):
        factory = self.get_random_primitive_factory()
        factory(location=tuple(loc))
        self.mover = bpy.context.scene.objects.active

        material = self.new_random_material()
        if self.mover.data.materials:
            self.mover.data.materials[0] = material
        else:
            self.mover.data.materials.append(material)

        #Set ambient shading for mover to reduce hazing caused by background plane color
        material.ambient = 0

        self.mover.active_material = material
        path, occPoint = self.add_path()
        bpy.ops.object.select_all(action='DESELECT')
        self.scene.objects.active = self.mover

        bpy.ops.object.constraint_add(type = 'FOLLOW_PATH')
        self.mover.constraints["Follow Path"].target = path
        self.mover.constraints["Follow Path"].forward_axis = 'FORWARD_X'
        self.mover.constraints["Follow Path"].use_curve_follow = True

        override={'constraint':self.mover.constraints["Follow Path"]}
        bpy.ops.constraint.followpath_path_animate(override, constraint='Follow Path')

        #Add occlusion mover
        self.add_occlusion(occPoint)



    def add_plane(self, loc=(0,0,-2), scale=(20, 20, 1)):
        bpy.ops.mesh.primitive_plane_add(location=loc)
        self.plane = bpy.context.scene.objects.active
        material = self.new_random_material()
        if self.plane.data.materials:
            self.plane.data.materials[0] = material
        else:
            self.plane.data.materials.append(material)

        self.plane.active_material = material
        self.plane.scale = scale

    def setup_scene(self):
        self.setup_lamp()
        self.setup_camera()
        self.add_mover()
        self.add_plane()

        #Shorten to 100 frames, default length for animation
        self.scene.frame_end=100

    def setup_render_node_tree(self, out_dir):
        tree = self.scene.node_tree
        nodes = tree.nodes
        links = tree.links
        for node in nodes:
            nodes.remove(node)
        for link in links:
            nodes.remove(link)

        rlayers_node = nodes.new(type = "CompositorNodeRLayers")

        image_node = nodes.new(type = "CompositorNodeOutputFile")
        image_node.base_path = os.path.join(out_dir, "images/")
        links.new(rlayers_node.outputs["Image"], image_node.inputs["Image"])

        '''
        color_node = nodes.new(type = "CompositorNodeOutputFile")
        color_node.base_path = os.path.join(out_dir, "reflectance/")
        links.new(rlayers_node.outputs["Color"], color_node.inputs["Image"])
        '''

    def render_scene(self, out_dir):
        #self.render.engine = "CYCLES"
        #self.scene.use_nodes = True
        #self.render.layers["RenderLayer"].use_pass_color = True
        #self.setup_render_node_tree(out_dir)
        bpy.data.scenes['Scene'].render.filepath = out_dir
        bpy.ops.render.render(animation = True)
        bpy.ops.image.save_dirty()

    def generate(self, out_dir):
        self.setup_scene()
        self.render_scene(out_dir)

def main():
    argv = sys.argv
    try:
        index = argv.index("--") + 1
    except ValueError:
        index = len(argv)
    argv = argv[index:]

    ap = argparse.ArgumentParser(description = "Script to generate IID dataset")
    ap.add_argument("--out-dir", type = str, default = "./output",
                    help = "Output directory for saving the video clips")
    ap.add_argument("--num-videos", type = int, default = 500,
                    help = "Number of videos to generate")
    ap.add_argument("--resume-from", type = int, default = 0,
                    help = "Resume creating videos from the given number")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir)

    for itr in range(args.resume_from, args.num_videos):
        print("=> Processing iteration {}".format(itr))
        out_dir = os.path.join(args.out_dir, str(itr) + "/")
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        scene = Generator()
        scene.cleanup_scene()
        scene.generate(out_dir = out_dir)

if __name__=="__main__":
    main()
