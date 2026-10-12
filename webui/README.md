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
| **A นำเข้าเด็ค** | เลือกเกมจากภาพ (22 เกม) → วางเด็คลิสต์/ลิงก์ → ดึงรูป → ตรวจผล (จำนวนต่อใบ, สองหน้า, คำเตือน) → "ใช้กับแผ่นพิมพ์" · แท็บ **ประวัติ** เปิดเด็คเก่าใช้ซ้ำได้ไม่ต้องดึงใหม่ | ดึงลงคลัง `webui/data/decks/<id>/` ก่อน แล้วค่อยคัดลอกเข้างาน (ดูด้านล่าง) |
| **B ① รูปการ์ด** | ลากวางรูปหน้า, หลังร่วม 1 รูป, หลังเฉพาะใบ (สองหน้า), การ์ดตัวอย่าง 8 ใบ, ปุ่มไปนำเข้าเด็ค | เก็บในโฟลเดอร์งานของตัวเอง `webui/jobs/<id>/` ไม่แตะ `game/` |
| **B ② ขนาดและกระดาษ** | เลือกกระดาษ/ขนาดการ์ด (เฉพาะคู่ที่มีเลย์เอาต์), borderless, mark 3/4 จุด, ยืด/ครอป, ขยาย bleed | คำนวณด้วย `page_manager.generate_layout` ตัวเดียวกับ SCM แสดงบนพื้นที่จำลองแผ่นรองตัดตามสเกลจริง |
| **B ③ สร้างไฟล์พิมพ์** | ข้อความกำกับ, เส้นขอบ, ใช้ค่าชดเชยสองหน้า, ภาพตัวอย่างทุกหน้า · ดาวน์โหลด PDF, PNG (zip), ชุดสำหรับ Studio (zip) | เรียก `utilities.generate_pdf` สองรอบ (PDF + `output_images=True`) แล้วฝัง DPI ให้ PNG |
| **B ④ พิมพ์และตัด** | เลือกเส้นทาง "พิมพ์จาก PDF" หรือ "พิมพ์จาก Silhouette Studio" แต่ละทางมีขั้นตอนของตัวเอง · ดาวน์โหลด `.studio3` ของขนาดที่ใช้, ตารางใบมีด | ใช้ `cutting_templates/` ของ SCM |
| **C ตั้งค่าเครื่อง** | ชดเชยสองหน้า (แผ่นคาลิเบรต + X/Y/มุม) · คลังไฟล์ตัด `.studio3` ทุกขนาดตามกระดาษ (★ = ขนาดที่ใช้อยู่) · แผ่น mark อย่างเดียว · ตารางใบมีด | `calibration/`, `GET /api/templates?paper=`, `/api/marks` |

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

## นำเข้าเด็ค (ดึงรูปการ์ดอัตโนมัติ + ประวัติ)

แถบบน → **นำเข้าเด็ค** · เลือกเกม (ภาพการ์ดตัวอย่าง 15 เกม, เกมที่ไม่มีภาพใช้ตัวย่อ+สีประจำเกม) → รูปแบบเด็ค → วางข้อความ export หรือลิงก์แชร์บรรทัดเดียว (แสดงจำนวนใบโดยประมาณ) → **ดึงรูปการ์ด** → หน้าตรวจผลแสดงภาพทุกแบบ จำนวน ×N ป้ายสองหน้า คำเตือนจาก log → เลือก **ต่อท้ายการ์ดเดิม** (ค่าเริ่มต้น) หรือ **แทนที่ทั้งหมด** → **ใช้กับแผ่นพิมพ์** แล้วไปขั้น ① ทันที · "แก้เด็ค" กลับไปแก้ข้อความเดิม · ดึงได้ทีละเด็ค กดหยุดได้

**คลังเด็ค = ประวัติ:** ทุกการดึงเก็บที่ `webui/data/decks/<id>/` (`deck.json` = เกม/รูปแบบ/ข้อความเด็ค/ตัวเลือก/เวลา/สถานะ/คำเตือน, `front/`, `double_sided/`, `log.txt`) · แท็บ ประวัติ เปิดเด็คเก่าได้ทันทีและใช้ซ้ำโดยไม่ต้องดาวน์โหลดอีก · ลบได้ทีละเด็ค · ไม่เก็บใน git (`data/` อยู่ใน `.gitignore`)

