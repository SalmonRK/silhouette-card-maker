# SCM Studio (web UI)

หน้าเว็บสำหรับ [Silhouette Card Maker](https://github.com/Alan-Cha/silhouette-card-maker) รันในเครื่องตัวเอง: ใส่รูปการ์ด → เลือกขนาด → สร้าง PDF → ดาวน์โหลดไฟล์ตัด `.studio3` ที่ตรงกัน พร้อมขั้นตอนพิมพ์และตัดด้วย CAMEO

A local web UI for Silhouette Card Maker: add card images, pick a size, make the PDF and download the matching `.studio3` cut file, with print-and-cut steps for the CAMEO.

## เริ่มใช้

```
webui\start.bat
```
หรือ `venv\Scripts\python webui\app.py` แล้วเปิด http://127.0.0.1:5190 (เปลี่ยนพอร์ตด้วย `SCM_WEBUI_PORT`)

ต้องมี Python 3.12+ · `start.bat` สร้าง venv และติดตั้ง `requirements.txt` + `webui/requirements.txt` ให้ครั้งแรก

## ทำอะไรได้บ้าง

แถบบนแบ่งเป็น 3 ส่วน (workspace): **นำเข้าเด็ค** · **สร้างแผ่นพิมพ์** · **ตั้งค่าเครื่อง**

| ส่วน / ขั้น | หน้าจอ | เบื้องหลัง |
|---|---|---|
| **A นำเข้าเด็ค** | เลือกเกมจากภาพ (22 เกม) → วางเด็คลิสต์/ลิงก์ → ดึงรูป → ตรวจผล (จำนวนต่อใบ, สองหน้า, คำเตือน) → "ใช้กับแผ่นพิมพ์" · แท็บ **ประวัติ** เปิดเด็คเก่าใช้ซ้ำได้ไม่ต้องดึงใหม่ | ดึงลงคลัง `webui/data/library/decks/<เกม>/<เจ้าของ>/…` ก่อน แล้วค่อยคัดลอกเข้างาน · แท็บ **การ์ดทั้งหมด** + Excel (ดูด้านล่าง) |
| **B ① รูปการ์ด** | ลากวางรูปหน้า, หลังร่วม 1 รูป, หลังเฉพาะใบ (สองหน้า), การ์ดตัวอย่าง 8 ใบ, ปุ่มไปนำเข้าเด็ค | เก็บในโฟลเดอร์งานของตัวเอง `webui/jobs/<id>/` ไม่แตะ `game/` |
| **B ② ขนาดและกระดาษ** | หน้าตาตามแบบ Figma D2/D2b: เลือกกระดาษ/ขนาดการ์ดจากภาพ (ขนาดตามแนวจริงของแผ่น เช่น ไร้ขอบ A4 = 210 × 297) + รายการขนาดทั้งหมด (เฉพาะคู่ที่มีเลย์เอาต์), สวิตช์ไร้ขอบ, borderless (A4/Letter ได้ 9 ใบ 3×3 แทน 8 — เปิดแล้วมีป้าย "8 → 9 ใบต่อแผ่น" และกล่องเตือนเงื่อนไข: พิมพ์จาก PDF เท่านั้น, วางกระดาษห่างมุม mat 6.5 มม., เครื่องพิมพ์ต้องพิมพ์ถึง 3.5 มม.), mark 3/4 จุด (ภาพ), ยืด/ครอป · ข้อมูลเลย์เอาต์เป็นชิปใต้แผ่นพิมพ์ · ไอคอน Lucide เก็บในเครื่อง (`static/icons.js`, ใช้ได้ offline) · ตั้งค่าเพิ่มเติม (พับได้): **ถมมุมโค้ง** (`--extend_corners`, เช่น 3.5mm สำหรับรูป Scryfall — นำเข้าเด็ค MTG เปิดให้เองถ้ายังว่าง), **ขยายขอบรูป** (`--extend_edges`), ขยาย bleed, ครอปขอบ | คำนวณด้วย `page_manager.generate_layout` ตัวเดียวกับ SCM แสดงบนพื้นที่จำลองแผ่นรองตัดตามสเกลจริง |
| **B ③ สร้างไฟล์พิมพ์** | ข้อความกำกับ, เส้นขอบ, ใช้ค่าชดเชยสองหน้า, ภาพตัวอย่างทุกหน้า · ดาวน์โหลด PDF, PNG (zip), ชุดสำหรับ Studio (zip) | เรียก `utilities.generate_pdf` สองรอบ (PDF + `output_images=True`) แล้วฝัง DPI ให้ PNG |
| **B ④ พิมพ์และตัด** | เลือกเส้นทาง "พิมพ์จาก PDF" หรือ "พิมพ์จาก Silhouette Studio" แต่ละทางมีขั้นตอนของตัวเอง · ดาวน์โหลด `.studio3` ของขนาดที่ใช้, ตารางใบมีด | ใช้ `cutting_templates/` ของ SCM |
| **C ตั้งค่าเครื่อง** | ชดเชยสองหน้า (แผ่นคาลิเบรต + X/Y/มุม) · คลังไฟล์ตัด `.studio3` ทุกขนาดตามกระดาษ (ขนาดที่ใช้อยู่อยู่บนสุด ป้าย "ใช้อยู่") · แผ่น mark อย่างเดียว · ตารางใบมีด | `calibration/`, `GET /api/templates?paper=`, `/api/marks` |

**หน้าตา (ตามแบบ Figma "SCM · Desktop 1440" D1–D8):** ทุกหน้าใช้ชิ้นส่วนชุดเดียวกัน — ไอคอน Lucide เก็บในเครื่อง (`static/icons.js`), tile เลือกจากภาพ, สวิตช์ (checkbox จริง `role=switch`), ปุ่ม "ถัดไป" ติดล่างแผง, ข้อมูลเป็นชิปมีไอคอนใต้แผ่นพิมพ์ (เปลี่ยนตามขั้น)
- ① กล่องวางรูปมีไอคอน, ปุ่มการ์ดตัวอย่าง/นำเข้าเด็ค, กล่องหลังการ์ด + สวิตช์พิมพ์เฉพาะหน้า, การ์ดเป็นภาพย่อ 4 คอลัมน์ (เลข, ลบ, "+ หลังเฉพาะใบ" / ป้ายเขียวเมื่อมีหลังแล้ว)
- ③ สวิตช์เส้นขอบ/ชดเชยสองหน้า (ล็อกปิดถ้ายังไม่ตั้งค่า), แถบผลสีเขียว "สร้างเสร็จใน … วินาที", ไฟล์เป็นแถว PDF (แนะนำ) / PNG / ชุด Studio
- ④ การ์ดเส้นทางพร้อมภาพ (PDF / Studio), ขั้นตอนเป็น timeline มีเลขและภาพ (`static/assets/guide/`)
- A ช่องรูปแบบเด็คแบบเดียวกับขั้น ②, ตัวเลือกของเกมเป็น tile พับได้ + สวิตช์
- C พื้น mat, การ์ดเครื่องมือมีภาพหัว, ป้าย "ตั้งแล้ว" ที่ชดเชยสองหน้า, ไฟล์ตัดเป็นแถวไฟล์

## ไฟล์ที่ได้จากขั้น 3

| ปุ่ม | ข้างใน | ใช้เมื่อ |
|---|---|---|
| PDF | ทุกแผ่น หน้า/หลัง สลับกัน มี mark ในไฟล์ | พิมพ์จากโปรแกรมเปิด PDF ที่ Actual size แล้วใช้ Studio แค่ตัด (แนะนำ) |
| PNG (zip) | `<paper>-<card>-s<แผ่น>-front.png` / `-back.png` มี mark เหมือน PDF · ฝัง DPI จริง | พิมพ์จากโปรแกรมดูภาพ หรือเก็บไว้ใช้ที่อื่น |
| ชุดสำหรับ Studio (zip) | ภาพหน้า**ที่ลบ mark ออกแล้ว** + ภาพหลัง + `.studio3` ที่ตรงกับขนาด + `README.txt` ขั้นตอน | Studio ที่เปิด PDF ไม่ได้ (รุ่น Basic) และต้องพิมพ์จาก Studio |

**ทำไมต้องฝัง DPI:** PNG ที่ SCM สร้างเองไม่มี chunk `pHYs` (ส่ง `resolution=` ให้ PIL แต่ PNG ใช้ `dpi=`) Silhouette Studio จึงเดาขนาดเอง เว็บนี้บันทึกใหม่ด้วย `dpi=(ppi, ppi)` เช่น A4 = 3507 × 2480 px ที่ 300 dpi = **296.93 × 209.97 มม.** เท่าหน้า PDF (SCM ปัด pixel ลง จึงสั้นกว่า 297 อยู่ 0.07 มม. ไม่มีผลเพราะ mark กับเส้นตัดอ้างอิงจาก pixel ชุดเดียวกัน)

**ทำไมต้องลบ mark ในชุด Studio:** ถ้าพิมพ์จาก Studio โดยเปิด Registration Marks ไว้ Studio จะพิมพ์ mark ของตัวเองทับ mark ที่อยู่ในภาพ ถ้าวางภาพคลาดแม้นิดเดียวจะได้ mark ซ้อนสองชุด เซนเซอร์อ่านเพี้ยน `scm_bridge.mark_mask()` วาด mark ใหม่ด้วย `page_manager.generate_reg_mark` ของ SCM เอง หมุน/ย่อแบบเดียวกับ `generate_pdf` ขยายขอบ 0.4 มม. แล้วระบายขาวเฉพาะตรงนั้น ภาพหลังเก็บ mark ไว้ (ค่าชดเชยสองหน้าอาจเลื่อนมันไปแล้ว และด้านหลังไม่ได้ตัด)

ตรวจแล้วกับทุกเลย์เอาต์ใน `layouts.json` × mark 3/4 จุด: mask ทับ mark จริง, ไม่โดนช่องการ์ดเลยสักช่อง, DPI อ่านกลับได้ 300

## พิมพ์จาก PDF กับพิมพ์จาก Studio ต่างกันอย่างไร

| เรื่อง | พิมพ์ PDF (Studio แค่ตัด) | พิมพ์จาก Studio (ภาพ PNG ใน `.studio3`) |
|---|---|---|
| mark กับภาพ | อยู่ในไฟล์เดียวกัน ตรงกันทุก pixel | Studio พิมพ์ mark เอง ภาพต้องวางให้ตรงด้วยมือ |
| จุดพลาดบ่อย | ลืมตั้ง Actual size / 100% · "Fit" ย่อ 3–6% ตัดผิดทั้งแผ่น | ขนาดภาพตอน Merge ผิด, ไม่ได้วางที่ X 0 / Y 0, mark ซ้อนสองชุด |
| คุณภาพภาพ | SCM ใส่ภาพใน PDF แบบ JPEG quality 100 | PNG ไม่สูญเสีย |
| สี | บางโปรแกรมเปิด PDF ปรับสีตามโปรไฟล์ | ส่งตรงไปไดรเวอร์ |
| การ์ดสองหน้า | PDF ไฟล์เดียวมีหน้าและหลัง | ทีละแผ่น ทีละด้าน |
| ไดรเวอร์เลื่อนภาพ / ขอบกระดาษ | mark กับภาพเลื่อนไปด้วยกัน ตัดยังตรง | เหมือนกัน |
| สเกลเครื่องพิมพ์คลาด ±0.2–0.3% | การ์ดไกลจาก mark เพี้ยน ต้องชดเชยสเกล (ยังไม่ทำ) | เหมือนกัน |

**แนวกระดาษ:** SCM หมุนทุกแผ่นเป็นแนวนอนเสมอ (`add_front_back_pages` → `rotate(90)`) ทาง PDF ไดรเวอร์หมุนกลับให้ตอนพิมพ์ แต่ไฟล์ตัดของเลย์เอาต์แนวตั้ง (เช่น `a4-standard-borderless-v2`, `letter-*-borderless`) เป็นหน้าแนวตั้ง ภาพในชุด Studio จึงหมุนกลับ (`rotate(-90)`) ให้แนวตรงกับไฟล์ตัด ตรวจแล้วทุกเลย์เอาต์ว่าสี่เหลี่ยมดำของ mark อยู่มุมบนซ้ายเหมือนในไฟล์ตัด · ชุด PNG (zip) ยังเป็นแนวนอนเหมือน PDF

**เลย์เอาต์ borderless ใช้ได้แค่ทาง PDF:** ไฟล์ตัด borderless ของ SCM ตั้งหน้ากระดาษใหญ่กว่าจริง 13 มม. (A4 → 223.01 × 309.88) เพราะ Studio บังคับ mark ห่างขอบ ≥10 มม. หน้าที่ใหญ่ขึ้นทำให้ mark อยู่ห่างขอบกระดาษจริงแค่ 3.5 มม. (ดู `hugo/content/miscellaneous/borderless.md`) ผลคือ
- ต้องวางกระดาษ**ห่างจากมุมบนซ้ายของตาราง mat 6.5 มม. ทั้งบนและซ้าย** ไม่ใช่ชิดมุม (ขั้น 4 แสดงคำเตือนเมื่อเลือก borderless)
- พิมพ์จาก Studio ไม่ได้ เพราะ Studio จะส่งหน้า 223 × 310 ไปเครื่องพิมพ์ ภาพเลื่อนและขอบขาด → `studio.zip` ตอบ 409 `borderless-pdf-only` และหน้าเว็บซ่อนปุ่มพร้อมบอกเหตุผล
- เครื่องพิมพ์ต้องพิมพ์ได้ถึง 3.5 มม. จากขอบด้วยโหมดปกติ (โหมด borderless ของไดรเวอร์จะขยายภาพ ตัดเพี้ยน)

**แผ่น mark อย่างเดียว (`/api/marks`):** สำหรับด้านหน้าที่พิมพ์ออกมาแล้วไม่มี mark ป้อนแผ่นเดิมกลับเข้าเครื่องแล้วพิมพ์ทับ · `scm_bridge.marks_only()` วาด mark ด้วย `generate_reg_mark` + การหมุน/ย่อแบบ `generate_pdf` (ฟังก์ชันเดียวกับที่ใช้ลบ mark) ตรวจแล้วกับ A4 standard borderless: mark ตรงกับหน้า PNG ของ SCM ทุก pixel (11,076 px ไม่มีเกินไม่มีขาด) หน้า PDF 296.93 × 209.97 มม. เท่า PDF การ์ด · `kind=pdf|png|upright` (upright = หมุนกลับแนวตั้ง มีเฉพาะเลย์เอาต์แนวตั้ง) · ขั้น 4 บอกระยะที่ต้องวัดก่อนพิมพ์ทับ (ขอบภาพการ์ดใบแรก = ช่องแรก − bleed เช่น A4 borderless: ซ้าย 8.55 / บน 14.56 มม.) · ข้อจำกัด: การป้อนกระดาษรอบสองของเครื่องพิมพ์คลาดได้ ~0.3–1 มม. ซึ่งจะไปอยู่ในการตัดตรง ๆ

**สีเส้นตัด:** เส้นตัดใน `.studio3` ของ SCM เป็นสีเทา ไม่ต้องเปลี่ยนเป็นแดง Studio ตัดตามเส้นที่ตั้งเป็น Cut ในแท็บ ส่ง ไม่ได้ดูสีเส้น (ยกเว้นเลือกโหมดตัดตามสีเส้นเอง) ตรวจที่แท็บ ส่ง ว่าการ์ดทุกใบถูกเน้นเป็นเส้นตัด

สรุป: ถ้าเปิด PDF ได้ ใช้ทาง PDF · ถ้าต้องอยู่ใน Studio ใช้ชุด Studio และเช็ก W/H ในแผง Transform ทุกครั้ง

## Preset ของ SRK (เลย์เอาต์ที่ `layouts.json` ทำไม่ได้)

SCM เว้นช่องระหว่างการ์ดตายตัว 1.25 มม. (`CARD_DISTANCE` ใน `page_manager.generate_layout`) borderless 3×3 จึงทนคลาดได้แค่ ±0.6 มม. ตัดจริงแถวล่างกินภาพใบบน (Card repo RESEARCH §20) · `webui/presets.py` เพิ่มเลย์เอาต์ของเราเองเป็น **specialty layout** ชื่อขึ้นต้น `srk-` (ไม่ชนชื่อ template ของ SCM `{paper}-{card}[-borderless]-vN`) และไม่แก้ไฟล์ upstream:
- `presets.install()` (เรียกตอน import `scm_bridge`) ห่อ `utilities.load_layout_config` ให้มี specialty ของเราเพิ่ม และห่อ `page_manager.generate_layout` ให้ใช้ช่องไฟของ preset **เฉพาะใน** `with presets.active(name)` นอกนั้นเป็นฟังก์ชันเดิมของ SCM
- ไฟล์ตัด `.studio3` ของ preset อยู่ที่ `webui/templates/` (สร้างครั้งเดียวใน Studio จาก DXF ขั้นตอนใน `webui/templates/README.md`) · `template_path` หาในโฟลเดอร์นี้ก่อน · DXF: `GET /api/preset/<name>.dxf`
- preset ที่ mark < 10 มม. ใช้เทคนิคหน้าใหญ่แบบ borderless → `meta.pdfOnly` (`studio.zip` ตอบ 409) และ `layout.matOffset` = ระยะวางกระดาษจากมุมตาราง mat (ขั้น 4 แสดงคำเตือน)

| preset | การ์ด | ช่องไฟ | mark (ระยะขอบ/ยาว/หนา) | หน้าใน Studio | วางกระดาษ |
|---|---|---|---|---|---|
| `srk-a4-standard-gap3` | standard 63×88 · 3×3 แนวตั้ง · ใบแรก x 7.54 / y 13.55 | **3 มม.** (bleed 1.5) | 5 / 5 / 1 มม. · 3 จุด | 220 × 307 มม. | ห่างมุม mat 5 มม. |

ตรวจแล้ว: PDF 9 ช่อง, mark ห่าง art ≥2 มม., เลย์เอาต์ SCM เดิม (A4 standard 4×2, borderless 3×3) ไม่เปลี่ยน, หน้าเว็บไทยไม่มี console error

## นำเข้าเด็ค (ดึงรูปการ์ดอัตโนมัติ + ประวัติ)

แถบบน → **นำเข้าเด็ค** · เลือกเกม (ภาพการ์ดตัวอย่าง 15 เกม, เกมที่ไม่มีภาพใช้ตัวย่อ+สีประจำเกม) → รูปแบบเด็ค → วางข้อความ export หรือลิงก์แชร์บรรทัดเดียว (แสดงจำนวนใบโดยประมาณ) → **ดึงรูปการ์ด** → หน้าตรวจผลแสดงภาพทุกแบบ จำนวน ×N ป้ายสองหน้า คำเตือนจาก log → เลือก **ต่อท้ายการ์ดเดิม** (ค่าเริ่มต้น) หรือ **แทนที่ทั้งหมด** → **ใช้กับแผ่นพิมพ์** แล้วไปขั้น ① ทันที · "แก้เด็ค" กลับไปแก้ข้อความเดิม · ดึงได้ทีละเด็ค กดหยุดได้

**คลังเด็ค = ประวัติ:** ทุกการดึงเก็บเป็นหมวด `webui/data/library/decks/<เกม>/<เจ้าของ>/<YYYY-MM-DD> <ชื่อเด็ค> [<id>]/` (`deck.json` = เกม/เจ้าของ/ชื่อเด็ค/ผู้สร้างจากเว็บ/รูปแบบ/ข้อความเด็ค/ตัวเลือก/สถานะ/คำเตือน/สรุปข้อมูลการ์ด, `front/`, `double_sided/`, `raw/`, `log.txt`) · ฟอร์มมีช่อง **เจ้าของ** (จำค่าล่าสุด) และ **ชื่อเด็ค** (เว้นว่าง = ใช้ชื่อจากเว็บต้นทาง เช่น Ashes/Elestrals/Bushiroad ถ้าไม่มีใช้ "<เกม> <เวลา>") · แก้เจ้าของ/ชื่อในหน้าผลการดึงได้ โฟลเดอร์ย้ายตาม · แท็บ ประวัติ กรองตามเกม/เจ้าของ/คำค้น · ลบได้ทีละเด็ค · ไม่เก็บใน git (`data/` อยู่ใน `.gitignore`) · เด็คจาก `data/decks/<id>/` แบบเก่าย้ายเข้าโครงใหม่อัตโนมัติตอนเปิดเซิร์ฟเวอร์

**ไม่ดึงซ้ำ (2 ชั้น):**
1. วางเด็คเดิม (เกม + รูปแบบ + ข้อความ + ตัวเลือกเดียวกัน) ที่เคยดึงสำเร็จแล้ว → เปิดเด็คเดิมให้ทันที ไม่ดาวน์โหลดเลย (`reused`) · ปุ่ม **ดึงใหม่** บังคับดึงอีกรอบ
2. ทุก request ของ plugin ผ่าน HTTP cache ถาวร (`requests-cache` → `data/library/http-cache.sqlite`): ข้อมูล API เก็บ 30 วัน รูปการ์ดเก็บถาวร · การ์ดที่เคยดึงในเด็คอื่นไม่ยิงซ้ำ · ถ้าเว็บต้นทางล่มยังตอบจาก cache · หน้าผลแสดง "ใช้ข้อมูลที่เก็บไว้ n/m ครั้ง"

**สถานะ "ไม่ได้การ์ดเลย" (`empty`):** plugin จบปกติแต่ไม่ได้รูปสักใบ (มักเลือกรูปแบบไม่ตรงกับข้อความ) — เดิมขึ้น "ดึงเสร็จแล้ว"

## คลังการ์ด: ชื่อ ค่าพลัง rarity + Excel (`catalog.py`)

plugin ของ SCM เก็บแค่รูป `capture.py` จึงบันทึก JSON ทุกคำตอบที่ plugin ได้ระหว่างดึงลง `<เด็ค>/raw/NNNN.json` แล้ว `catalog.py` หา object การ์ดในนั้น (ชื่อ + มี field อย่าง rarity/type/cost/code) จับคู่กับไฟล์รูป `<ลำดับ><ชื่อ><สำเนาที่>.png` ด้วยชื่อหรือรหัส แล้วบันทึกลง `data/library/library.sqlite`:
- `cards` — เกม · ชื่อ · ชุด · เลข/รหัส · ประเภท · rarity · cost · power · defense · hp · สี/ฝ่าย · ข้อความ · `stats` (ทุก field สั้น ๆ ของเกมนั้น) · รูป 1 ไฟล์ต่อการ์ดใน `data/library/images/<เกม>/`
- `decks` · `deck_cards` (เด็คไหน ใช้การ์ดอะไร กี่ใบ สองหน้าไหม)

4+1 plugin ไม่ถามฐานข้อมูลเลย (สร้าง URL รูปจากรหัส) จึงค้นเพิ่มเองผ่าน cache เดียวกัน: Yu-Gi-Oh → YGOPRODeck API (passcode) · Digimon → digimoncard.io · One Piece → optcgapi.com · Gundam → หน้า card detail ของ gundam-gcg.com · Pokémon → pokemontcg.io (ชุด+เลขจากเด็คลิสต์) สำรองด้วย TCGdex เพราะ pokemontcg.io ตอบ 500/502 บ่อย

ผลทดสอบ (README ตัวอย่างของแต่ละ plugin, 2026-10-13): ได้ข้อมูลครบทุกแบบ — Arkham 4/4 · Ashes 19/19 · Bushiroad 29/29 · Digimon 8/8 · Elestrals 26/26 · FFTCG 3/3 · FaB 5/5 · Grand Archive 9/9 · Gundam 10/10 · KeyForge 31/31 · Lorcana 7/7 · MTG 5/5 · Netrunner 23/23 · One Piece 10/10 · Pokémon 7/7 · SWU 4/4 · Yu-Gi-Oh 5/5
- Elestrals (carde.io) ส่ง set/rarity/type/cost เป็น id อ้างอิง → ได้ชื่อ ข้อความ attack/defense รหัสชุด แต่ rarity/ประเภทว่าง · SWU rarity เป็นตัวเลขตามที่ swudb ส่ง
- ทดสอบไม่ได้เพราะ plugin/เว็บต้นทางเสียเอง (ไม่เกี่ยวกับ webui): Altered (`api.altered.gg` DNS ไม่พบ) · Echoes of Astra (400) · Riftbound piltover_archive (404) · Sorcery (`NameError: get` ใน plugin) · LotR ยังไม่ได้ทดสอบ

**Excel `data/library/exports/การ์ดทั้งหมด.xlsx`** สร้างใหม่อัตโนมัติหลังดึง/แก้ชื่อ/ลบเด็ค และดาวน์โหลดได้จากปุ่ม **Excel** ในแท็บ การ์ดทั้งหมด: ชีต สรุป (เด็ค/ใบ ต่อเกม×เจ้าของ) · การ์ดทั้งหมด (คอลัมน์ร่วม + ลิงก์ไฟล์รูป) · ชีตละเกม (คอลัมน์ค่าพลังเต็มของเกมนั้น) · เด็ค · การ์ดในเด็ค — ทุกชีตเป็น Excel Table กรอง/เรียงได้ · ถ้าไฟล์เปิดค้างใน Excel จะเขียนเป็น `การ์ดทั้งหมด <วันเวลา>.xlsx` แทน

แท็บ **การ์ดทั้งหมด** ในหน้านำเข้าเด็ค: ตารางการ์ดทุกใบ (รูป · ชื่อ · ชุด/เลข · rarity · ประเภท · ค่าพลัง · จำนวนใบรวม · เจ้าของ/เด็ค) กรองตามเกม/เจ้าของ ค้นชื่อ/รหัส/rarity · การ์ดที่หาข้อมูลไม่ได้แสดง "ไม่มีข้อมูล" (ชื่อจากไฟล์รูป) · `POST /api/library/rebuild` อ่าน `raw/` ของทุกเด็คใหม่ (เมื่อ `catalog.py` รองรับแหล่งใหม่) โดยไม่ดาวน์โหลดซ้ำ

**ต่อท้ายอย่างไร:** SCM เรียงการ์ดตามชื่อไฟล์แบบ natural sort จึงตั้งชื่อไฟล์ที่คัดลอกเข้างานเป็น `zz<รอบ>-<ชื่อเดิม>` (เช่น `zz01-1LightningBolt1.png`) ให้อยู่หลังการ์ดที่มีอยู่และหลังเด็คที่ต่อท้ายก่อนหน้า · หน้า/หลังเฉพาะใบใช้ชื่อเดียวกันจึงยังจับคู่กัน · "แทนที่ทั้งหมด" ลบ `front/` กับ `double_sided/` ของงาน แต่หลังร่วมยังอยู่

เบื้องหลัง: ใช้ `plugins/<เกม>/fetch.py` ของ SCM ตรง ๆ ไม่แก้ upstream — `tools/run_plugin.py` แทนค่า `front_directory` / `double_sided_directory` (ชี้ `game/`) ด้วยโฟลเดอร์ในคลังเด็ค แล้วเรียก `cli` · ฟอร์มตัวเลือกสร้างจาก `cli.params` ของแต่ละ plugin (เช่น MTG: `--prefer_lang`, `--prefer_extra_art`, `--tokens`) · รูปแบบลิงก์/รหัส (`DIRECT_FORMATS` ใน `fetch_bridge.py`: `url`, `*_url`, `elestrals`, `ydke`) ส่งบรรทัดแรกให้ plugin ตรง ๆ รูปแบบอื่นเขียนเป็น `decklist/deck.txt` เสมอ (เดิมดูจากว่าขึ้นต้น `http`/`ydke` ทำให้ deck id ของ Elestrals ถูกเขียนเป็นไฟล์แล้วดึงไม่ได้) · ภาพบนการ์ดเลือกเกม: `static/assets/games/<plugin>.jpg` ดาวน์โหลดลงเครื่องด้วย `tools/fetch_game_art.py` (`start.bat` รันให้ครั้งแรก) — ภาพเป็นลิขสิทธิ์ของผู้ผลิตเกมจึงไม่เก็บใน git · ได้ 15 จาก 22 เกม ที่เหลือ (และถ้าไม่ได้รันสคริปต์) แสดงตัวย่อ+สีประจำเกม

API:
| | |
|---|---|
| `GET /api/plugins` | เกมทั้งหมด + รูปแบบ + ตัวเลือก + `art` (มีภาพตัวอย่างไหม) |
| `POST /api/decks/fetch {plugin, format, deck, options, owner, name, force}` | เริ่มดึง (409 `busy` ถ้ามีเด็คอื่นกำลังดึง) · เคยดึงแล้วตอบเด็คเดิม + `reused: true` เว้นแต่ `force` |
| `PATCH /api/decks/<id> {owner, name}` | เปลี่ยนเจ้าของ/ชื่อเด็ค (ย้ายโฟลเดอร์ + อัปเดตคลังการ์ดและ Excel) |
| `GET /api/decks` · `GET /api/decks/<id>` | ประวัติ · สถานะ/ไฟล์/log ของเด็ค |
| `POST /api/decks/<id>/cancel` · `DELETE /api/decks/<id>` | หยุด · ลบ |
| `POST /api/decks/<id>/use {job, mode: append\|replace}` | คัดลอกเข้างาน ตอบ `added` |
| `GET /api/decks/<id>/img/<front\|ds>/<name>` | ภาพในคลัง |
| `GET /api/library/cards?game=&owner=&q=` | การ์ดทั้งหมด (`owner=-` = ไม่ระบุเจ้าของ) |
| `GET /api/library/owners` · `GET /api/library/img/<path>` | รายชื่อเจ้าของ · รูปในคลังการ์ด |
| `GET /api/library/xlsx` · `POST /api/library/rebuild` | ดาวน์โหลด Excel · อ่านข้อมูลการ์ดของทุกเด็คใหม่ |

| เกม | ดึงรูปจาก |
|---|---|
| MTG | Scryfall API (PNG 745×1040 ≈ 300 ppi) · `mpcfill_xml` → MPCFill (Google Apps Script, มี bleed แล้ว ใช้ครอป 3 มม.) · `url` → Moxfield/Archidekt ฯลฯ ผ่าน `mtg_parser` |
| Pokémon | Limitless (CDN) / pokemontcg.io |
| Yu-Gi-Oh! | YGOPRODeck images |
| Lorcana | Lorcast · One Piece / Gundam / Digimon / FFTCG / Bushiroad → เว็บทางการของผู้ผลิต |
| อื่น ๆ | Altered, ArkhamDB, Ashes, Echoes of Astra, Elestrals, FaB (cardvault), Grand Archive, KeyForge (Master Vault / Archon Arcana), LotR (RingsDB/Hall of Beorn), Netrunner (NetrunnerDB), Riftbound (Piltover Archive), Sorcery (Curiosa), SWU (swu-db) |

หมายเหตุ: ต้องต่ออินเทอร์เน็ต · Scryfall มีมุมโค้งไม่มี bleed (SCM แนะนำ `--extend_corners 3.5mm`) · proxy ใช้เล่นกันเอง/ทดสอบเด็คเท่านั้น ห้ามขายหรือใช้ในทัวร์นาเมนต์

## โครงสร้าง

```
webui/
  app.py              Flask server + API
  scm_bridge.py       จุดเดียวที่เรียกโค้ด SCM (อ่านอย่างเดียว ไม่แก้ไฟล์ upstream)
  presets.py          preset ของ SRK (เลย์เอาต์ช่องไฟเอง เป็น specialty `srk-*`)
  templates/          .studio3 ของ preset (สร้างจาก DXF ใน Studio) + README ขั้นตอน
  fetch_bridge.py     อ่าน plugins/ ทั้งหมด (format + option จาก click) และรัน plugin ในโปรเซสลูก
  capture.py          HTTP cache ถาวร + เก็บ JSON ที่ plugin ได้ลง <เด็ค>/raw/ (ติดตั้งในโปรเซสของ plugin)
  catalog.py          คลังการ์ด: อ่าน raw/ → SQLite (ชื่อ ค่าพลัง rarity) · ค้นเพิ่ม 5 เกม · ส่งออก Excel
  static/             index.html · app.css · app.js · i18n.js (ไทย/อังกฤษ) · assets/
  tools/make_demo_cards.py   สร้างการ์ดตัวอย่าง (กรอบ 2 มม. ไว้ดูการตัดเหลื่อม)
  tools/run_plugin.py        รัน plugins/<เกม>/fetch.py โดยชี้โฟลเดอร์ output ไปที่คลังเด็ค
  tools/fetch_game_art.py    ดาวน์โหลดภาพการ์ดตัวอย่างของแต่ละเกม → static/assets/games/ (ไม่เก็บใน git)
  jobs/               ไฟล์งาน (ไม่เก็บใน git)
  data/               ค่าชดเชย, แผ่น mark, data/library/ = คลังเด็ค + คลังการ์ด + Excel + HTTP cache (ไม่เก็บใน git)
```

ข้อจำกัดที่รู้แล้ว
- สร้างได้ทีละงาน (SCM อ่าน `./data/offset_data.json` ตาม cwd จึงล็อกไว้) · แต่ละครั้งเรียก SCM สองรอบ (PDF + PNG) ใช้เวลาราว 2–3 วินาทีต่อการ์ด 8 ใบ
- เปิด `start.bat` ซ้ำไม่ได้: ถ้ามี SCM Studio เปิดอยู่แล้วจะเปิดเบราว์เซอร์ไปตัวเดิม (Windows ยอมให้สองโปรแกรม bind พอร์ตเดียวกัน คำขอจะแบ่งไปคนละตัว จึงต้องเช็กก่อน) · ปิดหน้าต่างดำเพื่อหยุดเซิร์ฟเวอร์
- ยังไม่มีการชดเชยสเกลเครื่องพิมพ์ (ปัญหาการ์ดคอลัมน์ขวาตัดเหลื่อม)
- หลังร่วมได้ 1 รูป (ถ้ามีหลายรูป SCM จะถามในคอนโซล)
- การ์ดที่มีหลังเฉพาะใบถูกวางท้ายชุด ตามลำดับของ SCM (หน้าเว็บแสดงลำดับเดียวกัน)
- ยังไม่แปลง DXF → `.studio3` (`dxf_to_studio3.py` ต้องคุม Silhouette Studio บนหน้าจอจริง)

## Fork นี้กับ repo หลัก

- `upstream` = Alan-Cha/silhouette-card-maker (ปิด push ไว้) · `origin` = fork ของเรา
- repo คู่กัน: **SRK-CARD-Studio** (`D:\SalmonRK\Card`, private) แอป photocard หลายชั้น เอกสารค้นคว้า CAMEO 5 อยู่ที่นั่น (`docs/RESEARCH-cameo5.md` §15–19) · บันทึกงานของทั้งสอง repo อยู่ใน `docs/WORKLOG.md` ของ repo นั้น
- `main` เก็บให้ตรงกับ upstream · งานเว็บอยู่ใน branch `srk-webui` และอยู่ในโฟลเดอร์ `webui/` เท่านั้น จึงไม่ชนกับไฟล์ของ upstream

ดึงอัปเดตจาก repo หลัก:
```
git checkout main
git fetch upstream
git merge --ff-only upstream/main
git push origin main
git checkout srk-webui
git merge main
```
ถ้า upstream เปลี่ยนชื่อฟังก์ชันที่ใช้อยู่ (`generate_pdf`, `generate_layout`, `load_layout_config`, `template_name`, `save_offset`) แก้ที่ `scm_bridge.py` ไฟล์เดียว · ตรวจหลัง merge ด้วย:
```
venv\Scripts\python -c "import sys; sys.path.insert(0,'webui'); import scm_bridge as b; print(b.resolve_layout('a4','standard')['slots'][0])"
```
ค่าที่ถูกสำหรับ A4 standard คือ x 20.659, y 16.425 มม. (ตรงกับ `a4-standard-v5.studio3`)

## แบบหน้าจอ (redesign)

แบบ desktop 1440 ทั้ง 8 หน้า (3 workspace) อยู่ใน repo SRK-CARD-Studio — ตอนนี้นำมาใช้แล้วเฉพาะโครง 3 workspace, หน้านำเข้าเด็ค/ประวัติ และหน้าตั้งค่าเครื่อง (ขั้น ①–④ ยังใช้แผงฟอร์มเดิม):
- ขั้นตอนทำงาน, ลิงก์ Figma/Stitch, เครื่องมือ: `D:\SalmonRK\Card\docs\SCM-REDESIGN.md` · จัดหมวดฟีเจอร์: `docs/SCM-FEATURES.md`
- ข้อมูลที่หน้าจอต้องตรง (ดึงจาก `static/i18n.js` + `/api/options`): `docs/SCM-INFO-SPEC.md` — ถ้าแก้ข้อความ/ตัวเลือกในเว็บ ให้แก้ spec ด้วย
- HTML ต้นแบบ: `design/scm/web/` · Figma page "SCM · Desktop 1440" (9 หน้าจอ รวม D2b ไร้ขอบ) และ "SCM · Foundations" (สี Light/Dark ตรงกับตัวแปรใน `static/app.css`, ตัวอักษร, ไอคอน) — ถ้าแก้สีใน `app.css` ให้แก้ variable ใน Figma ด้วย
