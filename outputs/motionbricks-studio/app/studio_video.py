"""Deterministic viewport rendering to atomic MP4, using the current camera."""
import copy
import ctypes
import math
from pathlib import Path
import subprocess
import tempfile
import numpy as np
import imageio_ffmpeg


def output_resolution(viewer):
    width,height=viewer.renderer.window.get_framebuffer_size()
    return width+width%2,height+height%2


def export_video(app,destination,include_audio=True):
    if app.timeline is None:raise ValueError('Generate an animation before exporting.')
    destination=Path(destination).resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    keys=['show_targets','show_generated','edit_bones','preview_playing','timeline_time','audio_sync']
    saved={key:getattr(app,key) for key in keys}
    camera=copy.deepcopy(app.viewer.camera.__dict__)
    show_ui=app.viewer.show_ui
    update_camera=app.viewer._update_camera
    ignore_mouse=app.viewer.gui.should_ignore_mouse_input
    audio_position=app.audio.position
    audio_playing=app.audio.playing
    width,height=app.viewer.renderer.window.get_framebuffer_size()
    frames=max(1,math.ceil(app.timeline.duration*30))
    with tempfile.TemporaryDirectory(prefix='studio_video_',dir=destination.parent) as folder:
        output=Path(folder)/'render.mp4'
        command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-pix_fmt','rgb24',
                 '-s',f'{width}x{height}','-r','30','-i','pipe:0']
        if include_audio and app.audio.path:
            command+=['-i',str(app.audio.path),'-map','0:v:0','-map','1:a:0','-af','apad','-c:a','aac']
        command+=['-t',str(frames/30),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
                  '-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-movflags','+faststart',str(output)]
        process=None
        try:
            app.audio.pause()
            app.video_exporting=True
            app.viewer.show_ui=False
            app.show_targets=False;app.show_generated=True;app.edit_bones=False
            app.preview_playing=False;app.audio_sync=False
            app.viewer._update_camera=lambda dt:None
            app.viewer.gui.should_ignore_mouse_input=lambda:True
            gl=app.viewer.renderer.gl
            pixels=(ctypes.c_ubyte*(width*height*3))()
            with (Path(folder)/'encoder.log').open('w+b') as log:
                process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                for frame in range(frames):
                    if not app.viewer.is_running():raise RuntimeError('Video export cancelled.')
                    if app.viewer.renderer.window.get_framebuffer_size()!=(width,height):
                        raise RuntimeError('Window size changed; export cancelled. Keep the window size fixed.')
                    app.viewer.camera.__dict__.update(copy.deepcopy(camera))
                    app.viewer._camera_dirty=True
                    app.timeline_time=frame/30
                    app.timeline.sample(app.timeline_time,app.current_pose,stream=app.engine.stream)
                    app.viewer.renderer.set_title(f'MotionBricks Studio Ti - MP4 {frame+1}/{frames}')
                    app.render()
                    if not app.viewer.is_running():raise RuntimeError('Video export cancelled.')
                    gl.glReadBuffer(gl.GL_FRONT)
                    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT,1)
                    gl.glReadPixels(0,0,width,height,gl.GL_RGB,gl.GL_UNSIGNED_BYTE,pixels)
                    image=np.ctypeslib.as_array(pixels).reshape(height,width,3)
                    process.stdin.write(image[::-1].tobytes())
                process.stdin.close()
                if process.wait(timeout=120):
                    log.seek(0);raise RuntimeError(log.read().decode('utf-8',errors='replace')[-3000:])
            output.replace(destination)
        finally:
            if process and process.poll() is None:
                process.kill();process.wait()
            for key,value in saved.items():setattr(app,key,value)
            app.viewer.camera.__dict__.update(camera)
            app.viewer._camera_dirty=True
            app.viewer.show_ui=show_ui
            app.viewer._update_camera=update_camera
            app.viewer.gui.should_ignore_mouse_input=ignore_mouse
            app.video_exporting=False
            if app.viewer.is_running():app.viewer.renderer.set_title('MotionBricks Studio Ti')
            app.audio.seek(audio_position)
            if audio_playing:app.audio.play()
    return str(destination)

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
