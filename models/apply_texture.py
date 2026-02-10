
import bpy
import os
import sys

# Parameters
model_file = "Avatar_001.glb"
texture_file = "ComfyUI_Event_02_00001_.png"
output_file = "Avatar_001_Bonded.glb"

# Ensure we are in the correct directory (where the script is run from)
# If running via "blender --background --python models/apply_texture.py", 
# CWD might be the root of the repo, but the files are in models/
# We will assume the script is run from the repo root and files are in 'models/'
# OR the script is run from 'models/' directory.
# Let's try to interpret paths relative to where the script is located if possible,
# or just assume a standard path structure.

# Check if we can find the files in the current working directory or relative to it.
base_dir = os.getcwd()
if os.path.basename(base_dir) != "models":
    # If we are not in models/, assume we need to append models/
    model_path = os.path.join(base_dir, "models", model_file)
    texture_path = os.path.join(base_dir, "models", texture_file)
    output_path = os.path.join(base_dir, "models", output_file)
else:
    model_path = os.path.join(base_dir, model_file)
    texture_path = os.path.join(base_dir, texture_file)
    output_path = os.path.join(base_dir, output_file)

print(f"Model Path: {model_path}")
print(f"Texture Path: {texture_path}")
print(f"Output Path: {output_path}")

if not os.path.exists(model_path):
    print(f"Error: Model file not found at {model_path}")
    sys.exit(1)

if not os.path.exists(texture_path):
    print(f"Error: Texture file not found at {texture_path}")
    sys.exit(1)

# Clear existing mesh objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import GLB
print("Importing GLB...")
bpy.ops.import_scene.gltf(filepath=model_path)

# Load Texture
print("Loading Texture...")
try:
    img = bpy.data.images.load(texture_path)
except Exception as e:
    print(f"Failed to load image: {e}")
    sys.exit(1)

# Apply texture to all materials
print("Applying Texture to Materials...")
for mat in bpy.data.materials:
    if not mat.use_nodes:
        mat.use_nodes = True
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Find Principled BSDF
    bsdf = None
    for node in nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bsdf = node
            break
    
    if bsdf:
        # Check if there is already an image texture connected to Base Color
        base_color_socket = bsdf.inputs['Base Color']
        
        # Create Image Texture Node
        tex_image_node = nodes.new('ShaderNodeTexImage')
        tex_image_node.image = img
        
        # Link it
        links.new(tex_image_node.outputs['Color'], base_color_socket)
        print(f"Applied texture to material: {mat.name}")
    else:
        print(f"No Principled BSDF found for material {mat.name}")

# Create Output Directory if it doesn't exist (managed by path construction, but good practice)
output_dir = os.path.dirname(output_path)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Export GLB
print(f"Exporting to {output_path}...")
bpy.ops.export_scene.gltf(filepath=output_path, export_format='GLB')

print("Done.")
