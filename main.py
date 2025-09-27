bl_info = {
    "name": "OSC Minimal Recorder",
    "author": "Carlos + ChatGPT",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "Sidebar > OSC",
    "description": "Receive OSC (UDP) into an internal reader object; live + record to keyframes; driver-friendly.",
    "category": "System",
}

import bpy
import socket
import struct
import re

# ==============================
# Helpers: Reader + Name utils
# ==============================

def get_reader():
    return bpy.data.objects.get("OSC_reader")

def create_reader(link_to_collection=True):
    obj = get_reader()
    if obj is None:
        obj = bpy.data.objects.new("OSC_reader", None)
        obj.use_fake_user = True
        if link_to_collection:
            try:
                bpy.context.collection.objects.link(obj)
            except Exception:
                pass
    return obj

def normalize_address(address: str | None) -> str:
    """Sanitize an OSC address into a valid custom property name."""
    text = (address or "").strip()
    if text.startswith("/"):
        text = text[1:]
    text = re.sub(r"[^0-9A-Za-z_]+", "_", text)
    if not text:
        text = "message"
    text = text.lower()
    if not text.startswith("osc_"):
        text = f"osc_{text}"
    return text

# ==========================================
# Minimal OSC parser (message, not bundles)
# ==========================================

def _read_cstring_padded(data, offset):
    """Read a null-terminated string padded to 4 bytes."""
    end = data.find(b'\x00', offset)
    if end == -1:
        raise ValueError("OSC: unterminated string")
    s = data[offset:end].decode("utf-8", errors="replace")
    size = (end - offset + 1)
    pad = (4 - (size % 4)) % 4
    new_offset = end + 1 + pad
    return s, new_offset

def parse_osc_message(packet: bytes):
    """Parse a single OSC message (no bundles)."""
    if packet.startswith(b"#bundle"):
        return None

    offset = 0
    address, offset = _read_cstring_padded(packet, offset)
    if not address.startswith("/"):
        return None

    type_tag, offset = _read_cstring_padded(packet, offset)
    if not type_tag.startswith(","):
        return address, "", []

    tags = type_tag[1:]
    args = []
    for t in tags:
        if t == "i":
            if offset + 4 > len(packet): return address, type_tag, args
            (val,) = struct.unpack(">i", packet[offset:offset+4])
            offset += 4
            args.append(val)
        elif t == "f":
            if offset + 4 > len(packet): return address, type_tag, args
            (val,) = struct.unpack(">f", packet[offset:offset+4])
            offset += 4
            args.append(val)
        elif t == "T":
            args.append(True)
        elif t == "F":
            args.append(False)
        elif t == "s":
            s, offset = _read_cstring_padded(packet, offset)
            args.append(s)
        else:
            break
    return address, "," + tags, args

# ==========================================
# OSC Receiver (UDP, non-blocking)
# ==========================================

class _OSCReceiver:
    def __init__(self, bind_ip: str, port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_ip, port))
        self.sock.setblocking(False)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

    def poll(self):
        reader = get_reader()
        if not reader:
            return
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
            except BlockingIOError:
                break
            except Exception:
                break

            parsed = parse_osc_message(data)
            if not parsed:
                continue
            address, _tags, args = parsed
            v = args[0] if len(args) > 0 else None

            prop_name = normalize_address(address)
            if isinstance(v, (bool, int, float, str)) or v is None:
                reader[prop_name] = v if v is not None else 0.0
            else:
                reader[prop_name] = str(v)

            reader.location = reader.location  # nudge depsgraph

# ==============================
# Record handler
# ==============================

def keyframe_osc_inputs(scene):
    reader = get_reader()
    if not reader:
        return
    frame = scene.frame_current
    for prop_name, prop_value in reader.items():
        if prop_name.startswith("osc_"):
            try:
                reader.keyframe_insert(data_path=f'["{prop_name}"]', frame=frame)
            except Exception as e:
                print(f"[OSC] Failed to keyframe {prop_name}: {e}")

# ==============================
# Scene Properties
# ==============================

class OSCAddOnSettings(bpy.types.PropertyGroup):
    bind_ip: bpy.props.StringProperty(
        name="Bind IP", default="0.0.0.0",
        description="Local IP to listen on (0.0.0.0 for all)",
    )
    port: bpy.props.IntProperty(
        name="Port", default=9000, min=1, max=65535,
        description="UDP port to listen for OSC",
    )
    live_running: bpy.props.BoolProperty(default=False)
    record_running: bpy.props.BoolProperty(default=False)

