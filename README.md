# OSCrecorder

An OSC listener that can record its values and bake them as animation keyframes, no extra add-ons required.

How it works in short:
- Start OSC (listens on the IP/port you set).
- Optional: Record to keyframes on the internal `OSC_reader` object.
- Create Nodegroup to expose received channels as numeric sockets.
- Copy a channel as a driver and paste it on any animatable property.
- Bake your driven object animation to regular keyframes.

## Copy Driver from OSC channel

After you’ve received some OSC messages and clicked “Create Nodegroup”, a node group called `OSC_Inputs` is created/updated with one output per channel (e.g. `osc_speed`, `osc_knob1`).

To grab a driver from any channel:
1) Open the Geometry Nodes editor and switch the data-block to edit the `OSC_Inputs` node group (not a modifier on an object; edit the group itself).
2) Select the “Group Output” node. You will see a numeric field for each output socket.
3) Right‑click the numeric field of the channel you want and choose “Copy As New Driver”. This driver reads from `OSC_reader["osc_…"]` already.

## Paste Driver on a target property

1) Go to the property you want to animate (for example `Object > Transform > Location X`).
2) Right‑click the property and choose “Paste Driver”. The value should now follow your incoming OSC.
3) Optional: Tweak the driver on the target property to scale/offset the input (e.g. set expression to `var * 0.1 + 1.0`).

Tips:
- If you don’t see your channel in `OSC_Inputs`, send at least one OSC message for that address and click “Create Nodegroup” again to refresh outputs.
- Channel names are normalized to `osc_<name>` (non‑alphanumerics become `_`).

## Bake object animation

Once a property is driven by OSC (live or from recorded keyframes on `OSC_reader`), you can bake the result to regular keyframes:

1) Set your frame range to the interval you want to bake.
2) Select the object(s) that have driven transform properties.
3) Object menu > Animation > Bake Action…
4) In the Bake dialog:
   - Start/End: set to your range.
   - Only Selected: as needed.
   - Visual Keying: ON (captures evaluated result of drivers/constraints).
   - Clear Constraints: OFF (keep), you can remove drivers manually after.
   - Bake Data: Object (for transforms). For bones, use Pose.
5) Confirm Bake. You should see regular keyframes on the baked channels.
6) Right‑click the property and choose “Delete Driver” to detach it, if desired.

Alternative workflow using the add-on’s Record button:
- Click “Start OSC”, then “Record”. The add-on inserts keyframes on `OSC_reader["osc_…"]` every frame while the timeline plays.
- With drivers applied to your object properties, run playback over the range to populate values.
- Use Bake Action as above to turn the driven result into regular keyframes on your object.

## Troubleshooting

- Add-on not visible: In Preferences > Add‑ons, click Refresh. Ensure your Blender version meets the minimum and that your symlink points to the folder containing `__init__.py`.
- No values updating: Confirm your IP/port, and test by sending a simple float to an address like `/knob1`. The reader will store it as `osc_knob1`.
- Drivers too noisy/high: Edit the driver expression (e.g., low‑pass yourself `prev*0.9 + var*0.1`, or scale with `var * 0.05`).
