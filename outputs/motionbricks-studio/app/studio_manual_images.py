"""Language-specific real UI figures with red callouts and zoomable crops."""
from pathlib import Path
import ctypes,json
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]/'docs/screenshots'
FIGURES={
 'interface_refresh_20261104':('overview',None),'workflow':('overview',None),'pose':('overview',1),'library':('overview',0),
 'timing':('overview',1),'playback':('overview',2),'saving':('overview',3),
 'fbx':('export',0),'vmd':('export',0),'mmd_check':('mmd',0),'mp4':('export',0),'requirements':('overview',3),
 'authoring':('authoring',0),'ue_bridge':('overview',3),'ue_sequencer_playback':('overview',3),
 'kimodo_connection':('kimodo',0),'external_fbx_bvh_import':('import',0),
 'environment':('environment',0),'full_motion':('authoring',0),'library_genres':('overview',0),'interval_motion':('interval',0)}
CAPTIONS={
 'ja':'図：赤枠が操作箇所です。クリックすると拡大します。',
 'en':'Figure: the red outline marks the controls. Click to enlarge.',
 'es':'Figura: el marco rojo indica los controles. Pulse para ampliar.',
 'fr':'Figure : le cadre rouge indique les commandes. Cliquez pour agrandir.',
 'zh':'图：红框表示操作位置。点击可放大。'}


def load_texture(app,path):
    cache=getattr(app,'_manual_image_cache',None)
    if cache is None:cache=app._manual_image_cache={}
    if path in cache:return cache[path]
    with Image.open(path) as image:data=np.ascontiguousarray(image.convert('RGBA'))
    gl=app.viewer.renderer.gl;texture=gl.GLuint();gl.glGenTextures(1,ctypes.byref(texture));gl.glBindTexture(gl.GL_TEXTURE_2D,texture)
    gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR)
    gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA8,data.shape[1],data.shape[0],0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,data.ctypes.data_as(ctypes.c_void_p))
    gl.glBindTexture(gl.GL_TEXTURE_2D,0)
    cache[path]=(texture.value,data.shape[1],data.shape[0]);return cache[path]


def draw_figure(app,ui,topic):
    if topic not in FIGURES:return
    language=app.language;kind,index=FIGURES[topic];path=ROOT/(language+'-'+kind+'.png')
    manifest=ROOT/'manifest.json'
    if not path.is_file() or not manifest.is_file():return
    if not hasattr(app,'_manual_figure_manifest'):app._manual_figure_manifest=json.loads(manifest.read_text(encoding='utf8'))
    texture,w,h=load_texture(app,path);uv0=ui.ImVec2(0,0);uv1=ui.ImVec2(1,1);aspect=w/h
    if index is not None:
        x,y,cw,ch=app._manual_figure_manifest[path.name]['boxes'][index]
        x=max(0,x-5);y=max(0,y-5);cw=min(w-x,cw+10);ch=min(h-y,ch+10)
        uv0=ui.ImVec2(x/w,y/h);uv1=ui.ImVec2((x+cw)/w,(y+ch)/h);aspect=cw/ch
    ui.text_wrapped(CAPTIONS.get(language,CAPTIONS['en']))
    available=ui.get_content_region_avail().x;width=min(available,650.)
    ui.image(ui.ImTextureRef(texture),ui.ImVec2(width,width/aspect),uv0,uv1)
    popup={'ja':'図を拡大','en':'Enlarge figure','es':'Ampliar figura','fr':'Agrandir la figure','zh':'放大图片'}.get(language,'Enlarge figure')+'###figure_zoom_'+topic
    if ui.is_item_clicked():ui.open_popup(popup)
    v=ui.get_main_viewport();ui.set_next_window_size(ui.ImVec2(v.size.x-40,v.size.y-60),ui.Cond_.first_use_ever)
    visible,_=ui.begin_popup_modal(popup,True)
    if visible:
        try:
            zoom=getattr(app,'_manual_figure_zoom',1.)
            _,zoom=ui.slider_float({'ja':'拡大率','en':'Zoom','es':'Ampliación','fr':'Zoom','zh':'缩放'}.get(language,'Zoom'),zoom,1.,4.,'%.1f x')
            app._manual_figure_zoom=zoom
            ui.begin_child('figure_scroll',ui.ImVec2(0,0),window_flags=ui.WindowFlags_.horizontal_scrollbar)
            try:
                width=max(100,ui.get_content_region_avail().x)*zoom
                ui.image(ui.ImTextureRef(texture),ui.ImVec2(width,width/aspect),uv0,uv1)
            finally:ui.end_child()
        finally:ui.end_popup()
    ui.spacing()
    if topic=='vmd':draw_figure(app,ui,'mmd_check')

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