# ==============================
# Operators: Live + Record
# ==============================

class OSC_OT_LiveStart(bpy.types.Operator):
    bl_idname = "osc.live_start"
    bl_label = "Start OSC"

    _timer = None
    _receiver = None

    def modal(self, context, event):
        s = context.scene.osc_minrec
        if event.type == 'TIMER' and self._receiver:
            self._receiver.poll()
        if not s.live_running or event.type in {'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def execute(self, context):
        s = context.scene.osc_minrec
        if s.live_running:
            s.live_running = False
            return {'CANCELLED'}
        create_reader()
        try:
            self._receiver = _OSCReceiver(s.bind_ip, s.port)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to bind {s.bind_ip}:{s.port} – {e}")
            return {'CANCELLED'}
        wm = context.window_manager
        self._timer = wm.event_timer_add(1/60, window=context.window)
        wm.modal_handler_add(self)
        s.live_running = True
        self.report({'INFO'}, f"OSC listening on {s.bind_ip}:{s.port}")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        s = context.scene.osc_minrec
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        if self._receiver:
            self._receiver.close()
            self._receiver = None
        s.live_running = False
        self.report({'INFO'}, "OSC Stopped.")

class OSC_OT_Record(bpy.types.Operator):
    bl_idname = "osc.record"
    bl_label = "Record OSC Inputs"

    _timer = None

    def modal(self, context, event):
        s = context.scene.osc_minrec
        if not s.record_running or event.type in {'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def execute(self, context):
        s = context.scene.osc_minrec
        if s.record_running:
            s.record_running = False
            return {'CANCELLED'}
        if not s.live_running:
            self.report({'WARNING'}, "Start OSC first.")
            return {'CANCELLED'}
        if keyframe_osc_inputs not in bpy.app.handlers.frame_change_pre:
            bpy.app.handlers.frame_change_pre.append(keyframe_osc_inputs)
        wm = context.window_manager
        self._timer = wm.event_timer_add(1/60, window=context.window)
        wm.modal_handler_add(self)
        bpy.ops.screen.animation_play()
        s.record_running = True
        self.report({'INFO'}, "Recording OSC…")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        s = context.scene.osc_minrec
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
        except Exception:
            pass
        if keyframe_osc_inputs in bpy.app.handlers.frame_change_pre:
            bpy.app.handlers.frame_change_pre.remove(keyframe_osc_inputs)
        s.record_running = False
        self.report({'INFO'}, "Stopped recording.")

# ==============================
# UI Panel
# ==============================

class OSC_PT_Main(bpy.types.Panel):
    bl_label = "OSC"
    bl_idname = "OSC_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OSC"

    def draw(self, context):
        layout = self.layout
        s = context.scene.osc_minrec

        col = layout.column(align=True)
        col.prop(s, "bind_ip")
        col.prop(s, "port")

        row = layout.row(align=True)
        if not s.live_running:
            row.operator("osc.live_start", text="Start", icon="PLAY")
        else:
            row.operator("osc.live_start", text="Stop", icon="PAUSE")

        row = layout.row(align=True)
        row.enabled = s.live_running
        if not s.record_running:
            row.operator("osc.record", text="Record", icon="REC")
        else:
            row.operator("osc.record", text="Stop Rec", icon="REC")

        layout.separator()
        reader = get_reader()
        if reader:
            box = layout.box()
            box.label(text="Live values (copyable fields):")
            shown = 0
            for k, v in reader.items():
                if not k.startswith("osc_"):
                    continue
                # Show as a real Blender property → right-click > Copy Data Path works
                box.prop(reader, f'["{k}"]', text=k)
                shown += 1
                if shown >= 12:
                    break
            if shown == 0:
                box.label(text="(waiting for OSC…)")

# ==============================
# Registration
# ==============================

classes = (
    OSCAddOnSettings,
    OSC_OT_LiveStart,
    OSC_OT_Record,
    OSC_PT_Main,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.osc_minrec = bpy.props.PointerProperty(type=OSCAddOnSettings)

def unregister():
    try:
        if keyframe_osc_inputs in bpy.app.handlers.frame_change_pre:
            bpy.app.handlers.frame_change_pre.remove(keyframe_osc_inputs)
    except Exception:
        pass
    del bpy.types.Scene.osc_minrec
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
