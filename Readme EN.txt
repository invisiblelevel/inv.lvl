========================================
  TEXTURE PACK — README (EN)
========================================

This pack contains a set of high-quality PBR textures.
All textures are seamless (tileable) and ready to use
in game engines and 3D software.

----------------------------------------
  WHAT'S INSIDE
----------------------------------------

Each texture includes the following maps:

  _Albedo      — Base Color / Diffuse
  _Normal      — Normal map (OpenGL)
  _Height      — Height map (for parallax / displacement)
  _AO          — Ambient Occlusion
  _Metallic    — Metalness
  _Smoothness  — Smoothness (for Unity)
  _ORM         — Packed map (R=AO, G=Roughness, B=Metallic)

Resolutions: 8K.
Format: PNG (lossless).

----------------------------------------
  IMPORTANT: SMOOTHNESS vs ROUGHNESS
----------------------------------------

This pack includes a **_Smoothness** map.

  White = smooth / glossy
  Black = rough / matte

This map is ready to use in Unity (Built-in, URP, HDRP).

IF YOU NEED A _Roughness MAP:

  Blender, Substance Painter, Unreal Engine and some other
  engines expect a Roughness map, which is the OPPOSITE
  of Smoothness.

  To get a Roughness map — simply invert the Smoothness map
  in any image editor:

    GIMP:        Colors → Invert (Ctrl + I)
    Photoshop:   Image → Adjustments → Invert
    Krita:       Filters → Adjust → Invert

  Or use the ready-made _ORM map (see below).

----------------------------------------
  ORM MAP (for Unreal Engine and others)
----------------------------------------

This pack includes a packed **_ORM.png** map:
  Red channel   (R) = Ambient Occlusion
  Green channel (G) = Roughness
  Blue channel  (B) = Metallic

If your shader supports ORM — plug this map in instead of
separate AO / Roughness / Metallic maps.

----------------------------------------
  FOR UNITY
----------------------------------------

Unity (Standard / URP / HDRP) expects Metallic and Smoothness
in a SINGLE texture:
  Red channel (R) = Metallic
  Alpha channel (A) = Smoothness

If you don't have a ready-made packed map — you can build
one manually in GIMP / Photoshop by putting _Metallic into
the red channel and _Smoothness into the alpha channel.

Don't forget to disable sRGB (Color Texture) in Unity's
texture import settings for all maps except _Albedo. 
