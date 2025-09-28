# OSC Recorder

An OSC listener for Blender that can record incoming values, expose them as drivers in Geometry Nodes, and bake them as animation keyframes — no extra add-ons required.

---

## How it works
- **Start OSC**: listens on the IP/port you set.  
- **Manage addresses**: add automatically (first message received) or manually. You can disable channels temporarily or remove them completely.  
- **Optional recording**: store osc data internally on `OSC_reader` object while the timeline plays, later you can use that to bake into keyframes.
- **Create/Update Nodegroup**: builds/refreshes a Geometry Nodes group (`OSC_Inputs`) with outputs for each active OSC channel.  
- **Use as drivers**: copy a channel as a driver and paste it onto any animatable property.  
- **Bake to keyframes**: convert live OSC-driven motion into regular keyframes on your objects.  

---

## Managing OSC addresses
- **Auto add**: new OSC addresses are created automatically when messages arrive (default).  
- **Manual add**: click **Add Address** and enter the OSC path (e.g. `/knob1`).  
- **Enable/Disable**: toggle a channel to stop/start listening without deleting it.  
- **Remove**: click **X** to delete a channel (also removes its property).  

---

## Create/Update Nodegroup

Click **Create/Update Nodegroup** to generate or refresh a Geometry Nodes group called `OSC_Inputs`.  

- Each OSC address becomes a **float output socket**.  
- Under the hood, sockets are backed by drivers linked to the `OSC_reader` custom properties.  
- Existing sockets keep their external connections when the group is updated.  

---

## Copy a driver from OSC channel

1. Open the **Geometry Nodes editor** and edit the `OSC_Inputs` node group (not as a modifier, but the group itself).  
2. Select the **Group Output** node. Each channel has a numeric field.  
3. Right-click a channel field and choose **Copy As New Driver**.  
   → This driver is already set up to read from `OSC_reader["osc_…"]`.  

---

## Paste driver on a target property

1. Go to the property you want to animate (e.g. *Object > Transform > Location X*).  
2. Right-click it and choose **Paste Driver**. The value now follows your OSC channel.  
3. Optional: edit the driver expression to scale or offset (e.g. `var * 0.1 + 1.0`).  

---

## Bake object animation

Once a property is driven by OSC (live or via recorded keyframes on `OSC_reader`), you can bake the motion:  

1. Set your frame range.  
2. Select the object(s) with OSC-driven transforms.  
3. Go to *Object menu > Animation > Bake Action…*  
4. In the dialog:  
   - **Start/End**: set your range.  
   - **Visual Keying**: ON (captures driver results).  
   - **Clear Constraints**: OFF (keep drivers until you remove them manually).  
   - **Bake Data**: Object (for transforms) or Pose (for bones).  
5. Confirm. You now have regular keyframes.  
6. (Optional) Right-click a property and choose **Delete Driver** to detach.  

---

## Alternative: Record button

Instead of using drivers:  

- Click **Start OSC**, then **Record**.  
- The add-on inserts keyframes on `OSC_reader["osc_…"]` every frame during playback.  
- Apply drivers from these recorded properties to your objects.  
- Bake as above to finalize.  

---

## Troubleshooting

- **Add-on not visible**: In *Preferences > Add-ons*, click *Refresh*. Ensure Blender is 3.6+ and that the folder contains `__init__.py`.  
- **No values updating**: Confirm IP/port. Test with a simple float to `/knob1`. It should appear as `osc_knob1`.  
- **Missing channels in nodegroup**: Send at least one OSC message or add manually, then click *Create/Update Nodegroup*.  
- **Drivers too noisy**: Adjust the driver expression (e.g. `prev*0.9 + var*0.1` for smoothing, or `var * 0.05` for scaling).  

---

## Current limitations

- It can only handle single values per adress, will be improved in future versions
- Only compatible with Blender 4.0 and above.
