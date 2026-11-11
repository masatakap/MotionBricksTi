"""Responsive panel geometry and one export menu for Studio."""

LABELS={
'notice':('Model check','モデルの確認','Verificación del modelo','Vérification du modèle','模型检查'),
'mmd_ready':('MMD model loaded. The supported bone checks passed.','MMDモデルの読み込みが完了しました。対応ボーンの検査を通過しました。','Modelo MMD cargado; huesos compatibles.','Modèle MMD chargé ; os compatibles.','MMD模型加载完成，已通过支持骨骼检查。'),
'mmd_failed':('This model is not supported.','このモデルは対応していません。','Este modelo no es compatible.','Ce modèle n’est pas pris en charge.','不支持此模型。'),
'options':('Export settings','書き出し設定','Opciones de exportación','Options d’exportation','导出设置'),
'resolution':('MP4: {w} × {h} px / 30 fps','MP4：{w} × {h} px／30fps','MP4: {w} × {h} px / 30 fps','MP4 : {w} × {h} px / 30 ips','MP4：{w} × {h} 像素／30fps'),
}


def caption(key,language):return LABELS[key][('en','ja','es','fr','zh').index(language if language in ('en','ja','es','fr','zh') else 'en')]


def panel_layout(width,height,scale):
    # Leave central canvas space even on smaller windows; all positions are
    # recomputed each frame rather than restored once from imgui.ini.
    left=min(360*scale,max(140,width*.23))
    right=min(430*scale,max(180,width*.28))
    top=min(32*scale,height*.15)
    timeline=min(155*scale,max(65,height*.22))
    return left,right,top,timeline


def same_line_if_fits(ui,label,language):
    from .studio_i18n import text
    if ui.get_item_rect_size().x+ui.calc_text_size(text(label,language)).x+32<ui.get_content_region_avail().x:ui.same_line()


def draw_export_menu(app,ui):
    # A developer-only isolated render hook can open the real menu for docs.
    if getattr(app,'_capture_export_menu',False):ui.open_popup('Export###Export')
    if not ui.begin_menu('Export'):return
    try:
        pos=ui.get_window_pos();size=ui.get_window_size();app._export_menu_bounds=(pos.x,pos.y,size.x,size.y)
        ready=getattr(app,'timeline',None) is not None and not app.busy
        if ui.menu_item('Export FBX...','',False,ready)[0]:app.pending='export'
        ui.separator()
        if ui.menu_item('Choose MMD target PMX or PMD...','',False,not app.busy)[0]:app.pending='vmd_model'
        if getattr(app,'vmd_target_path',None):ui.text_wrapped(app.vmd_target_path.name)
        ui.push_font(ui.get_font(),ui.get_font_size()*.8)
        ui.push_style_color(ui.Col_.text,ui.ImVec4(1.,.3,.3,1.))
        try:ui.text_wrapped('VMD uses target PMX or PMD proportions and FK bones. Leg IK is disabled.')
        finally:ui.pop_style_color();ui.pop_font()
        if ui.menu_item('Export MMD VMD...','',False,ready and getattr(app,'vmd_target_path',None) is not None)[0]:app.pending='vmd'
        ui.separator()
        from .studio_video import output_resolution
        w,h=output_resolution(app.viewer)
        if ui.menu_item('Export Reference MP4...','',False,ready)[0]:app.pending='video'
        ui.push_font(ui.get_font(),ui.get_font_size()*.8)
        try:ui.text_unformatted(caption('resolution',app.language).format(w=w,h=h))
        finally:ui.pop_font()
        ui.begin_disabled(app.busy)
        _,app.video_audio=ui.checkbox('Include music in MP4',app.video_audio)
        ui.end_disabled()
        ui.separator()
        if ui.begin_menu(caption('options',app.language)):
            ui.begin_disabled(app.busy)
            _,app.export_inplace=ui.checkbox('In-place (remove XY travel)',app.export_inplace)
            _,app.export_mesh=ui.checkbox('Include preview mesh',app.export_mesh)
            ui.end_disabled();ui.end_menu()
        if getattr(app,'_capture_export_close',False):ui.close_current_popup()
    finally:ui.end_menu()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
