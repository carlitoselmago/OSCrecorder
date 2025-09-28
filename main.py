bl_info = {
    "name": "OSC Recorder",
    "author": "Carlos Carbonell htmlfiesta.com",
    "version": (0, 4, 0),
    "blender": (3, 6, 0),
    "location": "Sidebar > OSC",
    "description": "Receive OSC (UDP), record to keyframes, expose as Geometry Nodes group, driver-friendly.",
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
    end = data.find(b'\x00', offset)
    if end == -1:
        raise ValueError("OSC: unterminated string")
    s = data[offset:end].decode("utf-8", errors="replace")
    size = (end - offset + 1)
    pad = (4 - (size % 4)) % 4
    new_offset = end + 1 + pad
    return s, new_offset

def parse_osc_message(packet: bytes):
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
# OSC Receiver
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
        s = bpy.context.scene.osc_minrec
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

            # If not existing yet
            if prop_name not in reader.keys():
                if not s.auto_add_addresses:
                    continue
                item = s.addresses.add()
                item.name = prop_name
                item.enabled = True
                reader[prop_name] = 0.0

            # Find metadata
            addr_meta = next((a for a in s.addresses if a.name == prop_name), None)
            if addr_meta and not addr_meta.enabled:
                continue  # skip if disabled

            # Assign value
            if isinstance(v, (bool, int, float, str)) or v is None:
                reader[prop_name] = v if v is not None else 0.0
            else:
                reader[prop_name] = str(v)
            reader.location = reader.location

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

class OSCAddressItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    enabled: bpy.props.BoolProperty(default=True)


class OSCAddOnSettings(bpy.types.PropertyGroup):
    bind_ip: bpy.props.StringProperty(
        name="Bind IP", default="0.0.0.0",
        description="Local IP to listen on (0.0.0.0 for all)",
    )
    port: bpy.props.IntProperty(
        name="Port", default=9000, min=1, max=65535,
        description="UDP port to listen for OSC",
    )
    auto_add_addresses: bpy.props.BoolProperty(
        name="Auto add OSC addresses",
        default=True,
        description="Automatically create new OSC properties when first received",
    )
    addresses: bpy.props.CollectionProperty(type=OSCAddressItem)
    live_running: bpy.props.BoolProperty(default=False)
    record_running: bpy.props.BoolProperty(default=False)

# ==============================
# Operators
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

class OSC_OT_AddAddress(bpy.types.Operator):
    bl_idname = "osc.add_address"
    bl_label = "Add OSC Address"

    address: bpy.props.StringProperty(name="OSC Address", default="/new/address")

    def execute(self, context):
        reader = create_reader()
        s = context.scene.osc_minrec
        prop_name = normalize_address(self.address)

        if prop_name not in reader.keys():
            reader[prop_name] = 0.0
            item = s.addresses.add()
            item.name = prop_name
            item.enabled = True
            self.report({'INFO'}, f"Added {prop_name}")
        else:
            self.report({'WARNING'}, f"{prop_name} already exists.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class OSC_OT_RemoveAddress(bpy.types.Operator):
    bl_idname = "osc.remove_address"
    bl_label = "Remove OSC Address"

    index: bpy.props.IntProperty()

    def execute(self, context):
        s = context.scene.osc_minrec
        reader = get_reader()
        if 0 <= self.index < len(s.addresses):
            prop_name = s.addresses[self.index].name
            if reader and prop_name in reader.keys():
                del reader[prop_name]
            s.addresses.remove(self.index)
            self.report({'INFO'}, f"Removed {prop_name}")
        return {'FINISHED'}

class OSC_OT_CreateNodegroup(bpy.types.Operator):
    bl_idname = "osc.create_nodegroup"
    bl_label = "Create/Update Nodegroup"

    def execute(self, context):
        s = context.scene.osc_minrec
        reader = create_reader()

        group_name = "OSC_Inputs"
        if group_name in bpy.data.node_groups:
            ng = bpy.data.node_groups[group_name]
        else:
            ng = bpy.data.node_groups.new(group_name, "GeometryNodeTree")

        # Ensure Group Output node exists
        if not any(n for n in ng.nodes if n.type == "GROUP_OUTPUT"):
            out_node = ng.nodes.new("NodeGroupOutput")
            out_node.location = (400, 0)
        else:
            out_node = next(n for n in ng.nodes if n.type == "GROUP_OUTPUT")

        # Build a map of existing sockets
        existing = {sock.name: sock for sock in ng.interface.items_tree if sock.item_type == 'SOCKET'}

        # Add new outputs if missing
        for addr in s.addresses:
            if addr.name not in existing:
                sock = ng.interface.new_socket(
                    name=addr.name,
                    in_out='OUTPUT',
                    socket_type='NodeSocketFloat'
                )
                # Create Value node + driver
                val_node = ng.nodes.new("ShaderNodeValue")
                val_node.label = addr.name
                val_node.location = (-200, -80 * len(ng.interface.items_tree))

                fcurve = val_node.outputs[0].driver_add("default_value")
                drv = fcurve.driver
                drv.type = 'SCRIPTED'
                var = drv.variables.new()
                var.name = "var"
                var.targets[0].id = reader
                var.targets[0].data_path = f'["{addr.name}"]'
                drv.expression = "var"

                ng.links.new(val_node.outputs[0], out_node.inputs[sock.identifier])

        # Remove outputs that no longer exist in addresses
        to_remove = [sock for sock in existing.keys() if sock not in [a.name for a in s.addresses]]
        for name in to_remove:
            sock = existing[name]
            ng.interface.remove(sock)

        self.report({'INFO'}, "Nodegroup created/updated with OSC addresses.")
        return {'FINISHED'}



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
        reader = get_reader()

        col = layout.column(align=True)
        col.prop(s, "bind_ip")
        col.prop(s, "port")
        col.prop(s, "auto_add_addresses")

        # Start/Stop
        row = layout.row(align=True)
        if not s.live_running:
            row.operator("osc.live_start", text="Start", icon="PLAY")
        else:
            row.operator("osc.live_start", text="Stop", icon="PAUSE")

        # Record
        row = layout.row(align=True)
        row.enabled = s.live_running
        if not s.record_running:
            row.operator("osc.record", text="Record", icon="REC")
        else:
            row.operator("osc.record", text="Stop Rec", icon="REC")

        layout.separator()
        layout.operator("osc.add_address", icon="ADD")
        layout.operator("osc.create_nodegroup", icon="NODETREE")

        # Address rows
        box = layout.box()
        if len(s.addresses) == 0:
            box.label(text="No addresses yet…")
        else:
            for i, addr in enumerate(s.addresses):
                row = box.row(align=True)
                row.prop(addr, "enabled", text="")
                row.label(text=addr.name)

                if reader and addr.name in reader.keys():
                    row.prop(reader, f'["{addr.name}"]', text="")

                op = row.operator("osc.remove_address", text="", icon="X")
                op.index = i

# ==============================
# Registration
# ==============================

classes = (
    OSCAddressItem,
    OSCAddOnSettings,
    OSC_OT_LiveStart,
    OSC_OT_Record,
    OSC_OT_AddAddress,
    OSC_OT_RemoveAddress,
    OSC_OT_CreateNodegroup,
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
