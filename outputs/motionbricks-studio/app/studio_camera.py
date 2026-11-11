"""Studio-only camera bindings; leave upstream Newton and left-button editing intact."""
def install_camera_controls(viewer):
    gui=viewer.gui
    original_press=gui.handle_mouse_press

    def press(x,y,button,to_framebuffer_coords):
        from pyglet.window import mouse
        if button==mouse.RIGHT: return
        original_press(x,y,button,to_framebuffer_coords)

    def drag(x,y,dx,dy,buttons,to_framebuffer_coords,modifiers=0):
        from pyglet.window import mouse
        if gui.should_ignore_mouse_input(): return
        camera=viewer.camera
        if buttons & mouse.MIDDLE:
            scale=gui._camera_pan_scale()
            camera.pan(-dx*scale,-dy*scale)
        elif buttons & mouse.RIGHT:
            camera.orbit(-dx*gui._camera_orbit_sensitivity,dy*gui._camera_orbit_sensitivity)
        else:
            # Left button is reserved for selection and the transform gizmo.
            return
        viewer._camera_dirty=True

    gui.handle_mouse_press=press
    gui.handle_mouse_drag=drag

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