**ต่อท้ายอย่างไร:** SCM เรียงการ์ดตามชื่อไฟล์แบบ natural sort จึงตั้งชื่อไฟล์ที่คัดลอกเข้างานเป็น `zz<รอบ>-<ชื่อเดิม>` (เช่น `zz01-1LightningBolt1.png`) ให้อยู่หลังการ์ดที่มีอยู่และหลังเด็คที่ต่อท้ายก่อนหน้า · หน้า/หลังเฉพาะใบใช้ชื่อเดียวกันจึงยังจับคู่กัน · "แทนที่ทั้งหมด" ลบ `front/` กับ `double_sided/` ของงาน แต่หลังร่วมยังอยู่

เบื้องหลัง: ใช้ `plugins/<เกม>/fetch.py` ของ SCM ตรง ๆ ไม่แก้ upstream — `tools/run_plugin.py` แทนค่า `front_directory` / `double_sided_directory` (ชี้ `game/`) ด้วยโฟลเดอร์ในคลังเด็ค แล้วเรียก `cli` · ฟอร์มตัวเลือกสร้างจาก `cli.params` ของแต่ละ plugin (เช่น MTG: `--prefer_lang`, `--prefer_extra_art`, `--tokens`) · ข้อความหลายบรรทัดเขียนเป็น `decklist/deck.txt`, บรรทัดเดียวที่ขึ้นต้น `http(s)://`/`ydke://` ส่งเป็นลิงก์ · ภาพบนการ์ดเลือกเกม: `static/assets/games/<plugin>.jpg` ดาวน์โหลดลงเครื่องด้วย `tools/fetch_game_art.py` (`start.bat` รันให้ครั้งแรก) — ภาพเป็นลิขสิทธิ์ของผู้ผลิตเกมจึงไม่เก็บใน git · ได้ 15 จาก 22 เกม ที่เหลือ (และถ้าไม่ได้รันสคริปต์) แสดงตัวย่อ+สีประจำเกม

API:
| | |
|---|---|
| `GET /api/plugins` | เกมทั้งหมด + รูปแบบ + ตัวเลือก + `art` (มีภาพตัวอย่างไหม) |
| `POST /api/decks/fetch {plugin, format, deck, options}` | เริ่มดึง (409 `busy` ถ้ามีเด็คอื่นกำลังดึง) |
| `GET /api/decks` · `GET /api/decks/<id>` | ประวัติ · สถานะ/ไฟล์/log ของเด็ค |
| `POST /api/decks/<id>/cancel` · `DELETE /api/decks/<id>` | หยุด · ลบ |
| `POST /api/decks/<id>/use {job, mode: append\|replace}` | คัดลอกเข้างาน ตอบ `added` |
| `GET /api/decks/<id>/img/<front\|ds>/<name>` | ภาพในคลัง |

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
  fetch_bridge.py     อ่าน plugins/ ทั้งหมด (format + option จาก click) และรัน plugin ในโปรเซสลูก
  static/             index.html · app.css · app.js · i18n.js (ไทย/อังกฤษ) · assets/
  tools/make_demo_cards.py   สร้างการ์ดตัวอย่าง (กรอบ 2 มม. ไว้ดูการตัดเหลื่อม)
  tools/run_plugin.py        รัน plugins/<เกม>/fetch.py โดยชี้โฟลเดอร์ output ไปที่คลังเด็ค
  tools/fetch_game_art.py    ดาวน์โหลดภาพการ์ดตัวอย่างของแต่ละเกม → static/assets/games/ (ไม่เก็บใน git)
  jobs/               ไฟล์งาน (ไม่เก็บใน git)
  data/               ค่าชดเชย, แผ่น mark, data/decks/ = คลังเด็คที่ดึงแล้ว (ไม่เก็บใน git)
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
- HTML ต้นแบบ: `design/scm/web/` · Figma page "SCM · Desktop 1440"
