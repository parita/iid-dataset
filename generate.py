import os
import sys
import bpy
import time
import numpy as np

blend_dir = os.path.basename(bpy.data.filepath)
if blend_dir not in sys.path:
       sys.path.append(blend_dir)
sys.path.append("./")

import argparse

class Generator():
    def __init__(self, use_gpu):
        self.scene = bpy.context.scene
        self.render = self.scene.render
        self.material_count = 0
        self.use_gpu = use_gpu

    def cleanup_scene(self):
        for material in bpy.data.materials:
            bpy.data.materials.remove(material)
        for curve in bpy.data.curves:
            bpy.data.curves.remove(curve)

    def setup_lamp(self):
        self.lamp = bpy.data.lamps['Lamp']
        self.lamp.type = "SUN"
        #self.lamp.color = (0.5172079205513, 0.9855771064758301, 1.0) # set to bluish light
        self.lamp.color = (1.0, 1.0, 1.0)
        #self.lamp.color = np.random.random((3,))
        self.lamp.energy = 1.0
        #self.lamp.distance = 10.0

    def add_material(self):
        material_name = "Material_" + str(self.material_count)
        bpy.data.materials.new(name = material_name)
        material = bpy.data.materials[material_name]
        material.diffuse_color = np.random.random((3,))
        self.material_count += 1
        return material

    def add_path(self):
        curve_data = bpy.data.curves.new("curve_data", type = "CURVE")
        curve_data.dimensions = '3D'

        num_points = 5
        coords = [np.random.random((3,)) * i for i in range(num_points)]
        polyline = curve_data.splines.new('POLY')
        polyline.points.add(len(coords) - 1)
        for i, coord in enumerate(coords):
            x, y, z = coord
            polyline.points[i].co = (x, y, z, 1)

        path = bpy.data.objects.new("cube_path", curve_data)
        curve_data.bevel_depth = 0.01

        self.scene.objects.link(path)
        self.scene.objects.active = path
        path.hide_render = True

        return path

    def setup_cube(self):
        self.cube = bpy.data.objects['Cube']
        material = self.add_material()
        if self.cube.data.materials:
            self.cube.data.materials[0] = material
        else:
            self.cube.data.materials.append(material)

        self.cube.active_material = material
        path = self.add_path()
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_pattern(pattern="Cube")
        self.scene.objects.active = self.cube

        bpy.ops.object.constraint_add(type = 'FOLLOW_PATH')
        self.cube.constraints["Follow Path"].target = path
        self.cube.constraints["Follow Path"].forward_axis = 'FORWARD_X'
        self.cube.constraints["Follow Path"].use_curve_follow = True

        override={'constraint':self.cube.constraints["Follow Path"]}
        bpy.ops.constraint.followpath_path_animate(override, constraint='Follow Path')

    def setup_plane(self):
        self.plane = bpy.data.objects['Plane']
        material = self.add_material()
        if self.plane.data.materials:
            self.plane.data.materials[0] = material
        else:
            self.plane.data.materials.append(material)

        self.plane.active_material = material

    def setup_scene(self):
        self.setup_lamp()
        self.setup_cube()
        self.setup_plane()

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

        color_node = nodes.new(type = "CompositorNodeOutputFile")
        color_node.base_path = os.path.join(out_dir, "reflectance/")
        links.new(rlayers_node.outputs["Diffuse"], color_node.inputs["Image"])

    def render_scene(self, out_dir):
        self.render.engine = "CYCLES"

        if self.use_gpu:
            for card_num, card in enumerate(bpy.context.user_preferences.addons['cycles'].preferences.devices):
                print("GPU Device {}: {}".format(card_num, card.name))
            bpy.context.scene.cycles.device = 'GPU'
            bpy.context.user_preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'
            # Modify the command below to CUDA_0 to use only the 0th CUDA device
            bpy.context.user_preferences.addons['cycles'].preferences.compute_device = 'CUDA_MULTI_2'
            bpy.ops.wm.save_userpref()
        else:
            bpy.context.scene.cycles.device = 'CPU'

        self.render.resolution_x = 1024
        self.render.resolution_y = 1024
        self.render.tile_x = 256
        self.render.tile_y = 256
        self.scene.frame_start = 1
        self.scene.frame_end = 100
        self.scene.use_nodes = True
        self.render.layers["RenderLayer"].samples = 64
        self.render.layers["RenderLayer"].use_pass_combined = False
        self.render.layers["RenderLayer"].use_pass_diffuse_color = True
        self.setup_render_node_tree(out_dir)
        #bpy.ops.render.render(animation = True)

        for itr in range(1, 20):
            self.scene.frame_set(itr)
            bpy.ops.render.render(write_still = True)

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
    ap.add_argument("--use-gpu", type = int, default = 0,
                    help = "Use GPU if available (default: 0)")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir)

    start = time.time()
    for itr in range(args.resume_from, args.num_videos):
        print("=> Processing iteration {}".format(itr))
        out_dir = os.path.join(args.out_dir, "{:05d}/".format(itr))
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        scene = Generator(use_gpu = args.use_gpu)
        scene.generate(out_dir = out_dir)
    print("\nBlender takes {} secs to generate {} videos".format(
        time.time() - start, args.num_videos - args.resume_from))

if __name__=="__main__":
    main()
