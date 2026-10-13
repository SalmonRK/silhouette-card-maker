# SRK preset cut files (`.studio3`)

Cut files for the layouts in [`../presets.py`](../presets.py). Upstream ships none for them, and a `.studio3`
can only be made inside Silhouette Studio, so build each one **once** from the preset's DXF and save it here
under the exact name below. `scm_bridge.template_path` looks in this folder first, so the web page then
offers it like any upstream template.

## `srk-a4-standard-gap3-v1.studio3` — A4 Standard 3×3, 3 mm gap

| | value |
|---|---|
| Cards | 9 × 63 × 88 mm, portrait A4, 3 mm between cards (1.5 mm bleed each side) |
| First card (on the real paper) | x 7.54 · y 13.55 mm |
| Cut-line group | W 194.91 × H 269.86 mm |
| Marks on the real paper | inset **5 mm**, length 5 mm, thickness 1 mm, 3 marks |
| Studio page (declared) | **220 × 307 mm** portrait = A4 + 2 × (10 − 5) mm |
| Sheet on the mat | **5 mm** in from the top-left grid corner (top and left) |

Steps (Silhouette Studio 5, units in mm):

1. **Edit › Preferences › Import › DXF Open = As-is** (otherwise Studio rescales the DXF).
2. Download the DXF from the web page (step 4, *Download cut lines DXF*) or
   `GET /api/preset/srk-a4-standard-gap3.dxf`, then **File › Open** it.
3. **Page Setup**: machine CAMEO 5 · cutting mat **12 × 12** · media size **Custom** · width **220** ·
   height **307** · portrait. If Studio refuses the height, untick *Constrain media to cutting mat*
   (upstream does the same for its borderless templates on the 12 × 12 mat).
4. `Ctrl+A`, `Ctrl+G`, **Transform › Center to Page**. Check the group: W 194.91 / H 269.86,
   X ≈ 12.54 / Y ≈ 18.57.
5. **Print & Cut**: registration marks **on**, type 1 (3 marks), **length 5 · thickness 1 · inset 10**.
   (Inset 10 on the 220 × 307 page = 5 mm on the real sheet.)
6. `Ctrl+A`, `Ctrl+Shift+G` (ungroup), then **File › Save As** →
   `webui/templates/srk-a4-standard-gap3-v1.studio3`.

Check before the first real cut: in Studio, File › Merge the front PNG of a generated job, place it at
X 5 / Y 5 (the paper's position on the declared page), and every cut line must sit on a card edge.

Using it: print the **PDF** at Actual size / 100% (never from Studio — the declared page is larger than the
paper), place the sheet 5 mm in from the mat grid corner, open this `.studio3` and Send.
