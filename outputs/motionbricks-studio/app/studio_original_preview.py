"""Render dense skeletal clips directly with the static SOMA mesh."""
import argparse,json,subprocess,hashlib
from types import SimpleNamespace
from pathlib import Path
import numpy as np
import warp as wp
import newton
from newton.viewer import ViewerGL
from pyglet.math import Vec3
from PIL import Image,ImageDraw
import imageio_ffmpeg
from motionbricks.io.utils import get_soma_human_model
from motionbricks.renderers.skeletal_mesh_renderer import SkeletalMeshRenderer
from motionbricks.renderers.solid_box_renderer import SolidBoxRenderer
from .studio_original_library import CATALOG
from .studio_motion_review import curve_hash

def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);parser.add_argument('--only',nargs='*');parser.add_argument('--video',action='store_true');parser.add_argument('--interaction',action='store_true');parser.add_argument('--front',action='store_true');parser.add_argument('--fixed-camera',action='store_true');parser.add_argument('--view',choices=('front','side','back','three-quarter'));parser.add_argument('--output-subdir',default='previews');parser.add_argument('--frames',nargs='+',type=int)
    parser.add_argument('--all-files',action='store_true',help='Render arbitrary converted clips; do not invent reference props.')
    args=parser.parse_args();folder=args.folder;wp.init()
    viewer=ViewerGL(width=960,height=720,headless=True);viewer.show_ui=False
    builder=newton.ModelBuilder();builder.add_ground_plane();ground=builder.finalize();viewer.set_model(ground);state=ground.state()
    mesh=get_soma_human_model();renderer=SkeletalMeshRenderer(mesh);pose=wp.empty(mesh.skeleton.num_joints,dtype=wp.transform);boxes=SolidBoxRenderer()
    previews=folder/args.output_subdir;previews.mkdir(exist_ok=True,parents=True)
    try:
        specs=[SimpleNamespace(id=p.stem,kind='imported') for p in sorted(folder.glob('*.npz')) if p.stem!='static-rig'] if args.all_files else CATALOG
        for spec in specs:
            if args.only and spec.id not in args.only:continue
            path=folder/(spec.id+'.npz')
            if not path.exists():continue
            poses=np.load(path)['poses'];tiles=[];selected=np.linspace(0,len(poses)-1,8).astype(int)
            if spec.kind.startswith('vault'):selected=np.array([0,25,34,38,42,46,52,len(poses)-1])
            if args.frames:
                selected=np.array(args.frames)
                if np.any(selected<0) or np.any(selected>=len(poses)):raise ValueError('Preview frame is outside the motion')
            movie=None
            if args.video:
                movie=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-pix_fmt','rgb24','-s','960x720','-r','30','-i','pipe:0','-c:v','libx264','-crf','20','-pix_fmt','yuv420p',str(previews/(spec.id+'.mp4'))],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
            for f in (range(len(poses)) if args.video else selected):
                p=poses[f];pose.assign(p);center=np.r_[p[0,:2],.90+max(0.,p[0,2]-.99)]
                if args.fixed_camera:center=np.r_[poses[0,0,:2],.90]
                # Three-quarter fixed heading with camera following root translation.
                view=args.view or ('front' if args.front else 'three-quarter')
                offset={'front':[0.,-3.3,.25],'side':[3.3,0.,.25],'back':[0.,3.3,.25],'three-quarter':[1.8,-2.8,.7]}[view]
                camera=center+np.array(offset);viewer.camera.pos=Vec3(*camera);viewer.camera.look_at(center.astype(np.float32));viewer._camera_dirty=True
                viewer.begin_frame(f/30);viewer.log_state(state)
                props=[];sizes=[]
                if spec.kind.startswith('vault'):
                    h=.5 if spec.kind=='vault_low' else .75;props=[wp.transform(wp.vec3(0,0,h/2),wp.quat_identity())];sizes=[wp.vec3(1.,getattr(spec,'reference_depth',(.6 if spec.kind=='vault_low' else .3) if args.interaction else .25),h)]
                elif spec.kind in ('sit_down','stand_up','seated_idle'):
                    h=getattr(spec,'reference_height',.4 if args.interaction else .45);props=[wp.transform(wp.vec3(0,.03,h-.025),wp.quat_identity())];sizes=[wp.vec3(.50,.48,.05)]
                boxes.draw_batch(viewer,props,sizes,[wp.vec3(.7,.43,.18)]*len(props),'reference_props')
                renderer.draw_pose(viewer,pose,wp.transform_identity(),wp.vec3(.28,.64,.88),'adult')
                viewer.end_frame();pixels=viewer.get_frame().numpy()
                if float(pixels.mean())<2. and int(pixels.max())<8:raise RuntimeError('Empty rendered frame; use one fresh renderer process per view')
                if movie:movie.stdin.write(pixels.tobytes())
                if f in selected:
                    image=Image.fromarray(pixels).resize((320,240));ImageDraw.Draw(image).text((8,8),f'{spec.id}  {f/30:.2f}s',fill='white');tiles.append(image)
            if movie:
                movie.stdin.close()
                if movie.wait(timeout=60):raise RuntimeError('Video encoding failed: '+spec.id)
            sheet=Image.new('RGB',(1280,240*max(1,(len(tiles)+3)//4)))
            for i,tile in enumerate(tiles):sheet.paste(tile,((i%4)*320,(i//4)*240))
            sheet.save(previews/(spec.id+'.jpg'));print('rendered',spec.id,flush=True)
            manifest=dict(curve_sha256=curve_hash(poses,mesh.skeleton._np_parent_indices,list(mesh.skeleton.joint_names),30.),frames=len(poses),fps=30,view=args.view or ('front' if args.front else 'three-quarter'),fixed_camera=args.fixed_camera,selected_frames=selected.tolist(),sheet_sha256=hashlib.sha256((previews/(spec.id+'.jpg')).read_bytes()).hexdigest())
            if args.video:manifest['video_sha256']=hashlib.sha256((previews/(spec.id+'.mp4')).read_bytes()).hexdigest()
            (previews/(spec.id+'-render.json')).write_text(json.dumps(manifest,indent=2),encoding='utf8')
    finally:viewer.close()

if __name__=='__main__':main()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
