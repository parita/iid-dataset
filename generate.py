import os
import sys
import bpy
import numpy as np

blend_dir = os.path.basename(bpy.data.filepath)
if blend_dir not in sys.path:
       sys.path.append(blend_dir)
sys.path.append("./")

import argparse

class Generator():
    def __init__(self):
        self.scene = bpy.context.scene
        self.render = self.scene.render

    def cleanup_scene(self):
        for material in bpy.data.materials:
            bpy.data.materials.remove(material)
        for curve in bpy.data.curves:
            bpy.data.curves.remove(curve)

    def setup_lamp(self):
        self.lamp = bpy.data.lamps['Lamp']
        self.lamp.type = "AREA"
        self.lamp.color = np.random.random((3,))
        self.lamp.energy = 1.0
        self.lamp.distance = 10.0

    def add_material(sekf):
        bpy.data.materials.new(name = "Material")
        material = bpy.data.materials["Material"]
        material.diffuse_color = np.random.random((3,))
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

    def setup_scene(self):
        self.setup_lamp()
        self.setup_cube()

    def render(self):
        self.render.engine = "BLENDER_RENDER"
        self.render.use_nodes = True

    def generate(self, out_dir):
        self.setup_scene()
        self.render()

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
    args = ap.parse_args(argv)

    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir)

    scene = Generator()
    scene.generate(out_dir = args.out_dir)

if __name__=="__main__":
    main()